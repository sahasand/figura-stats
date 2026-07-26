"""Comparator spine tests.

Two tiers of vector:
  * pure-function vectors for `close_enough` / `classify_cell` / `display_key` /
    `parse_ratio_tsv`, and
  * whole-case vectors that build a throwaway `cases/` + `results/` tree in
    tmp_path and run `compare_case` end to end, so the wiring (dispatch,
    exact-targets contract, finding taxonomy) is pinned too.

The base fixture is a deliberately PASSING case: every mutation test starts
from it and breaks exactly one thing, so an assertion can name the code it
expects without the fixture leaking unrelated findings.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

from compare import (
    DISPOSITIONS,
    classify_cell,
    classify_gc_effect_display,
    classify_km_logrank_display,
    classify_km_median_display,
    close_enough,
    compare_case,
    display_key,
    format_effect_gc,
    format_median_km,
    format_num_gc,
    format_p_gc,
    format_p_km,
    format_ratio_cell,
    gc_display_half_ulp,
    main,
    parse_gc_posthoc,
    parse_gc_test_clause,
    parse_km_group_median,
    parse_km_logrank,
    parse_ratio_tsv,
    reportable,
)

EN = "–"  # en dash U+2013, the character R's sprintf writes


# --------------------------------------------------------------------------
# fixture builders
# --------------------------------------------------------------------------

TSV = "\n".join([
    "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)",
    "arm (reference: Standard care)\t\t",
    f"New treatment\t1.02 (0.63{EN}1.66, p=0.932)\t0.50 (0.28{EN}0.91, p=0.023)",
    f"age (per 10 units)\t1.56 (1.19{EN}2.05, p=0.001)\t1.69 (1.26{EN}2.26, p<0.001)",
]) + "\n\nMultivariable logistic regression (n = 320, 91 events)."


def _base():
    """A case whose three artifacts agree everywhere. Real Figura numbers."""
    case = {
        "id": "c1",
        "figure": "logistic",
        "roles": {"outcome": "complication", "covariates": ["arm", "age"]},
        "options": {
            "event_value": "Yes",
            "ref_levels": {"arm": "Standard care"},
            "increments": {"age": 10},
        },
        "display": {"kind": "ratio_table"},
        "exact_targets": [
            "adjusted_or", "adjusted_ci", "adjusted_p", "n", "n_event", "n_dropped",
        ],
    }
    figura = {"id": "c1", "text": TSV, "code": "# script"}
    exact_terms = {
        "armNew treatment": {
            "est": 0.504705489501454, "se": 0.300877969145577,
            "lo": 0.279850141376259, "hi": 0.910228702691347,
            "p": 0.0230493060981703,
        },
        "age": {
            "est": 1.6884329138071, "se": 0.148515872657346,
            "lo": 1.26201508640443, "hi": 2.2589315572679,
            "p": 0.000420453419555958,
        },
    }
    exact = {
        "id": "c1", "figure": "logistic", "terms": copy.deepcopy(exact_terms),
        "n": 320, "n_event": 91, "n_dropped": 0,
    }
    unadjusted = {
        "armNew treatment": {
            "est": 1.0203, "se": 0.2481, "lo": 0.6301, "hi": 1.6551, "p": 0.9321,
        },
        "age": {
            "est": 1.5601, "se": 0.1391, "lo": 1.1902, "hi": 2.0451, "p": 0.0011,
        },
    }
    python = {
        "id": "c1", "figure": "logistic",
        "terms": copy.deepcopy(exact_terms),
        "unadjusted": copy.deepcopy(unadjusted),
        "display_terms": {
            "arm:New treatment": copy.deepcopy(exact_terms["armNew treatment"]),
            "age": copy.deepcopy(exact_terms["age"]),
        },
        "display_unadjusted": {
            "arm:New treatment": copy.deepcopy(unadjusted["armNew treatment"]),
            "age": copy.deepcopy(unadjusted["age"]),
        },
        "n": 320, "n_event": 91, "n_dropped": 0, "c_statistic": 0.6812,
    }
    return case, figura, exact, python


def _tree(tmp_path, case, figura, exact, python):
    cases = tmp_path / "cases" / case["id"]
    results = tmp_path / "results"
    cases.mkdir(parents=True)
    results.mkdir(exist_ok=True)
    (cases / "case.json").write_text(json.dumps(case))
    cid = case["id"]
    (results / f"{cid}.figura.json").write_text(json.dumps(figura))
    (results / f"{cid}.figura-exact.json").write_text(json.dumps(exact))
    (results / f"{cid}.python.json").write_text(json.dumps(python))
    return results, tmp_path / "cases"


def _run(tmp_path, mutate=None):
    case, figura, exact, python = _base()
    if mutate is not None:
        mutate(case, figura, exact, python)
    results, cases = _tree(tmp_path, case, figura, exact, python)
    return compare_case(case["id"], results=results, cases=cases)


def _codes(report):
    return [f["code"] for f in report["findings"]]


def _by_code(report, code):
    return [f for f in report["findings"] if f["code"] == code]


# --------------------------------------------------------------------------
# tolerance + display rule (the main text's four vectors, shapes adapted)
# --------------------------------------------------------------------------

def test_close_enough_uses_relative_tolerance():
    assert close_enough(1.0000001, 1.0)
    assert not close_enough(1.001, 1.0)
    assert close_enough(0.0, 0.0)


def test_format_ratio_cell_restates_the_display_rule():
    assert format_ratio_cell(3.3201, 2.4012, 4.591, 4e-7) == f"3.32 (2.40{EN}4.59, p<0.001)"
    assert format_ratio_cell(0.5047, 0.2799, 0.9102, 0.02305) == f"0.50 (0.28{EN}0.91, p=0.023)"


def test_identical_display_is_a_pass():
    f = classify_cell(
        term="stage:II", figura_cell=f"3.32 (2.40{EN}4.59, p<0.001)",
        python={"est": 3.3201, "lo": 2.4012, "hi": 4.5910, "p": 0.0000004},
    )
    assert f["code"] == "PASS"
    assert f["disposition"] == "pass"


def test_rounding_only_difference_is_an_artifact_not_a_defect():
    # 3.325 sits exactly on the 2-dp rounding boundary: Python renders "3.33",
    # Figura showed "3.32". The two true values are indistinguishable at
    # display precision, so this is a formatting artifact, not arithmetic.
    f = classify_cell(
        term="stage:II", figura_cell=f"3.32 (2.40{EN}4.59, p<0.001)",
        python={"est": 3.3250001, "lo": 2.4012, "hi": 4.5910, "p": 0.0000004},
    )
    assert f["code"] == "DISPLAY_ARTIFACT"
    assert f["disposition"] == "review"


def test_real_disagreement_is_a_defect():
    f = classify_cell(
        term="stage:II", figura_cell=f"3.32 (2.40{EN}4.59, p<0.001)",
        python={"est": 1.10, "lo": 0.80, "hi": 1.50, "p": 0.6},
    )
    assert f["code"] == "DEFECT"
    assert f["disposition"] == "defect"


# --------------------------------------------------------------------------
# addendum 6: the p-part is never an artifact
# --------------------------------------------------------------------------

def test_p_part_difference_is_a_defect_not_an_artifact():
    # est/lo/hi land on the same displayed strings; only p moves. Even though
    # p=0.030 vs p=0.031 is one display step, a p disagreement is a defect.
    f = classify_cell(
        term="stage:II", figura_cell=f"2.01 (1.07{EN}3.78, p=0.030)",
        python={"est": 2.0094, "lo": 1.0693, "hi": 3.7762, "p": 0.0314},
    )
    assert f["code"] == "DEFECT"
    assert "p-value" in f["note"]


def test_p_threshold_crossing_is_a_defect():
    f = classify_cell(
        term="age", figura_cell=f"1.69 (1.26{EN}2.26, p<0.001)",
        python={"est": 1.6884, "lo": 1.2620, "hi": 2.2589, "p": 0.0012},
    )
    assert f["code"] == "DEFECT"


# --------------------------------------------------------------------------
# addendum 7: unreportable disposition
# --------------------------------------------------------------------------

def test_both_paths_agree_unreportable_is_a_pass():
    f = classify_cell(
        term="grp:B", figura_cell="not reliably estimated",
        python={"est": 2.9e8, "lo": 1e-12, "hi": 8.4e17, "p": 0.99},
    )
    assert f["code"] == "PASS"
    assert "unreportable" in f["note"]


def test_figura_suppressed_but_python_reportable_is_a_defect():
    f = classify_cell(
        term="grp:B", figura_cell="not reliably estimated",
        python={"est": 1.5, "lo": 1.1, "hi": 2.1, "p": 0.01},
    )
    assert f["code"] == "DEFECT"


def test_python_unreportable_but_figura_showed_a_number_is_a_defect():
    f = classify_cell(
        term="grp:B", figura_cell=f"1.50 (1.10{EN}2.10, p=0.010)",
        python={"est": float("inf"), "lo": 1.1, "hi": float("inf"), "p": 0.01},
    )
    assert f["code"] == "DEFECT"


def test_reportable_restates_the_shared_reliability_rule():
    # Mirror of R/dispatch.R .ratio_reportable and validate.logistic.reportable.
    assert reportable({"est": 1.5, "lo": 1.1, "hi": 2.1})
    assert not reportable({"est": float("inf"), "lo": 1.0, "hi": 2.0})
    assert not reportable({"est": 2.0, "lo": 1e-9, "hi": 2.0})
    assert not reportable({"est": 2.0, "lo": 1.0, "hi": 1e7})


# --------------------------------------------------------------------------
# addendum 3: the real TSV row model
# --------------------------------------------------------------------------

def test_level_rows_key_as_covariate_colon_level_with_a_space_bearing_level():
    case, figura, _exact, _python = _base()
    rows, findings = parse_ratio_tsv(figura["text"], case)
    assert findings == []
    assert [r["key"] for r in rows] == ["arm:New treatment", "age"]
    assert rows[0]["adj"] == f"0.50 (0.28{EN}0.91, p=0.023)"
    assert rows[1]["unadj"] == f"1.56 (1.19{EN}2.05, p=0.001)"


def test_reference_header_row_carrying_cells_is_a_finding(tmp_path):
    def mutate(case, figura, exact, python):
        figura["text"] = figura["text"].replace(
            "arm (reference: Standard care)\t\t",
            f"arm (reference: Standard care)\t1.00 (1.00{EN}1.00, p=1.000)\t",
        )
    report = _run(tmp_path, mutate)
    hits = [f for f in report["findings"] if "reference header row" in f["note"]]
    assert hits, _codes(report)
    assert hits[0]["code"] == "DEFECT"


def test_level_row_without_a_preceding_header_is_flagged():
    case, figura, _exact, _python = _base()
    text = figura["text"].replace("arm (reference: Standard care)\t\t\n", "")
    rows, findings = parse_ratio_tsv(text, case)
    assert [f["code"] for f in findings] == ["MISSING_QUANTITY"]
    assert [r["key"] for r in rows] == ["age"]


def test_numeric_row_label_must_match_the_declared_increment():
    case, figura, _exact, _python = _base()
    text = figura["text"].replace("age (per 10 units)", "age (per 5 units)")
    rows, findings = parse_ratio_tsv(text, case)
    assert [f["code"] for f in findings] == ["DEFECT"]
    assert [r["key"] for r in rows] == ["arm:New treatment", "age"]


def test_a_table_header_of_the_wrong_shape_is_a_finding():
    # The parser reads the header positionally (label, unadjusted, adjusted);
    # a header that is not that shape means the columns may not be what the
    # rest of this function assumes, so it is recorded, never assumed away.
    case, figura, _exact, _python = _base()
    text = figura["text"].replace(
        "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)",
        "Variable\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)",
    )
    _rows, findings = parse_ratio_tsv(text, case)
    assert [f["code"] for f in findings] == ["DEFECT"]
    assert findings[0]["quantity"] == "table header"


def test_a_row_without_three_cells_is_a_finding_not_a_crash():
    case, figura, _exact, _python = _base()
    text = figura["text"].replace(
        f"New treatment\t1.02 (0.63{EN}1.66, p=0.932)\t0.50 (0.28{EN}0.91, p=0.023)",
        f"New treatment\t0.50 (0.28{EN}0.91, p=0.023)",  # one cell short
    )
    rows, findings = parse_ratio_tsv(text, case)
    assert [f["code"] for f in findings] == ["DEFECT"]
    assert findings[0]["quantity"] == "displayed row"
    assert [r["key"] for r in rows] == ["age"]  # the malformed row is not kept


def test_two_rows_resolving_to_the_same_key_is_a_finding():
    # Two level rows under one reference header with the same label would let
    # a later row silently overwrite an earlier one in rows_by_key, so one
    # comparison would quietly stand in for two.
    case, figura, _exact, _python = _base()
    dup = f"New treatment\t1.02 (0.63{EN}1.66, p=0.932)\t0.50 (0.28{EN}0.91, p=0.023)"
    text = figura["text"].replace(dup, dup + "\n" + dup)
    rows, findings = parse_ratio_tsv(text, case)
    assert [f["code"] for f in findings] == ["DEFECT"]
    assert "same key" in findings[0]["note"]
    assert [r["key"] for r in rows] == ["arm:New treatment", "arm:New treatment", "age"]


# --------------------------------------------------------------------------
# addendum 4: longest-covariate-prefix term splitting
# --------------------------------------------------------------------------

def test_longest_prefix_wins_when_one_covariate_prefixes_another():
    covs = ["stage", "stage2"]
    assert display_key("stageII", covs) == "stage:II"
    assert display_key("stage2II", covs) == "stage2:II"
    assert display_key("stage2", covs) == "stage2"  # exact match: numeric term


def test_levels_with_spaces_are_never_split_on_whitespace():
    assert display_key("armNew treatment", ["arm", "age"]) == "arm:New treatment"
    assert display_key("age", ["arm", "age"]) == "age"
    assert display_key("siteSt Mary's North", ["site"]) == "site:St Mary's North"


def test_path_b_derives_the_same_keys_as_the_comparator():
    """cli.py owns Path B's key derivation; compare.py owns Path A's. They are
    deliberately separate implementations — this pins them to one answer."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
    try:
        from validate.cli import display_label
    except ImportError as exc:  # pragma: no cover - env guard, never silent
        pytest.skip(f"Path B not importable: {exc}")
    covs = ["arm", "age", "stage", "stage2"]
    for term in ("armNew treatment", "age", "stageII", "stage2III", "stage2"):
        assert display_label(term, covs) == display_key(term, covs)


# --------------------------------------------------------------------------
# whole-case wiring
# --------------------------------------------------------------------------

def test_the_agreeing_fixture_passes_everything(tmp_path):
    report = _run(tmp_path)
    assert report["findings"] == []
    assert report["passed"] is True
    assert report["targets_met"] is True
    # 3 counts + 4 displayed cells + 2 terms x 5 exact quantities + 2 script cells
    assert report["compared"] == 19


def test_count_mismatch_when_both_sides_present_and_unequal(tmp_path):
    report = _run(tmp_path, lambda c, f, e, p: p.__setitem__("n_dropped", 3))
    hits = _by_code(report, "COUNT_MISMATCH")
    assert len(hits) == 1
    assert hits[0]["quantity"] == "n_dropped"
    assert hits[0]["disposition"] == "defect"
    assert report["findings"][0]["code"] == "COUNT_MISMATCH"  # ranked first


def test_absent_count_is_missing_quantity_not_a_silent_skip(tmp_path):
    report = _run(tmp_path, lambda c, f, e, p: p.pop("n_event"))
    hits = _by_code(report, "MISSING_QUANTITY")
    # Two distinct statements, both wanted: the artifact is missing a count,
    # and the exact target that count was the sole evidence for is unmet.
    assert [h["quantity"] for h in hits] == ["n_event", "n_event"]
    assert "did not report n_event" in hits[0]["note"]
    assert "zero comparisons performed" in hits[1]["note"]
    assert report["targets_met"] is False


def test_python_display_term_with_no_tsv_row_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        python["display_terms"]["ghost:X"] = {
            "est": 1.0, "se": 0.1, "lo": 0.9, "hi": 1.1, "p": 0.5,
        }
    report = _run(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY") if f["term"] == "ghost:X"]
    assert hits and "no displayed row" in hits[0]["note"]


def test_tsv_row_with_no_python_term_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        python["display_terms"].pop("age")
    report = _run(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY") if f["term"] == "age"]
    assert hits


def test_exact_tier_term_missing_on_one_side_is_missing_quantity(tmp_path):
    report = _run(tmp_path, lambda c, f, e, p: p["terms"].pop("age"))
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["term"] == "age" and f["quantity"] == "exact term"]
    assert hits


def test_exact_tier_se_beyond_tolerance_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["terms"]["age"]["se"] *= 1.001  # lo/hi untouched: se stands alone
    report = _run(tmp_path, mutate)
    hits = _by_code(report, "DEFECT")
    assert [h["quantity"] for h in hits] == ["se"]
    assert hits[0]["term"] == "age"


def test_script_divergence_when_the_exported_r_disagrees_with_the_screen(tmp_path):
    def mutate(case, figura, exact, python):
        # Only the exported script's harvest moves: Path B still matches the
        # screen, so this can only be caught by the Path-A-internal check.
        exact["terms"]["armNew treatment"]["est"] = 0.75
        exact["terms"]["armNew treatment"]["lo"] = 0.42
        exact["terms"]["armNew treatment"]["hi"] = 1.35
    report = _run(tmp_path, mutate)
    hits = _by_code(report, "SCRIPT_DIVERGENCE")
    assert len(hits) == 1
    assert hits[0]["term"] == "arm:New treatment"
    assert hits[0]["disposition"] == "defect"


def test_unwired_exact_target_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        case["exact_targets"].append("median_survival")
    report = _run(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["quantity"] == "median_survival"]
    assert hits
    assert report["targets_met"] is False


def test_an_empty_table_never_passes_vacuously(tmp_path):
    def mutate(case, figura, exact, python):
        figura["text"] = figura["text"].split("\n")[0] + "\n\nmethods."
        exact["terms"] = {}
        python["terms"] = {}
        python["display_terms"] = {}
        python["display_unadjusted"] = {}
    report = _run(tmp_path, mutate)
    assert report["passed"] is False
    notes = [f["note"] for f in _by_code(report, "MISSING_QUANTITY")]
    assert any("no estimate rows" in n for n in notes)
    assert any("no terms to compare" in n for n in notes)


def test_unknown_display_kind_exits_loudly(tmp_path):
    # table1 (Task 11) is still pending as of this test; km_summary (Task 9)
    # and gc_summary (Task 10) are both implemented now, so neither can stand
    # in here any longer.
    def mutate(case, figura, exact, python):
        case["display"]["kind"] = "table1"
    with pytest.raises(SystemExit) as excinfo:
        _run(tmp_path, mutate)
    assert "table1" in str(excinfo.value)


def test_a_figura_artifact_with_no_text_field_is_missing_quantity(tmp_path):
    # The displayed artifact is the whole display tier's input. Losing it must
    # read as "nothing was compared", never as a traceback and never as a pass.
    report = _run(tmp_path, lambda c, f, e, p: f.pop("text"))
    notes = [x["note"] for x in _by_code(report, "MISSING_QUANTITY")]
    assert any("no `text` field" in n for n in notes), _codes(report)
    assert report["passed"] is False


# --------------------------------------------------------------------------
# malformed Path B cells: the display tier reports, it does not raise
# --------------------------------------------------------------------------

def test_a_path_b_cell_missing_a_quantity_is_missing_quantity_not_a_keyerror():
    f = classify_cell(
        term="age", figura_cell=f"1.69 (1.26{EN}2.26, p<0.001)",
        python={"est": 1.6884, "lo": 1.2620},  # no hi, no p
    )
    assert f["code"] == "MISSING_QUANTITY"
    assert f["disposition"] == "defect"


def test_a_path_b_cell_with_a_non_numeric_value_is_missing_quantity():
    f = classify_cell(
        term="age", figura_cell=f"1.69 (1.26{EN}2.26, p<0.001)",
        python={"est": "NA", "lo": 1.2620, "hi": 2.2589, "p": 0.0004},
    )
    assert f["code"] == "MISSING_QUANTITY"


def test_a_malformed_display_cell_is_not_credited_as_a_comparison(tmp_path):
    def mutate(case, figura, exact, python):
        python["display_terms"]["age"].pop("p")
    report = _run(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["quantity"] == "displayed adjusted cell"]
    assert len(hits) == 1 and hits[0]["term"] == "age"
    # 19 in the agreeing fixture: the uncomparable cell must not be counted.
    assert report["compared"] == 18


# --------------------------------------------------------------------------
# km_summary: the free-text methods sentence + curve/median/log-rank tiers
# --------------------------------------------------------------------------

EN2 = "–"

# A real methods sentence shape, mirroring an actual run of km-twoarm
# (verified end to end via run-figura.R/run-script.R): the HR clause is not
# a km_summary target and is never parsed by anything under test here.
KM_TEXT = (
    "HR 1.23 (New treatment vs Standard care; 95% CI 0.80" + EN2 + "1.90); "
    "log-rank p = 0.045. Median survival: New treatment 24.0 Time; "
    "Standard care not reached."
)


def _base_km():
    """A km_summary case whose three artifacts agree everywhere."""
    case = {
        "id": "k1",
        "figure": "km",
        "roles": {"time": "followup_months", "status": "status", "group": "group"},
        "options": {"event_value": "Death"},
        "display": {"kind": "km_summary"},
        "exact_targets": [
            "median_survival", "logrank_p", "curve", "n", "n_event", "n_dropped",
        ],
    }
    figura = {"id": "k1", "text": KM_TEXT, "code": "# script"}
    curve = {
        "New treatment": [
            {"t": 5.0, "surv": 0.9, "at_risk": 20},
            {"t": 10.0, "surv": 0.8, "at_risk": 18},
        ],
        "Standard care": [
            {"t": 6.0, "surv": 0.95, "at_risk": 22},
        ],
    }
    medians = {"New treatment": 24.0, "Standard care": None}
    exact = {
        "id": "k1", "figure": "km",
        "curve": copy.deepcopy(curve), "medians": copy.deepcopy(medians),
        "logrank_p": 0.045, "n": 42, "n_event": 20, "n_dropped": 0,
    }
    python = {
        "id": "k1", "figure": "km",
        "curve": copy.deepcopy(curve), "medians": copy.deepcopy(medians),
        "logrank_p": 0.045, "n": 42, "n_event": 20, "n_dropped": 0,
    }
    return case, figura, exact, python


def _run_km(tmp_path, mutate=None):
    case, figura, exact, python = _base_km()
    if mutate is not None:
        mutate(case, figura, exact, python)
    results, cases = _tree(tmp_path, case, figura, exact, python)
    return compare_case(case["id"], results=results, cases=cases)


# -- pure-function vectors ---------------------------------------------------

def test_format_p_km_uses_spaces_unlike_the_ratio_table_rule():
    assert format_p_km(0.045) == "p = 0.045"
    assert format_p_km(0.0004) == "p < 0.001"


def test_format_median_km_is_one_decimal_place():
    assert format_median_km(24.0) == "24.0"
    assert format_median_km(3.14159) == "3.1"


def test_parse_km_logrank_finds_the_lowercase_embedded_phrase():
    assert parse_km_logrank(KM_TEXT) == "p = 0.045"
    assert parse_km_logrank("Log-rank p < 0.001. Median survival: A 1.0 Time.") \
        == "p < 0.001"
    assert parse_km_logrank("no log-rank phrase here") is None


def test_parse_km_group_median_finds_a_reached_value():
    shown = parse_km_group_median(KM_TEXT, "New treatment")
    assert shown == {"value": 24.0, "raw": "New treatment 24.0"}


def test_parse_km_group_median_finds_not_reached():
    shown = parse_km_group_median(KM_TEXT, "Standard care")
    assert shown == {"not_reached": True, "raw": "Standard care not reached"}


def test_parse_km_group_median_returns_none_for_an_absent_group():
    assert parse_km_group_median(KM_TEXT, "Placebo") is None


def test_classify_km_median_display_both_not_reached_is_a_pass():
    f = classify_km_median_display(
        "Standard care", {"not_reached": True, "raw": "Standard care not reached"},
        None)
    assert f["code"] == "PASS"


def test_classify_km_median_display_one_sided_not_reached_is_a_defect():
    # Addendum: one-sided not-reached is a DEFECT, not smoothed into an
    # artifact — Figura says not reached, Python computed a real value.
    f = classify_km_median_display(
        "Standard care", {"not_reached": True, "raw": "Standard care not reached"},
        30.0)
    assert f["code"] == "DEFECT"


def test_classify_km_median_display_rounding_only_is_an_artifact():
    # 24.0500001 sits just past the 1-dp rounding boundary: Python renders
    # "24.1", Figura showed "24.0". The two true values are indistinguishable
    # at display precision (KM_DISPLAY_HALF_ULP = 0.05), so this is a
    # formatting artifact, not arithmetic — mirrors the ratio-table version
    # of this same test at its own (2-dp) boundary.
    f = classify_km_median_display(
        "New treatment", {"value": 24.0, "raw": "New treatment 24.0"}, 24.0500001)
    assert f["code"] == "DISPLAY_ARTIFACT"


def test_classify_km_median_display_real_disagreement_is_a_defect():
    f = classify_km_median_display(
        "New treatment", {"value": 24.0, "raw": "New treatment 24.0"}, 5.0)
    assert f["code"] == "DEFECT"


def test_classify_km_logrank_display_p_difference_is_never_an_artifact():
    f = classify_km_logrank_display("p = 0.045", 0.046)
    assert f["code"] == "DEFECT"
    assert "never a display artifact" in f["note"]


# -- whole-case wiring --------------------------------------------------------

def test_km_agreeing_fixture_passes_everything(tmp_path):
    report = _run_km(tmp_path)
    assert report["findings"] == []
    assert report["passed"] is True
    assert report["targets_met"] is True
    # 3 counts + curve(2 pts * 2 quantities + 1 pt * 2 quantities = 6)
    # + 2 medians (exact) + 1 logrank (exact) + 2 medians (display)
    # + 1 logrank (display) + 2 medians (script) + 1 logrank (script)
    # = 3 + 6 + 2 + 1 + 2 + 1 + 2 + 1 = 18
    assert report["compared"] == 18


def test_km_one_sided_not_reached_is_a_defect_end_to_end(tmp_path):
    def mutate(case, figura, exact, python):
        python["medians"]["Standard care"] = 30.0
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "DEFECT")
    assert any(h["term"] == "Standard care" and h["quantity"] == "median_survival"
               for h in hits)


def test_km_unmatched_curve_point_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        python["curve"]["New treatment"].append(
            {"t": 99.0, "surv": 0.1, "at_risk": 1})
    report = _run_km(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["quantity"] == "curve t=99"]
    assert hits
    assert hits[0]["term"] == "New treatment"


def test_km_curve_surv_mismatch_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["curve"]["New treatment"][0]["surv"] = 0.5
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "DEFECT")
    assert any("survival estimate" in h["note"] for h in hits)


def test_km_curve_at_risk_mismatch_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["curve"]["New treatment"][0]["at_risk"] = 999
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "DEFECT")
    assert any("number at risk" in h["note"] for h in hits)


def test_km_group_present_only_on_one_side_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        python["curve"]["Extra group"] = [{"t": 1.0, "surv": 1.0, "at_risk": 5}]
    report = _run_km(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["term"] == "Extra group"]
    assert hits


def test_km_logrank_p_beyond_tolerance_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["logrank_p"] = 0.9
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "DEFECT")
    assert any(h["quantity"] == "logrank_p" for h in hits)


def test_km_displayed_logrank_p_disagreement_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        figura["text"] = figura["text"].replace(
            "log-rank p = 0.045", "log-rank p = 0.046")
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "DEFECT")
    assert any(h["quantity"] == "displayed logrank" for h in hits)


def test_km_script_median_disagrees_with_displayed_text_is_script_divergence(tmp_path):
    # Path-A-internal: exact.json (the exported script's own harvest) says
    # a different median than what the screen displayed. Python is left
    # UNTOUCHED (still 24.0, still agreeing with the display) so this finding
    # can only come from the script tier, never the exact or display tiers.
    def mutate(case, figura, exact, python):
        exact["medians"]["New treatment"] = 30.0
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "SCRIPT_DIVERGENCE")
    assert any(h["term"] == "New treatment"
               and h["quantity"] == "exported script median" for h in hits)


def test_km_script_logrank_disagrees_with_displayed_text_is_script_divergence(tmp_path):
    def mutate(case, figura, exact, python):
        exact["logrank_p"] = 0.5  # displayed text still says "p = 0.045"
    report = _run_km(tmp_path, mutate)
    hits = _by_code(report, "SCRIPT_DIVERGENCE")
    assert any(h["quantity"] == "exported script logrank" for h in hits)


def test_km_count_mismatch(tmp_path):
    report = _run_km(tmp_path, lambda c, f, e, p: p.__setitem__("n_event", 99))
    hits = _by_code(report, "COUNT_MISMATCH")
    assert len(hits) == 1 and hits[0]["quantity"] == "n_event"


def test_km_unwired_exact_target_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        case["exact_targets"].append("adjusted_or")  # never credited by km_summary
    report = _run_km(tmp_path, mutate)
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["quantity"] == "adjusted_or"]
    assert hits
    assert report["targets_met"] is False


def test_km_absent_text_field_is_missing_quantity_not_a_crash(tmp_path):
    report = _run_km(tmp_path, lambda c, f, e, p: f.pop("text"))
    notes = [x["note"] for x in _by_code(report, "MISSING_QUANTITY")]
    assert any("no `text` field" in n for n in notes)
    assert report["passed"] is False


# --------------------------------------------------------------------------
# the exact-targets contract is never vacuous
# --------------------------------------------------------------------------

def test_a_case_with_no_exact_targets_is_never_targets_met(tmp_path):
    # all([]) is True, so an absent contract would otherwise publish
    # `targets_met: true` and exit 0 while guaranteeing nothing.
    report = _run(tmp_path, lambda c, f, e, p: c.pop("exact_targets"))
    assert report["targets_met"] is False
    assert report["passed"] is False
    hits = [f for f in _by_code(report, "MISSING_QUANTITY")
            if f["quantity"] == "exact_targets"]
    assert hits and "no coverage contract" in hits[0]["note"]


def test_adjusted_hr_alias_credits_the_same_est_quantity_as_adjusted_or(tmp_path):
    # Cox cases declare `adjusted_hr` where logistic cases declare
    # `adjusted_or`; both alias to the same `est` quantity, so a Cox case's
    # exact_targets contract is discharged by the identical comparison
    # adjusted_or already performs — no Cox-specific wiring needed here.
    def mutate(case, figura, exact, python):
        case["exact_targets"] = [
            "adjusted_hr" if t == "adjusted_or" else t
            for t in case["exact_targets"]
        ]
    report = _run(tmp_path, mutate)
    assert report["targets_met"] is True
    assert report["targets"]["adjusted_hr"] > 0
    assert "adjusted_or" not in report["targets"]


def test_an_empty_exact_targets_list_is_treated_the_same(tmp_path):
    report = _run(tmp_path, lambda c, f, e, p: c.__setitem__("exact_targets", []))
    assert report["targets_met"] is False
    assert [f["quantity"] for f in _by_code(report, "MISSING_QUANTITY")] == \
        ["exact_targets"]


# --------------------------------------------------------------------------
# published output is strict JSON, and the vocabulary is honest
# --------------------------------------------------------------------------

def test_a_nan_is_never_published_as_bare_json(tmp_path):
    case, figura, exact, python = _base()
    exact["terms"]["age"]["est"] = float("nan")
    results, cases = _tree(tmp_path, case, figura, exact, python)
    with pytest.raises(SystemExit) as excinfo:
        main([case["id"]], results=results, cases=cases)
    assert "non-finite" in str(excinfo.value)
    # Nothing partial on disk: a bare NaN in findings.json is not valid JSON
    # and would break every downstream reader.
    assert not (results / "findings.json").exists()


def test_the_published_vocabulary_declares_only_codes_that_are_emitted():
    src = (Path(__file__).resolve().parents[1] / "compare.py").read_text()
    for code in DISPOSITIONS:
        emitted = re.search(r"finding\(\s*[\"']" + code + r"[\"']", src)
        assert emitted, f"{code} is declared but never emitted"
    # EXACT_PASS was in the plan's table; nothing emits it, because the exact
    # tier counts an agreement in `compared` and stays silent, exactly as the
    # display tier does for PASS.
    assert "EXACT_PASS" not in DISPOSITIONS


def test_the_agreeing_fixture_still_writes_parseable_findings(tmp_path):
    case, figura, exact, python = _base()
    results, cases = _tree(tmp_path, case, figura, exact, python)
    assert main([case["id"]], results=results, cases=cases) == 0
    published = json.loads((results / "findings.json").read_text())
    assert published["total_findings"] == 0
    assert published["cases"][0]["targets_met"] is True


def test_missing_artifact_exits_loudly(tmp_path):
    case, figura, exact, python = _base()
    results, cases = _tree(tmp_path, case, figura, exact, python)
    (results / "c1.python.json").unlink()
    with pytest.raises(SystemExit) as excinfo:
        compare_case("c1", results=results, cases=cases)
    assert "c1.python.json" in str(excinfo.value)


# ==========================================================================
# gc_summary (Task 10) — group comparison
#
# The two fixtures below are real sentence shapes, taken verbatim from actual
# runs of the three shipped gc cases through run-figura.R (numeric/parametric
# with a Tukey post-hoc, and categorical with none), so the parsers under test
# are built against ground truth rather than a guess at the format.
# ==========================================================================

GC_TEXT_NUMERIC = (
    "biomarker_normal across groups: High dose 58.4 ± 7.71; "
    "Low dose 54.1 ± 7.82; Placebo 45.7 ± 7.7. "
    "one-way ANOVA (Welch) (approximately normal (Shapiro–Wilk "
    "p = 0.876)): p < 0.001, eta-squared = 0.321 (95% CI 0.197 to 0.421). "
    "Tukey HSD, significant pairs: Low dose-High dose, Placebo-High dose, "
    "Placebo-Low dose."
)

GC_TEXT_CATEGORICAL = (
    "responder by group (n = 150): Pearson chi-square test: p < 0.001, "
    "Cramér's V = 0.421."
)

GC_TEXT_DIRTY = (
    "site_code across groups: High dose 3 (2" + EN2 + "3); Low dose 2 (1"
    + EN2 + "2); Placebo 2 (1" + EN2 + "2). Kruskal–Wallis test "
    "(departs from normal (Shapiro–Wilk p < 0.001)): p < 0.001, "
    "epsilon-squared = 0.404. Dunn's test (BH-adjusted), significant pairs: "
    "High dose-Low dose, High dose-Placebo. 4 row(s) with missing values were "
    "excluded."
)


def _base_gc():
    """A gc_summary case whose three artifacts agree everywhere. Real numbers
    from the shipped groupcompare-numeric case."""
    case = {
        "id": "g1",
        "figure": "groupcompare",
        "roles": {"outcome": "biomarker_normal", "group": "arm"},
        "options": {"plot": "box", "test": "auto"},
        "display": {"kind": "gc_summary"},
        "exact_targets": ["test_p", "test_statistic", "n", "n_dropped"],
    }
    figura = {"id": "g1", "text": GC_TEXT_NUMERIC, "code": "# script"}
    per_group = {"High dose": 50, "Low dose": 50, "Placebo": 50}
    exact = {
        "id": "g1", "figure": "groupcompare",
        "test_p": 3.7310304535906173e-12,
        "test_statistic": 34.835216031005963,
        "n": 150, "n_per_group": dict(per_group), "n_dropped": 0,
    }
    python = {
        "id": "g1", "figure": "groupcompare",
        "test_name": "one-way ANOVA (Welch)",
        "p_value": 3.7310304535906173e-12,
        "statistic": 34.835216031005963,
        "effect": {"label": "eta-squared", "value": 0.32102532801259492,
                   "lo": 0.19740468951566092, "hi": 0.42138945932347194},
        "n": 150, "n_per_group": dict(per_group), "n_dropped": 0,
        "posthoc": {"test": "Tukey HSD",
                    "significant_pairs": ["Low dose-High dose",
                                          "Placebo-High dose",
                                          "Placebo-Low dose"]},
    }
    return case, figura, exact, python


def _base_gc_categorical():
    """A gc_summary case on the categorical branch: chi-square, an effect with
    no interval, and NO post-hoc sentence on either side."""
    case = {
        "id": "g2",
        "figure": "groupcompare",
        "roles": {"outcome": "responder", "group": "arm"},
        "options": {"plot": "box", "test": "auto"},
        "display": {"kind": "gc_summary"},
        "exact_targets": ["test_p", "test_statistic", "n", "n_dropped"],
    }
    figura = {"id": "g2", "text": GC_TEXT_CATEGORICAL, "code": "# script"}
    per_group = {"High dose": 50, "Low dose": 50, "Placebo": 50}
    exact = {
        "id": "g2", "figure": "groupcompare",
        "test_p": 1.6476905471843762e-06,
        "test_statistic": 26.63227183775129,
        "n": 150, "n_per_group": dict(per_group), "n_dropped": 0,
    }
    python = {
        "id": "g2", "figure": "groupcompare",
        "test_name": "Pearson chi-square test",
        "p_value": 1.6476905471843762e-06,
        "statistic": 26.63227183775129,
        "effect": {"label": "Cramér's V", "value": 0.42136501862202791,
                   "lo": None, "hi": None},
        "n": 150, "n_per_group": dict(per_group), "n_dropped": 0,
        "posthoc": None,
    }
    return case, figura, exact, python


def _base_gc_dirty():
    """The dirty case: a numeric-LOOKING categorical outcome that the app
    routes to the NUMERIC branch, non-parametric, with Dunn pair names in the
    opposite order from Tukey's."""
    case = {
        "id": "g3",
        "figure": "groupcompare",
        "roles": {"outcome": "site_code", "group": "arm"},
        "options": {"plot": "box", "test": "auto"},
        "display": {"kind": "gc_summary"},
        "exact_targets": ["test_p", "test_statistic", "n", "n_dropped"],
    }
    figura = {"id": "g3", "text": GC_TEXT_DIRTY, "code": "# script"}
    per_group = {"High dose": 48, "Low dose": 49, "Placebo": 49}
    exact = {
        "id": "g3", "figure": "groupcompare",
        "test_p": 1.8682142740540386e-13,
        "test_statistic": 58.617246335913329,
        "n": 146, "n_per_group": dict(per_group), "n_dropped": 4,
    }
    python = {
        "id": "g3", "figure": "groupcompare",
        "test_name": "Kruskal–Wallis test",
        "p_value": 1.8682142740540386e-13,
        "statistic": 58.617246335913329,
        "effect": {"label": "epsilon-squared", "value": 0.40425687128216087,
                   "lo": None, "hi": None},
        "n": 146, "n_per_group": dict(per_group), "n_dropped": 4,
        "posthoc": {"test": "Dunn's test (BH-adjusted)",
                    "significant_pairs": ["High dose-Low dose",
                                          "High dose-Placebo"]},
    }
    return case, figura, exact, python


def _run_gc(tmp_path, mutate=None, base=_base_gc):
    case, figura, exact, python = base()
    if mutate is not None:
        mutate(case, figura, exact, python)
    results, cases = _tree(tmp_path, case, figura, exact, python)
    return compare_case(case["id"], results=results, cases=cases)


# -- pure-function vectors ---------------------------------------------------

def test_format_p_gc_matches_groupcompares_own_pfmt():
    assert format_p_gc(0.876) == "p = 0.876"
    assert format_p_gc(0.0004) == "p < 0.001"
    # Exactly 0.001 is NOT below the threshold.
    assert format_p_gc(0.001) == "p = 0.001"


def test_format_num_gc_is_three_significant_figures_not_decimal_places():
    # Probes checked against R itself, by running
    #   Rscript -e 'f <- function(v) format(signif(v, 3), trim=TRUE,
    #                 scientific=FALSE, drop0trailing=TRUE); f(<v>)'
    # rather than trusting R/summarize.R's own worked examples: that source
    # comment claims "1.125 -> 1.13", and R actually prints 1.12 (`signif`
    # inherits IEEE round-half-to-even on an exactly-representable tie). The
    # comment is wrong; the code is what ships, so the code is what is
    # restated here. Python's `round` reproduces R's tie behaviour on every
    # probe below, including 1.125 -> 1.12 and 1.135 -> 1.14.
    assert format_num_gc(250000) == "250000"
    assert format_num_gc(1.125) == "1.12"
    assert format_num_gc(1.135) == "1.14"
    assert format_num_gc(0.00123) == "0.00123"
    assert format_num_gc(7.7) == "7.7"
    assert format_num_gc(1e-8) == "0.00000001"  # never scientific notation
    assert format_num_gc(0.999999) == "1"
    # Real values from the shipped cases.
    assert format_num_gc(0.32102532801259492) == "0.321"
    assert format_num_gc(0.40425687128216087) == "0.404"
    assert format_num_gc(58.4123) == "58.4"
    assert format_num_gc(0) == "0"


def test_gc_display_half_ulp_scales_with_magnitude():
    # Three significant figures: the step is 0.001 near 0.3 and 0.1 near 58.
    assert gc_display_half_ulp(0.321) == pytest.approx(0.0005)
    assert gc_display_half_ulp(58.4) == pytest.approx(0.05)
    assert gc_display_half_ulp(250000) == pytest.approx(500.0)


def test_format_effect_gc_renders_with_and_without_an_interval():
    assert format_effect_gc({"label": "eta-squared",
                             "value": 0.32102532801259492,
                             "lo": 0.19740468951566092,
                             "hi": 0.42138945932347194}) == \
        "eta-squared = 0.321 (95% CI 0.197 to 0.421)"
    assert format_effect_gc({"label": "epsilon-squared", "value": 0.404,
                             "lo": None, "hi": None}) == \
        "epsilon-squared = 0.404"


def test_parse_gc_test_clause_reads_past_a_nested_reason():
    # "one-way ANOVA (Welch)" has parentheses in the NAME, and the routing
    # reason that follows has parentheses nested one deep.
    clause = parse_gc_test_clause(GC_TEXT_NUMERIC, "one-way ANOVA (Welch)")
    assert clause["p_text"] == "p < 0.001"
    assert clause["effect"] == "eta-squared = 0.321 (95% CI 0.197 to 0.421)"


def test_parse_gc_test_clause_reads_the_reasonless_categorical_shape():
    clause = parse_gc_test_clause(GC_TEXT_CATEGORICAL,
                                  "Pearson chi-square test")
    assert clause["p_text"] == "p < 0.001"
    assert clause["effect"] == "Cramér's V = 0.421"


def test_parse_gc_test_clause_returns_none_for_the_wrong_test_name():
    assert parse_gc_test_clause(GC_TEXT_NUMERIC, "Kruskal–Wallis test") \
        is None


def test_parse_gc_posthoc_reads_tukey_pairs():
    ph = parse_gc_posthoc(GC_TEXT_NUMERIC)
    assert ph["test"] == "Tukey HSD"
    assert ph["significant_pairs"] == ["Low dose-High dose",
                                       "Placebo-High dose", "Placebo-Low dose"]


def test_parse_gc_posthoc_reads_dunn_pairs_in_the_opposite_naming_order():
    # Tukey names a pair "<later>-<earlier>"; Dunn names it
    # "<earlier>-<later>". Both conventions are real and must survive intact.
    ph = parse_gc_posthoc(GC_TEXT_DIRTY)
    assert ph["test"] == "Dunn's test (BH-adjusted)"
    assert ph["significant_pairs"] == ["High dose-Low dose",
                                       "High dose-Placebo"]


def test_parse_gc_posthoc_distinguishes_no_pairs_from_no_posthoc():
    none_ran = parse_gc_posthoc(GC_TEXT_CATEGORICAL)
    assert none_ran is None  # the categorical branch never runs a post-hoc
    ran_but_empty = parse_gc_posthoc(
        "y across groups: A 1; B 2. Kruskal–Wallis test (r): p = 0.040, "
        "epsilon-squared = 0.1. Dunn's test (BH-adjusted): no pairwise "
        "differences at 0.05.")
    assert ran_but_empty["significant_pairs"] == []
    assert ran_but_empty["test"] == "Dunn's test (BH-adjusted)"


def test_classify_gc_effect_display_rounding_only_is_an_artifact():
    # 0.3215001 renders as "0.322" but sits within half a 3-significant-figure
    # step of the displayed 0.321 — the step near 0.321 is 0.001, so the half
    # step is 0.0005, widened by the exact tier's own slack exactly as
    # `display_agrees`/`display_agrees_km` do. A formatting artifact, not
    # arithmetic.
    f = classify_gc_effect_display(
        "eta-squared = 0.321 (95% CI 0.197 to 0.421)",
        {"label": "eta-squared", "value": 0.3215001,
         "lo": 0.19740468951566092, "hi": 0.42138945932347194},
        ["High dose", "Low dose", "Placebo"])
    assert f["code"] == "DISPLAY_ARTIFACT"


def test_classify_gc_effect_display_real_disagreement_is_a_defect():
    f = classify_gc_effect_display(
        "eta-squared = 0.321 (95% CI 0.197 to 0.421)",
        {"label": "eta-squared", "value": 0.9,
         "lo": 0.8, "hi": 0.95},
        ["High dose", "Low dose", "Placebo"])
    assert f["code"] == "DEFECT"


def test_classify_gc_effect_display_a_different_effect_label_is_a_defect():
    f = classify_gc_effect_display(
        "eta-squared = 0.321 (95% CI 0.197 to 0.421)",
        {"label": "epsilon-squared", "value": 0.321, "lo": None, "hi": None},
        ["High dose", "Low dose", "Placebo"])
    assert f["code"] == "DEFECT"


def test_classify_gc_effect_display_two_groups_require_the_direction_clause():
    two = ["New treatment", "Standard care"]
    ok = classify_gc_effect_display(
        "Cohen's d = 1.66 (95% CI 0.643 to 2.68) "
        "(Standard care vs New treatment)",
        {"label": "Cohen's d", "value": 1.659052981163355,
         "lo": 0.64285125388414688, "hi": 2.67525470844256308}, two)
    assert ok["code"] == "PASS"
    reversed_clause = classify_gc_effect_display(
        "Cohen's d = 1.66 (95% CI 0.643 to 2.68) "
        "(New treatment vs Standard care)",
        {"label": "Cohen's d", "value": 1.659052981163355,
         "lo": 0.64285125388414688, "hi": 2.67525470844256308}, two)
    assert reversed_clause["code"] == "DEFECT"


def test_classify_gc_effect_display_a_2x2_odds_ratio_clause_is_missing_quantity():
    # compare_groups' pinned return shape carries no odds ratio, so a 2x2
    # categorical case cannot be judged until the contract is extended. That
    # must be reported, never waved through.
    f = classify_gc_effect_display(
        "Cramér's V = 0.421; odds ratio for responder=No, A vs B = 2.5 "
        "(95% CI 1.2 to 5.2)",
        {"label": "Cramér's V", "value": 0.42136501862202791,
         "lo": None, "hi": None},
        ["A", "B"])
    assert f["code"] == "MISSING_QUANTITY"
    assert "odds-ratio clause" in f["note"]


def test_classify_gc_effect_display_missing_path_b_effect_is_missing_quantity():
    f = classify_gc_effect_display("eta-squared = 0.321", None,
                                   ["A", "B", "C"])
    assert f["code"] == "MISSING_QUANTITY"


# -- whole-case wiring --------------------------------------------------------

def test_gc_agreeing_numeric_fixture_passes_everything(tmp_path):
    report = _run_gc(tmp_path)
    assert report["findings"] == []
    assert report["passed"] is True
    assert report["targets_met"] is True
    # 2 counts (n, n_dropped) + 3 per-group counts + test_p + test_statistic
    # + displayed test name + displayed p + displayed effect
    # + post-hoc presence + post-hoc test + post-hoc pair set
    # + script-tier p = 2 + 3 + 2 + 3 + 3 + 1 = 14
    assert report["compared"] == 14


def test_gc_agreeing_categorical_fixture_passes_everything(tmp_path):
    report = _run_gc(tmp_path, base=_base_gc_categorical)
    assert report["findings"] == []
    assert report["targets_met"] is True
    # Same as above minus the two post-hoc comparisons that only happen when a
    # post-hoc sentence is present (test + pair set): 14 - 2 = 12.
    assert report["compared"] == 12


def test_gc_agreeing_dirty_fixture_passes_everything(tmp_path):
    # Dirty-case routing: a numeric-LOOKING categorical outcome that the app
    # sends down the NUMERIC branch. The comparator must judge it as the
    # Kruskal-Wallis it is, with Dunn pair names in Dunn's own order.
    report = _run_gc(tmp_path, base=_base_gc_dirty)
    assert report["findings"] == []
    assert report["targets_met"] is True
    assert report["compared"] == 14


def test_gc_dirty_case_routed_to_the_wrong_branch_is_a_defect(tmp_path):
    # If Path B "helpfully" treated the zero-padded site codes as categorical,
    # it would report a chi-square where the app ran a Kruskal-Wallis. The
    # displayed sentence then carries no clause for Path B's test name.
    def mutate(case, figura, exact, python):
        python["test_name"] = "Pearson chi-square test"
    report = _run_gc(tmp_path, mutate, base=_base_gc_dirty)
    codes = _codes(report)
    assert "DEFECT" in codes
    assert any("different tests" in f["note"] for f in report["findings"])


def test_gc_posthoc_pair_set_mismatch_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["posthoc"]["significant_pairs"] = ["Low dose-High dose"]
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"] if f["quantity"] == "post-hoc pairs"]
    assert len(hits) == 1
    assert hits[0]["code"] == "DEFECT"
    assert "only Figura" in hits[0]["note"]


def test_gc_posthoc_pair_names_in_the_wrong_order_are_a_defect(tmp_path):
    # Dunn's convention is "<earlier>-<later>". An implementation that
    # normalised both post-hoc methods to Tukey's "<later>-<earlier>" spelling
    # produces pair names the app never displayed.
    def mutate(case, figura, exact, python):
        python["posthoc"]["significant_pairs"] = ["Low dose-High dose",
                                                  "Placebo-High dose"]
    report = _run_gc(tmp_path, mutate, base=_base_gc_dirty)
    hits = [f for f in report["findings"] if f["quantity"] == "post-hoc pairs"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"


def test_gc_posthoc_missing_on_the_python_side_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["posthoc"] = None
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"]
            if f["quantity"] == "post-hoc presence"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"
    assert "Figura reports a post-hoc" in hits[0]["note"]


def test_gc_posthoc_missing_on_the_figura_side_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        figura["text"] = GC_TEXT_NUMERIC.split(" Tukey HSD")[0]
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"]
            if f["quantity"] == "post-hoc presence"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"
    assert "Python reports a post-hoc" in hits[0]["note"]


def test_gc_posthoc_ran_but_empty_is_not_the_same_as_no_posthoc(tmp_path):
    # "a post-hoc ran and nothing survived" vs "no post-hoc ran" are different
    # claims. Figura says the first, Python says the second.
    def mutate(case, figura, exact, python):
        figura["text"] = GC_TEXT_NUMERIC.replace(
            "Tukey HSD, significant pairs: Low dose-High dose, "
            "Placebo-High dose, Placebo-Low dose.",
            "Tukey HSD: no pairwise differences at 0.05.")
        python["posthoc"] = None
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"]
            if f["quantity"] == "post-hoc presence"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"


def test_gc_test_p_beyond_tolerance_is_a_defect(tmp_path):
    # NOTE the mutation is a whole-number-scale move, not a small relative
    # one: this case's real p is 3.7e-12, far below the comparator's ABS_TOL
    # floor of 1e-9, so `close_enough` cannot distinguish it from ANY other
    # equally tiny p. That floor is the shared, pre-existing convention for
    # every branch (km's logrank_p has the same property); the discriminating
    # evidence for a gc case at this magnitude is `test_statistic`, which is
    # O(10-60) and compares relatively.
    def mutate(case, figura, exact, python):
        python["p_value"] = 0.04
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"] if f["quantity"] == "test_p"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"


def test_gc_test_statistic_beyond_tolerance_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        python["statistic"] = exact["test_statistic"] + 1.0
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"] if f["quantity"] == "test_statistic"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"


def test_gc_fisher_null_statistic_on_both_sides_is_not_missing_quantity(tmp_path):
    # Fisher's exact test carries no statistic AT ALL: R's htest has no
    # `statistic` component. Both paths reporting null is a real agreement.
    # The case therefore must not declare test_statistic as an exact target —
    # and the next test proves that declaring it anyway fails loudly.
    def mutate(case, figura, exact, python):
        case["exact_targets"] = ["test_p", "n", "n_dropped"]
        figura["text"] = ("responder by group (n = 8): Fisher's exact test: "
                          "p = 0.486, Cramér's V = 0.5.")
        exact["test_statistic"] = None
        exact["test_p"] = 0.4857142857142856
        python["test_name"] = "Fisher's exact test"
        python["statistic"] = None
        python["p_value"] = 0.4857142857142856
        python["effect"] = {"label": "Cramér's V", "value": 0.5,
                            "lo": None, "hi": None}
        python["posthoc"] = None
    report = _run_gc(tmp_path, mutate, base=_base_gc_categorical)
    assert report["findings"] == []
    assert report["targets_met"] is True


def test_gc_fisher_case_declaring_test_statistic_fails_its_coverage_contract(tmp_path):
    # Same fixture as above but with test_statistic left in exact_targets: no
    # comparison can be performed for it, so the coverage contract is unmet.
    def mutate(case, figura, exact, python):
        figura["text"] = ("responder by group (n = 8): Fisher's exact test: "
                          "p = 0.486, Cramér's V = 0.5.")
        exact["test_statistic"] = None
        exact["test_p"] = 0.4857142857142856
        python["test_name"] = "Fisher's exact test"
        python["statistic"] = None
        python["p_value"] = 0.4857142857142856
        python["effect"] = {"label": "Cramér's V", "value": 0.5,
                            "lo": None, "hi": None}
        python["posthoc"] = None
    report = _run_gc(tmp_path, mutate, base=_base_gc_categorical)
    assert report["targets_met"] is False
    assert any(f["quantity"] == "test_statistic"
               and f["code"] == "MISSING_QUANTITY" for f in report["findings"])


def test_gc_a_non_fisher_null_statistic_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        exact["test_statistic"] = None
        python["statistic"] = None
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"] if f["quantity"] == "test_statistic"]
    assert len(hits) >= 1
    assert hits[0]["code"] == "MISSING_QUANTITY"


def test_gc_one_sided_statistic_on_a_fisher_test_is_a_defect(tmp_path):
    def mutate(case, figura, exact, python):
        # A Fisher case correctly declares no test_statistic target, so the
        # only finding left is the one under test.
        case["exact_targets"] = ["test_p", "n", "n_dropped"]
        figura["text"] = ("responder by group (n = 8): Fisher's exact test: "
                          "p = 0.486, Cramér's V = 0.5.")
        exact["test_statistic"] = None
        exact["test_p"] = 0.4857142857142856
        python["test_name"] = "Fisher's exact test"
        python["statistic"] = 3.2
        python["p_value"] = 0.4857142857142856
        python["effect"] = {"label": "Cramér's V", "value": 0.5,
                            "lo": None, "hi": None}
        python["posthoc"] = None
    report = _run_gc(tmp_path, mutate, base=_base_gc_categorical)
    hits = [f for f in report["findings"] if f["quantity"] == "test_statistic"]
    assert len(hits) == 1 and hits[0]["code"] == "DEFECT"


def test_gc_displayed_p_disagreement_is_never_an_artifact(tmp_path):
    def mutate(case, figura, exact, python):
        figura["text"] = GC_TEXT_NUMERIC.replace("p < 0.001", "p = 0.040")
        exact["test_p"] = 0.04
    report = _run_gc(tmp_path, mutate)
    display_hits = [f for f in report["findings"]
                    if f["quantity"] == "displayed p"]
    assert len(display_hits) == 1 and display_hits[0]["code"] == "DEFECT"
    assert "never a display artifact" in display_hits[0]["note"]


def test_gc_script_p_disagreeing_with_the_screen_is_script_divergence(tmp_path):
    # Mutate ONLY the harvest, leaving Path B agreeing with the display, so
    # the finding can only have come from the Path-A-internal script tier.
    def mutate(case, figura, exact, python):
        exact["test_p"] = 0.5
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"] if f["code"] == "SCRIPT_DIVERGENCE"]
    assert len(hits) == 1
    assert hits[0]["quantity"] == "exported script p"


def test_gc_count_mismatch(tmp_path):
    report = _run_gc(tmp_path, lambda c, f, e, p: p.update(n=149))
    assert "COUNT_MISMATCH" in _codes(report)


def test_gc_per_group_count_mismatch_is_a_count_mismatch(tmp_path):
    def mutate(case, figura, exact, python):
        python["n_per_group"]["Placebo"] = 49
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"] if f["quantity"] == "n_per_group"]
    assert len(hits) == 1 and hits[0]["code"] == "COUNT_MISMATCH"
    assert hits[0]["term"] == "Placebo"


def test_gc_a_group_present_on_only_one_side_is_missing_quantity(tmp_path):
    def mutate(case, figura, exact, python):
        python["n_per_group"]["Extra arm"] = 5
    report = _run_gc(tmp_path, mutate)
    hits = [f for f in report["findings"]
            if f["quantity"] == "n_per_group" and f["term"] == "Extra arm"]
    assert len(hits) == 1 and hits[0]["code"] == "MISSING_QUANTITY"


def test_gc_absent_text_field_is_missing_quantity_not_a_crash(tmp_path):
    report = _run_gc(tmp_path, lambda c, f, e, p: f.pop("text"))
    notes = [x["note"] for x in _by_code(report, "MISSING_QUANTITY")]
    assert any("no `text` field" in n for n in notes)
    assert report["passed"] is False


def test_gc_absent_python_test_name_is_missing_quantity(tmp_path):
    report = _run_gc(tmp_path, lambda c, f, e, p: p.pop("test_name"))
    notes = [x["note"] for x in _by_code(report, "MISSING_QUANTITY")]
    assert any("reported no test name" in n for n in notes)


def test_gc_an_unlocatable_test_clause_records_the_downstream_holes(tmp_path):
    # A wrong test name must never MASK a wrong effect size sitting behind it:
    # the clause is the anchor for the displayed p, the displayed effect, and
    # the script tier's p, so losing it makes all three MISSING_QUANTITY
    # alongside the test-name DEFECT itself.
    def mutate(case, figura, exact, python):
        python["test_name"] = "one-way ANOVA"   # classical, not "(Welch)"
        python["effect"]["value"] = 0.9         # also wrong, and must show up
    report = _run_gc(tmp_path, mutate)
    quantities = {f["quantity"]: f["code"] for f in report["findings"]}
    assert quantities["displayed test name"] == "DEFECT"
    for q in ("displayed p", "displayed effect", "exported script p"):
        assert quantities[q] == "MISSING_QUANTITY", q


def test_gc_no_silent_skips_every_continue_follows_a_recorded_finding():
    """The file's own DESIGN RULE, enforced mechanically for the gc branch:
    every `continue` inside compare_gc_summary must be immediately preceded by
    a findings.append(...) call."""
    src = (Path(__file__).resolve().parents[1] / "compare.py").read_text()
    body = src.split("def compare_gc_summary(")[1].split("\ndef ")[0]
    lines = body.split("\n")
    continues = [i for i, ln in enumerate(lines) if ln.strip().startswith("continue")]
    assert continues, "the gc branch is expected to contain `continue`s"
    for i in continues:
        window = "\n".join(lines[max(0, i - 8):i])
        assert "findings.append(" in window, (
            f"a `continue` at gc-branch line {i} has no recorded finding "
            f"before it:\n{window}")

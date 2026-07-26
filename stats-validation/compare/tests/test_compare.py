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
    close_enough,
    compare_case,
    display_key,
    format_ratio_cell,
    main,
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
    def mutate(case, figura, exact, python):
        case["display"]["kind"] = "km_summary"
    with pytest.raises(SystemExit) as excinfo:
        _run(tmp_path, mutate)
    assert "km_summary" in str(excinfo.value)


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

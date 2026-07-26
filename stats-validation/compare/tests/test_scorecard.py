"""Smoke test for build_scorecard.py (D11).

build_scorecard.py lives at the stats-validation/ repo root (sibling of
compare/, harness/, python/), not inside compare/ — it is imported here via a
path shim rather than a package relationship, deliberately: the scorecard is
a leaf consumer of findings.json, not part of the comparator package.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STATS_VALIDATION = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STATS_VALIDATION))

import build_scorecard  # noqa: E402
from compare import SRC_DISPLAY, SRC_EXACT, SRC_SCRIPT  # noqa: E402

FIXTURE = {
    "cases": [
        {
            "id": "case-pass",
            "kind": "ratio_table",
            "compared": 10,
            "passed": True,
            "targets_met": True,
            "targets": {"adjusted_or": 1},
            "findings": [],
        },
        {
            # The logistic-dirty shape, in miniature: the EXACT tier fails
            # (the exported script's harvest disagrees with Path B) while the
            # display tier passes. The scorecard must attribute the defect to
            # the exported script, not to the displayed numbers.
            "id": "case-defect",
            "kind": "ratio_table",
            "compared": 5,
            "passed": False,
            "targets_met": False,
            "targets": {"adjusted_or": 0},
            "findings": [
                {
                    "code": "DEFECT",
                    "disposition": "defect",
                    "term": "<script>alert(1)</script>",
                    "quantity": "est",
                    "figura": "1.23",
                    "python": "9.99",
                    "note": "beyond rel 1e-6 / abs 1e-9",
                    "source": SRC_EXACT,
                },
                {
                    "code": "SCRIPT_DIVERGENCE",
                    "disposition": "defect",
                    "term": "age",
                    "quantity": "exported script cell",
                    "figura": "1.66 (1.24-2.23, p<0.001)",
                    "python": "1.68 (1.25-2.26, p<0.001)",
                    "note": "the exported .R does not reproduce the screen",
                    "source": SRC_SCRIPT,
                },
            ],
        },
        {
            "id": "case-missing-quantity",
            "kind": "ratio_table",
            "compared": 0,
            "passed": False,
            "targets_met": False,
            "targets": {"adjusted_or": 0},
            "findings": [
                {
                    "code": "MISSING_QUANTITY",
                    "disposition": "defect",
                    "term": "-",
                    "quantity": "n",
                    "figura": None,
                    "python": None,
                    "note": "Path B did not report n; the count could not "
                             "be compared",
                    "source": SRC_EXACT,
                }
            ],
        },
        {
            # Task 11's table1 kind, whose DECISION (mean vs median) is itself
            # a validated output. DECISION_MISMATCH is disposition "defect" per
            # compare.py's DISPOSITIONS, so DEFECT_CODES must pick it up
            # automatically — it is derived from that mapping, never hand-listed.
            "id": "case-decision",
            "kind": "table1",
            "compared": 5,
            "passed": False,
            "targets_met": True,
            "targets": {"decisions": 5},
            "findings": [
                {
                    "code": "DECISION_MISMATCH",
                    "disposition": "defect",
                    "term": "age",
                    "quantity": "decisions",
                    "figura": "mean",
                    "python": "median",
                    "note": "the two paths chose different summary statistics",
                    "source": SRC_DISPLAY,
                }
            ],
        },
    ],
    "total_compared": 20,
    "total_findings": 4,
}


def _build(tmp_path: Path) -> str:
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(FIXTURE))
    out_path = build_scorecard.build(findings_path=findings_path,
                                     out_path=tmp_path / "scorecard.html")
    return out_path.read_text()


def test_tile_counts_correct(tmp_path):
    html = _build(tmp_path)
    # values compared, differences, defects, cases-meet-targets tiles.
    assert "<b>20</b>" in html  # total_compared
    # total_findings == defects here: DEFECT + SCRIPT_DIVERGENCE +
    # MISSING_QUANTITY + DECISION_MISMATCH
    assert "<b>4</b>" in html
    assert "<b>2/4</b>" in html  # 2 of 4 cases meet targets


def test_missing_quantity_counts_as_defect(tmp_path):
    """Regression pin for the reviewed bug: MISSING_QUANTITY is disposition
    "defect" per compare.py's own DISPOSITIONS mapping (compare.py classifies
    a coverage-failure finding the same as a value disagreement), and the
    scorecard's CSS styles .MISSING_QUANTITY identically red/bold to .DEFECT.
    A hand-picked DEFECT_CODES tuple that omitted MISSING_QUANTITY would
    render a red row while the defects tile claimed zero — this test fails
    if that regresses."""
    html = _build(tmp_path)
    # Every "defect"-disposition code must be counted: DEFECT,
    # SCRIPT_DIVERGENCE, MISSING_QUANTITY and DECISION_MISMATCH -> 4.
    assert "<b>4</b>" in html
    assert "class='MISSING_QUANTITY'" in html


def test_hostile_string_is_escaped(tmp_path):
    html = _build(tmp_path)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_defect_row_carries_fail_class(tmp_path):
    html = _build(tmp_path)
    assert "class='DEFECT'" in html


def test_targets_unmet_case_is_visibly_marked(tmp_path):
    html = _build(tmp_path)
    assert "TARGETS UNMET" in html
    assert "targets-unmet" in html
    # the passing, fully-covered case is marked distinctly, not as unmet.
    assert "targets met" in html


def test_no_dead_exact_pass_code_styled(tmp_path):
    """The comparator never emits EXACT_PASS (see compare.py's DISPOSITIONS
    comment), so the scorecard must not style it as a CSS selector or emit it
    as a row class — a prose mention explaining the omission is fine."""
    html = _build(tmp_path)
    assert ".EXACT_PASS" not in html
    assert "class='EXACT_PASS'" not in html


def test_webr_section_renders_honest_empty_state(tmp_path):
    html = _build(tmp_path)
    assert "Not yet run for this release" in html
    # ...and says how to produce one, including WHY it is not in `make all`.
    assert "make -C stats-validation webr" in html


# The shape stats-validation/e2e/webr-parity.spec.js writes: one identical case
# and one drifting one, so both renderings are pinned by the same fixture. The
# drifting values are the ones the tier's own negative-control run produced.
WEBR_TIER = {
    "runtime": "webR 0.6.1-dev+7603db7 (R 4.6.0)",
    "runtime_source": "read from the WebR instance's own version fields",
    "date": "2026-07-26",
    "cases": [
        {
            "id": "cox-adjusted",
            "identical": True,
            "cells_compared": 13,
            "differing_cells": [],
        },
        {
            "id": "logistic-confounding",
            "identical": False,
            "cells_compared": 23,
            "differing_cells": [
                {
                    "term": "<script>alert(2)</script>",
                    "column": "adjusted",
                    "native": "0.51 (0.28-0.91, p=0.023)",
                    "webr": "0.50 (0.28-0.91, p=0.023)",
                },
                {
                    "term": "(methods paragraph)",
                    "column": "sentence 3",
                    "native": "C-statistic = 0.67.",
                    "webr": "C-statistic = 0.68.",
                },
            ],
        },
    ],
}


def _build_with_webr(tmp_path, payload=None):
    (tmp_path / "webr-tier.json").write_text(
        json.dumps(WEBR_TIER if payload is None else payload))
    return _build(tmp_path)


def test_webr_section_renders_the_real_file(tmp_path):
    """Runtime, date, and a per-case identical/drift verdict with the number of
    cells behind it — not a raw JSON dump the reader has to parse by eye."""
    html = _build_with_webr(tmp_path)
    assert "Not yet run for this release" not in html
    assert "webR 0.6.1-dev+7603db7 (R 4.6.0)" in html
    assert "2026-07-26" in html
    assert "cox-adjusted" in html
    assert "IDENTICAL" in html
    assert "13 displayed cells matched native R exactly" in html
    assert "2 of 23 cells differ" in html


def test_webr_drift_row_is_visually_distinct_from_an_identical_one(tmp_path):
    """A drifting case must be styled like a defect, not like a footnote: the
    tier exists because a wasm-vs-native difference in a displayed number is a
    finding, and a reader skimming the section must not read one as a pass."""
    html = _build_with_webr(tmp_path)
    assert "class='webr-drift'>DRIFT" in html
    assert "class='webr-identical'>IDENTICAL" in html
    # ...and both classes reach the CSS, or the "distinct" claim is decorative.
    assert ".webr-drift" in html
    assert ".webr-identical" in html


def test_webr_drift_names_the_two_values(tmp_path):
    """"DRIFT" alone is unactionable. The cell, and both numbers, must be on
    the page so the reader can judge the SIZE of the difference."""
    html = _build_with_webr(tmp_path)
    assert "0.51 (0.28-0.91, p=0.023)" in html
    assert "0.50 (0.28-0.91, p=0.023)" in html
    assert "sentence 3" in html


def test_webr_runtime_provenance_is_shown(tmp_path):
    """The page prints no webR version, so the tier records how it identified
    the runtime. Rendering it keeps the runtime line from reading as an
    unsourced claim. (Asserted without the apostrophe: `esc` escapes it to
    `&#x27;`, which is correct output, not a missing string.)"""
    assert "read from the WebR instance" in _build_with_webr(tmp_path)


def test_webr_hostile_string_is_escaped(tmp_path):
    html = _build_with_webr(tmp_path)
    assert "<script>alert(2)</script>" not in html
    assert "&lt;script&gt;alert(2)&lt;/script&gt;" in html


def test_webr_file_that_is_not_json_says_so_rather_than_crashing(tmp_path):
    (tmp_path / "webr-tier.json").write_text("{not json")
    html = _build(tmp_path)
    assert "could not be read as JSON" in html


def test_webr_file_with_no_cases_does_not_render_an_empty_pass(tmp_path):
    """A run that wrote the file but listed no cases has gated nothing. An
    empty table would read as "no problems found"."""
    html = _build_with_webr(
        tmp_path, {"runtime": "webR x", "date": "2026-07-26", "cases": []})
    assert "lists no cases" in html
    # The verdict CLASS is the thing that must be absent — the words IDENTICAL
    # and DRIFT also appear in the CSS comment explaining how they are styled.
    assert "class='webr-identical'" not in html
    assert "class='webr-drift'" not in html


def test_every_finding_row_names_the_two_artifacts_it_compared(tmp_path):
    """THE ATTRIBUTION PIN. "Figura" is the screen on the display tier, the
    exported script's harvest on the exact tier, and on the script tier the
    "Python" column is not Path B at all. The shipped logistic-dirty case fails
    its exact tier while its display tier passes — the displayed numbers were
    right and the exported .R was wrong — so a table that labels those rows
    "Figura" alone tells the reader the opposite of what was measured.
    """
    html = _build(tmp_path)
    # The column exists...
    assert "<th>Compared</th>" in html
    # ...and each fixture finding's own source reaches the row.
    assert SRC_EXACT in html          # the exact-tier DEFECT + MISSING_QUANTITY
    assert SRC_SCRIPT in html         # the script-tier SCRIPT_DIVERGENCE
    assert SRC_DISPLAY in html        # the display-tier DECISION_MISMATCH
    # The legend must say what "exported script vs Python" implicates, in the
    # reader's terms, not just print the label.
    assert "export path" in html


def test_a_finding_with_no_source_is_not_silently_attributed(tmp_path):
    """A findings.json written before sources existed (or by a comparator bug)
    must render an em dash, never inherit the column header's implication."""
    fixture = json.loads(json.dumps(FIXTURE))
    del fixture["cases"][1]["findings"][0]["source"]
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(fixture))
    html = build_scorecard.build(findings_path=findings_path,
                                 out_path=tmp_path / "scorecard.html").read_text()
    assert "<td class='source'>&mdash;</td>" in html or \
           "<td class='source'>—</td>" in html


def test_registered_but_uncompared_cases_are_visible(tmp_path):
    """A case can be registered in the Makefile, run its Path A half, and have
    no Path B module yet (summary-table1, until the clean room lands). It is
    absent from findings.json, so without this the scorecard would read "7/7
    cases meet targets" while eight cases were registered — complete-looking
    and wrong. Every registered case appears; the denominator counts it."""
    for case_id in ("case-pass", "case-defect", "case-missing-quantity",
                    "case-decision", "summary-table1"):
        (tmp_path / f"{case_id}.done").write_text("")
    (tmp_path / "summary-table1.figura.json").write_text("{}")

    html = _build(tmp_path)
    assert "summary-table1" in html
    assert "NOT COMPARED" in html
    assert "class='NOT_COMPARED'" in html
    assert ".NOT_COMPARED" in html          # ...and it reaches the CSS
    # The tile denominator now counts five cases, not the four compared.
    assert "<b>2/5</b>" in html
    assert "<b>1</b><span>registered, not compared</span>" in html
    # The row says WHICH half is missing, derived from the artifacts on disk.
    assert "summary-table1.python.json" in html


def test_no_pending_row_or_tile_when_every_registered_case_was_compared(tmp_path):
    for case_id in ("case-pass", "case-defect", "case-missing-quantity",
                    "case-decision"):
        (tmp_path / f"{case_id}.done").write_text("")
    html = _build(tmp_path)
    # The legend explains NOT COMPARED unconditionally; what must be absent is
    # a ROW carrying the state, and the tile.
    assert "class='NOT_COMPARED'" not in html
    assert "registered, not compared</span>" not in html
    assert "<b>2/4</b>" in html


def test_an_absent_findings_file_is_a_clear_error_not_a_stale_scorecard(tmp_path):
    """`make all` deletes findings.json before comparing, so a crash leaves
    none. Publishing the previous run's scorecard would republish stale
    evidence as if it were current; the build stops instead."""
    import pytest
    with pytest.raises(SystemExit) as exc:
        build_scorecard.build(findings_path=tmp_path / "findings.json",
                              out_path=tmp_path / "scorecard.html")
    assert "no findings to publish" in str(exc.value)
    assert not (tmp_path / "scorecard.html").exists()


def test_decision_mismatch_is_styled_and_counted_as_a_defect(tmp_path):
    """Task 11's new code. It must reach the CSS (a row with no styling rule
    renders as ordinary body text, which would make a wrong summary statistic
    look like a passing row) and it must be inside the defects tile, which
    build_scorecard derives from compare.py's DISPOSITIONS rather than from a
    hand-written list."""
    html = _build(tmp_path)
    assert "class='DECISION_MISMATCH'" in html
    assert ".DECISION_MISMATCH" in html
    assert "DECISION_MISMATCH" in build_scorecard.DEFECT_CODES
    # ...and it is explained in the legend, not left as a bare code.
    assert "Decision mismatch" in html


def test_diagnostic_mismatch_is_styled_and_counted_as_a_defect(tmp_path):
    """Task A14's new code, same requirement DECISION_MISMATCH has: reach the
    CSS, reach the defects tile (derived from compare.py's DISPOSITIONS, not
    hand-listed), and be explained in the legend rather than left as a bare
    code."""
    assert "DIAGNOSTIC_MISMATCH" in build_scorecard.DEFECT_CODES
    html = _build(tmp_path)
    assert ".DIAGNOSTIC_MISMATCH" in html
    assert "Diagnostic mismatch" in html


def test_deferred_targets_are_named_in_the_coverage_cell(tmp_path):
    """A target the case declares but this run did not enforce is neither met
    nor failed. Left out of the cell, a case would read "targets met" in green
    while part of its published contract went unexamined."""
    case = {
        "id": "case-deferred",
        "kind": "ratio_table",
        "compared": 35,
        "passed": True,
        "targets_met": True,
        "targets": {"adjusted_or": 4},
        "deferred_targets": ["c_statistic", "vif_note"],
        "findings": [],
    }
    payload = {"cases": [case], "total_compared": 35, "total_findings": 0}
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(payload))
    html = build_scorecard.build(
        findings_path=findings_path,
        out_path=tmp_path / "scorecard.html").read_text()
    assert "2 DEFERRED: c_statistic, vif_note" in html
    assert "targets-deferred" in html
    # ...and the legend says what DEFERRED means.
    assert "<b>DEFERRED</b>" in html


def test_a_case_without_the_deferred_field_renders_as_before(tmp_path):
    """Every case in the main fixture predates `deferred_targets`; none may
    grow a stray marker. The legend's explanation of DEFERRED and the CSS rule
    for it are always present, so the assertion is on the per-case SPAN's class
    ATTRIBUTE — the only thing that could misreport a row."""
    assert "class='targets-deferred'" not in _build(tmp_path)


def test_a_case_with_deferred_targets_does_not_count_toward_the_tile_numerator(tmp_path):
    """Same precedent this file already applies to NOT_COMPARED's denominator
    ("a tile can never read complete while such a case exists"), applied to
    the numerator: a case can carry `targets_met: true` while some of its
    declared targets are DEFERRED (not yet checked at all, per compare.py's
    `_Targets.met`, which is computed only over the non-deferred declared
    targets). Left uncorrected the tile would read "8/8 cases meet targets"
    while 14 declared targets across three real cases were never enforced —
    exactly the misleading combination this test pins against a minimal
    fixture. `test_tile_counts_correct` established the base fixture's
    "2/4"; giving one of those two cases a deferred target must knock it out
    of the numerator without changing the denominator."""
    fixture = json.loads(json.dumps(FIXTURE))
    fixture["cases"][0]["targets_met"] = True
    fixture["cases"][0]["deferred_targets"] = ["c_statistic"]
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(fixture))
    html = build_scorecard.build(
        findings_path=findings_path,
        out_path=tmp_path / "scorecard.html").read_text()
    assert "<b>1/4</b>" in html
    assert "<b>2/4</b>" not in html
    # ...and the label no longer overclaims what the tile counts.
    assert "cases fully meet targets" in html
    # A new tile, mirroring "registered, not compared", makes the excluded
    # case visible rather than just silently smaller.
    assert "<b>1</b><span>cases with deferred targets</span>" in html


def test_no_deferred_cases_tile_when_nothing_is_deferred(tmp_path):
    """The base fixture predates `deferred_targets` entirely, so the new tile
    must not render a stray "0" (or any) tile — mirroring how the pending
    tile is absent when nothing is pending."""
    assert "cases with deferred targets</span>" not in _build(tmp_path)

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

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
                }
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
                }
            ],
        },
    ],
    "total_compared": 20,
    "total_findings": 3,
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
    # total_findings == defects here: DEFECT + MISSING_QUANTITY + DECISION_MISMATCH
    assert "<b>3</b>" in html
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
    # Every "defect"-disposition code must be counted: with one DEFECT, one
    # MISSING_QUANTITY and one DECISION_MISMATCH, the defects tile reads 3.
    assert "<b>3</b>" in html
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

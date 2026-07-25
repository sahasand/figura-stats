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
    ],
    "total_compared": 15,
    "total_findings": 1,
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
    assert "<b>15</b>" in html  # total_compared
    assert "<b>1</b>" in html  # total_findings == defects here (one DEFECT)
    assert "<b>1/2</b>" in html  # 1 of 2 cases meets targets


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

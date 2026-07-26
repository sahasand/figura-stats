"""Tests for gate.py — the findings-baseline gate.

The gate is the only thing standing between "make all exits non-zero by design"
and "CI cannot catch a regression", so its two failure modes both matter and
both are pinned here:

  * a FALSE RED (a last-digit float move, a reordered array) trains everyone to
    ignore the job, which is the exact failure the permanently-red alternative
    had;
  * a FALSE GREEN (a finding appeared, disappeared, changed tier, or a case
    silently stopped being compared) is the regression the gate exists for.

gate.py lives at the stats-validation/ root, imported through the same path
shim test_scorecard.py uses for build_scorecard.py, and for the same reason:
it is a leaf consumer of findings.json, not part of the comparator package.
"""
from __future__ import annotations

import copy
import io
import json
import sys
from pathlib import Path

import pytest

STATS_VALIDATION = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STATS_VALIDATION))

import gate  # noqa: E402

# A miniature of the shipped evidence: one clean case, one case publishing
# accepted findings (the logistic-dirty shape).
FINDINGS = {
    "total_compared": 30,
    "total_findings": 2,
    "cases": [
        {
            "id": "clean-case",
            "kind": "ratio_table",
            "compared": 20,
            "passed": True,
            "targets_met": True,
            "targets": {"adjusted_or": 2, "n": 1},
            "deferred_targets": [],
            "findings": [],
        },
        {
            "id": "dirty-case",
            "kind": "ratio_table",
            "compared": 10,
            "passed": False,
            "targets_met": True,
            "targets": {"adjusted_or": 2, "n": 1},
            "deferred_targets": [],
            "findings": [
                {
                    "code": "DEFECT", "disposition": "defect", "term": "age",
                    "quantity": "est", "figura": 1.6612, "python": 1.6809,
                    "note": "beyond rel 1e-06 / abs 1e-09",
                    "source": "exported script vs Python",
                },
                {
                    "code": "COUNT_MISMATCH", "disposition": "defect",
                    "term": "-", "quantity": "n", "figura": 312,
                    "python": 320,
                    "note": "the two paths analysed different rows",
                    "source": "exported script vs Python",
                },
            ],
        },
    ],
}


def _paths(tmp_path, findings=None):
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(findings or FINDINGS))
    baseline_path = tmp_path / "expected-findings.json"
    assert gate.update(findings_path, baseline_path, out=io.StringIO()) == 0
    return findings_path, baseline_path


def _run(findings_path, baseline_path, findings=None):
    """Check `findings` (default: whatever is on disk) against the baseline."""
    if findings is not None:
        findings_path.write_text(json.dumps(findings))
    out = io.StringIO()
    return gate.check(findings_path, baseline_path, out=out), out.getvalue()


# --- the gate passes on the evidence it was built from ----------------------

def test_baseline_matches_the_findings_it_was_generated_from(tmp_path):
    code, out = _run(*_paths(tmp_path))
    assert code == 0
    assert "OK" in out


def test_baseline_file_is_self_describing(tmp_path):
    """Whoever opens the file cold, or reviews it in a diff, must be able to
    tell what it is and how to update it without first finding gate.py."""
    _, baseline_path = _paths(tmp_path)
    note = " ".join(json.loads(baseline_path.read_text())["_note"])
    assert "do not" in note and "hand-edit" in note
    assert "gate-update" in note
    assert "SAME COMMIT" in note


# --- FALSE REDS the gate must not produce -----------------------------------

def test_a_float_move_in_the_measured_values_is_not_a_failure(tmp_path):
    """The whole reason values are excluded from the key. An odds ratio moving
    in its last digits is not a regression; a build that goes red for it is a
    build people stop reading."""
    findings_path, baseline_path = _paths(tmp_path)
    moved = copy.deepcopy(FINDINGS)
    moved["cases"][1]["findings"][0]["figura"] = 1.6612000000000003
    moved["cases"][1]["findings"][0]["python"] = 1.6808999999999998
    code, out = _run(findings_path, baseline_path, moved)
    assert code == 0, out


def test_reordering_cases_and_findings_is_not_a_failure(tmp_path):
    """The baseline is a set keyed by identity, not a transcript. Array order
    is an implementation detail of the comparator's loops."""
    findings_path, baseline_path = _paths(tmp_path)
    shuffled = copy.deepcopy(FINDINGS)
    shuffled["cases"].reverse()
    for case in shuffled["cases"]:
        case["findings"].reverse()
    code, out = _run(findings_path, baseline_path, shuffled)
    assert code == 0, out


# --- FALSE GREENS the gate must not allow -----------------------------------

def test_a_new_finding_fails_and_is_named(tmp_path):
    findings_path, baseline_path = _paths(tmp_path)
    regressed = copy.deepcopy(FINDINGS)
    regressed["cases"][0]["findings"].append({
        "code": "DEFECT", "disposition": "defect", "term": "arm",
        "quantity": "p", "figura": 0.03, "python": 0.9,
        "note": "beyond rel 1e-06 / abs 1e-09", "source": "screen vs Python",
    })
    regressed["total_findings"] = 3
    code, out = _run(findings_path, baseline_path, regressed)
    assert code == 1
    assert "+ NEW finding" in out
    assert "clean-case" in out and "term=arm" in out and "quantity=p" in out


def test_a_removed_finding_fails(tmp_path):
    """A finding disappearing means the evidence moved and the baseline is now
    a stale description of the repo — which is exactly what will happen when
    the Phase-2 export-path fix lands. That PR updates the baseline; it does
    not get to pass silently."""
    findings_path, baseline_path = _paths(tmp_path)
    fixed = copy.deepcopy(FINDINGS)
    fixed["cases"][1]["findings"].pop()
    fixed["total_findings"] = 1
    code, out = _run(findings_path, baseline_path, fixed)
    assert code == 1
    assert "- GONE finding" in out
    assert "COUNT_MISMATCH" in out


def test_a_finding_changing_tier_fails(tmp_path):
    """Same identity, different `source`: the numbers on SCREEN now disagree
    where only the exported script used to. That is a different, and far worse,
    claim about the product, and a set-membership check alone would miss it."""
    findings_path, baseline_path = _paths(tmp_path)
    worse = copy.deepcopy(FINDINGS)
    worse["cases"][1]["findings"][0]["source"] = "screen vs Python"
    code, out = _run(findings_path, baseline_path, worse)
    assert code == 1
    assert "~ CHANGED finding" in out
    assert "screen vs Python" in out


def test_a_case_that_silently_stops_comparing_fails(tmp_path):
    """The hole a findings-only gate has: a clean case whose comparison count
    collapses to zero adds no finding and removes none, so the findings set is
    untouched. Coverage is in the baseline for precisely this."""
    findings_path, baseline_path = _paths(tmp_path)
    hollow = copy.deepcopy(FINDINGS)
    hollow["cases"][0]["compared"] = 0
    hollow["cases"][0]["targets"] = {}
    hollow["total_compared"] = 10
    code, out = _run(findings_path, baseline_path, hollow)
    assert code == 1
    assert "coverage compared: 20 -> 0" in out


def test_a_case_disappearing_entirely_fails(tmp_path):
    findings_path, baseline_path = _paths(tmp_path)
    shrunk = copy.deepcopy(FINDINGS)
    shrunk["cases"] = shrunk["cases"][1:]
    code, out = _run(findings_path, baseline_path, shrunk)
    assert code == 1
    assert "stopped being compared" in out


def test_a_new_case_fails_until_the_baseline_records_it(tmp_path):
    """Coverage going UP is a change to what the evidence claims, and belongs
    in the commit that caused it — not silently absorbed."""
    findings_path, baseline_path = _paths(tmp_path)
    grown = copy.deepcopy(FINDINGS)
    grown["cases"].append({
        "id": "new-case", "kind": "gc_summary", "compared": 4, "passed": True,
        "targets_met": True, "targets": {"test_p": 1}, "deferred_targets": [],
        "findings": [],
    })
    grown["total_compared"] = 34
    code, out = _run(findings_path, baseline_path, grown)
    assert code == 1
    assert "new-case" in out and "ABSENT from the baseline" in out


def test_a_deferred_target_appearing_fails(tmp_path):
    """A target moving to DEFERRED means declared coverage stopped being
    enforced — the scorecard renders that, and the gate must not wave it past."""
    findings_path, baseline_path = _paths(tmp_path)
    deferred = copy.deepcopy(FINDINGS)
    deferred["cases"][0]["deferred_targets"] = ["c_statistic"]
    code, out = _run(findings_path, baseline_path, deferred)
    assert code == 1
    assert "deferred_targets" in out


# --- the gate's own inputs --------------------------------------------------

def test_a_missing_findings_file_is_exit_2_not_a_pass(tmp_path):
    """`make all` is allowed to fail, so CI ignores its exit code. If it died
    before compare.py wrote findings.json, the gate is the only thing left that
    can notice — and it must not read that as "no findings, all clear"."""
    _, baseline_path = _paths(tmp_path)
    code = gate.main(["--findings", str(tmp_path / "gone.json"),
                      "--baseline", str(baseline_path)])
    assert code == 2


def test_a_missing_baseline_is_exit_2_not_a_pass(tmp_path):
    findings_path, _ = _paths(tmp_path)
    code = gate.main(["--findings", str(findings_path),
                      "--baseline", str(tmp_path / "gone.json")])
    assert code == 2


def test_duplicate_finding_identities_are_refused_not_collapsed(tmp_path):
    """If the comparator ever emits two findings with the same key, one would
    silently mask the other. Widening the key is a human decision; the gate
    refuses rather than guessing."""
    findings_path, baseline_path = _paths(tmp_path)
    dupe = copy.deepcopy(FINDINGS)
    dupe["cases"][1]["findings"].append(
        copy.deepcopy(dupe["cases"][1]["findings"][0]))
    findings_path.write_text(json.dumps(dupe))
    with pytest.raises(gate.GateInputError, match="share the identity"):
        gate.check(findings_path, baseline_path, out=io.StringIO())


def test_update_is_idempotent(tmp_path):
    """Regenerating an already-current baseline must produce no diff, or every
    `gate-update` becomes noise in review."""
    findings_path, baseline_path = _paths(tmp_path)
    before = baseline_path.read_text()
    gate.update(findings_path, baseline_path, out=io.StringIO())
    assert baseline_path.read_text() == before


def test_update_makes_a_failing_gate_pass(tmp_path):
    """The documented remedy has to actually work: regenerate, and the gate is
    green again on exactly the new evidence."""
    findings_path, baseline_path = _paths(tmp_path)
    changed = copy.deepcopy(FINDINGS)
    changed["cases"][1]["findings"].pop()
    changed["total_findings"] = 1
    assert _run(findings_path, baseline_path, changed)[0] == 1
    gate.update(findings_path, baseline_path, out=io.StringIO())
    assert _run(findings_path, baseline_path)[0] == 0

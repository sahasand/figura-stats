"""Tests for freshness.py — is the COMMITTED evidence what this code regenerates?

This is the half of the CI verdict that owns the NUMBERS. `gate.py` deliberately
ignores them (test_gate.py::test_a_wildly_wrong_value_still_passes_this_gate
pins that a `figura` of 99999 is green there), so if this gate is wrong in either
direction the measured values are effectively checked by nothing.

Both directions are therefore pinned, and they are the same two the baseline gate
has:

  * FALSE RED — a last-digit float move failing the build. That is what a plain
    `git diff --exit-code` over findings.json would do: local (Homebrew R +
    Accelerate, source-built numpy) and CI (Ubuntu R + OpenBLAS, manylinux
    wheels) agree on an iterative fit to ~1e-10, not to the last bit, so a byte
    diff fails the first CI run for a NON-regression while accusing the developer
    of committing stale evidence.
  * FALSE GREEN — a value that genuinely moved, or an identity/kind/coverage
    change, passing.

The committed side is read with `git show`, so these tests build a REAL throwaway
git repo rather than mocking the call. Mocking it would leave the one thing most
likely to break (the `git show <ref>:<path>` invocation, and how git reports an
absent path) untested.
"""
from __future__ import annotations

import copy
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

STATS_VALIDATION = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STATS_VALIDATION))

import freshness  # noqa: E402

TRACKED = "stats-validation/results/findings.json"

# The shipped shape in miniature, with values at the precision compare.py
# actually publishes (9 significant digits).
FINDINGS = {
    "_published_precision": "values are rounded for publication; see compare.py",
    "total_compared": 30,
    "total_findings": 2,
    "cases": [
        {
            "id": "clean-case", "kind": "ratio_table", "compared": 20,
            "passed": True, "targets_met": True,
            "targets": {"adjusted_or": 2, "n": 1}, "deferred_targets": [],
            "findings": [],
        },
        {
            "id": "dirty-case", "kind": "ratio_table", "compared": 10,
            "passed": False, "targets_met": True,
            "targets": {"adjusted_or": 2, "n": 1}, "deferred_targets": [],
            "findings": [
                {
                    "code": "DEFECT", "disposition": "defect", "term": "age",
                    "quantity": "est", "figura": 1.68264486127,
                    "python": 1.66487510588,
                    "note": "beyond rel 1e-06 / abs 1e-09",
                    "source": "exported script vs Python",
                },
                {
                    "code": "COUNT_MISMATCH", "disposition": "defect",
                    "term": "-", "quantity": "n", "figura": 312, "python": 320,
                    "note": "the two paths analysed different rows",
                    "source": "exported script vs Python",
                },
            ],
        },
    ],
}


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.fixture
def repo(tmp_path):
    """A throwaway repo with the artifact committed at HEAD."""
    root = tmp_path / "repo"
    (root / "stats-validation" / "results").mkdir(parents=True)
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    path = root / TRACKED
    path.write_text(json.dumps(FINDINGS, indent=2) + "\n")
    _git(root, "add", TRACKED)
    _git(root, "commit", "-q", "-m", "publish evidence")
    return root


def _run(repo: Path, regenerated=None, ref="HEAD"):
    """Check `regenerated` (default: the committed content) against `ref`."""
    path = repo / TRACKED
    if regenerated is not None:
        path.write_text(json.dumps(regenerated, indent=2) + "\n")
    out = io.StringIO()
    code = freshness.check(path, ref, TRACKED, repo, out=out)
    return code, out.getvalue()


# --- the artifact is fresh --------------------------------------------------

def test_the_committed_artifact_matches_its_own_regeneration(repo):
    code, out = _run(repo)
    assert code == 0, out
    assert "OK" in out


def test_a_byte_identical_rebuild_is_fresh_even_with_reordered_arrays(repo):
    """The comparison is over the canonical shape gate.normalize() produces, so
    the comparator's loop order is not part of the contract."""
    shuffled = copy.deepcopy(FINDINGS)
    shuffled["cases"].reverse()
    for case in shuffled["cases"]:
        case["findings"].reverse()
    code, out = _run(repo, shuffled)
    assert code == 0, out


# --- FALSE REDS this gate must not produce ---------------------------------

def test_a_1e15_float_move_is_fresh(repo):
    """THE WHOLE REASON THIS EXISTS. A byte diff fails here; this must not.
    1e-15 relative is the last bit of a double — two runs of the same
    arithmetic on different BLAS."""
    moved = copy.deepcopy(FINDINGS)
    f = moved["cases"][1]["findings"][0]
    f["figura"] = f["figura"] * (1 + 1e-15)
    f["python"] = f["python"] * (1 - 1e-15)
    assert f["figura"] != FINDINGS["cases"][1]["findings"][0]["figura"]
    code, out = _run(repo, moved)
    assert code == 0, out


def test_a_move_just_inside_the_comparator_tolerance_is_fresh(repo):
    """The boundary is compare.py's own REL_TOL, not a second opinion about it:
    this gate's idea of "the same number" is by construction the comparator's."""
    moved = copy.deepcopy(FINDINGS)
    f = moved["cases"][1]["findings"][0]
    f["figura"] = f["figura"] * (1 + freshness.REL_TOL / 2)
    code, out = _run(repo, moved)
    assert code == 0, out


def test_a_true_zero_is_compared_through_the_absolute_floor(repo):
    """A relative tolerance alone cannot compare against zero. The comparator's
    ABS_TOL floor is inherited, so a p-value that underflowed to 0.0 on one
    machine and 1e-12 on another is still the same measurement."""
    committed = copy.deepcopy(FINDINGS)
    committed["cases"][1]["findings"][0]["python"] = 0.0
    path = repo / TRACKED
    path.write_text(json.dumps(committed, indent=2) + "\n")
    _git(repo, "commit", "-q", "-am", "zero")
    moved = copy.deepcopy(committed)
    moved["cases"][1]["findings"][0]["python"] = freshness.ABS_TOL / 2
    code, out = _run(repo, moved)
    assert code == 0, out


# --- FALSE GREENS this gate must not allow ---------------------------------

def test_a_1e4_float_move_is_stale(repo):
    """Beyond the comparator's tolerance the two paths do not agree about the
    number, and a committed artifact claiming otherwise is a wrong published
    claim — the one thing this gate is for."""
    moved = copy.deepcopy(FINDINGS)
    moved["cases"][1]["findings"][0]["figura"] = 1.68264486127 * (1 + 1e-4)
    code, out = _run(repo, moved)
    assert code == 1
    assert "value figura moved" in out
    assert "dirty-case" in out and "term=age" in out


def test_an_integer_count_moving_is_stale(repo):
    """Counts are not floats and get no tolerance: 312 -> 313 rows analysed is a
    different study."""
    moved = copy.deepcopy(FINDINGS)
    moved["cases"][1]["findings"][1]["figura"] = 313
    code, out = _run(repo, moved)
    assert code == 1
    assert "value figura moved" in out


def test_a_changed_identity_is_stale(repo):
    changed = copy.deepcopy(FINDINGS)
    changed["cases"][1]["findings"][0]["term"] = "arm"
    code, out = _run(repo, changed)
    assert code == 1
    # Reported by the same code the baseline gate uses, so the two can never
    # disagree about what a finding IS.
    assert "+ NEW finding" in out and "- GONE finding" in out


def test_a_changed_kind_is_stale(repo):
    changed = copy.deepcopy(FINDINGS)
    changed["cases"][1]["findings"][0]["source"] = "screen vs Python"
    code, out = _run(repo, changed)
    assert code == 1
    assert "~ CHANGED finding" in out


def test_changed_coverage_is_stale(repo):
    changed = copy.deepcopy(FINDINGS)
    changed["cases"][0]["compared"] = 0
    changed["total_compared"] = 10
    code, out = _run(repo, changed)
    assert code == 1
    assert "coverage compared: 20 -> 0" in out


def test_a_value_becoming_a_string_is_stale(repo):
    """A type change is never agreement — 1.68 and "1.68" are different claims
    about what the artifact holds, and a tolerance question cannot be asked."""
    changed = copy.deepcopy(FINDINGS)
    changed["cases"][1]["findings"][0]["figura"] = "1.68264486127"
    code, out = _run(repo, changed)
    assert code == 1


def test_a_rendered_cell_string_changing_is_stale(repo):
    """Display strings are compared EXACTLY. A cell that renders differently is
    a different thing on the user's screen; there is no tolerance for a string."""
    changed = copy.deepcopy(FINDINGS)
    changed["cases"][1]["findings"][0]["figura"] = "1.66 (1.24–2.23, p<0.001)"
    committed = copy.deepcopy(FINDINGS)
    committed["cases"][1]["findings"][0]["figura"] = "1.68 (1.25–2.26, p<0.001)"
    path = repo / TRACKED
    path.write_text(json.dumps(committed, indent=2) + "\n")
    _git(repo, "commit", "-q", "-am", "string value")
    code, out = _run(repo, changed)
    assert code == 1
    assert "value figura moved" in out


def test_nested_dict_values_are_compared_too(repo):
    """A MISSING_QUANTITY finding publishes Path B's whole malformed cell dict.
    Its floats get the same tolerance and its structure the same exactness."""
    committed = copy.deepcopy(FINDINGS)
    committed["cases"][1]["findings"][0]["python"] = {"est": 1.5, "lo": None}
    path = repo / TRACKED
    path.write_text(json.dumps(committed, indent=2) + "\n")
    _git(repo, "commit", "-q", "-am", "dict value")

    near = copy.deepcopy(committed)
    near["cases"][1]["findings"][0]["python"] = {"est": 1.5 * (1 + 1e-15),
                                                "lo": None}
    assert _run(repo, near)[0] == 0

    far = copy.deepcopy(committed)
    far["cases"][1]["findings"][0]["python"] = {"est": 1.6, "lo": None}
    assert _run(repo, far)[0] == 1

    reshaped = copy.deepcopy(committed)
    reshaped["cases"][1]["findings"][0]["python"] = {"est": 1.5}
    assert _run(repo, reshaped)[0] == 1


# --- the gate's own inputs -------------------------------------------------

def test_an_absent_committed_baseline_passes_and_says_why(repo):
    """The commit that FIRST publishes the artifact must not be blocked by the
    absence of the thing it is publishing. Also covers a checkout where the file
    was never tracked."""
    out = io.StringIO()
    code = freshness.check(repo / TRACKED, "HEAD",
                           "stats-validation/results/never-tracked.json",
                           repo, out=out)
    assert code == 0
    assert "no committed baseline" in out.getvalue()


def test_an_empty_repo_with_no_commits_passes(tmp_path):
    """`git show HEAD:...` on a repo with no HEAD at all — the true first-commit
    case — is reported, not an error."""
    root = tmp_path / "fresh"
    (root / "stats-validation" / "results").mkdir(parents=True)
    _git(root.parent, "init", "-q", str(root))
    path = root / TRACKED
    path.write_text(json.dumps(FINDINGS))
    out = io.StringIO()
    assert freshness.check(path, "HEAD", TRACKED, root, out=out) == 0
    assert "no committed baseline" in out.getvalue()


def test_a_missing_regenerated_findings_file_is_exit_2(repo):
    """`make all` is allowed to fail and CI does not obey its status, so a
    pipeline that died before writing findings.json must not read as "fresh"."""
    (repo / TRACKED).unlink()
    code = freshness.main(["--findings", str(repo / TRACKED), "--ref", "HEAD",
                           "--tracked-path", TRACKED, "--repo-root", str(repo)])
    assert code == 2


def test_a_malformed_regenerated_file_is_exit_2(repo):
    (repo / TRACKED).write_text("{not json")
    code = freshness.main(["--findings", str(repo / TRACKED), "--ref", "HEAD",
                           "--tracked-path", TRACKED, "--repo-root", str(repo)])
    assert code == 2


def test_a_ref_that_does_not_resolve_is_exit_2_not_a_pass(repo):
    """A typo'd `--ref` must not be indistinguishable from "no baseline yet".
    That mistake would otherwise pass green forever while checking nothing."""
    code = freshness.main(["--findings", str(repo / TRACKED),
                           "--ref", "no-such-ref", "--tracked-path", TRACKED,
                           "--repo-root", str(repo)])
    assert code == 2


def test_a_non_repo_directory_is_exit_2_not_a_pass(tmp_path):
    """No git at all: this gate cannot answer its question, and "cannot answer"
    must never render as "fresh"."""
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(FINDINGS))
    code = freshness.main(["--findings", str(path), "--ref", "HEAD",
                           "--tracked-path", TRACKED,
                           "--repo-root", str(tmp_path)])
    assert code == 2


def test_the_uncommitted_working_tree_is_what_is_judged(repo):
    """The baseline is the COMMIT, not the working tree — an uncommitted edit to
    findings.json is exactly what this gate exists to notice, so it must not
    accidentally compare the file against itself."""
    edited = copy.deepcopy(FINDINGS)
    edited["cases"][1]["findings"][0]["figura"] = 42.0
    (repo / TRACKED).write_text(json.dumps(edited, indent=2) + "\n")
    out = io.StringIO()
    assert freshness.check(repo / TRACKED, "HEAD", TRACKED, repo, out=out) == 1


def test_the_failure_message_names_both_possible_causes(repo):
    """A stale artifact and a genuine cross-environment disagreement are
    different problems with different fixes, and the message must not let a
    reader assume the first."""
    moved = copy.deepcopy(FINDINGS)
    moved["cases"][1]["findings"][0]["figura"] = 99999.0
    _, out = _run(repo, moved)
    assert "make -C stats-validation clean all" in out
    assert "genuinely disagree" in out
    assert "loosening this tolerance is the wrong fix" in out

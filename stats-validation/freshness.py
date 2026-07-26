"""The freshness gate: is the COMMITTED evidence what this code regenerates?

WHY THIS IS NOT `git diff --exit-code`. `results/findings.json` is tracked
evidence, and a stale committed copy is a published claim about a tree that no
longer exists — so it must be checked. But the file carries measured floats, and
a byte comparison of floats compares environments, not statistics:

    local   Homebrew R + Accelerate BLAS, source-built numpy on Python 3.14
    CI      Ubuntu R + OpenBLAS, manylinux wheels on Python 3.11

Two honest runs of an iteratively fitted model (logistic's IRLS, Cox's
Newton-Raphson) agree there to roughly 1e-10 — not to the last bit. So a byte
diff over the numbers fails the FIRST CI run for a non-regression, under a
message accusing the developer of committing a stale scorecard. That is the same
false red the baseline gate exists to avoid ("a last-digit move must never turn
the build red"), and a step that cries wolf is a step people delete.

WHAT THIS DOES INSTEAD. Two comparisons over the same pair of files, each at the
precision that field deserves:

  STRUCTURE, exactly.   Case ids, kinds, coverage counts, targets, deferred
                        targets, run totals, and every finding's identity
                        (code + term + quantity) and kind (disposition, source,
                        note). This reuses gate.normalize() and gate.diff()
                        rather than restating them, so the two gates can never
                        drift into disagreeing about what a finding IS.
  VALUES, to tolerance. `figura` and `python`, at compare.py's own REL_TOL /
                        ABS_TOL via its own close_enough(). Non-numeric values
                        (rendered cells, notes, nulls) are compared exactly —
                        they are strings, and a string has no tolerance.

So a 1e-15 wobble in an odds ratio passes; a 1e-4 move fails; and a changed
identity, kind or coverage count fails no matter what the numbers do.

THE BASELINE IS THE COMMIT, NOT THE WORKING TREE. It is read with
`git show <ref>:<path>`, so an uncommitted local edit to findings.json is
exactly what this gate is meant to notice. An ABSENT baseline (first commit of
the file, a shallow/exportless checkout, no git at all) is reported and exits 0:
there is nothing to be stale relative to, and inventing a failure there would
block the very commit that introduces the artifact.

WHAT THIS DOES NOT COVER. `results/scorecard.html` — CI byte-diffs that one, and
that is honest because the scorecard renders only the values findings.json
publishes, which compare.py rounds to PUBLISHED_SIGNIFICANT_DIGITS (9) on the
way out. Do not add a second, looser check for it here: an HTML artifact either
regenerates or it does not.

USAGE

    make -C stats-validation freshness

    .venv/bin/python freshness.py [--findings PATH] [--ref REF]
                                  [--tracked-path REPO/RELATIVE/PATH]

Exit codes: 0 fresh (or no baseline to compare against), 1 stale, 2 the inputs
could not be read at all.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_FINDINGS = HERE / "results" / "findings.json"
# The path git knows this file by, which is NOT the same string as the filesystem
# path above: `git show HEAD:<path>` needs a repo-relative path.
DEFAULT_TRACKED_PATH = "stats-validation/results/findings.json"
DEFAULT_REF = "HEAD"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "compare"))

import gate  # noqa: E402
from compare import ABS_TOL, REL_TOL, close_enough  # noqa: E402

BANNER = "EVIDENCE FRESHNESS GATE"

# The two value columns, the only fields compared numerically. Everything else a
# finding carries is compared exactly, by gate.normalize().
VALUE_FIELDS = ("figura", "python")


class FreshnessInputError(Exception):
    """The gate could not read what it was asked to compare (exit 2)."""


class NoBaseline(Exception):
    """No committed version of the artifact exists (reported, exit 0)."""


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=repo_root,
                              capture_output=True, text=True, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FreshnessInputError(f"could not run `git {' '.join(args)}` ({exc})")


def read_committed(ref: str, tracked_path: str,
                   repo_root: Path = REPO_ROOT) -> dict:
    """The artifact as COMMITTED at `ref`, via `git show`.

    Raises NoBaseline (reported, exit 0) for the two genuinely benign shapes:
    the path is absent at that ref (its first commit), or the repository has no
    commits at all (an unborn HEAD).

    Raises FreshnessInputError (exit 2) for everything else — no git, no
    repository, a `--ref` that does not resolve, a blob that is not JSON. A gate
    that cannot answer its question must never render as "fresh", and a typo'd
    ref is exactly the kind of thing that would otherwise pass silently forever.
    """
    # "Not a git repository" and "a repository with no commits yet" produce
    # nearly the same failure from `git show`, and they mean opposite things: the
    # second is the benign first-commit case, the first means this gate cannot
    # answer its question at all (a tarball export, a stripped container). Settle
    # it up front so the two can never be confused below.
    if _git(repo_root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise FreshnessInputError(
            f"{repo_root} is not inside a git work tree, so the COMMITTED "
            f"evidence cannot be read. This gate compares the working tree "
            f"against `git show {ref}:{tracked_path}`; without git there is "
            f"nothing to compare against, and that is not the same as being "
            f"fresh.")
    proc = _git(repo_root, "show", f"{ref}:{tracked_path}")
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        # git distinguishes "the ref is fine, the path is not in it" from "the
        # ref itself does not resolve", and so must this: only the first is
        # benign on its own.
        path_absent = ("does not exist in", "exists on disk, but not in",
                       "no such path")
        if any(marker in stderr for marker in path_absent):
            raise NoBaseline(stderr)
        # The ref did not resolve. An unborn HEAD (a repository with no commits
        # yet) is the true first-commit case and is benign; anything else is a
        # bad ref the caller passed, and that is an error.
        if _git(repo_root, "rev-parse", "--verify", "--quiet",
                f"{ref}^{{commit}}").returncode != 0:
            if ref == DEFAULT_REF and _git(
                    repo_root, "rev-parse", "--verify", "--quiet",
                    "HEAD").returncode != 0:
                raise NoBaseline(
                    "the repository has no commits yet (unborn HEAD)")
            raise FreshnessInputError(
                f"the ref {ref!r} does not resolve to a commit in {repo_root} "
                f"({stderr or proc.returncode})")
        raise FreshnessInputError(
            f"`git show {ref}:{tracked_path}` failed: {stderr or proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise FreshnessInputError(
            f"the committed {tracked_path} at {ref} is not valid JSON: {exc}")


def read_current(path: Path) -> dict:
    if not path.exists():
        raise FreshnessInputError(
            f"{path} does not exist. Run `make -C stats-validation all` first "
            "— compare.py writes findings.json before it returns, so its "
            "absence means the comparator did not finish.")
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise FreshnessInputError(f"{path} could not be read as JSON: {exc}")


def _numbers_agree(a, b) -> bool:
    """Are two published values the same measurement?

    Numbers go through compare.py's own close_enough(), so this gate's idea of
    "agrees" is by construction the comparator's idea of it. Everything else —
    strings, nulls, booleans, and the nested dicts a MISSING_QUANTITY finding
    publishes — is compared exactly, recursing so a dict's floats still get the
    tolerance treatment. A type change (number -> string) is never agreement.
    """
    a_num = isinstance(a, (int, float)) and not isinstance(a, bool)
    b_num = isinstance(b, (int, float)) and not isinstance(b, bool)
    if a_num != b_num:
        return False
    if a_num:
        if not (math.isfinite(float(a)) and math.isfinite(float(b))):
            # Non-finite values never reach a published artifact (compare.py
            # refuses to write them), so this is defensive: identical repr or
            # nothing.
            return repr(a) == repr(b)
        return close_enough(float(a), float(b))
    if isinstance(a, dict) and isinstance(b, dict):
        return (sorted(a.keys()) == sorted(b.keys())
                and all(_numbers_agree(a[k], b[k]) for k in a))
    if isinstance(a, list) and isinstance(b, list):
        return (len(a) == len(b)
                and all(_numbers_agree(x, y) for x, y in zip(a, b)))
    return a == b


def _show(value) -> str:
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def value_diff(committed: dict, current: dict) -> list[str]:
    """Findings whose measured values moved beyond tolerance. Empty == fresh.

    Runs only on findings that exist on BOTH sides with the same identity, so it
    never re-reports what gate.diff() already reported structurally.
    """
    com_cases = {c["id"]: c for c in committed["cases"]}
    cur_cases = {c["id"]: c for c in current["cases"]}
    lines: list[str] = []
    for case_id in sorted(set(com_cases) & set(cur_cases)):
        com = {gate._key(f): f for f in com_cases[case_id]["findings"]}
        cur = {gate._key(f): f for f in cur_cases[case_id]["findings"]}
        case_lines = []
        for key in sorted(set(com) & set(cur)):
            for field in VALUE_FIELDS:
                a, b = com[key].get(field), cur[key].get(field)
                if not _numbers_agree(a, b):
                    case_lines.append(
                        f"    value {field} moved: {_show(a)} -> {_show(b)}")
                    case_lines.append(
                        f"                       {gate._label(key)}")
        if case_lines:
            lines.append(f"  case {case_id}:")
            lines.extend(case_lines)
    return lines


def _with_values(data: dict) -> dict:
    """gate.normalize()'s canonical shape, with the value columns kept.

    gate.normalize() strips `figura`/`python` on purpose — the baseline must not
    record them. This gate needs the same canonical ORDERING and the same
    identity rules but does need the values, so it re-attaches them by identity
    from the raw document instead of reimplementing the normalisation.
    """
    normalized = gate.normalize(data)
    raw_cases = {str(c.get("id")): c for c in data["cases"]}
    for case in normalized["cases"]:
        raw = {gate._key(f): f for f in (raw_cases[str(case["id"])]
                                        .get("findings") or [])}
        for entry in case["findings"]:
            source = raw.get(gate._key(entry), {})
            for field in VALUE_FIELDS:
                entry[field] = source.get(field)
    return normalized


EXPLAINER = f"""
This step asks one question: does the evidence COMMITTED to the repo match what
this commit's code regenerates? A failure means one of two things.

  * The evidence moved and was not re-committed. Regenerate and commit it in the
    SAME commit as the change that moved it:

        make -C stats-validation clean all   # exits non-zero by design
        git add stats-validation/results/findings.json \\
                stats-validation/results/scorecard.html

  * Or the two environments genuinely disagree about a number by more than
    rel {REL_TOL} / abs {ABS_TOL}. That is a real finding about the statistics,
    not a formatting problem, and loosening this tolerance is the wrong fix —
    it is the same tolerance the comparator itself judges Path A against Path B
    with.

Structural differences (a finding added, removed, or changed in kind; a case's
coverage counts moving) are reported above by the same code the findings
baseline gate uses. Value differences are judged at the comparator's tolerance,
so a last-digit float move can never fail this step."""


def check(findings_path: Path, ref: str, tracked_path: str,
          repo_root: Path = REPO_ROOT, out=sys.stdout) -> int:
    current_raw = read_current(Path(findings_path))
    try:
        committed_raw = read_committed(ref, tracked_path, repo_root)
    except NoBaseline as why:
        # Sane absent-baseline behaviour: say what happened, and pass. The
        # commit that first adds the artifact must not be blocked by the absence
        # of the thing it is adding.
        print(f"{BANNER}: no committed baseline to compare against "
              f"({ref}:{tracked_path} — {why}). Nothing can be stale relative "
              f"to a file that is not in the tree yet; this is the expected "
              f"result for the commit that first publishes it.", file=out)
        return 0

    try:
        committed = _with_values(committed_raw)
        current = _with_values(current_raw)
    except gate.GateInputError as exc:
        raise FreshnessInputError(str(exc))

    structural = gate.diff(committed, current)
    values = value_diff(committed, current)
    if not structural and not values:
        n = sum(len(c["findings"]) for c in current["cases"])
        print(f"{BANNER}: OK — the regenerated evidence matches "
              f"{ref}:{tracked_path}. {len(current['cases'])} case(s), "
              f"{n} finding(s); structure identical, and every measured value "
              f"agrees within rel {REL_TOL} / abs {ABS_TOL}.", file=out)
        return 0

    print(f"{BANNER}: FAILED — {findings_path} is not what "
          f"{ref}:{tracked_path} says this commit publishes.", file=out)
    print("", file=out)
    for line in structural + values:
        print(line, file=out)
    print(EXPLAINER, file=out)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--findings", type=Path, default=DEFAULT_FINDINGS,
                        help="the regenerated artifact (working tree)")
    parser.add_argument("--ref", default=DEFAULT_REF,
                        help="the git ref holding the committed baseline")
    parser.add_argument("--tracked-path", default=DEFAULT_TRACKED_PATH,
                        help="repo-relative path of the artifact inside that ref")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)
    try:
        return check(args.findings, args.ref, args.tracked_path, args.repo_root)
    except FreshnessInputError as exc:
        print(f"{BANNER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

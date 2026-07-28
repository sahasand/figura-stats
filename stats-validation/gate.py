"""The findings-baseline gate: does this run's evidence still say what we
already dispositioned, and nothing else?

WHY THIS EXISTS AT ALL. `make all` exits non-zero **by design** — `logistic-dirty`
publishes 30 real findings (the app-vs-exported-script divergence of
`issues/02`) and will keep doing so until the Phase-2 app fix lands. That
leaves CI with two useless options and one useful one:

  * fail the build on a non-zero `all`  -> permanently red, so everybody learns
    to ignore it, and the day a REAL regression lands nobody looks;
  * ignore `all`'s exit code entirely   -> the job can never catch a regression,
    which is the only thing a gate is for;
  * compare the findings SET against a tracked baseline of the findings we have
    already read and accepted. Known findings pass. Anything added, removed, or
    changed in kind fails.

Only the third option is worth running, so that is what this is.

WHAT IS COMPARED, AND WHAT DELIBERATELY IS NOT.

A finding's IDENTITY is `(case, code, term, quantity)` — four stable strings.
Its KIND is `(disposition, source, note)` — what sort of problem it is, which
two artifacts disagreed, and how the comparator described it. Both are compared.

The measured VALUES (`figura`, `python`) are deliberately NOT compared. They are
floats and float-derived display strings; a last-digit move in an odds ratio is
not a regression and must not turn the build red, while a finding APPEARING,
DISAPPEARING, or changing tier is exactly what must. The baseline is a set, not
an ordering: cases are sorted by id and findings by their identity, so a
reordering inside findings.json is not a difference either.

THE DIVISION OF LABOUR — READ THIS BEFORE TRUSTING A GREEN GATE. This gate
checks IDENTITY, KIND and COVERAGE. It does NOT check values, and the omission
is total, not approximate: rewrite a finding's `figura` to 99999 and this gate
still exits 0 (verified by test_a_wildly_wrong_value_still_passes_this_gate).
That is deliberate, and it is only safe because a SECOND step owns values —
`make -C stats-validation freshness` (freshness.py), which compares the
regenerated findings against the committed artifact and judges the numbers at
the comparator's own REL_TOL/ABS_TOL. Two steps, two questions:

    gate       "is the SET of findings still the set we dispositioned?"
    freshness  "is the committed EVIDENCE what this code regenerates,
                numbers included, to the tolerance the comparator uses?"

Neither is a substitute for the other, and CI runs both. Removing `freshness`
from CI would leave the measured numbers checked by nothing at all.

COVERAGE IS COMPARED TOO, and for a reason that is easy to miss: a regression
that silently stopped comparing a clean case would remove no findings and add
none, so a findings-only gate would wave it through. Each case's `compared`
count, `passed`/`targets_met` verdicts, `targets` breakdown, and
`deferred_targets` are therefore part of the baseline, along with the top-level
totals. Coverage going UP is a failure too — it is a real change to what the
evidence claims, and it belongs in the commit that caused it.

A REMOVED FINDING IS A FAILURE, not a celebration. It means the evidence moved
and the baseline is now a stale description of the repo. That is precisely what
will happen when the Phase-2 export-path fix lands, and that fix's own PR is
where the baseline should be updated — deliberately, in the same commit,
reviewed alongside the change that earned it.

USAGE

    make -C stats-validation gate           # check (exit 0 / 1)
    make -C stats-validation gate-update    # rewrite the baseline from results/
    make -C stats-validation freshness      # the OTHER half — values (see above)

    .venv/bin/python gate.py [--update] [--findings PATH] [--baseline PATH]

Exit codes: 0 match, 1 mismatch (a readable diff is printed), 2 the inputs
could not be read at all (no findings.json, malformed JSON, duplicate keys).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_FINDINGS = HERE / "results" / "findings.json"
DEFAULT_BASELINE = HERE / "expected-findings.json"

# The four fields that IDENTIFY a finding inside its case. Chosen because every
# one of them is a stable string the comparator derives from the case
# definition and the quantity being checked — never from a measured value.
IDENTITY_FIELDS = ("code", "term", "quantity")
# The fields that describe what KIND of finding it is. Compared, but not part
# of the key: a finding whose `source` changed is the SAME finding reported
# against a different pair of artifacts, and "changed" is a more useful thing
# to print than "one removed, one added".
KIND_FIELDS = ("disposition", "source", "note")
# Per-case coverage/shape fields. `targets` and `deferred_targets` are handled
# separately because they are a dict and a list.
CASE_SCALARS = ("kind", "compared", "passed", "targets_met")

BANNER = "FINDINGS BASELINE GATE"


class GateInputError(Exception):
    """The gate could not read what it was asked to compare (exit 2)."""


def _key(finding: dict) -> tuple:
    return tuple(str(finding.get(f, "")) for f in IDENTITY_FIELDS)


def _label(key: tuple) -> str:
    code, term, quantity = key
    return f"{code} | term={term} | quantity={quantity}"


def normalize(data: dict) -> dict:
    """findings.json (or a baseline) -> the canonical, float-free comparison shape.

    Order-independent by construction: cases sorted by id, findings sorted by
    identity. Applied to BOTH sides, so the baseline file on disk is itself
    already in canonical form and a human can read a `git diff` of it.
    """
    if not isinstance(data, dict) or "cases" not in data:
        raise GateInputError("not a findings document: no top-level 'cases' key")
    cases = []
    for case in sorted(data["cases"], key=lambda c: str(c.get("id"))):
        findings = []
        seen: dict[tuple, dict] = {}
        for finding in case.get("findings") or []:
            entry = {f: finding.get(f) for f in IDENTITY_FIELDS + KIND_FIELDS}
            key = _key(entry)
            # Two findings sharing an identity would make the key ambiguous and
            # let one silently mask the other. Refuse rather than guess; if the
            # comparator ever emits such a pair, the KEY needs widening, and
            # that is a decision for a human, not a fallback.
            if key in seen:
                raise GateInputError(
                    f"case {case.get('id')!r}: two findings share the identity "
                    f"({_label(key)}). The baseline key "
                    f"(case + {' + '.join(IDENTITY_FIELDS)}) is no longer "
                    f"unique and must be widened before this gate can be trusted.")
            seen[key] = entry
            findings.append(entry)
        findings.sort(key=_key)
        cases.append({
            "id": case.get("id"),
            **{f: case.get(f) for f in CASE_SCALARS},
            "targets": dict(sorted((case.get("targets") or {}).items())),
            "deferred_targets": sorted(case.get("deferred_targets") or []),
            "findings": findings,
        })
    return {
        "total_compared": data.get("total_compared"),
        "total_findings": data.get("total_findings"),
        "cases": cases,
    }


def _read(path: Path, what: str) -> dict:
    if not path.exists():
        raise GateInputError(
            f"{what} does not exist: {path}. "
            + ("Run `make -C stats-validation all` first — compare.py writes "
               "findings.json before it returns, so its absence means the "
               "comparator did not finish."
               if what == "findings" else
               "Create it with `make -C stats-validation gate-update` and "
               "commit it alongside the evidence it describes."))
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise GateInputError(f"{what} could not be read as JSON ({path}): {exc}")


def _diff_findings(case_id: str, expected: list[dict], actual: list[dict]) -> list[str]:
    exp = {_key(f): f for f in expected}
    act = {_key(f): f for f in actual}
    lines = []
    for key in sorted(act.keys() - exp.keys()):
        f = act[key]
        lines.append(f"    + NEW finding      {_label(key)}")
        lines.append(f"                       source={f.get('source')!r} "
                     f"disposition={f.get('disposition')!r}")
        lines.append(f"                       note={f.get('note')!r}")
    for key in sorted(exp.keys() - act.keys()):
        f = exp[key]
        lines.append(f"    - GONE finding     {_label(key)}")
        lines.append(f"                       was: source={f.get('source')!r} "
                     f"disposition={f.get('disposition')!r}")
    for key in sorted(exp.keys() & act.keys()):
        changed = [
            f"                       {field}: {exp[key].get(field)!r} "
            f"-> {act[key].get(field)!r}"
            for field in KIND_FIELDS
            if exp[key].get(field) != act[key].get(field)
        ]
        if changed:
            lines.append(f"    ~ CHANGED finding  {_label(key)}")
            lines.extend(changed)
    if lines:
        lines.insert(0, f"  case {case_id}:")
    return lines


def _diff_coverage(case_id: str, expected: dict, actual: dict) -> list[str]:
    lines = []
    for field in CASE_SCALARS:
        if expected.get(field) != actual.get(field):
            lines.append(f"    coverage {field}: {expected.get(field)!r} "
                         f"-> {actual.get(field)!r}")
    exp_t, act_t = expected.get("targets") or {}, actual.get("targets") or {}
    for name in sorted(set(exp_t) | set(act_t)):
        if exp_t.get(name) != act_t.get(name):
            lines.append(f"    coverage targets[{name}]: {exp_t.get(name)!r} "
                         f"-> {act_t.get(name)!r}")
    if expected.get("deferred_targets") != actual.get("deferred_targets"):
        lines.append(f"    coverage deferred_targets: "
                     f"{expected.get('deferred_targets')!r} "
                     f"-> {actual.get('deferred_targets')!r}")
    if lines:
        lines.insert(0, f"  case {case_id}:")
    return lines


def diff(expected: dict, actual: dict) -> list[str]:
    """A readable baseline-vs-actual report. Empty list means they match."""
    lines: list[str] = []
    for field in ("total_compared", "total_findings"):
        if expected.get(field) != actual.get(field):
            lines.append(f"  totals {field}: {expected.get(field)!r} "
                         f"-> {actual.get(field)!r}")

    exp_cases = {c["id"]: c for c in expected["cases"]}
    act_cases = {c["id"]: c for c in actual["cases"]}
    for case_id in sorted(act_cases.keys() - exp_cases.keys()):
        lines.append(f"  case {case_id}: PRESENT in this run, ABSENT from the "
                     f"baseline (a new case was compared)")
    for case_id in sorted(exp_cases.keys() - act_cases.keys()):
        lines.append(f"  case {case_id}: in the baseline, ABSENT from this run "
                     f"(the case stopped being compared)")
    for case_id in sorted(exp_cases.keys() & act_cases.keys()):
        # Coverage and findings are reported under one case heading, so a case
        # that changed in both ways does not print its name twice.
        cov = _diff_coverage(case_id, exp_cases[case_id], act_cases[case_id])
        fnd = _diff_findings(case_id, exp_cases[case_id]["findings"],
                             act_cases[case_id]["findings"])
        if cov and fnd:
            lines.extend(cov + fnd[1:])
        else:
            lines.extend(cov or fnd)
    return lines


EXPLAINER = """
The baseline records the IDENTITY (case + code + term + quantity) and the KIND
(disposition, source, note) of every accepted finding, plus each case's coverage
counts. It deliberately does NOT record the measured values, so a last-digit
float move can never cause this failure — what you are seeing is a finding that
was added, removed, or changed in kind, or a change in what was compared. (The
values are not unchecked, they are checked ELSEWHERE: `make -C stats-validation
freshness` compares them against the committed artifact at the comparator's own
tolerance.)

If this change is INTENDED (a fix landed, a case was added, a disposition
changed), update the baseline in the SAME commit as the change that caused it,
never as a drive-by:

    make -C stats-validation gate-update
    git add stats-validation/expected-findings.json

If it is NOT intended, this is the regression the gate exists to catch."""


def check(findings_path: Path, baseline_path: Path, out=sys.stdout) -> int:
    actual = normalize(_read(findings_path, "findings"))
    expected = normalize(_read(baseline_path, "baseline"))
    lines = diff(expected, actual)
    if not lines:
        n = actual.get("total_findings")
        # The success line names what was NOT checked, because a reader who sees
        # only "OK" will assume this step vouched for the numbers. It did not,
        # and the step that does is named here rather than left to the docs.
        print(f"{BANNER}: OK — {n} finding(s) across "
              f"{len(actual['cases'])} case(s), all matching "
              f"{baseline_path.name}.\n"
              f"{BANNER}: checked IDENTITY (case + "
              f"{' + '.join(IDENTITY_FIELDS)}), KIND "
              f"({', '.join(KIND_FIELDS)}) and COVERAGE. The measured VALUES "
              f"were NOT checked here — `make -C stats-validation freshness` "
              f"owns those, at the comparator's own tolerance.", file=out)
        return 0
    print(f"{BANNER}: FAILED — the evidence in {findings_path} no longer "
          f"matches {baseline_path}.", file=out)
    print("", file=out)
    for line in lines:
        print(line, file=out)
    print(EXPLAINER, file=out)
    return 1


# Written into the baseline file itself so it is self-explanatory to whoever
# opens it cold, or reviews it in a diff, without first finding this module.
# `normalize()` reads only `total_compared`, `total_findings` and `cases`, so
# this key is inert on the comparison path.
BASELINE_NOTE = [
    "The accepted-findings baseline for stats-validation. Generated — do not",
    "hand-edit. `make -C stats-validation gate` fails when the pipeline's",
    "findings no longer match this file.",
    "",
    "It records each finding's IDENTITY (case + code + term + quantity) and",
    "KIND (disposition, source, note), plus each case's coverage counts. It",
    "records NO measured values: those are floats and float-derived strings",
    "that legitimately move in their last digits, and a build must not go red",
    "for that. Findings are sorted by identity and cases by id, so array order",
    "is never a difference either.",
    "",
    "Every finding listed here has been read and dispositioned. `logistic-dirty`",
    "is the only case with any: 30 export-path findings from the documented",
    "issues/02 divergence, which is why `make all` exits non-zero by design.",
    "",
    "Regenerate with `make -C stats-validation gate-update`, and commit the",
    "result IN THE SAME COMMIT as the change that moved the evidence — never",
    "as a drive-by. A finding disappearing is a failure here for exactly that",
    "reason: when the Phase-2 export-path fix lands, that PR updates this file.",
]


def update(findings_path: Path, baseline_path: Path, out=sys.stdout) -> int:
    normalized = {"_note": BASELINE_NOTE,
                  **normalize(_read(findings_path, "findings"))}
    baseline_path.write_text(json.dumps(normalized, indent=2,
                                        ensure_ascii=False) + "\n")
    print(f"{BANNER}: wrote {baseline_path} — "
          f"{normalized.get('total_findings')} finding(s) across "
          f"{len(normalized['cases'])} case(s). Commit it with the change that "
          f"moved the evidence.", file=out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true",
                        help="rewrite the baseline from the current findings")
    parser.add_argument("--findings", type=Path, default=DEFAULT_FINDINGS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args(argv)
    try:
        if args.update:
            return update(args.findings, args.baseline)
        return check(args.findings, args.baseline)
    except GateInputError as exc:
        print(f"{BANNER}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

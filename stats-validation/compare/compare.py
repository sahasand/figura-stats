"""Path A vs Path B — the comparator.

This module turns three artifacts into published findings:

  <id>.figura.json        Path A, DISPLAYED. What the screen actually showed
                          (the TSV `text` field) plus the exported .R `code`.
  <id>.figura-exact.json  Path A, FULL PRECISION. The unrounded model numbers
                          harvested by re-running Figura's own exported script.
  <id>.python.json        Path B. An independent re-implementation's numbers,
                          from stats-validation/python/validate/cli.py.

Three comparison tiers, each answering a different question:

  display tier   Does Python's number, pushed through Figura's own display
                 rule, produce the identical string the user saw? Both the
                 unadjusted and the adjusted column.
  exact tier     Do the full-precision adjusted numbers agree to rel 1e-6 /
                 abs 1e-9? est, se, lo, hi, p.
  script tier    Does the exported .R, rendered through the display rule,
                 reproduce the screen? This one never touches Path B — it is
                 an internal Path A consistency check, and a failure means the
                 user cannot reproduce what they saw.

DESIGN RULE — NO SILENT SKIPS. A quantity that cannot be compared is never
dropped; it becomes a MISSING_QUANTITY finding. Every `continue` in this file
follows a recorded finding or a structurally estimate-free row, and says so.

The display rule below (`format_ratio_cell`) and the reliability rule
(`reportable`) are RESTATEMENTS of R's `.logistic_or_cell` (R/logistic.R) and
`.ratio_reportable` (R/dispatch.R). They are written out here rather than
imported so the judge shares no code with either path it judges; the price is
that a change to R's formatting must be mirrored here, which the display-tier
comparison itself would catch on the very next run.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

# Exact-tier agreement. Relative, with an absolute floor so a true zero
# (n_dropped-like quantities, or a p-value that underflows) still compares.
REL_TOL, ABS_TOL = 1e-6, 1e-9

# Display tier. Cells are rendered at 2 dp, so a displayed "3.32" is not a
# number but an interval: Figura's true value lies in [3.315, 3.325). Half a
# display step is therefore the widest gap two agreeing values can show.
DISPLAY_DP = 2
DISPLAY_HALF_ULP = 0.5 * 10.0 ** -DISPLAY_DP

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CASES = ROOT / "cases"

EN_DASH = "–"
UNREPORTABLE = "not reliably estimated"
TABLE_HEADER_FIRST_CELL = "Characteristic"

# code -> disposition. `pass` codes never reach findings.json; `review` and
# `defect` do, and a case with any finding at all is not `passed`.
DISPOSITIONS = {
    "PASS": "pass",
    "EXACT_PASS": "pass",
    "DISPLAY_ARTIFACT": "review",
    "SCRIPT_DIVERGENCE": "defect",
    "COUNT_MISMATCH": "defect",
    "DEFECT": "defect",
    "MISSING_QUANTITY": "defect",
}
PASS_CODES = {c for c, d in DISPOSITIONS.items() if d == "pass"}

# Severity order for reporting. COUNT_MISMATCH first, deliberately: a
# disagreement about which rows were analysed means the two paths did not
# analyse the same study, and every downstream number is uninterpretable.
# MISSING_QUANTITY is next because an absent comparison is an absent guarantee.
SEVERITY = ["COUNT_MISMATCH", "MISSING_QUANTITY", "SCRIPT_DIVERGENCE",
            "DEFECT", "DISPLAY_ARTIFACT"]

# case.json `exact_targets` -> the exact-tier quantities that discharge them.
# This is the wired contract: a declared target that no performed comparison
# credits is a hole in the guarantee, not a pass.
TARGET_QUANTITIES = {
    "adjusted_or": ("est",),
    "adjusted_ci": ("lo", "hi", "se"),
    "adjusted_p": ("p",),
    "n": ("n",),
    "n_event": ("n_event",),
    "n_dropped": ("n_dropped",),
}


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------

def finding(code, term, quantity, figura, python, note):
    if code not in DISPOSITIONS:
        raise SystemExit(f"comparator bug: unknown finding code {code!r}")
    return {"code": code, "disposition": DISPOSITIONS[code], "term": term,
            "quantity": quantity, "figura": figura, "python": python,
            "note": note}


def _rank(f):
    return SEVERITY.index(f["code"]) if f["code"] in SEVERITY else len(SEVERITY)


# ---------------------------------------------------------------------------
# tolerance, display rule, reliability rule
# ---------------------------------------------------------------------------

def close_enough(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def format_p(p: float) -> str:
    """R: `if (p < 0.001) "p<0.001" else sprintf("p=%.3f", p)`."""
    return "p<0.001" if p < 0.001 else f"p={p:.3f}"


def format_ratio_cell(est: float, lo: float, hi: float, p: float) -> str:
    """R: `sprintf("%.2f (%.2f–%.2f, %s)", or, lo, hi, pf)` — en dash U+2013."""
    return f"{est:.2f} ({lo:.2f}{EN_DASH}{hi:.2f}, {format_p(p)})"


def reportable(cell: dict) -> bool:
    """R/dispatch.R `.ratio_reportable`; mirrored by validate.logistic.reportable."""
    est, lo, hi = cell["est"], cell["lo"], cell["hi"]
    if not all(math.isfinite(float(v)) for v in (est, lo, hi)):
        return False
    return float(lo) >= 1e-6 and float(hi) <= 1e6


CELL_RE = re.compile(
    r"^(?P<est>-?\d+\.\d{2}) \((?P<lo>-?\d+\.\d{2})" + EN_DASH +
    r"(?P<hi>-?\d+\.\d{2}), (?P<p>p<0\.001|p=\d+\.\d{3})\)$"
)


def parse_ratio_cell(cell: str):
    """Pull Figura's DISPLAYED numbers back out of a rendered cell.

    Strict against the display rule itself: a cell that does not match is a
    finding, never a shrug.
    """
    m = CELL_RE.match(cell)
    if m is None:
        return None
    return {"est": float(m["est"]), "lo": float(m["lo"]), "hi": float(m["hi"]),
            "p_text": m["p"]}


def display_agrees(value: float, shown: float) -> bool:
    """Could `value` and the true number behind `shown` be the same number?

    `shown` is a 2-dp rendering, so it stands for the interval
    [shown - 0.005, shown + 0.005). `value` agrees with SOME point of that
    interval when it is within half a display step of `shown`, widened by the
    exact-tier tolerance — that last term is what makes a value sitting a
    whisker past the rounding boundary (and so rendering one step away) read
    as the boundary artifact it is, rather than as arithmetic.
    """
    value, shown = float(value), float(shown)
    slack = max(ABS_TOL, REL_TOL * max(abs(value), abs(shown)))
    return abs(value - shown) <= DISPLAY_HALF_ULP + slack


def classify_cell(term: str, figura_cell: str, python: dict,
                  quantity: str = "displayed cell") -> dict:
    """One displayed cell, Path A vs Path B. Returns a finding (maybe PASS)."""
    py_ok = reportable(python)

    # Addendum 7 — the unreportable disposition. Agreeing that a cell cannot be
    # estimated is a real agreement, and disagreeing about it is a real defect.
    if figura_cell == UNREPORTABLE:
        if not py_ok:
            return finding("PASS", term, quantity, figura_cell, UNREPORTABLE,
                           "both paths agree the cell is unreportable")
        return finding(
            "DEFECT", term, quantity, figura_cell,
            format_ratio_cell(python["est"], python["lo"], python["hi"], python["p"]),
            "Figura suppressed the cell as unreliable; Python reports a value")
    if not py_ok:
        return finding("DEFECT", term, quantity, figura_cell, UNREPORTABLE,
                       "Python's cell fails the reliability rule; Figura "
                       "displayed a value")

    rendered = format_ratio_cell(python["est"], python["lo"], python["hi"],
                                 python["p"])
    if rendered == figura_cell:
        return finding("PASS", term, quantity, figura_cell, rendered,
                       "Python's value through Figura's display rule is the "
                       "identical string")

    shown = parse_ratio_cell(figura_cell)
    if shown is None:
        return finding("DEFECT", term, quantity, figura_cell, rendered,
                       "Figura's cell does not match the display rule and "
                       "could not be read back")

    # Addendum 6 — a differing p-part is never an artifact. The p-value carries
    # the inferential claim; a rounding story cannot excuse moving it.
    if shown["p_text"] != format_p(python["p"]):
        return finding("DEFECT", term, quantity, figura_cell, rendered,
                       "the p-value part differs; a p disagreement is never a "
                       "display artifact")

    same = all(display_agrees(python[q], shown[q]) for q in ("est", "lo", "hi"))
    if same:
        return finding("DISPLAY_ARTIFACT", term, quantity, figura_cell, rendered,
                       "values agree to within half a display step; the "
                       "rendered strings differ")
    return finding("DEFECT", term, quantity, figura_cell, rendered,
                   "displayed values disagree by more than a rounding boundary")


# ---------------------------------------------------------------------------
# row keys
# ---------------------------------------------------------------------------

def display_key(term: str, covariates) -> str:
    """A model coefficient name -> the comparator's row key.

    R and statsmodels both name a categorical coefficient by concatenating the
    covariate and the level with no separator (`armNew treatment`). Levels
    contain spaces, so the split is by LONGEST covariate prefix — never on
    whitespace, and longest first so `stage` cannot claim `stage2`'s
    coefficients.

    Path B derives the same keys independently in validate/cli.py
    (`display_label`); the two are kept as separate implementations on purpose,
    and a divergence surfaces loudly as MISSING_QUANTITY rather than as a
    quietly-matched wrong row.
    """
    if term in covariates:
        return term  # numeric covariate: the coefficient IS the covariate
    matches = [c for c in covariates if term.startswith(c)]
    if not matches:
        return term  # unmatched: kept verbatim so it surfaces as a finding
    cov = max(matches, key=len)
    return f"{cov}:{term[len(cov):]}"


def _strip_backticks(term: str) -> str:
    """R backticks a non-syntactic covariate name in the model formula, so its
    coefficients read ```study arm`Treated``. That is naming, not a
    statistical claim, so it is normalised away before term matching."""
    return term.replace("`", "")


def numeric_row_label(cov: str, increments) -> str:
    """R: `sprintf("%s (per %g units)", cl, k)`, or "per 1 unit" when k == 1."""
    k = float(increments.get(cov, 1) or 1)
    return f"{cov} (per 1 unit)" if k == 1 else f"{cov} (per {k:g} units)"


# ---------------------------------------------------------------------------
# the displayed table
# ---------------------------------------------------------------------------

HEADER_ROW_RE = re.compile(r"^(?P<cov>.+) \(reference: (?P<ref>.+)\)$")
NUMERIC_ROW_RE = re.compile(r"^(?P<cov>.+) \(per (?P<unit>.+)\)$")


def parse_ratio_tsv(text: str, case: dict):
    """The real shipped row model, verified against fig_logistic's output.

    After the column header line, a categorical covariate emits
    `"<cov> (reference: <level>)"` with EMPTY unadjusted/adjusted cells,
    followed by BARE level rows (fig_logistic calls trimws() on the term, so
    the two-space indent never reaches `text` — level rows are recognised
    positionally, by the reference header above them, never by whitespace).
    A numeric covariate emits a single `"<cov> (per <k> units)"` row.

    Returns (rows, findings). Each row is
    {key, label, unadj, adj} where key is `"<cov>:<level>"` or `"<cov>"` —
    never a bare level name, which would collide across covariates.
    """
    covariates = list(case["roles"]["covariates"])
    options = case.get("options", {})
    ref_levels = options.get("ref_levels", {})
    increments = options.get("increments", {})

    findings = []
    rows = []
    seen_keys = {}

    tsv = text.split("\n\n")[0]
    lines = [ln for ln in tsv.split("\n") if ln.strip() != ""]
    if not lines:
        findings.append(finding("DEFECT", "-", "displayed table", "", None,
                                "the displayed output carries no table"))
        return rows, findings

    head = [c.strip() for c in lines[0].split("\t")]
    if len(head) != 3 or head[0] != TABLE_HEADER_FIRST_CELL:
        findings.append(finding(
            "DEFECT", "-", "table header", lines[0], None,
            f"expected a 3-column header starting {TABLE_HEADER_FIRST_CELL!r}"))

    current_cov = None
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != 3:
            findings.append(finding(
                "DEFECT", parts[0].strip(), "displayed row", line, None,
                "row does not carry exactly 3 tab-separated cells"))
            continue  # NOT a silent skip: the malformed row was just recorded
        label, unadj, adj = (p.strip() for p in parts)

        m = HEADER_ROW_RE.match(label)
        if m is not None and m["cov"] in covariates:
            current_cov = m["cov"]
            if unadj or adj:
                findings.append(finding(
                    "DEFECT", current_cov, "displayed row", line, None,
                    "reference header row carries effect cells; it must be "
                    "empty in both columns"))
            expected_ref = ref_levels.get(current_cov)
            if expected_ref is not None and m["ref"] != expected_ref:
                findings.append(finding(
                    "DEFECT", current_cov, "reference level", m["ref"],
                    expected_ref,
                    "the displayed reference level differs from the case spec"))
            continue  # NOT a silent skip: a header row carries no estimate

        m = NUMERIC_ROW_RE.match(label)
        if m is not None and m["cov"] in covariates:
            cov = m["cov"]
            expected = numeric_row_label(cov, increments)
            if label != expected:
                findings.append(finding(
                    "DEFECT", cov, "increment label", label, expected,
                    "the displayed per-unit label does not match the case's "
                    "declared increment"))
            key = cov
            current_cov = None  # a numeric row closes any categorical block
        else:
            if current_cov is None:
                findings.append(finding(
                    "MISSING_QUANTITY", label, "displayed row", line, None,
                    "estimate row with no preceding reference header; it "
                    "cannot be keyed to a covariate"))
                continue  # NOT a silent skip: the unkeyable row was recorded
            key = f"{current_cov}:{label}"

        if key in seen_keys:
            findings.append(finding(
                "DEFECT", key, "displayed row", line, None,
                "two displayed rows resolve to the same key"))
        seen_keys[key] = True
        rows.append({"key": key, "label": label, "unadj": unadj, "adj": adj})

    return rows, findings


# ---------------------------------------------------------------------------
# per-kind comparison
# ---------------------------------------------------------------------------

class _Targets:
    """Credits exact_targets as comparisons are actually performed."""

    def __init__(self, declared):
        self.declared = list(declared)
        self.counts = {t: 0 for t in self.declared}
        self.by_quantity = {}
        for target, quantities in TARGET_QUANTITIES.items():
            for q in quantities:
                self.by_quantity.setdefault(q, []).append(target)

    def credit(self, quantity):
        for target in self.by_quantity.get(quantity, ()):
            if target in self.counts:
                self.counts[target] += 1

    def findings(self):
        out = []
        for target in self.declared:
            if target not in TARGET_QUANTITIES:
                out.append(finding(
                    "MISSING_QUANTITY", "-", target, None, None,
                    "declared exact target is not wired to any comparison "
                    "this comparator performs"))
            elif self.counts[target] == 0:
                out.append(finding(
                    "MISSING_QUANTITY", "-", target, None, None,
                    "declared exact target had zero comparisons performed"))
        return out

    @property
    def met(self):
        return all(t in TARGET_QUANTITIES and self.counts[t] > 0
                   for t in self.declared)


def compare_ratio_table(case, figura, exact, python):
    """The full ratio_table branch: display, exact, and script tiers."""
    findings = []
    compared = 0
    targets = _Targets(case.get("exact_targets", []))
    covariates = list(case["roles"]["covariates"])

    # -- counts. The highest-severity class: if the two paths disagree about
    # which rows were analysed, nothing downstream is interpretable.
    for key in ("n", "n_event", "n_dropped"):
        a, b = exact.get(key), python.get(key)
        if a is None or b is None:
            missing = "Path A" if a is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", "-", key, a, b,
                f"{missing} did not report {key}; the count could not be "
                "compared"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        targets.credit(key)
        if a != b:
            findings.append(finding(
                "COUNT_MISMATCH", "-", key, a, b,
                "the two paths analysed different rows"))

    # -- display tier, BOTH columns.
    text = figura.get("text")
    if not isinstance(text, str):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed table", text, None,
            "Path A's displayed artifact has no `text` field to parse"))
        text = ""
    rows, parse_findings = parse_ratio_tsv(text, case)
    findings.extend(parse_findings)
    rows_by_key = {r["key"]: r for r in rows}

    # A ratio_table with nothing in it must never pass: every loop below is
    # driven by these two collections, so an empty one means the comparison
    # ran and proved nothing at all.
    if not rows:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed table", text, None,
            "the displayed table carried no estimate rows to compare"))
    if not exact.get("terms"):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "exact terms", None, None,
            "the exported script's harvest carried no terms to compare"))

    columns = (
        ("unadjusted", "unadj", "display_unadjusted"),
        ("adjusted", "adj", "display_terms"),
    )
    for row in rows:
        for label, cell_key, py_field in columns:
            py_cells = python.get(py_field) or {}
            cell = py_cells.get(row["key"])
            if cell is None:
                findings.append(finding(
                    "MISSING_QUANTITY", row["key"], f"displayed {label} cell",
                    row[cell_key], None,
                    f"no Path B {label} term maps to this displayed row"))
                continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
            compared += 1
            f = classify_cell(row["key"], row[cell_key], cell,
                              quantity=f"displayed {label} cell")
            if f["code"] not in PASS_CODES:
                findings.append(f)

    # -- the other direction: a Path B term the screen never showed.
    for label, _cell_key, py_field in columns:
        for key in (python.get(py_field) or {}):
            if key not in rows_by_key:
                findings.append(finding(
                    "MISSING_QUANTITY", key, f"displayed {label} cell", None,
                    key, f"Path B produced a {label} term with no displayed "
                         "row to compare it against"))

    # -- exact tier, adjusted terms only (the unadjusted column is a display
    # claim; only the joint model is harvested at full precision).
    #
    # `se` is compared explicitly and separately from lo/hi: lo and hi are
    # built as exp(est ± 1.96·se) on BOTH sides, so agreement there is partly
    # tautological once est and se agree. se is the primary standard-error
    # evidence, and a CI that agrees while se does not would mean one path
    # built its interval from something other than its own model.
    exact_terms = {_strip_backticks(k): v for k, v in exact.get("terms", {}).items()}
    py_terms = python.get("terms") or {}
    for key in sorted(set(exact_terms) | set(py_terms)):
        a, b = exact_terms.get(key), py_terms.get(key)
        if a is None or b is None:
            missing = "Path A" if a is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", display_key(key, covariates), "exact term",
                key if a is not None else None, key if b is not None else None,
                f"{missing} has no full-precision term {key!r}"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        for q in ("est", "se", "lo", "hi", "p"):
            av, bv = a.get(q), b.get(q)
            if av is None or bv is None:
                missing = "Path A" if av is None else "Path B"
                findings.append(finding(
                    "MISSING_QUANTITY", display_key(key, covariates), q, av, bv,
                    f"{missing} did not report {q} for {key!r}"))
                continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
            compared += 1
            targets.credit(q)
            if not close_enough(float(av), float(bv)):
                findings.append(finding(
                    "DEFECT", display_key(key, covariates), q, av, bv,
                    f"beyond rel {REL_TOL} / abs {ABS_TOL}"))

    # -- script tier. Path A against itself: does the exported .R, rendered
    # through the display rule, reproduce the adjusted column the user saw?
    # Independent of Path B — a failure here means the user cannot reproduce
    # what was on screen, whatever Python says.
    for key in sorted(exact_terms):
        cell = exact_terms[key]
        dkey = display_key(key, covariates)
        row = rows_by_key.get(dkey)
        if row is None:
            findings.append(finding(
                "MISSING_QUANTITY", dkey, "exported script cell", key, None,
                "the exported script produced a term with no displayed row"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        try:
            rendered = (format_ratio_cell(cell["est"], cell["lo"], cell["hi"],
                                          cell["p"])
                        if reportable(cell) else UNREPORTABLE)
        except (KeyError, TypeError, ValueError):
            findings.append(finding(
                "MISSING_QUANTITY", dkey, "exported script cell", cell, None,
                "the exported script's term could not be rendered"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        if rendered != row["adj"]:
            findings.append(finding(
                "SCRIPT_DIVERGENCE", dkey, "exported script cell", row["adj"],
                rendered,
                "the exported .R does not reproduce the adjusted cell the "
                "screen showed"))

    findings.extend(targets.findings())
    return findings, compared, targets


# Per-kind dispatch. Registering a kind is the ONLY way to compare it: an
# unregistered kind stops loudly rather than being waved through as "nothing
# to compare", which would publish a green result backed by zero evidence.
KIND_HANDLERS = {"ratio_table": compare_ratio_table}

PENDING_KINDS = {
    "km_summary": "Task 9 (Kaplan-Meier)",
    "gc_summary": "Task 10 (group comparison)",
    "table1": "Task 11 (Table 1 / summary)",
}


# ---------------------------------------------------------------------------
# case wiring
# ---------------------------------------------------------------------------

def _load(path: Path):
    if not path.exists():
        raise SystemExit(f"comparator: missing artifact {path.name} ({path})")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"comparator: {path.name} is not valid JSON: {exc}")


def compare_case(case_id: str, results: Path = RESULTS,
                 cases: Path = CASES) -> dict:
    results, cases = Path(results), Path(cases)
    case = _load(cases / case_id / "case.json")
    figura = _load(results / f"{case_id}.figura.json")
    exact = _load(results / f"{case_id}.figura-exact.json")
    python = _load(results / f"{case_id}.python.json")

    kind = (case.get("display") or {}).get("kind")
    handler = KIND_HANDLERS.get(kind)
    if handler is None:
        pending = PENDING_KINDS.get(kind)
        detail = (f"display.kind {kind!r} arrives with {pending}"
                  if pending else f"unknown display.kind {kind!r}")
        raise SystemExit(
            f"comparator: no comparison implemented for {case_id} — {detail}. "
            f"Implemented kinds: {sorted(KIND_HANDLERS)}.")

    findings, compared, targets = handler(case, figura, exact, python)
    findings.sort(key=_rank)
    return {
        "id": case_id,
        "kind": kind,
        "compared": compared,
        "passed": len(findings) == 0,
        "targets_met": targets.met,
        "targets": dict(targets.counts),
        "findings": findings,
    }


def main(case_ids, results: Path = RESULTS, cases: Path = CASES) -> int:
    if not case_ids:
        raise SystemExit("usage: compare.py <case-id> [<case-id> ...]")
    results = Path(results)
    reports = [compare_case(c, results=results, cases=cases) for c in case_ids]
    out = {
        "cases": reports,
        "total_compared": sum(c["compared"] for c in reports),
        "total_findings": sum(len(c["findings"]) for c in reports),
    }
    (results / "findings.json").write_text(json.dumps(out, indent=2) + "\n")
    for c in reports:
        status = "PASS" if c["passed"] else f"{len(c['findings'])} finding(s)"
        met = "targets met" if c["targets_met"] else "TARGETS UNMET"
        print(f"{c['id']}: {c['compared']} compared, {status}, {met}")
        for f in c["findings"]:
            print(f"  [{f['disposition']:6}] {f['code']} {f['term']} "
                  f"{f['quantity']}: figura={f['figura']!r} "
                  f"python={f['python']!r} — {f['note']}")
    ok = all(c["passed"] and c["targets_met"] for c in reports)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

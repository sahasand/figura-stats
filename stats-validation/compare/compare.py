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

# KM's median survival is displayed at 1 dp (`sprintf("%.1f", x)` in
# R/km.R), not 2 — its own half-display-step, kept separate from the
# ratio-table constant above rather than reusing it under a different name.
KM_DISPLAY_DP = 1
KM_DISPLAY_HALF_ULP = 0.5 * 10.0 ** -KM_DISPLAY_DP

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CASES = ROOT / "cases"

EN_DASH = "–"
UNREPORTABLE = "not reliably estimated"
TABLE_HEADER_FIRST_CELL = "Characteristic"

# code -> disposition. `pass` codes never reach findings.json; `review` and
# `defect` do, and a case with any finding at all is not `passed`.
#
# The plan's taxonomy also listed EXACT_PASS ("exact values agree"), but this
# comparator never emits it: the exact tier counts an agreement in `compared`
# and stays silent, exactly as the display tier does for PASS. A published
# vocabulary entry that nothing can ever emit invites a reader to conclude a
# tier ran when it did not, so it is not declared here.
DISPOSITIONS = {
    "PASS": "pass",
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
    "adjusted_hr": ("est",),  # Cox's name for the same ratio-scale estimate
    "adjusted_ci": ("lo", "hi", "se"),
    "adjusted_p": ("p",),
    "n": ("n",),
    "n_event": ("n_event",),
    "n_dropped": ("n_dropped",),
    # km_summary's own targets: each names itself directly, since km_summary
    # has no shared ratio-scale abstraction (est/lo/hi/p) to alias into —
    # unlike adjusted_hr/adjusted_or above, credited only by the EXACT tier
    # (exact.json vs python.json), never by the display-tier text parse, per
    # the same convention ratio_table's own targets follow.
    "median_survival": ("median_survival",),
    "logrank_p": ("logrank_p",),
    "curve": ("curve",),
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


def cell_values(cell):
    """est/lo/hi/p as floats, or None when the cell is not a usable cell.

    A Path B cell missing a quantity (or carrying a non-numeric one) is a hole
    in the evidence, not a crash: the script tier already maps that shape to
    MISSING_QUANTITY, and the display tier does the same via this helper, so
    the same malformed input never raises on one tier and reports on the other.
    """
    if not isinstance(cell, dict):
        return None
    try:
        return {q: float(cell[q]) for q in ("est", "lo", "hi", "p")}
    except (KeyError, TypeError, ValueError):
        return None


def classify_cell(term: str, figura_cell: str, python: dict,
                  quantity: str = "displayed cell") -> dict:
    """One displayed cell, Path A vs Path B. Returns a finding (maybe PASS)."""
    py = cell_values(python)
    if py is None:
        return finding(
            "MISSING_QUANTITY", term, quantity, figura_cell, python,
            "Path B's cell is missing est/lo/hi/p or carries a non-numeric "
            "value; the displayed cell could not be compared")
    python = py
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
        # Vacuity guard, mirroring the empty-table and empty-harvest guards
        # below: `all([])` is True, so a case.json that lost (or never grew)
        # its exact_targets key would publish `targets_met: true` and exit 0
        # while guaranteeing nothing. A coverage claim with no declared
        # coverage is not a pass.
        if not self.declared:
            out.append(finding(
                "MISSING_QUANTITY", "-", "exact_targets", None, None,
                "the case declares no exact_targets; there is no coverage "
                "contract for this case to meet"))
            return out
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
        # `bool(self.declared)` first: an empty contract is never "met".
        return bool(self.declared) and all(
            t in TARGET_QUANTITIES and self.counts[t] > 0
            for t in self.declared)


def compare_ratio_table(case, figura, exact, python):
    """The full ratio_table branch: display, exact, and script tiers."""
    findings = []
    compared = 0
    # `or []` so an explicit null reads as "no contract" and hits the vacuity
    # guard, rather than raising inside _Targets.
    targets = _Targets(case.get("exact_targets") or [])
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
            f = classify_cell(row["key"], row[cell_key], cell,
                              quantity=f"displayed {label} cell")
            if f["code"] == "MISSING_QUANTITY":
                # The cell was unusable, so no comparison happened: record the
                # hole and do NOT credit `compared` with a comparison that was
                # never performed.
                findings.append(f)
                continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
            compared += 1
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


# ---------------------------------------------------------------------------
# km_summary: the free-text methods sentence, checked against R/km.R reality.
#
# Unlike ratio_table's TSV, fig_km's `text` carries no table at all — just a
# prose sentence with a per-group median clause and (for >= 2 groups) a
# log-rank clause. Verified against a real run of this exact case:
#   "HR 1.56 (Standard care vs New treatment; 95% CI 0.90-2.71); log-rank
#   p = 0.108. Median survival: New treatment not reached; Standard care
#   26.0 Time."
# The HR clause is not one of km_summary's targets and is never parsed here.
# ---------------------------------------------------------------------------

# R: `fmt_p <- function(p) if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)`
# WITH spaces around "=" / "<" — deliberately not `format_p` above, which
# restates the DIFFERENT, space-free ratio-table convention (`p=%.3f`).
def format_p_km(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


# R: `fmt1 <- function(x) sprintf("%.1f", x)`.
def format_median_km(value: float) -> str:
    return f"{value:.1f}"


LOGRANK_RE = re.compile(r"[Ll]og-rank (p (?:< 0\.001|= \d+\.\d{3}))")


def parse_km_logrank(text: str):
    """Pull the displayed log-rank p-phrase out of fig_km's text, or None."""
    m = LOGRANK_RE.search(text)
    return m.group(1) if m else None


def parse_km_group_median(text: str, group: str):
    """What Figura displayed for one group's median line, or None if that
    group's phrase cannot be found in the text at all.

    Returns {"not_reached": True, "raw": <matched text>} or
    {"value": <float>, "raw": <matched text>}. Matched by the LITERAL group
    name (known independently from exact/python's own median/curve keys, not
    guessed from the text), the same "search for something already known"
    approach `display_key`/`parse_ratio_cell` use elsewhere in this file —
    not a generic decomposition of arbitrary prose.
    """
    esc = re.escape(group)
    m = re.search(rf"\b{esc} not reached\b", text)
    if m is not None:
        return {"not_reached": True, "raw": m.group(0)}
    m = re.search(rf"\b{esc} (\d+\.\d)\b", text)
    if m is not None:
        return {"value": float(m.group(1)), "raw": m.group(0)}
    return None


def display_agrees_km(value: float, shown: float) -> bool:
    """km's own half-display-step rule, mirroring `display_agrees` above at
    1 dp instead of 2 (R/km.R's `fmt1` is `sprintf("%.1f", x)`)."""
    value, shown = float(value), float(shown)
    slack = max(ABS_TOL, REL_TOL * max(abs(value), abs(shown)))
    return abs(value - shown) <= KM_DISPLAY_HALF_ULP + slack


def classify_km_median_display(group: str, shown, python_value) -> dict:
    """One group's displayed median line, Path A vs Path B. Mirrors
    classify_cell's PASS/DISPLAY_ARTIFACT/DEFECT/MISSING_QUANTITY shape."""
    if shown is None:
        return finding(
            "MISSING_QUANTITY", group, "displayed median", None, python_value,
            "the displayed text carries no median phrase for this group")
    if shown.get("not_reached"):
        if python_value is None:
            return finding("PASS", group, "displayed median", shown["raw"],
                           "not reached",
                           "both paths agree the median was not reached")
        return finding(
            "DEFECT", group, "displayed median", shown["raw"], python_value,
            "Figura displayed 'not reached'; Python computed a value")
    if python_value is None:
        return finding(
            "DEFECT", group, "displayed median", shown["raw"], "not reached",
            "Figura displayed a value; Python reports the median as not "
            "reached")
    rendered = format_median_km(python_value)
    rendered_phrase = f"{group} {rendered}"
    if rendered == f"{shown['value']:.1f}":
        return finding("PASS", group, "displayed median", shown["raw"],
                       rendered_phrase, "Python's value through Figura's "
                       "display rule is the identical string")
    if display_agrees_km(python_value, shown["value"]):
        return finding(
            "DISPLAY_ARTIFACT", group, "displayed median", shown["raw"],
            rendered_phrase, "values agree to within half a display step; "
            "the rendered strings differ")
    return finding(
        "DEFECT", group, "displayed median", shown["raw"], rendered_phrase,
        "displayed values disagree by more than a rounding boundary")


def classify_km_logrank_display(shown_text, python_p) -> dict:
    """The displayed log-rank p-phrase, Path A vs Path B."""
    if shown_text is None:
        return finding(
            "MISSING_QUANTITY", "-", "displayed logrank", None, python_p,
            "the displayed text carries no log-rank phrase")
    if python_p is None:
        return finding(
            "MISSING_QUANTITY", "-", "displayed logrank", shown_text, None,
            "no Path B log-rank p to compare against the displayed text")
    rendered = format_p_km(python_p)
    if rendered == shown_text:
        return finding(
            "PASS", "-", "displayed logrank", shown_text, rendered,
            "Python's log-rank p through Figura's display rule is the "
            "identical string")
    # Mirrors addendum 6 above: a differing p-part is never a display
    # artifact, so there is no "close enough" leniency here at all.
    return finding(
        "DEFECT", "-", "displayed logrank", shown_text, rendered,
        "the log-rank p-value part differs; a p disagreement is never a "
        "display artifact")


def compare_km_summary(case, figura, exact, python):
    """The full km_summary branch: counts, curve, medians, log-rank p (exact
    tier), and the displayed methods-sentence median/log-rank clauses
    (display tier)."""
    findings = []
    compared = 0
    targets = _Targets(case.get("exact_targets") or [])

    # -- counts. Same shape/severity as compare_ratio_table's own count loop.
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

    # -- exact tier: curve. The strongest check available for KM — it
    # compares the entire step function, not just a headline number.
    exact_curve = exact.get("curve") or {}
    python_curve = python.get("curve") or {}
    if not exact_curve:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "curve", None, None,
            "Path A's harvest carried no curve to compare"))
    if not python_curve:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "curve", None, None,
            "Path B produced no curve to compare"))
    for group in sorted(set(exact_curve) | set(python_curve)):
        a_points = {p["t"]: p for p in exact_curve.get(group, [])}
        b_points = {p["t"]: p for p in python_curve.get(group, [])}
        # Symmetric: a Path B time with no Path A match, AND a Path A time
        # with no Path B match, are both MISSING_QUANTITY — never a silent
        # skip in either direction (addendum 4).
        for t in sorted(set(a_points) | set(b_points)):
            ap, bp = a_points.get(t), b_points.get(t)
            if ap is None or bp is None:
                missing = "Path A" if ap is None else "Path B"
                findings.append(finding(
                    "MISSING_QUANTITY", group, f"curve t={t:g}", ap, bp,
                    f"{missing} has no curve point at this time"))
                continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
            # surv and at_risk are two independent pieces of evidence about
            # the same point; each is compared and credited on its own.
            compared += 1
            targets.credit("curve")
            if not close_enough(ap["surv"], bp["surv"]):
                findings.append(finding(
                    "DEFECT", group, f"S(t={t:g})", ap["surv"], bp["surv"],
                    "survival estimate disagrees"))
            compared += 1
            targets.credit("curve")
            if ap["at_risk"] != bp["at_risk"]:
                findings.append(finding(
                    "DEFECT", group, f"at_risk(t={t:g})", ap["at_risk"],
                    bp["at_risk"], "number at risk disagrees"))

    # -- exact tier: median survival per group. Addendum: both-not-reached
    # (both None) is a real agreement (PASS, no finding); one-sided
    # not-reached is a DEFECT, never smoothed over as a display artifact.
    exact_medians = exact.get("medians") or {}
    python_medians = python.get("medians") or {}
    if not exact_medians:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "median_survival", None, None,
            "Path A's harvest carried no medians to compare"))
    if not python_medians:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "median_survival", None, None,
            "Path B produced no medians to compare"))
    for group in sorted(set(exact_medians) | set(python_medians)):
        if group not in exact_medians or group not in python_medians:
            missing = "Path A" if group not in exact_medians else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", group, "median_survival",
                exact_medians.get(group), python_medians.get(group),
                f"{missing} has no median for this group"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        a, b = exact_medians[group], python_medians[group]
        compared += 1
        targets.credit("median_survival")
        if a is None and b is None:
            pass  # both not-reached: a real agreement, not a hole.
        elif a is None or b is None:
            findings.append(finding(
                "DEFECT", group, "median_survival", a, b,
                "one path reports the median as not reached, the other a "
                "value"))
        elif not close_enough(a, b):
            findings.append(finding(
                "DEFECT", group, "median_survival", a, b,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))

    # -- exact tier: log-rank p.
    lr_a, lr_b = exact.get("logrank_p"), python.get("logrank_p")
    if lr_a is None or lr_b is None:
        missing = "Path A" if lr_a is None else "Path B"
        findings.append(finding(
            "MISSING_QUANTITY", "-", "logrank_p", lr_a, lr_b,
            f"{missing} did not report a log-rank p-value"))
    else:
        compared += 1
        targets.credit("logrank_p")
        if not close_enough(lr_a, lr_b):
            findings.append(finding(
                "DEFECT", "-", "logrank_p", lr_a, lr_b,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))

    # -- display tier. Path B's own numbers, pushed through Figura's real
    # display rule (format_p_km/format_median_km), string-compared against
    # what the screen actually showed. Independent of the exact tier above —
    # run over the SAME group union so a Path B absence is flagged here too,
    # exactly as compare_ratio_table's display loop independently flags it
    # alongside its own exact-tier MISSING_QUANTITY.
    text = figura.get("text")
    if not isinstance(text, str):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed text", text, None,
            "Path A's displayed artifact has no `text` field to parse"))
        text = ""
    for group in sorted(set(exact_medians) | set(python_medians)):
        shown = parse_km_group_median(text, group)
        if shown is None:
            findings.append(finding(
                "MISSING_QUANTITY", group, "displayed median", None,
                python_medians.get(group),
                "the displayed text carries no median phrase for this "
                "group"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        if group not in python_medians:
            findings.append(finding(
                "MISSING_QUANTITY", group, "displayed median", shown["raw"],
                None, "no Path B median for this group"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        f = classify_km_median_display(group, shown, python_medians[group])
        if f["code"] != "PASS":
            findings.append(f)

    shown_logrank = parse_km_logrank(text)
    if shown_logrank is None:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed logrank", None, lr_b,
            "the displayed text carries no log-rank phrase"))
    elif lr_b is None:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed logrank", shown_logrank,
            None, "no Path B log-rank p to compare against the displayed "
            "text"))
    else:
        compared += 1
        f = classify_km_logrank_display(shown_logrank, lr_b)
        if f["code"] != "PASS":
            findings.append(f)

    findings.extend(targets.findings())
    return findings, compared, targets


# Per-kind dispatch. Registering a kind is the ONLY way to compare it: an
# unregistered kind stops loudly rather than being waved through as "nothing
# to compare", which would publish a green result backed by zero evidence.
KIND_HANDLERS = {"ratio_table": compare_ratio_table, "km_summary": compare_km_summary}

PENDING_KINDS = {
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
    # allow_nan=False: Python's json writes bare NaN/Infinity by default, which
    # is not valid JSON and would hand every downstream reader (the scorecard,
    # any jq) a file it cannot parse — or, worse, one it parses differently.
    # A non-finite number in a finding means a path produced garbage; stop and
    # say so rather than publishing an unparseable scorecard input.
    try:
        payload = json.dumps(out, indent=2, allow_nan=False) + "\n"
    except ValueError as exc:
        culprits = [
            f"{c['id']} {f['term']}/{f['quantity']}"
            for c in reports for f in c["findings"]
            if any(isinstance(v, float) and not math.isfinite(v)
                   for v in (f["figura"], f["python"]))
        ]
        raise SystemExit(
            "comparator: refusing to write findings.json — a finding carries a "
            f"non-finite number (NaN/Infinity is not valid JSON): {exc}"
            + (f" [{', '.join(culprits)}]" if culprits else ""))
    (results / "findings.json").write_text(payload)
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

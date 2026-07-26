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
                 (screen vs Path B)
  exact tier     Do the full-precision adjusted numbers agree to rel 1e-6 /
                 abs 1e-9? est, se, lo, hi, p. The Path A side here is the
                 EXPORTED SCRIPT's harvest, so an exact-tier finding indicts
                 the exported .R, not necessarily the screen.
                 (exported script vs Path B)
  script tier    Does the exported .R, rendered through the display rule,
                 reproduce the screen? This one never touches Path B — it is
                 an internal Path A consistency check, and a failure means the
                 user cannot reproduce what they saw.
                 (screen vs exported script)

The advisory DIAGNOSTICS (C-statistic, VIF, EPV, Cook's distance, the
separation caution, cox.zph) are judged on the same three tiers where the
evidence for each exists, plus one claim the estimates do not have: whether the
advisory SENTENCE fires at all, which is its own finding code
(DIAGNOSTIC_MISMATCH). See the diagnostics section further down.

Every finding therefore carries a `source` naming which two things it compared
— see the SRC_* constants. "Figura" alone is ambiguous, and the ambiguity is
not academic: logistic-dirty's display tier PASSES while its exact tier fails,
which means the screen was right and the export path was wrong.

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

# Group comparison renders every number in its sentence through R's `.fmt_num`
# (R/summarize.R): `format(signif(v, 3), scientific = FALSE, drop0trailing =
# TRUE)`. That is SIGNIFICANT figures, not decimal places, so unlike the two
# constants above there is no single half-display-step — the step depends on
# the value's magnitude. See `gc_display_half_ulp`.
GC_SIGNIF_DIGITS = 3

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
    "DECISION_MISMATCH": "defect",
    "DIAGNOSTIC_MISMATCH": "defect",
    "DEFECT": "defect",
    "MISSING_QUANTITY": "defect",
}
PASS_CODES = {c for c, d in DISPOSITIONS.items() if d == "pass"}

# Severity order for reporting. COUNT_MISMATCH first, deliberately: a
# disagreement about which rows were analysed means the two paths did not
# analyse the same study, and every downstream number is uninterpretable.
# MISSING_QUANTITY is next because an absent comparison is an absent guarantee.
#
# DECISION_MISMATCH sits above SCRIPT_DIVERGENCE and DEFECT: Table 1's choice of
# mean +/- SD vs median (IQR) is itself a published output, and a wrong CHOICE
# invalidates the whole row even when every number in it is individually
# correct. It is a claim about the variable, not about one cell.
#
# DIAGNOSTIC_MISMATCH sits BELOW DEFECT, and the ordering is the argument for
# the code existing at all. The advisory diagnostics (C-statistic, VIF, EPV,
# Cook's distance, the separation caution, cox.zph) never gate a fit and never
# change a reported estimate — R/logistic.R and R/cox.R both say so in as many
# words — so a disagreement about whether one of their sentences FIRES is
# strictly less grave than a disagreement about a published odds ratio. It is
# still a defect: the sentence is printed for the user and pasted into a
# manuscript, and "the assumption may not hold" appearing on one path and not
# the other is a real, publishable disagreement.
#
# It is a SEPARATE code rather than DEFECT for the same reason DECISION_MISMATCH
# is: the scorecard groups by code, and a reader must be able to tell at a
# glance that the failure is in an advisory sentence rather than in an estimate.
# Values INSIDE a note both paths agree fires stay DEFECT/DISPLAY_ARTIFACT —
# those are numbers disagreeing, which is what those codes already mean.
# DIAGNOSTIC_MISMATCH is reserved for the note's triggered/not-triggered STATE.
SEVERITY = ["COUNT_MISMATCH", "MISSING_QUANTITY", "DECISION_MISMATCH",
            "SCRIPT_DIVERGENCE", "DEFECT", "DIAGNOSTIC_MISMATCH",
            "DISPLAY_ARTIFACT"]

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
    # gc_summary's own targets, same self-naming convention as km_summary's.
    # Both are credited by the EXACT tier only (figura-exact.json vs
    # python.json), never by the display-tier text parse.
    "test_p": ("test_p",),
    "test_statistic": ("test_statistic",),
    # table1's own target, and the one target in this map that is NOT credited
    # by a numeric comparison: `decisions` is discharged by the per-variable
    # mean-vs-median-vs-count comparison (see compare_table1), because for
    # Table 1 the CHOICE of summary statistic is itself a validated output.
    "decisions": ("decisions",),
    # ---- the advisory diagnostics (task A14).
    #
    # Two classes, and the split is not cosmetic. `c_statistic` and `zph` are
    # credited by the EXACT tier, because the exported .R really computes those
    # two (the C-statistic as a printed expression, cox.zph as a printed call),
    # so a full-precision Path A value exists for them.
    #
    # The `*_note` targets are credited by the DISPLAY tier instead — the
    # note's triggered/not-triggered state, checked against the sentence Figura
    # printed. The exported script computes no VIF, no Cook's distance, no EPV
    # and no separation check, so those diagnostics have NO exact-tier Path A
    # value and none is invented (harness/run-script.R says the same thing at
    # the harvest end). Naming them `*_note` keeps the distinction visible in
    # the case file: a case declaring `vif_note` is claiming its VIF SENTENCE is
    # under comparison, not its VIF number against a Path A number that does
    # not exist.
    "c_statistic": ("c_statistic",),
    "zph": ("zph_global_p",),
    "vif_note": ("VIF note",),
    "epv_note": ("EPV note",),
    "cooks_note": ("Cook's distance note",),
    "separation_note": ("separation note",),
    "ph_note": ("proportional-hazards note",),
}


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------

# WHAT THE TWO VALUE COLUMNS HOLD. A finding carries `figura` and `python`, and
# the names are not enough: "figura" is TWO different artifacts depending on the
# tier, and on the script tier the `python` column is not Path B at all.
#
#   display tier   figura = the DISPLAYED table/sentence (the screen)
#                  python = Path B
#   exact tier     figura = the harvest from RE-RUNNING THE EXPORTED SCRIPT
#                  python = Path B
#   script tier    figura = the screen
#                  python = the exported script's harvest, rendered
#
# That distinction is load-bearing evidence, not bookkeeping: the shipped
# logistic-dirty case fails its exact tier while its display tier PASSES,
# meaning the numbers on screen were right and the exported .R was wrong. A
# scorecard that labels those rows "Figura" alone reads as an indictment of the
# displayed numbers, which is the opposite of what was measured. Every finding
# therefore names its comparison, and build_scorecard.py prints it in its own
# column.
SRC_DISPLAY = "screen vs Python"
SRC_EXACT = "exported script vs Python"
SRC_SCRIPT = "screen vs exported script"
# One-sided findings: something is wrong with a single artifact, so there is no
# comparison to name — only the artifact the value came from.
SRC_SCREEN = "screen (displayed artifact)"
SRC_HARVEST = "exported script (harvest)"
SRC_PATH_B = "Python (Path B output)"
SRC_COVERAGE = "coverage contract"
# A finding that reached publication without a source is a comparator bug, and
# it says so on the scorecard rather than silently borrowing a neighbour's
# attribution.
SRC_UNCLASSIFIED = "UNCLASSIFIED (comparator bug)"

SOURCES = (SRC_DISPLAY, SRC_EXACT, SRC_SCRIPT, SRC_SCREEN, SRC_HARVEST,
           SRC_PATH_B, SRC_COVERAGE, SRC_UNCLASSIFIED)


def finding(code, term, quantity, figura, python, note, source=None):
    if code not in DISPOSITIONS:
        raise SystemExit(f"comparator bug: unknown finding code {code!r}")
    if source is not None and source not in SOURCES:
        raise SystemExit(f"comparator bug: unknown finding source {source!r}")
    return {"code": code, "disposition": DISPOSITIONS[code], "term": term,
            "quantity": quantity, "figura": figura, "python": python,
            "note": note, "source": source}


def _source(findings, source):
    """Stamp a slice of freshly-appended findings with their comparison source.

    FIRST TAG WINS: a finding that already named its own source (the mixed
    loops, where two tiers append inside one pass) keeps it, so a coarse
    block-level marker can never overwrite a precise per-finding one.
    """
    for f in findings:
        if f.get("source") is None:
            f["source"] = source
    return findings


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
    """Credits exact_targets as comparisons are actually performed.

    `deferred` names targets whose comparison BLOCK has not landed yet (see
    PENDING_PATH_B_DIAGNOSTICS). They are removed from the contract this run
    enforces and published separately, so a not-yet-implemented comparison
    reads as "not checked yet" rather than as either a pass or a failure. The
    accounting below is untouched by the mechanism: everything still declared
    must still be credited.
    """

    def __init__(self, declared, deferred=()):
        deferred = set(deferred)
        self.deferred = [t for t in declared if t in deferred]
        self.declared = [t for t in declared if t not in deferred]
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
        #
        # `self.deferred` is checked too: a case whose whole contract happens to
        # be deferred DID declare one, so calling it contract-less would be
        # false. It still fails `met` below, which is the honest reading —
        # nothing was checked — and `deferred_targets` says why.
        if not self.declared and not self.deferred:
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


# ---------------------------------------------------------------------------
# the ADVISORY DIAGNOSTICS (task A14)
#
# Figura appends advisory sentences to the methods text of both ratio_table
# figures. Not one of them gates a fit or changes an estimate, and every one of
# them is displayed to the user and pasted into a manuscript, so each is
# validated on two claims:
#
#   the NOTE'S STATE   does the sentence fire on both paths?  -> DIAGNOSTIC_MISMATCH
#   the NOTE'S VALUE   when both agree it fires, does Path B's number pushed
#                      through Figura's own sprintf produce the identical
#                      string?                                -> DEFECT / DISPLAY_ARTIFACT
#
# plus, for the two diagnostics the exported .R actually computes, an exact tier
# (rel 1e-6) and a script tier, exactly like the estimates.
#
# WHICH DIAGNOSTICS HAVE AN EXACT-TIER PATH A VALUE, and why the others do not.
# The exported logistic script prints the C-statistic (its own expression, on
# its own `prob`/`n1`/`n0`); the exported cox script prints `cox.zph(fit)`. Both
# are harvested. The exported scripts compute NO VIF, NO Cook's distance, NO EPV
# and NO separation check — nothing in them touches lm(), cooks.distance(), or
# the fitted probabilities. Those diagnostics therefore have no Path A number at
# all, and this comparator does not conjure one from the harvest's `fit`: they
# are judged on the DISPLAY tier, against the sentence Figura really printed,
# which is honest evidence about the artifact the user was handed. See
# harness/run-script.R's harvesters and spec/*.md's "Which tier judges which
# diagnostic".
#
# The sentence formats below are restatements of R/logistic.R's and R/cox.R's
# own sprintf calls, written out here for the same reason format_ratio_cell is —
# the judge shares no code with either path it judges.
# ---------------------------------------------------------------------------

# Path B's `diagnostics` block is written by the CLEAN-ROOM half of task A14.
# Until it lands, python.json carries no `diagnostics` key at all, and this set
# names the figures whose diagnostics comparison is therefore NOT YET PERFORMED.
#
# It is a published deferral, not a silent skip, and it is narrow in three ways
# that matter:
#   * it is per FIGURE and by NAME, so it can never quietly widen;
#   * it only fires when Path B's `diagnostics` key is ABSENT ENTIRELY. The
#     moment Path B emits the block, the gate is inert even before this constant
#     is emptied, and a partial or malformed block goes through the normal
#     MISSING_QUANTITY path like any other hole;
#   * the case's diagnostics exact_targets are reported as DEFERRED rather than
#     as met, so the coverage claim never overstates what ran.
# Delete the entries when validate/logistic.py and validate/cox.py return their
# diagnostics blocks — that is the whole activation step, and the acceptance
# tests in python/tests/ are already red until then.
PENDING_PATH_B_DIAGNOSTICS = {"logistic", "cox"}

# exact_targets discharged ONLY by the diagnostics block, per figure. Used to
# mark them deferred while the block is; nothing else keys off it.
DIAGNOSTIC_TARGETS = {
    "logistic": ("c_statistic", "vif_note", "epv_note", "cooks_note",
                 "separation_note"),
    "cox": ("zph", "ph_note", "epv_note", "separation_note"),
}

# R/logistic.R: sprintf(" Overall model discrimination: apparent (in-sample)
# C-statistic = %.2f.", auc) — printed whenever the C-statistic is finite.
C_STAT_RE = re.compile(
    r"Overall model discrimination: apparent \(in-sample\) "
    r"C-statistic = (-?\d+\.\d{2})\.")
# R/logistic.R: sprintf(" CAUTION: about %.1f events per model term (EPV < 10);
# ...") — the ONE advisory sentence that carries its own number at 1 dp.
EPV_LOGISTIC_RE = re.compile(
    r"CAUTION: about (\d+\.\d) events per model term \(EPV < 10\)")
# R/cox.R's EPV sentence carries NO number at all — a fixed string. The two
# figures' EPV notes are deliberately not one rule.
EPV_COX_TEXT = ("CAUTION: fewer than 10 events per model term (EPV < 10); "
                "the adjusted estimates may be unstable.")
# R/logistic.R: "largest VIF = %s", where %s is sprintf("%.1f", max(vif)) or the
# literal words when any VIF is non-finite.
VIF_RE = re.compile(
    r"CAUTION: multicollinearity among continuous covariates "
    r"\(largest VIF = (effectively infinite|-?\d+\.\d), "
    r"above the usual threshold of 5\)")
VIF_INFINITE = "effectively infinite"
# R/logistic.R: sprintf(" %d observation(s) were flagged as influential "
# "(Cook's distance > 4/n); ...")
COOKS_RE = re.compile(
    r"(\d+) observation\(s\) were flagged as influential "
    r"\(Cook's distance > 4/n\)")
# Both figures open the separation caution with the same clause; R/logistic.R
# and R/cox.R diverge only in the remedies they go on to suggest, so the opening
# is what is matched.
SEPARATION_TEXT = "CAUTION: separation or severe collinearity was detected"
# R/cox.R: sprintf(" The proportional-hazards assumption was assessed with
# scaled Schoenfeld residuals (global %s).", <the ratio-table p rule>)
ZPH_RE = re.compile(
    r"scaled Schoenfeld residuals \(global (p<0\.001|p=\d+\.\d{3})\)")
ZPH_VIOLATION_TEXT = ("CAUTION: the assumption may not hold (global p<0.05)")
# R/logistic.R's .logistic_other_warn fallback embeds R's OWN verbatim warning
# text. That is one implementation's warning catalogue, not a statistical
# quantity, so no independent implementation can be asked to reproduce it and it
# is outside the contract. Detected and reported (mirroring GC_OR_CLAUSE), never
# ignored: a case that provokes it needs the contract extended first.
OTHER_WARN_CLAUSE = "CAUTION: fitting reported a numerical warning"

# The C-statistic is displayed at 2 dp, like the ratio cells, so it shares
# DISPLAY_HALF_ULP. The logistic EPV note is at 1 dp and the VIF note at 1 dp;
# both get km's constant, which is the same 1-dp half step under a name that
# says what it is here.
DIAG_1DP_HALF_ULP = KM_DISPLAY_HALF_ULP


def methods_text(text: str) -> str:
    """The methods paragraph of a ratio_table `text` field.

    fig_logistic/fig_cox emit `"<TSV>\\n\\n<methods sentence>"`. The diagnostics
    live only in the sentence, and a TSV cell could in principle contain a
    substring one of the patterns above would match, so the paragraph is split
    off rather than searched whole.
    """
    if not isinstance(text, str):
        return ""
    parts = text.split("\n\n", 1)
    return parts[1] if len(parts) == 2 else parts[0]


def _note(findings, targets, term, quantity, target_quantity,
          shown_fires: bool, py_fires, shown_raw, note_subject: str):
    """Compare one advisory note's TRIGGERED STATE, screen vs Path B.

    Tri-state return, so the caller's `compared` counter never credits a
    comparison that did not happen (the rule the whole file follows):

        None   Path B published no usable claim -> MISSING_QUANTITY, no
               comparison performed, nothing credited.
        False  compared; the two paths disagree, or agree the note is silent.
        True   compared; both agree it fires, so the caller may go on to judge
               the value inside it.

    `target_quantity` may be None for a note whose exact_targets credit belongs
    to another tier — the C-statistic's does, since it has a real exact tier and
    `c_statistic` follows `adjusted_or`'s convention of being credited there.
    """
    if not isinstance(py_fires, bool):
        findings.append(finding(
            "MISSING_QUANTITY", term, quantity,
            shown_raw if shown_fires else "(no sentence)", py_fires,
            f"Path B reports no boolean for whether the {note_subject} fires"))
        return None
    if target_quantity is not None:
        targets.credit(target_quantity)
    if shown_fires != py_fires:
        fired, silent = (("Figura", "Python") if shown_fires
                         else ("Python", "Figura"))
        findings.append(finding(
            "DIAGNOSTIC_MISMATCH", term, quantity,
            shown_raw if shown_fires else "(no sentence)", py_fires,
            f"{fired} raises the {note_subject} and {silent} does not; the two "
            "paths disagree about whether the advisory applies"))
        return False
    return shown_fires


def _diag_value(findings, term, quantity, shown_value, py_value, rendered,
                shown_raw, half_ulp):
    """Compare the number inside a note both paths agree fires.

    Same three-way disposition as classify_cell: identical string is a pass,
    within half a display step is a DISPLAY_ARTIFACT, anything else a DEFECT.
    Deliberately NOT DIAGNOSTIC_MISMATCH — the note fired on both sides, so what
    disagrees here is a number, which is what DEFECT already means.
    """
    if py_value is None:
        findings.append(finding(
            "MISSING_QUANTITY", term, quantity, shown_raw, None,
            "Path B raises this advisory but reports no value behind it"))
        return
    if rendered == shown_raw:
        return
    if shown_value is None:
        findings.append(finding(
            "DEFECT", term, quantity, shown_raw, rendered,
            "the displayed sentence does not match the display rule and its "
            "value could not be read back"))
        return
    slack = max(ABS_TOL, REL_TOL * max(abs(py_value), abs(shown_value)))
    if abs(py_value - shown_value) <= half_ulp + slack:
        findings.append(finding(
            "DISPLAY_ARTIFACT", term, quantity, shown_raw, rendered,
            "values agree to within half a display step; the rendered strings "
            "differ"))
        return
    findings.append(finding(
        "DEFECT", term, quantity, shown_raw, rendered,
        "displayed values disagree by more than a rounding boundary"))


def format_vif_largest(vif) -> str:
    """R/logistic.R: `if (any(!is.finite(vif))) "effectively infinite" else
    sprintf("%.1f", max(vif))`.

    Keyed off the PRESENCE of a non-finite VIF, not off the absence of finite
    ones: with a third independent covariate a finite VIF near 1.0 also exists,
    and reporting that would read "largest VIF = 1.0, above the usual threshold
    of 5".
    """
    values = [float(v) for v in vif.values()]
    if any(not math.isfinite(v) for v in values):
        return VIF_INFINITE
    return f"{max(values):.1f}"


def _compare_logistic_diagnostics(text, exact, python, targets):
    """(findings, comparisons performed) for fig_logistic's advisory block."""
    findings = []
    compared = 0
    py = python.get("diagnostics")
    if not isinstance(py, dict):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "diagnostics", None, py,
            "Path B produced no `diagnostics` block; none of the advisory "
            "diagnostics could be compared", source=SRC_PATH_B))
        return findings, compared

    mark = len(findings)
    if OTHER_WARN_CLAUSE in text:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "numerical-warning note", OTHER_WARN_CLAUSE,
            None,
            "the displayed text carries the numerical-warning fallback, which "
            "embeds R's own verbatim warning string; fit_logistic's contract "
            "does not report it, so the contract must be extended before this "
            "case can be judged"))

    # -- C-statistic. Note state, then the 2-dp value inside it. R prints the
    # sentence only when the statistic `is.finite`, so a non-finite Path B value
    # is the claim "no sentence", not a sentence carrying a nan.
    m = C_STAT_RE.search(text)
    shown_c = float(m.group(1)) if m else None
    py_c = py.get("c_statistic")
    py_c_fires = py_c is not None and math.isfinite(float(py_c))
    state = _note(findings, targets, "-", "C-statistic note", None,
                  m is not None, py_c_fires,
                  m.group(0) if m else None, "C-statistic sentence")
    compared += state is not None
    if state:
        compared += 1
        _diag_value(findings, "-", "C-statistic note", shown_c, float(py_c),
                    f"Overall model discrimination: apparent (in-sample) "
                    f"C-statistic = {float(py_c):.2f}.",
                    m.group(0), DISPLAY_HALF_ULP)

    # -- VIF. `None` (fewer than two continuous covariates) and `{}` are
    # different claims on the Path B side; only the trigger reaches the screen.
    m = VIF_RE.search(text)
    py_vif = py.get("vif")
    py_vif_fires = py.get("vif_triggered")
    state = _note(findings, targets, "-", "VIF note", "VIF note", m is not None,
                  py_vif_fires, m.group(0) if m else None, "VIF caution")
    compared += state is not None
    if state:
        if not isinstance(py_vif, dict) or not py_vif:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "VIF note", m.group(0), py_vif,
                "Path B raises the VIF caution but reports no per-covariate "
                "VIF map behind it"))
        else:
            compared += 1
            rendered = format_vif_largest(py_vif)
            shown = m.group(1)
            if rendered != shown:
                # The infinite branch is a WORD, not a number, so there is no
                # half-display-step story available in either direction.
                if VIF_INFINITE in (rendered, shown):
                    findings.append(finding(
                        "DEFECT", "-", "VIF note", shown, rendered,
                        "one path reports an effectively infinite VIF and the "
                        "other a finite one"))
                else:
                    _diag_value(findings, "-", "VIF note", float(shown),
                                max(float(v) for v in py_vif.values()),
                                rendered, shown, DIAG_1DP_HALF_ULP)

    # -- EPV.
    m = EPV_LOGISTIC_RE.search(text)
    py_epv = py.get("epv")
    state = _note(findings, targets, "-", "EPV note", "EPV note", m is not None,
                  py.get("epv_triggered"), m.group(0) if m else None,
                  "EPV caution")
    compared += state is not None
    if state:
        compared += 1
        _diag_value(findings, "-", "EPV note",
                    float(m.group(1)),
                    None if py_epv is None else float(py_epv),
                    None if py_epv is None
                    else f"about {float(py_epv):.1f} events per model term",
                    f"about {m.group(1)} events per model term",
                    DIAG_1DP_HALF_ULP)

    # -- Cook's distance. The value inside the sentence is an INTEGER count, so
    # there is no rounding tier: it agrees or it does not.
    m = COOKS_RE.search(text)
    py_cooks = py.get("cooks_influential")
    state = _note(findings, targets, "-", "Cook's distance note",
                  "Cook's distance note", m is not None,
                  py.get("cooks_triggered"), m.group(0) if m else None,
                  "Cook's-distance caution")
    compared += state is not None
    if state:
        if py_cooks is None:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "Cook's distance note", m.group(0),
                None, "Path B raises the Cook's-distance caution but reports "
                "no influential-observation count"))
        else:
            compared += 1
            if int(py_cooks) != int(m.group(1)):
                findings.append(finding(
                    "DEFECT", "-", "Cook's distance note", int(m.group(1)),
                    int(py_cooks),
                    "the two paths flagged different numbers of influential "
                    "observations"))

    # -- separation. A fixed sentence: state is the whole claim.
    compared += _note(
        findings, targets, "-", "separation note", "separation note",
        SEPARATION_TEXT in text, py.get("separation_caution"),
        SEPARATION_TEXT if SEPARATION_TEXT in text else None,
        "separation/collinearity caution") is not None
    _source(findings[mark:], SRC_DISPLAY)

    # -- exact tier: the one diagnostic the exported script computes.
    mark = len(findings)
    a = (exact.get("diagnostics") or {}).get("c_statistic")
    if a is None or py_c is None:
        missing = "Path A" if a is None else "Path B"
        findings.append(finding(
            "MISSING_QUANTITY", "-", "c_statistic", a, py_c,
            f"{missing} did not report a C-statistic at full precision"))
    else:
        compared += 1
        targets.credit("c_statistic")
        if not close_enough(float(a), float(py_c)):
            findings.append(finding(
                "DEFECT", "-", "c_statistic", a, py_c,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))
    _source(findings[mark:], SRC_EXACT)

    # -- script tier: does the exported .R's C-statistic re-render the sentence
    # the screen showed? Never touches Path B.
    mark = len(findings)
    shown = C_STAT_RE.search(text)
    if a is not None and shown is not None:
        compared += 1
        if f"{float(a):.2f}" != shown.group(1):
            findings.append(finding(
                "SCRIPT_DIVERGENCE", "-", "exported script C-statistic",
                shown.group(0), f"C-statistic = {float(a):.2f}.",
                "the exported .R's C-statistic does not reproduce the value "
                "the screen showed"))
    _source(findings[mark:], SRC_SCRIPT)
    return findings, compared


def _compare_cox_diagnostics(text, exact, python, targets):
    """(findings, comparisons performed) for fig_cox's advisory block."""
    findings = []
    compared = 0
    py = python.get("diagnostics")
    if not isinstance(py, dict):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "diagnostics", None, py,
            "Path B produced no `diagnostics` block; none of the advisory "
            "diagnostics could be compared", source=SRC_PATH_B))
        return findings, compared

    mark = len(findings)
    # -- the proportional-hazards sentence: state, then the p-phrase. Mirrors
    # addendum 6 — a differing p-part is never a display artifact — so the
    # rendered phrase is compared as a STRING with no rounding leniency.
    m = ZPH_RE.search(text)
    py_global = py.get("zph_global_p")
    state = _note(findings, targets, "-", "proportional-hazards note",
                  "proportional-hazards note", m is not None,
                  py_global is not None, m.group(0) if m else None,
                  "proportional-hazards sentence")
    compared += state is not None
    if state:
        compared += 1
        rendered = format_p(float(py_global))
        if rendered != m.group(1):
            findings.append(finding(
                "DEFECT", "-", "proportional-hazards note", m.group(1),
                rendered,
                "the global p-value part differs; a p disagreement is never a "
                "display artifact"))

    # -- the violation CAUTION rides inside the same sentence and is its own
    # claim: "the assumption may not hold" is what a reader acts on.
    compared += _note(
        findings, targets, "-", "PH violation caution",
        "proportional-hazards note", ZPH_VIOLATION_TEXT in text,
        py.get("ph_violation"),
        ZPH_VIOLATION_TEXT if ZPH_VIOLATION_TEXT in text else None,
        "proportional-hazards violation caution") is not None

    # -- EPV. cox's sentence carries no number, so state is the whole claim.
    compared += _note(
        findings, targets, "-", "EPV note", "EPV note",
        EPV_COX_TEXT in text, py.get("epv_triggered"),
        EPV_COX_TEXT if EPV_COX_TEXT in text else None,
        "EPV caution") is not None

    # -- separation.
    compared += _note(
        findings, targets, "-", "separation note", "separation note",
        SEPARATION_TEXT in text, py.get("separation_caution"),
        SEPARATION_TEXT if SEPARATION_TEXT in text else None,
        "separation/collinearity caution") is not None
    _source(findings[mark:], SRC_DISPLAY)

    # -- exact tier: cox.zph, global and per covariate. The per-covariate
    # p-values never reach the screen, so this is the ONLY tier that judges
    # them, and it is a real one: the exported script prints cox.zph(fit).
    mark = len(findings)
    a_diag = exact.get("diagnostics") or {}
    a_global = a_diag.get("zph_global_p")
    if a_global is None or py_global is None:
        missing = "Path A" if a_global is None else "Path B"
        findings.append(finding(
            "MISSING_QUANTITY", "-", "zph_global_p", a_global, py_global,
            f"{missing} did not report a global proportional-hazards p-value"))
    else:
        compared += 1
        targets.credit("zph_global_p")
        if not close_enough(float(a_global), float(py_global)):
            findings.append(finding(
                "DEFECT", "-", "zph_global_p", a_global, py_global,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))

    a_terms = {_strip_backticks(k): v
               for k, v in (a_diag.get("zph_terms") or {}).items()}
    b_terms = py.get("zph_terms") or {}
    if not a_terms:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "zph_terms", None, None,
            "Path A's harvest carried no per-covariate proportional-hazards "
            "p-values"))
    if not b_terms:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "zph_terms", None, None,
            "Path B produced no per-covariate proportional-hazards p-values"))
    for key in sorted(set(a_terms) | set(b_terms)):
        a, b = a_terms.get(key), b_terms.get(key)
        if a is None or b is None:
            missing = "Path A" if a is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", key, "zph term p", a, b,
                f"{missing} has no proportional-hazards p-value for this "
                "covariate"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        if not close_enough(float(a), float(b)):
            findings.append(finding(
                "DEFECT", key, "zph term p", a, b,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))
    _source(findings[mark:], SRC_EXACT)

    # -- script tier: does the exported .R's global p re-render the sentence the
    # screen showed? Re-searches `text` rather than reusing `m` from the
    # display-tier block ~90 lines above — the logistic twin does the same
    # (its own `shown = C_STAT_RE.search(text)` right before this tier) so
    # neither function's script tier depends on nothing having reassigned a
    # shared variable in between.
    mark = len(findings)
    shown = ZPH_RE.search(text)
    if a_global is not None and shown is not None:
        compared += 1
        rendered = format_p(float(a_global))
        if rendered != shown.group(1):
            findings.append(finding(
                "SCRIPT_DIVERGENCE", "-", "exported script zph p",
                shown.group(1), rendered,
                "the exported .R's proportional-hazards p does not reproduce "
                "the value the screen showed"))
    _source(findings[mark:], SRC_SCRIPT)
    return findings, compared


DIAGNOSTIC_HANDLERS = {"logistic": _compare_logistic_diagnostics,
                       "cox": _compare_cox_diagnostics}


def compare_diagnostics(case, figura, exact, python, targets):
    """Dispatch the advisory-diagnostics block on the case's FIGURE.

    ratio_table serves two figures whose advisory sentences are different
    sentences about different quantities, so the dispatch is on `figure`, not on
    `display.kind`. A ratio_table figure with no registered handler is a hole,
    reported as one — never waved through as "this figure has no diagnostics",
    which is a claim only its own handler can make.
    """
    figure = case.get("figure")
    handler = DIAGNOSTIC_HANDLERS.get(figure)
    if handler is None:
        return [finding(
            "MISSING_QUANTITY", "-", "diagnostics", None, None,
            f"no diagnostics contract is registered for figure {figure!r}, so "
            "its advisory sentences were not compared",
            source=SRC_COVERAGE)], 0
    return handler(methods_text(figura.get("text")), exact, python, targets)


def compare_ratio_table(case, figura, exact, python):
    """The full ratio_table branch: display, exact, and script tiers."""
    findings = []
    compared = 0
    # The advisory-diagnostics block is deferred while Path B has not published
    # its `diagnostics` contract (see PENDING_PATH_B_DIAGNOSTICS). Deciding that
    # HERE, before _Targets is built, is what lets the case's diagnostics
    # exact_targets read as deferred rather than as unmet coverage.
    figure = case.get("figure")
    # "diagnostics" not in python — not an isinstance check — because the
    # documented invariant (see PENDING_PATH_B_DIAGNOSTICS above) is that the
    # key is ABSENT ENTIRELY until Path B lands. `not isinstance(..., dict)`
    # would also fire for null/[]/"oops", which would misread a clean-room
    # module's own internal-failure sentinel (`diagnostics: None`, say) as
    # "not implemented yet" instead of the coverage failure it actually is;
    # a present-but-malformed value must fall through to the ordinary
    # MISSING_QUANTITY path in the handlers below, not the deferral gate.
    diagnostics_deferred = (
        figure in PENDING_PATH_B_DIAGNOSTICS
        and "diagnostics" not in python)
    # `or []` so an explicit null reads as "no contract" and hits the vacuity
    # guard, rather than raising inside _Targets.
    targets = _Targets(
        case.get("exact_targets") or [],
        DIAGNOSTIC_TARGETS.get(figure, ()) if diagnostics_deferred else ())
    covariates = list(case["roles"]["covariates"])

    # -- counts. The highest-severity class: if the two paths disagree about
    # which rows were analysed, nothing downstream is interpretable. The counts
    # come from the EXPORTED SCRIPT's harvest, not from the screen — hence
    # SRC_EXACT (see the SRC_* comment above; this is exactly the attribution
    # logistic-dirty depends on).
    mark = len(findings)
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
    _source(findings[mark:], SRC_EXACT)

    # -- display tier, BOTH columns.
    mark = len(findings)
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
    _source(findings[mark:], SRC_SCREEN)
    mark = len(findings)
    if not exact.get("terms"):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "exact terms", None, None,
            "the exported script's harvest carried no terms to compare"))
    _source(findings[mark:], SRC_HARVEST)

    mark = len(findings)
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
    _source(findings[mark:], SRC_DISPLAY)

    mark = len(findings)
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
    _source(findings[mark:], SRC_EXACT)

    mark = len(findings)
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
    _source(findings[mark:], SRC_SCRIPT)

    # -- the advisory diagnostics. Runs LAST so its findings sort below the
    # estimate tiers within a case even before SEVERITY reorders them, and so a
    # reader scanning the console output meets the published numbers first.
    if not diagnostics_deferred:
        diag_findings, diag_compared = compare_diagnostics(
            case, figura, exact, python, targets)
        findings.extend(diag_findings)
        compared += diag_compared

    findings.extend(_source(targets.findings(), SRC_COVERAGE))
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

    # -- counts. Same shape/severity as compare_ratio_table's own count loop,
    # and the same source: the counts are the exported script's, not the
    # screen's.
    mark = len(findings)
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
    _source(findings[mark:], SRC_EXACT)

    # -- display tier. Path B's own numbers, pushed through Figura's real
    # display rule (format_p_km/format_median_km), string-compared against
    # what the screen actually showed. Independent of the exact tier above —
    # run over the SAME group union so a Path B absence is flagged here too,
    # exactly as compare_ratio_table's display loop independently flags it
    # alongside its own exact-tier MISSING_QUANTITY.
    mark = len(findings)
    text = figura.get("text")
    if not isinstance(text, str):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed text", text, None,
            "Path A's displayed artifact has no `text` field to parse",
            source=SRC_SCREEN))
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
    _source(findings[mark:], SRC_DISPLAY)

    mark = len(findings)
    # -- script tier. Path A against itself: does exact.json's full-precision
    # median/log-rank, rendered through fig_km's own display rule, reproduce
    # the text the screen actually showed? Mirrors compare_ratio_table's own
    # script tier (SCRIPT_DIVERGENCE) — never touches Path B, so a finding
    # here means the user cannot reproduce the screen from the exported
    # script, independent of whether Python agrees with either side.
    for group in sorted(exact_medians):
        shown = parse_km_group_median(text, group)
        if shown is None:
            continue  # already recorded as MISSING_QUANTITY by the display tier above
        a = exact_medians[group]
        rendered = "not reached" if a is None else format_median_km(a)
        shown_str = "not reached" if shown.get("not_reached") else f"{shown['value']:.1f}"
        compared += 1
        if rendered != shown_str:
            findings.append(finding(
                "SCRIPT_DIVERGENCE", group, "exported script median",
                shown["raw"], rendered, "the exported script's median does "
                "not reproduce the screen's displayed value"))

    if shown_logrank is not None and lr_a is not None:
        compared += 1
        rendered = format_p_km(lr_a)
        if rendered != shown_logrank:
            findings.append(finding(
                "SCRIPT_DIVERGENCE", "-", "exported script logrank",
                shown_logrank, rendered, "the exported script's log-rank p "
                "does not reproduce the screen's displayed value"))
    _source(findings[mark:], SRC_SCRIPT)

    findings.extend(_source(targets.findings(), SRC_COVERAGE))
    return findings, compared, targets


# ---------------------------------------------------------------------------
# gc_summary: group comparison's free-text methods sentence, checked against
# R/groupcompare.R reality.
#
# fig_groupcompare emits one of two sentence shapes, verified by generating all
# three real gc cases end to end:
#
#   numeric branch
#     "<outcome> across groups: <per-group summaries>. <test name><reason>:
#      <p>, <effect>.<post-hoc><notes>"
#     e.g. "biomarker_normal across groups: High dose 58.4 ± 7.71; ... .
#           one-way ANOVA (Welch) (approximately normal (Shapiro–Wilk
#           p = 0.876)): p < 0.001, eta-squared = 0.321 (95% CI 0.197 to
#           0.421). Tukey HSD, significant pairs: Low dose-High dose, ... ."
#
#   categorical branch (no per-group summaries, NO routing reason, NO post-hoc)
#     "<outcome> by group (n = <n>): <test name>: <p>, <effect>.<notes>"
#     e.g. "responder by group (n = 150): Pearson chi-square test: p < 0.001,
#           Cramér's V = 0.421."
#
# The per-group summaries (mean ± SD / median (IQR)) are deliberately NOT part
# of this contract: they are a Table-1-style rendering of the same quantities
# Task 11's `table1` kind owns, and `compare_groups`'s pinned return shape
# (INTERFACES.md) carries no per-group location/spread. That is a stated scope
# boundary, not a skipped comparison — nothing in this branch silently drops a
# quantity the contract does declare.
# ---------------------------------------------------------------------------

# R (R/groupcompare.R, both branches):
#   `pfmt <- if (pv < 0.001) "p < 0.001" else sprintf("p = %.3f", pv)`
# The rendered strings coincide with km's `format_p_km`, but this is restated
# from groupcompare's own source rather than aliased to it: the two figures
# format independently, and sharing one function here would let a change in one
# silently retune the comparator for the other.
def format_p_gc(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _r_nearbyint(value: float) -> float:
    """C's `nearbyint` under the default rounding mode: round half to EVEN.
    Python's ONE-argument `round` on a float is exactly that."""
    return float(round(value))


def _signif(value: float, digits: int = GC_SIGNIF_DIGITS) -> float:
    """R's `signif(v, 3)` — restated as R actually COMPUTES it.

    R's `signif` is not "round the exact decimal value of the double". It is
    src/nmath/fprec.c: `nearbyint(x * 10^e) / 10^e` with
    `e = digits - 1 - floor(log10(|x|))` — and that scaling multiply carries its
    own floating-point error. The two rules disagree whenever `x * 10^e` lands
    on the far side of a .5 boundary from x's exact decimal expansion.

    THE MECHANISM, measured, and the reason this function has this shape. The
    double nearest 2.225 is 2.22500000000000008882..., which is strictly ABOVE
    the decimal tie, so a decimal-exact rounding (Python's TWO-argument
    `round(2.225, 2)`) rounds up and gives 2.23. But the scaling multiply SNAPS
    that value onto the tie: `2.225 * 100` is exactly 222.5 (verified —
    `Decimal(2.225 * 100) == Decimal("222.5")`), and `nearbyint` resolves an
    exact tie half to EVEN, giving 222 and therefore **2.22**. 2.22 is what
    `fig_summary` printed for crp's Treatment Q1 in the shipped summary-table1
    case. The previous two-argument-`round` restatement reported a
    SCRIPT_DIVERGENCE against a perfectly correct cell; this one does not.

    So the disagreement is not "the multiply drifts below the tie" — it is that
    the multiply LANDS ON the tie, where half-to-even applies, while a
    decimal-exact round never sees a tie at all. Which way that goes depends on
    the parity of the scaled integer, not on the direction of any drift:
    `2.475 * 100` is likewise exactly 247.5, and half-to-even rounds it UP to
    248 (248 is the even neighbour), so 2.475 gives 2.48 under both rules —
    agreement by coincidence, not by construction. 1.315 is the discriminating
    probe in the OTHER direction: its double is 1.31499999999999994670...,
    just BELOW the tie, so `round(1.315, 2)` gives 1.31 — while `1.315 * 100`
    is again exactly 131.5 and half-to-even gives 132, so R's signif answers
    **1.32**. Both probes are pinned in the tests.

    R's fprec additionally splits the scaling into two powers near the
    representable extremes; that guard is replaced here by returning `x`
    unrounded when the scaling would overflow, which no quantity this
    comparator formats can reach.
    """
    x = float(value)
    if x == 0.0 or not math.isfinite(x):
        return x
    sign = -1.0 if x < 0 else 1.0
    x = abs(x)
    e10 = (digits - 1) - int(math.floor(math.log10(x)))
    if e10 > 0:
        p10 = 10.0 ** e10
        if not math.isfinite(p10) or not math.isfinite(x * p10):
            return sign * x
        return sign * (_r_nearbyint(x * p10) / p10)
    p10 = 10.0 ** (-e10)
    return sign * (_r_nearbyint(x / p10) * p10)


def format_num_gc(value: float) -> str:
    """R/summarize.R `.fmt_num`: 3 significant figures, plain notation, no
    trailing zeros. 250000 -> "250000", 1.125 -> "1.12", 0.00123 -> "0.00123",
    7.70 -> "7.7".

    Note the 1.125 case: `.fmt_num`'s own source comment in R/summarize.R claims
    "1.13", but R prints "1.12" — `signif` inherits IEEE round-half-to-even on an
    exactly-representable tie. The comment is wrong; this restates what ships,
    measured. See test_format_num_gc_is_three_significant_figures_not_decimal_
    places for the probe set.
    """
    x = _signif(float(value))
    if x == 0.0:
        return "0"
    if not math.isfinite(x):
        return str(x)
    exponent = math.floor(math.log10(abs(x)))
    decimals = max(0, (GC_SIGNIF_DIGITS - 1) - exponent)
    text = f"{x:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def gc_display_half_ulp(value: float) -> float:
    """Half of one step at 3 significant figures, for `value`'s magnitude.

    The ratio-table and km rules above are fixed decimal places, so their half
    step is a constant. `.fmt_num` rounds to significant figures instead, so
    the step is 10^(exponent - 2) and the half step scales with the number.
    """
    value = abs(float(value))
    if value == 0.0 or not math.isfinite(value):
        return 0.0
    return 0.5 * 10.0 ** (math.floor(math.log10(value)) - (GC_SIGNIF_DIGITS - 1))


def format_effect_gc(effect: dict) -> str:
    """R/groupcompare.R `.gc_ci_phrase`:
    `sprintf("%s = %s (95%% CI %s to %s)", name, v, lo, hi)`, or just
    `"<name> = <v>"` for the two effect sizes the app reports without an
    interval (epsilon-squared and Cramér's V)."""
    label = effect["label"]
    value = format_num_gc(effect["value"])
    lo, hi = effect.get("lo"), effect.get("hi")
    if lo is None or hi is None:
        return f"{label} = {value}"
    return (f"{label} = {value} (95% CI {format_num_gc(lo)} "
            f"to {format_num_gc(hi)})")


def effect_values(effect):
    """`{label, value, lo, hi}` normalised, or None when unusable.

    Mirrors `cell_values` above: a Path B effect missing its label/value, or
    carrying a non-numeric one, is a hole in the evidence rather than a crash.
    """
    if not isinstance(effect, dict):
        return None
    try:
        label = effect["label"]
        value = float(effect["value"])
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(label, str):
        return None
    bounds = {}
    for key in ("lo", "hi"):
        raw = effect.get(key)
        if raw is None:
            bounds[key] = None
            continue
        try:
            bounds[key] = float(raw)
        except (TypeError, ValueError):
            return None
    return {"label": label, "value": value, **bounds}


# A trailing " (<second sorted group> vs <first sorted group>)" direction clause
# is appended by EXACTLY TWO of the app's five effect sizes — `.gc_effect_t`
# (Cohen's d) and `.gc_effect_wilcox` (rank-biserial r), R/groupcompare.R:51-52
# and :63-64 — and by none of the other three.
#
# It is therefore a function of the EFFECT, not of the group count. Those two
# effects are reachable only from the numeric branch at k == 2, so on that
# branch "two groups" and "carries a direction clause" coincide; on the
# CATEGORICAL branch they do not. `.gc_categorical` builds its effect phrase at
# R/groupcompare.R:211 as a bare `"Cramér's V = <v>"` and never appends a
# direction clause at any group count — a two-group categorical outcome with
# three or more outcome levels displays no clause at all. Verified against the
# real figure rather than reasoned about: a 2-group x 3-outcome-level table put
# through `render_figure()` printed
#   `resp by group (n = 90): Pearson chi-square test: p = 0.003,
#    Cramér's V = 0.364.`
# with no trailing clause. Gating this on `len(group_levels) == 2` would have
# demanded one there and reported a DEFECT against correct output.
GC_DIRECTION_EFFECT_LABELS = frozenset({"Cohen's d", "rank-biserial r"})


def gc_direction_suffix(effect_label, group_levels) -> str:
    if effect_label not in GC_DIRECTION_EFFECT_LABELS:
        return ""
    levels = sorted(group_levels)
    # Both producers run only at k == 2; anything else is an inconsistent pair
    # of inputs, and inventing a clause from them would be worse than omitting
    # it (the effect-value comparison below still runs either way).
    return f" ({levels[1]} vs {levels[0]})" if len(levels) == 2 else ""


# The 2x2-only odds-ratio clause R appends after Cramér's V. `compare_groups`'s
# pinned return shape carries no odds ratio, so a case that displays one needs
# the contract extended before it can be judged — detected and reported, never
# quietly ignored.
GC_OR_CLAUSE = "; odds ratio for "


def _gc_clause_re(test_name: str):
    """`<test name>[ (<reason>)]: <p>, <effect>.` anchored on a KNOWN test name.

    Built from Path B's own `test_name` rather than from a general grammar of
    the sentence — the same "search for something already known" approach
    `parse_ratio_cell` and `parse_km_group_median` use. The optional reason
    group allows ONE level of nesting because the real reason strings nest:
    " (approximately normal (Shapiro–Wilk p = 0.876))".

    The effect runs to the first "." followed by whitespace or end-of-string;
    every "." inside a rendered number is followed by a digit, so this cannot
    truncate a value. (A group level containing ". " could truncate the
    two-group direction clause; no real level does, and the mismatch would
    surface as a DEFECT rather than as a silent pass.)
    """
    reason = r"(?: \((?:[^()]|\([^()]*\))*\))?"
    return re.compile(
        re.escape(test_name) + reason +
        r": (?P<p>p < 0\.001|p = \d+\.\d{3}), (?P<eff>.+?)\.(?=\s|$)")


def parse_gc_test_clause(text: str, test_name: str):
    """The displayed p-phrase and effect phrase for a known test name, or None
    when that test's clause is not in the text at all."""
    m = _gc_clause_re(test_name).search(text)
    if m is None:
        return None
    return {"p_text": m["p"], "effect": m["eff"]}


GC_POSTHOC_SIG_RE = re.compile(
    r"\s(?P<test>[^:.]+), significant pairs: (?P<pairs>.+?)\.(?=\s|$)")
GC_POSTHOC_NONE_RE = re.compile(
    r"\s(?P<test>[^:.]+): no pairwise differences at 0\.05\.")


def parse_gc_posthoc(text: str):
    """R/groupcompare.R `.gc_posthoc`'s sentence, or None when there is none.

    `.gc_posthoc` returns the empty string — no sentence at all — whenever
    there are fewer than three groups or the omnibus p is >= 0.05, so None here
    means "the app ran no post-hoc", which is itself a claim both paths must
    agree on. `{"significant_pairs": []}` is the DIFFERENT claim "a post-hoc
    ran and nothing survived adjustment".

    The test label is captured rather than matched against a fixed vocabulary,
    so a future third post-hoc method is read back rather than silently
    reported as an absent sentence.
    """
    m = GC_POSTHOC_SIG_RE.search(text)
    if m is not None:
        return {"test": m["test"].strip(),
                "significant_pairs": [p.strip() for p in m["pairs"].split(", ")],
                "raw": m.group(0).strip()}
    m = GC_POSTHOC_NONE_RE.search(text)
    if m is not None:
        return {"test": m["test"].strip(), "significant_pairs": [],
                "raw": m.group(0).strip()}
    return None


GC_EFFECT_RE_TAIL = (
    r" = (?P<value>-?[0-9][0-9.]*)"
    r"(?: \(95% CI (?P<lo>-?[0-9][0-9.]*) to (?P<hi>-?[0-9][0-9.]*)\))?"
    r"(?P<suffix>.*)$")


def parse_gc_effect(shown: str, label: str):
    """Read Figura's displayed effect phrase back into numbers, using Path B's
    own label as the anchor. None when the phrase does not match the display
    rule (which includes the case where the two paths named the effect
    differently — a real disagreement, not a parse shrug)."""
    m = re.match(re.escape(label) + GC_EFFECT_RE_TAIL, shown)
    if m is None:
        return None
    out = {"value": float(m["value"]), "suffix": m["suffix"]}
    out["lo"] = float(m["lo"]) if m["lo"] is not None else None
    out["hi"] = float(m["hi"]) if m["hi"] is not None else None
    return out


def display_agrees_gc(value: float, shown: float) -> bool:
    """gc's own half-display-step rule, at 3 significant figures."""
    value, shown = float(value), float(shown)
    slack = max(ABS_TOL, REL_TOL * max(abs(value), abs(shown)))
    return abs(value - shown) <= gc_display_half_ulp(shown) + slack


def classify_gc_effect_display(shown: str, python_effect,
                               group_levels) -> dict:
    """One displayed effect phrase, Path A vs Path B. Mirrors classify_cell's
    PASS/DISPLAY_ARTIFACT/DEFECT/MISSING_QUANTITY shape."""
    eff = effect_values(python_effect)
    if eff is None:
        return finding(
            "MISSING_QUANTITY", "-", "displayed effect", shown, python_effect,
            "Path B's effect is missing label/value or carries a non-numeric "
            "bound; the displayed effect could not be compared")
    if GC_OR_CLAUSE in shown:
        return finding(
            "MISSING_QUANTITY", "-", "displayed effect", shown,
            format_effect_gc(eff),
            "the displayed effect carries a 2x2 odds-ratio clause, which "
            "compare_groups' return shape does not report; the contract must "
            "be extended before this case can be judged")

    suffix = gc_direction_suffix(eff["label"], group_levels)
    rendered = format_effect_gc(eff) + suffix
    if rendered == shown:
        return finding("PASS", "-", "displayed effect", shown, rendered,
                       "Python's effect through Figura's display rule is the "
                       "identical string")

    parsed = parse_gc_effect(shown, eff["label"])
    if parsed is None:
        return finding(
            "DEFECT", "-", "displayed effect", shown, rendered,
            "Figura's effect phrase does not match the display rule for Path "
            "B's effect label and could not be read back")
    if parsed["suffix"] != suffix:
        return finding(
            "DEFECT", "-", "displayed effect", shown, rendered,
            "the effect phrase's trailing direction clause differs from the "
            "one the group levels imply")

    pairs = [(eff["value"], parsed["value"]),
             (eff["lo"], parsed["lo"]), (eff["hi"], parsed["hi"])]
    for mine, theirs in pairs:
        if (mine is None) != (theirs is None):
            return finding(
                "DEFECT", "-", "displayed effect", shown, rendered,
                "one path reports a confidence interval for this effect and "
                "the other does not")
    same = all(display_agrees_gc(mine, theirs)
               for mine, theirs in pairs if mine is not None)
    if same:
        return finding("DISPLAY_ARTIFACT", "-", "displayed effect", shown,
                       rendered, "values agree to within half a display step; "
                       "the rendered strings differ")
    return finding("DEFECT", "-", "displayed effect", shown, rendered,
                   "displayed effect values disagree by more than a rounding "
                   "boundary")


def _is_fisher(name) -> bool:
    """Fisher's exact test is the one test here with NO test statistic — R's
    htest carries no `statistic` component at all. That is structural, so a
    null statistic on BOTH sides is an agreement rather than a hole."""
    return isinstance(name, str) and "Fisher" in name


def compare_gc_summary(case, figura, exact, python):
    """The full gc_summary branch: counts and per-group counts, test_p and
    test_statistic (exact tier), the displayed test-name/p/effect phrases and
    the post-hoc pair set (display tier), and the exported script's p rendered
    against the screen (script tier)."""
    findings = []
    compared = 0
    targets = _Targets(case.get("exact_targets") or [])

    # -- counts. Same shape/severity as the other branches' count loops. There
    # is no `n_event` in a group comparison: nothing here is an event. Source
    # as elsewhere: the counts are the exported script's harvest, not the
    # screen's.
    mark = len(findings)
    for key in ("n", "n_dropped"):
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

    # -- per-group counts. Symmetric over the key union, so a group present on
    # only one side is a finding in either direction. This is also what
    # establishes the group-level vocabulary the display tier's direction
    # clause is built from, so a disagreement here must surface before it can
    # quietly mis-key anything downstream.
    exact_groups = exact.get("n_per_group") or {}
    python_groups = python.get("n_per_group") or {}
    if not exact_groups:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "n_per_group", None, None,
            "Path A's harvest carried no per-group counts to compare"))
    if not python_groups:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "n_per_group", None, None,
            "Path B produced no per-group counts to compare"))
    for group in sorted(set(exact_groups) | set(python_groups)):
        a, b = exact_groups.get(group), python_groups.get(group)
        if a is None or b is None:
            missing = "Path A" if a is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", group, "n_per_group", a, b,
                f"{missing} has no count for this group"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        if a != b:
            findings.append(finding(
                "COUNT_MISMATCH", group, "n_per_group", a, b,
                "the two paths analysed different rows for this group"))

    # -- exact tier: the omnibus p-value. Path A's harvest names it `test_p`
    # (it is harvested off the htest object); Path B's contract names it
    # `p_value`. The two names are deliberately different and are mapped here
    # once, rather than one side renaming to match the other.
    name = python.get("test_name")
    p_a, p_b = exact.get("test_p"), python.get("p_value")
    if p_a is None or p_b is None:
        missing = "Path A" if p_a is None else "Path B"
        findings.append(finding(
            "MISSING_QUANTITY", "-", "test_p", p_a, p_b,
            f"{missing} did not report the test p-value"))
    else:
        compared += 1
        targets.credit("test_p")
        if not close_enough(float(p_a), float(p_b)):
            findings.append(finding(
                "DEFECT", "-", "test_p", p_a, p_b,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))

    # -- exact tier: the test statistic, with the Fisher rule.
    s_a, s_b = exact.get("test_statistic"), python.get("statistic")
    if s_a is None and s_b is None:
        if _is_fisher(name):
            # Both paths agree there is no statistic, because the test has
            # none. A real agreement, so no finding — and no credit either,
            # since no comparison was performed: a case that nonetheless
            # DECLARES test_statistic as an exact target will (correctly) fail
            # its coverage contract via _Targets rather than pass vacuously.
            pass
        else:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "test_statistic", s_a, s_b,
                "neither path reported a test statistic, and the test is not "
                "Fisher's exact test (the only one that structurally has "
                "none)"))
    elif s_a is None or s_b is None:
        missing = "Path A" if s_a is None else "Path B"
        if _is_fisher(name):
            findings.append(finding(
                "DEFECT", "-", "test_statistic", s_a, s_b,
                "Fisher's exact test has no test statistic, but one path "
                "reported one"))
        else:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "test_statistic", s_a, s_b,
                f"{missing} did not report a test statistic"))
    else:
        compared += 1
        targets.credit("test_statistic")
        if not close_enough(float(s_a), float(s_b)):
            findings.append(finding(
                "DEFECT", "-", "test_statistic", s_a, s_b,
                f"beyond rel {REL_TOL} / abs {ABS_TOL}"))
    _source(findings[mark:], SRC_EXACT)

    # -- display tier.
    mark = len(findings)
    text = figura.get("text")
    if not isinstance(text, str):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed text", text, None,
            "Path A's displayed artifact has no `text` field to parse",
            source=SRC_SCREEN))
        text = ""

    group_levels = sorted(set(exact_groups) | set(python_groups))
    clause = None
    if not isinstance(name, str) or not name:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed test name", text or None, name,
            "Path B reported no test name, so the displayed test clause "
            "cannot be located"))
    else:
        clause = parse_gc_test_clause(text, name)
        compared += 1
        if clause is None:
            findings.append(finding(
                "DEFECT", "-", "displayed test name", text, name,
                "the displayed sentence carries no clause for Path B's test "
                "name; the two paths chose different tests, or the display "
                "rule changed"))

    if clause is None:
        # The clause is the anchor for the displayed p, the displayed effect,
        # and the script tier's p. Losing it means those three comparisons did
        # not happen — each is recorded as a hole rather than left to look like
        # a pass, so a wrong test name can never mask a wrong effect size
        # sitting behind it.
        for quantity in ("displayed p", "displayed effect",
                         "exported script p"):
            findings.append(finding(
                "MISSING_QUANTITY", "-", quantity, None, None,
                "the displayed test clause could not be located, so this "
                "quantity had no displayed value to compare against",
                # The third hole is the SCRIPT tier's, not the display tier's:
                # it is the screen-vs-exported-script check that did not happen.
                source=(SRC_SCRIPT if quantity == "exported script p"
                        else SRC_DISPLAY)))
    else:
        # p, display tier. Mirrors addendum 6 / classify_km_logrank_display: a
        # differing p-part is NEVER a display artifact.
        rendered_p = format_p_gc(float(p_b)) if p_b is not None else None
        if rendered_p is None:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "displayed p", clause["p_text"], None,
                "no Path B p-value to compare against the displayed text"))
            # NOT a silent skip: MISSING_QUANTITY was just recorded, and
            # `compared` is deliberately NOT credited for a comparison that
            # could not be performed.
        else:
            compared += 1
            if rendered_p != clause["p_text"]:
                findings.append(finding(
                    "DEFECT", "-", "displayed p", clause["p_text"], rendered_p,
                    "the p-value part differs; a p disagreement is never a "
                    "display artifact"))

        f = classify_gc_effect_display(clause["effect"], python.get("effect"),
                                       group_levels)
        if f["code"] == "MISSING_QUANTITY":
            # The effect was unusable, so no comparison happened: record the
            # hole and do NOT credit a comparison that was never performed.
            findings.append(f)
        else:
            compared += 1
            if f["code"] not in PASS_CODES:
                findings.append(f)

    # -- display tier: the post-hoc sentence. Presence/absence is itself a
    # claim both paths must agree on, and it is checked before the pair set.
    shown_posthoc = parse_gc_posthoc(text)
    py_posthoc = python.get("posthoc")
    compared += 1
    if (shown_posthoc is None) != (py_posthoc is None):
        present, absent = (("Figura", "Python") if py_posthoc is None
                           else ("Python", "Figura"))
        findings.append(finding(
            "DEFECT", "-", "post-hoc presence",
            shown_posthoc["raw"] if shown_posthoc else None,
            py_posthoc,
            f"{present} reports a post-hoc comparison and {absent} does not; "
            "the two paths disagree about whether one was warranted"))
    elif shown_posthoc is not None:
        compared += 1
        py_test = py_posthoc.get("test") if isinstance(py_posthoc, dict) else None
        if py_test != shown_posthoc["test"]:
            findings.append(finding(
                "DEFECT", "-", "post-hoc test", shown_posthoc["test"], py_test,
                "the two paths ran different post-hoc methods"))
        py_pairs = (py_posthoc.get("significant_pairs")
                    if isinstance(py_posthoc, dict) else None)
        if py_pairs is None:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "post-hoc pairs",
                shown_posthoc["significant_pairs"], None,
                "Path B's post-hoc carries no significant_pairs list"))
        else:
            compared += 1
            shown_set = set(shown_posthoc["significant_pairs"])
            py_set = set(py_pairs)
            if shown_set != py_set:
                findings.append(finding(
                    "DEFECT", "-", "post-hoc pairs",
                    sorted(shown_set), sorted(py_set),
                    "the significant-pair sets differ; only Figura: "
                    f"{sorted(shown_set - py_set)}, only Python: "
                    f"{sorted(py_set - shown_set)}"))
    _source(findings[mark:], SRC_DISPLAY)

    mark = len(findings)
    # -- script tier. Path A against itself: does the exported .R's harvested
    # p-value, rendered through fig_groupcompare's own display rule, reproduce
    # the p the screen showed? Never touches Path B — a finding here means the
    # user cannot reproduce the screen from the script they downloaded.
    if clause is not None:
        if p_a is None:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "exported script p",
                clause["p_text"], None,
                "the exported script's harvest carried no p-value, so the "
                "screen could not be checked against it"))
            # NOT a silent skip: MISSING_QUANTITY was just recorded.
        else:
            compared += 1
            rendered = format_p_gc(float(p_a))
            if rendered != clause["p_text"]:
                findings.append(finding(
                    "SCRIPT_DIVERGENCE", "-", "exported script p",
                    clause["p_text"], rendered,
                    "the exported .R's p-value does not reproduce the p the "
                    "screen showed"))
    _source(findings[mark:], SRC_SCRIPT)

    findings.extend(_source(targets.findings(), SRC_COVERAGE))
    return findings, compared, targets


# ---------------------------------------------------------------------------
# table1: Summary (Table 1), checked against R/summarize.R reality.
#
# Table 1 is the one analysis whose DECISION is itself a published output: for
# every continuous variable the app chooses mean +/- SD or median (IQR) and
# prints that choice in the row's own label. A table whose numbers are each
# individually right but whose choice is wrong is still wrong, so the choice is
# compared as its own quantity, with its own code (DECISION_MISMATCH).
#
# The real displayed `text` (verified by running the shipped summary-table1 case
# end to end, not reasoned about):
#
#   Characteristic\tControl (N=60)\tTreatment (N=60)\tMissing
#   age, mean ± SD\t59.6 ± 11.1\t60.2 ± 11.4\t0
#   length_of_stay, median (IQR)\t3.7 (2.25–6)\t4.1 (2–7.3)\t8
#   crp, median (IQR)\t4.5 (2.48–7.15)\t4.85 (2.22–8.45)\t0
#   sex\t\t\t0
#   Female\t32 (53%)\t28 (47%)\t
#   Male\t28 (47%)\t32 (53%)\t
#   diabetes\t\t\t0
#   No\t32 (53%)\t44 (73%)\t
#   Yes\t28 (47%)\t16 (27%)\t
#
# A categorical variable emits a bare-name header row with EMPTY group cells,
# then bare level rows — the same positional model ratio_table's reference
# header / level rows use, and for the same reason: a level row's label is the
# level alone, so it can only be keyed by the block it sits in.
#
# TIER SHAPE, and how it differs from every other kind here. `summarize`'s
# contract (INTERFACES.md) returns RENDERED CELL STRINGS, not raw numbers,
# because at three significant figures the string IS the published claim. So:
#
#   display tier  every per-variable-per-group cell string, plus the Missing
#                 cell, compared EXACTLY against Path B. There is deliberately
#                 no DISPLAY_ARTIFACT tier for table1 — with no numbers behind
#                 the strings there is no "half a display step" to be within,
#                 and inventing one would weaken the only tier that judges the
#                 published artifact.
#   decision tier the per-variable kind (mean/median/count), Path A vs Path B.
#   exact tier    n, n_dropped, and the per-group Ns. Count-level against Path
#                 B by construction (see above) — which is why summary-table1
#                 declares exact_targets ["n", "n_dropped", "decisions"] and
#                 not a list of estimates it cannot credit.
#   script tier   Path A against itself, and the STRONGEST tier here: the
#                 exported .R leaves unrounded per-variable, per-group
#                 mean/sd or type-7 quartiles (harvest_summary in
#                 harness/run-script.R), so the harvest is pushed through the
#                 app's own display rule and string-compared to the screen —
#                 including the statistic it CHOSE, which the script re-expresses
#                 by computing one or the other.
# ---------------------------------------------------------------------------

TABLE1_HEADER_FIRST_CELL = "Characteristic"
TABLE1_HEADER_LAST_CELL = "Missing"
EM_DASH = "—"

# R: `sprintf("%s, %s", disp(col), if (kind == "mean") "mean ± SD" else
# "median (IQR)")` — R/summarize.R, the continuous row label. U+00B1.
TABLE1_KIND_SUFFIX = {", mean ± SD": "mean", ", median (IQR)": "median"}

# R: `sprintf("%s (N=%d)", levels_g, group_n)`.
TABLE1_GROUP_HEADER_RE = re.compile(r"^(?P<level>.+) \(N=(?P<n>\d+)\)$")

# R/summarize.R's `.fmt_num` is shared BY SOURCE between fig_groupcompare and
# fig_summary: literally the same function, in the same file — not two rules
# that happen to coincide. (Contrast format_p_km / format_p_gc above, restated
# separately precisely because they are two different R functions whose output
# currently agrees.) So table1 aliases the existing restatement instead of
# making a second copy that could drift; a change to `.fmt_num` must move
# exactly one thing in this file.
format_num_t1 = format_num_gc


def format_mean_cell_t1(mean, sd) -> str:
    """R `.fmt_continuous(x, "mean")`: `sprintf("%s ± %s", ...)`, U+00B1.

    `sd is None` is the harvest's signal for a one-value group (R's `sd()` of
    length 1 is NA), which `fig_summary` displays as the bare value.
    """
    if mean is None:
        return EM_DASH
    if sd is None:
        return format_num_t1(mean)
    return f"{format_num_t1(mean)} ± {format_num_t1(sd)}"


def format_median_cell_t1(q1, q2, q3) -> str:
    """R `.fmt_continuous(x, "median")`: `sprintf("%s (%s–%s)", q2, q1, q3)`,
    EN DASH U+2013, quartiles from `quantile(..., type = 7)`.

    KNOWN LIMIT: a group with exactly ONE non-missing value is displayed by the
    app as the bare value, but the exported script's `quantile()` returns three
    equal numbers, which render here as `v (v–v)`. No shipped case has such a
    group; if one appears the resulting SCRIPT_DIVERGENCE is a true statement
    (this harvest cannot reproduce that cell), not a silenced difference.
    """
    if q2 is None:
        return EM_DASH
    return (f"{format_num_t1(q2)} ({format_num_t1(q1)}{EN_DASH}"
            f"{format_num_t1(q3)})")


def format_count_cell_t1(k, denom) -> str:
    """R: `if (denom == 0) "—" else sprintf("%d (%.0f%%)", k, 100 * k / denom)`.

    NOT `.fmt_num`: the percent is whole-number `%.0f`, and it rounds half to
    EVEN (C's printf, and Python's own format spec — verified identical:
    `sprintf("%.0f", 12.5)` is "12" in both, `37.5` is "38" in both).
    """
    if denom in (None, 0):
        return EM_DASH
    return f"{int(k)} ({100 * float(k) / float(denom):.0f}%)"


def parse_table1_tsv(text: str, case: dict):
    """The displayed Table 1 -> (group headers, rows, findings).

    Each row is {key, label, variable, level, kind, cells: {level: str},
    missing: str}. `key` is the variable name for a continuous row or a
    categorical HEADER row, and `"<variable>: <level>"` for a level row — never
    a bare level, which would collide across variables.

    Anchored on the case's DECLARED continuous/categorical roles, the same
    "search for something already known" approach parse_ratio_cell and
    parse_km_group_median use. That also makes a reclassification by the app
    (a variable the case calls continuous displayed as a categorical block, or
    the reverse) visible as a finding instead of being absorbed by a generic
    grammar.
    """
    roles = case.get("roles") or {}
    continuous = list(roles.get("continuous") or [])
    categorical = list(roles.get("categorical") or [])

    findings = []
    rows = []
    headers = []
    group_n = {}

    tsv = text.split("\n\n")[0]
    lines = [ln for ln in tsv.split("\n") if ln.strip() != ""]
    if not lines:
        findings.append(finding("DEFECT", "-", "displayed table", "", None,
                                "the displayed output carries no table"))
        return headers, group_n, rows, findings

    head = [c.strip() for c in lines[0].split("\t")]
    if len(head) < 3 or head[0] != TABLE1_HEADER_FIRST_CELL \
            or head[-1] != TABLE1_HEADER_LAST_CELL:
        findings.append(finding(
            "DEFECT", "-", "table header", lines[0], None,
            f"expected a header starting {TABLE1_HEADER_FIRST_CELL!r} and "
            f"ending {TABLE1_HEADER_LAST_CELL!r}"))
    # `slots` is POSITIONAL — one entry per group column, None where that
    # column's header could not be read. The cells below are keyed through it,
    # never through `headers`: `headers` drops the unreadable ones, so zipping
    # a row's cells against it positionally would shift every column after the
    # first bad header and file one group's numbers under the next group's
    # name. A finding then reports a real disagreement that never happened.
    # Reporting the bad header first is right; mis-keying afterwards is not.
    slots = []
    for cell in head[1:-1]:
        m = TABLE1_GROUP_HEADER_RE.match(cell)
        if m is None:
            slots.append(None)
            findings.append(finding(
                "DEFECT", cell, "group header", cell, None,
                "the column header does not match the app's '<level> (N=<n>)' "
                "rule, so its group level and N cannot be read"))
            continue  # NOT a silent skip: the unreadable header was recorded
        slots.append(m["level"])
        headers.append(m["level"])
        group_n[m["level"]] = int(m["n"])

    n_cols = len(head) - 2  # everything between Characteristic and Missing
    current_var = None
    seen_keys = set()
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) != n_cols + 2:
            findings.append(finding(
                "DEFECT", parts[0].strip(), "displayed row", line, None,
                f"row does not carry {n_cols + 2} tab-separated cells"))
            continue  # NOT a silent skip: the malformed row was just recorded
        label = parts[0].strip()
        cells = {slots[i]: parts[i + 1].strip()
                 for i in range(min(n_cols, len(slots)))
                 if slots[i] is not None}
        missing = parts[-1].strip()

        variable = level = None
        kind = None
        for suffix, k in TABLE1_KIND_SUFFIX.items():
            if label.endswith(suffix) and label[: -len(suffix)] in continuous:
                variable, kind = label[: -len(suffix)], k
                break
        if variable is not None:
            current_var = None  # a continuous row closes any categorical block
        elif label in categorical:
            variable, kind, current_var = label, "count", label
            if any(c != "" for c in cells.values()):
                findings.append(finding(
                    "DEFECT", label, "displayed row", line, None,
                    "a categorical header row carries value cells; it must be "
                    "empty in every group column"))
        elif label in continuous:
            findings.append(finding(
                "DEFECT", label, "displayed row", line, None,
                "a continuous row's label carries no ', mean ± SD' or "
                "', median (IQR)' suffix, so it declares no summary kind"))
            continue  # NOT a silent skip: the kind-less row was just recorded
        else:
            if current_var is None:
                findings.append(finding(
                    "MISSING_QUANTITY", label, "displayed row", line, None,
                    "level row with no preceding categorical header row; it "
                    "cannot be keyed to a variable"))
                continue  # NOT a silent skip: the unkeyable row was recorded
            variable, level, kind = current_var, label, "count"

        key = variable if level is None else f"{variable}: {level}"
        if key in seen_keys:
            findings.append(finding(
                "DEFECT", key, "displayed row", line, None,
                "two displayed rows resolve to the same key"))
        seen_keys.add(key)
        rows.append({"key": key, "label": label, "variable": variable,
                     "level": level, "kind": kind, "cells": cells,
                     "missing": missing})

    for var in continuous + categorical:
        if not any(r["variable"] == var for r in rows):
            findings.append(finding(
                "MISSING_QUANTITY", var, "displayed row", None, None,
                "the case declares this variable but the displayed table has "
                "no row for it"))
    return headers, group_n, rows, findings


def python_table1_rows(python: dict):
    """Path B's rows -> ({key: row}, {variable: kind}, findings).

    The key derivation is a SECOND, independent implementation of the same rule
    parse_table1_tsv applies to the screen — deliberately, exactly as
    display_key / validate.cli.display_label are kept separate. A divergence
    surfaces as MISSING_QUANTITY rather than a quietly-matched wrong row.
    """
    findings = []
    by_key = {}
    kinds = {}
    for row in python.get("rows") or []:
        if not isinstance(row, dict) or "variable" not in row:
            findings.append(finding(
                "MISSING_QUANTITY", "-", "Path B row", None, row,
                "Path B produced a row with no `variable`; it cannot be keyed"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        var, level = row["variable"], row.get("level")
        key = var if level in (None, "") else f"{var}: {level}"
        if key in by_key:
            # SYMMETRIC with parse_table1_tsv's own duplicate-key DEFECT on the
            # displayed side. Without this the second row silently replaced the
            # first and the comparison ran against whichever one Path B happened
            # to emit last — a passing result that proves nothing about the row
            # that was overwritten. The overwrite still happens (last wins, as
            # on the displayed side), but it is now published.
            findings.append(finding(
                "DEFECT", key, "Path B row", None, key,
                "two Path B rows resolve to the same key; the later one "
                "overwrites the earlier, so one of them was never compared"))
        by_key[key] = row
        kind = row.get("kind")
        if var in kinds and kinds[var] != kind:
            findings.append(finding(
                "DECISION_MISMATCH", var, "decision", None,
                f"{kinds[var]} / {kind}",
                "Path B reports two different kinds for the same variable; the "
                "kind is a property of the variable, not of one row"))
        kinds[var] = kind
    return by_key, kinds, findings


def compare_table1(case, figura, exact, python):
    """The full table1 branch: counts, decisions, displayed cells, script."""
    findings = []
    compared = 0
    targets = _Targets(case.get("exact_targets") or [])

    # -- counts. Same shape/severity as every other branch's count loop. There
    # is no `n_event`: Table 1 has no event. Source as elsewhere: `exact` is the
    # exported script's harvest, not the screen.
    mark = len(findings)
    for key in ("n", "n_dropped"):
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
    _source(findings[mark:], SRC_EXACT)

    mark = len(findings)
    text = figura.get("text")
    if not isinstance(text, str):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed table", text, None,
            "Path A's displayed artifact has no `text` field to parse"))
        text = ""
    headers, shown_group_n, rows, parse_findings = parse_table1_tsv(text, case)
    findings.extend(parse_findings)
    _source(findings[mark:], SRC_SCREEN)
    rows_by_key = {r["key"]: r for r in rows}
    mark = len(findings)
    py_by_key, py_kinds, py_findings = python_table1_rows(python)
    findings.extend(py_findings)
    _source(findings[mark:], SRC_PATH_B)

    # A table1 with nothing in it must never pass: every loop below is driven by
    # these collections, so an empty one means the comparison proved nothing.
    if not rows:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "displayed table", text, None,
            "the displayed table carried no rows to compare",
            source=SRC_SCREEN))
    if not py_by_key:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "Path B rows", None, None,
            "Path B produced no rows to compare", source=SRC_PATH_B))
    if not (exact.get("continuous") or exact.get("categorical")):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "exported script harvest", None, None,
            "the exported script's harvest carried no per-variable statistics",
            source=SRC_HARVEST))

    # -- per-group Ns, from BOTH directions. The displayed `(N=...)` headers are
    # a display claim; the harvest's n_per_group is Path A's own count. Both are
    # compared against Path B over the key union, so a level present on only one
    # side is a finding either way.
    mark = len(findings)
    py_group_n = python.get("n_per_group") or {}
    exact_group_n = exact.get("n_per_group") or {}
    if not py_group_n:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "n_per_group", None, None,
            "Path B produced no per-group counts to compare"))
    if not exact_group_n:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "n_per_group", None, None,
            "Path A's harvest carried no per-group counts to compare"))
    for level in sorted(set(headers) | set(py_group_n) | set(exact_group_n)):
        shown, a, b = (shown_group_n.get(level), exact_group_n.get(level),
                       py_group_n.get(level))
        if a is None or b is None:
            missing = "Path A" if a is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", level, "n_per_group", a, b,
                f"{missing} has no count for this group level"))
        else:
            compared += 1
            if a != b:
                findings.append(finding(
                    "COUNT_MISMATCH", level, "n_per_group", a, b,
                    "the two paths analysed different rows for this group"))
        # This loop is MIXED: the n_per_group comparisons above are harvest vs
        # Path B, the two below are screen vs Path B. A block marker cannot tell
        # them apart, so the displayed ones name their own source and the marker
        # (first tag wins) leaves them alone.
        if shown is None:
            findings.append(finding(
                "MISSING_QUANTITY", level, "displayed group header", None, b,
                "the displayed table has no column header for this group "
                "level", source=SRC_DISPLAY))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        if b is None:
            continue  # already recorded as MISSING_QUANTITY above
        compared += 1
        if shown != b:
            findings.append(finding(
                "COUNT_MISMATCH", level, "displayed group header", shown, b,
                "the displayed column header's N disagrees with Path B's "
                "per-group count", source=SRC_DISPLAY))
    _source(findings[mark:], SRC_EXACT)

    # -- ORDER. The spec pins both orders as normative — group levels in
    # FIRST-APPEARANCE order (never sorted), and rows as all continuous
    # variables then all categorical, in selection order. Neither is checked by
    # any loop above (they all run over sorted key unions), so without this a
    # correctly-valued table printed in the wrong order would pass silently.
    # Both comparisons are gated on the two sides carrying the same keys, so a
    # missing row or level is reported once, as MISSING_QUANTITY, rather than
    # also as a spurious ordering difference.
    mark = len(findings)
    py_levels = python.get("levels")
    if not isinstance(py_levels, list):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "level order", headers, py_levels,
            "Path B reports no `levels` list, so the displayed column order "
            "could not be checked"))
    elif set(py_levels) == set(headers):
        compared += 1
        if py_levels != headers:
            findings.append(finding(
                "DEFECT", "-", "level order", headers, py_levels,
                "the group columns are in a different order; the app orders "
                "levels by first appearance in the file, never sorted"))
    py_order = [k for k in (
        (r["variable"] if r.get("level") in (None, "")
         else f"{r['variable']}: {r['level']}")
        for r in (python.get("rows") or []) if isinstance(r, dict)
        and "variable" in r)]
    shown_order = [r["key"] for r in rows]
    if set(py_order) == set(shown_order):
        compared += 1
        if py_order != shown_order:
            findings.append(finding(
                "DEFECT", "-", "row order", shown_order, py_order,
                "the table rows are in a different order; the app emits every "
                "continuous variable first, then every categorical one, in "
                "selection order"))

    # -- the DECISION tier. One kind per variable, on each side, compared as its
    # own quantity: mean vs median vs count. This is the quantity that makes
    # Table 1 different from every other analysis here.
    shown_kinds = {}
    for row in rows:
        shown_kinds.setdefault(row["variable"], row["kind"])
    for var in sorted(set(shown_kinds) | set(py_kinds)):
        a, b = shown_kinds.get(var), py_kinds.get(var)
        if a is None or b is None:
            missing = "Path A" if a is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", var, "decisions", a, b,
                f"{missing} reports no summary kind for this variable"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        targets.credit("decisions")
        if a != b:
            findings.append(finding(
                "DECISION_MISMATCH", var, "decisions", a, b,
                "the two paths chose different summary statistics for this "
                "variable; a wrong choice is a defect even when both sets of "
                "numbers are individually correct"))

    # -- display tier. Every cell string, exactly. No artifact tier: at three
    # significant figures the rendered string IS the published claim.
    for key in sorted(set(rows_by_key) | set(py_by_key)):
        row, py = rows_by_key.get(key), py_by_key.get(key)
        if row is None or py is None:
            missing = "Path A" if row is None else "Path B"
            findings.append(finding(
                "MISSING_QUANTITY", key, "displayed row",
                row["label"] if row else None, key if py else None,
                f"{missing} has no row for this key"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        py_cells = py.get("cells")
        if not isinstance(py_cells, dict):
            findings.append(finding(
                "MISSING_QUANTITY", key, "displayed cell", row["cells"],
                py_cells, "Path B's row carries no `cells` mapping"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        for level in sorted(set(row["cells"]) | set(py_cells)):
            shown, mine = row["cells"].get(level), py_cells.get(level)
            if shown is None or mine is None:
                missing = "Path A" if shown is None else "Path B"
                findings.append(finding(
                    "MISSING_QUANTITY", key, f"displayed cell [{level}]",
                    shown, mine, f"{missing} has no cell for this group level"))
                continue  # NOT a silent skip: MISSING_QUANTITY was recorded
            compared += 1
            if shown != mine:
                findings.append(finding(
                    "DEFECT", key, f"displayed cell [{level}]", shown, mine,
                    "the displayed cell strings differ; for Table 1 the "
                    "rendered string at 3 significant figures is the claim"))
        mine_missing = py.get("missing")
        if mine_missing is None:
            findings.append(finding(
                "MISSING_QUANTITY", key, "displayed missing cell",
                row["missing"], None,
                "Path B's row carries no `missing` cell"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        compared += 1
        if row["missing"] != mine_missing:
            findings.append(finding(
                "DEFECT", key, "displayed missing cell", row["missing"],
                mine_missing,
                "the displayed missing-value counts differ"))
    # Covers the order block, the decision tier and the display tier above: all
    # three read the SCREEN on the left and Path B on the right.
    _source(findings[mark:], SRC_DISPLAY)

    # -- script tier. Path A against itself: does the exported .R, rendered
    # through fig_summary's own display rule, reproduce the table on screen —
    # both the numbers AND the statistic it chose? Never touches Path B.
    script_findings, script_compared = _table1_script_tier(exact, rows_by_key)
    findings.extend(_source(script_findings, SRC_SCRIPT))
    compared += script_compared

    findings.extend(_source(targets.findings(), SRC_COVERAGE))
    return findings, compared, targets


def _table1_harvest_cells(exact):
    """The exported script's harvest -> {row key: (kind, kind_is_evidence,
    {level: cell string})}.

    One place builds this so the script tier's count of comparisons and its
    findings can never be derived from two different readings of the harvest.

    `kind_is_evidence` says whether the harvest's `kind` is a CLAIM the script
    made or a label this function wrote. For a continuous variable it is a
    claim: run-script.R reads it off the harvested element names (`c("mean",
    "sd")` vs `c("25%","50%","75%")`), so the script really did re-express the
    app's mean-vs-median choice and comparing it is evidence. For a categorical
    variable there is no choice to make and no name to read — "count" is
    hard-coded on BOTH sides (here, and in parse_table1_tsv's categorical
    branch), so comparing them is comparing two constants. The comparison is
    still performed (a screen row that claimed `mean` for a variable the script
    tabulated is worth saying out loud), but it is NOT counted as a comparison
    performed: `compared` is the evidence count, and a constant equals itself
    for free.
    """
    out = {}
    for var, info in (exact.get("continuous") or {}).items():
        kind = info.get("kind")
        cells = {}
        for level, stat in (info.get("stats") or {}).items():
            stat = stat or {}
            if kind == "mean":
                cells[level] = format_mean_cell_t1(stat.get("mean"),
                                                   stat.get("sd"))
            elif kind == "median":
                cells[level] = format_median_cell_t1(
                    stat.get("25%"), stat.get("50%"), stat.get("75%"))
            else:
                cells[level] = None
        out[var] = (kind, True, cells)
    for var, info in (exact.get("categorical") or {}).items():
        denom = info.get("denom") or {}
        counts = info.get("counts") or {}
        out[var] = ("count", False, {level: "" for level in counts})
        for level in info.get("levels") or []:
            out[f"{var}: {level}"] = (
                "count", False,
                {g: format_count_cell_t1((counts.get(g) or {}).get(level, 0),
                                         denom.get(g))
                 for g in counts})
    return out


def _table1_script_tier(exact, rows_by_key):
    """(findings, comparisons performed) for the script tier."""
    findings = []
    compared = 0
    harvest = _table1_harvest_cells(exact)
    for key, (kind, kind_is_evidence, cells) in sorted(harvest.items()):
        row = rows_by_key.get(key)
        if row is None:
            findings.append(finding(
                "MISSING_QUANTITY", key, "exported script row", None, key,
                "the exported script produced a variable or level with no "
                "displayed row"))
            continue  # NOT a silent skip: MISSING_QUANTITY was just recorded
        if kind_is_evidence:
            compared += 1  # the kind claim the script actually made
        if kind != row["kind"]:
            findings.append(finding(
                "SCRIPT_DIVERGENCE", key, "exported script decision",
                row["kind"], kind,
                "the exported .R computed a different summary statistic than "
                "the one the screen declared for this variable"))
        for level, rendered in sorted(cells.items()):
            shown = row["cells"].get(level)
            if shown is None:
                findings.append(finding(
                    "MISSING_QUANTITY", key,
                    f"exported script cell [{level}]", None, rendered,
                    "the exported script produced a group the displayed row "
                    "has no cell for"))
                continue  # NOT a silent skip: MISSING_QUANTITY was recorded
            if rendered is None:
                findings.append(finding(
                    "MISSING_QUANTITY", key,
                    f"exported script cell [{level}]", shown, None,
                    "the exported script's statistic could not be rendered "
                    "through the app's display rule"))
                continue  # NOT a silent skip: MISSING_QUANTITY was recorded
            compared += 1
            if rendered != shown:
                findings.append(finding(
                    "SCRIPT_DIVERGENCE", key,
                    f"exported script cell [{level}]", shown, rendered,
                    "the exported .R does not reproduce the cell the screen "
                    "showed"))
    for key, row in sorted(rows_by_key.items()):
        if key not in harvest:
            findings.append(finding(
                "MISSING_QUANTITY", key, "exported script row", row["label"],
                None,
                "the displayed table has a row the exported script's harvest "
                "does not account for"))
    return findings, compared


# Per-kind dispatch. Registering a kind is the ONLY way to compare it: an
# unregistered kind stops loudly rather than being waved through as "nothing
# to compare", which would publish a green result backed by zero evidence.
KIND_HANDLERS = {"ratio_table": compare_ratio_table,
                 "km_summary": compare_km_summary,
                 "gc_summary": compare_gc_summary,
                 "table1": compare_table1}

# Kinds this comparator knows are coming but cannot compare yet. Empty: every
# display.kind any shipped case declares is implemented. (`table1` lived here
# until Task 11 implemented it. The remaining Table 1 gap is Path B —
# validate/summary.py — not the comparator; the Makefile carries that, so a
# case whose python.json does not exist is never handed to compare.py at all.)
PENDING_KINDS = {}


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
    # Safety net for the source attribution: a finding that reached publication
    # without one is a comparator bug, and it must SAY so on the scorecard
    # rather than inherit a neighbour's label. Not a crash — an unlabelled
    # finding is still a real finding, and suppressing the whole report to
    # punish a missing annotation would lose evidence.
    _source(findings, SRC_UNCLASSIFIED)
    findings.sort(key=_rank)
    return {
        "id": case_id,
        "kind": kind,
        "compared": compared,
        "passed": len(findings) == 0,
        "targets_met": targets.met,
        "targets": dict(targets.counts),
        # Declared coverage this run did not enforce because the comparison
        # block has not landed yet. Empty for every case whose blocks are all
        # live. Published rather than folded into `targets`, so "targets met"
        # can never be read as "everything the case declares was checked".
        "deferred_targets": list(targets.deferred),
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
        # A deferred target is neither met nor failed — it was not checked. Say
        # so on the same line as the coverage verdict, so a green case never
        # reads as fully covered while a block is still pending.
        deferred = c.get("deferred_targets") or []
        if deferred:
            met += f" ({len(deferred)} DEFERRED: {', '.join(deferred)})"
        print(f"{c['id']}: {c['compared']} compared, {status}, {met}")
        for f in c["findings"]:
            # The source is printed here too, not only on the scorecard: this
            # console output is what gets pasted into reports, and "figura="
            # alone does not say whether the value came from the screen or from
            # the exported script.
            print(f"  [{f['disposition']:6}] {f['code']} [{f['source']}] "
                  f"{f['term']} {f['quantity']}: figura={f['figura']!r} "
                  f"python={f['python']!r} — {f['note']}")
    ok = all(c["passed"] and c["targets_met"] for c in reports)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

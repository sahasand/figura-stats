"""Descriptive Table 1, written from spec/summary-table1.md.

The spec models the LIVE APP ONLY (web/guided/summary/analyze-form.js's
buildSummarySpec feeding R/summarize.R's fig_summary), never the exported .R
script. Cell-reading, classification, the mean-vs-median decision, and number
formatting are restated here exactly as that spec pins them; see DECISIONS.md
for the handful of points the spec leaves silent.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .groupcompare import _r_numeric, _text

MISSING_GROUP_LABEL = "(missing)"


# ---------------------------------------------------------------------------
# number formatting
# ---------------------------------------------------------------------------

def fmt_num(v):
    """R's .fmt_num: format(signif(v, 3), trim=TRUE, scientific=FALSE,
    drop0trailing=TRUE).

    Implements R's actual signif algorithm -- scale by 10**e, round the
    SCALED value half-to-even (Python's argument-less round() on a float),
    scale back -- rather than a decimal-exact round, per the spec's own
    worked examples (2.225 -> "2.22", 1.315 -> "1.32").
    """
    v = float(v)
    if v == 0:
        return "0"
    sign = -1 if v < 0 else 1
    av = abs(v)

    e = 3 - 1 - math.floor(math.log10(av))
    scaled = av * (10.0 ** e)
    # log10/floor can land a hair outside [100, 1000) at the boundary
    # (floating-point drift); nudge e back into range before rounding.
    while scaled >= 1000:
        e -= 1
        scaled = av * (10.0 ** e)
    while scaled < 100:
        e += 1
        scaled = av * (10.0 ** e)

    rounded = round(scaled)  # ties-to-even, exactly what R's nearbyint does
    if rounded >= 1000:
        rounded //= 10
        e -= 1
    elif rounded < 100:
        rounded *= 10
        e += 1

    return _render_digits(rounded, e, sign)


def _render_digits(rounded, e, sign):
    digits = str(int(rounded))
    if e <= 0:
        s = digits + "0" * (-e)
    elif e >= len(digits):
        s = "0." + "0" * (e - len(digits)) + digits
    else:
        s = digits[:-e] + "." + digits[-e:]
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s == "" or s == "0":
        return "0"
    return ("-" if sign < 0 else "") + s


# ---------------------------------------------------------------------------
# the decision rule
# ---------------------------------------------------------------------------

def _population_skewness(x):
    m = float(np.mean(x))
    s = math.sqrt(float(np.mean((x - m) ** 2)))
    if s == 0:
        return 0.0
    return float(np.mean((x - m) ** 3) / s ** 3)


def decide(x):
    """The mean-vs-median rule. `x` is the array of values already fed to the
    decision (group-mean-centred and pooled, by the caller, when a group role
    exists); this function does not know or care whether that centring
    happened -- population skewness and Shapiro-Wilk are both shift-invariant,
    so re-centring already-centred data is a no-op.
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = x.size
    distinct = len(set(x.tolist()))

    if n < 3 or distinct < 3:
        return {"kind": "median"}

    skewness = _population_skewness(x)

    if n > 300:
        # No normality test at this size -- Shapiro-Wilk over-rejects trivial
        # departures for large n.
        kind = "mean" if abs(skewness) < 1 else "median"
        return {"kind": kind, "skewness": skewness}

    p_value = float(stats.shapiro(x).pvalue)
    kind = "mean" if (p_value >= 0.05 and abs(skewness) < 1) else "median"
    return {"kind": kind, "skewness": skewness, "p_value": p_value}


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def _is_continuous(texts):
    """Numeric AND more than five distinct non-missing (trimmed-text) values.

    Numeric: every non-blank cell parses as a finite number (R's as.numeric,
    the same parser groupcompare.py's _r_numeric restates) and at least one
    cell is non-blank. One literal "NA" cell -- not a number -- makes the
    whole column categorical.
    """
    non_blank = [t for t in texts if t != ""]
    if not non_blank:
        return False
    if not all(_r_numeric(t) is not None for t in non_blank):
        return False
    return len(set(non_blank)) > 5


# ---------------------------------------------------------------------------
# continuous rows
# ---------------------------------------------------------------------------

def _continuous_cell(xg, kind):
    if xg.size == 0:
        return "—"  # em dash
    if xg.size == 1:
        return fmt_num(float(xg[0]))
    if kind == "mean":
        mean_v = float(np.mean(xg))
        sd_v = float(np.std(xg, ddof=1))
        return f"{fmt_num(mean_v)} ± {fmt_num(sd_v)}"
    q1, q2, q3 = np.quantile(xg, [0.25, 0.5, 0.75], method="linear")
    return f"{fmt_num(q2)} ({fmt_num(q1)}–{fmt_num(q3)})"


def _continuous_row(var, texts, group_of_row, levels):
    values = [_r_numeric(t) if t != "" else None for t in texts]
    missing = sum(1 for v in values if v is None)

    raw_by_group = {level: [] for level in levels}
    for value, level in zip(values, group_of_row):
        if value is not None:
            raw_by_group[level].append(value)

    # The decision is made ONCE per variable, on group-mean-centred values
    # pooled across all groups -- never re-decided per group.
    centred = []
    for level in levels:
        vals = raw_by_group[level]
        if vals:
            group_mean = sum(vals) / len(vals)
            centred.extend(v - group_mean for v in vals)
    kind = decide(np.array(centred, dtype=float))["kind"]

    # The cells themselves come from each group's RAW (uncentred) values.
    cells = {level: _continuous_cell(np.array(raw_by_group[level], dtype=float), kind)
             for level in levels}

    return {
        "variable": var,
        "level": None,
        "kind": kind,
        "cells": cells,
        "missing": str(missing),
    }


# ---------------------------------------------------------------------------
# categorical rows
# ---------------------------------------------------------------------------

def _categorical_rows(var, texts, group_of_row, levels):
    missing = sum(1 for t in texts if t == "")

    header = {
        "variable": var,
        "level": None,
        "kind": "count",
        "cells": {level: "" for level in levels},
        "missing": str(missing),
    }
    rows = [header]

    level_values = sorted(t for t in set(texts) if t != "")
    denom = {level: 0 for level in levels}
    counts = {level: {lv: 0 for lv in level_values} for level in levels}
    for t, g in zip(texts, group_of_row):
        if t == "":
            continue
        denom[g] += 1
        counts[g][t] += 1

    for lv in level_values:
        cells = {}
        for level in levels:
            d = denom[level]
            k = counts[level][lv]
            if d == 0:
                cells[level] = "—"
            else:
                pct = round(100 * k / d)  # sprintf("%.0f%%"), half-to-even
                cells[level] = f"{k} ({pct}%)"
        rows.append({
            "variable": var,
            "level": lv,
            "kind": "count",
            "cells": cells,
            "missing": "",
        })

    return rows


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def summarize(df, variables, group=None):
    n = len(df)

    if group is None:
        levels = ["Overall"]
        group_of_row = ["Overall"] * n
    else:
        raw_group_text = [_text(c) for c in df[group]]
        group_of_row = [g if g != "" else MISSING_GROUP_LABEL for g in raw_group_text]
        levels = []
        seen = set()
        for g in group_of_row:
            if g not in seen:
                seen.add(g)
                levels.append(g)

    n_per_group = {level: 0 for level in levels}
    for g in group_of_row:
        n_per_group[g] += 1

    rows = []
    for var in variables:
        texts = [_text(c) for c in df[var]]
        if _is_continuous(texts):
            rows.append(_continuous_row(var, texts, group_of_row, levels))
        else:
            rows.extend(_categorical_rows(var, texts, group_of_row, levels))

    return {
        "rows": rows,
        "levels": levels,
        "n_per_group": n_per_group,
        "n": n,
        "n_dropped": 0,
    }

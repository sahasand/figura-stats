"""Group comparison, written from spec/groupcompare-{numeric,categorical,dirty}.md.

The specs model the LIVE APP (web/guided/groupcompare/spec.js feeding
R/groupcompare.R), never the exported .R script, and they win over any textbook
form of the same-named quantity. The places where this module deliberately
departs from a library default are marked; they are the whole point of the
module.
"""
import math
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq

from .io import complete_cases

# Test names carry EN DASHes (U+2013), not hyphens; the comparator compares the
# strings literally.
WELCH_T = "Welch t-test"
MANN_WHITNEY = "Mann–Whitney U test"
WELCH_ANOVA = "one-way ANOVA (Welch)"
KRUSKAL_WALLIS = "Kruskal–Wallis test"
CHI_SQUARE = "Pearson chi-square test"
FISHER = "Fisher's exact test"


# ---------------------------------------------------------------------------
# Cell reading
# ---------------------------------------------------------------------------

def _text(cell):
    """Every cell is read as text and trimmed before anything else looks at it.

    Mirrors the app's CSV parser, which applies String(cell).trim() to every
    cell as it builds the table. A cell that is empty after trimming is blank.
    """
    if cell is None:
        return ""
    if isinstance(cell, float) and math.isnan(cell):
        return ""
    if cell is pd.NA or cell is pd.NaT:
        return ""
    return str(cell).strip()


def _r_numeric(text):
    """R's numeric conversion, or None when the text does not parse.

    Pinned by the specs against R directly. Accepted: "01", " 01 ", "1e3",
    "0x1A", "Inf", "-Inf". Rejected: "NA", "NaN", "1,000", "TRUE", and any
    whitespace-only cell that reached here untrimmed.

    Two divergences from Python's own float() are handled here rather than
    inherited: float() accepts "nan" (R's as.numeric gives NaN, which the app's
    is.na check treats as non-parsing) and accepts underscore digit separators
    ("1_000"), which R rejects; float() rejects hex, which R accepts.
    """
    s = text.strip()
    if s == "":
        return None
    if "_" in s:
        return None
    body = s[1:] if s[:1] in "+-" else s
    if body[:2].lower() == "0x":
        try:
            value = float.fromhex(s)
        except ValueError:
            return None
        return value
    try:
        value = float(s)
    except ValueError:
        return None
    if math.isnan(value):
        return None
    return value


def _is_numeric_outcome(texts):
    """NUMERIC iff every non-blank cell parses. Blanks are ignored by the test,
    so an all-blank column is vacuously numeric.

    Parseability alone — no distinct-value threshold, no leading-zero check, no
    cardinality heuristic. A column of zero-padded site codes is NUMERIC.
    """
    return all(_r_numeric(t) is not None for t in texts if t != "")


def _mapped_frame(df, outcome, group):
    """The two mapped roles, trimmed. Unmapped columns never cross into any
    intermediate representation, so a blank in one of them can never drop a row.
    """
    return pd.DataFrame({
        "outcome": [_text(c) for c in df[outcome]],
        "group": [_text(c) for c in df[group]],
    })


# ---------------------------------------------------------------------------
# Shared numerics
# ---------------------------------------------------------------------------

def _bh_adjust(pvalues):
    """R's p.adjust(method = "BH") — Benjamini-Hochberg FDR, not Bonferroni and
    not Holm."""
    p = np.asarray(pvalues, dtype=float)
    n = p.size
    if n == 0:
        return p
    order = np.argsort(-p, kind="stable")
    ranks = np.arange(n, 0, -1)
    adjusted = np.minimum.accumulate(n / ranks * p[order])
    out = np.empty(n, dtype=float)
    out[order] = np.minimum(adjusted, 1.0)
    return out


def _mid_ranks(values):
    return stats.rankdata(values, method="average")


def _tie_term(values):
    """sum(t^3 - t) over groups of tied VALUES of size t."""
    _, counts = np.unique(values, return_counts=True)
    counts = counts.astype(float)
    return float(np.sum(counts ** 3 - counts))


# ---------------------------------------------------------------------------
# Parametric / non-parametric routing
# ---------------------------------------------------------------------------

def _route(values_by_group):
    """The routing rule, decided ONCE and globally.

    Step 1 centres within groups: the normality assessment runs on the pooled
    group-MEAN-centred residuals, never on the raw pooled outcome. Pooling raw
    values from separated groups gives a multi-modal mixture that fails any
    normality test.

    Returns True for the non-parametric branch.
    """
    centred = [np.asarray(v, dtype=float) - np.mean(v)
               for v in values_by_group.values()]
    x = np.concatenate(centred)
    x = x[~np.isnan(x)]
    n = x.size

    # Distinctness is counted on the CENTRED residuals, not the raw outcome.
    if n < 3 or len(set(x.tolist())) < 3:
        return True

    m = float(np.mean(x))
    s = math.sqrt(float(np.mean((x - m) ** 2)))          # population SD: / n
    sk = 0.0 if s == 0 else float(np.mean((x - m) ** 3) / s ** 3)

    if n > 300:
        # Shapiro-Wilk is deliberately not consulted above n = 300.
        return not (abs(sk) < 1)

    shapiro_p = float(stats.shapiro(x).pvalue)
    # Both conditions must hold. p exactly 0.05 is parametric; |sk| exactly 1
    # is not.
    return not (shapiro_p >= 0.05 and abs(sk) < 1)


# ---------------------------------------------------------------------------
# Omnibus tests
# ---------------------------------------------------------------------------

def _welch_t(x1, x2):
    """R's t.test default: unequal variances assumed, NOT the pooled/Student
    test. The statistic is (first sorted group - second)."""
    n1, n2 = x1.size, x2.size
    v1, v2 = float(np.var(x1, ddof=1)), float(np.var(x2, ddof=1))
    se2 = v1 / n1 + v2 / n2
    t = (float(np.mean(x1)) - float(np.mean(x2))) / math.sqrt(se2)
    df = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    p = 2 * float(stats.t.sf(abs(t), df))
    return t, p


def _mann_whitney(x, y):
    """R's wilcox.test defaults: an exact p-value when both group sizes are
    under 50 and the pooled data has no ties, otherwise the normal
    approximation WITH a continuity correction.

    W is R's own statistic — the count of pairs (i, j) with x_i > y_j, tied
    pairs contributing one half, for x the FIRST group in string-sort order.
    """
    n1, n2 = x.size, y.size
    pooled = np.concatenate([x, y])
    ranks = _mid_ranks(pooled)
    w = float(np.sum(ranks[:n1]) - n1 * (n1 + 1) / 2)

    tie_term = _tie_term(pooled)
    has_ties = tie_term > 0

    if n1 < 50 and n2 < 50 and not has_ties:
        # Exact: R's pwilcox two-sided construction.
        if w > n1 * n2 / 2:
            tail = float(stats.mannwhitneyu(
                x, y, alternative="greater", method="exact").pvalue)
        else:
            tail = float(stats.mannwhitneyu(
                x, y, alternative="less", method="exact").pvalue)
        return w, min(2 * tail, 1.0)

    n = n1 + n2
    sigma = math.sqrt((n1 * n2 / 12) * ((n + 1) - tie_term / (n * (n - 1))))
    z = w - n1 * n2 / 2
    correction = math.copysign(0.5, z) if z != 0 else 0.0
    z = (z - correction) / sigma
    tail = float(stats.norm.sf(z)) if z > 0 else float(stats.norm.cdf(z))
    return w, min(2 * tail, 1.0)


def _welch_oneway(values_by_group):
    """Welch 1951, R's oneway.test default var.equal = FALSE. NOT the classical
    fixed-effects one-way ANOVA: no pooling of within-group variances, and
    Welch-Satterthwaite (fractional) denominator df.
    """
    n_i = np.array([v.size for v in values_by_group.values()], dtype=float)
    m_i = np.array([np.mean(v) for v in values_by_group.values()], dtype=float)
    v_i = np.array([np.var(v, ddof=1) for v in values_by_group.values()],
                   dtype=float)
    k = n_i.size

    w_i = n_i / v_i
    w_sum = float(np.sum(w_i))
    mbar = float(np.sum(w_i * m_i) / w_sum)

    tmp = float(np.sum((1 - w_i / w_sum) ** 2 / (n_i - 1)))
    a = float(np.sum(w_i * (m_i - mbar) ** 2)) / (k - 1)
    b = tmp * 2 * (k - 2) / (k ** 2 - 1)
    f = a / (1 + b)
    df1 = float(k - 1)
    df2 = (k ** 2 - 1) / (3 * tmp)
    p = float(stats.f.sf(f, df1, df2))
    return f, p, df1, df2


def _kruskal_wallis(values_by_group):
    """R's kruskal.test: mid-ranks over the pooled sample, H corrected for ties
    by dividing by 1 - sum(t^3 - t) / (N^3 - N), p from the upper chi-square
    tail with k - 1 df."""
    pooled = np.concatenate(list(values_by_group.values()))
    ranks = _mid_ranks(pooled)
    n = pooled.size
    k = len(values_by_group)

    start = 0
    h = 0.0
    for values in values_by_group.values():
        size = values.size
        rbar = float(np.mean(ranks[start:start + size]))
        h += size * (rbar - (n + 1) / 2) ** 2
        start += size
    h *= 12 / (n * (n + 1))

    tie_term = _tie_term(pooled)
    h /= 1 - tie_term / (n ** 3 - n)
    p = float(stats.chi2.sf(h, k - 1))
    return h, p


def _classical_anova(values_by_group):
    """The ordinary pooled-variance one-way ANOVA. It never produces a reported
    p-value in this branch — it exists to feed eta-squared and Tukey, which the
    app builds on the classical fit even though the Welch test decided
    significance. That inconsistency is the app's, and is preserved."""
    pooled = np.concatenate(list(values_by_group.values()))
    n = pooled.size
    k = len(values_by_group)
    grand = float(np.mean(pooled))

    ss_b = float(sum(v.size * (float(np.mean(v)) - grand) ** 2
                     for v in values_by_group.values()))
    ss_r = float(sum(float(np.sum((v - np.mean(v)) ** 2))
                     for v in values_by_group.values()))
    df1 = float(k - 1)
    df2 = float(n - k)
    f = (ss_b / df1) / (ss_r / df2)
    return ss_b, ss_r, f, df1, df2


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------

def _cohens_d(x1, x2):
    """The app's Cohen's d: pooled SD, NO Hedges/J small-sample correction, and
    an SE whose second denominator is 2*(n1+n2) rather than the textbook
    2*(n1+n2-2). The interval uses the literal constant 1.96.

    Sign is (second sorted group - first), so a positive d means the SECOND
    group is larger.
    """
    n1, n2 = x1.size, x2.size
    v1, v2 = float(np.var(x1, ddof=1)), float(np.var(x2, ddof=1))
    sp = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    d = (float(np.mean(x2)) - float(np.mean(x1))) / sp
    se = math.sqrt((n1 + n2) / (n1 * n2) + d ** 2 / (2 * (n1 + n2)))
    return {"label": "Cohen's d", "value": d,
            "lo": d - 1.96 * se, "hi": d + 1.96 * se}


def _rank_biserial(u, n1, n2):
    """From the same U (R's W) the test reported. The clamp is applied only to
    the value fed into the Fisher-z interval; the reported r is NOT clamped and
    may be exactly +/-1 under complete separation."""
    r = 1 - 2 * u / (n1 * n2)
    z = math.atanh(min(max(r, -0.999999), 0.999999))
    se = 1 / math.sqrt(n1 + n2 - 3)
    return {"label": "rank-biserial r", "value": r,
            "lo": math.tanh(z - 1.96 * se), "hi": math.tanh(z + 1.96 * se)}


def _eta_squared(ss_b, ss_r, f_value, df1, df2):
    """eta-squared with a non-central-F (Steiger) interval. Both the point
    estimate and the interval come from the CLASSICAL ANOVA decomposition, not
    from the Welch test that produced the p-value."""
    eta_sq = ss_b / (ss_b + ss_r)

    def cdf(lam):
        if lam <= 0:
            return float(stats.f.cdf(f_value, df1, df2))
        return float(stats.ncf.cdf(f_value, df1, df2, lam))

    def lam_to_eta(lam):
        return lam / (lam + df1 + df2 + 1)

    def find(q):
        # The bracketing is part of the specification: it determines the
        # fallbacks.
        if cdf(0) - q < 0:
            return 0.0
        hi = 1.0
        while cdf(hi) - q > 0 and hi < 1e6:
            hi *= 2
        if cdf(hi) - q > 0:
            return None
        # Converged tightly on purpose. R's uniroot stops at its own default
        # tolerance (~1.2e-4 on the non-centrality scale), so R's own limits sit
        # a small distance from a fully converged root; the spec says not to
        # chase that gap.
        return brentq(lambda lam: cdf(lam) - q, 0.0, hi,
                      xtol=1e-12, rtol=1e-14, maxiter=500)

    a = 0.025
    lower_lam = find(1 - a)
    upper_lam = find(a)
    lo = 0.0 if lower_lam is None else max(0.0, lam_to_eta(lower_lam))
    hi = 1.0 if upper_lam is None else min(1.0, lam_to_eta(upper_lam))
    return {"label": "eta-squared", "value": eta_sq, "lo": lo, "hi": hi}


def _epsilon_squared(h, n):
    """No confidence interval — the app reports the point estimate alone."""
    return {"label": "epsilon-squared", "value": h / (n - 1),
            "lo": None, "hi": None}


# ---------------------------------------------------------------------------
# Post-hoc
# ---------------------------------------------------------------------------

def _tukey_pairs(values_by_group, ss_r, df2):
    """Tukey HSD on the classical one-way fit.

    Pair naming is "<later>-<earlier>" in string-sort order — R's own TukeyHSD
    row labels. The OPPOSITE of Dunn's convention below; do not normalise them.
    """
    levels = list(values_by_group)
    k = len(levels)
    mse = ss_r / df2

    significant = []
    for i, j in combinations(range(k), 2):
        a, b = values_by_group[levels[i]], values_by_group[levels[j]]
        diff = float(np.mean(b)) - float(np.mean(a))
        se = math.sqrt(mse / 2 * (1 / a.size + 1 / b.size))
        q = abs(diff) / se
        p_adj = float(stats.studentized_range.sf(q, k, df2))
        if p_adj < 0.05:
            significant.append(f"{levels[j]}-{levels[i]}")
    return {"test": "Tukey HSD", "significant_pairs": significant}


def _dunn_pairs(values_by_group):
    """Dunn's test from the SHARED overall ranking — the pooled outcome is
    ranked once, across all groups, with mid-ranks for ties. Never re-ranked
    within a pair.

    Pair naming is "<earlier>-<later>", the app's own pairing loop over the
    sorted levels — the opposite of Tukey's.
    """
    levels = list(values_by_group)
    pooled = np.concatenate([values_by_group[level] for level in levels])
    ranks = _mid_ranks(pooled)
    n_total = pooled.size
    tie_term = _tie_term(pooled)

    rbar, sizes = {}, {}
    start = 0
    for level in levels:
        size = values_by_group[level].size
        rbar[level] = float(np.mean(ranks[start:start + size]))
        sizes[level] = size
        start += size

    pairs, raw = [], []
    for level_i, level_j in combinations(levels, 2):
        sigma = math.sqrt(
            (n_total * (n_total + 1) / 12
             - tie_term / (12 * (n_total - 1)))
            * (1 / sizes[level_i] + 1 / sizes[level_j]))
        z = (rbar[level_i] - rbar[level_j]) / sigma
        pairs.append(f"{level_i}-{level_j}")
        raw.append(2 * float(stats.norm.cdf(-abs(z))))

    # All k*(k-1)/2 raw p-values are adjusted TOGETHER, by BH.
    adjusted = _bh_adjust(raw)
    significant = [name for name, p in zip(pairs, adjusted) if p < 0.05]
    return {"test": "Dunn's test (BH-adjusted)",
            "significant_pairs": significant}


# ---------------------------------------------------------------------------
# Categorical branch
# ---------------------------------------------------------------------------

def _chi_square(table):
    """Pearson chi-square WITHOUT any continuity correction. R applies Yates'
    by default on 2x2 tables; the app explicitly turns it off."""
    observed = np.asarray(table, dtype=float)
    row_tot = observed.sum(axis=1, keepdims=True)
    col_tot = observed.sum(axis=0, keepdims=True)
    total = observed.sum()
    expected = row_tot @ col_tot / total
    x2 = float(np.sum((observed - expected) ** 2 / expected))
    dof = (observed.shape[0] - 1) * (observed.shape[1] - 1)
    p = float(stats.chi2.sf(x2, dof))
    return x2, p, expected


def _fisher_rxc(table):
    """Fisher's exact test, general r x c form, by exhaustive enumeration.

    The null distribution is the multivariate hypergeometric over all tables
    with the SAME row and column margins as the observed one; the two-sided
    p-value is the total probability of every such table whose probability is
    at most the observed table's, R admitting a table exceeding it by no more
    than a relative 1e-7 (a tolerance that only affects exact ties).

    Enumerated directly rather than delegated: scipy.stats.fisher_exact is
    exact only for 2x2 and runs a Monte Carlo test for anything larger — two
    calls on one 3x3 input return two different answers, which cannot meet the
    harness's 1e-6 gate.
    """
    observed = np.asarray(table, dtype=np.int64)
    nrow, ncol = observed.shape
    row_tot = [int(v) for v in observed.sum(axis=1)]
    col_tot = [int(v) for v in observed.sum(axis=0)]
    total = int(observed.sum())

    log_fact = [math.lgamma(i + 1.0) for i in range(total + 1)]
    const = (sum(log_fact[r] for r in row_tot)
             + sum(log_fact[c] for c in col_tot) - log_fact[total])
    observed_logp = const - sum(log_fact[int(v)] for v in observed.ravel())
    threshold = observed_logp + math.log1p(1e-7)

    accumulated = 0.0

    def walk_row(i, cols_left, log_denominator):
        nonlocal accumulated
        if i == nrow - 1:
            # The last row is forced by the remaining column totals.
            logp = const - (log_denominator
                            + sum(log_fact[c] for c in cols_left))
            if logp <= threshold:
                accumulated += math.exp(logp)
            return
        walk_cell(i, 0, row_tot[i], cols_left, log_denominator)

    def walk_cell(i, j, left_in_row, cols_left, log_denominator):
        if j == ncol - 1:
            if left_in_row > cols_left[j]:
                return
            updated = list(cols_left)
            updated[j] -= left_in_row
            walk_row(i + 1, updated, log_denominator + log_fact[left_in_row])
            return
        capacity = sum(cols_left[j + 1:])
        low = max(0, left_in_row - capacity)
        high = min(left_in_row, cols_left[j])
        for value in range(low, high + 1):
            updated = list(cols_left)
            updated[j] -= value
            walk_cell(i, j + 1, left_in_row - value, updated,
                      log_denominator + log_fact[value])

    walk_row(0, col_tot, 0.0)
    return min(accumulated, 1.0)


def _cramers_v(x2, n, table_shape):
    """Always reported, and always from the UNCORRECTED chi-square statistic —
    including in the Fisher branch, where that statistic is computed on the same
    table purely to feed this effect size even though its p-value was
    discarded."""
    value = math.sqrt(x2 / (n * (min(table_shape) - 1)))
    return {"label": "Cramér's V", "value": value, "lo": None, "hi": None}


def _compare_categorical(frame, n_dropped):
    outcome_levels = sorted(set(frame["outcome"]))
    group_levels = sorted(set(frame["group"]))
    if len(group_levels) < 2:
        raise ValueError(
            "group comparison requires at least two distinct group values; "
            f"got {len(group_levels)}")

    counts = {(o, g): 0 for o in outcome_levels for g in group_levels}
    for o, g in zip(frame["outcome"], frame["group"]):
        counts[(o, g)] += 1
    table = np.array([[counts[(o, g)] for g in group_levels]
                      for o in outcome_levels], dtype=np.int64)
    n = int(table.sum())

    x2, chi_p, expected = _chi_square(table)

    # Strictly less than 5 on ANY single cell — not "20% of cells", not "<= 5".
    if float(expected.min()) < 5:
        test_name = FISHER
        p_value = _fisher_rxc(table)
        statistic = None            # structurally none; never the chi-square
    else:
        test_name = CHI_SQUARE
        p_value = chi_p
        statistic = x2

    return {
        "test_name": test_name,
        "p_value": p_value,
        "statistic": statistic,
        "effect": _cramers_v(x2, n, table.shape),
        "n_per_group": {g: int(table[:, j].sum())
                        for j, g in enumerate(group_levels)},
        "n": n,
        "n_dropped": int(n_dropped),
        # The app performs no pairwise follow-up after a categorical
        # comparison, at any table size and any p-value.
        "posthoc": None,
    }


# ---------------------------------------------------------------------------
# Numeric branch
# ---------------------------------------------------------------------------

def _compare_numeric(frame, n_na, nonparametric):
    values = np.array([_r_numeric(t) for t in frame["outcome"]], dtype=float)
    groups = list(frame["group"])

    # Any group left with fewer than two remaining values is dropped entirely,
    # along with all of its rows — and only AFTER the missing-value filter. The
    # dropped group disappears from n_per_group; it is not reported with a
    # count of 0 or 1.
    by_group = {}
    for value, level in zip(values, groups):
        by_group.setdefault(level, []).append(value)
    n_small = sum(len(v) for v in by_group.values() if len(v) < 2)
    values_by_group = {level: np.array(by_group[level], dtype=float)
                       for level in sorted(by_group)
                       if len(by_group[level]) >= 2}

    k = len(values_by_group)
    if k < 2:
        raise ValueError(
            f"group comparison requires at least two surviving groups; got {k}")

    n = int(sum(v.size for v in values_by_group.values()))

    # Decided once, globally, before any test is selected.
    if nonparametric is None:
        use_nonparametric = _route(values_by_group)
    else:
        use_nonparametric = bool(nonparametric)

    levels = list(values_by_group)
    posthoc = None

    if k == 2:
        x1, x2 = values_by_group[levels[0]], values_by_group[levels[1]]
        if use_nonparametric:
            test_name = MANN_WHITNEY
            statistic, p_value = _mann_whitney(x1, x2)
            effect = _rank_biserial(statistic, x1.size, x2.size)
        else:
            test_name = WELCH_T
            statistic, p_value = _welch_t(x1, x2)
            effect = _cohens_d(x1, x2)
    elif use_nonparametric:
        test_name = KRUSKAL_WALLIS
        statistic, p_value = _kruskal_wallis(values_by_group)
        effect = _epsilon_squared(statistic, n)
        if p_value < 0.05:
            posthoc = _dunn_pairs(values_by_group)
    else:
        test_name = WELCH_ANOVA
        statistic, p_value, _df1, _df2 = _welch_oneway(values_by_group)
        ss_b, ss_r, f_value, a_df1, a_df2 = _classical_anova(values_by_group)
        effect = _eta_squared(ss_b, ss_r, f_value, a_df1, a_df2)
        if p_value < 0.05:
            posthoc = _tukey_pairs(values_by_group, ss_r, a_df2)

    return {
        "test_name": test_name,
        "p_value": p_value,
        "statistic": statistic,
        "effect": effect,
        "n_per_group": {level: int(values_by_group[level].size)
                        for level in levels},
        "n": n,
        "n_dropped": int(n_na + n_small),
        "posthoc": posthoc,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def compare_groups(df, outcome, group, nonparametric=None):
    """Compare `outcome` across `group`, per the groupcompare specs.

    `nonparametric` is the routing override: None runs the spec's rule,
    True/False force the branch. It is ignored entirely in the categorical
    branch, which has no such routing decision.
    """
    frame = _mapped_frame(df, outcome, group)

    # Which branch runs is decided by the outcome column's contents. The test is
    # on the raw text after trimming, over the WHOLE column, before any row is
    # dropped: one non-parsing cell anywhere flips the entire analysis.
    numeric_outcome = _is_numeric_outcome(frame["outcome"])

    kept, n_dropped = complete_cases(frame, ["outcome", "group"])
    kept = kept.reset_index(drop=True)

    if numeric_outcome:
        return _compare_numeric(kept, n_dropped, nonparametric)
    return _compare_categorical(kept, n_dropped)

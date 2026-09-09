"""Path B: independent linear-regression implementation.

Written from ``stats-validation/spec/linear-confounding.md`` alone. Every
interpretation choice is recorded in ``DECISIONS-linear.md``.

Nothing here is rounded: the module reports floats at full precision and
leaves rendering to its caller.
"""

import math

import numpy as np
import pandas as pd
from scipy.stats import chi2, shapiro as _shapiro, t as _t

from validate.io import complete_cases, to_numeric, treatment_dummies

# R's dqrdc2 pivoting tolerance, the rank test lm() itself uses.
_RANK_TOL = 1e-7


# --------------------------------------------------------------------------
# Cell reading
# --------------------------------------------------------------------------

def _trim(value):
    """The app's parser trims every cell before anything else looks at it."""
    if isinstance(value, str):
        return value.strip()
    return value


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    try:
        if value is not None and pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return value == ""


def _parses_numeric(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _as_text(value):
    return value if isinstance(value, str) else str(value)


def _trimmed_column(df, column):
    return df[column].map(_trim)


def _all_non_blank_parse(series):
    """The whole-column numeric rule; blank cells are exempt."""
    for value in series:
        if _is_blank(value):
            continue
        if not _parses_numeric(value):
            return False
    return True


# --------------------------------------------------------------------------
# Level ordering
# --------------------------------------------------------------------------

def _collate_key(level):
    """Emulates R's locale-aware sort() under en_CA.UTF-8.

    Primary key is case-insensitive, secondary key puts lowercase before
    uppercase, which reproduces sort(c("B", "B", "a", "a")) -> a, B. A plain
    code-point sort would give B. See DECISIONS-linear.md.
    """
    text = _as_text(level)
    return (text.casefold(), text.swapcase())


# --------------------------------------------------------------------------
# The increment
# --------------------------------------------------------------------------

def _resolve_reference(values, declared):
    """The declared level when still present, else the most frequent one.

    "Most frequent" is not a total order, so the tie-break is the spec's: sort
    the tabulated levels ascending under R's locale-aware collation, sort that
    table by count descending stably, take the first name. On a tie the level
    that sorts FIRST wins.

    io.py's treatment_dummies carries the same fallback but tie-breaks on a
    code-point sort, which differs from R for mixed-case levels, so the
    reference is resolved here and handed to the helper already decided.
    """
    levels = list(pd.Series(values).unique())
    if declared is not None and declared in levels:
        return declared
    if not levels:
        return declared
    counts = pd.Series(values).value_counts()
    ordered = sorted(counts.index, key=_collate_key)
    return max(ordered, key=lambda level: counts[level])


def _increment(raw):
    """A positive finite number, or 1."""
    if isinstance(raw, bool):
        return 1.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(value) or value <= 0:
        return 1.0
    return value


# --------------------------------------------------------------------------
# Least squares, with R's left-to-right aliasing rule
# --------------------------------------------------------------------------

def _retained_columns(X):
    """Walk the design left to right; drop a column already spanned.

    Returns the indices kept, in order. A column whose residual against the
    columns already retained has shrunk below _RANK_TOL of its own norm is
    aliased, so the LATER member of an exactly collinear pair is the one
    dropped -- exactly as R's pivoting does.
    """
    kept = []
    basis = []  # orthonormal columns spanning what has been retained
    for j in range(X.shape[1]):
        column = X[:, j].astype(float)
        norm = float(np.linalg.norm(column))
        residual = column.copy()
        for q in basis:
            residual = residual - q * float(q @ residual)
        residual_norm = float(np.linalg.norm(residual))
        if norm == 0.0 or residual_norm <= _RANK_TOL * norm:
            continue
        basis.append(residual / residual_norm)
        kept.append(j)
    return kept


def _ols(X, y):
    """An ordinary least-squares fit with an intercept already in X."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n = X.shape[0]
    ncol = X.shape[1]

    kept = _retained_columns(X)
    aliased = [j for j in range(ncol) if j not in kept]
    Xk = X[:, kept]
    p = len(kept)

    beta_kept, *_ = np.linalg.lstsq(Xk, y, rcond=None)
    fitted = Xk @ beta_kept
    resid = y - fitted
    rss = float(resid @ resid)
    df_resid = n - p

    beta = np.full(ncol, np.nan)
    se = np.full(ncol, np.nan)
    lo = np.full(ncol, np.nan)
    hi = np.full(ncol, np.nan)
    pval = np.full(ncol, np.nan)
    hat = np.full(n, np.nan)

    if p > 0:
        Q, R = np.linalg.qr(Xk)
        hat = np.einsum("ij,ij->i", Q, Q)

    if df_resid > 0 and p > 0:
        s2 = rss / df_resid
        Rinv = np.linalg.inv(R)
        cov = s2 * (Rinv @ Rinv.T)
        se_kept = np.sqrt(np.diag(cov))
        crit = float(_t.ppf(0.975, df_resid))
        with np.errstate(divide="ignore", invalid="ignore"):
            tstat = beta_kept / se_kept
        p_kept = 2.0 * _t.sf(np.abs(tstat), df_resid)
        for slot, j in enumerate(kept):
            beta[j] = beta_kept[slot]
            se[j] = se_kept[slot]
            lo[j] = beta_kept[slot] - crit * se_kept[slot]
            hi[j] = beta_kept[slot] + crit * se_kept[slot]
            pval[j] = p_kept[slot]
        s2_value = s2
    else:
        for slot, j in enumerate(kept):
            beta[j] = beta_kept[slot]
        s2_value = float("nan")

    centred = y - y.mean()
    tss = float(centred @ centred)
    if tss > 0:
        r_squared = 1.0 - rss / tss
    else:
        r_squared = float("nan")
    if df_resid > 0 and n > 1 and math.isfinite(r_squared):
        adj_r_squared = 1.0 - (1.0 - r_squared) * (n - 1) / df_resid
    else:
        adj_r_squared = float("nan")

    return {
        "n": n,
        "p": p,
        "df_resid": df_resid,
        "kept": kept,
        "aliased": aliased,
        "beta": beta,
        "se": se,
        "lo": lo,
        "hi": hi,
        "pval": pval,
        "fitted": fitted,
        "resid": resid,
        "rss": rss,
        "s2": s2_value,
        "hat": hat,
        "r_squared": r_squared,
        "adj_r_squared": adj_r_squared,
    }


def _cells(fit, names):
    """The {est, se, lo, hi, p} mapping; an aliased term is present with NaNs."""
    out = {}
    for j, name in enumerate(names):
        out[name] = {
            "est": float(fit["beta"][j]),
            "se": float(fit["se"][j]),
            "lo": float(fit["lo"][j]),
            "hi": float(fit["hi"][j]),
            "p": float(fit["pval"][j]),
        }
    return out


def reportable(cell):
    """A cell carries usable information when est and both bounds are finite."""
    return all(
        isinstance(cell.get(key), (int, float)) and math.isfinite(float(cell[key]))
        for key in ("est", "lo", "hi")
    )


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------

def _r_squared_of(X, y):
    fit = _ols(X, y)
    return fit["r_squared"]


def _shapiro_p(resid):
    n = len(resid)
    if n < 3 or n > 5000:
        return None
    try:
        stat = _shapiro(np.asarray(resid, dtype=float))
    except Exception:
        return None
    value = float(stat.pvalue)
    if not math.isfinite(value):
        return None
    return value


def _breusch_pagan_p(resid, fitted):
    n = len(resid)
    e2 = np.asarray(resid, dtype=float) ** 2
    X = np.column_stack([np.ones(n), np.asarray(fitted, dtype=float)])
    r2 = _r_squared_of(X, e2)
    if not math.isfinite(r2):
        return float("nan")
    return float(chi2.sf(n * r2, 1))


def _cooks_influential(fit):
    n = fit["n"]
    p = fit["p"]
    s2 = fit["s2"]
    if n == 0 or p == 0 or not math.isfinite(s2) or s2 <= 0:
        return 0
    e = fit["resid"]
    h = fit["hat"]
    with np.errstate(divide="ignore", invalid="ignore"):
        d = (e ** 2 / (p * s2)) * h / (1.0 - h) ** 2
    finite = np.isfinite(d)
    return int(np.sum(finite & (d > 4.0 / n)))


def _vif(continuous_columns):
    """Continuous covariates only; None when there are fewer than two."""
    names = list(continuous_columns)
    if len(names) < 2:
        return None
    n = len(continuous_columns[names[0]])
    out = {}
    for name in names:
        y = np.asarray(continuous_columns[name], dtype=float)
        others = [np.asarray(continuous_columns[o], dtype=float) for o in names if o != name]
        X = np.column_stack([np.ones(n)] + others)
        r2 = _r_squared_of(X, y)
        if not math.isfinite(r2) or r2 >= 1.0:
            out[name] = float("inf")
        else:
            out[name] = 1.0 / (1.0 - r2)
    return out


# --------------------------------------------------------------------------
# The analysis
# --------------------------------------------------------------------------

def fit_linear(df, outcome, covariates, ref_levels, increments):
    ref_levels = ref_levels or {}
    increments = increments or {}
    covariates = list(covariates)

    trimmed = pd.DataFrame(index=df.index)
    for column in [outcome] + covariates:
        trimmed[column] = _trimmed_column(df, column)

    # Whole-column classification, blanks exempt, BEFORE the complete-case
    # filter (the Outcome section's "blank cells are exempt" only makes sense
    # if the check sees rows the filter would later drop).
    if not _all_non_blank_parse(trimmed[outcome]):
        raise ValueError(
            "outcome column %r has a non-blank cell that does not parse as a number" % outcome
        )
    is_continuous = {c: _all_non_blank_parse(trimmed[c]) for c in covariates}

    kept, n_dropped = complete_cases(trimmed, [outcome] + covariates)
    n = len(kept)

    y = to_numeric(kept[outcome]).to_numpy(dtype=float)

    # Design pieces, in the declared covariate order.
    design_columns = []          # (term name, np.ndarray)
    covariate_slices = {}        # covariate -> (start, stop) into design_columns
    continuous_values = {}       # covariate -> rescaled column, for VIF
    level_counts = {}            # covariate -> distinct levels after the filter

    for covariate in covariates:
        start = len(design_columns)
        if is_continuous[covariate]:
            column = to_numeric(kept[covariate]).to_numpy(dtype=float)
            k = _increment(increments.get(covariate, 1))
            if k != 1.0:
                column = column / k
            design_columns.append((covariate, column))
            continuous_values[covariate] = column
        else:
            values = kept[covariate].map(_as_text)
            reference = _resolve_reference(values, ref_levels.get(covariate))
            dummies, reference = treatment_dummies(values, reference)
            levels = sorted(dummies.keys(), key=_collate_key)
            level_counts[covariate] = len(levels) + 1
            for level in levels:
                design_columns.append(
                    (covariate + level, np.asarray(dummies[level], dtype=float))
                )
        covariate_slices[covariate] = (start, len(design_columns))

    intercept = np.ones(n)

    # Joint model.
    joint_names = [name for name, _ in design_columns]
    X_joint = np.column_stack([intercept] + [column for _, column in design_columns])
    joint = _ols(X_joint, y)
    terms = _cells(joint, ["(Intercept)"] + joint_names)
    terms.pop("(Intercept)")

    # Univariable models: one per covariate, flattened into one mapping keyed
    # by the same coefficient names.
    unadjusted = {}
    for covariate in covariates:
        start, stop = covariate_slices[covariate]
        pieces = design_columns[start:stop]
        if not pieces:
            continue
        X_uni = np.column_stack([intercept] + [column for _, column in pieces])
        uni = _ols(X_uni, y)
        cells = _cells(uni, ["(Intercept)"] + [name for name, _ in pieces])
        cells.pop("(Intercept)")
        unadjusted.update(cells)

    # Diagnostics -- all of them describe the joint model.
    terms_count = 0
    for covariate in covariates:
        if is_continuous[covariate]:
            terms_count += 1
        else:
            terms_count += max(level_counts.get(covariate, 1) - 1, 0)

    shapiro_p = _shapiro_p(joint["resid"])
    bp_p = _breusch_pagan_p(joint["resid"], joint["fitted"])
    obs_per_term = (n / terms_count) if terms_count > 0 else float("nan")
    vif = _vif(continuous_values)
    cooks_influential = _cooks_influential(joint)

    diagnostics = {
        "shapiro_p": shapiro_p,
        "shapiro_triggered": shapiro_p is not None and shapiro_p < 0.05,
        "bp_p": bp_p,
        "bp_triggered": math.isfinite(bp_p) and bp_p < 0.05,
        "obs_per_term": float(obs_per_term),
        "obs_per_term_triggered": math.isfinite(obs_per_term) and obs_per_term < 10,
        "vif": vif,
        "vif_triggered": vif is not None and any(v > 5 for v in vif.values()),
        "cooks_influential": cooks_influential,
        "cooks_triggered": cooks_influential > 0,
        "aliased_caution": len(joint["aliased"]) > 0,
    }

    return {
        "terms": terms,
        "unadjusted": unadjusted,
        "n": int(n),
        "n_dropped": int(n_dropped),
        "r_squared": float(joint["r_squared"]),
        "adj_r_squared": float(joint["adj_r_squared"]),
        "diagnostics": diagnostics,
    }

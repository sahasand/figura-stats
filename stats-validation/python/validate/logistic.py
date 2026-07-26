import numpy as np
import pandas as pd
from scipy.stats import rankdata
from statsmodels.genmod.families import Binomial
from statsmodels.genmod.generalized_linear_model import GLM
from statsmodels.tools import add_constant

from .io import code_event, complete_cases, to_numeric, treatment_dummies


# The machine epsilon for a double, spelled out as the spec spells it out.
_EPS = 2.220446049250313e-16


def _is_categorical(cov, ref_levels):
    # A covariate is categorical exactly when the case declares a reference
    # level for it — the same rule _covariate_matrix already codes by, so the
    # diagnostics never disagree with the design matrix about what `arm` is.
    return cov in ref_levels


def _covariate_matrix(df, covariates, ref_levels, increments):
    columns = {}
    for cov in covariates:
        if cov in ref_levels:
            dummies, _ref = treatment_dummies(df[cov], ref_levels[cov])
            for level, indicator in dummies.items():
                columns[f"{cov}{level}"] = indicator.reset_index(drop=True)
        else:
            increment = increments.get(cov, 1)
            numeric = to_numeric(df[cov]).reset_index(drop=True) / increment
            columns[cov] = numeric
    return pd.DataFrame(columns)


def _covariate_groups(df, covariates, ref_levels):
    """Map each covariate to the design-matrix columns it contributes.

    Same column names and same order as `_covariate_matrix` produces, so a
    diagnostic keyed by covariate (Cox's `zph_terms`) can address the right
    block of a matrix indexed by coefficient.
    """
    groups = {}
    for cov in covariates:
        if cov in ref_levels:
            dummies, _ref = treatment_dummies(df[cov], ref_levels[cov])
            groups[cov] = [f"{cov}{level}" for level in dummies]
        else:
            groups[cov] = [cov]
    return groups


def _fit_one(y, X):
    design = add_constant(X, has_constant="add")
    result = GLM(y, design, family=Binomial()).fit()
    terms = {}
    for term in X.columns:
        coef = result.params[term]
        se = result.bse[term]
        terms[term] = {
            "est": np.exp(coef),
            # RAW log-scale standard error, reported alongside the interval it
            # generates. lo/hi are exp(coef +/- 1.96*se) on both paths, so a
            # CI comparison alone is partly tautological once est agrees; se
            # is the primary standard-error evidence, and the harness's
            # figura-exact.json carries R's `Std. Error` for exactly this
            # comparison (stats-validation/harness/run-script.R).
            "se": se,
            "lo": np.exp(coef - 1.96 * se),
            "hi": np.exp(coef + 1.96 * se),
            "p": result.pvalues[term],
        }
    return terms, result, design


def _c_statistic(y, pred):
    y = np.asarray(y)
    pred = np.asarray(pred)
    pos = pred[y == 1]
    neg = pred[y == 0]
    n1, n0 = len(pos), len(neg)
    if n1 == 0 or n0 == 0:
        return None
    # rankdata's default tie rule IS the midrank rule the spec pins: with a
    # single two-level covariate almost every pair is tied, and breaking those
    # ties by position instead of averaging lands somewhere else entirely.
    ranks = rankdata(np.concatenate([pos, neg]))
    sum_ranks_pos = ranks[:n1].sum()
    u = sum_ranks_pos - n1 * (n1 + 1) / 2
    return u / (n1 * n0)


def _r_squared(target, others):
    """Multiple R-squared of an OLS fit of `target` on `others`, intercept in."""
    design = np.column_stack([np.ones(len(target)), others])
    coef, _res, _rank, _sv = np.linalg.lstsq(design, target, rcond=None)
    resid = target - design @ coef
    rss = float(resid @ resid)
    centred = target - target.mean()
    tss = float(centred @ centred)
    if tss == 0:
        return float("nan")
    return 1.0 - rss / tss


def _vif(kept, covariates, ref_levels):
    """1/(1 - R^2_j) per CONTINUOUS covariate; None when fewer than two.

    Categorical covariates take no part at all — not as regressand and not as
    regressor — so collinearity among them is simply not assessed. The
    increment rescaling divides a column by a positive constant and leaves
    R^2 alone, so this reads the unscaled columns and is rescaling-invariant
    by construction rather than by luck.
    """
    continuous = [c for c in covariates if not _is_categorical(c, ref_levels)]
    if len(continuous) < 2:
        return None

    columns = {c: to_numeric(kept[c]).to_numpy(dtype=float) for c in continuous}
    out = {}
    for cov in continuous:
        others = np.column_stack([columns[c] for c in continuous if c != cov])
        r2 = _r_squared(columns[cov], others)
        out[cov] = float("inf") if not np.isfinite(r2) or r2 >= 1 else 1.0 / (1.0 - r2)
    return out


def _cooks_influential(y, mu, design, n_coef):
    """Rows whose Cook's distance exceeds 4/n, non-finite distances excluded."""
    y = np.asarray(y, dtype=float)
    mu = np.asarray(mu, dtype=float)
    X = np.asarray(design, dtype=float)
    n = len(y)

    w = mu * (1.0 - mu)
    with np.errstate(divide="ignore", invalid="ignore"):
        pearson = (y - mu) / np.sqrt(w)

    root_w = np.sqrt(w)
    Xw = X * root_w[:, None]
    xtwx = Xw.T @ Xw
    # Leverage of the final weighted least-squares step: the diagonal of
    # W^(1/2) X (X'WX)^-1 X' W^(1/2). pinv keeps a rank-deficient design from
    # raising instead of producing the hat values it still has.
    hat = np.einsum("ij,jk,ik->i", Xw, np.linalg.pinv(xtwx), Xw)

    with np.errstate(divide="ignore", invalid="ignore"):
        distance = (pearson / (1.0 - hat)) ** 2 * hat / n_coef

    # Dispersion is 1 for the binomial family, so it drops out of D_i above.
    influential = np.isfinite(distance) & (distance > 4.0 / n)
    return int(influential.sum())


def _separation_caution(terms, unadjusted, mu):
    # Clause 1 — an interval that ran away in EITHER column. An unadjusted cell
    # can run away while the adjusted one stays finite, and that cell would
    # otherwise sit in the table with no sentence explaining it.
    for cells in (terms, unadjusted):
        for cell in cells.values():
            if not reportable(cell):
                return True
    # Clause 2 — fitted probabilities numerically 0 or 1, R's glm.fit condition.
    mu = np.asarray(mu, dtype=float)
    if mu.size and bool(np.any(mu > 1 - 10 * _EPS) or np.any(mu < 10 * _EPS)):
        return True
    return False


def fit_logistic(df, outcome, event_value, covariates, ref_levels, increments):
    columns = [outcome] + list(covariates)
    kept, n_dropped = complete_cases(df, columns)
    kept = kept.reset_index(drop=True)

    y = code_event(kept[outcome], event_value)

    X_full = _covariate_matrix(kept, covariates, ref_levels, increments)
    terms, fitted, design = _fit_one(y, X_full)

    unadjusted = {}
    for cov in covariates:
        X_single = _covariate_matrix(kept, [cov], ref_levels, increments)
        single_terms, _result, _design = _fit_one(y, X_single)
        unadjusted.update(single_terms)

    pred = fitted.predict(design)
    c_stat = _c_statistic(y, pred)

    n = len(kept)
    n_event = int(y.sum())

    vif = _vif(kept, covariates, ref_levels)
    # terms = non-intercept coefficients: one per continuous covariate,
    # (levels - 1) per categorical, levels counted after the complete-case
    # filter — which is exactly the joint design matrix's column count.
    n_terms = X_full.shape[1]
    # min(n_event, n - n_event), NOT the event count: an outcome that is mostly
    # events is judged on its rarer class. (Cox's EPV uses the event count;
    # the two are different quantities under one name.)
    epv = min(n_event, n - n_event) / n_terms
    cooks = _cooks_influential(y, pred, design, design.shape[1])

    diagnostics = {
        "c_statistic": c_stat,
        "vif": vif,
        "vif_triggered": vif is not None and any(v > 5 for v in vif.values()),
        "epv": epv,
        "epv_triggered": epv < 10,
        "cooks_influential": cooks,
        "cooks_triggered": cooks > 0,
        "separation_caution": _separation_caution(terms, unadjusted, pred),
    }

    return {
        "terms": terms,
        "unadjusted": unadjusted,
        "n": n,
        "n_event": n_event,
        "n_dropped": n_dropped,
        # Superseded by diagnostics["c_statistic"], kept so an older caller
        # does not break (INTERFACES.md).
        "c_statistic": c_stat,
        "diagnostics": diagnostics,
    }


def reportable(cell):
    est, lo, hi = cell["est"], cell["lo"], cell["hi"]
    if not (np.isfinite(est) and np.isfinite(lo) and np.isfinite(hi)):
        return False
    return lo >= 1e-6 and hi <= 1e6

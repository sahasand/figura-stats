import numpy as np
import pandas as pd
from scipy.stats import rankdata
from statsmodels.genmod.families import Binomial
from statsmodels.genmod.generalized_linear_model import GLM
from statsmodels.tools import add_constant

from .io import code_event, complete_cases, to_numeric, treatment_dummies


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


def _fit_one(y, X):
    design = add_constant(X, has_constant="add")
    result = GLM(y, design, family=Binomial()).fit()
    terms = {}
    for term in X.columns:
        coef = result.params[term]
        se = result.bse[term]
        terms[term] = {
            "est": np.exp(coef),
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
    ranks = rankdata(np.concatenate([pos, neg]))
    sum_ranks_pos = ranks[:n1].sum()
    u = sum_ranks_pos - n1 * (n1 + 1) / 2
    return u / (n1 * n0)


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

    return {
        "terms": terms,
        "unadjusted": unadjusted,
        "n": len(kept),
        "n_event": int(y.sum()),
        "n_dropped": n_dropped,
        "c_statistic": c_stat,
    }


def reportable(cell):
    est, lo, hi = cell["est"], cell["lo"], cell["hi"]
    if not (np.isfinite(est) and np.isfinite(lo) and np.isfinite(hi)):
        return False
    return lo >= 1e-6 and hi <= 1e6

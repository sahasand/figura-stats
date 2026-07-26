import math

from lifelines import CoxPHFitter
from scipy.stats import norm

from .io import code_event, complete_cases, to_numeric
from .logistic import _covariate_matrix

# Converge well past lifelines' defaults (precision=1e-7, r_precision=1e-9,
# max_steps=500) so the Newton-Raphson stopping tolerance doesn't leak into
# the reported estimates. See INTERFACES.md's Numerical precision note.
_FIT_OPTIONS = {"precision": 1e-11, "r_precision": 1e-13, "max_steps": 1000}

_DURATION_COL = "__time__"
_EVENT_COL = "__event__"


def _population(df, time, covariates):
    columns = [time] + list(covariates)
    kept, n_dropped_blank = complete_cases(df, columns)
    kept = kept.reset_index(drop=True)

    time_numeric = to_numeric(kept[time])
    time_ok = time_numeric.notna() & (time_numeric >= 0)
    n_dropped_time = int((~time_ok).sum())

    kept = kept[time_ok].reset_index(drop=True)
    time_numeric = time_numeric[time_ok].reset_index(drop=True)

    return kept, time_numeric, n_dropped_blank + n_dropped_time


def _fit_one(time_numeric, event, X):
    frame = X.copy()
    frame[_DURATION_COL] = time_numeric.values
    frame[_EVENT_COL] = event.values

    cph = CoxPHFitter()
    cph.fit(frame, duration_col=_DURATION_COL, event_col=_EVENT_COL, fit_options=_FIT_OPTIONS)

    terms = {}
    for term in X.columns:
        coef = cph.params_[term]
        se = cph.standard_errors_[term]
        z = coef / se
        p = 2 * norm.sf(abs(z))
        terms[term] = {
            "est": math.exp(coef),
            "se": se,
            "lo": math.exp(coef - 1.96 * se),
            "hi": math.exp(coef + 1.96 * se),
            "p": p,
        }
    return terms


def fit_cox(df, time, status, event_value, covariates, ref_levels, increments=None):
    increments = increments or {}

    kept, time_numeric, n_dropped = _population(df, time, covariates)
    event = code_event(kept[status], event_value)

    X_full = _covariate_matrix(kept, covariates, ref_levels, increments)
    terms = _fit_one(time_numeric, event, X_full)

    unadjusted = {}
    for cov in covariates:
        X_single = _covariate_matrix(kept, [cov], ref_levels, increments)
        unadjusted.update(_fit_one(time_numeric, event, X_single))

    return {
        "terms": terms,
        "unadjusted": unadjusted,
        "n": len(kept),
        "n_event": int(event.sum()),
        "n_dropped": n_dropped,
    }

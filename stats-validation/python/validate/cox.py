import math

import numpy as np
from lifelines import CoxPHFitter
from scipy.stats import chi2, norm

from .io import code_event, complete_cases, to_numeric
from .logistic import _covariate_groups, _covariate_matrix, reportable

# Converge well past lifelines' defaults (precision=1e-7, r_precision=1e-9,
# max_steps=500) so the Newton-Raphson stopping tolerance doesn't leak into
# the reported estimates. See INTERFACES.md's Numerical precision note, and
# DECISIONS-diagnostics.md for what each digit here is measured to buy:
# briefly, the previous 1e-11/1e-13/1000 already bought the tied-times fixture
# ~3 orders of magnitude on beta-hat, and these three extra digits buy the PH
# score test a further 5 (global-p residual 4.0e-8 -> 2.9e-13 relative to R) at
# no measurable runtime cost (~7 ms per joint fit either way, 20-fit mean).
_FIT_OPTIONS = {"precision": 1e-15, "r_precision": 1e-17, "max_steps": 5000}

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


def _km_time_transform(time, event):
    """`g(t) = 1 - S(t-)` at each distinct event time, centred on event rows.

    `S` is the Kaplan-Meier survivor function of the observed times over the
    WHOLE sample, no covariates and no strata, evaluated LEFT-CONTINUOUSLY:
    `S(t-) = 1` at or before the first event time, so `g` starts at 0. This is
    R `cox.zph`'s `transform = "km"` default, and it is part of the spec — not
    something to be swapped for whatever a library happens to default to
    (lifelines defaults to `"rank"`).

    Returns the sorted distinct event times and the centred `g` beside them.
    """
    event_times = np.unique(time[event == 1])
    if event_times.size == 0:
        return event_times, np.zeros(0)

    d = np.array([np.sum((time == t) & (event == 1)) for t in event_times], dtype=float)
    at_risk = np.array([np.sum(time >= t) for t in event_times], dtype=float)

    surv = np.cumprod(1.0 - d / at_risk)
    # Shift by one: the survivor value just BEFORE each event time.
    surv_before = np.concatenate([[1.0], surv[:-1]])
    g = 1.0 - surv_before

    # Centre over the EVENT ROWS, so a time with d tied events counts d times.
    return event_times, g - float(np.sum(d * g) / np.sum(d))


def _zph(X, time, event, beta, groups):
    """Scaled-Schoenfeld score test of `theta = 0` in the extended model
    `lambda(t|x) = lambda0(t) exp(x'beta + g(t) x'theta)`.

    Evaluated at the fitted `beta` with `theta = 0`, so nothing is refitted.
    This is the modern (survival 3.x) `cox.zph` score test, NOT the older
    residual-versus-time correlation test some libraries still ship under the
    same name. Risk sets use the same Efron construction the model was fitted
    with.

    `X` must be the design-matrix DATAFRAME, not a bare array: the per-covariate
    statistic needs to know which of its columns belong to which covariate, and
    that is resolved by NAME below rather than by assuming a layout.

    Returns `(global_p, {covariate: p})`.
    """
    # Column positions come from the frame's own index, so the per-term block
    # below can never be silently off by one. The alternative — walking `groups`
    # and accumulating widths — is correct only while `_covariate_matrix` and
    # `_covariate_groups` emit blocks in the same order, an invariant no code
    # enforces and a comment cannot.
    positions = {name: X.columns.get_loc(name) for name in X.columns}
    X = np.asarray(X, dtype=float)
    p = X.shape[1]
    risk = np.exp(X @ beta)

    event_times, g = _km_time_transform(time, event)

    U = np.zeros(p)
    i_bb = np.zeros((p, p))
    i_bt = np.zeros((p, p))
    i_tt = np.zeros((p, p))

    for gt, t in zip(g, event_times):
        in_risk = time >= t
        died = in_risk & (time == t) & (event == 1)
        d = int(died.sum())

        Xr, wr = X[in_risk], risk[in_risk]
        Xd, wd = X[died], risk[died]
        s0_r, s1_r = wr.sum(), wr @ Xr
        s2_r = Xr.T @ (Xr * wr[:, None])
        s0_d, s1_d = wd.sum(), wd @ Xd
        s2_d = Xd.T @ (Xd * wd[:, None])

        # Efron: the k-th sub-term gives each of the d tied rows weight 1-k/d.
        v_t = np.zeros((p, p))
        xbar_total = np.zeros(p)
        for k in range(d):
            frac = k / d
            s0 = s0_r - frac * s0_d
            s1 = s1_r - frac * s1_d
            s2 = s2_r - frac * s2_d
            xbar = s1 / s0
            v_t += s2 / s0 - np.outer(xbar, xbar)
            xbar_total += xbar

        U += gt * (Xd.sum(axis=0) - xbar_total)
        i_bb += v_t
        i_bt += gt * v_t
        i_tt += gt * gt * v_t

    # The score for beta is zero at the fit, so the test reduces to the Schur
    # complement of the extended model's information.
    S = i_tt - i_bt.T @ np.linalg.solve(i_bb, i_bt)

    global_chisq = float(U @ np.linalg.solve(S, U))
    global_p = float(chi2.sf(global_chisq, p))

    offsets = {}
    for cov, names in groups.items():
        missing = [name for name in names if name not in positions]
        if missing:
            # A covariate whose columns are not in the design at all is a
            # wiring error between _covariate_matrix and _covariate_groups, not
            # a statistical result. Raise rather than test a wrong submatrix:
            # fit_cox's own except clause turns a ValueError into
            # `zph_global_p = None`, the honest "could not be computed".
            raise ValueError(
                f"covariate {cov!r} names design columns absent from the "
                f"design matrix: {missing}")
        offsets[cov] = [positions[name] for name in names]

    per_term = {}
    for cov, index in offsets.items():
        if not index:
            continue
        idx = np.array(index)
        # S_jj is the SUBMATRIX of S on this covariate's columns — NOT the
        # corresponding block of S inverse. Inverting the wrong piece gives a
        # chi-square that is wildly wrong, not merely imprecise.
        s_jj = S[np.ix_(idx, idx)]
        u_j = U[idx]
        chisq = float(u_j @ np.linalg.solve(s_jj, u_j))
        per_term[cov] = float(chi2.sf(chisq, len(idx)))

    return global_p, per_term


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
    return terms, cph


def fit_cox(df, time, status, event_value, covariates, ref_levels, increments=None):
    increments = increments or {}

    kept, time_numeric, n_dropped = _population(df, time, covariates)
    event = code_event(kept[status], event_value)

    X_full = _covariate_matrix(kept, covariates, ref_levels, increments)
    terms, joint = _fit_one(time_numeric, event, X_full)

    unadjusted = {}
    for cov in covariates:
        X_single = _covariate_matrix(kept, [cov], ref_levels, increments)
        single_terms, _fit = _fit_one(time_numeric, event, X_single)
        unadjusted.update(single_terms)

    n_event = int(event.sum())

    beta = joint.params_[list(X_full.columns)].to_numpy(dtype=float)
    groups = _covariate_groups(kept, covariates, ref_levels)
    try:
        zph_global_p, zph_terms = _zph(
            X_full,
            time_numeric.to_numpy(dtype=float),
            event.to_numpy(dtype=float),
            beta,
            groups,
        )
    except (np.linalg.LinAlgError, ValueError, ZeroDivisionError):
        # The app wraps the test and prints nothing when it cannot be computed.
        zph_global_p, zph_terms = None, {}

    # The EVENT count, not logistic's min(n_event, n - n_event): Cox
    # regression's information comes from events alone.
    epv = n_event / X_full.shape[1]

    diagnostics = {
        "zph_global_p": zph_global_p,
        "zph_terms": zph_terms,
        "ph_violation": zph_global_p is not None and zph_global_p < 0.05,
        "epv": epv,
        "epv_triggered": epv < 10,
        # Both columns are inspected: an unadjusted cell can run away while the
        # adjusted one stays inside the bound, and the reverse happens too.
        "separation_caution": any(
            not reportable(cell)
            for cells in (terms, unadjusted)
            for cell in cells.values()
        ),
    }

    return {
        "terms": terms,
        "unadjusted": unadjusted,
        "n": len(kept),
        "n_event": n_event,
        "n_dropped": n_dropped,
        "diagnostics": diagnostics,
    }

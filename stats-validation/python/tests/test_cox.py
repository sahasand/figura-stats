import math

import numpy as np
import pandas as pd
import pytest
from validate.cox import _fit_one, _population, _zph, fit_cox
from validate.io import code_event
from validate.logistic import _covariate_matrix


def _frame(seed=11, n=400, log_hr=0.7):
    rng = np.random.default_rng(seed)
    arm = rng.choice(["Control", "Treated"], size=n)
    x = (arm == "Treated").astype(float)
    scale = np.exp(-log_hr * x)
    t_event = rng.exponential(scale=scale)
    t_cens = rng.exponential(scale=1.5, size=n)
    time = np.minimum(t_event, t_cens)
    status = (t_event <= t_cens).astype(int)
    return pd.DataFrame({"time": time, "status": status.astype(str), "arm": arm})


def test_recovers_a_known_hazard_ratio():
    out = fit_cox(_frame(), "time", "status", "1", ["arm"], {"arm": "Control"})
    t = out["terms"]["armTreated"]
    assert 1.6 < t["est"] < 2.4  # true HR = exp(0.7) = 2.01
    # cells carry a log-scale standard error alongside est/lo/hi/p (INTERFACES.md)
    assert t["se"] > 0


def test_ci_is_symmetric_on_the_log_scale():
    out = fit_cox(_frame(), "time", "status", "1", ["arm"], {"arm": "Control"})
    t = out["terms"]["armTreated"]
    lo, hi, est = np.log(t["lo"]), np.log(t["hi"]), np.log(t["est"])
    assert abs((est - lo) - (hi - est)) < 1e-12


def test_event_count_matches_the_status_column():
    df = _frame()
    out = fit_cox(df, "time", "status", "1", ["arm"], {"arm": "Control"})
    assert out["n_event"] == int((df["status"] == "1").sum())


def test_n_dropped_counts_a_blank_covariate_cell():
    df = _frame()
    df.loc[0, "arm"] = ""
    out = fit_cox(df, "time", "status", "1", ["arm"], {"arm": "Control"})
    assert out["n_dropped"] == 1
    assert out["n"] == len(df) - 1


# ---------------------------------------------------------------------------
# D13: tied event times, checked against R's survival::coxph (Efron ties,
# its default) at full precision. 40 rows, integer times drawn from a small
# range so the model must actually resolve heavy ties, two arms of 20.
#
# Precomputed once with:
#
#   Rscript -e '
#   set.seed(42)
#   n <- 40
#   arm <- rep(c("A","B"), each = n/2)
#   time <- sample(1:8, n, replace = TRUE)
#   status <- rbinom(n, 1, 0.7)
#   cat("time <- c(", paste(time, collapse=", "), ")\n")
#   cat("status <- c(", paste(status, collapse=", "), ")\n")
#   '
#
# then, with that generated data:
#
#   Rscript -e '
#   library(survival)
#   time <- c(<as printed above>); status <- c(<as printed above>)
#   arm <- c(rep("A", 20), rep("B", 20))
#   fit <- coxph(Surv(time, status) ~ arm, data.frame(time, status, arm),
#                ties = "efron")
#   sm <- summary(fit)$coefficients
#   sprintf("%.17g", sm["armB", c("coef", "se(coef)", "Pr(>|z|)")])
#   '
#
# -> coef = -0.0048465162299981494, se(coef) = 0.37209859334202033,
#    Pr(>|z|) = 0.98960799312353342 (survival 3.x; ties="efron" is coxph's
#    default and the spec's requirement). HR/CI below are exp(coef) and
#    exp(coef +/- 1.96*se) — the spec's literal-1.96 rule, not confint()'s
#    exact normal quantile.
#
# Tolerance is rel 1e-6 — the same REL_TOL compare.py's exact tier enforces
# (binding requirement) — not a looser one. Verified empirically on this
# exact fixture with a throwaway lifelines.CoxPHFitter:
#   - DEFAULT solver settings: only ~1e-5 relative from R's optimum on
#     est/lo/hi/p (se lands ~2e-7), purely from Newton-Raphson
#     stopping-tolerance differences between implementations — not a
#     modelling error, but it WOULD fail rel 1e-6 here.
#   - Tightly converged (fit_options={"precision": 1e-11,
#     "r_precision": 1e-13, "max_steps": 1000}): every one of
#     coef/se/p/est/lo/hi lands within rel 2.5e-12 to 5.4e-10 of R — three
#     to nine orders of magnitude inside rel 1e-6. No quantity needs an
#     exemption; the tolerance below is fully achievable when the
#     implementation converges as INTERFACES.md's numerical-precision note
#     requires. A WRONG tie method (Breslow instead of Efron) misses by
#     roughly 0.5% on this fixture — ~5000x outside this tolerance — so the
#     test still catches a real defect, and now also catches an
#     under-converged solver, which is the point: rel 1e-6 forces the
#     clean-room implementer to converge well past their library's
#     defaults, exactly as INTERFACES.md warns them to.
_TIED_TIME = [1, 5, 1, 1, 2, 4, 2, 2, 1, 8, 7, 8, 7, 4, 1, 5, 6, 4, 2, 2,
              7, 3, 1, 1, 3, 4, 5, 7, 5, 5, 4, 2, 4, 8, 3, 2, 1, 2, 8, 6]
_TIED_STATUS = [1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1,
                1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1]
_TIED_ARM = ["A"] * 20 + ["B"] * 20

_R_COEF = -0.0048465162299981494
_R_SE = 0.37209859334202033
_R_P = 0.98960799312353342
_R_EST = math.exp(_R_COEF)
_R_LO = math.exp(_R_COEF - 1.96 * _R_SE)
_R_HI = math.exp(_R_COEF + 1.96 * _R_SE)


def _tied_frame():
    return pd.DataFrame({
        "time": _TIED_TIME,
        "status": [str(s) for s in _TIED_STATUS],
        "arm": _TIED_ARM,
    })


def test_tied_times_match_r_efron_at_full_precision():
    out = fit_cox(_tied_frame(), "time", "status", "1", ["arm"], {"arm": "A"})
    t = out["terms"]["armB"]
    assert math.isclose(t["est"], _R_EST, rel_tol=1e-6)
    assert math.isclose(t["se"], _R_SE, rel_tol=1e-6)
    assert math.isclose(t["p"], _R_P, rel_tol=1e-6)
    assert math.isclose(t["lo"], _R_LO, rel_tol=1e-6)
    assert math.isclose(t["hi"], _R_HI, rel_tol=1e-6)
    assert out["n"] == 40
    assert out["n_event"] == 29


# ---------------------------------------------------------------------------
# A14: the advisory DIAGNOSTICS block.
#
# Red until the clean-room round adds `diagnostics` to fit_cox's return, which
# is the designed state: the contract is published (INTERFACES.md) and the test
# is specified (spec/cox-adjusted.md's Diagnostics section, which writes the
# score statistic out in full) before it is implemented.
#
# THE PROPORTIONAL-HAZARDS TEST IS NOT A LIBRARY DEFAULT, and this fixture is
# built to catch exactly that. It is 50 rows with integer times drawn from 1..9,
# so ties are everywhere and the Efron risk-set construction the spec pins is
# doing real work; and `arm` genuinely violates proportional hazards (its p is
# 0.013), so a wrong transform or a wrong test does not merely shift a digit —
# it can flip `ph_violation`.
#
# Two known ways to fail it, both worth stating because both are one-liners in a
# library: lifelines' `proportional_hazard_test` defaults to
# `time_transform="rank"`, not the `km` transform R defaults to and the spec
# pins; and it implements the OLDER correlation form of the test rather than the
# score test on the extended time-varying model. Neither reproduces the numbers
# below.
#
# Precomputed once with:
#
#   Rscript -e '
#   library(survival)
#   set.seed(202); n <- 50
#   arm <- rep(c("Control","Treated"), each = n/2)
#   age <- round(rnorm(n, 62, 8), 1)
#   time <- sample(1:9, n, replace = TRUE)
#   status <- rbinom(n, 1, 0.6)
#   d <- data.frame(time, status, arm = relevel(factor(arm), ref = "Control"), age)
#   f <- coxph(Surv(time, status) ~ arm + age, data = d)
#   z <- cox.zph(f)          # transform = "km" is the default; verified in args()
#   sprintf("%.17g", z$table[, "p"])
#   '
#
# -> arm 0.013236251207516418, age 0.20463625578319466,
#    GLOBAL 0.02750379169749223  (survival 3.x). 31 events over 2 coefficients,
#    so EPV is 15.5 and its note does NOT fire; the logistic suite pins the
#    triggered side of the same threshold.
# ---------------------------------------------------------------------------

_ZPH_TIME = [8, 6, 1, 3, 2, 6, 3, 9, 2, 3, 9, 4, 4, 8, 5, 1, 2, 5, 4, 2,
             5, 8, 9, 3, 1, 9, 4, 3, 7, 7, 2, 3, 4, 9, 8, 1, 8, 3, 3, 4,
             7, 8, 9, 8, 6, 5, 8, 8, 8, 9]
_ZPH_STATUS = [1, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1,
               1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 0, 1, 0, 0,
               1, 0, 1, 1, 0, 1, 1, 1, 1, 1]
_ZPH_ARM = ["Control"] * 25 + ["Treated"] * 25
_ZPH_AGE = [52.9, 58.5, 59.3, 55.2, 60.8, 50.6, 55.8, 46.5, 64.5, 65.7, 60.9,
            71.4, 55.8, 61.1, 75.4, 59.9, 77.8, 57.5, 69.7, 73.6, 64.7, 69,
            69.2, 68, 64.9, 64, 66.6, 65.3, 56.7, 84, 76.1, 69.5, 55.7, 50.7,
            59.1, 66, 55.1, 66.1, 48, 56.1, 76.7, 66.8, 61.1, 66.1, 70.7,
            64.7, 76.8, 53, 64, 56.7]

_R_ZPH_ARM = 0.013236251207516418
_R_ZPH_AGE = 0.20463625578319466
_R_ZPH_GLOBAL = 0.02750379169749223
_R_ZPH_EPV = 15.5


def _zph_frame():
    return pd.DataFrame({
        "time": _ZPH_TIME,
        "status": [str(s) for s in _ZPH_STATUS],
        "arm": _ZPH_ARM,
        "age": _ZPH_AGE,
    })


def _zph_fit():
    return fit_cox(_zph_frame(), "time", "status", "1", ["arm", "age"],
                   {"arm": "Control"})


def test_diagnostics_block_is_present_with_every_contract_key():
    d = _zph_fit()["diagnostics"]
    for key in ("zph_global_p", "zph_terms", "ph_violation", "epv",
                "epv_triggered", "separation_caution"):
        assert key in d, key


def test_zph_global_p_matches_r_with_the_km_transform():
    d = _zph_fit()["diagnostics"]
    assert math.isclose(d["zph_global_p"], _R_ZPH_GLOBAL, rel_tol=1e-6)


def test_zph_per_covariate_p_matches_r():
    d = _zph_fit()["diagnostics"]
    # Keyed by COVARIATE, never by coefficient level: `arm`, not `armTreated`.
    assert set(d["zph_terms"]) == {"arm", "age"}
    assert math.isclose(d["zph_terms"]["arm"], _R_ZPH_ARM, rel_tol=1e-6)
    assert math.isclose(d["zph_terms"]["age"], _R_ZPH_AGE, rel_tol=1e-6)


def test_ph_violation_follows_the_global_p():
    d = _zph_fit()["diagnostics"]
    assert d["ph_violation"] is True          # global p = 0.0275 < 0.05


def test_cox_epv_counts_events_not_the_smaller_outcome_group():
    d = _zph_fit()["diagnostics"]
    assert math.isclose(d["epv"], _R_ZPH_EPV, rel_tol=1e-9)
    assert d["epv_triggered"] is False


def test_separation_caution_is_false_on_a_clean_fit():
    assert _zph_fit()["diagnostics"]["separation_caution"] is False


def test_zph_resolves_a_covariates_columns_by_name_not_by_position():
    """`zph_terms` is keyed by covariate while `U`/`S` are indexed by
    coefficient, so `_zph` has to map one to the other. It must do that by
    COLUMN NAME: walking `groups` and accumulating widths is correct only while
    `_covariate_matrix` and `_covariate_groups` happen to emit blocks in the
    same order, which is an invariant no code enforces.

    Handing `_zph` a `groups` dict whose insertion order is the REVERSE of the
    design's column order is exactly that mismatch. Position-based offsets would
    give `age` the `armTreated` column and vice versa — and because the two
    per-term p-values here differ by 15x, the swap shows up as a wrong number
    rather than as a wash."""
    df = _zph_frame()
    kept, time_numeric, _dropped = _population(df, "time", ["arm", "age"])
    event = code_event(kept["status"], "1")
    X = _covariate_matrix(kept, ["arm", "age"], {"arm": "Control"}, {})
    assert list(X.columns) == ["armTreated", "age"]
    terms, cph = _fit_one(time_numeric, event, X)
    beta = cph.params_[list(X.columns)].to_numpy(dtype=float)

    reversed_groups = {"age": ["age"], "arm": ["armTreated"]}
    global_p, per_term = _zph(
        X, time_numeric.to_numpy(dtype=float),
        event.to_numpy(dtype=float), beta, reversed_groups)
    assert math.isclose(global_p, _R_ZPH_GLOBAL, rel_tol=1e-6)
    assert math.isclose(per_term["arm"], _R_ZPH_ARM, rel_tol=1e-6)
    assert math.isclose(per_term["age"], _R_ZPH_AGE, rel_tol=1e-6)


def test_zph_raises_rather_than_testing_a_wrong_submatrix():
    """A covariate naming a column the design does not have is a wiring error,
    not a statistical result. `_zph` raises; `fit_cox`'s own except clause turns
    that into `zph_global_p = None`, the honest "could not be computed", instead
    of silently testing whatever columns happened to line up."""
    df = _zph_frame()
    kept, time_numeric, _dropped = _population(df, "time", ["arm", "age"])
    event = code_event(kept["status"], "1")
    X = _covariate_matrix(kept, ["arm", "age"], {"arm": "Control"}, {})
    terms, cph = _fit_one(time_numeric, event, X)
    beta = cph.params_[list(X.columns)].to_numpy(dtype=float)
    with pytest.raises(ValueError) as excinfo:
        _zph(X, time_numeric.to_numpy(dtype=float),
             event.to_numpy(dtype=float), beta,
             {"arm": ["armTreated"], "bmi": ["bmi"]})
    assert "bmi" in str(excinfo.value)

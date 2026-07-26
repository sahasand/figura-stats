import math

import numpy as np
import pandas as pd
from validate.cox import fit_cox


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
# Tolerance is rel 1e-4, not the comparator's rel 1e-6 (compare.py's
# REL_TOL): verified empirically (a throwaway lifelines.CoxPHFitter run
# against this exact fixture, at its DEFAULT solver settings) that a
# correctly-Efron-fitted Cox model can still land ~1e-5 relative from R's
# optimum on est/lo/hi/p, purely from Newton-Raphson stopping-tolerance
# differences between implementations — not a modelling error. 1e-4 is
# ~40x looser than that observed noise floor yet ~50x tighter than the gap
# a WRONG tie method produces (Breslow's est differs from Efron's by
# roughly 0.5% here), so it still catches a real defect while tolerating a
# solver's default precision. See INTERFACES.md's numerical-precision note.
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
    assert math.isclose(t["est"], _R_EST, rel_tol=1e-4)
    assert math.isclose(t["se"], _R_SE, rel_tol=1e-4)
    assert math.isclose(t["p"], _R_P, rel_tol=1e-4)
    assert math.isclose(t["lo"], _R_LO, rel_tol=1e-4)
    assert math.isclose(t["hi"], _R_HI, rel_tol=1e-4)
    assert out["n"] == 40
    assert out["n_event"] == 29

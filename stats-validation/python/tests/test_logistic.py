import math

import numpy as np
import pandas as pd
from validate.logistic import _c_statistic, fit_logistic, reportable


def _frame(seed=7, n=400):
    rng = np.random.default_rng(seed)
    stage = rng.choice(["I", "II"], size=n)
    x = (stage == "II").astype(float)
    logit = -1.0 + 1.2 * x
    y = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    return pd.DataFrame(
        {"resp": np.where(y == 1, "Yes", "No"), "stage": stage}
    )


def test_recovers_a_known_odds_ratio():
    df = _frame()
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    est = out["terms"]["stageII"]["est"]
    assert 2.4 < est < 4.4  # true OR = exp(1.2) = 3.32


def test_ci_uses_the_literal_1_96():
    df = _frame()
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    t = out["terms"]["stageII"]
    # log-CI must be symmetric about the log estimate to machine precision
    lo, hi, est = np.log(t["lo"]), np.log(t["hi"]), np.log(t["est"])
    assert abs((est - lo) - (hi - est)) < 1e-12


def test_increment_rescales_the_odds_ratio():
    rng = np.random.default_rng(3)
    age = rng.normal(60, 10, 500)
    y = rng.binomial(1, 1 / (1 + np.exp(-(-6 + 0.1 * age))))
    df = pd.DataFrame({"resp": np.where(y == 1, "Yes", "No"), "age": age})
    per1 = fit_logistic(df, "resp", "Yes", ["age"], {}, {})
    per10 = fit_logistic(df, "resp", "Yes", ["age"], {}, {"age": 10})
    assert abs(np.log(per10["terms"]["age"]["est"])
               - 10 * np.log(per1["terms"]["age"]["est"])) < 1e-9
    # the p-value is invariant to rescaling
    assert abs(per10["terms"]["age"]["p"] - per1["terms"]["age"]["p"]) < 1e-9


def test_counts_are_reported():
    df = _frame()
    df.loc[0, "stage"] = ""
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    assert out["n_dropped"] == 1
    assert out["n"] == len(df) - 1
    assert out["n_event"] == int((df.drop(index=0)["resp"] == "Yes").sum())


def test_unadjusted_and_adjusted_both_present():
    rng = np.random.default_rng(11)
    n = 500
    arm = rng.choice(["Standard care", "New treatment"], size=n)
    age = rng.normal(60, 10, n)
    logit = -4 + 0.05 * age + 0.4 * (arm == "New treatment")
    y = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    df = pd.DataFrame({
        "resp": np.where(y == 1, "Yes", "No"), "arm": arm, "age": age,
    })
    out = fit_logistic(df, "resp", "Yes", ["arm", "age"],
                       {"arm": "Standard care"}, {"age": 10})
    for key in ("armNew treatment", "age"):
        assert key in out["terms"]
        assert key in out["unadjusted"]
    assert 0.5 < out["c_statistic"] < 1.0


def test_perfect_separation_is_not_reportable():
    # Spec Reportability: estimate and both CI bounds finite, interval within
    # [1e-6, 1e6] — a perfectly separated covariate must fail this.
    df = pd.DataFrame({
        "resp": ["Yes"] * 20 + ["No"] * 20,
        "grp": ["A"] * 20 + ["B"] * 20,
    })
    out = fit_logistic(df, "resp", "Yes", ["grp"], {"grp": "A"}, {})
    cell = out["terms"]["grpB"]
    assert not reportable(cell)


def test_reportable_accepts_a_normal_cell():
    assert reportable({"est": 1.5, "lo": 1.1, "hi": 2.1, "p": 0.01})
    assert not reportable({"est": float("inf"), "lo": 1.0, "hi": 2.0, "p": 0.5})
    assert not reportable({"est": 2.0, "lo": 1e-9, "hi": 2.0, "p": 0.5})


# ---------------------------------------------------------------------------
# A14: the advisory DIAGNOSTICS block.
#
# Everything below is red until the clean-room round adds `diagnostics` to
# fit_logistic's return, which is the designed state — the contract is
# published (INTERFACES.md) and specified (spec/logistic-confounding.md's
# Diagnostics section) before it is implemented.
#
# THE FIXTURES ARE PRE-COMPUTED IN R, from the same base-R expressions
# R/logistic.R uses. Two of them, because one cannot exercise everything:
#
#   L1  60 rows, `arm` (2 levels) + `age` + `bmi`, with bmi built as
#       0.35*age + noise so the two continuous covariates are genuinely
#       collinear. Triggers VIF (7.0), EPV (2.7) and Cook's (8) at once, on a
#       heavily unbalanced outcome (52 events / 8 non-events) so the EPV rule's
#       min(events, non-events) reading is the one being tested — an
#       implementation that divided the EVENT count by the term count would
#       report 17.3 here and never fire the note at all.
#   L2  20 rows, ONE two-level factor, so the model produces exactly TWO
#       distinct fitted probabilities and almost every pair is tied. This is the
#       midrank test: the C-statistic is hand-checkable as
#       (7*6 concordant + 0.5*(7*5 + 2*6) tied) / (9*11) = 65.5/99, and an
#       implementation that broke ties by position instead of averaging ranks
#       lands somewhere else entirely.
#
# Generated once with (L1):
#
#   Rscript -e '
#   set.seed(101); n <- 60
#   age <- round(rnorm(n, 60, 9), 1)
#   bmi <- round(0.35 * age + rnorm(n, 8, 1.2), 1)
#   arm <- rep(c("Standard care", "New treatment"), length.out = n)
#   lp <- -3.2 + 0.05*age + 0.06*bmi + 0.8*(arm == "New treatment")
#   y <- rbinom(n, 1, 1/(1+exp(-lp)))
#   dat <- data.frame(.y = y, arm = relevel(factor(arm), ref = "Standard care"),
#                     age = age, bmi = bmi)
#   fit <- glm(.y ~ arm + age + bmi, family = binomial, data = dat)
#   prob <- fitted(fit); n1 <- sum(y == 1); n0 <- sum(y == 0)
#   sprintf("%.17g", (sum(rank(prob)[y == 1]) - n1*(n1+1)/2)/(n1*n0))
#   cd <- cooks.distance(fit); sum(cd > 4/length(cd), na.rm = TRUE)
#   summary(lm(age ~ bmi, data = dat))$r.squared    # -> VIF = 1/(1-r2)
#   '
#
# and (L2) with the literal y/grp vectors below through the same glm + rank
# expression. Full R output is quoted in the constants beneath each fixture.
# ---------------------------------------------------------------------------

_L1_AGE = [57.1, 65, 53.9, 61.9, 62.8, 70.6, 65.6, 59, 68.3, 58, 64.7, 52.8,
           72.8, 46.8, 57.9, 58.3, 52.4, 60.5, 52.6, 41.5, 58.5, 66.4, 57.6,
           46.8, 66.7, 47.3, 64.2, 58.9, 64.2, 64.5, 68.1, 62.5, 69.1, 41.3,
           70.7, 53.5, 61.5, 68.3, 45, 64, 64.3, 66.8, 39.1, 55.9, 50.1, 63.6,
           65.1, 53.6, 57.4, 46.6, 49.6, 57.5, 65.2, 47.4, 66.7, 50.5, 61.5,
           70.2, 70.6, 56.1]
_L1_BMI = [27.7, 29.1, 26.1, 29.8, 30.5, 33.2, 30.1, 28.8, 31.8, 28.2, 32.5,
           28.4, 34.9, 24.3, 26.1, 27.2, 26.7, 27.6, 26.6, 22.5, 30.7, 32.6,
           27.5, 23.7, 29.3, 25.1, 30.5, 30.2, 31.3, 32.4, 33.4, 29.8, 31.8,
           21.6, 33.1, 25.8, 29, 33.5, 24.3, 29.4, 30.8, 30.7, 24.2, 29, 26.4,
           30, 30.9, 24.1, 27.5, 26.3, 24.7, 28.1, 30.6, 26.5, 32.3, 24.7,
           28.8, 31.6, 32, 28.8]
_L1_ARM = ["Standard care", "New treatment"] * 30
_L1_OUTCOME = [
    "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes",
    "Yes", "Yes", "Yes", "No", "Yes", "Yes", "No", "Yes", "Yes", "Yes",
    "Yes", "Yes", "Yes", "Yes", "Yes", "No", "Yes", "Yes", "Yes", "Yes",
    "Yes", "Yes", "No", "Yes", "No", "Yes", "No", "Yes", "Yes", "Yes",
    "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes",
    "Yes", "No", "Yes", "No", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes"]

# R, on the frame above:
#   c-statistic                    0.61538461538461542
#   cooks.distance > 4/n           8
#   summary(lm(age ~ bmi))$r.squared  0.85731968579599449  -> VIF 7.0086753423474493
#   min(52, 8) / 3 non-intercept coefficients             -> EPV 2.6666666666666665
_L1_C_STATISTIC = 0.61538461538461542
_L1_COOKS = 8
_L1_VIF = 7.0086753423474493
_L1_EPV = 2.6666666666666665


def _l1_frame():
    return pd.DataFrame({"resp": _L1_OUTCOME, "arm": _L1_ARM,
                         "age": _L1_AGE, "bmi": _L1_BMI})


def _l1_fit():
    return fit_logistic(_l1_frame(), "resp", "Yes", ["arm", "age", "bmi"],
                        {"arm": "Standard care"}, {})


def test_diagnostics_block_is_present_with_every_contract_key():
    d = _l1_fit()["diagnostics"]
    for key in ("c_statistic", "vif", "vif_triggered", "epv", "epv_triggered",
                "cooks_influential", "cooks_triggered", "separation_caution"):
        assert key in d, key


def test_c_statistic_matches_r_normalised_mann_whitney():
    d = _l1_fit()["diagnostics"]
    assert math.isclose(d["c_statistic"], _L1_C_STATISTIC, rel_tol=1e-6)


def test_vif_matches_r_one_over_one_minus_r_squared():
    d = _l1_fit()["diagnostics"]
    # Continuous covariates ONLY: `arm` takes no part, as regressand or
    # regressor. A GVIF-style implementation would put a third key here.
    assert set(d["vif"]) == {"age", "bmi"}
    for cov in ("age", "bmi"):
        assert math.isclose(d["vif"][cov], _L1_VIF, rel_tol=1e-6), cov
    assert d["vif_triggered"] is True


def test_vif_is_none_not_empty_with_fewer_than_two_continuous_covariates():
    """"the diagnostic did not run" and "it ran and found nothing" are
    different claims, and the comparator reads them differently."""
    out = fit_logistic(_l1_frame(), "resp", "Yes", ["arm", "age"],
                       {"arm": "Standard care"}, {})
    assert out["diagnostics"]["vif"] is None
    assert out["diagnostics"]["vif_triggered"] is False


def test_a_duplicated_covariate_gives_an_infinite_vif():
    # assign() rather than df["age_copy"] = ...: the in-place form on a frame
    # built by _l1_frame() trips pandas 3.0's ChainedAssignmentError
    # FutureWarning, and this suite adds no warning noise of its own.
    df = _l1_frame().assign(age_copy=lambda d: d["age"])
    out = fit_logistic(df, "resp", "Yes", ["age", "age_copy"], {}, {})
    vif = out["diagnostics"]["vif"]
    assert math.isinf(vif["age"]) and math.isinf(vif["age_copy"])
    assert out["diagnostics"]["vif_triggered"] is True


def _l1_rank_deficient():
    """L1 plus an exact copy of `age`: 3 design columns, only 2 of them
    estimable. assign() rather than in-place, same reason as above."""
    df = _l1_frame().assign(age_copy=lambda d: d["age"])
    return fit_logistic(df, "resp", "Yes", ["age", "age_copy"], {}, {})


# Derived from spec/logistic-confounding.md's Cook's clause alone, not measured
# off the implementation. The spec's `p` is "the number of ESTIMATED
# coefficients including the intercept", which on this design is 2 (intercept +
# age), not the 3 columns present — `age_copy` adds no rank, so no coefficient
# is estimated for it.
#
# Re-derived independently by dropping the duplicated column: on the REDUCED
# design [const, age] the fit, the fitted probabilities and the hat matrix are
# identical, the design is unambiguously full rank, and `p` is plainly 2. Then,
# with D_i = (r_i/(1-h_i))^2 * h_i / p, the literal inverse the spec writes, and
# the 4/n = 0.0666... cut-off:
#
#   trace(H) = 2.000000000000004  (= p, the internal check that the divisor and
#                                  the leverage agree about the rank)
#   no D_i is non-finite, so nothing is excluded
#   7 rows exceed the cut: 0-based 13, 16, 25, 32, 34, 36, 53, with
#     D_i = 0.128393, 0.069767, 0.121188, 0.192649, 0.233441, 0.075046, 0.119796
#   the largest D_i BELOW the cut is 0.056705, so the boundary is not tight
#
# Dividing by the column count 3 instead scales every D_i by 2/3 and drops rows
# 16 (0.0698 -> 0.0465) and 36 (0.0750 -> 0.0500) below the cut, giving 5 — the
# undercount the column-count reading produces.
_L1_DUP_COOKS = 7


def test_cooks_p_is_the_estimated_coefficient_count_not_the_column_count():
    d = _l1_rank_deficient()["diagnostics"]
    assert d["cooks_influential"] == _L1_DUP_COOKS
    assert d["cooks_triggered"] is True


def test_a_full_rank_design_is_untouched_by_the_rank_reading():
    """rank == column count on every design that is not deficient, so the L1
    count pinned against R above cannot move."""
    assert _l1_fit()["diagnostics"]["cooks_influential"] == _L1_COOKS


def test_an_aliased_covariate_has_no_estimate_and_fires_the_caution():
    """A rank-deficient design estimates FEWER coefficients than it has columns
    (the spec's own Cook's wording), so the aliased column has no estimate at
    all — it cannot satisfy Reportability's "the estimate and both CI bounds are
    finite", so separation clause 1 fires. The displayed sentence names this
    case in as many words: covariates that "duplicate information already
    carried by another covariate, so those odds ratios are not reliably
    estimated by standard logistic regression".

    Without this, statsmodels' pinv solve hands back the minimum-norm split —
    two identical, finite, reportable odds ratios — and the caution stays
    silent on the one fixture in the suite that is built to provoke it."""
    out = _l1_rank_deficient()
    # left-to-right: the FIRST occurrence keeps its coefficient
    assert reportable(out["terms"]["age"])
    assert not reportable(out["terms"]["age_copy"])
    assert math.isnan(out["terms"]["age_copy"]["est"])
    assert out["diagnostics"]["separation_caution"] is True
    # the univariable fits are each full rank, so both still have estimates
    assert reportable(out["unadjusted"]["age"])
    assert reportable(out["unadjusted"]["age_copy"])


def test_vif_is_unchanged_by_the_increment_rescaling():
    """Dividing a column by a positive constant leaves R^2 alone, so the app's
    per-10-years rescaling must not move a VIF."""
    plain = _l1_fit()["diagnostics"]["vif"]
    scaled = fit_logistic(_l1_frame(), "resp", "Yes", ["arm", "age", "bmi"],
                          {"arm": "Standard care"},
                          {"age": 10})["diagnostics"]["vif"]
    for cov in ("age", "bmi"):
        assert math.isclose(plain[cov], scaled[cov], rel_tol=1e-9), cov


def test_epv_uses_the_smaller_outcome_group_not_the_event_count():
    d = _l1_fit()["diagnostics"]
    assert math.isclose(d["epv"], _L1_EPV, rel_tol=1e-9)
    assert d["epv_triggered"] is True


def test_cooks_distance_count_matches_r():
    d = _l1_fit()["diagnostics"]
    assert d["cooks_influential"] == _L1_COOKS
    assert d["cooks_triggered"] is True


def test_separation_caution_is_false_on_a_clean_fit():
    assert _l1_fit()["diagnostics"]["separation_caution"] is False


# L2 — two distinct fitted probabilities, so the C-statistic is almost all ties.
# grp A: 7 events / 5 non-events; grp B: 2 events / 6 non-events.
#   concordant 7*6 = 42, tied 0.5*(7*5 + 2*6) = 23.5, discordant 2*5 = 10 -> 0
#   C = 65.5 / (9*11) = 0.66161616161616166   (R agrees to 17 digits)
_L2_Y = [1] * 7 + [0] * 5 + [1] * 2 + [0] * 6
_L2_GRP = ["A"] * 12 + ["B"] * 8
_L2_C_STATISTIC = 0.66161616161616166


def test_c_statistic_averages_ranks_at_ties():
    df = pd.DataFrame({"resp": ["Yes" if v else "No" for v in _L2_Y],
                       "grp": _L2_GRP})
    out = fit_logistic(df, "resp", "Yes", ["grp"], {"grp": "A"}, {})
    assert math.isclose(out["diagnostics"]["c_statistic"], _L2_C_STATISTIC,
                        rel_tol=1e-9)


def test_c_statistic_is_none_when_a_class_is_empty():
    """`None` when either class is empty, per the spec — not 0, not nan, and not
    a ZeroDivisionError on n1*n0. `None` is the contracted "the diagnostic could
    not be computed" value and the comparator reads it as the sentence being
    silent; a 0.0 would render " C-statistic = 0.00." and claim a measurement.

    Called directly: no fixture with a single-class outcome can reach it through
    fit_logistic, because a constant outcome gives glm nothing to fit."""
    assert _c_statistic([1, 1, 1], [0.2, 0.5, 0.9]) is None      # no y = 0
    assert _c_statistic([0, 0, 0], [0.2, 0.5, 0.9]) is None      # no y = 1
    assert _c_statistic([], []) is None                          # no rows at all
    # and the finite case still returns a number, so the guard is not swallowing
    # a legitimate computation
    assert _c_statistic([1, 0], [0.9, 0.1]) == 1.0


def test_separation_caution_fires_on_an_unreportable_cell():
    """The dominant clause in practice. Measured in R: on a perfectly separated
    15-vs-15 fixture glm's IRLS stops at min(mu) = 7.9e-12 — four orders of
    magnitude ABOVE the 10*eps the fitted-probability clause tests — so R issues
    no warning at all and the caution comes entirely from the unreportable
    cell."""
    df = pd.DataFrame({"resp": ["No"] * 15 + ["Yes"] * 15,
                       "grp": ["lo"] * 15 + ["hi"] * 15})
    out = fit_logistic(df, "resp", "Yes", ["grp"], {"grp": "lo"}, {})
    assert not reportable(out["terms"]["grphi"])
    assert out["diagnostics"]["separation_caution"] is True

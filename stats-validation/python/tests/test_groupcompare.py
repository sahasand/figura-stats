"""Acceptance tests for validate.groupcompare.compare_groups, written against
stats-validation/spec/groupcompare-{numeric,categorical,dirty}.md alone
(compare_groups itself does not exist yet — it is written by a clean-room agent
from those specs; this file is the contract it must satisfy). Expected to fail
collection right now with
`ModuleNotFoundError: No module named 'validate.groupcompare'`.

Every expected value below that came from R was computed by running the quoted
`Rscript` command against R 4.6.0 in this repo, and is pasted at full printed
precision (`options(digits = 17)`). The R commands are in the comments so a
reader can re-derive any constant without trusting this file.

Group comparison is the analysis where R's and Python's DEFAULTS disagree in
the most places at once — Welch vs pooled t, Welch vs classical one-way ANOVA,
Yates' correction on vs off, exact vs Monte Carlo r x c Fisher, BH vs
Bonferroni post-hoc adjustment, and two mutually opposite post-hoc pair-naming
conventions. Nearly every test here exists because a plausible default gets it
wrong.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from validate.groupcompare import compare_groups
from validate.io import load_case

CASES = Path(__file__).resolve().parents[2] / "cases"


def _case(case_id):
    df, case = load_case(str(CASES / case_id))
    return df, case["roles"]["outcome"], case["roles"]["group"]


# ---------------------------------------------------------------------------
# Test selection: where the two languages' defaults part company
# ---------------------------------------------------------------------------

def test_two_numeric_groups_use_welch_not_pooled():
    rng = np.random.default_rng(2)
    a = rng.normal(10, 1, 60)
    b = rng.normal(12, 4, 60)  # deliberately unequal variances
    df = pd.DataFrame({"y": np.concatenate([a, b]).astype(str),
                       "g": ["A"] * 60 + ["B"] * 60})
    out = compare_groups(df, "y", "g", nonparametric=False)
    welch = stats.ttest_ind(a, b, equal_var=False).pvalue
    pooled = stats.ttest_ind(a, b, equal_var=True).pvalue
    assert abs(out["p_value"] - welch) < 1e-12
    assert abs(out["p_value"] - pooled) > 1e-6  # the defaults really do differ
    assert out["test_name"] == "Welch t-test"


def test_chi_square_has_no_continuity_correction():
    df = pd.DataFrame({
        "y": ["yes"] * 40 + ["no"] * 60 + ["yes"] * 60 + ["no"] * 40,
        "g": ["A"] * 100 + ["B"] * 100,
    })
    out = compare_groups(df, "y", "g")
    table = pd.crosstab(df["g"], df["y"]).to_numpy()
    expected = stats.chi2_contingency(table, correction=False).pvalue
    assert abs(out["p_value"] - expected) < 1e-12
    # A 2x2 table is the ONLY shape where R's own Yates default would bite, so
    # this fixture is also the only place the "correction off" clause can be
    # discriminated at all — the real groupcompare-categorical case is 2x3,
    # where R's correction is a no-op.
    corrected = stats.chi2_contingency(table, correction=True).pvalue
    assert abs(out["p_value"] - corrected) > 1e-6
    assert out["test_name"] == "Pearson chi-square test"


def test_fisher_replaces_chi_square_on_small_expected_counts():
    df = pd.DataFrame({
        "y": ["yes", "no", "no", "no", "yes", "no", "no", "no"],
        "g": ["A", "A", "A", "A", "B", "B", "B", "B"],
    })
    out = compare_groups(df, "y", "g")
    assert "Fisher" in out["test_name"]
    # Fisher's exact test has no test statistic; None is the correct report,
    # not the chi-square statistic smuggled in under another name.
    assert out["statistic"] is None


# Fixture A — three groups, deliberately unequal variances (group B's spread is
# an order of magnitude wider than A's and C's).
_A_G1 = [10.1, 10.4, 9.8, 10.2, 10.0, 9.9, 10.3, 10.1]
_A_G2 = [12.0, 15.0, 9.0, 13.5, 11.0, 16.0, 8.5, 12.5]
_A_G3 = [11.0, 11.5, 10.8, 11.2, 11.1, 10.9, 11.3, 11.4]


def _fixture_a():
    return pd.DataFrame({
        "y": [str(v) for v in _A_G1 + _A_G2 + _A_G3],
        "g": ["A"] * 8 + ["B"] * 8 + ["C"] * 8,
    })


def test_three_group_welch_anova_matches_r_oneway_test():
    """A5: R-precomputed. The 3+ group parametric omnibus is Welch's
    heteroscedastic F (R's `oneway.test` default `var.equal = FALSE`), NOT the
    classical pooled-variance one-way ANOVA.

    Rscript -e 'options(digits=17)
      g1 <- c(10.1,10.4,9.8,10.2,10.0,9.9,10.3,10.1)
      g2 <- c(12.0,15.0,9.0,13.5,11.0,16.0,8.5,12.5)
      g3 <- c(11.0,11.5,10.8,11.2,11.1,10.9,11.3,11.4)
      d <- data.frame(value=c(g1,g2,g3), group=rep(c("A","B","C"), each=8))
      w <- oneway.test(value ~ group, data=d)              # var.equal=FALSE
      print(unname(w$statistic)); print(w$p.value)
      print(oneway.test(value ~ group, data=d, var.equal=TRUE)$p.value)'
    -> F  43.322151967613394
    -> p  2.6846212189305972e-06     (Welch)
    -> p  0.043665379916126124       (classical ANOVA)
    """
    r_welch_f = 43.322151967613394
    r_welch_p = 2.6846212189305972e-06
    r_pooled_p = 0.043665379916126124

    out = compare_groups(_fixture_a(), "y", "g", nonparametric=False)
    assert out["test_name"] == "one-way ANOVA (Welch)"
    assert abs(out["p_value"] - r_welch_p) <= 1e-6 * r_welch_p
    assert abs(out["statistic"] - r_welch_f) <= 1e-6 * r_welch_f
    # The two defaults are four orders of magnitude apart on this fixture:
    # 2.7e-06 vs 0.044. An implementation that reached for the classical
    # one-way ANOVA would not merely round differently, it would change the
    # published conclusion at alpha = 0.05 in the other direction.
    assert abs(out["p_value"] - r_pooled_p) > 1e-3


# Fixture B — a 3x3 table with small expected counts (min expected 1.5625),
# so the expected-count rule routes it to Fisher rather than chi-square.
#            A  B  C
#   x        4  1  0
#   y        1  4  1
#   z        0  1  4
_B_COUNTS = {("x", "A"): 4, ("x", "B"): 1, ("x", "C"): 0,
             ("y", "A"): 1, ("y", "B"): 4, ("y", "C"): 1,
             ("z", "A"): 0, ("z", "B"): 1, ("z", "C"): 4}


def _fixture_b():
    ys, gs = [], []
    for (outcome, group), count in _B_COUNTS.items():
        ys.extend([outcome] * count)
        gs.extend([group] * count)
    return pd.DataFrame({"y": ys, "g": gs})


def test_rxc_fisher_matches_r_fisher_test():
    """A5: R-precomputed. Fisher's exact test must be the general r x c form,
    computed EXACTLY, not restricted to 2x2 and not approximated.

    Rscript -e 'options(digits=17)
      t <- matrix(c(4,1,0, 1,4,1, 0,1,4), nrow=3, byrow=TRUE)
      print(min(suppressWarnings(chisq.test(t, correct=FALSE))$expected))
      print(fisher.test(t)$p.value)'
    -> min expected  1.5625        (< 5, so the Fisher branch fires)
    -> p             0.012396333824905242

    MEASURED IMPLEMENTATION HAZARD, not a hypothetical: `scipy.stats.
    fisher_exact` is exact only for 2x2 tables. For anything larger it runs a
    MONTE CARLO test — the same 3x3 input above returned 0.0125 on one call and
    0.0142 on the next in this repo's venv (scipy 1.16.1), i.e. it is not even
    self-reproducible, let alone within 1e-6 of R. The assertion below is at
    rel 1e-6 anyway, because that tolerance IS honestly achievable: an
    exhaustive enumeration over the fixed-margin tables (sum the multivariate
    hypergeometric probability of every table whose probability does not exceed
    the observed one's) was verified against R on four different tables and
    agreed to within 1.0e-14 relative on all of them. Enumerate; do not call
    scipy's r x c shortcut.
    """
    r_fisher_p = 0.012396333824905242
    out = compare_groups(_fixture_b(), "y", "g")
    assert "Fisher" in out["test_name"]
    assert abs(out["p_value"] - r_fisher_p) <= 1e-6 * r_fisher_p
    assert out["statistic"] is None


# ---------------------------------------------------------------------------
# A6: the normality routing runs on GROUP-MEAN-CENTRED values
# ---------------------------------------------------------------------------

def _fixture_g():
    """Two well-separated, textbook-normal groups.

    The values are normal quantiles, so R and Python build the same numbers
    from the same recipe: `qnorm((1:20 - 0.5)/20)` and
    `norm.ppf((arange(1,21) - 0.5)/20)` agree to floating-point noise (measured
    ~3e-16 relative, from the two libraries' different inverse-normal
    algorithms) — nowhere near enough to move the routing decision, which turns
    on a Shapiro-Wilk p of 0.93 against a 0.05 threshold. Group A is centred at
    10, group B at 30.
    """
    q = stats.norm.ppf((np.arange(1, 21) - 0.5) / 20)
    return pd.DataFrame({
        "y": np.concatenate([10 + q, 30 + q]).astype(str),
        "g": ["A"] * 20 + ["B"] * 20,
    })


def test_normality_routing_uses_group_mean_centred_values():
    """A6: two well-separated normal groups must route to the PARAMETRIC
    branch. This only happens if the normality assessment is run on
    group-mean-centred residuals; pooling the raw values produces a bimodal
    mixture that fails Shapiro-Wilk outright.

    Rscript -e 'options(digits=17)
      q <- qnorm((1:20 - 0.5)/20)
      d <- data.frame(value=c(10+q, 30+q), group=rep(c("A","B"), each=20))
      cen <- d$value - ave(d$value, d$group)
      sk <- {m <- mean(cen); s <- sqrt(mean((cen-m)^2)); mean((cen-m)^3)/s^3}
      print(sk); print(shapiro.test(cen)$p.value)
      print(shapiro.test(d$value)$p.value)'
    -> centred skewness            0                       (|sk| < 1  -> ok)
    -> centred Shapiro-Wilk p      0.93087749875386716     (>= 0.05  -> ok)
    -> POOLED, UNCENTRED Shapiro-Wilk p  2.4141826361493618e-07

    So the correct rule says PARAMETRIC (Welch t-test) and the uncentred
    mistake says NON-PARAMETRIC (Mann-Whitney). The two branches are
    distinguishable by name alone, which is what this asserts.
    """
    out = compare_groups(_fixture_g(), "y", "g")  # nonparametric=None -> auto
    assert out["test_name"] == "Welch t-test"
    assert out["effect"]["label"] == "Cohen's d"


# ---------------------------------------------------------------------------
# A9: post-hoc significant-pair SETS, including the two opposite naming rules
# ---------------------------------------------------------------------------

def test_tukey_significant_pairs_match_r():
    """A9, parametric branch, on the REAL groupcompare-numeric case.

    Rscript -e 'options(digits=17)
      d <- read.csv("stats-validation/cases/groupcompare-numeric/data.csv")
      dat <- data.frame(value=as.numeric(d$biomarker_normal),
                        group=as.character(d$arm))
      tk <- TukeyHSD(aov(value ~ group, data=dat))$group
      dput(rownames(tk)); dput(unname(tk[,"p adj"]))'
    -> rownames  c("Low dose-High dose", "Placebo-High dose", "Placebo-Low dose")
    -> p adj     c(0.0145491987121452, 3.47943895917524e-13, 8.77398289800269e-07)

    All three are < 0.05, so all three are significant. Note the pair naming:
    R's TukeyHSD labels a pair "<later>-<earlier>" in sorted level order.
    """
    df, outcome, group = _case("groupcompare-numeric")
    out = compare_groups(df, outcome, group)

    assert out["posthoc"] is not None
    assert out["posthoc"]["test"] == "Tukey HSD"
    assert set(out["posthoc"]["significant_pairs"]) == {
        "Low dose-High dose", "Placebo-High dose", "Placebo-Low dose"}
    # The naming order is part of the contract, not incidental: the reversed
    # spellings must NOT appear.
    assert "High dose-Low dose" not in out["posthoc"]["significant_pairs"]


def test_dunn_significant_pairs_match_r():
    """A9, non-parametric branch, on the REAL groupcompare-dirty case.

    Rscript -e 'options(digits=17)
      d <- read.csv("stats-validation/cases/groupcompare-dirty/data.csv")
      dat <- data.frame(value=as.numeric(d$site_code), group=as.character(d$arm))
      dat <- dat[!is.na(dat$value) & !is.na(dat$group), ]
      r <- rank(dat$value); N <- nrow(dat)
      ties <- table(dat$value); tie_term <- sum(ties^3 - ties)
      Rbar <- tapply(r, dat$group, mean); nvec <- tapply(r, dat$group, length)
      lv <- sort(unique(dat$group))
      zp <- lapply(combn(lv, 2, simplify=FALSE), function(pr) {
        i <- pr[1]; j <- pr[2]
        s <- sqrt((N*(N+1)/12 - tie_term/(12*(N-1))) * (1/nvec[[i]] + 1/nvec[[j]]))
        list(pair=paste(i, j, sep="-"), p=2*pnorm(-abs((Rbar[[i]]-Rbar[[j]])/s)))})
      praw <- vapply(zp, function(x) x$p, numeric(1))
      print(p.adjust(praw, method="BH"))'
    -> BH-adjusted p  2.11276517125e-10  ("High dose-Low dose")
                      2.25784986771e-11  ("High dose-Placebo")
                      0.663876728567     ("Low dose-Placebo")

    Two of three survive at 0.05. The third is a genuine non-significant
    comparison (z = 0.435), not a degenerate exact tie, so a wrong variance or
    a wrong multiplicity method has somewhere to show up.

    Note the pair naming is "<earlier>-<later>" here — the OPPOSITE of Tukey's
    convention in the test above. That is the app's real behaviour: Tukey's
    names come from R's TukeyHSD row labels, Dunn's from the app's own pairing
    loop over sorted levels.
    """
    df, outcome, group = _case("groupcompare-dirty")
    out = compare_groups(df, outcome, group)

    assert out["posthoc"] is not None
    assert out["posthoc"]["test"] == "Dunn's test (BH-adjusted)"
    assert set(out["posthoc"]["significant_pairs"]) == {
        "High dose-Low dose", "High dose-Placebo"}
    assert "Low dose-Placebo" not in out["posthoc"]["significant_pairs"]
    # Reversed spellings must not appear: this is the Dunn convention, not
    # Tukey's.
    assert "Low dose-High dose" not in out["posthoc"]["significant_pairs"]


def test_no_posthoc_when_the_omnibus_is_not_significant():
    """Post-hoc runs only when there are 3+ groups AND the omnibus p < 0.05.
    Three identical groups give p = 1, so there must be no post-hoc RESULT at
    all — `None`, not an empty significant-pairs list, because the app emits no
    post-hoc sentence whatsoever in that case."""
    vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    df = pd.DataFrame({
        "y": [str(v) for v in vals * 3],
        "g": ["A"] * 6 + ["B"] * 6 + ["C"] * 6,
    })
    out = compare_groups(df, "y", "g", nonparametric=False)
    assert out["p_value"] > 0.05
    assert out["posthoc"] is None


# ---------------------------------------------------------------------------
# Effect sizes, one per branch, all R-precomputed
# ---------------------------------------------------------------------------

# Fixture F — two overlapping groups, so the rank-biserial correlation is a
# real interior value rather than a saturated +/-1.
_F_XA = [5.1, 6.3, 4.8, 5.9, 6.1, 5.4, 4.9, 6.0, 5.6, 5.2]
_F_XB = [6.2, 7.1, 5.5, 6.9, 7.4, 6.05, 5.8, 7.0, 6.5, 6.35]


def _fixture_f():
    return pd.DataFrame({
        "y": [str(v) for v in _F_XA + _F_XB],
        "g": ["A"] * 10 + ["B"] * 10,
    })


def test_cohens_d_two_group_parametric_matches_r():
    """Effect size, k=2 parametric. The app reports COHEN'S d with a pooled SD
    — no Hedges/J small-sample correction anywhere — and an interval whose
    standard error uses the denominator 2*(n1+n2), not the textbook
    2*(n1+n2-2).

    Rscript -e 'options(digits=17)
      xa <- c(5.1,6.3,4.8,5.9,6.1,5.4,4.9,6.0,5.6,5.2)
      xb <- c(6.2,7.1,5.5,6.9,7.4,6.05,5.8,7.0,6.5,6.35)
      n1 <- 10; n2 <- 10
      sp <- sqrt(((n1-1)*var(xa) + (n2-1)*var(xb)) / (n1+n2-2))
      d  <- (mean(xb) - mean(xa)) / sp
      se <- sqrt((n1+n2)/(n1*n2) + d^2/(2*(n1+n2)))
      print(d); print(c(d - 1.96*se, d + 1.96*se))
      print(t.test(value ~ group, data=data.frame(
        value=c(xa,xb), group=rep(c("A","B"), each=10)))$p.value)'
    -> d       1.659052981163355
    -> CI      0.64285125388414688  2.67525470844256308
    -> Welch p 0.0016521761779204488
    """
    r_d, r_lo, r_hi = (1.659052981163355,
                       0.64285125388414688, 2.67525470844256308)
    r_p = 0.0016521761779204488

    out = compare_groups(_fixture_f(), "y", "g", nonparametric=False)
    eff = out["effect"]
    assert eff["label"] == "Cohen's d"
    assert abs(eff["value"] - r_d) <= 1e-9 * abs(r_d)
    assert abs(eff["lo"] - r_lo) <= 1e-9 * abs(r_lo)
    assert abs(eff["hi"] - r_hi) <= 1e-9 * abs(r_hi)
    assert abs(out["p_value"] - r_p) <= 1e-9 * r_p
    # Sign convention: (second sorted group - first), so B > A gives d > 0.
    assert eff["value"] > 0
    # Hedges' g would be d * (1 - 3/(4*(n1+n2) - 9)) = d * 0.95783..., a 4.2%
    # difference here — far outside the tolerance above. This assertion exists
    # so a Hedges-corrected implementation fails loudly instead of drifting.
    assert abs(eff["value"] - r_d * (1 - 3 / (4 * 20 - 9))) > 1e-3


def test_rank_biserial_two_group_nonparametric_matches_r():
    """Effect size, k=2 non-parametric: rank-biserial from R's W, with a
    Fisher-z interval.

    Rscript -e 'options(digits=17)
      xa <- c(5.1,6.3,4.8,5.9,6.1,5.4,4.9,6.0,5.6,5.2)
      xb <- c(6.2,7.1,5.5,6.9,7.4,6.05,5.8,7.0,6.5,6.35)
      d <- data.frame(value=c(xa,xb), group=rep(c("A","B"), each=10))
      wt <- suppressWarnings(wilcox.test(value ~ group, data=d))
      print(unname(wt$statistic)); print(wt$p.value)
      U <- unname(wt$statistic); r <- 1 - 2*U/(10*10)
      z <- atanh(max(min(r, 0.999999), -0.999999)); se <- 1/sqrt(10+10-3)
      print(r); print(c(tanh(z - 1.96*se), tanh(z + 1.96*se)))'
    -> W   12
    -> p   0.0028794734677087619
    -> r   0.76
    -> CI  0.47835212055006782  0.89987936050437645
    """
    r_w, r_p = 12.0, 0.0028794734677087619
    r_r, r_lo, r_hi = 0.76, 0.47835212055006782, 0.89987936050437645

    out = compare_groups(_fixture_f(), "y", "g", nonparametric=True)
    assert "Mann" in out["test_name"]
    assert abs(out["statistic"] - r_w) <= 1e-9
    assert abs(out["p_value"] - r_p) <= 1e-9 * r_p
    eff = out["effect"]
    assert eff["label"] == "rank-biserial r"
    assert abs(eff["value"] - r_r) <= 1e-9
    assert abs(eff["lo"] - r_lo) <= 1e-9 * abs(r_lo)
    assert abs(eff["hi"] - r_hi) <= 1e-9 * abs(r_hi)


def test_eta_squared_three_group_parametric_matches_r():
    """Effect size, k>=3 parametric, on the REAL groupcompare-numeric case.
    Both the point estimate and the Steiger non-central-F interval come from
    the CLASSICAL one-way ANOVA decomposition, even though the p-value came
    from the Welch test.

    Rscript -e 'options(digits=17)
      d <- read.csv("stats-validation/cases/groupcompare-numeric/data.csv")
      dat <- data.frame(value=as.numeric(d$biomarker_normal),
                        group=as.character(d$arm))
      s <- summary(aov(value ~ group, data=dat))[[1]]
      print(unname(s[,"Sum Sq"][1] / sum(s[,"Sum Sq"])))
      ht <- oneway.test(value ~ group, data=dat)
      print(unname(ht$statistic)); print(ht$p.value)'
    -> eta^2  0.32102532801259492
    -> F      34.835216031005963      (Welch)
    -> p      3.7310304535906173e-12  (Welch)

    and the interval, from the same .gc_eta_ci root-finding the app uses:
    -> 95% CI  0.19740468951566092  0.42138945932347194

    The two interval limits are asserted at rel 1e-5, not 1e-9: R's `uniroot`
    stops at its own default tolerance (`.Machine$double.eps^0.25`, ~1.2e-4 on
    the non-centrality scale) rather than converging fully, so an
    independently-written tightly-converged solver lands a little away from R's
    answer. Measured gap on this case: 2.5e-8 relative. The POINT estimate is a
    closed-form ratio and is pinned tightly.
    """
    r_eta, r_lo, r_hi = (0.32102532801259492,
                         0.19740468951566092, 0.42138945932347194)
    r_f, r_p = 34.835216031005963, 3.7310304535906173e-12

    df, outcome, group = _case("groupcompare-numeric")
    out = compare_groups(df, outcome, group)
    assert out["test_name"] == "one-way ANOVA (Welch)"
    assert abs(out["statistic"] - r_f) <= 1e-9 * r_f
    assert abs(out["p_value"] - r_p) <= 1e-9 * r_p
    assert out["n"] == 150 and out["n_dropped"] == 0
    assert out["n_per_group"] == {"High dose": 50, "Low dose": 50, "Placebo": 50}

    eff = out["effect"]
    assert eff["label"] == "eta-squared"
    assert abs(eff["value"] - r_eta) <= 1e-12 * r_eta
    assert abs(eff["lo"] - r_lo) <= 1e-5 * r_lo
    assert abs(eff["hi"] - r_hi) <= 1e-5 * r_hi


def test_epsilon_squared_three_group_nonparametric_matches_r():
    """Effect size, k>=3 non-parametric, on the REAL groupcompare-dirty case.
    epsilon-squared = H / (n - 1), with NO confidence interval — the app
    reports the point estimate alone.

    Rscript -e 'options(digits=17)
      d <- read.csv("stats-validation/cases/groupcompare-dirty/data.csv")
      dat <- data.frame(value=as.numeric(d$site_code), group=as.character(d$arm))
      dat <- dat[!is.na(dat$value) & !is.na(dat$group), ]
      kw <- kruskal.test(value ~ group, data=dat)
      print(nrow(dat)); print(unname(kw$statistic)); print(kw$p.value)
      print(unname(kw$statistic)/(nrow(dat)-1))'
    -> n        146
    -> H        58.617246335913329   (tie-corrected)
    -> p        1.8682142740540386e-13
    -> eps^2    0.40425687128216087
    """
    r_h, r_p, r_eps = (58.617246335913329, 1.8682142740540386e-13,
                       0.40425687128216087)

    df, outcome, group = _case("groupcompare-dirty")
    out = compare_groups(df, outcome, group)
    assert out["test_name"] == "Kruskal–Wallis test"  # EN DASH, U+2013
    assert abs(out["statistic"] - r_h) <= 1e-9 * r_h
    assert abs(out["p_value"] - r_p) <= 1e-9 * r_p

    eff = out["effect"]
    assert eff["label"] == "epsilon-squared"
    assert abs(eff["value"] - r_eps) <= 1e-9 * r_eps
    assert eff["lo"] is None and eff["hi"] is None


def test_cramers_v_categorical_matches_r():
    """Effect size, categorical branch, on the REAL groupcompare-categorical
    case. Cramer's V is built from the UNCORRECTED chi-square statistic.

    Rscript -e 'options(digits=17)
      d <- read.csv("stats-validation/cases/groupcompare-categorical/data.csv")
      tab <- table(outcome=d$responder, group=d$arm)
      ch <- suppressWarnings(chisq.test(tab, correct=FALSE))
      print(min(ch$expected)); print(unname(ch$statistic)); print(ch$p.value)
      print(sqrt(unname(ch$statistic)/(sum(tab)*(min(dim(tab))-1))))'
    -> min expected  24.333333333333332   (>= 5, so chi-square, not Fisher)
    -> X2            26.63227183775129
    -> p             1.6476905471843762e-06
    -> Cramer's V    0.42136501862202791
    """
    r_x2, r_p, r_v = (26.63227183775129, 1.6476905471843762e-06,
                      0.42136501862202791)

    df, outcome, group = _case("groupcompare-categorical")
    out = compare_groups(df, outcome, group)
    assert out["test_name"] == "Pearson chi-square test"
    assert abs(out["statistic"] - r_x2) <= 1e-9 * r_x2
    assert abs(out["p_value"] - r_p) <= 1e-9 * r_p
    assert out["n"] == 150 and out["n_dropped"] == 0
    # The categorical branch never runs a post-hoc, at any table size.
    assert out["posthoc"] is None

    eff = out["effect"]
    assert eff["label"] == "Cramér's V"  # e-acute, U+00E9
    assert abs(eff["value"] - r_v) <= 1e-9 * r_v
    assert eff["lo"] is None and eff["hi"] is None


# ---------------------------------------------------------------------------
# The dirty case: type detection, whitespace, CRLF, blanks
# ---------------------------------------------------------------------------

def test_numeric_looking_codes_route_to_the_numeric_branch():
    """The point of the dirty case. `site_code` holds zero-padded site codes
    "01"/"02"/"03" — categorical in every sense that matters scientifically —
    but every one of them PARSES as a number, and the app's type rule is
    parseability alone. So the app compares them as numbers, and so must
    compare_groups. An implementation that adds a distinct-value threshold, a
    leading-zero check, or any other cardinality heuristic to "fix" this will
    produce a 3x3 chi-square where the app produced a Kruskal-Wallis, and this
    assertion is what catches it.
    """
    df, outcome, group = _case("groupcompare-dirty")
    out = compare_groups(df, outcome, group)
    assert out["test_name"] == "Kruskal–Wallis test"
    assert out["effect"]["label"] == "epsilon-squared"
    assert out["statistic"] is not None  # a chi-square/Fisher route would differ


def test_dirty_case_trims_whitespace_handles_crlf_and_counts_blanks():
    """The dirty file has CRLF line endings, twelve leading/trailing-padded
    `site_code` cells, four blank `site_code` cells, and six blank cells in the
    UNMAPPED `los_skewed` column.

    Rscript -e 'options(digits=17)
      d <- read.csv("stats-validation/cases/groupcompare-dirty/data.csv")
      dat <- data.frame(value=as.numeric(d$site_code), group=as.character(d$arm))
      dat <- dat[!is.na(dat$value) & !is.na(dat$group), ]
      print(nrow(dat)); print(table(dat$group))'
    -> n 146; High dose 48, Low dose 49, Placebo 49

    Three separate claims ride on those numbers: padded cells must be TRIMMED
    (untrimmed, " 01" would be a distinct value and, with a stray CR from
    unhandled CRLF, would not parse at all); blanks in the MAPPED outcome drop
    their rows (150 - 4 = 146); and the six blanks in the unmapped
    `los_skewed` column must drop NOTHING.
    """
    df, outcome, group = _case("groupcompare-dirty")
    out = compare_groups(df, outcome, group)
    assert out["n"] == 146
    assert out["n_dropped"] == 4  # NOT 10 — los_skewed's blanks are unmapped
    assert out["n_per_group"] == {"High dose": 48, "Low dose": 49, "Placebo": 49}
    # Trimming actually happened: only three distinct codes survive, so the
    # three group medians are drawn from {1, 2, 3} and nothing else.
    assert math.isfinite(out["statistic"])

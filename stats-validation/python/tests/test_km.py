"""Acceptance tests for validate.km.fit_km, written against
stats-validation/spec/km-twoarm.md alone (fit_km itself does not exist yet —
it is written by a clean-room agent from that spec; this file is the
contract it must satisfy). Expected to fail collection right now with
`ModuleNotFoundError: No module named 'validate.km'`.
"""
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from validate.km import fit_km


def test_hand_computed_product_limit():
    # 5 subjects: events at 1 and 4, censored at 2, 3, 5.
    df = pd.DataFrame({
        "time": ["1", "2", "3", "4", "5"],
        "status": ["1", "0", "0", "1", "0"],
        "group": ["A"] * 5,
    })
    out = fit_km(df, "time", "status", "1", "group")
    curve = {p["t"]: p["surv"] for p in out["curve"]["A"]}
    # S(1) = 1 - 1/5 = 0.8; then 2 censored leave, S(4) = 0.8 * (1 - 1/2) = 0.4
    assert abs(curve[1.0] - 0.8) < 1e-12
    assert abs(curve[4.0] - 0.4) < 1e-12


def test_median_not_reached_is_none_not_the_last_time():
    df = pd.DataFrame({
        "time": ["1", "2", "3"],
        "status": ["1", "0", "0"],
        "group": ["A"] * 3,
    })
    out = fit_km(df, "time", "status", "1", "group")
    assert out["medians"]["A"] is None


def test_logrank_detects_a_real_separation():
    rng = np.random.default_rng(5)
    a = rng.exponential(1.0, 150)
    b = rng.exponential(3.0, 150)
    df = pd.DataFrame({
        "time": np.concatenate([a, b]).astype(str),
        "status": ["1"] * 300,
        "group": ["A"] * 150 + ["B"] * 150,
    })
    out = fit_km(df, "time", "status", "1", "group")
    assert out["logrank_p"] < 0.001


def test_hand_rolled_agrees_with_lifelines():
    # The spec describes the product-limit formula directly (per-timestamp
    # tie convention included), so a from-spec implementation is expected to
    # hand-roll the estimate rather than delegate to a library — this test is
    # the second, independent check that the hand-rolled curve agrees with
    # lifelines' own KaplanMeierFitter at every point.
    rng = np.random.default_rng(9)
    t = rng.exponential(2.0, 200)
    e = rng.binomial(1, 0.7, 200)
    df = pd.DataFrame({"time": t.astype(str), "status": e.astype(str),
                       "group": ["A"] * 200})
    out = fit_km(df, "time", "status", "1", "group")
    kmf = KaplanMeierFitter().fit(t, e)
    for p in out["curve"]["A"]:
        assert abs(p["surv"] - float(kmf.predict(p["t"]))) < 1e-9


# ---------------------------------------------------------------------------
# D13: tie convention — an event AND a censoring at the same timestamp.
#
# 4 subjects, group "A": times [1, 1, 1, 2], status [event, censored, event,
# censored]. At t=1: n(1) = 4 (ALL four are still at risk just before t=1 —
# nobody has exited yet), d(1) = 2 (two events). Per the spec's tie
# convention, the tied censoring at t=1 STILL counts in n(1)'s denominator;
# it leaves the risk set only for t > 1.
#   S(1) = 1 * (1 - 2/4) = 0.5
# The risk set for t=2 then excludes all three subjects who were at t=1 (two
# events + the one tied censoring), leaving only the 4th subject (censored at
# t=2, contributing no event) — so the curve has no further drop, and t=2 is
# a PURE censoring time: per spec, only distinct EVENT times are reported,
# so t=2 must not appear as a curve point at all.
#
# A WRONG implementation that removes the tied censoring from the risk set
# BEFORE computing the t=1 denominator would compute n(1) = 3 instead of 4,
# giving S(1) = 1 - 2/3 = 0.333..., a clearly different (and wrong) number —
# so this test discriminates the two conventions, not just restates the
# formula.
def test_tie_convention_event_and_censoring_at_same_time():
    df = pd.DataFrame({
        "time":   ["1", "1", "1", "2"],
        "status": ["1", "0", "1", "0"],
        "group":  ["A"] * 4,
    })
    out = fit_km(df, "time", "status", "1", "group")
    curve = {p["t"]: p for p in out["curve"]["A"]}
    assert abs(curve[1.0]["surv"] - 0.5) < 1e-12
    assert curve[1.0]["at_risk"] == 4
    assert 2.0 not in curve  # pure-censoring time: no curve row


# ---------------------------------------------------------------------------
# n_dropped: a blank cell in ANY of time/status/group drops the row — per
# spec, this is a deliberate departure from Cox (where a blank status cell is
# censored, not dropped). Blanking STATUS specifically is the discriminating
# case: an implementation that ported Cox's "blank status = censored" rule
# would compute n_dropped = 0 and n = 4 here, not n_dropped = 1 and n = 3.
def test_n_dropped_counts_a_blank_cell_in_any_of_time_status_group():
    df = pd.DataFrame({
        "time":   ["1", "2", "3", "4"],
        "status": ["1", "0", "1", ""],  # blank status on the 4th row
        "group":  ["A", "A", "B", "B"],
    })
    out = fit_km(df, "time", "status", "1", "group")
    assert out["n_dropped"] == 1
    assert out["n"] == 3


# ---------------------------------------------------------------------------
# Median rule: R's actual "minmin" rule (spec/km-twoarm.md's Reported
# quantities), not the naive "smallest t with S(t) <= 0.5" reading of the
# product-limit formula. The spec's ORIGINAL version of this rule (before
# this fix round) said the naive thing and was wrong — this test pins the
# fixture that discriminates the two.
#
# 4 subjects, group "A", all events (no censoring), at times 1, 2, 3, 4:
#   S(1) = 1 - 1/4 = 0.75
#   S(2) = 0.75 * (1 - 1/3) = 0.50   <- first t with S(t) <= 0.5
#   S(3) = 0.50 * (1 - 1/2) = 0.25   <- strictly lower than S(2)
#   S(4) = 0.25 * (1 - 1/1) = 0.00
# S(2) lands EXACTLY on 0.5 (within tol = sqrt(.Machine$double.eps)), and a
# later time (3) has a strictly lower survival than S(2) — so per the
# minmin rule, the median is the MIDPOINT of t=2 and t=3, i.e. (2+3)/2 = 2.5,
# NOT 2. Confirmed directly against R: `Rscript -e 'library(survival);
# summary(survfit(Surv(c(1,2,3,4), c(1,1,1,1)) ~ 1))$table["median"]'`
# prints 2.5. A naive "first t with S(t) <= 0.5" implementation would
# wrongly return 2 here — this fixture is chosen specifically because it
# discriminates the two rules (most fixtures don't: the midpoint step only
# ever fires when S lands EXACTLY on 0.5, which needs a risk-set fraction
# like 2/4, 1/2, 4/8, ... at the crossing time).
def test_median_rule_matches_rs_minmin_rule_not_the_naive_reading():
    df = pd.DataFrame({
        "time":   ["1", "2", "3", "4"],
        "status": ["1", "1", "1", "1"],
        "group":  ["A"] * 4,
    })
    out = fit_km(df, "time", "status", "1", "group")
    assert abs(out["medians"]["A"] - 2.5) < 1e-12

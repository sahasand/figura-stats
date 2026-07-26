"""Acceptance tests for Path B's Table 1 — validate/summary.py.

WRITTEN BEFORE THE MODULE EXISTS, and expected to fail with
`ModuleNotFoundError: No module named 'validate.summary'` until the clean-room
half of Task 11 writes it from stats-validation/spec/summary-table1.md alone.
That is the only failure this file may show; any other failure is a real one.

EVERY constant below is precomputed in R, with the command that produced it
quoted beside it, so a disagreement is a disagreement with the shipping app and
not with this file's author. The two big-sample fixtures deliberately use
DETERMINISTIC quantile grids (`qnorm((i - 0.5)/n)`, `qexp(...)`) rather than a
numpy RNG stream: a PCG64 draw cannot be reproduced in R at all, so an
R-precomputed constant for it would be an assertion about nothing.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from validate.summary import decide, fmt_num, summarize

CASE_CSV = Path(__file__).resolve().parents[2] / "cases" / "summary-table1" / "data.csv"


# ---------------------------------------------------------------------------
# deterministic fixtures, reproducible in BOTH languages
#
#   R:      p <- (seq_len(n) - 0.5)/n; qnorm(p); qexp(p)
#   Python: p = (np.arange(1, n + 1) - 0.5)/n; norm.ppf(p); expon.ppf(p)
# ---------------------------------------------------------------------------

def _grid(n: int) -> np.ndarray:
    return (np.arange(1, n + 1) - 0.5) / n


def normal_grid(n: int) -> np.ndarray:
    return sps.norm.ppf(_grid(n))


def exponential_grid(n: int) -> np.ndarray:
    return sps.expon.ppf(_grid(n))


# ---------------------------------------------------------------------------
# the decision rule
# ---------------------------------------------------------------------------

def test_few_distinct_values_forces_median():
    """Rule 1: fewer than 3 distinct values -> median, before any test runs."""
    assert decide(np.array([1.0, 1.0, 2.0]))["kind"] == "median"


def test_fewer_than_three_values_forces_median():
    """Rule 1's other half: n < 3 -> median."""
    assert decide(np.array([4.0, 9.0]))["kind"] == "median"


def test_large_symmetric_sample_uses_mean_without_shapiro():
    """Rule 2, n > 300: |skewness| < 1 decides alone.

    R:  p <- (seq_len(400) - 0.5)/400; x <- qnorm(p)
        skewp <- function(x){m<-mean(x);s<-sqrt(mean((x-m)^2));mean((x-m)^3)/s^3}
        skewp(x)   # 1.784987304e-16
    """
    x = normal_grid(400)
    assert len(x) > 300
    assert decide(x)["kind"] == "mean"


def test_large_skewed_sample_uses_median():
    """Rule 2, n > 300: |skewness| >= 1 -> median, still with no Shapiro test.

    R:  p <- (seq_len(400) - 0.5)/400; x <- qexp(p); skewp(x)  # 1.902340974
    """
    x = exponential_grid(400)
    assert len(x) > 300
    assert decide(x)["kind"] == "median"


def test_shapiro_path_is_actually_consulted_between_3_and_300():
    """Rule 3: BOTH conditions must hold, so a symmetric-but-not-normal sample
    goes to median even though its skewness passes.

    A uniform grid is the discriminating case — skewness 0, and Shapiro-Wilk
    rejects hard. An implementation that decided on skewness alone (or skipped
    Shapiro at this size) would answer "mean" here.

    R:  p <- (seq_len(200) - 0.5)/200
        skewp(p)                      # 1.326894012e-16
        shapiro.test(p)$p.value       # 5.39206e-06   -> median
        g <- qnorm(p); skewp(g)       # 1.434846032e-15
        shapiro.test(g)$p.value       # 1            -> mean
    """
    uniform = _grid(200)
    assert 3 <= len(uniform) <= 300
    assert decide(uniform)["kind"] == "median"

    normal = normal_grid(200)
    assert decide(normal)["kind"] == "mean"


# ---------------------------------------------------------------------------
# number formatting
# ---------------------------------------------------------------------------

def test_three_significant_figures_with_trailing_zeros_dropped():
    """R: f <- function(v) format(signif(v, 3), trim = TRUE,
                                  scientific = FALSE, drop0trailing = TRUE)

    Every expectation below is that function's real output, not a reading of
    R/summarize.R's own source comment — which claims `1.125 -> "1.13"` and is
    WRONG. `signif` inherits round-half-to-even, and R prints 1.12.
    """
    assert fmt_num(12.3456) == "12.3"      # f(12.3456)
    assert fmt_num(1234.5) == "1230"       # f(1234.5)     -- sig figs, not dp
    assert fmt_num(0.00123456) == "0.00123"
    assert fmt_num(2.50) == "2.5"
    assert fmt_num(2.0) == "2"
    assert fmt_num(1.125) == "1.12"        # f(1.125)      -- half to EVEN
    assert fmt_num(1.135) == "1.14"        # f(1.135)
    assert fmt_num(250000) == "250000"     # plain, never 2.5e+05
    assert fmt_num(0) == "0"


def test_signif_rounds_the_scaled_value_the_way_r_does():
    """R's `signif` is `nearbyint(x * 10^e) / 10^e`, NOT a decimal-exact round.

    THE MECHANISM: the scaling multiply lands EXACTLY on a .5 tie, where
    `nearbyint` rounds half to EVEN — while a decimal-exact round of the double
    never sees a tie at all, because the double sits a hair above or below it.
    Which way they differ depends on the parity of the scaled integer, so this
    cannot be approximated by "round, but nudge ties down".

    Verified in Python (Decimal shows the exact double):
        Decimal(2.225)       -> 2.2250000000000000888...   above the tie
        Decimal(2.225 * 100) -> exactly 222.5 -> half-even -> 222 -> 2.22
        round(2.225, 2)      -> 2.23     <- what a decimal-exact rule answers
        Decimal(2.475 * 100) -> exactly 247.5 -> half-even -> 248 -> 2.48
        round(2.475, 2)      -> 2.48     <- agrees here, by coincidence
        Decimal(1.315)       -> 1.3149999999999999467...   BELOW the tie
        Decimal(1.315 * 100) -> exactly 131.5 -> half-even -> 132 -> 1.32
        round(1.315, 2)      -> 1.31     <- differs in the OTHER direction
    and in R:
        f(2.225); f(2.475); f(1.315)     # "2.22"  "2.48"  "1.32"

    2.225 and 2.475 are real cells — crp's Treatment and Control first
    quartiles in the shipped summary-table1 case, displayed as "2.22" and
    "2.48". 1.315 is the discriminating probe in the opposite direction.
    """
    assert fmt_num(2.225) == "2.22"
    assert fmt_num(2.475) == "2.48"
    assert fmt_num(1.315) == "1.32"


# ---------------------------------------------------------------------------
# cells
# ---------------------------------------------------------------------------

def test_median_cell_uses_type_7_quartiles():
    """R:  x <- c(1,2,3,4,5,6,7,8,30)
           skewp(x)                          # 2.158328  -> |skew| >= 1
           shapiro.test(x)$p.value           # 0.0003238335
           quantile(x, c(.25,.5,.75), names = FALSE, type = 7)   # 3 5 7

    numpy's default method="linear" IS R's type 7. The 30 is what routes this
    to median (a bare 1..9 is symmetric enough that Shapiro passes at
    p = 0.913561 and the app answers MEAN — see the next test); the quartiles
    are unchanged by it, so the expected cell is still the brief's "5 (3-7)".
    """
    df = pd.DataFrame({"x": [str(v) for v in [1, 2, 3, 4, 5, 6, 7, 8, 30]]})
    out = summarize(df, ["x"])
    row = next(r for r in out["rows"] if r["variable"] == "x")
    assert row["kind"] == "median"
    assert row["cells"]["Overall"] == "5 (3–7)"   # EN DASH U+2013


def test_type_7_quartiles_interpolate_between_order_statistics():
    """The interpolating case, so a type-1/type-6 implementation is caught.

    R:  y <- c(1,2,3,4,5,6,7,8,9,40)
        quantile(y, c(.25,.5,.75), names = FALSE, type = 7)  # 3.25 5.5 7.75
        shapiro.test(y)$p.value  # 4.04447e-05 -> median
    """
    df = pd.DataFrame({"y": [str(v) for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 40]]})
    row = next(r for r in summarize(df, ["y"])["rows"] if r["variable"] == "y")
    assert row["kind"] == "median"
    assert row["cells"]["Overall"] == "5.5 (3.25–7.75)"


def test_mean_cell_is_the_sample_sd_denominator_n_minus_1():
    """R:  x <- 1:9; shapiro.test(x)$p.value  # 0.913561 -> mean
           f(mean(x)); f(sd(x))              # 5    2.74

    `sd` is the SAMPLE standard deviation (n - 1). numpy's default `std()` is
    the population one (ddof=0), which would render 2.58 here.
    """
    df = pd.DataFrame({"x": [str(v) for v in range(1, 10)]})
    row = next(r for r in summarize(df, ["x"])["rows"] if r["variable"] == "x")
    assert row["kind"] == "mean"
    assert row["cells"]["Overall"] == "5 ± 2.74"   # U+00B1


def test_categorical_cell_is_count_and_whole_number_percent():
    """R:  sprintf("%d (%.0f%%)", k, 100 * k / denom)

    NOT `.fmt_num`: whole-number percent, and half-to-even like C's printf.
    R-verified: sprintf("%.0f", 12.5) is "12"; sprintf("%.0f", 37.5) is "38".
    So 1 of 8 renders "1 (12%)" and 3 of 8 renders "3 (38%)".
    """
    df = pd.DataFrame({"g": ["A"] * 8, "v": ["x"] + ["y"] * 7})
    out = summarize(df, ["v"], group="g")
    cells = {r.get("level"): r["cells"]["A"] for r in out["rows"]
             if r["variable"] == "v" and r.get("level") is not None}
    assert cells["x"] == "1 (12%)"
    assert cells["y"] == "7 (88%)"     # sprintf("%.0f", 87.5) -> "88"

    df3 = pd.DataFrame({"g": ["A"] * 8, "v": ["x"] * 3 + ["y"] * 5})
    out3 = summarize(df3, ["v"], group="g")
    cells3 = {r.get("level"): r["cells"]["A"] for r in out3["rows"]
              if r["variable"] == "v" and r.get("level") is not None}
    assert cells3["x"] == "3 (38%)"    # sprintf("%.0f", 37.5) -> "38"
    assert cells3["y"] == "5 (62%)"    # sprintf("%.0f", 62.5) -> "62"


def test_blank_categorical_cells_leave_the_percentage_denominator():
    """A blank is excluded from the counts AND from the denominator, and the
    row is NOT dropped: 2 of 4 non-blank is 50%, not 2 of 6 (33%)."""
    df = pd.DataFrame({"v": ["x", "x", "y", "y", "", ""]})
    out = summarize(df, ["v"])
    cells = {r.get("level"): r["cells"]["Overall"] for r in out["rows"]
             if r["variable"] == "v" and r.get("level") is not None}
    assert cells["x"] == "2 (50%)"
    assert cells["y"] == "2 (50%)"
    assert out["n"] == 6
    assert out["n_dropped"] == 0


# ---------------------------------------------------------------------------
# the grouped rule — the one most likely to be got wrong
# ---------------------------------------------------------------------------

def test_grouped_decision_is_made_once_on_group_centred_values():
    """The decision is made ONCE per variable, on GROUP-MEAN-CENTRED values,
    then applied to every group's cell.

    Two groups, each a perfect normal grid, shifted 10 apart. Pooling them
    UNCENTRED gives a bimodal mixture that Shapiro rejects; centring within
    groups gives a clean normal. The app centres, so the answer is mean.

    R:  pa <- (seq_len(30) - 0.5)/30; a <- qnorm(pa) + 5; b <- qnorm(pa) + 15
        shapiro.test(c(a, b))$p.value                       # 1.37928e-07
        shapiro.test(c(a - mean(a), b - mean(b)))$p.value   # 0.970325
        f(mean(a)); f(sd(a))   # 5    0.996
        f(mean(b)); f(sd(b))   # 15   0.996

    An implementation that pooled the raw values would answer median, and its
    A cell would read "5 (4.35–5.65)" (R: quantile(a, c(.25,.5,.75), type=7)).
    An implementation that decided PER GROUP would also answer mean here, so
    the pooled/centred distinction is what this test pins; the "once" half is
    pinned by both groups sharing one kind below.
    """
    grid = normal_grid(30)
    a, b = grid + 5.0, grid + 15.0
    df = pd.DataFrame({
        "g": ["A"] * 30 + ["B"] * 30,
        "x": [repr(float(v)) for v in np.concatenate([a, b])],
    })
    out = summarize(df, ["x"], group="g")
    row = next(r for r in out["rows"] if r["variable"] == "x")

    assert row["kind"] == "mean", (
        "the decision must be made on group-mean-centred values; pooling the "
        "raw values makes this bimodal and yields median")
    assert row["cells"]["A"] == "5 ± 0.996"
    assert row["cells"]["B"] == "15 ± 0.996"
    assert out["levels"] == ["A", "B"]
    assert out["n_per_group"] == {"A": 30, "B": 30}


def test_group_levels_are_in_first_appearance_order_not_sorted():
    """R: `levels_g <- unique(grp)` — first appearance, never sort()."""
    df = pd.DataFrame({"g": ["Zebra", "Zebra", "Alpha", "Alpha"],
                       "v": ["1", "2", "3", "4"]})
    out = summarize(df, ["v"], group="g")
    assert out["levels"] == ["Zebra", "Alpha"]


# ---------------------------------------------------------------------------
# the shipped case, end to end
# ---------------------------------------------------------------------------

def test_the_shipped_case_reproduces_the_displayed_table():
    """Every constant here is what `fig_summary` actually printed for
    stats-validation/cases/summary-table1 — captured from a real
    `render_figure()` run, not recomputed. See spec/summary-table1.md.
    """
    df = pd.read_csv(CASE_CSV, dtype=str, keep_default_na=False)
    out = summarize(df, ["age", "length_of_stay", "crp", "sex", "diabetes"],
                    group="arm")
    assert out["n"] == 120
    assert out["n_dropped"] == 0
    assert out["levels"] == ["Control", "Treatment"]
    assert out["n_per_group"] == {"Control": 60, "Treatment": 60}

    by_key = {(r["variable"], r.get("level")): r for r in out["rows"]}
    expected = {
        ("age", None): ("mean", "59.6 ± 11.1", "60.2 ± 11.4", "0"),
        ("length_of_stay", None): ("median", "3.7 (2.25–6)",
                                   "4.1 (2–7.3)", "8"),
        ("crp", None): ("median", "4.5 (2.48–7.15)",
                        "4.85 (2.22–8.45)", "0"),
        ("sex", None): ("count", "", "", "0"),
        ("sex", "Female"): ("count", "32 (53%)", "28 (47%)", ""),
        ("sex", "Male"): ("count", "28 (47%)", "32 (53%)", ""),
        ("diabetes", None): ("count", "", "", "0"),
        ("diabetes", "No"): ("count", "32 (53%)", "44 (73%)", ""),
        ("diabetes", "Yes"): ("count", "28 (47%)", "16 (27%)", ""),
    }
    for key, (kind, control, treatment, missing) in expected.items():
        row = by_key[key]
        assert row["kind"] == kind, key
        assert row["cells"]["Control"] == control, key
        assert row["cells"]["Treatment"] == treatment, key
        assert row["missing"] == missing, key

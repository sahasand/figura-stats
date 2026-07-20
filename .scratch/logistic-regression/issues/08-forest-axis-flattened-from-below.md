# 08 — A very protective term can still flatten the forest axis (both cox and logistic)

Status: resolved
Type: task
Found: 2026-07-20, during review of `fix/cox-forest-and-preview` (issue 05's fix closed the upper tail only)

## Problem

`.cox_forest_svg` (`R/cox.R:225-226`) and `.logistic_forest_svg` (`R/logistic.R:214`) both
bound only the **upper** confidence limit:

```r
keep <- is.finite(...) & exp(jci[, 2]) <= 1e6
```

A term whose effect is extreme in the protective direction produces a CI that is finite,
raises no fit warning, and sits far below the 1e6 bound — so it is kept. Because the
x-axis is `scale_x_log10()` and shared across terms, it flattens every other covariate just
as effectively as a runaway upper bound does. Issue 05 fixed the upper tail; this is the
same symptom from the other direction.

## Failing scenario

Reproduced during the review of issue 05 using the mirror of that branch's own fixture
(`mk_cox_rows_huge()` with `lp <- -15 * x`):

- joint fit does **not** warn
- `x`'s adjusted CI is `1.46e-11 – 1.78e-07` — both limits finite, both far under 1e6
- the term is kept and plotted, spanning ~11 decades
- a healthy co-covariate (`arm: Treated`, `0.31 – 0.69`) collapses to a hairline

## Fix

Add the symmetric lower bound alongside the existing upper one, in **both** files:

```r
& exp(<lower>) >= 1e-6
```

Two decisions to make explicitly rather than by default:

1. **Threshold symmetry.** `1e-6` is the reciprocal of the existing `1e6`. Confirm that is
   the intent rather than picking an independent floor.
2. **Table/plot consistency.** `.logistic_or_cell` (`R/logistic.R:151`) already applies
   `hi > 1e6` to the table, so adding a plot-only lower bound would make *logistic*
   asymmetric in the way issue 09 describes for cox. Decide whether the lower bound belongs
   in the cell functions too — note that adding it there **moves numbers currently printed
   in shipped output**, which needs owner sign-off.

## Test

`tests/testthat/test-cox.R` and `tests/testthat/test-logistic.R` — a fixture with one
extremely protective term and one healthy term; assert the healthy term's label is present
in the forest SVG and the extreme term's is not. Confirm RED against the current bound.

## Comments

Resolved on `main`, with issue 09 (same decision).

Both explicit decisions the issue asked for, made deliberately:

1. **Threshold symmetry — yes, 1e-6 is the reciprocal of 1e6, by intent.** The bound exists
   to catch "this fit carries no usable information about this term", and that condition is
   sign-agnostic: an OR of 1e-11 destroys a shared log axis exactly as an OR of 1e11 does.
   A single reciprocal pair also means one number to reason about rather than two.
2. **The lower bound belongs in the cell functions too, not only the plots.** Putting it in
   the plot alone would have made logistic asymmetric in precisely the way issue 09
   describes for cox — the bug, moved rather than fixed.

The rule now lives once, as `.ratio_reportable()` in `R/dispatch.R`, and both analyses call
it from both their cell formatter and their forest filter.

This moved an existing test. `test-logistic.R`'s "an unreliable UNADJUSTED cell is
explained in the methods text" built its fixture with `x <- z + rnorm(n, 0, 0.3)`, which
left x's ADJUSTED CI at 3.8e-07 – 1.4e+04 — eleven decades, printed in the shipped table as
"0.07 (0.00–13730.00, p=0.672)". The symmetric rule correctly refuses that, which would
have made both columns unreliable and silently destroyed the test's premise. The fixture's
noise sd moved 0.3 -> 0.6 to restore the intended contrast; **every assertion is unchanged**,
and the reason is recorded in the test itself. That cell is the clearest evidence the
one-sided rule was wrong: an eleven-decade interval was shipping as a finding.

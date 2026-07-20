# 05 — Cox forest plot has no reliability filter, so an unestimable term can flatten the axis

Status: ready-for-agent
Type: task
Found: 2026-07-20, during the whole-branch review of `fix/cox-shell-issues` (deferred: out of scope for that branch, which was scoped to four tracked defects)

## Problem

The Cox table and the Cox forest plot disagree about which estimates are trustworthy.

`.cox_hr_cell` (`R/cox.R:107-109`) refuses to print an HR on **two** grounds:

```r
if (!is.null(warn) || !is.finite(est) || !is.finite(lo) || !is.finite(hi))
  return("not reliably estimated")
```

— a non-finite estimate/CI **or** a captured `coxph` fit warning (`.cox_fit_one`,
`R/cox.R:87-93`, records e.g. "Loglik converged before variable ...; coefficient may be
infinite").

`.cox_forest_svg` (`R/cox.R:219`) filters on only the first:

```r
keep <- is.finite(jc) & is.finite(jci[, 1]) & is.finite(jci[, 2])
```

The logistic sibling, `.logistic_forest_svg` (`R/logistic.R:214`), additionally caps the
upper bound:

```r
keep <- is.finite(or) & is.finite(lo) & is.finite(hi) & hi <= 1e6
```

## Failing scenario

A covariate with near-complete separation of events (a rare level where every subject has
the event, routine in a small subgroup) fits with a huge finite coefficient and a huge
finite CI, and `coxph` emits a convergence warning. Then:

- the table cell reads **"not reliably estimated"** (the warning branch fires), but
- the forest plot still draws that term, with an upper CI of, say, 10^8.

Because the forest x-axis is `scale_x_log10()` and shared, every other covariate's CI
collapses into a hairline at the left edge. The figure a user downloads for a manuscript
is unreadable, and it plots an interval the table just declined to report — the same
number presented two contradictory ways in one output.

## Fix

Bring `.cox_forest_svg`'s `keep` up to the union of the two existing rules:

1. pass `fits$joint$warn` into the filter (or, cleaner, have `.cox_forest_svg` drop every
   term when the joint fit warned, mirroring how `.cox_hr_cell` treats a warned fit —
   decide which, but be explicit; the joint warning is not per-term, so per-term dropping
   is not directly available from `warn`);
2. add the `hi <= 1e6` bound that `.logistic_forest_svg` already applies.

The existing `if (!any(keep)) return("")` early return already handles the case where
everything is filtered out, so no new empty-plot path is needed.

## Test

`tests/testthat/test-cox.R` — build a covariate with a separated level so `coxph` warns,
then assert that the term's HR cell reads "not reliably estimated" **and** that the forest
SVG does not carry its label. Confirm the assertion is RED against the current `keep`
before relying on it.

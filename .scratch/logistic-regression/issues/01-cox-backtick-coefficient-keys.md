# 01 — Cox HR cells read "not reliably estimated" for column names with spaces

Status: resolved
Type: task
Found: 2026-07-20, during the logistic-regression build (left unfixed by owner decision to keep that branch scoped)

## Problem

`R/cox.R` writes its formulas with backticked column names:

- `R/cox.R:89` — `survival::Surv(time, status) ~ \`%s\`` (univariable)
- `R/cox.R:91` — the joint formula, same backticking

so `coxph`'s coefficient names for a non-syntactic column are `` `study arm`Treated ``. But the row lookup keys are built from the **bare** name:

- `R/cox.R:129` — `key <- paste0(cl, l)` → `"study armTreated"`

The key never matches `rownames(smat)`, so `.cox_hr_cell` returns `"not reliably estimated"` for **every** level of that covariate. A CSV header containing a space — routine in clinical exports — therefore renders a whole covariate as unestimable. This is wrong output presented as a statistical statement, not an error.

## Fix

Mirror `R/logistic.R`, which solved exactly this:

```r
.logistic_term_label <- function(cl) {
  if (identical(make.names(cl), cl)) cl else sprintf("`%s`", cl)
}
```

Use the same label function to build the lookup key in `.cox_rows` (and anywhere else cox derives a coefficient name from a column name, including the forest-plot row matcher). Add a regression test with a space-containing covariate header.

## Comments

Fixed on `fix/cox-shell-issues`. Added `.cox_term_label()` (mirrors
`.logistic_term_label`) and used it for the coefficient lookup key in `.cox_rows`
for **both** the numeric branch (previously `uc[cl]`) and the categorical branch
(previously `paste0(cl, l)`). Also fixed `.cox_forest_svg`'s labeller, which had
two latent bugs beyond the one reported: it matched covariates in `p$covs` order,
so `age` claimed `age2`'s coefficient and the duplicate label made
`factor(levels = rev(...))` **error out**, killing the whole forest plot; and it
stripped the prefix with `sub(paste0("^", cl), "", key)`, treating the column name
as a regex. Now: longest-term-label-first ordering + literal `substring()` strip.
Regression tests in `tests/testthat/test-cox.R` cover the space-headered covariate
(table cells and forest labels) and the `age`/`age2` prefix case.

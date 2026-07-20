# 01 — Cox HR cells read "not reliably estimated" for column names with spaces

Status: ready-for-agent
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

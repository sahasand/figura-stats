# Path B interface contract

Path B modules are written from `stats-validation/spec/<case>.md` ONLY. The
statistical behaviour is fully determined by the spec; this file pins only the
call signatures and return shapes the harness and comparator depend on.

## validate/io.py

- `load_case(case_dir) -> (DataFrame, dict)` — reads `<case_dir>/data.csv` and
  `<case_dir>/case.json`. Every CSV cell is preserved as written text (no type
  guessing, no missing-value substitution at load time — the spec defines what
  counts as missing).
- `code_event(series, event_value, blank_is_missing=False) -> Series[float]` —
  1.0 when a cell is an event per the spec's outcome-coding rule, 0.0
  otherwise; NaN for blank cells when `blank_is_missing=True`.
- `complete_cases(df, columns) -> (DataFrame, int)` — the kept rows and the
  dropped-row count, per the spec's Population rule.
- `to_numeric(series) -> Series` — numeric coercion, non-numeric to NaN.
- `treatment_dummies(values, reference) -> (dict[level, Series[float]], str)` —
  0/1 indicator columns for non-reference levels plus the resolved reference
  level, per the spec's covariate-coding rule (including the fallback when the
  declared reference is absent).

## validate/logistic.py

- `fit_logistic(df, outcome, event_value, covariates, ref_levels, increments)
  -> dict` with keys:
  - `terms`: `{term: {est, lo, hi, p}}` — adjusted (joint-model) estimates on
    the ratio scale. Term naming: continuous covariate → the column name;
    categorical level → column name immediately followed by the level string
    (e.g. `armNew treatment`).
  - `unadjusted`: same shape, one univariable model per covariate.
  - `n`, `n_event`, `n_dropped`: integers.
  - `c_statistic`: float.
- `reportable(cell) -> bool` — whether a `{est, lo, hi, p}` cell is reportable
  per the spec's Reportability rule.

Report all floats at full precision — never round inside the module.

## validate/cox.py

- `fit_cox(df, time, status, event_value, covariates, ref_levels,
  increments=None) -> dict` with keys:
  - `terms`: `{term: {est, se, lo, hi, p}}` — adjusted (joint-model) hazard
    ratios on the ratio scale. `se` is REQUIRED — the raw log-scale standard
    error. Term naming is identical to `fit_logistic`: continuous covariate
    → the column name; categorical level → column name immediately followed
    by the level string (e.g. `armNew treatment`).
  - `unadjusted`: same shape, one univariable Cox model per covariate.
  - `n`, `n_event`, `n_dropped`: integers.

Report all floats at full precision — never round inside the module.

**Numerical precision.** Cox's partial-likelihood optimum is found
iteratively, unlike logistic's closed-form-per-step IRLS — verified
empirically (a throwaway solver run against both the real `cox-adjusted`
case and a small heavily-tied fixture) that a correctly-Efron-fitted model
can still land ~1e-5 relative from R's `survival::coxph` optimum on
est/lo/hi/p at a solver's default stopping tolerance — not a modelling
error, just an under-converged fit. A default-tolerance solver therefore
risks a false DEFECT: `stats-validation/python/tests/test_cox.py`'s
tied-times acceptance test enforces rel 1e-6, the same tolerance the exact
tier's comparator gate (`compare.py`'s `REL_TOL`) enforces. Converge well
past whatever your solver's defaults are before returning — tightening the
convergence criteria closed the same gap to ~1e-8 in the same check.

## validate/km.py

- `fit_km(df, time, status, event_value, group) -> dict` with keys:
  - `curve`: `{group_level: [{"t", "surv", "at_risk"}, ...]}` — one entry per
    DISTINCT EVENT time (a pure-censoring time contributes no row). `t` is
    the raw parsed number, never rounded — the comparator matches curve
    points by exact float equality, per the spec's own tie/precision
    convention (both paths parse the same CSV strings).
  - `medians`: `{group_level: float | None}` — `None` means the median was
    not reached, never a sentinel value (e.g. never the group's largest
    observed time). Per the spec's median rule (`spec/km-twoarm.md`), this
    is R's own "minmin" rule, not the naive "smallest t with S(t) <= 0.5"
    reading of the formula.
  - `logrank_p`: `float | None` — `None` when there are fewer than two
    groups (a log-rank test needs at least two to compare).
  - `n`, `n_event`, `n_dropped`: integers.
  - **Group keys are the literal group-column strings** (e.g. `"Standard
    care"`), identical between `curve` and `medians` — never a synthetic
    label like `"Overall"` for a single-group case; a group key is always
    one of the values actually present in the group column after the
    Population filter.

Report all floats at full precision — never round inside the module.

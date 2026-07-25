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

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

## validate/groupcompare.py

- `compare_groups(df, outcome, group, nonparametric=None) -> dict` with keys:
  - `test_name`: `str` — the app's own test-name string, verbatim, including
    its EN DASHes: one of `"Welch t-test"`, `"Mann–Whitney U test"`,
    `"one-way ANOVA (Welch)"`, `"Kruskal–Wallis test"`,
    `"Pearson chi-square test"`, `"Fisher's exact test"`.
  - `p_value`: `float` — the omnibus test's two-sided p-value.
  - `statistic`: `float | None` — the chosen test's own statistic (`t`, `W`,
    Welch `F`, tie-corrected `H`, or the UNCORRECTED Pearson chi-square).
    **`None` for Fisher's exact test, which structurally has none** — R's
    htest carries no `statistic` component there. Never substitute the
    chi-square statistic in its place; the comparator encodes "a null
    statistic is not-applicable for Fisher, and MISSING_QUANTITY for anything
    else".
  - `effect`: `{"label": str, "value": float, "lo": float | None,
    "hi": float | None}` — value-plus-label, NOT a pre-rendered display
    string; the comparator restates R's own `.fmt_num`/`.gc_ci_phrase`
    formatting itself, so the effect is judged at full precision with a
    display-artifact tier of its own. `label` is the app's own effect name,
    verbatim, including its accent: `"Cohen's d"`, `"rank-biserial r"`,
    `"eta-squared"`, `"epsilon-squared"`, `"Cramér's V"`. `lo`/`hi` are
    `None` for exactly the two effects the app reports without an interval
    (epsilon-squared and Cramér's V) and floats for the rest.
  - `n_per_group`: `{group level: int}` — surviving groups only, keyed by the
    literal group-column strings (never a synthetic or normalised label).
  - `n`, `n_dropped`: integers. `n_dropped` is the TOTAL not analysed —
    missing-value drops plus, in the numeric branch, rows in groups left with
    fewer than two values.
  - `posthoc`: `None`, or `{"test": str, "significant_pairs": [str, ...]}`.
    `None` and `{"significant_pairs": []}` are DIFFERENT claims: `None` means
    no post-hoc ran at all (fewer than three groups, or an omnibus p >= 0.05,
    or the categorical branch, which never runs one), while an empty list
    means one ran and no pair survived adjustment. Pair names follow the app's
    two MUTUALLY OPPOSITE conventions — Tukey's `"<later>-<earlier>"`, from
    R's own `TukeyHSD` row labels, and Dunn's `"<earlier>-<later>"`, from the
    app's own pairing loop. Do not normalise them to one order.

`nonparametric` is the parametric/non-parametric override: `None` runs the
spec's routing rule, `True`/`False` force the branch. It is ignored entirely in
the categorical branch, which has no such routing decision.

Report all floats at full precision — never round inside the module.

**No 2x2 odds ratio in this contract.** The app additionally displays an odds
ratio beside Cramér's V when a categorical table is exactly 2x2. No shipped
case is 2x2, and `compare_groups` does not report it; the comparator detects
that clause in the displayed text and raises MISSING_QUANTITY rather than
ignoring it, so adding such a case requires extending this contract first.

**Fisher's exact test must be exact.** For r x c tables `scipy.stats.
fisher_exact` runs a MONTE CARLO test (measured: two different answers from two
calls on the identical 3x3 input, scipy 1.16.1) and cannot meet the 1e-6 exact
tier. Enumerate the fixed-margin tables instead — an exhaustive enumeration was
verified against R to within 1e-14 relative. The 2x2 path is genuinely exact
and reproduces R.

## validate/summary.py

- `summarize(df, variables, group=None) -> dict`. `variables` is the flat list
  of columns to summarize, in display order; `group` is the group column name or
  `None`. **`summarize` classifies continuous vs categorical itself, from the
  data** — the same rule the app's `classifyColumns` applies (a numeric column
  with MORE THAN FIVE distinct non-missing values is continuous; anything else
  is categorical). The case's declared `roles.continuous`/`roles.categorical`
  split is the COMPARATOR's expectation, never an input to Path B.

  Returned keys:
  - `rows`: `[{variable, level, kind, cells, missing}, ...]` — one entry per
    displayed table row, in display order (all continuous variables first, in
    `variables` order, then all categorical variables, each as a header row
    followed by its level rows).
    - `variable`: `str` — the bare column name. Never the displayed
      `"<variable>, mean ± SD"` label.
    - `level`: `str | None` — the level string on a categorical LEVEL row;
      `None` on a continuous row and on a categorical header row.
    - `kind`: `"mean" | "median" | "count"`. **The kind is a property of the
      VARIABLE, not of the row**: a categorical variable's header row and all
      of its level rows carry `"count"`, so one decision per variable can be
      read off either side. This is the `decisions` quantity the comparator
      compares under its own code, `DECISION_MISMATCH` — for Table 1 the
      CHOICE of summary statistic is itself a validated output.
    - `cells`: `{group level: str}` — the **rendered cell strings**, not
      numbers. At three significant figures the string IS the published claim,
      so the comparator compares them exactly and Table 1 has no
      display-artifact tier. Render per `spec/summary-table1.md`: `"M ± SD"`
      (U+00B1), `"Q2 (Q1–Q3)"` (EN DASH U+2013, type-7 quartiles),
      `"k (p%)"` (whole-number percent, `%.0f`, half-to-even), `"—"` (U+2014)
      for an empty group, and the bare formatted value for a group with exactly
      one non-missing value.
    - `missing`: `str` — the rendered Missing cell; `""` on a level row.
  - `levels`: `[str]` — the group levels in DISPLAY order (first appearance in
    the file, not sorted). `["Overall"]` when `group` is `None`.
  - `n_per_group`: `{group level: int}` — every row in the group, including rows
    missing the variable under summary.
  - `n`: `int` — total rows. `n_dropped`: `int` — **always 0**; Summary has no
    complete-case filter and never drops a row. It is reported so the count tier
    has the same shape as every other analysis's, and so that an implementation
    that silently starts dropping rows is caught.

  Two module-level helpers are additionally part of the contract, because the
  acceptance tests in `tests/test_summary.py` exercise them directly:
  - `decide(x) -> dict` with at least `{"kind": "mean" | "median"}` — the
    mean-vs-median rule of `spec/summary-table1.md`, on an array of values.
  - `fmt_num(v) -> str` — R's `.fmt_num`, three significant figures, plain
    notation, trailing zeros dropped, **round-half-to-even at the tie**
    (`1.125` renders `"1.12"`). Note that R's `signif` rounds the SCALED value
    `x * 10^e`, not the exact decimal expansion of the double — and the
    difference is that the multiply can land *exactly* on a `.5` tie, where
    half-to-even applies, while a decimal-exact round never sees a tie. So
    `2.225` renders `"2.22"` (`2.225 * 100` is exactly `222.5`; half-to-even
    gives `222`, whereas `round(2.225, 2)` gives `2.23`) and `1.315` renders
    `"1.32"` (`131.5` -> `132`, whereas `round(1.315, 2)` gives `1.31`).
    `compare.py`'s `_signif` restates that algorithm; both probes are pinned in
    `tests/test_summary.py` and `compare/tests/test_compare.py`.

Cells are rendered strings by design; every other quantity is at full precision.

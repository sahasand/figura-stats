# Decisions — validate/cox.py

Silent-spec interpretation choices made while implementing `fit_cox`, recorded
per the task's strict rules.

## Ties method
lifelines' `CoxPHFitter` always resolves tied event times in the partial
likelihood via Efron's method (`_newton_raphson_for_efron_model` /
`_get_efron_values_*` in `lifelines/fitters/coxph_fitter.py`), independent of
its `baseline_estimation_method` constructor argument (default `"breslow"`,
which only controls how the *baseline hazard* is estimated afterwards, not
how ties are handled during coefficient estimation). Confirmed by reading the
library source — there is no Breslow-ties code path to accidentally select.
Left `baseline_estimation_method` at its default since it has no effect on
the reported coefficient/se/p, which come from `params_`/`standard_errors_`
before any baseline-hazard step.

## Numerical precision
Passed `fit_options={"precision": 1e-11, "r_precision": 1e-13, "max_steps":
1000}` to `CoxPHFitter.fit`, per INTERFACES.md's numerical-precision note and
the values it reports as empirically closing the gap to R's `coxph` optimum
to ~1e-8–1e-10 relative. lifelines' own defaults (`precision=1e-7,
r_precision=1e-9, max_steps=500`) were confirmed too loose for the test
suite's rel-1e-6 tied-times fixture.

## p-value
Computed as the two-sided Wald p-value `2 * norm.sf(abs(coef / se))` using
`scipy.stats.norm.sf` (survival function, more accurate in the tail than
`1 - cdf`), matching R's `coxph` convention (`2 * pnorm(-abs(z))`). Not taken
from lifelines' own `summary()`/`_compute_p_values()` to avoid any extra
rounding or formatting inside that path — computed directly from `params_`
and `standard_errors_`.

## Time validity
The spec requires dropping rows where time is blank (via the Population
complete-case rule) *and, separately*, rows where a present time value fails
to parse as a number or parses negative — both counted into one `n_dropped`
total. Implemented as two sequential filters: `io.complete_cases` first (over
`[time] + covariates`, deliberately excluding `status`, per spec), then a
second mask `to_numeric(time).notna() & (time >= 0)` applied only to the
survivors of the first filter. Both drop counts are summed.

## Status coding
Reused `io.code_event` with its default `blank_is_missing=False`, which
implements the spec's Cox-specific rule exactly: a blank status cell is
*not* missing and codes as censored (0.0), unlike logistic's outcome coding.
No `blank_is_missing=True` override is passed anywhere in this module.

## Covariate construction
Reused `logistic.py`'s private `_covariate_matrix` helper (treatment
contrasts via `io.treatment_dummies`, reference-level fallback to the most
frequent remaining level, alphabetical ordering of non-reference levels,
continuous covariates divided by an optional per-covariate increment) rather
than reimplementing it, since the Covariates section of this spec states the
identical rule the logistic module already encodes, and the task brief
explicitly permits reusing prior-team helpers for consistency.

## `increments` parameter
`fit_cox`'s `increments` defaults to `None` per INTERFACES.md; treated as an
empty dict internally so every continuous covariate falls back to increment
1 (i.e., its raw scale), matching the spec's "age — reported per 1 unit (no
rescaling)" requirement. No case in this spec passes a non-default
increment.

## `se` field
Reported as lifelines' `standard_errors_` value directly — the raw log-scale
(coefficient-scale) standard error — never rounded, and used both to report
`se` itself and to derive `lo`/`hi` via the spec's literal `± 1.96 × se` on
the log scale before exponentiating.

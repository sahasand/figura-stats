# Analysis spec: cox-adjusted

Input: `stats-validation/cases/cox-adjusted/data.csv`.

## Population
Complete cases only. Drop any row where the time, the status, or either of
the two covariates is missing or an empty string. Report the number dropped.
A blank cell is missing. The literal string `NA` is an ordinary value, not
missing — do not treat it as NA.

A time value that is blank is missing, per the rule above. A time value that
is present but does not parse as a number, or parses to a negative number,
cannot be used as a survival time; treat that row as missing too — drop it
and count it in the same dropped total.

## Status coding
The status column is `status`. A row is an event when its value equals the
string `"Death"`. If both the cell and `"Death"` parse as numbers, numeric
equality also counts. Everything else — any non-blank value other than
`"Death"` — is censored at its recorded time value. A blank status cell is
missing (see Population), not censored.

## Covariates
- `arm` — categorical, reference level `"Standard care"`.
- `age` — continuous, reported per 1 unit (no rescaling).

If a declared reference level is absent from the data after complete-case
filtering, the reference level is instead the most frequent remaining level.

Categorical covariates use treatment contrasts: the reference level first,
remaining levels in alphabetical order.

## Models
Cox proportional-hazards regression, partial likelihood, **Efron** handling
of tied event times.
1. For each covariate, a univariable Cox model of the time/status pair on
   that covariate alone. This gives the unadjusted hazard ratio.
2. One multivariable Cox model of the time/status pair on both covariates
   jointly. This gives the adjusted hazard ratios.

## Reported quantities
Per covariate term: hazard ratio = exp(coefficient); 95% CI =
exp(coefficient ± 1.96 × standard error) — the literal constant 1.96, not the
exact normal quantile; two-sided Wald p-value.

Also report: n analysed, number of events, and number of rows dropped.

## Reportability
A hazard ratio cell is reported only when the estimate and both CI bounds are
finite and the interval lies within [1e-6, 1e6]. Otherwise the cell reads
"not reliably estimated".

## Display
`%.2f (%.2f–%.2f, p=%.3f)` with an en-dash separator; when p < 0.001 the
p-part reads `p<0.001`.

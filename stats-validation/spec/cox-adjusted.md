# Analysis spec: cox-adjusted

Input: `stats-validation/cases/cox-adjusted/data.csv`.

## Population
Complete cases on the time column and the covariates only. Drop any row
where the time or either of the two covariates is missing or an empty
string. Report the number dropped as `n_dropped`. A blank cell is missing.
The literal string `NA` is an ordinary value, not missing — do not treat it
as NA.

The status column is deliberately excluded from this completeness check —
see Status coding below for why a blank status cell is never dropped.

A time value that is blank is missing, per the rule above. A time value that
is present but does not parse as a number, or parses to a negative number,
cannot be used as a survival time; treat that row as missing too — drop it
and count it in the same dropped total.

## Status coding
The status column is `status`. A row is an event when its value equals the
string `"Death"`. If both the cell and `"Death"` parse as numbers, numeric
equality also counts. **Everything else is censored at its recorded time
value, including a blank cell.** A blank status cell is not missing and is
not dropped from the analysis — it is coded as censored, exactly like any
other non-event value.

This is a deliberate departure from logistic regression's outcome coding,
where a blank outcome cell IS treated as missing and the row IS dropped. The
two figures code a blank event-like cell differently on purpose, to match
the app's real behavior: `R/cox.R`'s status derivation never maps a blank
cell to missing before testing it against the event value, so `"" == "Death"`
evaluates to false and the row survives as censored; `R/logistic.R`'s
outcome derivation explicitly rewrites a blank cell to missing before the
same comparison, so the row is dropped. Implement Cox's rule as written
above — do not port logistic's blank-is-missing outcome handling here.

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

## Known display nuance
The app's own on-screen table computes its displayed 95% CI by calling R's
`confint()` generic on the fitted joint `coxph` object. The `survival`
package defines no `confint.coxph` method, so this call falls through to
`stats::confint.default`, which uses the exact normal quantile
`qnorm(0.975) = 1.959963985` — not the literal constant `1.96` that this
spec's Reported quantities section requires. Logistic regression has no
such gap: `R/logistic.R`'s displayed cell is hand-computed with the literal
1.96 directly, so its on-screen CI already matches this spec's rule
exactly.

The app's displayed Cox CI and this spec's literal-1.96 rule therefore
differ by roughly `(1.959963985 - 1.96) / 1.96 ≈ 1.8e-5` relative on the z
multiplier itself — almost always invisible after rounding to 2 decimal
places, but occasionally close enough to a `.xx5` rounding boundary that a
bound computed with one z constant rounds to a different displayed digit
than the same bound computed with the other. Do not resolve this by
changing the literal 1.96 anywhere in this pipeline (this spec, the
harvester, or an independent implementation) — 1.96 is the pinned
convention that keeps the exact tier and the script tier self-consistent.
A Cox-only single-digit CI-bound mismatch that lands exactly at a rounding
boundary is this known nuance, not a defect; rule it out before escalating
one.

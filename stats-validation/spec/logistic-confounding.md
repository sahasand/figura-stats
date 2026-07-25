# Analysis spec: logistic-confounding

Input: `stats-validation/cases/logistic-confounding/data.csv`.

## Population
Complete cases only. Drop any row where the outcome or any of the three
covariates is missing or an empty string. Report the number dropped. A blank
cell is missing. The literal string `NA` is an ordinary value, not missing —
do not treat it as NA.

## Outcome coding
The outcome column is `complication`. A row is an event (y = 1) when its
value equals the string `"Yes"`. If both the cell and `"Yes"` parse as
numbers, numeric equality also counts. Everything else is y = 0. A blank
cell is missing, not a non-event.

## Covariates
- `arm` — categorical, reference level `"Standard care"`.
- `stage` — categorical, reference level `"I"`.
- `age` — continuous, reported per 10 units. Divide the column by 10 before
  fitting, so the coefficient is the log odds ratio per 10 years.

If a declared reference level is absent from the data after complete-case
filtering, the reference level is instead the most frequent remaining level.

Categorical covariates use treatment contrasts: the reference level first,
remaining levels in alphabetical order.

## Models
1. For each covariate, a univariable logistic regression of y on that
   covariate alone. This gives the unadjusted odds ratio.
2. One multivariable logistic regression of y on all three covariates
   jointly. This gives the adjusted odds ratios.

Both are maximum-likelihood binomial GLMs with a logit link.

## Reported quantities
Per covariate term: odds ratio = exp(coefficient); 95% CI =
exp(coefficient ± 1.96 × standard error) — the literal constant 1.96, not the
exact normal quantile; two-sided Wald p-value.

Also report: n analysed, number of events, number of rows dropped, and the
apparent (in-sample) C-statistic, computed as the normalised Mann-Whitney
statistic of predicted probabilities against observed outcome.

## Reportability
An odds ratio cell is reported only when the estimate and both CI bounds are
finite and the interval lies within [1e-6, 1e6]. Otherwise the cell reads
"not reliably estimated".

## Display
`%.2f (%.2f–%.2f, p=%.3f)` with an en-dash separator; when p < 0.001 the
p-part reads `p<0.001`.

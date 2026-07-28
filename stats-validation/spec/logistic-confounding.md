# Analysis spec: logistic-confounding

Input: `stats-validation/cases/logistic-confounding/data.csv`.

**This spec, and `fit_logistic`, model the LIVE APP ONLY**
(`web/guided/logistic/spec.js`'s `buildLogisticSpec` feeding `R/logistic.R`'s
`fig_logistic` — what a user's browser session actually runs) — never the
downloadable/exported `.R` script. The two were NOT interchangeable for
missing-value and whitespace handling: `stats-validation/issues/02` was that
divergence, and the shipped `logistic-dirty` case measured it on every run.
That issue is **resolved (2026-07-28)** — the exported preamble now reads a
cell the way the browser parser does, and `logistic-dirty` publishes zero
findings — but the modelling boundary stands regardless: this spec describes
the live app, and the exported script is a separate artifact that has to be
kept in parity, not assumed to be in it. Where this spec describes the export
tier at all it says so explicitly and in its own section — see the Diagnostics
section's export notes.

## Cell reading

Every cell is read as text and **trimmed of leading and trailing whitespace
before anything else looks at it**. This happens in the app's shared CSV parser
(`web/lib/csv.js`'s `parseCsv`, which does `row[c] = (cells[j] ?? "").trim()`
for every cell of every row), so the analysis code downstream never sees
untrimmed text. Two consequences, both normative:

- **A whitespace-only cell is an empty cell**, and therefore missing under every
  rule below — there is no separate "whitespace" case to handle. `" "` in the
  outcome column or in a covariate behaves exactly as `""` does, so a
  whitespace-only outcome cell is missing and its row is dropped.
- **A padded value is its unpadded self.** `" Standard care "` and
  `"Standard care"` are the same covariate level, match the same declared
  reference level, and never produce two levels. A padded numeric cell
  (`" 42 "`) is the number 42.

This is the same rule `spec/groupcompare-numeric.md`, `spec/groupcompare-dirty.md`,
`spec/summary-table1.md` and `spec/cox-adjusted.md` state, for the same reason:
one parser feeds all of them. The exported script used not to trim (it re-reads
the raw CSV with `read.csv`), which was divergence 3 of
`stats-validation/issues/02`; since 2026-07-28 its preamble trims every
character column, so the two agree.

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

**The tie-break for that fallback, stated because "most frequent" is not a
total order.** `R/logistic.R`'s `.logistic_most_frequent` is
`names(sort(table(x), decreasing = TRUE))[1]` on the non-blank values —
character-for-character the same expression as Cox's `.cox_most_frequent`.
`table()` emits its names already in ascending sorted order, and R's `sort()` on
a named integer vector is **stable**, so a decreasing sort leaves tied counts in
that ascending order. **On a tie, the level that sorts FIRST wins.** Measured in
R: `c("zebra","zebra","apple","apple")` -> `apple`;
`c("c","c","a","a","b","b")` -> `a`. Never "first seen in the file", never
"last".

**The sort is R's locale-aware collation, not a code-point sort**, because it is
`sort()`/`factor()`, not a byte comparison. Under the `en_CA.UTF-8` locale this
build runs in, `c("B","B","a","a")` resolves to **`a`**, where a code-point sort
would give `B` (`"B"` is 0x42, `"a"` is 0x61). This case's levels (`Standard
care`/`New treatment`, and `I`/`II`/`III`) are ASCII and same-case, so the two
orders coincide here and nothing in the shipped comparison depends on the
difference — but implement the locale rule, and treat a future case whose levels
mix case or leading punctuation as needing a re-verification against R rather
than an assumption.

Categorical covariates use treatment contrasts: **the reference level first,
then the remaining levels in R's `factor()` order — the same locale-aware
`sort(unique(...))` just described**, with the reference lifted out of it by
`stats::relevel`. (The other specs in this directory differ deliberately on this
point: `spec/groupcompare-*.md` pin a plain **code-point** sort and explain why
in their own Group-level ordering sections; `spec/summary-table1.md` and
`spec/cox-adjusted.md` pin the locale-aware sort, as here. They differ because
they are describing different R call sites, not because one of them is loose.)

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

## Diagnostics (advisory)

Figura appends advisory sentences to the methods text. **Not one of them gates
a fit or changes a reported estimate** — every odds ratio above is the same
number whether they fire or not. They are nonetheless published claims about
the model, pasted into a manuscript alongside the estimates, so they are
validated: the numeric ones by value, and every one of them by whether the
sentence FIRES AT ALL.

Report them in a `diagnostics` block; `stats-validation/python/INTERFACES.md`
pins the key names and types. All of them describe the JOINT (adjusted) model
fitted on the complete-case rows of the Population section, after the increment
rescaling and the reference releveling of the Covariates section.

Every threshold below is a strict inequality, exactly as written.

### C-statistic — `c_statistic`

Apparent (in-sample) discrimination: no split-sample and no bootstrap
correction, measured on the same rows the model was fitted to, so it is
optimistically biased. It is the normalised Mann-Whitney U statistic of the
joint model's fitted probabilities against the observed outcome.

Let `p_i` be the joint model's fitted probability for row `i`, `n1` the number
of rows with y = 1 and `n0` the number with y = 0. Rank all n = n1 + n0 fitted
probabilities together in ascending order, **assigning tied values their
average rank** (midranks — the tie rule matters: with a single two-level
categorical covariate every row takes one of two fitted probabilities, so
almost every pair is tied). Then

    C = ( sum of the ranks of the y = 1 rows  -  n1 * (n1 + 1) / 2 ) / (n1 * n0)

That is Mann-Whitney U divided by n1 * n0, so a tied event/non-event pair
contributes exactly 0.5 to the concordance count. `None` when either class is
empty.

Displayed, whenever C is finite:

    " Overall model discrimination: apparent (in-sample) C-statistic = %.2f."

### Variance inflation — `vif`, `vif_triggered`

Computed for **CONTINUOUS covariates only**. Categorical covariates take no
part at all: not as the regressand, not as a regressor. Collinearity among
categorical terms (which would need a generalised VIF) is not assessed, and
this is a limit of the diagnostic as shipped, not an omission to repair.

- With fewer than **two** continuous covariates there is nothing to regress
  against, so **no VIF is computed at all**: `vif` is `None` (not an empty
  map — "the diagnostic did not run" and "it ran and found nothing" are
  different claims), and the note can never fire.
- Otherwise, for each continuous covariate j, fit an ordinary least-squares
  regression **with an intercept** of column j on every OTHER continuous
  covariate, over the same complete-case rows the logistic model used. Let
  `R²_j` be that fit's multiple R-squared (1 - RSS/TSS, TSS about the mean).
  Then

      VIF_j = 1 / (1 - R²_j)

  When `R²_j` is not finite or is >= 1 — an exactly duplicated covariate —
  `VIF_j` is **positive infinity**.
- The increment rescaling of the Covariates section divides a column by a
  positive constant, which leaves `R²_j` unchanged, so VIF is the same
  before and after it.

`vif_triggered` is true when `vif` is not `None` and **any** VIF > 5.

Displayed, when triggered:

    " CAUTION: multicollinearity among continuous covariates (largest VIF =
      %s, above the usual threshold of 5); consider dropping a redundant
      variable."

where `%s` is the literal string `effectively infinite` when **any** VIF is
non-finite, and otherwise `sprintf("%.1f", max(VIF))`. The infinite case is
keyed off the presence of a non-finite VIF, not off the absence of finite
ones: with a third, independent covariate a finite VIF near 1.0 also exists,
and reporting that one would read "largest VIF = 1.0, above the usual
threshold of 5".

### Events per variable — `epv`, `epv_triggered`

Let `terms` be the number of model coefficients **excluding the intercept**:
one per continuous covariate, and (number of levels - 1) per categorical
covariate, levels counted **after** the complete-case filter. Let

    n_min = min(n_event, n - n_event)

— the smaller outcome group, not the event count, so an outcome that is mostly
events is judged on its rarer class. Then

    epv = n_min / terms

`epv_triggered` is true when `epv` < 10.

Displayed, when triggered:

    " CAUTION: about %.1f events per model term (EPV < 10); the adjusted
      estimates may be unstable and are best treated as exploratory."

### Influential observations — `cooks_influential`, `cooks_triggered`

Cook's distance for the joint model, at the conventional 4/n cut-off.

For row i, with `μ_i` the fitted probability, `y_i` the 0/1 outcome, and `p`
the number of estimated coefficients **including the intercept**:

- Pearson residual `r_i = (y_i - μ_i) / sqrt(μ_i * (1 - μ_i))`.
- IRLS working weight `w_i = μ_i * (1 - μ_i)`; hat value `h_i` is the i-th
  diagonal of `W^(1/2) X (X' W X)^(-1) X' W^(1/2)` with `W = diag(w)` and `X`
  the design matrix including the intercept column — that is, the leverage of
  the final weighted least-squares step.
- Dispersion is **1** (binomial family), so it drops out:

      D_i = ( r_i / (1 - h_i) )^2 * h_i / p

- A row whose `D_i` is not finite (h_i == 1) is **not counted** — treat it as
  missing, never as influential.

`cooks_influential` is the number of rows with `D_i > 4 / n`, where n is the
number of rows in the fit. `cooks_triggered` is true when that count > 0.

Displayed, when triggered:

    " %d observation(s) were flagged as influential (Cook's distance > 4/n);
      inspect them for data-entry errors."

### Separation / collinearity caution — `separation_caution`

True when **either** of:

1. any displayed cell in **either** column — unadjusted or adjusted — fails the
   Reportability rule above (the interval ran away in either tail); or
2. the joint fit's fitted probabilities are numerically 0 or 1: any `μ_i` >
   1 - 10ε or < 10ε, with ε the machine epsilon for a double
   (2.220446049250313e-16). This is exactly the condition R's `glm.fit` warns
   on.

Both columns are inspected in clause 1 because an unadjusted cell can run away
while the adjusted one stays finite (a crude effect that is explained away),
and that cell would otherwise sit in the table with no sentence explaining it.

Displayed, when triggered:

    " CAUTION: separation or severe collinearity was detected — one or more
      covariates either predict the outcome (near-)perfectly or duplicate
      information already carried by another covariate, so those odds ratios
      are not reliably estimated by standard logistic regression. Consider
      collapsing sparse categories, dropping or combining a redundant
      variable, or a penalized (Firth) fit, and seek statistical review."

**Known sensitivity, measured.** Clause 2 is evaluated wherever the iterative
fit stopped, so it is solver-dependent: on a perfectly separated 15-vs-15
fixture R's own IRLS stops with `min(μ) = 7.9e-12`, four orders of magnitude
ABOVE 10ε, so R issues no warning and the caution comes entirely from clause 1.
Clause 1 is the clause that fires in practice. Do not tune clause 2's threshold
to make a case agree — 10ε is the shipped rule.

### Two notes deliberately outside this contract

- **The numerical-warning fallback.** When no separation caution is printed,
  the app prints ` CAUTION: fitting reported a numerical warning ("<message>");
  ...` embedding R's own verbatim warning text. That string is an artifact of
  one implementation's warning catalogue, not a statistical quantity, so no
  independent implementation can be asked to reproduce it. It is outside this
  contract; the comparator detects the clause in the displayed text and reports
  MISSING_QUANTITY rather than ignoring it, so a case that provokes it requires
  this contract to be extended first.
- **The dropped-row note** (` %d row(s) with missing values were excluded.`) is
  not a diagnostic: `n_dropped` is already compared as a count.

### Which tier judges which diagnostic

The exported `.R` script computes and prints the C-statistic with the identical
expression given above, from objects it assigns (`prob`, `n1`, `n0`, `dat$.y`),
so the C-statistic **has a full-precision Path A value** and is compared at rel
1e-6 / abs 1e-9 like any estimate, plus a script-tier check that the exported
script's C-statistic re-renders the sentence the screen showed.

The exported script computes **no VIF, no Cook's distance, no EPV and no
separation check** — there is no `lm()`, no `cooks.distance()` and no fitted-
probability inspection anywhere in it. Those four diagnostics therefore have
**no exact-tier Path A value at all**, and none is manufactured: they are judged
against the DISPLAY tier only — the sentence Figura actually printed — which is
honest evidence about the artifact the user was given.

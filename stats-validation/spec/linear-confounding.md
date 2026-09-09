# Analysis spec: linear-confounding

Input: `stats-validation/cases/linear-confounding/data.csv`.

**This spec, and `fit_linear`, model the LIVE APP ONLY**
(`web/guided/linear/spec.js`'s `buildLinearSpec` feeding `R/linear.R`'s
`fig_linear` — what a user's browser session actually runs) — never the
downloadable/exported `.R` script. The two are separate artifacts held in
parity, not one artifact seen twice: `stats-validation/issues/02` was exactly
such a divergence for the logistic path (missing-value and whitespace
handling), and it is resolved only because the exported preamble was changed to
read a cell the way the browser parser does. The modelling boundary stands
regardless. Where this spec describes the export tier at all it says so
explicitly and in its own section — see "Which tier judges which diagnostic".

The outcome here is CONTINUOUS and the reported quantity is a **coefficient**,
not a ratio. Nothing in this spec is ever exponentiated, the estimates are
signed, and there is no ratio-scale plausibility window anywhere. An
implementer coming from `spec/logistic-confounding.md` or `spec/cox-adjusted.md`
should read the Reported quantities, Reportability and Display sections as
deliberate departures from those two, not as restatements of them.

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

This is the same rule `spec/logistic-confounding.md`, `spec/cox-adjusted.md`,
`spec/groupcompare-numeric.md`, `spec/groupcompare-dirty.md` and
`spec/summary-table1.md` state, for the same reason: one parser feeds all of
them.

## Population

Complete cases only. Drop any row where the outcome or any of the three
covariates is missing or an empty string. Report the number dropped. A blank
cell is missing.

**The literal string `NA` is an ordinary value, not missing** — do not treat it
as NA. What that means differs by column kind, and the difference is worth
stating because it is a behaviour, not a technicality:

- In a **categorical** covariate, `NA` is just another level, counted and
  contrasted like any other.
- In a **numeric** column, `NA` does not parse as a number. A column is
  classified numeric only when EVERY non-blank cell parses numerically (see
  Outcome and Covariates below), so a covariate column containing a literal
  `NA` is classified **categorical** instead, and `NA` becomes one of its
  levels. In the OUTCOME column the same failure to parse is a hard error
  (see Outcome).

The complete-case filter is applied to the outcome and all selected covariates
together, in one pass, **before** the increment rescaling and **before** the
reference releveling of the Covariates section. Every quantity in this spec —
every count, every level list, every diagnostic — is computed on the rows that
survive it.

For this case: 320 rows, none dropped.

### Boundaries the app enforces that this case never reaches

Two app-level stops exist and are stated here only so an implementer knows they
are deliberate app behaviour rather than an omission. **Path B is not asked to
reproduce either**; the shipped case data triggers neither, and no comparison
depends on them.

- **Residual degrees of freedom.** After the complete-case filter the app
  refuses to fit when `n − 1 − terms < 10`, where `terms` is the count defined
  in the observations-per-term diagnostic below. The refusal is an error
  message, not a returned model.
- **Perfect fit.** After fitting, the app refuses to report when the joint
  model's residual variance is numerically zero — specifically when the
  residual mean square is finite and smaller than
  `(mean(fitted)² + var(fitted)) · 1e-30`, which is R's own "essentially
  perfect fit" test. A fit that exact has undefined standard errors and
  p-values and always means a covariate duplicates or derives from the
  outcome.

The app additionally refuses when the outcome has zero variance after the
filter, and when a categorical covariate is left with only one level.

## Outcome

The outcome column is `los`, read as a number.

**Every non-blank cell of the outcome column must parse numerically.** If any
does not — a literal `NA`, a stray unit suffix, any text — the app produces an
error and no analysis at all. There is no per-cell fallback: the check is over
the whole column, and it fails the column, not the row. Blank (or, per Cell
reading, whitespace-only) cells are exempt from the check and are missing.

The outcome enters the model on its own scale. It is never transformed, never
standardised, and never rescaled by an increment.

## Covariates

Three covariates, in this order — the order matters, and it is the order the
case declares (`arm`, `age`, `stage`), because it fixes the column order of the
joint design matrix and therefore which column is dropped under exact
collinearity (see Reportability):

- `arm` — categorical, declared reference level `"Standard care"`.
- `age` — continuous, reported per 10 units. Divide the column by 10 **before
  fitting**, so the coefficient is the difference in `los` per 10 years.
- `stage` — categorical, declared reference level `"I"`.

(The bullets are in the declared order, which is also the design-matrix order.
The joint model's non-intercept columns are therefore `armNew treatment`,
`age`, `stageII`, `stageIII`, in that sequence.)

### Continuous vs categorical

A covariate column is **continuous** when every non-blank cell of it parses as
a number, and **categorical** otherwise. This is the same whole-column rule the
Outcome section states, but with a different consequence: a covariate that
fails it is silently treated as categorical rather than raising an error.

### The increment

Each continuous covariate carries a positive increment `k`, defaulting to 1.
The declared value is coerced to a number; **anything that is not a single
finite number strictly greater than zero falls back to 1** — a missing entry, a
non-numeric string, zero, a negative number, an infinity. When `k` is 1 the
column is left untouched; otherwise the column is divided by `k` after the
complete-case filter and before fitting.

Dividing a column by a positive constant multiplies its coefficient, its
standard error and both CI bounds by that constant, and **leaves the p-value
and the whole model fit unchanged** (identical fitted values, residuals, R²,
and every diagnostic). An implementation that rescales the coefficient
afterwards instead of the column before must reproduce that invariance exactly.

### Reference levels and the fallback

A categorical covariate's reference level is the declared one **when that level
is still present after the complete-case filter**. When it is absent — declared
but never observed, or observed only in dropped rows — the reference level is
instead the **most frequent remaining level**. The same fallback applies when
no reference level is declared at all.

**The tie-break for that fallback, stated because "most frequent" is not a
total order.** The rule is: tabulate the non-blank values, sort that table by
count descending, take the first name. R's `table()` emits its names already in
ascending sorted order, and R's `sort()` on a named integer vector is
**stable**, so a decreasing sort leaves tied counts in that ascending order.
**On a tie, the level that sorts FIRST wins.** Measured in R:
`c("zebra","zebra","apple","apple")` → `apple`; `c("c","c","a","a","b","b")` →
`a`. Never "first seen in the file", never "last".

**The sort is R's locale-aware collation, not a code-point sort**, because it is
`sort()`/`factor()`, not a byte comparison. Under the `en_CA.UTF-8` locale this
build runs in, `c("B","B","a","a")` resolves to **`a`**, where a code-point sort
would give `B` (`"B"` is 0x42, `"a"` is 0x61). This case's levels (`Standard
care`/`New treatment`, and `I`/`II`/`III`) are ASCII and same-case, so the two
orders coincide here and nothing in the shipped comparison depends on the
difference — but implement the locale rule, and treat a future case whose levels
mix case or leading punctuation as needing a re-verification against R rather
than an assumption.

### Contrast coding and level order

Categorical covariates use **treatment (dummy) contrasts with the reference
level as baseline**: one indicator column per non-reference level, 1 when the
row takes that level and 0 otherwise, and no column for the reference level
itself. The reference level's effect is therefore not estimated; it is
structurally 0.

Within a covariate, the level order is **the reference level first, then the
remaining levels in R's `factor()` order** — the same locale-aware
`sort(unique(...))` just described, with the reference lifted out of it. That
order fixes the row order of the display table and the column order of the
design matrix.

(The other specs in this directory differ deliberately on this point:
`spec/groupcompare-*.md` pin a plain **code-point** sort and explain why in
their own Group-level ordering sections; `spec/summary-table1.md`,
`spec/cox-adjusted.md` and `spec/logistic-confounding.md` pin the locale-aware
sort, as here. They differ because they describe different R call sites, not
because one of them is loose.)

## Models

1. For each covariate, an **ordinary least-squares regression of the outcome on
   that covariate alone**, with an intercept. This gives the unadjusted
   coefficient. A categorical covariate contributes all of its indicator
   columns to its own univariable model.
2. One **ordinary least-squares regression of the outcome on all three
   covariates jointly**, with an intercept. This gives the adjusted
   coefficients.

Both are least-squares fits with no weights, no offsets and no regularisation.
Every model is fitted on the same complete-case rows, after the same increment
rescaling and the same releveling — the univariable models are not refitted on
a wider set of rows.

For this case the joint model has 5 estimated coefficients: the intercept,
`armNew treatment`, `age`, `stageII` and `stageIII`.

### Term naming, and how the unadjusted results are keyed

A coefficient is named for the design column it belongs to: a **continuous**
covariate's coefficient takes the bare column name, and a **categorical**
covariate's takes the column name immediately followed by the level string,
with no separator — `arm` plus `New treatment` is `armNew treatment`. The
increment does not enter the name: `age` divided by 10 is still keyed `age`.
The display label of the Display section (`age (per 10 units)`) is a rendering,
never a key.

The unadjusted results are a **single flat mapping keyed by the same
coefficient names**, not one entry per covariate holding a nested model. A
categorical covariate contributes one entry per non-reference level there too,
exactly as it does in the joint model, so a three-level covariate contributes
two unadjusted entries. Keys never collide across covariates because each is
prefixed by its own column name.

## Reported quantities

Per non-intercept coefficient of a model:

- **Coefficient** β — the least-squares estimate, on the outcome's own scale.
  It is a difference in the outcome, signed, and is **never exponentiated**.
- **Standard error** se — the square root of the corresponding diagonal entry
  of the coefficient covariance matrix, which is `s² (X'X)⁻¹` with
  `s² = RSS / (n − p)`.
- **95% confidence interval** — `β ± t(0.975, n − p) · se`, where `t(0.975, df)`
  is the **Student t quantile** at the 0.975 level on `df` degrees of freedom,
  `n` is the number of rows fitted, and `p` is the number of **estimated**
  coefficients **including the intercept**.

  **This is NOT the constant 1.96 and NOT the normal quantile.** The logistic
  and Cox specs in this directory pin Wald intervals built on 1.96; this one
  does not, and an implementation that uses 1.96 here will be wrong in the
  fourth decimal place on a case this size and much more wrong on a small one.
  For this case `n − p = 320 − 5 = 315` and `t(0.975, 315) ≈ 1.9675`.

- **p-value** — two-sided, from the t statistic `β / se` on the same `n − p`
  degrees of freedom: `p = 2 · P(T_{n−p} > |β / se|)`.

Note that `p` counts **estimated** coefficients. Under exact collinearity a
column is dropped and contributes no estimated coefficient, so `n − p` is the
model's residual degrees of freedom as actually fitted, not `n − 1 − (number of
design columns you intended)`.

Also reported, for the joint model:

- **n** — rows analysed after the complete-case filter.
- **n dropped** — rows removed by that filter.
- **R²** = `1 − RSS / TSS`, with `RSS` the residual sum of squares and `TSS`
  the total sum of squares about the mean of the outcome (the model has an
  intercept, so TSS is centred).
- **Adjusted R²** = `1 − (1 − R²) · (n − 1) / (n − p)`, with the same `p` as
  above.

There is **no event count** in this contract. A continuous outcome has none,
and no substitute for one may be reported.

## Reportability

A coefficient cell carries usable information — is **reportable** — exactly
when the estimate and both confidence bounds are all finite. There is no
ratio-scale window to fail: a coefficient of −8000 is an ordinary number, not
an implausible one.

An **aliased** coefficient — one whose design column is an exact linear
combination of the columns before it, so the model cannot estimate it — is
unreportable. **All five of its reported quantities are undefined**: the
estimate, the standard error, both confidence bounds, and the p-value. None of
the five is 0, and none is omitted while the others are present.

An aliased term is **present in the results with every value undefined, never
omitted**. The distinction is deliberate: a missing key would read as "this
analysis did not produce that term", whereas an undefined value reads as "this
analysis produced that term and could not estimate it", which is what actually
happened and what the display shows.

**Which column is dropped.** Order the joint design's columns as: the
intercept, then each covariate's columns in the covariate order the case
declares, and within a categorical covariate its non-reference levels in the
level order fixed above. Walking that order left to right, a column that is an
exact linear combination of the columns already retained is dropped; every
other column is kept. **The LATER column of an exactly collinear pair is the
one dropped**, and swapping the two covariates in the declared order swaps
which one loses its estimate. Verified in R: with `age2 = 2 · age` and the
covariates ordered `arm, age, age2`, `age2` is the aliased term; ordered
`arm, age2, age`, `age` is.

Aliasing is a property of the design a coefficient belongs to. A covariate
that is aliased in the joint model is typically perfectly estimable in its own
univariable model, and must be reported there as an ordinary reportable cell.

**The display adds one more condition.** A cell is *rendered* as a number only
when it is reportable **and** its p-value is finite; otherwise it renders as
the literal string `not reliably estimated`. The two conditions are separate on
purpose: the reportability predicate itself is about the estimate and the
bounds only, and is the same predicate the adjusted-coefficient forest plot uses
to decide which terms to draw, so the table and the plot can never disagree
about which terms carry usable information.

## Display

A reportable cell renders as

    %.2f (%.2f to %.2f, <p-part>)

— for example `-1.47 (-2.05 to -0.90, p<0.001)`. **The separator between the
bounds is the ASCII word ` to `, surrounded by single spaces**, not an en dash.
This differs from the ratio-scale analyses on purpose: a coefficient can be
negative, and `-2.05–-0.90` is unreadable.

The p-part reads `p<0.001` when the p-value is below 0.001, and otherwise
`p=%.3f` — three decimal places, no space around the `=`.

An unreportable cell renders as the bare string `not reliably estimated`, with
no parentheses and no p-part.

### Row labels and the reference row

One display row per covariate LEVEL, in the level order fixed above.

- A **continuous** covariate produces one row, labelled `<column> (per 1 unit)`
  when its increment is 1 and `<column> (per <k> units)` otherwise, with `k`
  rendered in R's `%g` general format (so `10` prints as `10`, not `10.0`). For
  this case: `age (per 10 units)`.
- A **categorical** covariate produces a header row labelled
  `<column> (reference: <reference level>)`, followed by one indented row per
  non-reference level, labelled with the bare level string. For this case:
  `arm (reference: Standard care)` then `New treatment`; `stage (reference: I)`
  then `II` then `III`.

**The reference header row's two effect cells are BLANK in the TSV and read
`0 (reference)` in the HTML.** This asymmetry is load-bearing, not an oversight:
the validation parser (`stats-validation/compare/compare.py`) requires a
reference header row to carry empty cells so it can tell a header from a level
row, while a human reading the rendered table looks at the header row for the
reference level's effect and should find the null of a difference, which is 0.
Every level row below a header always carries a real cell, reportable or not.

The table's three columns are headed `Characteristic`,
`Unadjusted β (95% CI, p)` and `Adjusted β (95% CI, p)`.

### The methods paragraph

The `text` field is the TSV, a blank line, then a methods paragraph. The
paragraph opens with a lead sentence and then appends advisory sentences, in
this fixed order: aliased caution, numerical-warning fallback,
observations-per-term caution, Shapiro–Wilk note, Breusch–Pagan caution, VIF
caution, influential-observations note, dropped-row note. Each is omitted
entirely when it does not fire.

With two or more covariates the lead sentence reads

    Multivariable linear regression (n = %d) of <outcome> adjusted for
    <covariates, comma-separated>. Unadjusted coefficients are from
    single-covariate models; adjusted coefficients are from the joint model
    (R² = %.3f, adjusted R² = %.3f).

With exactly one covariate there is no joint model to speak of, and the lead
sentence instead says the unadjusted and adjusted columns report the same
model, carrying the same parenthesised R² pair. **The R² pair is printed
unconditionally, in both forms of the sentence, at three decimal places.**

### Citation paragraph (not compared)

The `text` field ends with one extra paragraph, separated from everything
above it by a blank line: a fixed attribution sentence beginning
`Analyses were performed with Figura (` and ending `in the browser.`. It
names the tool, a URL, a year, and the R packages the analysis used. It
carries no statistical content and is excluded from every comparison: the
comparator removes exactly one such trailing paragraph before parsing. An
implementer of this spec must not emit it and must not parse it.

## Diagnostics (advisory)

Figura appends advisory sentences to the methods text. **Not one of them gates
a fit or changes a reported estimate** — every coefficient above is the same
number whether they fire or not. They are nonetheless published claims about
the model, pasted into a manuscript alongside the estimates, so they are
validated: the numeric ones by value, and every one of them by whether the
sentence FIRES AT ALL.

Report them in a `diagnostics` block; `stats-validation/python/INTERFACES.md`
pins the key names and types. **All of them describe the JOINT (adjusted)
model**, fitted on the complete-case rows of the Population section, after the
increment rescaling and the reference releveling of the Covariates section.
None of them looks at a univariable model.

Every threshold below is a **strict inequality**, exactly as written.

### Residual normality — `shapiro_p`, `shapiro_triggered`

The Shapiro–Wilk W test applied to the joint model's **residuals** (the raw
residuals `y − fitted`, not standardised or studentised).

The test runs **only when the number of residuals `n` satisfies `3 ≤ n ≤ 5000`**
— its own supported size window. Outside that window it is not run and
`shapiro_p` is `None`, meaning "not assessed": never a placeholder p, never 1.0,
never 0. `shapiro_p` is also `None` when the test cannot run at all (for
instance when every residual is identical); that is an absence, never an error.

`shapiro_triggered` is true when `shapiro_p` is not `None` and `shapiro_p` <
0.05.

Displayed, when triggered — note this one is not a CAUTION, and its second half
is conditional on n:

    " Residuals depart from normality (Shapiro–Wilk <p-part>); with n = %d
      <tail>."

where `<p-part>` follows the Display section's p rule, and `<tail>` is

- when `n` >= 30: `the coefficient estimates are unaffected, and the confidence
  intervals are usually robust to this unless the residual plots also show
  non-constant variance or influential points`
- otherwise: `the confidence intervals may be unreliable; consider transforming
  the outcome or a non-parametric comparison`

For this case `shapiro_p` ≈ 0.51, so the sentence does not fire.

### Non-constant variance — `bp_p`, `bp_triggered`

Koenker's studentized Breusch–Pagan test, computed by hand from two ordinary
least-squares fits and nothing else.

Let `e` be the joint model's residuals and `f` its fitted values, both vectors
of length `n`. Fit an **auxiliary ordinary least-squares regression, with an
intercept, of `e²` on `f`** — that is, the squared residuals regressed on the
FITTED VALUES, a single regressor. **Not on the design matrix**, not on the
covariates, not on the absolute residuals. Let `R²_aux` be that auxiliary fit's
multiple R-squared (`1 − RSS / TSS`, TSS about the mean). Then

    LM = n · R²_aux
    bp_p = P(χ²₁ > LM)     — the UPPER tail of a chi-square on 1 degree of freedom

`n` here is the number of residuals, which is the same `n` as everywhere else in
this spec.

`bp_p` is always reported as a number — unlike `shapiro_p` it has no size window
and no "not assessed" state, so it is never `None`. `bp_triggered` is true when
`bp_p` is finite and `bp_p` < 0.05; the finiteness guard is there only for the
degenerate auxiliary fit and is not a licence to report a null p.

Displayed, when triggered:

    " CAUTION: residual variance is not constant across fitted values
      (Breusch–Pagan <p-part>); the standard errors may be misleading, and
      robust standard errors or an outcome transform are worth considering."

For this case `bp_p` ≈ 0.22, so the sentence does not fire.

### Observations per term — `obs_per_term`, `obs_per_term_triggered`

    obs_per_term = n / terms

where `n` is the number of rows analysed and `terms` is the number of
**non-intercept model terms in the joint design**: **one per continuous
covariate**, and **(number of distinct levels − 1) per categorical covariate**,
with levels counted **after** the complete-case filter.

**`terms` is counted from the covariate structure, not from the fitted model's
rank.** An aliased column still contributes its 1 (or its levels − 1) to
`terms`, because the count is taken before any model is fitted and never
revisited. This is the shipped behaviour and it is what the displayed sentence
reports; do not subtract dropped columns to "correct" it.

Note also that this is **n over terms, not events over terms**. A continuous
outcome has no events, so there is no analogue of the logistic spec's
smaller-outcome-group rule. Under one name — the EPV family — these are
different quantities in different specs.

`obs_per_term_triggered` is true when `obs_per_term` < 10.

Displayed, when triggered:

    " CAUTION: about %.1f observations per model term (fewer than 10); the
      adjusted estimates may be unstable and are best treated as exploratory."

For this case `terms` = 4 (`arm` contributes 1, `age` contributes 1, `stage`
contributes 2) and `obs_per_term` = 80, so the sentence does not fire.

### Variance inflation — `vif`, `vif_triggered`

Computed for **CONTINUOUS covariates only**. Categorical covariates take no
part at all: not as the regressand, not as a regressor. Collinearity among
categorical terms (which would need a generalised VIF) is not assessed, and
this is a limit of the diagnostic as shipped, not an omission to repair.

- With fewer than **two** continuous covariates there is nothing to regress
  against, so **no VIF is computed at all**: `vif` is `None` (not an empty
  map — "the diagnostic did not run" and "it ran and found nothing" are
  different claims), and the note can never fire. This case has exactly one
  continuous covariate, so `vif` is `None` here.
- Otherwise, for each continuous covariate j, fit an ordinary least-squares
  regression **with an intercept** of column j on every OTHER continuous
  covariate, over the same complete-case rows the linear model used. Let
  `R²_j` be that fit's multiple R-squared (`1 − RSS / TSS`, TSS about the
  mean). Then

      VIF_j = 1 / (1 - R²_j)

  When `R²_j` is not finite or is >= 1 — an exactly duplicated covariate —
  `VIF_j` is **positive infinity**.
- The increment rescaling of the Covariates section divides a column by a
  positive constant, which leaves `R²_j` unchanged, so VIF is the same
  before and after it.

`vif` is keyed by the bare covariate column name, never by a coefficient name.

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

### Influential observations — `cooks_influential`, `cooks_triggered`

Cook's distance for the joint model, at the conventional `4/n` cut-off.

For row `i`, with `e_i` the residual, `h_i` the i-th diagonal of the hat matrix
`X (X'X)⁻¹ X'` (with `X` the fitted design matrix including the intercept
column and excluding any aliased column), `p` the number of **estimated**
coefficients **including the intercept**, and `s² = RSS / (n − p)` the residual
mean square:

    D_i = ( e_i² / (p · s²) ) · h_i / (1 - h_i)²

A row whose `D_i` is not finite (`h_i == 1`, a point of full leverage) is **not
counted** — treat it as missing, never as influential.

    cooks_influential = number of rows with  D_i > 4 / n

`cooks_triggered` is true when `cooks_influential` > 0.

Displayed, when triggered:

    " %d observation(s) were flagged as influential (Cook's distance > 4/n);
      inspect them for data-entry errors."

For this case `cooks_influential` is 18, so the sentence fires.

### Aliased coefficients — `aliased_caution`

True when **any** coefficient of the joint model is not estimable — that is,
when the joint design is rank-deficient and at least one column was dropped per
the Reportability section's ordering rule. It is a property of the joint model
only; a univariable model's estimability does not enter it.

This is a pure boolean with no number in it. It is false for this case.

Displayed, when triggered:

    " CAUTION: one or more covariates were dropped from the adjusted model
      because they are linear combinations of others (their cells read
      \"not reliably estimated\"); remove a redundant variable."

## Which tier judges which diagnostic

The exported `.R` script computes and prints `summary(fit)` (which carries R²
and adjusted R²), `shapiro.test(resid(fit))` under the identical `3 ≤ n ≤ 5000`
guard, and the Breusch–Pagan pair `aux <- lm(resid(fit)^2 ~ fitted(fit))`,
`pchisq(n * summary(aux)$r.squared, df = 1, lower.tail = FALSE)`. Those four
quantities — **R², adjusted R², `shapiro_p` and `bp_p`** — therefore have
full-precision **Path A values on the exact tier**, harvested from the script's
own objects with the identical expressions, and are compared as numbers.

The exported script prints `cooks.distance(fit)` but **never counts the `> 4/n`
exceedances**, and it computes **no VIF, no observations-per-term ratio and no
rank-deficiency check** — there is no auxiliary `lm()` for VIF and no inspection
of which coefficients came back undefined. `cooks_influential`,
`obs_per_term`, `vif` and `aliased_caution` therefore have **no exact-tier
Path A value at all**, and none is manufactured: they are judged against the
DISPLAY tier only — the sentence Figura actually printed — which is honest
evidence about the artifact the user was given.

The coefficients themselves (β, se, both CI bounds, p) have exact-tier Path A
values from the script's `summary(fit)$coefficients` and `confint(fit)`, per
term, including undefined-everywhere entries for aliased terms.

## Two notes deliberately outside this contract

- **The numerical-warning fallback.** When the least-squares fit emits a
  numerical warning, the app appends
  ` CAUTION: fitting reported a numerical warning ("<message>"); the
  coefficients above may come from a model that did not fit cleanly. Check the
  covariates for extreme values, and seek statistical review.`, embedding R's
  own verbatim warning text. That string is an artifact of one implementation's
  warning catalogue, not a statistical quantity, so no independent
  implementation can be asked to reproduce it. It is outside this contract; the
  comparator detects the clause in the displayed text and reports
  MISSING_QUANTITY rather than ignoring it, so a case that provokes it requires
  this contract to be extended first.
- **The dropped-row note** (` %d row(s) with missing values were excluded.`) is
  not a diagnostic: `n_dropped` is already compared as a count.

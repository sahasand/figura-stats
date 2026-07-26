# Analysis spec: logistic-dirty

Input: `stats-validation/cases/logistic-dirty/data.csv`. Header
`arm,age,stage,complication`, 320 data rows. Roles: outcome = `complication`,
covariates = `arm`, `age`, `stage`; event value `Yes`; reference levels
`arm = "Standard care"`, `stage = "I"`; increment `age = 10`.

**The statistical contract is identical to `stats-validation/spec/logistic-confounding.md`.**
Read that file for Population, outcome coding, covariate coding, the two models,
the reported quantities, the reportability rule, and the display rule. Nothing
about the model changes here. `fit_logistic` needs no new behaviour for this
case; it is the same call on a dirtier file.

What changes is the **input**, and the purpose of the case is the divergence
that dirt exposes between the live app and the `.R` script the app exports.

## The injected dirt

Derived from `cases/logistic-confounding/data.csv` (a byte-for-byte copy except
for the ten cells below), so every difference in the results is attributable to
the dirt and nothing else.

1. **Eight `stage` cells hold the literal two-character text `NA`** — file lines
   7, 14, 21, 28, 175, 182, 189, 203 (1-based, line 1 being the header). They
   were chosen to be balanced: four `complication = Yes` and four `No`, four in
   each arm, so the resulting level is estimable rather than separated.
2. **Two `age` cells carry a trailing space** — lines 50 (`56 `) and 250 (`69 `).
   `age` is NUMERIC, deliberately: whitespace padding is confined to a numeric
   column, because a padded FACTOR level does not merely change numbers, it
   breaks the exported script outright (`grouping factor must have exactly 2
   levels`) or silently adds an arm — divergence 3 in
   `stats-validation/issues/02-app-vs-exported-script-missing-values.md`, already
   verified there and deliberately not re-litigated as a permanently-red case.

The outcome column and the reference-defining `arm` column are untouched.

## What each reader does with it

**The live app** (`web/lib/csv.js` -> `buildLogisticSpec` -> `R/logistic.R`):

- trims every cell, so ` 56` / `56 ` are the number 56. The padding is inert.
- treats `NA` as ORDINARY TEXT. `stage` therefore has **four** levels — `I`,
  `II`, `III`, and a level literally named `NA` — and the fitted model carries a
  `stageNA` coefficient that is displayed to the user as an ordinary row.
- drops nothing: `n = 320`, `n_event = 91`, `n_dropped = 0`.

**The exported `.R` script** (`R/script.R`'s `.script_data` preamble):

```r
df <- read.csv("data.csv", check.names = FALSE)
df[df == ""] <- NA   # blank cells are missing values
```

`read.csv` carries the default `na.strings = "NA"`, which is not overridden, so
the eight literal-`NA` `stage` cells become real `NA` **before** the script's own
prep runs; `complete.cases(dat)` then removes those eight rows. The script's
model has **three** `stage` levels and fits 312 rows. (The padded `age` cells are
inert on this side too: `type.convert` still reads the column as numeric, since
`as.numeric("56 ")` is 56.)

So `n = 312`, `n_event = 87`, `n_dropped = 8`, and **no `stageNA` term exists**.

## Expected result — this case is DESIGNED to publish findings

`fit_logistic` (Path B) models the live app, so it agrees with the screen and
disagrees with the exported script. That is the point. Running the full
comparator on this case is expected to produce, and did produce:

- **display tier: PASS.** Every displayed cell — including the `NA` stage row —
  is reproduced exactly by Path B pushed through the app's own display rule.
  The app and the independent implementation agree completely about what the
  user was shown.
- **`COUNT_MISMATCH` x3** — `n` 312 vs 320, `n_event` 87 vs 91, `n_dropped` 8 vs 0.
- **`MISSING_QUANTITY` x1** — `stage:NA`: Path A's harvest has no
  full-precision term `stageNA` at all, because the script never saw the level.
- **`SCRIPT_DIVERGENCE` x4** — one per displayed adjusted cell: the exported `.R`,
  rendered through the app's own display rule, does not reproduce the screen.
- **`DEFECT` x20** — est/se/lo/hi/p for each of the four shared terms, all beyond
  rel 1e-6: the two paths fitted different data.

`exact_targets` are the same six as `logistic-confounding`, and they are all
**met**: every declared quantity really was compared. `targets_met: true` with
`passed: false` is the honest shape for this case — the coverage contract was
discharged and the comparison found real disagreements. The comparator exits 1,
which is the correct pipeline outcome; `findings.json` and the scorecard are
still written, because the failing evidence IS the deliverable.

**Do not suppress, special-case, or "fix" these findings.** They are the
mechanical catch of issue 02 divergence 1, which until now existed only as a
hand-built repro in a Markdown file.

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

> **Status, 2026-07-28.** That divergence is **fixed**
> (`stats-validation/issues/02-app-vs-exported-script-missing-values.md`,
> resolved: `R/script.R`'s `.script_data` now reads the file the way the
> browser's own parser does). This case published 30 findings from the day it
> shipped until that fix landed, and publishes **0** today across 52 compared
> values. It stays in the roster exactly as it is: it is now the standing
> regression test for the fix — a case built to fail, passing only while the
> exported script keeps parity with `web/lib/csv.js`. The sections below give
> both readings, before and after, because the before is why the case exists.

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
   (That reasoning was written pre-fix and is kept because it explains the file
   as it stands. Divergence 3 is closed too, so padding a factor level would no
   longer break anything — but the case's data is not changing to prove it: the
   `trimws` half of the fix is covered by `tests/testthat/test-script.R`, whose
   group-comparison test runs the exported script against padded group cells.)

The outcome column and the reference-defining `arm` column are untouched.

## What each reader does with it

**The live app** (`web/lib/csv.js` -> `buildLogisticSpec` -> `R/logistic.R`):

- trims every cell, so ` 56` / `56 ` are the number 56. The padding is inert.
- treats `NA` as ORDINARY TEXT. `stage` therefore has **four** levels — `I`,
  `II`, `III`, and a level literally named `NA` — and the fitted model carries a
  `stageNA` coefficient that is displayed to the user as an ordinary row.
- drops nothing: `n = 320`, `n_event = 91`, `n_dropped = 0`.

**The exported `.R` script** (`R/script.R`'s `.script_data` preamble). Since the
issue-02 fix it reads:

```r
df <- read.csv("data.csv", check.names = FALSE, na.strings = character(0))
df[] <- lapply(df, function(x) if (is.character(x)) trimws(x) else x)
df[df == ""] <- NA
```

`na.strings = character(0)` leaves the eight literal-`NA` `stage` cells as the
ordinary value `"NA"`, so the script sees the same four `stage` levels the app
did and `complete.cases(dat)` removes nothing. The padded `age` cells are inert
here as they always were: `age` is numeric, and `read.table` strips whitespace
from a numeric field regardless of the `trimws` line.

So `n = 320`, `n_event = 91`, `n_dropped = 0`, and the `stageNA` term is present
— identical to the live app, which is the whole point of the fix.

**What it used to read, and why the case exists.** Before 2026-07-28 the
preamble was two lines with no `na.strings` override:

```r
df <- read.csv("data.csv", check.names = FALSE)
df[df == ""] <- NA   # blank cells are missing values
```

`read.csv`'s default `na.strings = "NA"` turned those eight `stage` cells into
real missing values **before** the script's own prep ran; `complete.cases(dat)`
then dropped the rows. The script's model had **three** `stage` levels and fitted
312 rows: `n = 312`, `n_event = 87`, `n_dropped = 8`, and **no `stageNA` term at
all**.

## Expected result — a case DESIGNED to fail, now passing

`fit_logistic` (Path B) models the live app. It therefore agrees with the screen
in both eras, and the case's verdict is a direct readout of whether the exported
script agrees with the app.

**Today (post-fix): 52 values compared, 0 findings, all four tiers PASS.** The
exported script's full-precision harvest matches Path B on every term including
`stageNA`, on all three counts, and on the C-statistic; the display tier passes
as it always did. `exact_targets` are the same six as `logistic-confounding` and
all are met.

**Before the fix: 46 compared, 30 findings**, every one of them attributed to the
export path —

- **display tier: PASS.** Every displayed cell — including the `NA` stage row —
  was reproduced exactly by Path B pushed through the app's own display rule.
  The app and the independent implementation agreed completely about what the
  user was shown. This never changed.
- **`COUNT_MISMATCH` x3** — `n` 312 vs 320, `n_event` 87 vs 91, `n_dropped` 8 vs 0.
- **`MISSING_QUANTITY` x1** — `stage:NA`: Path A's harvest had no
  full-precision term `stageNA` at all, because the script never saw the level.
- **`SCRIPT_DIVERGENCE` x5** — one per displayed adjusted cell (4), plus the
  exported script's C-statistic sentence: the exported `.R`, rendered through
  the app's own display rule, did not reproduce the screen.
- **`DEFECT` x21** — est/se/lo/hi/p for each of the four shared terms (20) plus
  the `c_statistic` itself, all beyond rel 1e-6: the two paths fitted different
  data.

`targets_met: true` with `passed: false` was the honest shape for that era — the
coverage contract was discharged and the comparison found real disagreements. The
comparator exited 1, which was the correct pipeline outcome; `findings.json` and
the scorecard were still written, because the failing evidence WAS the
deliverable.

**Why the compared count rose 46 -> 52** (corrected 2026-07-28; an earlier draft
credited the C-statistic pair, which is wrong — see the two C-statistic findings
listed under Diagnostics below, which are pre-fix and which *are* comparisons).
All six are the `stageNA` term's: its **five** full-precision quantities
(`est`/`se`/`lo`/`hi`/`p`, previously a single `MISSING_QUANTITY` for the whole
absent term, recorded before the per-quantity loop was ever reached) and the
**one** script-tier "exported script cell" it adds, because that tier iterates
the harvested term set and that set grew from four terms to five. Tier by tier:

| tier | before | after |
| --- | --- | --- |
| counts | 3 | 3 |
| display (5 rows x 2 columns) | 10 | 10 |
| exact (terms x 5 quantities) | 20 | 25 |
| script (1 cell per harvested term) | 4 | 5 |
| diagnostics | 9 | 9 |
| **total** | **46** | **52** |

Every component held or grew. A published finding is emitted *after* the
comparison that produced it is counted, so anything with a pre-fix finding —
the C-statistic included — was already being compared.

**Do not suppress, special-case, or "fix" this case in either direction.** Its
findings were the mechanical catch of issue 02 divergence 1, which until it
shipped existed only as a hand-built repro in a Markdown file; its silence now is
the evidence that the fix holds. If it goes red again, the exported script has
drifted from `web/lib/csv.js`, and that is a real app defect, not a case to
adjust.

## Diagnostics

**The diagnostics contract is identical to
`stats-validation/spec/logistic-confounding.md`'s Diagnostics section.** Read
that file for the C-statistic construction, the VIF rule, EPV, Cook's distance,
the separation caution, and which tier judges which. `fit_logistic` needs no new
diagnostics behaviour for this case either.

What the dirt does to the diagnostics, measured on both readers, before and after
the issue-02 fix:

| quantity | live app / Path B (320 rows, 4 stage levels) | exported script, post-fix (320 rows, 4 levels) | exported script, pre-fix (312 rows, 3 levels) |
| --- | --- | --- | --- |
| `c_statistic` | 0.6866452324967609, displayed `0.69` | 0.686645232496761, renders `0.69` | 0.68265644955300131, rendered `0.68` |
| `cooks_influential` | 15 | 15 | 13 (never computed by the script; measured only to show the dirt moved it) |
| `epv` | 91 / 5 = 18.2, not triggered | same | 87 / 4 = 21.75, not triggered |
| `vif` | `None` — only one continuous covariate (`age`) | same | same |
| `separation_caution` | false | false | false |

The dirt reaches the diagnostics too, and before the fix it reached them in the
same direction as the estimates: the app and Path B agreed, and the exported
script disagreed with both. Those were this case's last two findings —

- **`DEFECT` x1** — exact tier, `c_statistic` 0.68265644955300131 (exported
  script) vs 0.6866452324967609 (Path B), beyond rel 1e-6.
- **`SCRIPT_DIVERGENCE` x1** — script tier, the exported `.R`'s C-statistic
  rendered ` ... C-statistic = 0.68.` where the screen showed `0.69`.

— and both are gone: the script now fits the same 320 rows, so its C-statistic
agrees with Path B to the last published digit and renders the same `0.69`. Every
display-tier diagnostic PASSED throughout: the C-statistic sentence, the absent
VIF and EPV sentences, the 15-observation Cook's sentence and the absent
separation sentence are all reproduced exactly by Path B. Through both eras the
screen was right; only the export path ever moved.

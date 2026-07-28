# 02 — The downloadable/exported `.R` script's cell handling disagrees with the live app (KM, Cox, and Group comparison)

Status: resolved
Type: task
Location: **`stats-validation/issues/`, not `.scratch/<slug>/issues/`.** This is a
deliberate deviation from `docs/agents/issue-tracker.md` and the repo `CLAUDE.md`.
`.scratch/` is gitignored, and this issue is *published evidence* — the scorecard,
`expected-findings.json` and the shipped `logistic-dirty` case all cite it — so it
has to be tracked. Phase 1 must not edit anything outside `stats-validation/`, so
the convention docs were left unamended rather than updated to mention this
directory. See `stats-validation/README.md` §"Where the issue files live".
Found: 2026-07-25, during Task 9's fix round (statistical-validation phase 1), while
correcting `stats-validation/spec/km-twoarm.md`'s Population section against the real
behavior of the exported script `R/km.R`'s `.km_script` generates (Task 9's original pass
had asserted the live app and the exported script "agree" on blank-cell handling; that
claim was too broad — it holds only for a truly empty cell, not for the two cases below).

Extended 2026-07-26, during Task 10's fix round, with a **third divergence of the same
family — untrimmed text cells producing phantom group levels** (see "Divergence 3" below).
It is not a missing-value divergence at all, which is why the title now says "cell
handling"; it shares the root cause (the exported script re-reads the CSV with `read.csv`
instead of reproducing the browser parser) and the same fix would address all three.

## Problem

Every figure's exported `.R` script is assembled by the same shared preamble,
`.script_assemble` (`R/script.R:63-70`) via `.script_data` (`R/script.R:37-59`), which for a
file-backed upload emits:

```r
df <- read.csv("<filename>", check.names = FALSE)
df[df == ""] <- NA   # blank cells are missing values
```

`read.csv` (via `read.table`) has a default argument `na.strings = "NA"` that is NOT
overridden here. That default interacts with the second line in two ways the comment does
not mention, producing a real behavioral divergence from the live app (which parses CSVs
entirely in the browser, in `web/lib/csv.js`, and never calls `read.csv` at all):

1. **A literal `"NA"` text cell is silently converted to R's real `NA` by `read.csv` itself,
   BEFORE `df[df == ""] <- NA` ever runs.** The row is then dropped by whatever
   `complete.cases()`/`!is.na(...)` filter the script's own prep applies — even though the
   live app's blank-check (`String(v).trim() === ""` in `web/guided/km/spec.js`'s `blank()`,
   or the absence of any such check at all for Cox's status column, see below) never treats
   the two-character text `"NA"` as missing.
2. **A whitespace-only cell (e.g. a single space `" "`) is NOT converted to NA by either
   line.** `read.csv`'s default `na.strings` matches only the literal text `"NA"`, not
   whitespace; `df[df == ""] <- NA` compares for exact equality to the empty string, and
   `" " != ""`. The cell survives into the script's working frame as the literal
   one-character string `" "`. The live app's JS-side `blank()` helper, where one exists,
   TRIMS first (`String(v).trim() === ""`), so the identical cell is treated as missing
   there.

A third, KM-specific divergence: KM's exported script (`R/km.R:219-224`, `.km_script`) emits
an extra numeric-equality OR branch when recoding status —
`status_raw == event_value | (both parse as numbers & numerically equal)` — that the live
app's event-coding rule (`web/guided/km/spec.js`: `String(s) === String(eventValue) ? 1 : 0`)
does not have. It is inert whenever the event value is non-numeric (as in the `km-twoarm`
case, `event_value = "Death"`), but real, and would matter for a numeric event value (e.g.
`event_value = "1"` against a status column `read.csv` infers as numeric, so a cell literally
`1` compares as a number, not a string, to `"1"`).

## Verified repro — KM

Generated a real `fig_km` spec (24 rows: 20 ordinary + 4 special) via `devtools::load_all()`
+ `render_figure()`, with two special rows: `followup_months = 9999, status = "NA"` (literal
text) and `followup_months = 8888, status = " "` (whitespace). Wrote the equivalent
`data.csv`, extracted the real `res$code` (the exact `.km_script` output for this spec), and
ran it in a clean environment:

```
live app (post JS blank-filter): 23 of 24 rows kept — JS dropped exactly the
  whitespace row (time=8888); the literal-"NA" row (time=9999) survived, coded
  censored (0).
exported script's `dat`:          23 of 24 rows kept — read.csv's na.strings="NA"
  dropped exactly the literal-"NA" row (time=9999); the whitespace row
  (time=8888) survived as status=" ", also coded censored (0).
```

**Both paths agree on the row COUNT (23) by coincidence, but disagree on WHICH row survives**
— a comparator or user checking only `n`/`n_dropped` would see no discrepancy at all; only a
row-by-row diff (or the literal presence/absence of `time == 9999` / `time == 8888` in `dat`)
reveals it. This is exactly the kind of silent divergence `stats-validation/spec/km-twoarm.md`
now calls out explicitly rather than asserting general agreement.

## Verified repro — Cox

Same method (`devtools::load_all()` + `render_figure(figure = "cox")`, 34 rows: 30 ordinary +
one literal-`"NA"`-status row at `followup_months = 9999` + one whitespace-status row at
`followup_months = 8888`, one categorical covariate `arm`):

```
live app: n = 34 (per the displayed methods sentence) — Cox's live app has NO
  blank-check on status at all (issue 01: `.cox_prep` never converts a blank/odd
  status cell to NA), so BOTH the literal-"NA" row and the whitespace row are
  kept, each coded censored (status = 0).
exported script's `dat`: 33 rows. The literal-"NA" row (time=9999) is ABSENT —
  read.csv's na.strings="NA" converts its status cell to real NA before the
  script's own `as.character(status_raw) == "Death"` recode runs, so the
  recoded status is NA too, and `complete.cases(dat)` drops the row. The
  whitespace row (time=8888) IS present, status coded 0 (censored) — same
  as the live app for that one row, since neither read.csv's na.strings nor
  `df[df == ""] <- NA` touches a literal " " status cell, and
  `as.numeric(" ")` is NA in both the live app's numeric path and the
  script's, so no numeric-fallback branch fires for it either.
```

So for Cox specifically: the **literal-`"NA"`-text divergence is real and verified** (script
drops a row the live app keeps) — this is the aside flagged as unverified in Task 8's own
report (`stats-validation/.sdd/task-8-report.md`'s Concern 1 predecessor, restated in Task
9's original report as "plausible from reading `R/script.R`'s shared preamble, but not
empirically re-verified"; it is now empirically verified). The **whitespace-only divergence
does NOT reproduce for Cox's status column** — both the live app and the exported script
already agree it survives as censored, because Cox's live app has no `blank()`-style
trim-and-drop check on status in the first place (issue 01), unlike KM's. (Whitespace-only
TIME cells do not diverge either, for both figures: `as.numeric(" ")` is `NA` in R regardless
of which code path calls it, so both the live app's `.numeric_col`/`buildKmSpec` numeric
coercion and the script's own `as.numeric(...)` treat it as missing identically.)

The numeric-equality-branch divergence does **not** apply to Cox: Cox's live app
(`R/cox.R:46-49`, `.cox_prep`) already has the identical numeric-equality OR fallback its own
exported script (`R/cox.R:314-320`, `.cox_script`) does — both paths agree there. It is
KM-specific, because KM's live-app event recoding happens in JavaScript
(`web/guided/km/spec.js`) with no numeric fallback at all, while its exported script's prep
(regenerated in R) adds one.

## Divergence 3 — untrimmed text cells become phantom group levels (Group comparison)

Found 2026-07-26 during Task 10's fix round, on `stats-validation/spec/groupcompare-*.md`.
Same root cause as the two above (the script re-reads the CSV with `read.csv` rather than
reproducing the browser parser), different symptom, and **worse**: it can make the exported
script fail outright, or silently analyse a study with one more arm than the app did.

The live app's CSV parser applies `String(cell).trim()` to every cell as it builds the
table (`web/lib/csv.js`'s `parseCsv`), so `"Placebo "` and `"Placebo"` are one value. R's
`read.csv` does **not** trim character columns, so in the exported script they are two.
Group comparison is where this bites hardest, because it is the only analysis whose GROUP
role is free text with no reference level, no event value, and no recoding step in front of
it — an extra level goes straight into `table(dat$group)` and changes the analysis.
(`.gc_prep` drops groups with fewer than two values, so a *single* padded cell is absorbed;
two or more identically-padded cells create a surviving phantom level.)

### Verified repro 3a — the exported script does not run at all

30 rows, `arm` = `Drug` x10, `Placebo` x14, `Placebo ` x6 (trailing space), one numeric
`value` column. Built the live-app spec from the TRIMMED cells (what `parseCsv` hands R),
ran `render_figure()`, wrote `res$code` to disk, and executed it against the CSV with the
padding intact:

```
live app:   2 groups — Drug(10), Placebo(20)
            "value across groups: Drug 12.2 ± 2.53; Placebo 11.1 ± 2.11.
             Welch t-test (approximately normal (Shapiro–Wilk p = 0.244)):
             p = 0.244, Cohen's d = -0.499 (95% CI -1.27 to 0.27) (Placebo vs Drug)."
read.csv:   3 groups — 'Drug'(10), 'Placebo'(14), 'Placebo '(6)
exported script: Error in t.test.formula(value ~ group, data = dat) :
                   grouping factor must have exactly 2 levels
```

The app saw two levels, so it deparsed `t.test(value ~ group, data = dat)` into the script.
The script's own `dat` has three. The download is a hard error in the user's face, with
nothing in the app or the script explaining why.

### Verified repro 3b — the exported script runs and quietly answers a different question

60 rows, `arm` = `High` x20, `Low` x20, `Placebo` x14, `Placebo ` x6:

```
live app:   3 groups — High(20), Low(20), Placebo(20)
            Welch F = 16.4548849843620, p = 7.3519740079422e-06 (displayed "p < 0.001")
            eta-squared = 0.394 (95% CI 0.186 to 0.532)
            Tukey HSD, significant pairs: Low-High, Placebo-High, Placebo-Low
read.csv:   4 groups — 'High'(20), 'Low'(20), 'Placebo'(14), 'Placebo '(6)
exported script (ran cleanly, nrow(dat) = 60):
            one-way ANOVA (Welch), p = 0.00017732165567181   (24x the app's p)
            eta-squared = 0.411 (95% CI 0.189 to 0.539)
            Tukey HSD, significant pairs: Low-High, Placebo-High, Placebo -High,
                                          Placebo-Low
```

Note the fourth post-hoc pair, `Placebo -High` — a comparison between two spellings of the
same arm, printed to the user as a finding. **`nrow(dat)` is 60 on both paths**, so a
row-count check catches nothing here either; only the level set differs.

## Impact

A user who downloads and runs the exported `.R` script for either figure, on data containing
a literal `"NA"` text cell or a whitespace-only cell in the status/event column, can get a
**different set of analysed rows** than the one the live app fit and displayed — silently,
with no warning in either place, and (for KM, per the repro above) without even a `n`/`n`
row-count mismatch to flag it. This directly undermines the app's own "the statistical calls
below are the exact calls the app ran" honesty line (`R/script.R:21`, `.script_header`'s
default `honesty` text) for any CSV containing either kind of cell — the CALLS are exact, but
the DATA the calls run over is not guaranteed to be the same data the app itself analysed.

Divergence 3 raises that from "different rows" to "different study design": the exported
Group-comparison script can compare four arms where the app compared three (repro 3b), or
refuse to run because the app deparsed a two-group test into a script whose data has three
groups (repro 3a). Both are reachable from an ordinary CSV with a stray trailing space —
one of the most common defects in a real clinical data export, and one the live app is
specifically built to absorb.

## Repro (reusable)

1. Build (or upload) a CSV with a status/event column containing, on separate rows: the
   literal event-value string (e.g. `Death`), the literal two-character text `NA`, a
   whitespace-only cell (e.g. a single space), a truly empty cell, and the literal
   non-event string (e.g. `Censored`).
2. Run it through the guided KM (or Cox) analyze form; note `n`/`n_dropped` and which rows
   the app kept.
3. Download the exported `.R` script for that exact run and execute it against the same CSV
   in a fresh R session; inspect its working frame (`dat`) — compare row-for-row (not just by
   count) against the app's own kept rows.
4. Expect: the literal-`"NA"`-text row is present in the app's analysis and absent from the
   script's; the whitespace-only row is present in the script's analysis and (KM only) absent
   from the app's.

For divergence 3, Group comparison:

1. Build a CSV whose GROUP column holds one arm spelled two ways — `Placebo` on most rows
   and `Placebo ` (one trailing space) on at least two others — plus a numeric outcome.
2. Run it through the guided Group comparison analyze form; note the arm count in the
   displayed sentence and the test the app chose.
3. Download the `.R` script for that run and execute it in the same folder as the CSV.
4. Expect: with two app-visible arms the script errors with `grouping factor must have
   exactly 2 levels`; with three or more it runs, reports one extra arm, a different
   p-value and effect size, and a post-hoc pair naming the padded spelling.

## Scope note

This is a genuine app-behavior finding surfaced while writing/correcting the independent
validation spec (`stats-validation/spec/km-twoarm.md`), not a defect in the validation harness
itself — mirrors issue 01's own scope note. `fit_km`'s spec has been corrected to model the
live app only and state this divergence explicitly rather than assert general agreement.
Fixing `R/script.R`'s `.script_data` (e.g. passing `na.strings = character(0)` to `read.csv`
so only the script's own `df[df == ""] <- NA` line defines "missing," and/or trimming
whitespace there too) is out of scope for this task and left for a maintainer decision — it
is a behavior change to a shipped, shared code path (`.script_assemble` backs every
analysis's export, not just KM's and Cox's), not a validation-tooling fix.

The same applies to divergence 3, surfaced while writing
`stats-validation/spec/groupcompare-{numeric,categorical,dirty}.md`. All three gc specs
already model the live app only and state the divergence explicitly. Note that the natural
fix for divergences 1 and 2 (`na.strings = character(0)`) does **not** address 3 — that one
needs the emitted preamble to trim character columns as well, e.g. a
`df[] <- lapply(df, function(x) if (is.character(x)) trimws(x) else x)` line beside the
existing `df[df == ""] <- NA`, applied before it so a whitespace-only cell also becomes
blank. One shared preamble change would close all three at once; that is a maintainer
decision, not a harness one.

## Disposition — divergence 1 is now mechanically caught (2026-07-26)

Added during Task 11. Divergence 1 (a literal `"NA"` text cell dropped by the exported
script's `read.csv` and kept by the live app) is no longer only a hand-built repro in this
file: it is now a **shipped, permanently-running validation case**,
`stats-validation/cases/logistic-dirty/` (spec: `stats-validation/spec/logistic-dirty.md`),
which is in the Makefile's `CASES` and runs on every `make -C stats-validation all`.

The case is `logistic-confounding`'s data with eight `stage` cells changed to the literal
text `NA` (plus two trailing-space `age` cells, on a NUMERIC column only — padding a factor
level is divergence 3, already verified above, and would only produce a permanently-broken
export rather than new information). Running the full pipeline publishes **30 findings**
(this read 28 before amendment A14 added the C-statistic pair below; the shipped evidence
in `results/findings.json` and `expected-findings.json` is 30 — 3/1/5/21):

- **3 x `COUNT_MISMATCH`** — `n` 312 vs 320, `n_event` 87 vs 91, `n_dropped` 8 vs 0. The
  exported script analysed 8 fewer patients than the app displayed.
- **1 x `MISSING_QUANTITY`** — `stage:NA`: the app fitted and displayed a `stageNA`
  coefficient (OR 4.02, 95% CI 0.90-17.91, p = 0.068); the exported script has no such term
  at all, because it never saw the level.
- **5 x `SCRIPT_DIVERGENCE`** — one per displayed adjusted cell (4), plus the exported
  script's C-statistic sentence (screen: `apparent (in-sample) C-statistic = 0.69`;
  script: `C-statistic = 0.68`). The downloaded `.R` does not reproduce a single one of
  them.
- **21 x `DEFECT`** — est/se/lo/hi/p for all four shared terms (20), plus the
  `c_statistic` itself (0.68265645 vs 0.686645232), all beyond rel 1e-6.
- **display tier: PASS.** The app and the independent Python re-implementation agree
  completely about what the screen showed. The disagreement is entirely between the app and
  its own exported script — which is precisely this issue.

*(Written 2026-07-26, before the fix. Superseded by "Resolution" below: the fix landed
2026-07-28 and this case now publishes 0 findings across 52 compared values.)*

**This does not close the issue.** The underlying behaviour is unchanged, and the fix is
still the maintainer decision described in the Scope note above (`na.strings = character(0)`
plus a `trimws` pass in `R/script.R`'s `.script_data`, which would close all three
divergences at once). What has changed is that the divergence is now *measured on every
run and published on the scorecard* instead of living only in this file, and that a future
fix to `.script_data` will show up immediately as `logistic-dirty` going green.

**Do not "fix" the case to make the scorecard green.** `stats-validation/cases/logistic-dirty`
is expected to fail; its findings ARE the deliverable. The comparator exits 1 for it, and the
Makefile is structured so the scorecard is still built from the written `findings.json`
before that status is propagated.

## Disposition — publicly disclosed on the validation page (2026-07-26)

Added during Phase 2 item 1. This defect is no longer only tracked internally: it is
**explained to users on `web/validation.html`**, the page the app links from its nav rail,
generated from `results/findings.json` by `build_scorecard.py --web` and regenerated on
every run.

The page states, in clinical language rather than in finding codes: that the app fitted 320
patients and the downloaded script fitted 312; that all four adjusted odds ratios and the
C-statistic move; that the `stage = NA` row the app displayed has no counterpart in the
script's output; that **the displayed numbers were right** (the screen-vs-Path-B comparison
passed, and the page renders that claim only while every finding on the case is
export-path — a single `screen vs Python` finding switches it to a generic block); that the
defect is **known, open, and tracked in this file**, with the `R/script.R` `.script_data`
fix planned; and who it affects (only a downloaded script, only for a file containing
`NA`-as-text or padded cells). The "how to check this yourself" section carries the same
caveat against its own advice to re-run the exported `.R`.

Two consequences for whoever lands the fix (*both discharged 2026-07-28 — see
"Resolution" below: `CASE_STATUS`/`CASE_CAUSE` are now empty dicts, and the fix commit
regenerated the page*):

- **The page's copy is generated, not written.** Every number in it comes from
  `findings.json`, and the narrative block, the caveat and the `CASE_STATUS` box are all
  keyed to this case's findings existing. When the fix lands and `logistic-dirty` goes
  green, they disappear on their own — no prose to remember to delete. What DOES need a
  human is `build_scorecard.py`'s `CASE_STATUS["logistic-dirty"]`, which says "it has not
  landed as of the evidence on this page": that sentence is only reachable while findings
  exist, but if the fix lands it should be removed with them rather than left dormant.
- **CI byte-diffs `web/validation.html`.** The fix commit must regenerate it (`make -C
  stats-validation all`) alongside `expected-findings.json` and the scorecard, in the same
  commit, or the build fails on a stale published page.

## Resolution — all three divergences closed in `.script_data` (2026-07-28)

Phase 2 item 2. **One change, in `R/script.R`'s `.script_data` uploaded-file branch.**
The emitted preamble went from two lines to three, and now reproduces `parseCsv`
(`web/lib/csv.js:21`, `row[c] = (cells[j] ?? "").trim()`) instead of relying on
`read.csv`'s defaults:

```r
# before
df <- read.csv("data.csv", check.names = FALSE)
df[df == ""] <- NA   # blank cells are missing values

# after
df <- read.csv("data.csv", check.names = FALSE, na.strings = character(0))
df[] <- lapply(df, function(x) if (is.character(x)) trimws(x) else x)
df[df == ""] <- NA
```

(preceded by a four-line comment saying, in the app's voice, that these lines read the
file the way the app read it). Which line closes which divergence:

- **Divergence 1 — literal `"NA"` eaten.** `na.strings = character(0)` removes the only
  string `read.csv` would otherwise convert. The two-character text `NA` now arrives as
  the value `"NA"`, exactly as `parseCsv` delivers it, and becomes an ordinary factor
  level rather than a dropped row.
- **Divergence 2 — whitespace-only cell survives.** `trimws` on every character column
  turns `" "` into `""`, which the existing `df[df == ""] <- NA` line then makes missing.
  Order is load-bearing: trimming must run BEFORE the blank check, or `" "` survives it.
- **Divergence 3 — padded text becomes a phantom level.** The same `trimws` pass makes
  `"Placebo "` and `"Placebo"` one value, so a two-arm comparison stays two-arm and the
  deparsed `t.test` runs instead of dying on `grouping factor must have exactly 2 levels`.

**`colClasses = "character"` was considered and rejected.** It would be the most literal
mirror of `parseCsv` (which hands R strings for every column), but it breaks
`.summary_script`, whose emitted code calls `mean()`/`quantile()` on the raw column with
no `as.numeric()` in front of it. It is also unnecessary: `read.table` always strips
whitespace from a numeric field and reads a blank one as `NA`, so numeric columns already
agreed with `parseCsv` on all three counts — verified empirically before choosing, not
assumed. Type inference stays in agreement too: a column carrying a literal `NA` fails
`type.convert` under `na.strings = character(0)` and comes back character, which is what
`parseCsv`'s own numeric test decides for the same column.

**The embedded-example branch (no `source_filename`) needed no change**, and now says so
in a comment. Its cells are `spec$data`, which already came through `parseCsv`; a literal
`"NA"` fails its `as.numeric` test, stays character, and deparses back out as the quoted
string `"NA"` while a real `NA` deparses bare — so the distinction the file branch had to
restore was never lost there.

**Regression cover:** `tests/testthat/fixtures/dirty-cells.csv` (30 rows carrying a
literal `NA`, a whitespace-only cell, and a padded text value) plus three tests in
`tests/testthat/test-script.R`, which transcribe `parseCsv` into R as the reference and
assert against the app, not against a second copy of the script's own rules: the emitted
preamble's frame cell-for-cell, an end-to-end logistic run (row count, coded outcome,
factor levels, joint coefficients), and the group-comparison script running at all on
padded group cells. All three fail on the pre-fix `.script_data` (verified by reverting).

**Measured result — the pipeline, not a prediction.** `make -C stats-validation clean all`:

```
                            before            after
logistic-dirty              46 compared, 30 findings   52 compared, 0 findings
every other case            unchanged                  unchanged
total                       325 compared, 30 findings  331 compared, 0 findings
```

`make all` exits 0 for the first time. The comparison count rose by 6 because the
`stage = NA` term now exists on both sides, so its five quantities plus the C-statistic
pair became comparable instead of being a `MISSING_QUANTITY`. `expected-findings.json`
was rewritten by `make gate-update` in the same commit; `web/validation.html` and
`results/scorecard.html` regenerated; two consecutive `make clean all` runs are
byte-identical.

**`logistic-dirty` stays in the roster and stays exactly as it is.** It was never a case
to "fix"; it is now the standing regression test for this issue on the published page —
a case built to fail that passes only while `.script_data` keeps parity with `parseCsv`.

**The standing contract, for whoever edits `.script_data` next:** the emitted preamble
must reproduce `parseCsv` (`web/lib/csv.js`), not `read.csv`'s defaults. The app parses
CSVs in the browser and never calls `read.csv` at all, so any divergence between the two
readers is a divergence between the screen and the download.

**Not fixed here, and still open:** the KM-specific numeric-equality branch described
above (`R/km.R:219-224` adds an OR term the live app's JS event coding has no counterpart
for). It is a different mechanism in a different file, out of this task's scope, and
remains inert for a non-numeric event value.

## Comments

None yet.

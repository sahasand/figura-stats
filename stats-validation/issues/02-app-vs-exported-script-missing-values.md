# 02 — The downloadable/exported `.R` script's missing-value handling disagrees with the live app (KM and Cox)

Status: needs-triage
Type: task
Found: 2026-07-25, during Task 9's fix round (statistical-validation phase 1), while
correcting `stats-validation/spec/km-twoarm.md`'s Population section against the real
behavior of the exported script `R/km.R`'s `.km_script` generates (Task 9's original pass
had asserted the live app and the exported script "agree" on blank-cell handling; that
claim was too broad — it holds only for a truly empty cell, not for the two cases below).

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

## Impact

A user who downloads and runs the exported `.R` script for either figure, on data containing
a literal `"NA"` text cell or a whitespace-only cell in the status/event column, can get a
**different set of analysed rows** than the one the live app fit and displayed — silently,
with no warning in either place, and (for KM, per the repro above) without even a `n`/`n`
row-count mismatch to flag it. This directly undermines the app's own "the statistical calls
below are the exact calls the app ran" honesty line (`R/script.R:21`, `.script_header`'s
default `honesty` text) for any CSV containing either kind of cell — the CALLS are exact, but
the DATA the calls run over is not guaranteed to be the same data the app itself analysed.

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

## Comments

None yet.

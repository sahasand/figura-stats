# 01 — Cox silently codes a blank status cell as censored; logistic drops the analogous blank outcome cell

Status: needs-triage
Type: task
Found: 2026-07-25, during Task 8's fix round (statistical-validation phase 1), while
reconciling `stats-validation/spec/cox-adjusted.md`'s Population/Status-coding sections
against the real behavior of `R/cox.R`.

## Problem

`fig_cox` and `fig_logistic` treat a blank event-column cell (status for Cox, outcome for
logistic) differently, and only one of the two says so anywhere.

**Logistic explicitly converts a blank outcome cell to missing**, so the row is dropped by
`complete.cases()`:

- `R/logistic.R:47` — `ev <- as.character(spec$options$event_value %||% "")`
- `R/logistic.R:48` — `outcome_raw <- .char_col(rows, ocol)`
- `R/logistic.R:49-50` — comment: "A blank outcome cell is missing, not a non-event: NA here
  so complete.cases drops the row instead of silently counting it in the non-event group."
- `R/logistic.R:51` — `outcome_raw[!is.na(outcome_raw) & outcome_raw == ""] <- NA`
- `R/logistic.R:52-55` — `y <- as.integer(outcome_raw == ev | (...))`, now operating on the
  NA-substituted vector, so a blank cell propagates to `y = NA` and is dropped downstream by
  `df[stats::complete.cases(df), ]` (`R/logistic.R:73`).

**Cox has no equivalent conversion.** `.cox_prep` reads the status column and compares it to
the event value directly, with no blank-to-NA step first:

- `R/cox.R:44` — `ev <- as.character(spec$options$event_value %||% "")`
- `R/cox.R:45` — `status_raw <- .char_col(rows, scol)` (no blank-to-NA rewrite anywhere)
- `R/cox.R:46-49` —
  ```r
  ev_num <- suppressWarnings(as.numeric(ev))
  status <- as.integer(status_raw == ev |
    (!is.na(ev_num) & !is.na(suppressWarnings(as.numeric(status_raw))) &
       suppressWarnings(as.numeric(status_raw)) == ev_num))
  ```
- `R/cox.R:50` — `status[is.na(status)] <- NA_integer_` (a no-op here: see below)

For a blank cell, `.char_col` (`R/summarize.R:92-97`) returns `""`, not `NA` — confirmed by
tracing `web/lib/csv.js`'s `parseCsv`, which always writes `row[c] = (cells[j] ?? "").trim()`
for every declared column of every row (`web/lib/csv.js:21`); a blank CSV cell is `""` in the
spec JSON, never a missing key. So for a blank status cell: `status_raw == ev` evaluates
`"" == "Death"` → `FALSE`; the numeric branch is also `FALSE` (`ev_num` is `NA` because
`"Death"` does not parse as a number, so `!is.na(ev_num)` is `FALSE`); the whole OR is
`FALSE`; `status <- as.integer(FALSE)` = `0L`, not `NA`. `status[is.na(status)] <- NA_integer_`
at line 50 never fires for this row, because `status` is already `0L`, not `NA`.

That `0` then flows into `.cox_prep`'s working frame as an ordinary, non-missing value:
`stats::complete.cases(df)` (`R/cox.R:67`) sees a real integer, not `NA`, and **keeps the row**
— counted as a censored observation (`status == 0`) in `n`, `n_event` (excluded, correctly,
since it is not an event), and the fitted model.

## Impact

A user who uploads a CSV with a genuinely blank status cell (a data-entry gap, not a
recorded outcome) gets that row silently folded into the risk set as **censored at whatever
time value the row carries** — a real modelling assumption applied without the user's
knowledge or consent, and without appearing in `n_dropped` or the "N row(s) with missing
values were excluded" methods sentence (`R/cox.R:202-203`), because the row was never
dropped. The equivalent gap in logistic regression cannot happen: the analogous blank
outcome cell is caught and the row is excluded, with `n_dropped` and the methods sentence
both reflecting it.

This is not a crash and not visibly wrong output — the table renders, the numbers are
internally consistent, and nothing warns the user. That is exactly what makes it worth
flagging: a censored-vs-missing conflation is a substantive difference in survival analysis
(one is "we don't know," the other is "we know they did not have the event by this time"),
and only careful line-by-line tracing of the blank-cell path surfaces it.

## Repro

1. Take `stats-validation/cases/cox-adjusted/data.csv` (or any Cox-eligible CSV) and blank out
   the `status` cell on one row, leaving `followup_months`/covariates populated.
2. Run it through the guided Cox analyze form (`web/guided/cox/`), or call `fig_cox()` directly
   with that row present.
3. Compare `n`/`n_event`/the drop-count sentence against the same experiment run through
   logistic regression with an analogous blank outcome cell on one row.
4. Cox: `n` includes the blank-status row, `n_event` is unaffected (row treated as censored),
   no drop is reported for it. Logistic: `n` excludes the blank-outcome row, and (if it is the
   only dropped row) the drop-count sentence reports it.

## Scope note

This is a genuine app-behavior finding surfaced while writing the independent validation spec
(`stats-validation/spec/cox-adjusted.md`), not a defect in the validation harness itself. The
spec has been corrected to document Cox's actual behavior (a blank status cell is censored,
not missing) rather than assert the behavior logistic has and Cox does not — see that file's
Population and Status coding sections. Fixing `R/cox.R` itself (e.g., mirroring
`R/logistic.R:51`'s blank-to-NA rewrite so a blank status cell is dropped like a blank outcome
cell, if that is judged to be the desired behavior) is out of scope for this task and is left
for a maintainer decision — it is a behavior change to a shipped figure, not a validation-tooling
fix.

## Comments

None yet.

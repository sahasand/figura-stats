# Analysis spec: km-twoarm

Input: `stats-validation/cases/km-twoarm/data.csv`. The real header is
`participant_id,followup_months,status,group` — `participant_id` is not a
mapped role and must never influence the analysis or cross into any
intermediate representation. The mapped roles are: time = `followup_months`,
status = `status`, group = `group`. The event value is the literal string
`"Death"` (the other observed status value, `"Censored"`, is not special —
see Event coding below for the actual rule, which does not hardcode either
string).

## Population

**This spec, and `fit_km`, model the LIVE APP ONLY** (`web/guided/km/spec.js`'s
`buildKmSpec`, which is what a user's browser session actually runs) — never
the downloadable/exported `.R` script. The two are NOT interchangeable for
missing-value handling; see the divergence note at the end of this section
before assuming otherwise.

Complete cases across all three roles: time, status, AND group. A row is
dropped, and counted in `n_dropped`, when time, status, or group is blank
(an empty string after trimming whitespace) — unlike Cox regression, where a
blank status cell is coded as censored rather than dropped, Kaplan-Meier
drops a blank status cell exactly like a blank time or group cell. Verified
directly in the live app's own source: `buildKmSpec` builds its working rows
with `if (blank(t) || blank(s) || blank(g)) { dropped++; continue; }`
(`blank = (v) => v == null || String(v).trim() === ""`) before any status
recoding happens — a blank status cell never reaches the figure-rendering
code at all.

The literal string `"NA"` is an ordinary value, not missing, in the live
app — do not treat it as blank. `blank()` above checks for the trimmed-empty
string specifically; the two-character text `"NA"` does not trim to `""`, so
it is kept as an ordinary (non-matching, hence censored) status value.

**Divergence from the exported script, a real, separately verified Figura
finding (`stats-validation/issues/02-app-vs-exported-script-missing-values.md`)
— stated here so this spec's Population rule is never mistaken for a
description of the script too:** the downloadable `.R` script's missing-value
handling was NOT identical to the live app's `blank()` rule above, in two
concrete ways.

> **Both are CLOSED as of 2026-07-28** (`issues/02` resolved). `.script_data`
> now emits `read.csv(..., na.strings = character(0))` plus a `trimws` pass
> ahead of `df[df == ""] <- NA`, so the exported script reads a cell the way
> `web/lib/csv.js` does. The two divergences below are kept in past tense
> because they are what this spec's Population rule had to be distinguished
> FROM, and because that agreement is now a contract on `R/script.R` rather
> than something to re-derive. **`fit_km` is unaffected either way: this spec
> models the live app, and the live app's rule never changed.**

- **A literal `"NA"` text cell IS treated as missing by the script**, unlike
  the live app: the script's `read.csv(...)` call (`R/script.R`'s
  `.script_data`, shared by every figure's export) uses R's default
  `na.strings = "NA"`, so a status cell containing the literal text `"NA"`
  becomes R's real `NA` at parse time — BEFORE the script's own
  `df[df == ""] <- NA` line ever runs — and the row is then dropped by the
  script's `!is.na(...)` filter. The live app keeps that same row (coded
  censored, unless the event value itself is the literal string `"NA"`).
- **A whitespace-only cell (e.g. a single space `" "`) is KEPT by the
  script**, unlike the live app: `df[df == ""] <- NA` matches the exact
  empty string only, so `" "` (which does not equal `""`) survives as the
  literal one-character string. The live app's `blank()` trims first, so the
  same cell is dropped there and counted in `n_dropped`. The script instead
  keeps the row, with the literal `" "` compared against the event value
  (per Event coding below) — a non-match, so the row survives as censored.

Both divergences were verified empirically (not just read from source): a
five-row fixture with `status` values `Death` / `NA` / `" "` (whitespace) /
`""` (empty) / `Censored`, run through both paths, produced the SAME row
COUNT after filtering (23 of 24 rows survived both the live app and the
script, in one concrete regenerated repro) but a DIFFERENT SET of surviving
rows — the app dropped the whitespace row and kept the literal-`"NA"` row;
the script dropped the literal-`"NA"` row and kept the whitespace row. See
the issue file for the full repro and line references. Re-run on the fixed
preamble both paths keep the literal-`"NA"` row and drop the whitespace one,
which is the app's answer.

Every non-blank time value must parse as a finite, non-negative number. This
is a precondition the app itself enforces at the whole-analysis level (`if
(any(!is.finite(df$time)) || any(df$time < 0)) stop(...)` in `R/km.R`'s
`fig_km`) rather than a per-row drop rule — a CSV that violates it fails the
entire figure, not just the offending row. The real case data always
satisfies this (`followup_months` is fully numeric and non-negative for
every one of the 120 rows), so this spec does not define `fit_km`'s
behaviour on a violating input; it is out of scope, exactly as it is for the
app.

## Event coding

The status column is `status`. A row is an event when its value is EXACTLY
EQUAL, as text, to the event value `"Death"`. Everything else non-blank
(here, exactly the value `"Censored"`, but the rule does not special-case
that string) is censored at its recorded time.

**This is a deliberate, verified departure from Cox and logistic
regression's event/outcome coding, which also accept numeric equality as a
fallback** (`cell == event_value`, OR both parse as numbers and are
numerically equal). Kaplan-Meier's event coding has no such fallback: the
app's live analyze form recodes status with `String(s) === String(eventValue)
? 1 : 0` (`web/guided/km/spec.js`) — plain string equality only, evaluated
entirely in the browser before any row ever reaches the R figure code (which
receives an already-0/1-coded `status` and never re-derives it). There is no
numeric-equality branch anywhere in this path. Do not reuse a numeric-
fallback event-coding helper (such as one written for Cox or logistic) here
without removing that fallback — on data where it would matter (e.g. a
status cell reading `"1.0"` against an event value of `"1"`), the two rules
disagree.

**This string-equality-only claim is scoped to the live app, per the
Population section above — the exported script is NOT the same code path
and does NOT follow this rule.** `R/km.R:219-224`'s `.km_script` DOES emit a
second, numeric-equality OR branch (`status_raw == suppressWarnings(as.numeric(event))`
when both sides parse as numbers) that the live app has no equivalent of.
For this case, that branch is inert — the event value `"Death"` never
parses as a number, so the fallback can never fire — but it is a real,
verified app-vs-script divergence for a case whose event value IS numeric
(e.g. `event_value = "1"` with a status column read.csv infers as numeric),
documented alongside the other two exported-script divergences in
`stats-validation/issues/02-app-vs-exported-script-missing-values.md`.
**This one is still open.** The two cell-reading divergences above were fixed
in `.script_data` on 2026-07-28; this branch lives in `R/km.R`'s own script
builder, is a different mechanism, and was out of that fix's scope.

## Roles

- **time** — numeric, the survival/censoring time. Must be present and a
  finite non-negative number for every analysed row (see Population).
- **status** — arbitrary text; recoded to event/censored per Event coding
  above. Not required to be `0`/`1`, `"Yes"`/`"No"`, or any other fixed
  vocabulary — only equality to the event value matters.
- **group** — arbitrary text; the stratification variable. Every distinct
  non-blank value occurring after the Population filter is its own group,
  with no ordering, reference level, or minimum-group-size requirement (this
  is unlike Cox/logistic's covariates, which need a declared or
  fallback-derived reference level for treatment contrasts — Kaplan-Meier
  has no such concept, since nothing here is a regression coefficient). This
  case has exactly two groups, `"Standard care"` and `"New treatment"`
  (60 rows each before the Population filter), but the estimator and the
  log-rank test below are both defined for any number of groups >= 1
  (log-rank requires >= 2 to be meaningful).

## Estimator

The Kaplan-Meier product-limit estimator, computed separately within each
level of the group column, using only that group's own rows.

Within one group, consider its distinct recorded time values in increasing
order. At each distinct time value `t`:

- `n(t)` = the number of that group's subjects still at risk at `t` — i.e.,
  every subject (event OR censored) whose recorded time is `>= t`. A
  subject censored at exactly `t` is STILL counted in `n(t)`: censoring at
  `t` removes a subject from the risk set only for times strictly AFTER
  `t`, never at `t` itself.
- `d(t)` = the number of that group's subjects with an event (per Event
  coding above) at exactly `t`.
- If `d(t) > 0`, the running survival probability is multiplied by
  `(1 - d(t)/n(t))`. `S(t)` is that running product immediately after
  processing `t`; `S(0) = 1` before the first distinct time.
- If `d(t) == 0` (a time with only censoring, no event), the survival
  probability does not change at `t`, and `t` is NOT one of the distinct
  event times reported in the step function (see Reported quantities).

**Tie convention, stated explicitly because it is the one place a naive
implementation silently disagrees with the correct answer:** when a single
timestamp carries BOTH one or more events and one or more censorings (e.g.
two subjects share the same recorded time, one with an event and one
censored), ALL subjects still at risk — including the ones being censored at
that exact timestamp — count in `n(t)`'s denominator. The censored
subject(s) leave the risk set only after the survival-probability drop at
`t` is computed, i.e., they are absent from `n(t')` for the NEXT distinct
time `t' > t`, never from `n(t)` itself. An implementation that removes a
tied censoring from the risk set BEFORE computing `n(t)` at that same `t`
will compute a smaller, wrong denominator and a wrong `S(t)`.

## Reported quantities

- **Median survival per group**: **R's actual rule, verified directly
  against a live `Rscript` run of `survival::survfit`/`summary()$table` (R
  4.6.0) — NOT the naive "smallest `t` with `S(t) <= 0.5`" reading of the
  product-limit formula, which is wrong in a case common enough to matter.**
  This is the same "minmin" rule `survival:::survmean` uses internally
  (verified by reading that function's source, `getAnywhere(survmean)`, not
  guessed). Let `tol = sqrt(.Machine$double.eps)` (~1.4901161e-08 in IEEE
  double precision — Python's `math.sqrt(sys.float_info.epsilon)` is the
  identical value):
  - Walk the group's step function (see the step function below; because
    `S(t)` only changes at event times, restricting the walk to distinct
    EVENT times, as this spec's step function already does, loses nothing —
    a pure-censoring time never causes `S` to first cross 0.5) in increasing
    `t` order and find the smallest `t1` with `S(t1) < 0.5 + tol`.
  - If no such `t1` exists — including a group with zero events, whose
    survival curve never drops from 1 — the median is NOT REACHED. Report it
    as such (`None`/null), NEVER as the group's largest observed time or any
    other numeric stand-in.
  - **If `S(t1)` is within `tol` of exactly 0.5, AND some later reported time
    `t2 > t1` has `S(t2) < S(t1)` (a strictly lower survival probability),
    the median is the MIDPOINT `(t1 + t2) / 2`, where `t2` is the SMALLEST
    such later time** — not `t1` alone. This is not a rare edge case to
    special-case away: it is the ordinary rule whenever a group's curve
    happens to land exactly on 0.5 partway through, which routinely happens
    with small or heavily tied samples (any group whose event count near the
    midpoint is a power of two is a common trigger, e.g. 4 subjects with a
    2/4 risk-set fraction at the crossing time).
  - Otherwise (S(t1) is not indistinguishable from 0.5 — the curve stepped
    past 0.5 without landing on it) the median is `t1` itself.

  **Worked example, checked against a real `survival::survfit` call, not
  merely derived from the formula:** 4 subjects, all events (no censoring),
  at times 1, 2, 3, 4. `S(1) = 0.75`, `S(2) = 0.50`, `S(3) = 0.25`,
  `S(4) = 0`. The first `t1` with `S(t1) < 0.5 + tol` is `t1 = 2`
  (`S(2) = 0.5`). `S(2)` is exactly 0.5 (within `tol`), and `S(3) = 0.25 <
  S(2)`, so the median is `(2 + 3) / 2 = 2.5` — **not `2`**. Confirmed
  directly: `Rscript -e 'library(survival);
  summary(survfit(Surv(c(1,2,3,4), c(1,1,1,1)) ~ 1))$table["median"]'`
  prints `2.5`. `stats-validation/python/tests/test_km.py`'s
  `test_median_rule_matches_rs_minmin_rule_not_the_naive_reading` pins this
  exact fixture at `2.5`, with the derivation hand-commented above the
  assertion, specifically to catch an implementation that stops at the naive
  "first `t` with `S(t) <= 0.5`" rule (which would silently return `2`).
- **The two-sided log-rank test p-value** comparing the groups: the
  Mantel-Haenszel form, with equal weight at every distinct event time
  across the pooled groups (i.e., the ordinary log-rank test — not the Peto
  or Peto-Prentice weighting, and not the Gehan-Wilcoxon weighting, both of
  which down-weight later event times differently).
- **n analysed** (`n`): the total row count remaining after the Population
  filter, across all groups.
- **Number of events** (`n_event`): the total count, across all groups, of
  rows coded as an event per Event coding above.
- **Number of rows dropped** (`n_dropped`): the count removed by the
  Population filter.
- **The full step function per group**: every DISTINCT EVENT time for that
  group (a time with `d(t) > 0`; a pure-censoring time contributes no row),
  each with its survival probability `S(t)` immediately after that time's
  drop, and the number at risk `n(t)` used as that step's denominator (the
  same `n(t)` defined in Estimator, including any subject tied-censored at
  that same time).

## Reportability

Every quantity above is reported for every group with at least one row
after the Population filter; there is no suppression/"not reliably
estimated" rule here (unlike Cox/logistic's ratio-scale cells) — the only
value that can be legitimately absent is a not-reached median, which is
reported as such, not omitted.

## Display (informational — not part of `fit_km`'s contract)

`fit_km` itself never formats text; this section exists only so the
independent comparator that checks the app's on-screen methods sentence
against `fit_km`'s numbers is built from the same documented rule, not a
second guess at it. Verified against `R/km.R`'s `fig_km`, by actually
generating this case's real output:

- A per-group median line reads `"<group> not reached"` when the median is
  not reached, or `"<group> <value> <time label>"` (value formatted
  `%.1f`, default time label `"Time"`) when it is. All groups' lines are
  joined with `"; "` inside one `"Median survival: ...."` sentence.
- The log-rank p-value is formatted `"p = %.3f"` (WITH spaces around `=`)
  when `p >= 0.001`, or the literal text `"p < 0.001"` (WITH spaces around
  `<`) otherwise. This is deliberately different punctuation from the
  ratio-table display rule used by Cox/logistic (`p=%.3f`/`p<0.001`, no
  spaces) — do not conflate the two when reading or replicating displayed
  text.
- Real example, generated from this exact case's data: `"HR 1.56 (Standard
  care vs New treatment; 95% CI 0.90–2.71); log-rank p = 0.108. Median
  survival: New treatment not reached; Standard care 26.0 Time."` (the
  hazard-ratio clause is a Cox model fitted only when there are exactly two
  groups; it is not one of this spec's Reported quantities and is not
  independently re-implemented or checked here — only the median and
  log-rank clauses are).

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

Complete cases across all three roles: time, status, AND group. A row is
dropped, and counted in `n_dropped`, when time, status, or group is blank
(an empty string after trimming whitespace) — unlike Cox regression, where a
blank status cell is coded as censored rather than dropped, Kaplan-Meier
drops a blank status cell exactly like a blank time or group cell. This was
verified two ways, not assumed from analogy with Cox:

- The app's live analyze form (`web/guided/km/spec.js`'s `buildKmSpec`)
  builds its working rows with `if (blank(t) || blank(s) || blank(g)) {
  dropped++; continue; }` before any status recoding happens — a blank
  status cell never reaches the figure-rendering code at all.
- The app's downloadable/exported R script (`R/km.R`'s `.km_script`,
  verified by actually generating and running it) begins with `df[df ==
  ""] <- NA` before building its own working frame, so a blank status cell
  becomes `NA` there too, and the exported script's own final filter
  (`dat <- dat[!is.na(dat$time) & !is.na(dat$status) & !is.na(dat$group), ]`)
  drops it. Both code paths agree.

The literal string `"NA"` is an ordinary value, not missing — do not treat
it as blank. (Confirmed against the same two code paths above: both check
for the empty string specifically, `String(v).trim() === ""` in JS and
`df == ""` in R — neither treats the two-character text `"NA"` as blank.)

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

- **Median survival per group**: the smallest reported event time `t` (see
  Reported quantities' step function, below) at which `S(t) <= 0.5`. If the
  group's curve never reaches `S(t) <= 0.5` — including a group with zero
  events, whose survival curve never drops from 1 — the median is NOT
  REACHED. Report it as such (`None`/null), NEVER as the group's largest
  observed time or any other numeric stand-in.
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

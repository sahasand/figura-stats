# Decisions — validate/km.py

Silent-spec choices made while implementing `fit_km` (`spec/km-twoarm.md`,
`INTERFACES.md`). Nothing here contradicts the spec; these are the places
the spec doesn't dictate a literal implementation and a choice had to be
made.

## Did not reuse `io.code_event`

`io.code_event` has a numeric-equality fallback (`cell == event_value` OR
both parse as numbers and are numerically equal), written for Cox/logistic.
The spec's Event coding section explicitly forbids that fallback for
Kaplan-Meier ("plain string equality only... do not reuse a numeric-fallback
event-coding helper... without removing that fallback"). `km.py` instead
does its own `str(cell) == str(event_value)` check inline.

## Did not reuse `io.complete_cases`

`io.complete_cases`'s blank check (`_is_blank`) treats a cell as blank only
when it equals `""` exactly (after any pandas NaN check) — it does not trim
whitespace first. The spec's Population section defines blank as `String(v)
.trim() === ""`, which drops a whitespace-only cell (e.g. `" "`) that
`io.complete_cases` would keep. `km.py` implements its own `_is_blank` with
an explicit `.strip()` to match the live app's rule, since this module
targets the live app, not the exported script (see Population's divergence
note).

## Log-rank test generalized to k >= 2 groups

The spec's Reported quantities section defines the log-rank test as "the
ordinary log-rank test" (Mantel-Haenszel, equal weight at every distinct
pooled event time) and separately says the estimator/log-rank machinery is
"defined for any number of groups >= 1 (log-rank requires >= 2 to be
meaningful)". This case only has two groups, so only the 2-group form is
exercised by the acceptance tests, but `fit_km` implements the general
k-group Mantel-Haenszel covariance form (the same one `survival::survdiff`
uses), which reduces algebraically to the familiar 2-group
chi-square-on-1-df statistic when k == 2. One group is dropped when forming
the reduced (k-1)x(k-1) covariance matrix to avoid a singular system; the
resulting chi-square/p-value is invariant to which group is dropped, since
observed-minus-expected sums to zero across all groups by construction.

## Median tie tolerance

`abs(S(t1) - 0.5) <= tol` (not strictly `<`) is used to decide whether
`S(t1)` counts as "within tol of exactly 0.5" for the minmin median rule.
The spec's own worked example lands exactly on 0.5 (difference of exactly
0), so both `<=` and strict `<` give the same answer on the given fixture;
`<=` was chosen since the spec's prose ("within tol") reads as an inclusive
tolerance band rather than a strict one.

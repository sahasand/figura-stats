# Analysis spec: groupcompare-numeric

Input: `stats-validation/cases/groupcompare-numeric/data.csv`. The real header is
`arm,biomarker_normal,los_skewed,responder`. The mapped roles are:
outcome = `biomarker_normal`, group = `arm`. `los_skewed` and `responder` are
NOT mapped roles and must never influence the analysis or cross into any
intermediate representation.

`arm` has **three** levels — `"High dose"`, `"Low dose"`, `"Placebo"` (50 rows
each) — so this case exercises the three-or-more-groups omnibus test and the
post-hoc branch, not the two-group t/Mann-Whitney branch. Both branches are
specified below regardless: `compare_groups` is one function and must implement
all of it.

This spec covers the **numeric-outcome branch** of group comparison. Which
branch runs is decided by the outcome column's contents, not by the case name —
see Outcome type detection below, which is normative and must be implemented
even for a case whose outcome is "obviously" numeric.

**This spec, and `compare_groups`, model the LIVE APP ONLY** (what a user's
browser session actually runs: `web/guided/groupcompare/spec.js`'s
`buildGroupCompareSpec` feeding `R/groupcompare.R`'s `fig_groupcompare`) — never
the downloadable/exported `.R` script. The two are not interchangeable for
whitespace and missing-value handling; see the divergence note at the end of
Population.

## Cell reading

Every cell is read as text and **trimmed of leading and trailing whitespace
before anything else looks at it**. This happens in the app's CSV parser, which
applies `String(cell).trim()` to every cell of every row as it builds the table,
so the analysis code downstream never sees untrimmed text. A cell that is empty
after trimming is *blank* (see Population). Line endings may be CRLF or LF; both
are stripped by the same parser and neither leaves a stray `\r` inside the last
column's values.

An implementation that reads the CSV without trimming will disagree with the app
on any padded cell: a padded group value such as `"Placebo "` would become its
own extra group level, and a whitespace-only cell would be a present value
rather than a blank one.

Note **where** that bites. Padding on a NUMERIC outcome cell is inert on both
sides — every reasonable numeric conversion, in either language, ignores
surrounding whitespace, so `" 01 "` and `"01"` agree without any trimming step.
Padding on the GROUP column is not inert, because group values are compared as
text. That is the only place an untrimmed implementation actually diverges, and
it is where the acceptance test
`test_padded_group_values_collapse_to_one_group_level` puts its fixture.

## Population

Complete cases across the two mapped roles, outcome AND group:

1. The outcome column is coerced to a number. A cell that is blank becomes
   missing. (A cell that is neither blank nor numeric cannot occur in this
   branch — such a column would have been routed to the categorical branch by
   Outcome type detection below, so by the time the numeric branch runs, every
   non-blank cell is known to parse.)
2. The group column is read as text; a blank group cell becomes missing.
3. A row with a missing outcome OR a missing group is dropped. Call that count
   `n_na`.
4. **Then, and only then**, any group left with fewer than two remaining values
   is dropped entirely, along with all of its rows. Call that count `n_small`.
   The threshold is on the group's size AFTER step 3, not before. A group with
   three rows of which two have a blank outcome is therefore dropped, even
   though its raw size was three. The dropped group disappears from
   `n_per_group` entirely — it is not reported with a count of 0 or 1. (Pinned
   by the acceptance test
   `test_groups_left_with_fewer_than_two_values_are_dropped`, which also pins
   the ordering.)

   This filter is specific to the numeric branch. The categorical branch has
   **no** small-group rule and keeps a one-row group in its table; see
   `spec/groupcompare-categorical.md`.
5. `n_dropped` = `n_na + n_small` — the total number of input rows not analysed.
   `n` = the number of rows that survive both filters.

For this case both counts are zero: `biomarker_normal` has no blank cells, `arm`
has no blank cells, and all three groups have 50 rows.

The literal text `"NA"` is **not** missing here — but it also cannot appear in a
numeric outcome column, because a column containing it fails Outcome type
detection and routes to the categorical branch instead. In the *group* column
the literal `"NA"` is an ordinary group level like any other.

The analysis requires at least two surviving groups; with fewer it is an error,
not a result.

**Divergence from the exported script (stated so this Population rule is never
mistaken for a description of the script too).** The downloadable `.R` script
that the app offers alongside the figure does its own CSV read with R's
`read.csv(...)`, and its missing-value handling was not identical to the live
app's.

> **All three are CLOSED as of 2026-07-28** (`issues/02` resolved).
> `.script_data` now emits `read.csv(..., na.strings = character(0))` plus a
> `trimws` pass ahead of `df[df == ""] <- NA`, so the script reads a cell the
> way `web/lib/csv.js` does — including the two-arm case below, which used to
> fail outright and now runs. The measured numbers are kept as the record of
> what the divergence cost; `fit_groupcompare` is unaffected either way,
> because this spec models the live app and the live app's rule never changed.

- **Whitespace is not trimmed by the script for text columns.** The script's
  parser leaves a padded group cell as the literal padded string, so `"Placebo "`
  and `"Placebo"` become two separate groups there while the live app sees one.
  Measured, on a 60-row file where six of twenty `Placebo` rows carried a
  trailing space: the live app compared three arms (Welch F p = 7.35e-06,
  eta-squared 0.394) and the script compared four (p = 0.000177, eta-squared
  0.411) with an extra post-hoc pair comparing the two spellings of the same
  arm — at an identical analysed row count of 60, so nothing about `n` reveals
  it. On a file whose app-visible design has only TWO arms the script does not
  even run: the app deparses a two-group `t.test` into it, and the script's own
  three-level data makes that call fail with `grouping factor must have exactly
  2 levels`. (A padded *numeric* outcome cell does not diverge: R's numeric
  conversion ignores surrounding whitespace, so `" 01 "` and `"01"` both become
  1 on both paths.)
- **A literal `"NA"` text cell is treated as missing by the script**, because
  R's `read.csv` maps the two-character string `NA` to a real missing value at
  parse time. The live app keeps it as an ordinary value.
- **A whitespace-only cell is kept by the script** (its blank-to-missing step
  matches the exact empty string only, so a single space survives as a
  one-character string) while the live app trims it to blank and drops the row.

## Outcome type detection

**Normative, and the single most consequential rule in this file.** The outcome
column is treated as NUMERIC if and only if **every non-blank cell parses as a
number** under R's numeric conversion; otherwise the column is CATEGORICAL and
the analysis is the one in `spec/groupcompare-categorical.md` instead.

- Blank cells are ignored by this test — they neither make a column numeric nor
  disqualify it. A column whose cells are all blank is therefore (vacuously)
  numeric.
- The test is on the RAW TEXT of the cells, after trimming. It has nothing to do
  with how many distinct values there are, whether the values look like codes,
  or whether the column is used as an identifier. `"01"`, `"02"`, `"03"` all
  parse as numbers, so **a column of zero-padded codes is NUMERIC** and gets a
  t-test/ANOVA-family comparison, not a contingency table. That behaviour is the
  app's, it is deliberate in the sense that nothing overrides it, and it is what
  must be reproduced — do not "improve" it by adding a distinct-value or
  leading-zero heuristic.
- Values that R accepts and that therefore keep a column numeric, verified
  directly: `"01"` -> 1, `" 01 "` -> 1, `"1e3"` -> 1000, `"0x1A"` -> 26,
  `"Inf"` -> infinity, `"-Inf"`.
- Values that R rejects and that therefore make the whole column categorical,
  verified directly: `"NA"`, `"NaN"`, `"1,000"`, `"TRUE"`, and any
  whitespace-only cell that reached this point untrimmed.

One non-parsing cell anywhere in the column flips the ENTIRE analysis to the
categorical branch. There is no per-cell fallback and no partial coercion.

## Roles

- **outcome** — the column tested above; in this branch, numeric.
- **group** — arbitrary text. Every distinct non-blank value surviving the
  Population filter is its own group. There is no reference level and no
  ordering concept (unlike Cox/logistic covariates). **Group levels are ordered
  by ordinary ascending string sort wherever an order is needed** — for the
  per-group display order, for which group is "first" in a two-group effect
  size, and for post-hoc pair naming. Sort the raw strings; do not sort by
  group size, first appearance, or numeric value.

  **Collation caveat, measured not assumed.** The app's sort is R's `sort()`,
  which orders by the process's LC_COLLATE locale rather than by code point.
  Under a UTF-8 locale R sorts `c("beta","Alpha","alpha","B","_z","Zed")` as
  `_z, alpha, Alpha, B, beta, Zed`, while an ordinary code-point sort gives
  `Alpha, B, Zed, _z, alpha, beta` — a genuinely different order, verified by
  running both. The two agree whenever the levels differ at their first
  character within one case class, which is true of every level in every
  shipped case (`"High dose"`, `"Low dose"`, `"Placebo"`), so nothing here is
  ambiguous in practice. Use a plain code-point sort, and treat a future case
  whose group levels differ only by letter case or by leading punctuation as
  needing this pinned before it can be compared.

  **Why these three specs pin code-point where the other three pin locale.** The
  group-comparison specs deliberately require a code-point sort: reproducibility
  beats fidelity here, because the app's real order depends on the LC_COLLATE of
  whatever process runs R, and for webR in a browser that is not the developer's
  locale and is not stated anywhere the user can see. Every shipped group level
  makes the two orders identical, so pinning the deterministic one costs nothing
  and removes an environment dependency from the comparison.
  `spec/summary-table1.md`, `spec/cox-adjusted.md` and
  `spec/logistic-confounding.md` instead state the locale-aware rule, because
  their sorts feed R's own `factor()` level order and reference-level fallback,
  where restating the rule as code-point would misdescribe the call site. No
  shipped case reaches a level set where the two rules disagree; all six specs say
  so explicitly rather than leaving it to inference.

## Parametric vs non-parametric routing

The choice is made **once, globally**, before any test is selected, and the same
decision then drives the omnibus test, the effect size, the per-group display
summary, and the post-hoc method. It is never re-made per group or per pair.

If the case declares a test override (`options.test`) of `"parametric"` or
`"nonparametric"`, that wins outright. `"auto"` (this case's setting, and the
app's default) runs the rule below.

**Step 1 — centre within groups.** Subtract each row's own group MEAN from its
outcome value, and pool all the resulting residuals into one vector. The
normality assessment is run on those pooled group-mean-centred residuals, NEVER
on the raw pooled outcome. This matters enormously: pooling raw values from
groups with different means produces a multi-modal mixture that fails any
normality test, so an implementation that skips the centring will route almost
every genuinely-normal, genuinely-separated dataset to the non-parametric
branch.

**Step 2 — decide.** Let `x` be the centred residuals with missing values
removed, `n = length(x)`, and let `sk` be the **population** skewness of `x`:

```
m  = mean(x)
s  = sqrt(mean((x - m)^2))      # population SD: divide by n, NOT n - 1
sk = mean((x - m)^3) / s^3
```

with `sk` defined as 0 when `s == 0`, and undefined (never used) when `n < 3`.

Then, in this exact order:

1. If `n < 3` **or** the number of DISTINCT values in `x` is less than 3 ->
   **non-parametric**. (Distinctness is counted on the centred residuals, not on
   the raw outcome.)
2. Else if `n > 300` -> **parametric** when `abs(sk) < 1`, otherwise
   non-parametric. Shapiro-Wilk is deliberately not consulted above n = 300: it
   rejects trivial departures at large n.
3. Else (`3 <= n <= 300`) -> **parametric** when the Shapiro-Wilk test on `x`
   gives `p >= 0.05` **AND** `abs(sk) < 1`; otherwise non-parametric. Both
   conditions must hold.

Note that the n > 300 threshold is strict (`n > 300`, so n = 300 still runs
Shapiro-Wilk) and the two comparisons are `p >= 0.05` and `abs(sk) < 1` — a
Shapiro p of exactly 0.05 is parametric, a skewness of exactly 1 is not.

For this case: n = 150 centred residuals, skewness 0.0087, Shapiro-Wilk
p = 0.876 -> **parametric**.

## Test selection

Let `k` be the number of surviving groups.

- **k == 2, parametric** — **Welch's two-sample t-test, unequal variances
  assumed.** This is R's `t.test` default and is NOT the pooled-variance
  (Student) t-test. The two give different p-values on the same data whenever
  the group variances or sizes differ; the pooled test is wrong here. Reported
  test name: `Welch t-test`.
- **k == 2, non-parametric** — the **Mann-Whitney U (Wilcoxon rank-sum) test**,
  two-sided, as R's `wilcox.test` computes it with its own defaults: an exact
  p-value when both group sizes are under 50 and there are no ties in the pooled
  data, otherwise the normal approximation **with a continuity correction**
  applied. The reported statistic is R's `W`, the count of pairs (i, j) with
  `x_i > y_j` where `x` is the FIRST group in string-sort order (equivalently
  `U` for that group), with tied pairs contributing one half each. Reported test
  name: `Mann–Whitney U test` — the separator between "Mann" and
  "Whitney" is an EN DASH (U+2013), not a hyphen; the string is compared
  literally.
- **k >= 3, parametric** — **Welch's heteroscedastic one-way F test (Welch
  1951)**, i.e. R's `oneway.test` with its default `var.equal = FALSE`. This is
  NOT the classical fixed-effects one-way ANOVA: it does not pool the within-
  group variances, its numerator and denominator degrees of freedom are the
  Welch-Satterthwaite ones (the denominator df is fractional), and its p-value
  differs from classical ANOVA's whenever group variances or sizes differ. For a
  concrete measure of how far apart the two defaults are, see the acceptance
  test `test_three_group_welch_anova_matches_r_oneway_test`, where the same 24
  observations give Welch p = 2.68e-06 and classical-ANOVA p = 0.0437 — four
  orders of magnitude. Reported test name: `one-way ANOVA (Welch)`.

  The Welch statistic, spelled out so it can be implemented without guessing at
  R's internals: with group means `m_i`, sample variances `v_i` (divisor
  `n_i - 1`), sizes `n_i`, and `k` groups, let `w_i = n_i / v_i`,
  `W = sum(w_i)`, `mbar = sum(w_i * m_i) / W`, and

  ```
  A    = sum(w_i * (m_i - mbar)^2) / (k - 1)
  B    = sum((1 - w_i / W)^2 / (n_i - 1)) * 2 * (k - 2) / (k^2 - 1)
  F    = A / (1 + B)
  df1  = k - 1
  df2  = (k^2 - 1) / (3 * sum((1 - w_i / W)^2 / (n_i - 1)))
  p    = upper tail of the F distribution with (df1, df2) at F
  ```

- **k >= 3, non-parametric** — the **Kruskal-Wallis test**, two-sided, as R's
  `kruskal.test` computes it: mid-ranks for ties over the pooled sample, the
  H statistic corrected for ties by dividing by `1 - sum(t^3 - t) / (N^3 - N)`
  (summed over tie groups of size `t`), and the p-value from the upper tail of
  the chi-square distribution with `k - 1` degrees of freedom. Reported test
  name: `Kruskal–Wallis test` — the separator between "Kruskal" and
  "Wallis" is an EN DASH (U+2013), not a hyphen; the string is compared
  literally.

The **reported `statistic`** is whatever the chosen test's own statistic is:
`t` for the Welch t-test, `W` for Mann-Whitney, `F` for the Welch one-way test,
and the tie-corrected `H` (a chi-square statistic) for Kruskal-Wallis. It is
never `None` in this branch.

## Effect sizes

Exactly one effect size is reported, chosen by the same `k` / parametric split.
Each is reported as a value plus, where one exists, a 95% confidence interval.
**These are the app's formulas, transcribed from its code; several differ from
the textbook version of the same-named quantity, and where they do, the app's
version is what must be implemented.**

- **k == 2, parametric — Cohen's d with a pooled standard deviation.** Not
  Hedges' g: there is NO small-sample bias correction factor anywhere in this
  computation. With `x1` the values of the FIRST group in string-sort order and
  `x2` the second, `v1`/`v2` their sample variances (divisor `n - 1`):

  ```
  sp = sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
  d  = (mean(x2) - mean(x1)) / sp
  se = sqrt((n1 + n2) / (n1 * n2) + d^2 / (2 * (n1 + n2)))
  CI = d - 1.96 * se  to  d + 1.96 * se
  ```

  Note two things that differ from common references: the denominator of the
  second term of `se` is `2 * (n1 + n2)`, **not** `2 * (n1 + n2 - 2)`; and the
  interval uses the literal constant 1.96, not the exact normal quantile
  1.959963985 and not a t quantile. Note also that the sign is
  (second sorted group minus first), so a positive d means the SECOND group is
  larger. Effect label: `Cohen's d`.

  (This is an internally inconsistent pairing — a Welch test, which assumes
  unequal variances, reported alongside an effect size built on a pooled
  standard deviation, which assumes equal ones. It is nonetheless exactly what
  the app computes, and reproducing the app is this harness's whole purpose.)

- **k == 2, non-parametric — rank-biserial correlation**, from the same `U`
  (R's `W`) the test reported:

  ```
  r  = 1 - 2 * U / (n1 * n2)
  z  = atanh(clamp(r, -0.999999, +0.999999))     # Fisher z, with that clamp
  se = 1 / sqrt(n1 + n2 - 3)
  CI = tanh(z - 1.96 * se)  to  tanh(z + 1.96 * se)
  ```

  The clamp is applied before the `atanh` and only to the value fed into the
  interval; the reported `r` itself is NOT clamped and may be exactly +/-1 under
  complete separation. `n1`/`n2` are the sizes of the first and second groups in
  string-sort order, matching the group `U` was computed for, so a positive `r`
  again means the SECOND sorted group is larger. Effect label:
  `rank-biserial r`.

- **k >= 3, parametric — eta-squared, with a non-central-F (Steiger) interval.**
  Both the point estimate and the interval come from the **classical
  fixed-effects one-way ANOVA decomposition**, not from the Welch test that
  produced the p-value. Fit the ordinary one-way ANOVA of outcome on group and
  take its between-groups sum of squares `SS_b`, residual sum of squares
  `SS_r`, F statistic `Fv`, and degrees of freedom `df1 = k - 1`,
  `df2 = n - k`:

  ```
  eta_sq = SS_b / (SS_b + SS_r)
  ```

  For the interval, define `lam_to_eta(lam) = lam / (lam + df1 + df2 + 1)` and,
  for a target tail probability `q`, let `find(q)` be the non-centrality `lam`
  solving `F_cdf(Fv; df1, df2, ncp = lam) = q`, found as follows (the bracketing
  is part of the specification, because it determines the fallbacks):

  - if `F_cdf(Fv; df1, df2, ncp = 0) - q < 0`, return `lam = 0`;
  - otherwise start with `hi = 1` and double it while
    `F_cdf(Fv; df1, df2, ncp = hi) - q > 0` and `hi < 1e6`; if that loop exits
    with the value still positive, `find(q)` is undefined;
  - otherwise solve for the root in `[0, hi]`.

  Then with `a = 0.025`: the LOWER limit uses `find(1 - a)` and the UPPER limit
  uses `find(a)`. An undefined lower `find` yields a lower limit of 0; an
  undefined upper `find` yields an upper limit of 1. Finally clamp:
  lower = `max(0, lam_to_eta(find(1 - a)))`, upper = `min(1, lam_to_eta(find(a)))`.
  Effect label: `eta-squared`.

  **Precision caveat, measured not assumed:** the point estimate `eta_sq` is a
  closed-form ratio and reproduces to floating-point noise (~1e-15 relative).
  The two INTERVAL limits do not: R's root-finder stops at its own default
  tolerance (`.Machine$double.eps^0.25`, about 1.2e-4 on the non-centrality
  scale) rather than converging fully, so an independently-written, tightly
  converged solver lands a small distance away from R's answer — measured at
  2.5e-8 relative on this case's limits. Do not chase that gap; it is R's
  looseness, not an error. The interval is deliberately not one of this case's
  exact targets for the same reason.

- **k >= 3, non-parametric — epsilon-squared**, from the tie-corrected
  Kruskal-Wallis statistic `H` and the analysed row count `n`:

  ```
  eps_sq = H / (n - 1)
  ```

  **There is no confidence interval for this one** — the app reports the point
  estimate alone, and so must `compare_groups` (`lo` and `hi` are absent/None).
  Effect label: `epsilon-squared`.

## Post-hoc

Post-hoc pairwise testing runs **only when both** of these hold:

- there are three or more groups, AND
- the omnibus p-value computed above is **strictly less than 0.05**.

Otherwise there is no post-hoc result at all (not an empty one — the app emits
no post-hoc sentence whatsoever). `compare_groups` reports `posthoc = None` in
that case.

- **Parametric — Tukey's Honestly Significant Difference**, computed on the
  ordinary one-way ANOVA fit (again the classical, pooled-variance model, not
  the Welch test that decided significance — an inconsistency the app carries
  and this spec preserves). A pair is *significant* when its Tukey-adjusted
  p-value is `< 0.05`. Post-hoc test label: `Tukey HSD`.

  **Pair naming: `"<later>-<earlier>"`** in string-sort order of the group
  levels — the SECOND level of the pair first, joined by a single hyphen with no
  spaces around it. For this case's levels, the three pairs are named
  `"Low dose-High dose"`, `"Placebo-High dose"`, `"Placebo-Low dose"`.

- **Non-parametric — Dunn's test**, hand-computed from the SHARED overall
  ranking (rank the pooled outcome once, across all groups, mid-ranks for ties;
  do NOT re-rank within a pair). With `N` the analysed row count, `r` the pooled
  ranks, `Rbar_i` the mean rank of group `i`, `n_i` its size, and
  `tie_term = sum(t^3 - t)` over groups of tied outcome VALUES of size `t`:

  ```
  sigma_ij = sqrt( (N * (N + 1) / 12  -  tie_term / (12 * (N - 1)))
                   * (1 / n_i + 1 / n_j) )
  z_ij     = (Rbar_i - Rbar_j) / sigma_ij
  p_ij     = 2 * Phi(-abs(z_ij))          # two-sided standard normal
  ```

  All `k * (k - 1) / 2` raw p-values are then adjusted **together** by the
  Benjamini-Hochberg procedure (`p.adjust(method = "BH")`, i.e. BH
  false-discovery-rate, NOT Bonferroni and NOT Holm), and a pair is
  *significant* when its BH-adjusted p-value is `< 0.05`. Post-hoc test label:
  `Dunn's test (BH-adjusted)`.

  **Pair naming: `"<earlier>-<later>"`** — the OPPOSITE order from Tukey's.
  Pairs are enumerated as all 2-combinations of the string-sorted levels, in
  combination order, and named first-of-the-pair then second. For this case's
  levels the three pairs are named `"High dose-Low dose"`,
  `"High dose-Placebo"`, `"Low dose-Placebo"`.

  This ordering difference between the two post-hoc methods is not a typo in
  this spec: Tukey's names come from R's own `TukeyHSD` row labels, Dunn's are
  built by the app's own pairing loop, and the two conventions genuinely
  disagree. An implementation that normalises both to one order will produce
  pair names the app never displays.

`posthoc`, when present, reports the test label and the LIST OF SIGNIFICANT
PAIRS (possibly empty, when the omnibus was significant but no pair survived
adjustment). Pairs are reported in the enumeration order above, not sorted by
p-value.

For this case: the omnibus Welch F test gives p = 3.73e-12, so Tukey runs, and
all three pairs are significant (adjusted p = 0.0145, 3.48e-13, 8.77e-07
respectively).

## Reported quantities

`compare_groups(df, outcome, group, nonparametric=None) -> dict`:

- `test_name` — the exact test-name string listed under Test selection.
- `p_value` — the omnibus test's two-sided p-value, full precision.
- `statistic` — the omnibus test's own statistic, full precision.
- `effect` — `{label, value, lo, hi}`; `lo`/`hi` are `None` for epsilon-squared
  and present for every other numeric-branch effect size.
- `n_per_group` — `{group level: int}` for the surviving groups only, keyed by
  the literal group strings.
- `n` — total analysed rows.
- `n_dropped` — total input rows not analysed (`n_na + n_small`).
- `posthoc` — `None`, or `{test, significant_pairs}` per Post-hoc above.

`nonparametric` is the override: `None` means run the routing rule, `True`/
`False` force the branch (equivalent to `options.test` being `"nonparametric"` /
`"parametric"`).

Report all floats at full precision — never round inside the function.

## Display (informational — not part of `compare_groups`'s contract)

`compare_groups` never formats text. This section documents the app's real
`text` output so that the independent comparator checking the on-screen sentence
against these numbers is built from a stated rule rather than a second guess.
Verified by generating this exact case's output.

The numeric-branch sentence is:

```
<outcome> across groups: <per-group summaries joined by "; ">. <test name><reason>: <p>, <effect>.<post-hoc><notes>
```

- `<reason>` is ` (<the routing reason>)` — for automatic routing, one of
  `approximately normal (Shapiro–Wilk p = 0.876)`,
  `departs from normal (Shapiro–Wilk p < 0.001)`,
  `right-skewed (skewness 1.5); Shapiro–Wilk p < 0.001`,
  `approximately symmetric (skewness 0.1, n = 400)`,
  `right-skewed (skewness 1.5), n = 400`, or
  `too few distinct values to assess normality; using median (IQR)`; for a
  user override it is the literal ` (user-selected)`. (Those **six** are the
  complete set the routing rule can produce — one per branch of the decision
  above, with the skewness/Shapiro variants split by which signal is more
  legible. Count them: the two Shapiro forms, the two skewness forms, the
  large-n symmetric form, and the too-few-distinct-values form.)
- `<p>` is `p < 0.001` when p < 0.001, else `p = %.3f` — **with spaces** around
  `=` and `<`.
- Numbers inside the per-group summaries and the effect phrase are rendered by
  one shared rule: **3 significant figures, plain (never scientific) notation,
  trailing zeros dropped** (250000 -> `250000`, 0.00123 -> `0.00123`,
  7.70 -> `7.7`). This is R's `.fmt_num` — literally the same function this
  case's branch calls, defined once in `R/summarize.R` and reused by
  `R/groupcompare.R` — so the tie rule below is identical to the one
  `spec/summary-table1.md` states, and neither spec is stating a variant.

  **The tie rule is R's `signif`, which is NOT "round the decimal value
  half-to-even".** `signif(x, 3)` (`src/nmath/fprec.c`) computes
  `e = 3 - 1 - floor(log10(|x|))` and then `nearbyint(x * 10^e) / 10^e` — it
  **scales, rounds the SCALED value half-to-even, and scales back**. The
  scaling multiply is itself a floating-point operation and can land *exactly*
  on a `.5` tie even when the original double is nowhere near one, which is
  where a decimal-exact rule diverges. Implement the algorithm, not an
  approximation of it: scale, apply Python's one-argument `round()` to the
  scaled float (that is exactly round-half-to-even), scale back. Never a
  two-argument `round(v, k)`, never `Decimal(ROUND_HALF_UP)`, never
  `printf("%.2f")`.

  R-verified probes, chosen because they **discriminate between the two rules**:

  | v | rendered | a decimal-exact rule would say |
  |---|---|---|
  | `2.225` | `2.22` | `2.23` (the double is `2.22500000000000008…`, above the tie, but `2.225 * 100` is exactly `222.5` and half-to-even gives `222`) |
  | `1.315` | `1.32` | `1.31` (the double is `1.31499999999999994…`, below the tie, but `1.315 * 100` is exactly `131.5` and half-to-even gives `132`) |

  Probes that do **not** discriminate, kept only as sanity checks: `1.125` ->
  `1.12` and `1.135` -> `1.14` render the same under both rules, so an
  implementation can pass both while still being wrong. Do not use them alone.
- Per-group summary: `<group> <mean> ± <sd>` (sample SD, divisor n-1) under the
  parametric branch; `<group> <median> (<Q1>–<Q3>)` (quantile type 7, EN DASH
  between the quartiles) under the non-parametric branch. Groups appear in
  string-sort order.
- Effect phrase: `<label> = <value> (95% CI <lo> to <hi>)`, or `<label> =
  <value>` when there is no interval. The two-group effects — and **only**
  those two, `Cohen's d` and `rank-biserial r` — additionally carry a trailing
  ` (<second sorted group> vs <first sorted group>)` direction clause. It is a
  property of those effect sizes, not of the group count: `eta-squared`,
  `epsilon-squared` and (in the categorical branch) `Cramér's V` never carry
  one, at any group count.
- Post-hoc sentence, when present: ` <label>, significant pairs: <pairs joined
  by ", ">.` or ` <label>: no pairwise differences at 0.05.`
- Notes, appended in this order when non-zero: ` <n_small> row(s) in groups with
  <2 values were dropped.` then ` <n_na> row(s) with missing values were
  excluded.`

Real example, generated from this exact case's data:

> `biomarker_normal across groups: High dose 58.4 ± 7.71; Low dose 54.1 ± 7.82;
> Placebo 45.7 ± 7.7. one-way ANOVA (Welch) (approximately normal (Shapiro–Wilk
> p = 0.876)): p < 0.001, eta-squared = 0.321 (95% CI 0.197 to 0.421). Tukey
> HSD, significant pairs: Low dose-High dose, Placebo-High dose, Placebo-Low
> dose.`

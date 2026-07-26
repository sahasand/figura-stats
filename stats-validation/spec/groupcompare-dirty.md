# Analysis spec: groupcompare-dirty

Input: `stats-validation/cases/groupcompare-dirty/data.csv`. The real header is
`arm,biomarker_normal,los_skewed,responder,site_code`. The mapped roles are:
outcome = `site_code`, group = `arm`. `biomarker_normal`, `los_skewed`, and
`responder` are NOT mapped roles and must never influence the analysis or cross
into any intermediate representation.

The file is derived from the app's shipped group-comparison demo fixture with
a fifth column added and deliberate dirt injected, to pin the app's real
behaviour on input that is messy in the ways real uploads are messy:

- **`site_code` is a numeric-LOOKING categorical column** — zero-padded site
  codes `"01"`, `"02"`, `"03"`. Read it below before assuming what happens.
- **CRLF (`\r\n`) line endings** on every line, not LF.
- **Leading and/or trailing spaces** on twelve of the `site_code` cells
  (` 01`, `01 `, ` 02 `, and so on).
- **Four blank `site_code` cells**, one per missing-value drop.
- The pre-existing six blank `los_skewed` cells of the original fixture are
  still present, and are irrelevant here: `los_skewed` is not a mapped role, so
  its blanks must not affect `n` or `n_dropped` in any way. A row is dropped for
  a blank in a MAPPED column only.

`arm` has three levels — `"High dose"`, `"Low dose"`, `"Placebo"` — with 50 rows
each before filtering.

**This spec, and `compare_groups`, model the LIVE APP ONLY** (`web/guided/
groupcompare/spec.js`'s `buildGroupCompareSpec` feeding `R/groupcompare.R`'s
`fig_groupcompare`) — never the downloadable/exported `.R` script; see the
divergence note at the end of Population, which is where the dirt bites hardest.

## Cell reading

Every cell is read as text and **trimmed of leading and trailing whitespace
before anything else looks at it**: the app's CSV parser splits lines on
`\r?\n` (so a CRLF file and an LF file give identical results, with no stray
`\r` left on the last column's values) and applies `String(cell).trim()` to
every cell as it builds the table. A cell that is empty after trimming is
*blank*.

Consequences for this file, all normative:

- ` 01` , `01 `, and ` 02 ` are read as `"01"`, `"01"`, `"02"`. They are NOT
  distinct values and must not create extra levels or extra distinct outcome
  values.
- The four empty `site_code` fields are blank.
- The CRLF endings are invisible to everything downstream.

An implementation that reads this file without trimming will differ from the app
on every one of those twelve padded cells. An implementation that does not
handle CRLF will carry a trailing `\r` on every `site_code` value (the last
column), which would make every cell non-numeric and flip the whole analysis to
the categorical branch — a completely different result, not a rounding
difference.

## Outcome type detection — the point of this case

**Normative.** The outcome column is treated as NUMERIC if and only if **every
non-blank cell parses as a number** under R's numeric conversion; otherwise the
column is CATEGORICAL and gets a contingency-table analysis instead.

- Blank cells are ignored by this test — they neither make a column numeric nor
  disqualify it.
- The test is on the RAW TEXT of the cells, after trimming. It has nothing to do
  with how many distinct values the column has, whether they are zero-padded,
  whether they look like identifiers, or whether treating them as numbers is
  scientifically meaningful.

**Therefore `site_code` is NUMERIC.** `"01"`, `"02"`, and `"03"` all parse as
the numbers 1, 2, and 3, so the app routes this case to the numeric branch and
compares site codes across arms as if they were measurements — a
`Kruskal–Wallis test` on the values 1/2/3, with an epsilon-squared effect size
and Dunn post-hoc pairs. That is what the app does, it is what this case
records, and it is what `compare_groups` must reproduce.

This is stated deliberately and at length because the intuitive answer is the
opposite one. A site code is categorical in every sense that matters
scientifically, and a reasonable implementer, told "numeric-looking categorical
column", might add a distinct-value threshold, a leading-zero check, or a
cardinality heuristic to "fix" it. **Do not.** There is no such heuristic in the
app, and adding one would make `compare_groups` disagree with the software it
exists to check. If this behaviour is a product problem, it is a product problem
to be reported from the evidence — not one to be papered over inside the
comparison harness.

Values R accepts (column stays numeric), verified directly: `"01"`, `" 01 "`,
`"1e3"`, `"0x1A"`, `"Inf"`, `"-Inf"`. Values R rejects (one of them anywhere in
the column flips the ENTIRE analysis to the categorical branch), verified
directly: `"NA"`, `"NaN"`, `"1,000"`, `"TRUE"`, and any whitespace-only cell
that arrived untrimmed. Note the asymmetry that follows: had a single
`site_code` cell read `"NA"` instead of being empty, this whole case would be a
2 x 3 chi-square instead of a Kruskal-Wallis.

## Population

Complete cases across the two mapped roles, outcome AND group:

1. The outcome column is coerced to a number; a blank cell becomes missing.
2. The group column is read as text; a blank group cell becomes missing.
3. A row with a missing outcome OR a missing group is dropped. Call that count
   `n_na`. **A blank in an unmapped column never drops a row.**
4. **Then, and only then**, any group left with fewer than two remaining values
   is dropped entirely, along with all of its rows. Call that count `n_small`.
5. `n_dropped = n_na + n_small`; `n` is the surviving row count.

For this case: four blank `site_code` cells -> `n_na = 4`; no group falls below
two values -> `n_small = 0`; so `n_dropped = 4` and `n = 146`, with
`n_per_group = {"High dose": 48, "Low dose": 49, "Placebo": 49}`.

The analysis requires at least two surviving groups.

**Divergence from the exported script (this case is where it matters most).**
The downloadable `.R` script reads the CSV with R's `read.csv(...)`, which does
NOT trim whitespace from text columns. For THIS file the two paths still agree,
because the padding was injected only into the numeric `site_code` column and
R's numeric conversion ignores surrounding whitespace (`" 01 "` -> 1 on both
paths). Had the same padding been injected into the `arm` column instead, the
script would have produced extra group levels (`"Placebo "` distinct from
`"Placebo"`) that the live app never sees, and the two paths would have analysed
different studies — measured on a purpose-built 60-row file: three arms and
Welch F p = 7.35e-06 in the app against four arms and p = 0.000177 in the
script, at an identical analysed row count, with a post-hoc pair comparing the
two spellings of the same arm. That is why this case's padding is deliberately
confined to the numeric outcome column: putting it on `arm` would have planted
a permanent, unrelated app-vs-script mismatch in a case whose purpose is type
detection. Two further script-only divergences apply generally: a
literal `"NA"` text cell is treated as missing by the script but as an ordinary
value by the live app, and a whitespace-only cell survives the script's
blank-to-missing step (which matches the exact empty string only) while the live
app trims it to blank and drops the row.

## Roles

- **outcome** — `site_code`; numeric by the rule above.
- **group** — `arm`; arbitrary text. Every distinct non-blank value surviving
  the Population filter is its own group; there is no reference level and no
  ordering concept. **Group levels are ordered by ordinary ascending string
  sort** wherever an order is needed (display order, post-hoc pair naming).

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

## Parametric vs non-parametric routing

Decided **once, globally**, before any test is selected; the same decision drives
the omnibus test, the effect size, the per-group display summary, and the
post-hoc method.

A case may force the branch (`options.test` = `"parametric"` /
`"nonparametric"`); this case uses `"auto"`, which runs the rule below.

**Step 1 — centre within groups.** Subtract each row's own group MEAN from its
outcome value and pool the residuals. The normality assessment runs on those
pooled group-mean-centred residuals, never on the raw pooled outcome.

**Step 2 — decide.** With `x` the centred residuals (missing removed),
`n = length(x)`, and `sk` the **population** skewness of `x`
(`m = mean(x)`; `s = sqrt(mean((x - m)^2))`, dividing by `n`, NOT `n - 1`;
`sk = mean((x - m)^3) / s^3`; `sk = 0` when `s == 0`):

1. If `n < 3` **or** the number of DISTINCT values in `x` is under 3 ->
   **non-parametric**.
2. Else if `n > 300` -> **parametric** when `abs(sk) < 1`, else non-parametric
   (Shapiro-Wilk is deliberately not consulted above n = 300).
3. Else -> **parametric** when Shapiro-Wilk on `x` gives `p >= 0.05` **AND**
   `abs(sk) < 1`; otherwise non-parametric.

For this case `n = 146`, so rule 3 applies. The centred residuals of a
three-valued code column are nowhere near normal: Shapiro-Wilk gives
p < 0.001, so the routing is **non-parametric**.

Note that rule 1's distinctness test is on the CENTRED residuals, not on the raw
outcome. This case's raw outcome has exactly 3 distinct values, which would
narrowly pass a raw-value reading of the test; the centred residuals have many
more (three per group, offset by three different group means). Either reading
reaches rule 3 here, but they are not the same test and the centred one is the
app's.

## Test selection

Three groups and non-parametric routing select the **Kruskal-Wallis test**,
two-sided, as R's `kruskal.test` computes it: mid-ranks for ties over the pooled
sample; the H statistic corrected for ties by dividing by
`1 - sum(t^3 - t) / (N^3 - N)` summed over groups of tied VALUES of size `t`;
p-value from the upper tail of the chi-square distribution with `k - 1` degrees
of freedom. Reported test name: `Kruskal–Wallis test` — the separator between
"Kruskal" and "Wallis" is an EN DASH (U+2013), not a hyphen; the string is
compared literally.

The tie correction is not optional here — with only three distinct outcome
values and 146 rows, essentially every observation is tied with dozens of
others, and omitting the correction changes H materially.

The **reported `statistic`** is that tie-corrected `H`.

The other three numeric-branch selections, for completeness, since
`compare_groups` is one function: two groups parametric -> **Welch's** two-sample
t-test (unequal variances, R's `t.test` default — NOT the pooled/Student test);
two groups non-parametric -> Mann-Whitney U (R's `wilcox.test`, exact when both
group sizes are under 50 with no ties, else the normal approximation WITH
continuity correction); three or more parametric -> **Welch's heteroscedastic
one-way F test** (R's `oneway.test` default `var.equal = FALSE`, NOT classical
one-way ANOVA). See `spec/groupcompare-numeric.md` for their effect sizes; this
case never reaches them.

## Effect size

Non-parametric with three or more groups selects **epsilon-squared**, from the
tie-corrected Kruskal-Wallis statistic `H` and the analysed row count `n`:

```
eps_sq = H / (n - 1)
```

**There is no confidence interval** — the app reports the point estimate alone,
and so must `compare_groups` (`lo` and `hi` absent/None). Effect label:
`epsilon-squared`.

For this case: `H = 58.617246335913329`, `n = 146`, so
`eps_sq = 0.40425687128216087`.

## Post-hoc

Post-hoc pairwise testing runs **only when both** of these hold: three or more
groups, AND the omnibus p-value is **strictly less than 0.05**. Otherwise there
is no post-hoc result at all and `compare_groups` reports `posthoc = None`.

Non-parametric routing selects **Dunn's test**, hand-computed from the SHARED
overall ranking — rank the pooled outcome once, across all groups, mid-ranks for
ties; do NOT re-rank within a pair. With `N` the analysed row count, `r` the
pooled ranks, `Rbar_i` the mean pooled rank of group `i`, `n_i` its size, and
`tie_term = sum(t^3 - t)` over groups of tied outcome VALUES of size `t`:

```
sigma_ij = sqrt( (N * (N + 1) / 12  -  tie_term / (12 * (N - 1)))
                 * (1 / n_i + 1 / n_j) )
z_ij     = (Rbar_i - Rbar_j) / sigma_ij
p_ij     = 2 * Phi(-abs(z_ij))          # two-sided standard normal
```

All `k * (k - 1) / 2` raw p-values are adjusted **together** by the
Benjamini-Hochberg procedure (BH false-discovery-rate — NOT Bonferroni, NOT
Holm, NOT Dunn's own Bonferroni convention), and a pair is *significant* when
its BH-adjusted p-value is `< 0.05`. Post-hoc test label:
`Dunn's test (BH-adjusted)`.

**Pair naming: `"<earlier>-<later>"`** in string-sort order of the group levels
— pairs are enumerated as all 2-combinations of the sorted levels, in
combination order, and each is named first-of-the-pair then second, joined by a
single hyphen with no spaces. For this case: `"High dose-Low dose"`,
`"High dose-Placebo"`, `"Low dose-Placebo"`.

**This is the OPPOSITE order from the parametric branch's Tukey pair names**,
which come from R's own `TukeyHSD` row labels and read `"<later>-<earlier>"`
(e.g. `"Low dose-High dose"`). The two conventions genuinely disagree; do not
normalise them to one order, or `compare_groups` will produce pair names the app
never displays.

`posthoc`, when present, reports the test label and the LIST OF SIGNIFICANT
PAIRS (possibly empty, when the omnibus was significant but no pair survived
adjustment), in enumeration order rather than sorted by p-value.

For this case the omnibus p is 1.87e-13, so Dunn runs. The three BH-adjusted
p-values are 2.11e-10 (`High dose-Low dose`), 2.26e-11 (`High dose-Placebo`),
and 0.664 (`Low dose-Placebo`), so the significant set is exactly
`["High dose-Low dose", "High dose-Placebo"]` — two of three, with the third a
real non-significant comparison rather than a degenerate tie.

## Reported quantities

`compare_groups(df, outcome, group, nonparametric=None) -> dict`:

- `test_name` — `Kruskal–Wallis test` for this case (EN DASH, U+2013,
  between "Kruskal" and "Wallis" — the string is compared literally).
- `p_value` — the omnibus two-sided p-value, full precision.
- `statistic` — the tie-corrected `H`, full precision.
- `effect` — `{label: "epsilon-squared", value, lo: None, hi: None}`.
- `n_per_group` — `{group level: int}` for surviving groups, keyed by the
  literal group strings.
- `n` — total analysed rows (146 here).
- `n_dropped` — total input rows not analysed (4 here).
- `posthoc` — `{test, significant_pairs}` per Post-hoc above.

`nonparametric` is the override: `None` runs the routing rule, `True`/`False`
force the branch.

Report all floats at full precision — never round inside the function.

## Display (informational — not part of `compare_groups`'s contract)

The app's numeric-branch sentence, verified by generating this exact case's
output:

```
<outcome> across groups: <per-group summaries joined by "; ">. <test name><reason>: <p>, <effect>.<post-hoc><notes>
```

- `<reason>` is ` (<routing reason>)`; for this case,
  ` (departs from normal (Shapiro–Wilk p < 0.001))`.
- `<p>` is `p < 0.001` when p < 0.001, else `p = %.3f` — **with spaces** around
  `=` and `<`.
- Numbers are rendered at **3 significant figures, plain (never scientific)
  notation, trailing zeros dropped**.
- Per-group summary under the non-parametric branch is
  `<group> <median> (<Q1>–<Q3>)` (quantile type 7 — linear interpolation
  between order statistics — and an EN DASH between the quartiles). Groups
  appear in string-sort order.
- Effect phrase: `<label> = <value>` (no interval for epsilon-squared).
- Post-hoc sentence: ` <label>, significant pairs: <pairs joined by ", ">.` or
  ` <label>: no pairwise differences at 0.05.`
- Notes, appended in this order when non-zero: ` <n_small> row(s) in groups with
  <2 values were dropped.` then ` <n_na> row(s) with missing values were
  excluded.`

Real example, generated from this exact case's data:

> `site_code across groups: High dose 3 (2–3); Low dose 2 (1–2); Placebo 2
> (1–2). Kruskal–Wallis test (departs from normal (Shapiro–Wilk p < 0.001)):
> p < 0.001, epsilon-squared = 0.404. Dunn's test (BH-adjusted), significant
> pairs: High dose-Low dose, High dose-Placebo. 4 row(s) with missing values
> were excluded.`

Note that the site codes are displayed as `3`, `2`, `2` — the medians of the
NUMBERS 1/2/3, with the zero padding gone. The app never displays `"03"` again
once it has decided the column is numeric.

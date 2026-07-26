# Analysis spec: groupcompare-categorical

Input: `stats-validation/cases/groupcompare-categorical/data.csv` (the same
fixture as `groupcompare-numeric`, mapped differently). The real header is
`arm,biomarker_normal,los_skewed,responder`. The mapped roles are:
outcome = `responder`, group = `arm`. `biomarker_normal` and `los_skewed` are
NOT mapped roles and must never influence the analysis or cross into any
intermediate representation.

`arm` has **three** levels — `"High dose"`, `"Low dose"`, `"Placebo"` (50 rows
each) — and `responder` has two, `"No"` (73) and `"Yes"` (77), so the
contingency table for this case is **2 x 3**, not 2 x 2. The 2 x 2-only clauses
below (odds ratio, and R's continuity-correction default) therefore do not fire
for this case, but they are specified because `compare_groups` is one function
and a 2 x 2 case must behave correctly too.

This spec covers the **categorical-outcome branch** of group comparison. Which
branch runs is decided by the outcome column's contents, not by the case name —
see Outcome type detection below, which is normative.

**This spec, and `compare_groups`, model the LIVE APP ONLY** (`web/guided/
groupcompare/spec.js`'s `buildGroupCompareSpec` feeding `R/groupcompare.R`'s
`fig_groupcompare`) — never the downloadable/exported `.R` script; see the
divergence note at the end of Population.

## Cell reading

Every cell is read as text and **trimmed of leading and trailing whitespace
before anything else looks at it** (the app's CSV parser applies
`String(cell).trim()` to every cell as it builds the table). A cell that is
empty after trimming is *blank*. Line endings may be CRLF or LF.

This matters more in the categorical branch than in the numeric one, because
here the outcome values are compared as STRINGS: without trimming, `"Yes"` and
`"Yes "` would be two different outcome levels and the contingency table would
gain a spurious row.

## Outcome type detection

**Normative.** The outcome column is treated as NUMERIC — and therefore handled
by `spec/groupcompare-numeric.md` instead of this file — if and only if **every
non-blank cell parses as a number** under R's numeric conversion. Otherwise it
is CATEGORICAL and this spec applies.

- Blank cells are ignored by this test. A column of entirely blank cells is
  (vacuously) numeric.
- The test is on the RAW TEXT after trimming, and is about parseability alone —
  not about how many distinct values there are or whether they look like codes.
  `"01"`, `"02"`, `"03"` all parse, so a column of zero-padded site codes is
  **numeric** and does NOT reach this spec (see `spec/groupcompare-dirty.md`).
- Values R accepts (column stays numeric), verified directly: `"01"`, `" 01 "`,
  `"1e3"`, `"0x1A"`, `"Inf"`, `"-Inf"`.
- Values R rejects (column becomes categorical), verified directly: `"NA"`,
  `"NaN"`, `"1,000"`, `"TRUE"`, any whitespace-only cell that arrived untrimmed.

`responder` contains only `"Yes"` and `"No"`, neither of which parses, so this
case is categorical.

## Population

Complete cases across the two mapped roles. Both the outcome and the group
column are read as text; a blank cell in either makes the row missing, and the
row is dropped and counted in `n_dropped`. `n` is the number of surviving rows,
equivalently the sum of the contingency table.

**Unlike the numeric branch, the categorical branch does NOT drop small
groups.** There is no "fewer than two values" filter here at all: a group with a
single row stays in the table and contributes to the test. `n_dropped` in this
branch counts missing-value drops only. (This asymmetry between the two branches
is the app's, verified in its code, not an oversight in this spec.)

For this case, `responder` and `arm` both have zero blank cells, so
`n_dropped = 0` and `n = 150`.

The analysis requires at least two distinct surviving group values; with fewer
it is an error, not a result.

The literal text `"NA"` is an ordinary outcome or group level here, not missing.

**Divergence from the exported script.** The downloadable `.R` script reads the
CSV with R's `read.csv(...)`, whose behaviour differs from the live app's in
three ways: it does not trim whitespace from text cells (so `"Yes "` becomes its
own level there); it treats a literal `"NA"` cell as missing; and it keeps a
whitespace-only cell as a one-character string rather than dropping the row.
This spec describes the live app.

## Roles

- **outcome** — arbitrary text; every distinct non-blank value is a level of the
  table's ROW dimension.
- **group** — arbitrary text; every distinct non-blank value is a level of the
  table's COLUMN dimension. No reference level, no ordering concept.

**Both dimensions are ordered by ordinary ascending string sort.** The row
levels are the sorted distinct outcome strings, the column levels the sorted
distinct group strings. This ordering is load-bearing for the 2 x 2 odds ratio
below, which is defined by cell position.

**Collation caveat, measured not assumed.** The app's sort is R's `sort()`,
which orders by the process's LC_COLLATE locale rather than by code point.
Under a UTF-8 locale R sorts `c("beta","Alpha","alpha","B","_z","Zed")` as
`_z, alpha, Alpha, B, beta, Zed`, while Python's `sorted()` gives
`Alpha, B, Zed, _z, alpha, beta` — a genuinely different order, verified by
running both. The two agree whenever the levels differ at their first
character within one case class, which is true of every level in every
shipped case (`"High dose"`, `"Low dose"`, `"Placebo"`), so nothing here is
ambiguous in practice. Use a plain code-point sort, and treat a future case
whose group levels differ only by letter case or by leading punctuation as
needing this pinned before it can be compared.

## The contingency table

Cross-tabulate outcome (rows) against group (columns) over the surviving rows.
`n` is the table's total.

For this case the table is:

```
          High dose  Low dose  Placebo
No               10        28       35
Yes              40        22       15
```

## Test selection

First compute the **Pearson chi-square test of independence WITHOUT any
continuity correction** on the table, and take its expected cell counts
`E_ij = row_total_i * col_total_j / n`.

- **If any expected cell count is strictly less than 5 -> Fisher's exact test**,
  in its general **r x c** form (not restricted to 2 x 2). Reported test name:
  `Fisher's exact test`.
- **Otherwise -> the Pearson chi-square test, still with no continuity
  correction.** Reported test name: `Pearson chi-square test`.

Two things about the correction, both load-bearing:

- The rule is **no continuity correction, ever** — the chi-square statistic and
  p-value are the uncorrected ones. R applies Yates' correction by default, and
  only to 2 x 2 tables; the app explicitly turns it off. On a 2 x 2 table the
  corrected and uncorrected p-values genuinely differ, so an implementation that
  leaves a correction on will disagree. (On any larger table, including this
  case's 2 x 3, R's correction is a no-op, so this case cannot by itself
  distinguish the two settings — the acceptance test
  `test_chi_square_has_no_continuity_correction` uses a 2 x 2 fixture precisely
  because this case cannot.)
- The expected-count rule uses the expected counts from that same uncorrected
  chi-square computation, and the threshold is **strictly less than 5** on ANY
  single cell — not "20% of cells", not "less than or equal to 5".

For this case the smallest expected count is 24.33, so the chi-square test runs.

**Fisher's exact test, r x c form**, specified because the choice of
implementation matters: the null distribution is the multivariate
hypergeometric over all tables with the SAME row and column margins as the
observed one, and the two-sided p-value is the total probability of every such
table whose probability is less than or equal to the observed table's (R admits
a table whose probability exceeds the observed one by no more than a relative
1e-7, a tolerance that only affects exact ties). This is a deterministic,
exhaustive calculation.

> **Warning for the implementer, measured not assumed.** `scipy.stats.
> fisher_exact` is exact for 2 x 2 tables (it reproduces R to floating-point
> noise), but for **larger tables it is a Monte Carlo test**: it returns a
> different answer on repeated calls with the identical input (measured: the
> same 3 x 3 table gave 0.0125 and then 0.0142 against R's exact
> 0.012396333824905242) and cannot meet this harness's 1e-6 agreement gate. Use
> an exhaustive enumeration over the fixed-margin tables instead; a
> straightforward one was verified to reproduce R to within 1e-14 relative on
> four different tables.

The **reported `statistic`**:

- for the chi-square branch, the uncorrected Pearson chi-square statistic
  `sum((O - E)^2 / E)`;
- for the Fisher branch, **`None`** — Fisher's exact test has no test statistic.
  This is a structural property of the test, not a missing value, and `None` is
  the correct report. Do not substitute the chi-square statistic there.

## Effect sizes

- **Cramer's V, always.** Computed from the **uncorrected chi-square statistic
  `X2` — including in the Fisher branch**, where the chi-square statistic is
  still computed (on the same table, with correction off) purely to feed this
  effect size even though its p-value was discarded:

  ```
  V = sqrt( X2 / (n * (min(nrow, ncol) - 1)) )
  ```

  with `n` the table total. Effect label: `Cramér's V` (note the acute accent on
  the `e`). There is no confidence interval — `lo` and `hi` are absent/None.

- **Odds ratio, 2 x 2 tables ONLY.** When the table is exactly 2 x 2, an odds
  ratio and 95% CI are reported in ADDITION to Cramer's V, built from the table
  by position with the row/column ordering fixed by the string sort above. With
  `a = table[1][1]`, `b = table[1][2]`, `c = table[2][1]`, `d = table[2][2]`
  (1-indexed):

  - **Haldane-Anscombe correction:** if ANY of the four cells is zero, add 0.5
    to ALL FOUR cells first (not just the zero one), and say so in the report.
  - `OR = (a * d) / (b * c)`
  - `se = sqrt(1/a + 1/b + 1/c + 1/d)` (on the corrected cells if the correction
    was applied)
  - `CI = exp(log(OR) - 1.96 * se)` to `exp(log(OR) + 1.96 * se)` — the literal
    constant 1.96, not the exact normal quantile.

  The odds ratio is for the FIRST outcome level in the FIRST group versus the
  SECOND group, both in string-sort order.

  This case's table is 2 x 3, so no odds ratio is reported for it.

## Post-hoc

**There is none in this branch.** The app performs no pairwise follow-up after a
categorical comparison, at any table size and at any p-value. `posthoc` is
always `None` here. (This is not symmetric with the numeric branch, which does
run Tukey/Dunn for three or more groups; the asymmetry is the app's.)

## Reported quantities

`compare_groups(df, outcome, group, nonparametric=None) -> dict`:

- `test_name` — `Pearson chi-square test` or `Fisher's exact test`.
- `p_value` — the chosen test's two-sided p-value, full precision.
- `statistic` — the uncorrected chi-square statistic, or `None` for Fisher.
- `effect` — `{label, value, lo, hi}` for Cramer's V, with `lo`/`hi` `None`.
- `n_per_group` — `{group level: int}`, the table's column totals.
- `n` — the table total.
- `n_dropped` — rows dropped for missing values.
- `posthoc` — always `None`.

The `nonparametric` argument is ignored in this branch: the parametric/
non-parametric routing rule is a numeric-outcome concept and is never consulted
for a categorical outcome, not even when the caller forces it.

Report all floats at full precision — never round inside the function.

## Display (informational — not part of `compare_groups`'s contract)

The app's categorical sentence, verified by generating this exact case's output,
is:

```
<outcome> by group (n = <n>): <test name>: <p>, <effect>.<notes>
```

Note the differences from the numeric branch's sentence: there are **no
per-group summaries**, **no routing-reason clause** (there is no routing
decision to report), and **no post-hoc clause**; the analysed row count appears
inline as `(n = <n>)` instead.

- `<p>` is `p < 0.001` when p < 0.001, else `p = %.3f` — **with spaces** around
  `=` and `<`.
- Numbers are rendered at **3 significant figures, plain (never scientific)
  notation, trailing zeros dropped**.
- `<effect>` is `Cramér's V = <value>`, followed — for a 2 x 2 table only — by
  `; odds ratio for <outcome column>=<first outcome level>, <first group> vs
  <second group> = <OR> (95% CI <lo> to <hi>)`, itself followed by
  ` (0.5 continuity correction applied)` when the Haldane-Anscombe correction
  fired.
- Notes: ` <n_dropped> row(s) with missing values were excluded.` when non-zero.

Real example, generated from this exact case's data:

> `responder by group (n = 150): Pearson chi-square test: p < 0.001, Cramér's
> V = 0.421.`

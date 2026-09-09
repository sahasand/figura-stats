# Analysis spec: summary-table1

Input: `stats-validation/cases/summary-table1/data.csv`. The real header is
`age,length_of_stay,crp,sex,diabetes,arm` (verified: `head -1`), 120 data rows.
The mapped roles are:

- **group** = `arm` — two levels, `Control` (60 rows) and `Treatment` (60 rows),
  in that order in the file.
- **continuous** = `age`, `length_of_stay`, `crp`
- **categorical** = `sex`, `diabetes`

The file is a verbatim copy of the app's shipped Summary demo fixture
(`tests/testthat/fixtures/summary-demo.csv`, md5 `d1ae84f62c3b31126b2b1c24424b1bd4`
on both). Its generator (`data-raw/summary-demo-generator.R`) engineered it so
that **age reads approximately normal (-> mean +/- SD) while `length_of_stay` and
`crp` are right-skewed (-> median (IQR))**, with exactly **8 blank
`length_of_stay` cells** to exercise per-variable missing-value reporting. The
case therefore covers all three row shapes in one table: the mean branch, the
median branch, and the categorical count branch.

**This spec, and `summarize`, model the LIVE APP ONLY** (`web/guided/summary/
analyze-form.js`'s `buildSummarySpec` feeding `R/summarize.R`'s `fig_summary`) —
never the downloadable/exported `.R` script. See "Divergence from the exported
script" at the end.

**Table 1's distinctive property: the DECISION is an output.** For every
continuous variable the app chooses between mean +/- SD and median (IQR) and
prints that choice in the row label. A table whose numbers are each individually
correct but whose *choice* is wrong is still wrong, so the choice is a validated
quantity in its own right (`decisions`, and the comparator's
`DECISION_MISMATCH`), not a presentational detail.

## Cell reading

Every cell is read as text and **trimmed of leading and trailing whitespace
before anything else looks at it**: the app's CSV parser splits lines on `\r?\n`
and applies `String(cell).trim()` to every cell as it builds the table
(`web/lib/csv.js`'s `parseCsv`). A cell that is empty after trimming is *blank*.

- A **blank** cell in a continuous column is a **missing value** (`as.numeric("")`
  is `NA`, and `.numeric_col` explicitly exempts the empty string from its
  "must be numeric" check). It is counted in that variable's Missing column and
  excluded from that variable's statistics. **The row is NOT dropped** — see
  Population.
- A **blank** cell in a categorical column is a missing value: it is excluded
  from the level counts AND from the percentage denominator, and counted in that
  variable's Missing column.
- A **blank** cell in the GROUP column is not missing and not dropped: the row
  is assigned to a group level literally named `(missing)`
  (`grp[is.na(grp) | grp == ""] <- "(missing)"`). This file has no blank `arm`
  cells, so no `(missing)` column appears.
- The literal two-character text **`NA` is NOT a missing value** anywhere in the
  live app. In a categorical column it is an ordinary level named `NA`; in the
  group column it is an ordinary group named `NA`. In a **continuous** column it
  is a hard error: `.numeric_col` raises `Column '<name>' must be numeric.` and
  `fig_summary` renders nothing at all. (This file contains no literal `NA`
  cells.)
- Whitespace-only cells cannot survive the parser's trim, so they are blanks.

## Which variables are continuous and which are categorical

**Normative, and `summarize`'s own job.** `summarize(df, variables, group=None)`
receives a FLAT list of variables — the split into continuous and categorical is
not an input, it is a decision the implementation makes from the data, exactly
as the app does. (The case's declared `roles.continuous` / `roles.categorical`
are the comparator's expectation of the answer, never a hint to Path B.)

The rule, restating `classifyColumns` in `web/guided/summary/analyze-form.js`
(whose output becomes `options.continuous` / `options.categorical` in the spec
sent to R — `R/summarize.R` never re-classifies anything, it does what those two
lists say):

> A variable is **continuous** if and only if its column is **numeric** AND it
> has **MORE THAN FIVE** distinct non-missing values. Everything else is
> **categorical**.

with the two terms pinned:

- **numeric** is the CSV parser's per-column type (`web/lib/csv.js`'s
  `parseCsv`): a column is numeric when **every non-blank cell parses as a
  finite number** and at least one cell is non-blank. Blank cells do not
  disqualify a column. The literal text `NA` is not a number, so **one `NA`
  cell makes the whole column categorical** — the same asymmetry the Cell
  reading section describes.
- **distinct** counts the trimmed cell TEXT, not parsed values, and excludes
  blanks. `"1"` and `"1.0"` are two distinct values.

Consequences worth stating because they are easy to get backwards:

- The boundary is **more than five**, not five or more: a numeric column with
  exactly 5 distinct values is CATEGORICAL.
- A 0/1-coded numeric flag is categorical (2 distinct values), and is reported
  as counts and percentages, never as a mean.
- A numeric column carrying one literal `NA` is categorical, so it never
  reaches `.numeric_col` and never raises the "must be numeric" error.
- The group column is never among `variables`, so it is never classified.

For this case (counted from the file): `age` numeric with 45 distinct values,
`length_of_stay` numeric with 64 (and 8 blanks), `crp` numeric with 82 — all
three continuous; `sex` and `diabetes` are non-numeric with 2 levels each —
categorical; `arm` is the group.

## Population

**No row is ever dropped.** Unlike every other analysis in this repository,
Summary has no complete-case filter: `fig_summary` iterates the full row list
for every variable and handles missingness per variable, per group.

- `n` = 120 = the number of data rows in the CSV.
- `n_dropped` = **0**, always, for every Summary case. It is reported so the
  comparator's count tier has the same shape as every other analysis's, and so
  that a future implementation that silently starts dropping rows is caught.
- Per-group N (the `(N=...)` in each column header) counts **all** rows in that
  group, including rows whose value for a given variable is missing. It is
  therefore NOT the denominator of anything — see Categorical cells.
- Missingness is reported per variable in a trailing Missing column: for a
  continuous variable, the count of `NA` after numeric coercion; for a
  categorical variable, the count of blank cells (on the variable's header row
  only — its level rows carry an empty Missing cell).

For this case: `age` 0 missing, `length_of_stay` 8 missing, `crp` 0 missing,
`sex` 0 missing, `diabetes` 0 missing.

## The decision rule — mean +/- SD vs median (IQR)

**Normative.** For one continuous variable, with `x` the values fed to the
decision (see "Grouped data" below) after dropping `NA`, and `n = length(x)`:

1. If `n < 3` **or** `x` has fewer than 3 distinct values -> **median (IQR)**.
2. Otherwise, if `n > 300` -> **mean +/- SD** when `|skewness| < 1`, else
   **median (IQR)**. **No normality test is run at this size** (Shapiro-Wilk
   over-rejects trivial departures at large n).
3. Otherwise (`3 <= n <= 300`) run a Shapiro-Wilk test on `x`. Use
   **mean +/- SD** when its p-value is `>= 0.05` **and** `|skewness| < 1`.
   Otherwise **median (IQR)**.

Both conditions in rule 3 must hold for mean; either one failing gives median.
The threshold is `n > 300` (strict), so `n == 300` takes the Shapiro path.

**Skewness is the population (biased) third standardised moment**, not the
sample-corrected G1 and not `scipy.stats.skew(bias=False)`:

```
m = mean(x)
s = sqrt(mean((x - m)^2))          # population SD, denominator n
skewness = mean((x - m)^3) / s^3
```

Fewer than 3 non-missing values -> skewness is undefined (`NA`); zero spread
(`s == 0`) -> skewness is exactly `0`. (Both are unreachable from rule 1, which
has already routed those cases to median.)

### Grouped data — the decision is made ONCE per variable

**Normative, and the rule most likely to be got wrong.** When a group role
exists, the mean-vs-median decision is made **once for the whole variable** and
then applied to **every** group's cell, so a variable's row is one shape across
all columns. It is never re-decided per group.

The values fed to that single decision are **group-mean-centred**: within each
group, that group's own non-missing mean is subtracted from its values, and the
centred values from all groups are pooled and passed to the decision rule above
(`decide_values` in `fig_summary`). Pooling *uncentred* group-shifted normals
produces a bimodal mixture that fails Shapiro-Wilk even when every group is
perfectly normal; centring tests the within-group shape, which is what the table
actually summarises.

The **cells** are computed from the RAW (uncentred) values of each group — only
the decision sees the centred values.

Verified on this case (R, from the repo root):

```r
d <- read.csv("stats-validation/cases/summary-table1/data.csv", check.names = FALSE)
grp <- as.character(d$arm)
skewp <- function(x) { x <- x[!is.na(x)]; m <- mean(x); s <- sqrt(mean((x-m)^2)); mean((x-m)^3)/s^3 }
for (col in c("age","length_of_stay","crp")) {
  x <- suppressWarnings(as.numeric(as.character(d[[col]]))); ce <- x
  for (g in unique(grp)) { i <- grp == g & !is.na(x); ce[i] <- x[i] - mean(x[i]) }
  ce <- ce[!is.na(ce)]
  cat(col, length(ce), skewp(ce), shapiro.test(ce)$p.value, "\n")
}
```

| variable | n (non-missing) | population skewness (centred) | Shapiro-Wilk p (centred) | decision |
|---|---|---|---|---|
| `age` | 120 | -0.124159 | 0.553753 | **mean +/- SD** |
| `length_of_stay` | 112 | 1.30768 | 3.30962e-09 | **median (IQR)** |
| `crp` | 120 | 3.11134 | 6.1587e-15 | **median (IQR)** |

All three take the Shapiro path (`3 <= n <= 300`). `age` passes both conditions;
`length_of_stay` and `crp` fail both.

## Number formatting

**Normative.** Every reported number goes through one rule
(`.fmt_num`, `R/summarize.R`):

```r
format(signif(v, 3), trim = TRUE, scientific = FALSE, drop0trailing = TRUE)
```

That is: round to **3 significant figures** (not 3 decimal places), render in
**plain notation** (never scientific, at any magnitude), and **drop trailing
zeros** (and a trailing decimal point).

**How `signif` actually rounds, which is the one thing an independent
implementation is likely to get wrong.** `signif(x, 3)` is not "round the exact
decimal value of the double to 3 significant figures". R computes it
(`src/nmath/fprec.c`) as

```
e = 3 - 1 - floor(log10(|x|));   nearbyint(x * 10^e) / 10^e
```

— it **scales, rounds the scaled value half-to-even, and scales back**. The
scaling multiply is itself a floating-point operation, and it can land *exactly*
on a `.5` tie even when the original double is not a tie at all. That is where a
decimal-exact rounding rule diverges:

- `2.225` as a double is `2.2250000000000000888…`, strictly ABOVE the tie, so a
  decimal-exact rule rounds it up to `2.23` — but `2.225 * 100` is **exactly**
  `222.5`, and half-to-even gives `222`, so R renders **`2.22`**.
- `1.315` as a double is `1.3149999999999999467…`, strictly BELOW the tie, so a
  decimal-exact rule rounds it down to `1.31` — but `1.315 * 100` is again
  exactly `131.5`, and half-to-even gives `132`, so R renders **`1.32`**.
- `2.475` gives `2.48` under both rules — the scaled `247.5` rounds up to the
  even `248`, and the double is above the tie. Agreement by coincidence.

So implement the algorithm, not an approximation of it: **scale, round the
scaled value half-to-even (Python's one-argument `round()` on a float is exactly
that), scale back** — never a two-argument `round(v, k)` or a decimal-exact
half-up rule. (C's `printf("%.2f")` and a naive `Decimal(ROUND_HALF_UP)` are
wrong in a third way.)

R-verified probe set (`format(signif(v, 3), trim = TRUE, scientific = FALSE,
drop0trailing = TRUE)`):

| v | rendered |
|---|---|
| `12.3456` | `12.3` |
| `1234.5` | `1230` |
| `0.00123456` | `0.00123` |
| `2.50` | `2.5` |
| `2.0` | `2` |
| **`1.125`** | **`1.12`** (half-to-even; NOT `1.13`) |
| **`2.225`** | **`2.22`** (scaled tie; a decimal-exact round says `2.23`) |
| **`1.315`** | **`1.32`** (scaled tie; a decimal-exact round says `1.31`) |
| `2.475` | `2.48` |
| `250000` | `250000` (plain, not `2.5e+05`) |
| `0` | `0` |

## Continuous cells

For a group's non-missing values `xg`, in this order:

1. `length(xg) == 0` -> the cell is the em dash `—` (U+2014).
2. `length(xg) == 1` -> the cell is the bare formatted value, `.fmt_num(xg)`.
   (A single value has no sample SD — `sd()` of length 1 is `NA` — so no
   `M +/- SD` cell can be formed. This applies to BOTH kinds.)
3. Otherwise the variable's chosen kind decides:
   - **mean** -> `"<mean> ± <sd>"`, with U+00B1 and a space each side. `sd` is
     the **sample** standard deviation, denominator `n - 1` (R's `stats::sd`).
   - **median** -> `"<Q2> (<Q1>–<Q3>)"`, with an **EN DASH** U+2013 between the
     quartiles and no spaces around it. The quartiles are
     `stats::quantile(x, c(0.25, 0.5, 0.75), type = 7)` — **type 7**, linear
     interpolation between order statistics, which is numpy's default
     `method="linear"`. Every number goes through `.fmt_num`.

R-verified cells for this case:

| row | Control (N=60) | Treatment (N=60) | Missing |
|---|---|---|---|
| `age, mean ± SD` | `59.6 ± 11.1` | `60.2 ± 11.4` | `0` |
| `length_of_stay, median (IQR)` | `3.7 (2.25–6)` | `4.1 (2–7.3)` | `8` |
| `crp, median (IQR)` | `4.5 (2.48–7.15)` | `4.85 (2.22–8.45)` | `0` |

## Categorical cells

A categorical variable emits a **header row** followed by one **level row** per
level:

- The header row's label is the bare variable name, its group cells are all the
  **empty string**, and its Missing cell is the count of blank cells across all
  rows. (In the HTML table the header row also carries a `n (%) of <N> with
  data` note; that note is NOT part of the copy-pasteable text output.)
- Levels are the distinct non-blank values, **sorted** (`sort(unique(...))` — R's
  locale-aware string sort, ordered by the process's LC_COLLATE rather than by
  code point; for this file's ASCII, same-case levels that is plain
  lexicographic: `Female` before `Male`, `No` before `Yes`).

  **Locale-aware here, code-point in the group-comparison specs — deliberately,
  and here is why.** `spec/groupcompare-{numeric,categorical,dirty}.md` require a
  plain code-point sort: their orders are only ever a display and pair-naming
  convention, so they trade fidelity for an order that does not depend on the
  locale of whatever process runs R (webR in a browser is not the developer's
  locale). This spec, `spec/cox-adjusted.md` and `spec/logistic-confounding.md`
  state the locale rule instead, because their sorts are R's own
  `sort()`/`factor()` level order feeding the rendered table and the
  reference-level fallback, where "code point" would simply misdescribe the call
  site. Under `en_CA.UTF-8` the two rules disagree on, e.g., `c("B","a")`
  (locale: `a, B`; code point: `B, a`); no shipped case has such a level set, and
  all six specs say so rather than leaving it to inference.
- A level row's cell for group `g` is:

  ```r
  denom <- <count of non-blank cells for this variable in group g>
  k     <- <count of cells equal to this level in group g>
  if (denom == 0) "—" else sprintf("%d (%.0f%%)", k, 100 * k / denom)
  ```

  **The percentage does NOT go through `.fmt_num`.** It is `sprintf("%.0f%%")` —
  a whole number of percent, no decimal places, no significant-figure rule —
  and it rounds **half to even** (C's `printf`): R-verified,
  `sprintf("%.0f", 12.5)` is `"12"` and `sprintf("%.0f", 37.5)` is `"38"`.
- A level row's Missing cell is the **empty string** (missingness is reported
  once, on the header row).
- The denominator is the **non-missing count within that group**, never the
  group's `(N=...)` header count. Those coincide here (no blank `sex`/`diabetes`
  cells) but are different quantities.

R-verified cells for this case: `sex` — `Female` `32 (53%)` / `28 (47%)`,
`Male` `28 (47%)` / `32 (53%)`; `diabetes` — `No` `32 (53%)` / `44 (73%)`,
`Yes` `28 (47%)` / `16 (27%)`.

## Row and column order

- Group levels (the table's columns) are in **first-appearance order in the
  file**, not sorted: `Control`, then `Treatment`. The column header is
  `sprintf("%s (N=%d)", level, n_in_level)`.
- Rows are **all continuous variables first, in the order they were selected,
  then all categorical variables, in the order they were selected**. The
  selection order is the CSV's own column order (`buildSummarySpec` filters
  `table.columns`), so here: `age`, `length_of_stay`, `crp`, `sex`, `diabetes`.
- With no group role, there is exactly one column, headed `Overall (N=<n>)`.

## How the DECISION is surfaced in the displayed output

**Normative — this is what the comparator's display tier reads.** The `text`
field is a TSV of the same table, followed by a blank line and a methods
paragraph. `fig_summary` prints the choice **in the row's own label**:

```
Characteristic	Control (N=60)	Treatment (N=60)	Missing
age, mean ± SD	59.6 ± 11.1	60.2 ± 11.4	0
length_of_stay, median (IQR)	3.7 (2.25–6)	4.1 (2–7.3)	8
crp, median (IQR)	4.5 (2.48–7.15)	4.85 (2.22–8.45)	0
sex			0
Female	32 (53%)	28 (47%)	
Male	28 (47%)	32 (53%)	
diabetes			0
No	32 (53%)	44 (73%)	
Yes	28 (47%)	16 (27%)	
```

So a continuous row's label is exactly `"<variable>, mean ± SD"` or
`"<variable>, median (IQR)"` — the decision, verbatim, in the published artifact.
A categorical variable's kind is surfaced structurally instead: a bare-name row
with empty cells, followed by level rows. The per-variable *reason* (the
Shapiro-Wilk p-value or skewness that drove the choice) appears only in the HTML
table's `why` sub-line and in the exported script's comments — **not** in the
TSV — so the reason is deliberately outside this contract; only the choice is
compared.

The methods paragraph after the blank line is fixed prose plus one conditional
clause: `normality was assessed within groups with the Shapiro-Wilk test
(n <= 300) and skewness.` when a group role exists, and the same sentence without
`within groups` when there is none.

### Citation paragraph (not compared)

The `text` field ends with one extra paragraph, separated from everything
above it by a blank line: a fixed attribution sentence beginning
`Analyses were performed with Figura (` and ending `in the browser.`. It
names the tool, a URL, a year, and the R packages the analysis used. It
carries no statistical content and is excluded from every comparison: the
comparator removes exactly one such trailing paragraph before parsing. An
implementer of this spec must not emit it and must not parse it.

## Reported quantities

`summarize` reports, as the exact displayed string wherever the display is the
claim:

- `rows` — one entry per displayed table row, in display order:
  `{variable, level, kind, cells: {group_level: str}, missing: str}`.
  - `variable` is the bare column name (never the `", mean ± SD"` label).
  - `level` is the level string for a categorical level row, and `None` for a
    continuous row or a categorical header row.
  - `kind` is `"mean"`, `"median"`, or `"count"`. A categorical variable's
    header row and all of its level rows carry `"count"` — the kind is a
    property of the VARIABLE, so the comparator can read one decision per
    variable off either side.
  - `cells` values are the **rendered strings**, per the rules above. At three
    significant figures the string IS the published claim, so the comparator
    compares them exactly and there is no display-artifact tier for Table 1.
  - `missing` is the rendered Missing cell (`""` for a level row).
- `levels` — the group levels in display order (first-appearance).
- `n_per_group` — `{group level: int}`, counting every row in the group.
- `n` — total rows. `n_dropped` — always `0`; see Population.

## Divergence from the exported script (informational)

The downloadable `.R` script re-reads the CSV with `read.csv(...)` followed by a
`trimws` pass and `df[df == ""] <- NA` (`R/script.R`'s `.script_data`), which is
**not** the browser parser — it is a second reader built to match it. For this
case the two agree — the file has no literal `NA` text, no whitespace-padded
cells, and blank numeric cells become `NA` under both readers — so the exported
script reproduces every cell in the table above.

That agreement used to be a property of this file rather than a general
guarantee, and `stats-validation/cases/logistic-dirty/` was a case where the same
preamble made the script analyse a different study. Since **2026-07-28** it is a
general guarantee: `issues/02` is resolved, `.script_data` overrides
`na.strings` and trims character columns, and `logistic-dirty` publishes zero
findings. The reason to keep reading it as two readers rather than one is that
the parity is a maintained contract on `R/script.R`, not an identity — see
`stats-validation/issues/02-app-vs-exported-script-missing-values.md`.

**One thing that constrains any future edit to that preamble, and is easiest to
see from this case:** `.summary_script` calls `mean()`/`quantile()` on the raw
`df[[col]]` with no `as.numeric()` in front of it, so the preamble must keep
letting `read.csv` type-convert numeric columns. `colClasses = "character"` — the
apparently-closer mirror of the browser parser, which hands R strings for every
column — would break Table 1's exported script specifically. It was considered
and rejected for that reason when issue 02 was fixed.

The script also computes only the statistic the app chose (`tapply(..., mean/sd)`
for a mean variable, `tapply(..., quantile(type = 7))` for a median one), so the
DECISION itself is re-expressed there and can be checked against the screen —
that is the script tier for Table 1.

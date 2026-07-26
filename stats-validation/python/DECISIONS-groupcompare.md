# DECISIONS — validate/groupcompare.py

Choices the three specs and `INTERFACES.md` left silent, or where two documents
had to be reconciled. Everything the specs state explicitly is implemented as
stated and is not repeated here.

## 0. [RESOLVED — see postscript] Blocking gap: the `cases/` fixtures are absent

`python/tests/test_groupcompare.py` resolves `CASES = parents[2]/"cases"` and
loads `cases/groupcompare-{numeric,categorical,dirty}/{data.csv,case.json}` via
`load_case`. **No `cases/` directory exists in this working tree.** Seven of the
nineteen acceptance tests therefore fail at fixture load with
`FileNotFoundError`, before any assertion runs:

| test | case |
|---|---|
| `test_tukey_significant_pairs_match_r` | groupcompare-numeric |
| `test_eta_squared_three_group_parametric_matches_r` | groupcompare-numeric |
| `test_dunn_significant_pairs_match_r` | groupcompare-dirty |
| `test_epsilon_squared_three_group_nonparametric_matches_r` | groupcompare-dirty |
| `test_numeric_looking_codes_route_to_the_numeric_branch` | groupcompare-dirty |
| `test_dirty_case_counts_blanks_in_mapped_columns_only` | groupcompare-dirty |
| `test_cramers_v_categorical_matches_r` | groupcompare-categorical |

**Decision: do not synthesise the fixtures.** Those seven tests assert
R-precomputed constants (Welch F 34.835216031005963, eta-squared
0.32102532801259492, H 58.617246335913329, Cramér's V 0.42136501862202791, …)
about specific 150-row datasets. Data manufactured to reproduce those constants
would make the suite report green while verifying nothing — the exact failure
mode this module exists to detect, in a module whose only purpose is independent
verification. The seven are left failing, visibly, with the missing input named.
Dropping the real `cases/` tree into the repository root should turn them green
with no code change.

What was done instead, to keep the un-runnable paths from going unexercised
(these are engineering sanity checks, **not** substitutes for the acceptance
tests, since none of them pins an R constant):

- tie-corrected Kruskal-Wallis `H` and `p` vs `scipy.stats.kruskal` on a heavily
  tied 1/2/3 code column — agreed to 7e-14 relative;
- `_bh_adjust` vs `statsmodels`' `fdr_bh` — bit-identical;
- `_fisher_rxc` vs `scipy.stats.fisher_exact` on four 2x2 tables (scipy's 2x2
  path is genuinely exact) — agreed to ~6e-15 relative, and bit-identical across
  repeated calls on the 3x3 table where scipy's r x c path is not;
- the Mann-Whitney tied/large asymptotic path vs scipy's
  `method="asymptotic", use_continuity=True` — bit-identical;
- a synthetic frame of the same *shape* as groupcompare-dirty (CRLF endings, 12
  padded `site_code` cells, 4 blank `site_code` cells, 6 blanks in the unmapped
  `los_skewed`) routed to `Kruskal–Wallis test` / `epsilon-squared` with
  `n = 146`, `n_dropped = 4` (not 10), three group keys, and Dunn pair names in
  `<earlier>-<later>` order.

The 3x3 Fisher constant *is* pinned against R by a test that does run
(`test_rxc_fisher_matches_r_fisher_test`, R's 0.012396333824905242, reproduced
to 9.7e-15 relative).

### Integrator's postscript (2026-07-26)

The account in §0 documents the sanitized clean-room environment where this module was originally written, in which the `cases/` directory was deliberately excluded to avoid distributing confidential research datasets. In that isolated environment, 7 of 19 tests failed at fixture load. However, when the module is integrated into the repository and the genuine `cases/` fixture tree is present in the root, all 19 acceptance tests execute successfully and pass. No coverage gap exists in the repository.

## 1. Emulating R's numeric conversion (`_r_numeric`)

The specs give verified accept/reject lists but not an algorithm, and Python's
`float()` is not R's `as.numeric` in three places. Implemented explicitly:

- **hex accepted** — `float("0x1A")` raises in Python; R gives 26. Routed
  through `float.fromhex` when the body after an optional sign starts `0x`/`0X`.
- **`"NaN"` rejected** — `float("NaN")` succeeds in Python. R's `as.numeric`
  returns NaN, which the app's `is.na` check treats as non-parsing, and all
  three specs list `"NaN"` among the values that flip a column to categorical.
  Any parse yielding NaN is therefore reported as non-parsing.
- **underscore digit separators rejected** — `float("1_000")` is 1000 in Python
  and an error in R. Rejected before parsing. (`"1,000"` is rejected by both.)

`"Inf"`/`"-Inf"`/`"infinity"` are accepted by both, and pass through.

## 2. Type detection runs on the whole column, before any row is dropped

The specs say the test is over "every non-blank cell" of the outcome column and
that "one non-parsing cell anywhere in the column flips the ENTIRE analysis".
They do not say whether cells on rows that the Population filter will drop for a
blank *group* still count. Read literally — the column, not the surviving rows —
so detection runs first, on the full column. This matters only for a row with a
non-parsing outcome and a blank group.

## 3. Trimming uses Python's `str.strip()`

The app's parser is JS `String(cell).trim()`. `str.strip()` and JS `trim()` both
remove Unicode whitespace from both ends; they differ only on exotic code points
(e.g. `\x1c`–`\x1f`, stripped by Python and not by JS) that no CSV in scope
contains. Non-string cells are coerced with `str()` first, matching `String()`;
`None`/`NaN`/`pd.NA` are treated as blank rather than stringified to `"nan"`.

## 4. Two documents disagreed on the 2x2 odds ratio — `INTERFACES.md` wins

`spec/groupcompare-categorical.md` specifies an odds ratio with a
Haldane-Anscombe correction for exactly-2x2 tables. `INTERFACES.md` states the
contract carries no odds-ratio key, that no shipped case is 2x2, and that adding
one "requires extending this contract first" — a comparator that sees the clause
in displayed text raises MISSING_QUANTITY rather than ignoring it. Since
`INTERFACES.md` is the return-shape authority and the spec clause is written
under Display/effect reporting, **no odds ratio is returned**. The spec's
formula is not implemented rather than implemented-and-hidden, so nothing has to
be kept in sync with a contract that has not been extended. Flagging this as the
one place a future 2x2 case needs work in both files.

## 5. Fewer than two surviving groups raises `ValueError`

Both branches' specs say this "is an error, not a result" without naming a type.
`ValueError` with a message naming the surviving group count; nothing in the
contract describes an error return shape, so no sentinel dict is invented.

## 6. Fisher enumeration details

- The relative tie tolerance is applied in log space:
  `log p <= log p_obs + log1p(1e-7)`, avoiding an overflow-prone exponentiation
  before the comparison.
- Recursion is over rows, with the last row forced by the remaining column
  totals and a reachability bound (`max(0, row_left - capacity_of_later_cols)`)
  pruning branches that cannot complete. Exhaustive, deterministic, no sampling.
- **No size cap.** Exactness is the requirement, so a large sparse table is
  allowed to be slow rather than silently approximated. The Fisher branch only
  fires when some expected count is below 5, which in practice bounds the tables
  that reach it; a genuinely large one would need a network algorithm, and that
  is a change to make deliberately, not a fallback to hide.
- The 2x2 path goes through the same enumerator (verified equal to R's rule and
  to scipy's exact 2x2 result), so there is one code path, not two.

## 7. Numerical method choices where the spec named a quantity, not a routine

- **Shapiro-Wilk**: `scipy.stats.shapiro` (AS R94, the same algorithm R uses).
  Only ever compared against the 0.05 threshold.
- **Tukey adjusted p**: `scipy.stats.studentized_range.sf(q, k, df_resid)` with
  `q = |mean_j - mean_i| / sqrt(MSE/2 * (1/n_i + 1/n_j))` — R's `ptukey` on the
  classical fit, matching `TukeyHSD`.
- **eta-squared interval**: `scipy.stats.ncf.cdf` with `brentq`
  (`xtol=1e-12, rtol=1e-14`), and `scipy.stats.f.cdf` at `lam == 0` where the
  non-central parameterisation is degenerate. The spec's bracketing (start
  `hi = 1`, double while positive, cap `1e6`, undefined → 0 / 1 fallback) is
  implemented literally, since it determines the fallbacks. Converged tightly on
  purpose: the spec says R's own `uniroot` stops loose (~1.2e-4 on the
  non-centrality scale, ~2.5e-8 relative on the limits) and not to chase the
  gap; the acceptance tolerance on the limits is 1e-5 relative.
- **Distinct-value counts** (routing rule 1) use exact float equality on the
  centred residuals, matching R's `unique` on doubles. No epsilon clustering.
- **Mann-Whitney exact p** is delegated to `scipy.stats.mannwhitneyu(method=
  "exact")` one-sided, doubled and capped at 1 — R's own
  `min(2 * pwilcox(...), 1)` construction, chosen by which side of `n1*n2/2` W
  falls. The asymptotic branch is written out by hand to R's formula (tie-
  corrected sigma, `sign(z) * 0.5` continuity correction) rather than trusted to
  a library default.
- **Exactness threshold** reads "both group sizes are under 50" as
  `n1 < 50 and n2 < 50` (strict), matching R's `wilcox.test`.

## 8. `n_per_group` ordering and types

Insertion-ordered by ascending code-point group sort (the specs' collation
caveat says to use a plain code-point sort and to treat case-only or
leading-punctuation differences as needing a pin first). Values are built with
`int()` rather than left as `numpy.int64`, so the dict compares and serialises
as plain Python. Keys are the literal trimmed group strings.

## 9. Reuse of prior modules

`io.complete_cases` is reused for the missing-value filter, applied to a frame
of the two mapped roles only — which is both the spec's "a row is dropped for a
blank in a MAPPED column only" rule and what keeps unmapped columns out of any
intermediate representation. It is applied *after* trimming, since its
blank test matches the empty string exactly and would otherwise keep a
whitespace-only cell. `io.to_numeric` is deliberately **not** reused: it is
`pandas.to_numeric`, which rejects `"0x1A"` and accepts `"NaN"`/`"nan"` — the
opposite of R on both, and type detection is the hinge the whole dirty case
turns on.

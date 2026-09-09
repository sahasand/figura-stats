# Decisions

Path B's linear regression (`validate/linear.py`) was written from
`stats-validation/spec/linear-confounding.md`, `INTERFACES.md`,
`tests/test_linear.py` and `validate/io.py` only. No file under `R/`, `web/`,
`stats-validation/results/`, `harness/`, `compare/`, no `cases/*/case.json`, no
other `spec/*.md` and no other `validate/*.py` was opened, and no git history
was consulted. Where the spec left something open it was resolved from the
spec alone; every such choice is below.

## Interpretation choices

**What "blank" meant.** The spec's Cell reading section makes trimming happen
before anything else looks at a cell, so every cell of the outcome and of each
covariate is passed through a trim first; a non-string value (the acceptance
tests hand `fit_linear` a frame with real float columns, not the all-text frame
`load_case` returns) is left alone. A cell is blank when it is `None`, a NaN
float, a pandas missing value, or the empty string after that trim. A
whitespace-only cell is therefore blank and its row is dropped, which is what
`test_counts_and_blank_handling` exercises. `io.py`'s `complete_cases` is then
called on the trimmed frame, so the shared helper never has to know about
whitespace.

**A literal `NA` is an ordinary value.** Nothing special-cases the string
`"NA"`. It simply fails the numeric parse, which makes a covariate column
containing it categorical and gives it a level named `NA`, and makes the same
string in the outcome a hard error. That falls out of the parse rule rather
than being coded separately.

**What "parses as a number" means.** A cell parses when Python's `float()`
accepts it AND the result is finite. The finiteness half is a choice the spec
does not force: it means a cell reading `Inf` or `NaN` fails the parse, so a
covariate column containing one is classified categorical and the same string
in the outcome is an error. The alternative reading would let a non-finite
value into the design silently, where it would poison every coefficient with no
signal at all, and the spec's own concern in this area — the literal `NA`,
which fails `float()` under either reading — is unaffected. No shipped cell is
`Inf` or `NaN`.

**When the numeric classification is decided: before the complete-case
filter.** The spec says the outcome check is over the whole column and that
blank cells are exempt from it. Blanks only still exist before the filter, so
the check must see rows the filter will later drop. The covariate rule is
stated as "the same whole-column rule", so covariate classification is also
taken over the whole original column. The consequence, worth naming: a numeric
covariate carrying one stray non-numeric cell is classified categorical even
when that cell sits in a row the filter removes. This case is unaffected (320
rows, none dropped, every cell clean), and no acceptance test distinguishes the
two readings, but the reading is a choice and this is where it is recorded.

**How rank deficiency is detected, and which column is declared aliased.** The
design's columns are walked left to right in the order the spec fixes:
intercept, then each covariate in declared order, and within a categorical
covariate its non-reference levels in level order. An orthonormal basis of the
columns already retained is carried along; each new column is projected off it
and the column is declared aliased when the residual norm has collapsed to at
most `1e-7` times the column's own norm, or when the column is identically
zero. `1e-7` is R's own `dqrdc2` pivoting tolerance, and the ratio-of-norms
form is what makes the test scale-free. Because the walk is left to right, the
LATER member of an exactly collinear pair loses its estimate, which is the
behaviour the spec pins and which was checked both ways: with covariates
ordered `arm, age, age2` the aliased term is `age2`, and ordered
`arm, age2, age` it is `age`.

An aliased term is present in `terms` with all five values `float("nan")` —
estimate, standard error, both bounds and p — never omitted and never zero.
Its own univariable model is fitted separately and reports it as an ordinary
reportable cell.

**The exact t-quantile and chi-square calls.** The interval half-width is
`scipy.stats.t.ppf(0.975, n - p) * se` and the p-value is
`2 * scipy.stats.t.sf(abs(beta / se), n - p)`, with `p` the number of columns
actually retained by the rank walk, including the intercept — so a dropped
column lowers `p` and raises the residual degrees of freedom, exactly as the
spec requires. The constant 1.96 appears nowhere. Breusch–Pagan's upper tail is
`scipy.stats.chi2.sf(n * r2_aux, 1)`.

**The coefficient covariance.** `s2 * R⁻¹R⁻ᵀ` from the QR factorisation of the
retained design, rather than an explicit inverse of `X'X`, which is the same
quantity computed the better-conditioned way. Standard errors are the square
roots of its diagonal.

**Leverage and Cook's distance.** The hat diagonal is the row-wise sum of
squares of `Q` from that same QR factorisation, which is algebraically
`diag(X(X'X)⁻¹X')` without forming the n-by-n matrix. Cook's distance is the
spec's formula verbatim, with `p` the retained-column count including the
intercept and `s²` the residual mean square. A non-finite `D_i` — a point of
full leverage, where `h_i` is 1 — is excluded from the count rather than
counted as influential. The shipped case gives 18, matching the spec.

**Ties and constants in Shapiro–Wilk.** The test is run only when
`3 <= n <= 5000`, checked before the call rather than left to the library, so
the size window is the spec's and not scipy's. Outside it, `shapiro_p` is
`None`. Inside it, the call is wrapped: any exception, and any non-finite
p-value, also yields `None`. That covers the degenerate inputs the spec names —
identical residuals, and by extension a residual vector with too little
variation for the statistic to be defined — as an absence rather than an error,
and it means a heavily tied but non-constant residual vector still gets
whatever p scipy computes rather than being second-guessed. `shapiro_triggered`
is false whenever `shapiro_p` is `None`.

scipy's Shapiro–Wilk agrees with R's to about eight significant figures on the
shipped case (0.5101217797 against R's 0.5101217193), a difference in the two
AS R94 implementations rather than in the model. The acceptance test allows
`1e-4` for exactly this reason.

**Breusch–Pagan is Koenker's studentized form, computed by hand.** An auxiliary
least-squares fit, with intercept, of the squared residuals on the FITTED
VALUES — one regressor, not the design matrix — through the same fitting
routine as everything else, so a constant fitted vector is handled by the rank
walk (the regressor is dropped, `R²_aux` is 0, `LM` is 0). When the auxiliary
response has zero total sum of squares, `R²_aux` is 0/0 and `bp_p` is `NaN`;
`bp_triggered` is false there, per the spec's finiteness guard. `bp_p` is never
`None`.

**Observations per term is counted from the covariate structure.** One per
continuous covariate, levels-minus-one per categorical covariate with levels
counted after the complete-case filter, and an aliased column still contributes
its share. The count is not taken from the fitted model's rank. For the shipped
case that gives 4 terms and 80 observations per term.

**VIF.** Continuous covariates only, `None` rather than an empty map when there
are fewer than two, keyed by the bare column name, and `float("inf")` when the
auxiliary `R²` is non-finite or has reached 1. A duplicated covariate is the
case that produces the infinity, and it survives as a float, not a string. The
shipped case has one continuous covariate, so `vif` is `None` there.

**Level ordering and the locale-aware sort.** The spec pins R's locale-aware
collation under `en_CA.UTF-8`, not a code-point sort. Setting the process
`LC_COLLATE` from inside a library module would be a global side effect on
every other Path B module in the same interpreter, so the collation is instead
a pure key: case-insensitive primary, lowercase-before-uppercase secondary.
That reproduces the ordering the spec gives as its worked example — `B` and `a`
resolve to `a`, where a code-point sort gives `B` — and it was checked against
this machine's actual `en_CA.UTF-8` collation, which sorts `['B','a','A','b']`
to `['a','A','b','B']`, the same answer the key gives. It does not reproduce
glibc's ignoring of punctuation and spaces at the primary level. No level in
this case mixes case or carries leading punctuation, so nothing in the shipped
comparison depends on either difference; a future case whose levels do should
be re-verified against R rather than trusted to this key, exactly as the spec
warns.

**The reference-level fallback is resolved here, not delegated.** `io.py`'s
`treatment_dummies` carries its own fallback, but it tie-breaks with Python's
`sorted()`, a code-point sort, which contradicts the spec's locale rule for
mixed-case levels — on `c("B","B","a","a")` the helper picks `B` where the spec
requires `a`. The reference is therefore resolved in this module first (the
declared level when it survives the filter, otherwise the most frequent, ties
going to the level that sorts first under the collation above) and handed to
`treatment_dummies` already decided, so the helper still builds the indicator
columns and still reports the resolved reference but its own fallback branch is
never reached. The shared file was not modified. All three of the spec's worked
examples were checked: `B`/`a` gives `a`, `zebra`/`apple` gives `apple`,
`c`/`a`/`b` gives `a`. The helper's non-reference levels come back code-point
sorted and are re-sorted with the collation key before they enter the design.

**The increment.** Coerced to a float; anything that is not a single finite
number strictly greater than zero falls back to 1 — a missing entry, a
non-numeric string, zero, a negative, an infinity, and a bool, which Python
would otherwise happily read as 1 or 0. When `k` is 1 the column is untouched;
otherwise the column is divided before fitting, never the coefficient after.
Verified that dividing the column multiplies the estimate by `k` and leaves the
p-value alone.

One measured caveat on the invariance the spec asserts. Rescaling changes the
conditioning of the design, so the fit is invariant only to floating point.
Every reported coefficient, the R² pair, `bp_p`, the Cook's count and the
observations-per-term ratio come back bit-identical with and without the
increment; `shapiro_p` moves in the thirteenth significant figure (0.6988619402711549
against 0.698861940271216 on a 300-row probe). That is arithmetic noise from a
differently scaled design, roughly eight orders of magnitude inside the
comparator's own exact-tier tolerance, and not a modelling difference.

**Outcome parse failure.** A non-blank outcome cell that does not parse raises
`ValueError` from `fit_linear`. The spec says the app produces an error and no
analysis at all; an exception is the Python analogue. The exact message is not
part of the contract.

**Boundaries deliberately not implemented.** The spec states four app-level
stops — residual degrees of freedom below 10, R's essentially-perfect-fit test,
zero outcome variance, a categorical covariate left with one level — and states
that Path B is not asked to reproduce them. None is implemented. `fit_linear`
fits and reports in those situations rather than refusing.

**Not implemented, by instruction.** The display strings, the methods
paragraph, the advisory sentences' wording and the citation paragraph are all
rendering, not statistics; this module returns values and the comparator does
its own formatting. The numerical-warning fallback is explicitly outside the
contract and is not emitted.

## Shape

`terms`, `unadjusted`, `n`, `n_dropped`, `r_squared` and `adj_r_squared` are at
the top level; `shapiro_p` and `bp_p` are inside `diagnostics`, which carries
exactly the eleven keys `INTERFACES.md` lists and no others. There is no
`n_event`. `n`, `n_dropped` and `cooks_influential` are Python ints; every other
number is a float at full precision. The module rounds nothing anywhere.

## Concerns

None blocking. The two open readings worth a second pair of eyes are the
pre-filter numeric classification and the fallback reference resolution being
taken out of the shared helper's hands; both are argued above, and neither
changes any value in the shipped case.

# Path B decisions — the advisory `diagnostics` blocks

Choices made while extending `validate/logistic.py` and `validate/cox.py` with
the `diagnostics` key. Everything here is a judgement call the specs left open,
or a place where two readings were available and one was picked. Where the spec
is explicit, it was simply followed and is not restated.

## Shared

**What counts as a continuous covariate.** Neither Diagnostics section defines
how an implementation decides that `arm` is categorical and `age` is not, but
both diagnostics blocks depend on the answer (logistic's VIF runs on continuous
covariates only; Cox's `zph_terms` groups columns by covariate). Reused the
rule `_covariate_matrix` was already coding by: **a covariate is categorical
exactly when the caller declared a reference level for it in `ref_levels`.**
Chosen so the diagnostics can never disagree with the design matrix about what
a covariate is — a data-sniffing rule (say, "non-numeric column") could classify
a numerically-coded factor one way for the fit and the other way for the VIF.
Factored out as `_is_categorical`.

**A classification disagreement with Figura cannot be a diagnostics-only
finding.** Worth writing down because the rule above looks like a private
diagnostics decision and is not. `_is_categorical` reads the same `ref_levels`
that `_covariate_matrix` codes the design by, so if Path B ever classified a
covariate differently from Figura, the DESIGN MATRIX would differ first: a
covariate treated as categorical contributes `levels − 1` dummy columns named
`<cov><level>`, one treated as continuous contributes a single column named
`<cov>`. Different columns mean different **term keys** and different
**estimates**, so the disagreement surfaces on the exact tier as
MISSING_QUANTITY (a term one path has and the other does not) and DEFECT
(estimates that do not match), and on the display tier as rows that cannot be
keyed — every one of them loud, and every one of them ahead of any VIF or
`zph_terms` difference in the same run. There is no reachable state in which the
two paths agree on the whole ratio table and disagree only about a diagnostic's
covariate classification. Consequence for reading the scorecard: a VIF or
`zph_terms` finding standing ALONE is evidence about the diagnostic's own
arithmetic, never about which covariates went into it.

**Term counts come from the design matrix, not from a recount.** Both specs
define EPV's denominator as "one per continuous covariate, (levels − 1) per
categorical, levels counted after the [complete-case / Population] filter".
That is exactly the joint design matrix's column count, so both modules use
`X_full.shape[1]` rather than re-deriving it. One source of truth; a covariate
whose levels collapse under the filter cannot be counted twice.

**`_covariate_groups` (new, in `logistic.py`).** Cox's `zph_terms` is keyed by
covariate while `U` and `S` are indexed by coefficient, so the mapping between
them had to exist somewhere. Added beside `_covariate_matrix` and built from the
same `treatment_dummies` call, so the column names and their order are the same
object's output rather than a second guess at it. Placed in `logistic.py`
because `cox.py` already imports the design-matrix builder from there.

**No rounding anywhere.** Every float is returned as computed. The two spec'd
display formats (`%.2f`, `%.1f`) belong to the renderer, not to these modules.

## logistic.py

**`_c_statistic` now returns `None` when a class is empty**, per the spec and
INTERFACES.md. Previously it divided by `n1 * n0 == 0`. This is the one change
to an existing function's behaviour; the input that reaches it is one no green
test exercises (every fixture has both classes), and the finite-case arithmetic
is untouched. `scipy.stats.rankdata`'s default tie rule already IS the midrank
rule the spec pins, so the tie handling needed no change.

**Top-level `c_statistic` kept.** INTERFACES.md marks it superseded but says an
older caller reads it. It returns the identical object as
`diagnostics["c_statistic"]`, so the two can never drift.

**VIF is computed on the UNSCALED columns.** The spec notes that dividing a
column by a positive constant leaves `R²_j` unchanged, so VIF must be
increment-invariant. Both readings satisfy that in exact arithmetic, but only
the unscaled one satisfies it *bit-for-bit* in floating point — reading the
rescaled design-matrix columns would make `vif` differ in the last few ulps
between an `increments={}` call and an `increments={"age": 10}` call on the same
data. So `_vif` re-reads `to_numeric(kept[cov])` from the kept rows rather than
taking the design matrix's columns. Invariance by construction, not by luck.

**`R² >= 1` → infinity, and the duplicate case reaches it by arithmetic, not by
a special case.** For an exactly duplicated covariate the OLS residuals are
~1e-14, so `RSS/TSS` is ~1e-30 and `1 - RSS/TSS` evaluates to exactly `1.0` in
double precision — the spec's `R²_j >= 1` branch fires on its own. No epsilon
threshold was introduced to force it. `TSS == 0` (a constant covariate) returns
`nan` from `_r_squared`, which the same non-finite branch turns into infinity.

**Cook's distance uses `pinv` for `(X'WX)⁻¹`.** The spec writes the hat matrix
with a literal inverse. Used the pseudo-inverse so a rank-deficient design
(a duplicated covariate — a case the tests construct) yields the hat values it
still has instead of raising. On a full-rank design the two agree to machine
precision. Non-finite `D_i` is excluded from the count, never counted as
influential, exactly as the spec (and R's `cooks.distance.glm`) require.

**What `pinv` does and does not buy, corrected.** An earlier version of this
file said `pinv` "handles" the duplicated-covariate case. It does not — it makes
it SILENT. `pinv` stops the linear algebra from raising; it does not make the
rank-deficient design a fitted model. Two consequences were being papered over,
and both are now fixed rather than tolerated:

**Cook's `p` is the design's RANK, not its column count.** The spec defines `p`
as "the number of ESTIMATED coefficients **including the intercept**" — wording
that can only differ from the column count on a rank-deficient design, so the
spec itself contemplates a design column with no coefficient behind it. The
implementation was passing `design.shape[1]`. On the suite's own
duplicated-covariate fixture (`age` + an exact copy, 60 rows) that divides every
`D_i` by 3 where the spec's reading divides by 2, and reports **5** influential
rows where the rank reading reports **7**. Two independent checks say 2 is the
right divisor: `trace(H) = 2.000000000000004` on that design (the hat matrix has
exactly `rank` units of leverage to distribute, so a divisor of 3 is
inconsistent with the leverage the same formula uses), and dropping the
duplicated column outright — which changes neither the fit, the fitted
probabilities, nor the hat matrix — gives an unambiguously full-rank design with
`p = 2` and the same 7 rows over the 4/n cut-off. Full-rank designs are
untouched: rank == column count there, so the L1 count pinned against R's
`cooks.distance` is unmoved. The rank comes from `_estimated_columns`, the same
scan that decides which cells get a coefficient, so the divisor and the
unreportable cells can never disagree about it.

**An ALIASED column has no estimate, so `separation_caution` fires on it.** With
`pinv`, statsmodels hands back the minimum-norm solution — for a duplicated
covariate, the effect split evenly between the two identical columns, both cells
finite, both passing the spec's Reportability rule, `separation_caution` False.
That is the one fixture in the suite built to provoke the caution, and it was
silent on it. The spec's own text resolves this without appeal to any other
implementation: the Cook's clause establishes that a rank-deficient design
estimates fewer coefficients than it has columns; Reportability requires "the
estimate and both CI bounds are finite"; a coefficient that was never estimated
has no finite estimate; so the cell is unreportable and separation clause 1
fires. The displayed sentence names this exact case in as many words —
covariates that "duplicate information already carried by another covariate, so
those odds ratios are not reliably estimated by standard logistic regression".
So the SPEC was left alone and the implementation was made to satisfy it:
`_fit_one` marks an aliased column's cell `_NOT_ESTIMATED` (est/se/lo/hi/p all
nan), and clause 1 then fires through the module's single `reportable`
definition rather than through a second, parallel rule.

WHICH column is the aliased one is decided by `_estimated_columns`, scanning
left to right — the intercept first, then the covariate blocks in
`_covariate_matrix`'s order — and rejecting a column that adds no rank to the
columns already accepted. Deterministic, and it leaves the FIRST occurrence of a
duplicated covariate estimated instead of picking arbitrarily between two
identical columns. The univariable fits are each full rank on their own, so both
duplicates still get an unadjusted odds ratio; only the joint column is aliased,
which is the honest reading of what the joint model could and could not
estimate.

**Cook's `p` and EPV's `terms` are deliberately different counts.** EPV's
denominator is spelled out by the spec as a counting recipe over the covariates
("one per continuous covariate, and (number of levels − 1) per categorical"),
which is the design's column count and stays `X_full.shape[1]`. Cook's `p` is
"the number of estimated coefficients", which is the rank. They coincide on
every full-rank design; only the rank-deficient fixture separates them, and
there the spec asks for different numbers in the two places.

**Separation clause 1 reads the `est`/`lo`/`hi` cells through the module's own
`reportable`**, over `terms` and `unadjusted` both, rather than a second copy of
the bound. One definition of reportability in the module.

**Separation clause 2's threshold is the shipped one.** `10 * eps` with `eps`
written out as `2.220446049250313e-16`, not tuned. The spec is explicit that on
a separated fixture R's own IRLS stops four orders of magnitude above this and
clause 1 is what actually fires; the acceptance test agrees. Left alone.

## cox.py

**The PH score test is implemented from the spec's formula in numpy.** No
survival library was used for it. lifelines'
`proportional_hazard_test` defaults to `time_transform="rank"` and implements
the older residual-versus-time correlation form, so neither its default nor its
`km` setting is the test the spec pins.

**`g(t) = 1 − S(t⁻)` is left-continuous as written**, so `g` is 0 at the first
event time, and centring subtracts the mean of `g` over the **event rows** —
i.e. a time with `d` tied events contributes `d` times to that mean, not once.
Worth noting why this matters: `U` is invariant to the centring (the
uncentred sum is the score at `β̂`, which is zero), but `I_βθ` and `I_θθ` are
not, so the centring is doing all its work inside `S`.

**`V(t)` reuses the Efron construction directly.** For `d` tied events the
`k`-th sub-term's totals are formed as `s_r − (k/d)·s_d` — the risk-set total
minus the fraction of the tied rows' contribution — which is algebraically the
"each tied row gets weight `1 − k/d`" rule the spec states, computed in `O(d)`
rather than by rebuilding the weighted risk set `d` times.

**`_zph` resolves a covariate's columns BY NAME.** `zph_terms` is keyed by
covariate while `U` and `S` are indexed by coefficient, so the mapping has to be
built somewhere. It was built by walking `groups` and accumulating widths, which
is correct only while `_covariate_matrix` and `_covariate_groups` emit blocks in
the same order — an invariant that held by construction but that no code
enforced and a comment could not. `_zph` now requires the design-matrix
DATAFRAME and takes positions from `X.columns.get_loc`, and raises `ValueError`
when a covariate names a column the design does not have (`fit_cox`'s existing
except clause turns that into `zph_global_p = None`, the honest "could not be
computed", rather than a test run on a wrong submatrix). Pinned by a test that
hands `_zph` a `groups` dict in reverse insertion order: the positional version
gave `age` the `armTreated` column and vice versa, and because those two
p-values differ by 15x on the fixture, the swap reads as a wrong number rather
than as a wash.

**`S_jj` is the submatrix of `S`.** Implemented as `S[np.ix_(idx, idx)]` and
then inverted, per the spec's emphasis, not as a block of `S⁻¹`. Both the
per-term and the global statistic are solved with `np.linalg.solve` rather than
by forming an explicit inverse — same quantity, better conditioned. The
single-column case falls out of the quadratic form as `U_j²/S_jj` with no
separate branch, so a categorical covariate on 2+ df takes the identical code
path.

**Accuracy achieved, and where the residual actually came from.** An earlier
version of this section got the causal story wrong in two ways. Both are
corrected below, and the correction turned out to be worth five orders of
magnitude, so `_FIT_OPTIONS` was tightened rather than merely re-described.

*The starting position.* Against the R constants in `tests/test_cox.py`, with
the then-shipped `_FIT_OPTIONS` (`precision=1e-11, r_precision=1e-13,
max_steps=1000`): global `4.03e-8`, `arm` `4.72e-8`, `age` `2.04e-9` relative —
25x to 500x inside the required rel 1e-6, but not the floor.

*Correction 1: those options were not what kept the PH residual small.* The old
text said "the existing tightened `_FIT_OPTIONS` are what keep it this small".
Measured: on the zph fixture, lifelines' DEFAULTS and the shipped options
converge to a **bit-identical** `β̂` (`-0.28016353589302817`,
`0.037594872265116215` under both), so all three zph p-values are bit-identical
too — `0.027503792805580213` either way. The tightening bought that fixture
**nothing**. Where it does earn its keep is the tied-times fixture in
`test_cox.py`: there `β̂` sits near zero (`-0.00485`), so the same absolute
convergence slack reads as a large relative error — default `2.5e-3` relative on
the coefficient, shipped `5.2e-10`, a ~5-million-fold improvement (equivalently
`1.2e-5` → `2.5e-12` relative on `est = exp(coef)`, which is the framing
`test_cox.py`'s own comment uses). So: keep the tightening, for the reason the
tied-times test states, and not for the PH test.

*Correction 2: relative in, absolute out.* The old sentence "perturbing `β̂` by
1e-6 relative moves the global p by 1.6e-8" compared a relative input to an
absolute output as if they were the same kind of number. Re-measured, with the
units named: perturbing `β̂` by **1e-6 relative** moves the global p by
**1.57e-8 absolute** (= 5.69e-7 relative), and the response is linear over the
range that matters (1e-7 → 1.57e-9 absolute, 1e-8 → 1.57e-10). The
back-inference itself was sound: the observed **1.11e-9 absolute** gap therefore
implies a `β̂` difference of roughly 7e-8 relative, and the directly measured
`β̂` difference between the old options and full convergence is 1.10e-7 / 5.40e-8
on the two coefficients. The residual was lifelines' Newton-Raphson stopping
point, not the score test — the same solver-convergence effect INTERFACES.md's
numerical-precision note describes.

*The free margin, claimed.* Because correction 1 showed the PH residual was
pure convergence slack that the old options never touched, there was headroom
sitting unused. `_FIT_OPTIONS` is now `precision=1e-15, r_precision=1e-17,
max_steps=5000`. Measured, all four ways:

| | old (1e-11/1e-13/1000) | new (1e-15/1e-17/5000) |
|---|---|---|
| zph global p, rel vs R | 4.03e-8 | **2.93e-13** |
| zph `arm` p, rel vs R | 4.72e-8 | **4.44e-13** |
| zph `age` p, rel vs R | 2.04e-9 | **6.51e-14** |
| tied-times fixture (est/se/p/lo/hi) | rel 2.5e-12 … 5.4e-12 | **bit-identical to old** |
| hard-PH-violation fixture (crossing hazards, global p ≈ 1.9e-15) | `ph_violation` True | `ph_violation` True |
| joint fit runtime, 20-fit mean | 6.9 ms | 7.2 ms |

The tied-times fixture is bit-for-bit unchanged (it was already at its floor),
the hard-violation fixture's verdict is unchanged (its p moves in the 7th
significant figure of a 1.9e-15 number, which is noise at that magnitude), the
runtime difference is inside measurement noise, and the full suite is green. Five
orders of magnitude for nothing, so it was taken rather than documented as a
floor.

**`ph_violation` is a HARD `< 0.05` boolean, and that is why the residual is
worth chasing.** `zph_global_p is not None and zph_global_p < 0.05` — no
tolerance band, no hysteresis. Every other diagnostic comparison in the
comparator judges a number against a tolerance, but this one collapses to a bit,
so a case whose true global p sits within the numerical residual of 0.05 flips
`ph_violation` — and with it the CAUTION sentence's presence, which is a
DIAGNOSTIC_MISMATCH rather than a near-miss on a value. At the old 4e-8 relative
residual that window is about ±2e-9 wide around p = 0.05; at 2.9e-13 it is about
±1.5e-14. No fixture in the suite sits in either window (the zph fixture's
global p is 0.0275, the hard-violation fixture's is 1.9e-15), but a future case
could, and the width of that window is exactly what the tightening bought.

**`zph_global_p is None` is a narrow branch.** Only a genuinely uncomputable
test returns `None` — a singular `I_ββ` or `S`, or no events at all — caught as
`LinAlgError`/`ValueError`/`ZeroDivisionError` around the whole test, with
`zph_terms` then `{}`. A large p-value is a result, not a failure, and is
returned as-is. `ph_violation` is `False` (not `None`) when the test did not
run, since it is contracted as a `bool`.

**Cox's EPV is `n_event / terms` — deliberately NOT logistic's
`min(n_event, n - n_event) / terms`.** The two modules report different
quantities under one key name, per both specs; the divergence is intentional
and is the thing the two suites' EPV tests probe from opposite sides.

**Cox's `separation_caution` has only clause 1.** `spec/cox-adjusted.md` gives
the unreportable-cell rule and no fitted-probability analogue, so none was
invented. The spec's "known sensitivity" (the app forcing a cell unreportable
because `coxph` emitted a warning) is explicitly outside the contract and is
not implemented.

**`_fit_one` now returns `(terms, cph)`.** The score test needs the joint fit's
`β̂`, which was previously discarded. Internal signature only — the univariable
loop ignores the second element and `fit_cox`'s return shape is unchanged apart
from the new `diagnostics` key.

## Verification

`cd python && ../.venv/bin/python -m pytest tests -q` → **36 passed**. The 19
tests that were green before the change are still green and none of them was
modified; the 17 that were red on `KeyError: 'diagnostics'` now pass.

**Second review round** (Cook's rank, the aliased-column caution, the
`_FIT_OPTIONS` tightening, `_zph`'s name-resolved offsets): **83 passed** in
`python/tests`, **201 passed** in `compare/tests`, `make -C stats-validation
test` exit 0, and `make -C stats-validation clean all` still **325 compared /
30 findings** with `results/findings.json` and `results/scorecard.html`
**byte-identical to the previous run**.

The one Path B number that moved on a shipped case is worth naming, since it
moved without changing any verdict: `cox-adjusted`'s UNADJUSTED column shifted
by rel 1.0e-8 … 2.3e-8 on est/se/lo/hi (and 1.5e-5 on `age`'s p, which is
4.13e-8, where relative error on a tail probability amplifies), all of it the
univariable fits converging further. The JOINT fit's `terms` and the whole
`diagnostics` block are bit-identical, because that fit was already at its floor
under the old options. Nothing in the comparator sees the shift:
`figura-exact.json` for cox carries the ADJUSTED terms only, so the unadjusted
column has no exact tier at all and is judged on its rendered 2-dp cells, which
a rel-2e-8 move cannot touch.

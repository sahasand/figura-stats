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

**`S_jj` is the submatrix of `S`.** Implemented as `S[np.ix_(idx, idx)]` and
then inverted, per the spec's emphasis, not as a block of `S⁻¹`. Both the
per-term and the global statistic are solved with `np.linalg.solve` rather than
by forming an explicit inverse — same quantity, better conditioned. The
single-column case falls out of the quadratic form as `U_j²/S_jj` with no
separate branch, so a categorical covariate on 2+ df takes the identical code
path.

**Accuracy achieved.** Against the R constants in `tests/test_cox.py`: global
`4.0e-8`, `arm` `4.7e-8`, `age` `2.0e-9` relative — 25x to 500x inside the
required rel 1e-6. Measured the source of the residual gap rather than assuming
it: perturbing `β̂` by 1e-6 relative moves the global p by 1.6e-8, so the
observed 1.1e-9 absolute gap corresponds to a `β̂` difference of roughly 7e-8
relative. It is lifelines' Newton-Raphson stopping point, not the score test —
the same solver-convergence effect INTERFACES.md's numerical-precision note
describes. The existing tightened `_FIT_OPTIONS` are what keep it this small.

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

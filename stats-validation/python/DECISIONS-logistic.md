# Decisions

## Environment fix (not an interpretation choice, but required to run at all)

The pinned `.venv` combination of `scipy==1.16.1` and `statsmodels==0.14.4` is
broken for `import statsmodels.api`: that module eagerly imports
`statsmodels.distributions.discrete`, which does `from scipy._lib._util import
_lazywhere` — a private name scipy 1.16 no longer exports. `logistic.py`
sidesteps this by importing the needed pieces directly from their submodules
(`statsmodels.genmod.generalized_linear_model.GLM`,
`statsmodels.genmod.families.Binomial`, `statsmodels.tools.add_constant`)
instead of `statsmodels.api`. No package versions were changed and nothing
outside this directory was consulted; this is a pure import-path workaround
around a pre-existing incompatibility in the provided environment.

## Interpretation choices

The spec and INTERFACES.md were silent on a handful of mechanical details.
Choices made, all standard/conservative:

1. **"Blank" cell.** Defined as an actual missing value (`NaN`/`None`) or the
   literal empty string `""`. Whitespace-only strings are *not* treated as
   blank — the spec says "empty string", not "blank after stripping", and
   `test_literal_NA_is_an_ordinary_value_not_missing` confirms the spec wants
   a narrow, literal reading of what counts as missing.

2. **Numeric-equality check in `code_event`.** Parsed both the cell and
   `event_value` with Python's `float()`; if both parse and are numerically
   equal, it's an event. This matches `"1.0"` equalling `"1"` in the test
   suite. Values that don't parse as floats simply fail the numeric check and
   fall through to the string-equality / non-event path — no error raised.

3. **Tie-break for "most frequent remaining level" (reference fallback).**
   When the declared reference level is absent, the spec says to use the
   most frequent remaining level but doesn't say what to do on a count tie.
   Resolved ties alphabetically (smallest level string wins), for a
   deterministic, reproducible result.

4. **Default increment for continuous covariates.** `fit_logistic`'s
   `increments` dict only needs entries for covariates that should be
   rescaled (e.g. `{"age": 10}` per the spec's "report age per 10 units").
   Any continuous covariate absent from `increments` is used at its raw
   scale (increment = 1), matching the `test_increment_rescales_the_odds_ratio`
   test, which calls `fit_logistic(..., {})` and expects per-1-unit
   coefficients as the baseline.

5. **`c_statistic` is computed from the multivariable (adjusted) model.**
   `fit_logistic`'s return dict has a single top-level `c_statistic`, not one
   per model, and the spec discusses discrimination once, after both models
   are introduced. Used the joint model's in-sample fitted probabilities
   against the observed outcome.

6. **C-statistic via rank sums, average-rank tie handling.** Implemented the
   "normalised Mann-Whitney statistic" directly as
   `(sum of ranks of events − n_event·(n_event+1)/2) / (n_event·n_nonevent)`,
   using `scipy.stats.rankdata`'s default average-rank method for ties. This
   is the standard closed-form identity between the Mann-Whitney U statistic
   and the AUC/C-statistic, and it handles tied predicted probabilities
   (e.g. from a single categorical covariate) sensibly without needing a
   separate rank-correlation library call.

7. **Wald p-value uses the exact normal quantile, not 1.96.** The spec pins
   the literal constant 1.96 for the *confidence interval* only ("the literal
   constant 1.96, not the exact normal quantile") and separately calls the
   p-value a "two-sided Wald p-value" with no such override. Used
   statsmodels' GLM z-test p-values (`result.pvalues`), which are the exact
   two-sided normal Wald p-values `2·(1 − Φ(|z|))`. `test_ci_uses_the_literal
   _1_96` and `test_increment_rescales_the_odds_ratio`'s
   p-value-invariance-to-rescaling check both pass under this reading.

8. **Perfect separation is not special-cased.** When a covariate perfectly
   predicts the outcome, statsmodels' GLM fit still converges (with a
   `PerfectSeparationWarning`) to a very large coefficient and standard
   error; the resulting CI bound overflows to `inf` in `exp()`. This is left
   to surface naturally and is exactly what `reportable()` is meant to catch
   (non-finite bound → not reportable), per
   `test_perfect_separation_is_not_reportable`. No try/except or
   separation-detection logic was added — the spec's reportability rule
   already covers this case at the reporting layer, and the module never
   suppresses or fabricates a result.

9. **`complete_cases` / population filtering happens once, on the raw
   (pre-coding) columns**, using the outcome column plus all covariates
   passed to `fit_logistic`, before any dummy-coding or numeric coercion.
   The same filtered analysis set (`n`, `n_event`, `n_dropped`) is then reused
   for both the univariable and the multivariable fits, since the spec's
   Population section applies to "the outcome or any of the three
   covariates" once, not per-model.

## Final test run

```
$ cd python && ../.venv/bin/python -m pytest tests -v
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-8.3.4, pluggy-1.6.0
rootdir: .../pathb-logistic/python
collecting ... collected 14 items

tests/test_io.py::test_code_event_matches_string PASSED                  [  7%]
tests/test_io.py::test_blank_outcome_is_missing_not_a_non_event PASSED   [ 14%]
tests/test_io.py::test_numeric_equality_also_counts PASSED               [ 21%]
tests/test_io.py::test_complete_cases_drops_blank_strings PASSED         [ 28%]
tests/test_io.py::test_literal_NA_is_an_ordinary_value_not_missing PASSED [ 35%]
tests/test_io.py::test_declared_reference_absent_falls_back_to_most_frequent PASSED [ 42%]
tests/test_io.py::test_treatment_dummies_reference_first_rest_alphabetical PASSED [ 50%]
tests/test_logistic.py::test_recovers_a_known_odds_ratio PASSED          [ 57%]
tests/test_logistic.py::test_ci_uses_the_literal_1_96 PASSED             [ 64%]
tests/test_logistic.py::test_increment_rescales_the_odds_ratio PASSED    [ 71%]
tests/test_logistic.py::test_counts_are_reported PASSED                  [ 78%]
tests/test_logistic.py::test_unadjusted_and_adjusted_both_present PASSED [ 85%]
tests/test_logistic.py::test_perfect_separation_is_not_reportable PASSED [ 92%]
tests/test_logistic.py::test_reportable_accepts_a_normal_cell PASSED     [100%]

=============================== warnings summary ===============================
tests/test_logistic.py::test_perfect_separation_is_not_reportable (x2)
  .../statsmodels/genmod/generalized_linear_model.py:1342: PerfectSeparationWarning:
  Perfect separation or prediction detected, parameter may not be identified

tests/test_logistic.py::test_perfect_separation_is_not_reportable (x2)
  validate/logistic.py:35: RuntimeWarning: overflow encountered in exp

======================== 14 passed, 4 warnings in 0.88s ========================
```

Both warnings are expected consequences of decision 8 above (the perfect-
separation test deliberately drives a coefficient to overflow) and do not
indicate a defect.

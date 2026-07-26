# Analysis spec: cox-adjusted

Input: `stats-validation/cases/cox-adjusted/data.csv`.

## Population
Complete cases on the time column and the covariates only. Drop any row
where the time or either of the two covariates is missing or an empty
string. Report the number dropped as `n_dropped`. A blank cell is missing.
The literal string `NA` is an ordinary value, not missing — do not treat it
as NA.

The status column is deliberately excluded from this completeness check —
see Status coding below for why a blank status cell is never dropped.

A time value that is blank is missing, per the rule above. A time value that
is present but does not parse as a number, or parses to a negative number,
cannot be used as a survival time; treat that row as missing too — drop it
and count it in the same dropped total.

## Status coding
The status column is `status`. A row is an event when its value equals the
string `"Death"`. If both the cell and `"Death"` parse as numbers, numeric
equality also counts. **Everything else is censored at its recorded time
value, including a blank cell.** A blank status cell is not missing and is
not dropped from the analysis — it is coded as censored, exactly like any
other non-event value.

This is a deliberate departure from logistic regression's outcome coding,
where a blank outcome cell IS treated as missing and the row IS dropped. The
two figures code a blank event-like cell differently on purpose, to match
the app's real behavior: `R/cox.R`'s status derivation never maps a blank
cell to missing before testing it against the event value, so `"" == "Death"`
evaluates to false and the row survives as censored; `R/logistic.R`'s
outcome derivation explicitly rewrites a blank cell to missing before the
same comparison, so the row is dropped. Implement Cox's rule as written
above — do not port logistic's blank-is-missing outcome handling here.

## Covariates
- `arm` — categorical, reference level `"Standard care"`.
- `age` — continuous, reported per 1 unit (no rescaling).

If a declared reference level is absent from the data after complete-case
filtering, the reference level is instead the most frequent remaining level.

Categorical covariates use treatment contrasts: the reference level first,
remaining levels in alphabetical order.

## Models
Cox proportional-hazards regression, partial likelihood, **Efron** handling
of tied event times.
1. For each covariate, a univariable Cox model of the time/status pair on
   that covariate alone. This gives the unadjusted hazard ratio.
2. One multivariable Cox model of the time/status pair on both covariates
   jointly. This gives the adjusted hazard ratios.

## Reported quantities
Per covariate term: hazard ratio = exp(coefficient); 95% CI =
exp(coefficient ± 1.96 × standard error) — the literal constant 1.96, not the
exact normal quantile; two-sided Wald p-value.

Also report: n analysed, number of events, and number of rows dropped.

## Reportability
A hazard ratio cell is reported only when the estimate and both CI bounds are
finite and the interval lies within [1e-6, 1e6]. Otherwise the cell reads
"not reliably estimated".

## Display
`%.2f (%.2f–%.2f, p=%.3f)` with an en-dash separator; when p < 0.001 the
p-part reads `p<0.001`.

## Diagnostics (advisory)

Figura appends advisory sentences to the methods text. **Not one of them gates
a fit or changes a reported estimate.** They are nonetheless published claims
about the model, so they are validated: the numeric ones by value, and every one
of them by whether the sentence FIRES AT ALL.

Report them in a `diagnostics` block; `stats-validation/python/INTERFACES.md`
pins the key names and types. All of them describe the JOINT (adjusted) model
fitted on the rows the Population section keeps.

### Proportional hazards — `zph_global_p`, `zph_terms`, `ph_violation`

The proportional-hazards assumption is checked with **scaled Schoenfeld
residuals**: a score test of `θ = 0` in the extended model

    λ(t | x) = λ0(t) · exp( x'β + g(t) · x'θ )

in which every coefficient is allowed to drift with transformed time,
`β_j(t) = β_j + θ_j · g(t)`. Evaluated at the fitted `β̂` with `θ = 0`, so no
second model is fitted. This is R `survival`'s modern (3.x) `cox.zph`, which is
a proper score test — **not** the older residual-versus-time correlation test
that some implementations still ship under the same name, and not a refit.

**The time transform is pinned.** `g(t) = 1 − S(t⁻)`, where `S` is the
Kaplan–Meier estimate of the survivor function of the observed times, computed
**over the whole sample with no covariates and no strata**, evaluated
LEFT-CONTINUOUSLY (the value just before `t`; `S(t⁻) = 1` at or before the
first event time). `g` is then centred by subtracting the mean of `g` over the
**event rows only**.

This is R's `cox.zph` default, verified in the installed package's own
signature: `cox.zph(fit, transform = "km", terms = TRUE, singledf = FALSE,
global = TRUE)`. **Other implementations default differently** — lifelines'
`proportional_hazard_test` defaults to `time_transform="rank"`, and its test is
the correlation form, not this score test. Neither default will reproduce the
numbers below; the transform and the test are both part of this spec, not of
whatever a library happens to do.

The statistic, written out. Let `p` be the number of model coefficients, and
for each distinct event time `t` let `V(t)` be the risk-set covariance matrix
of the covariates used by the partial likelihood at `t` — the **same Efron
construction the model itself was fitted with**, i.e. for `d` tied events at
`t`, `V(t)` is the sum over `k = 0 … d−1` of the covariance of `x` under the
risk-set weights that give each of the `d` tied rows weight `1 − k/d`. Let

    U = Σ_t  g(t) · ( Σ_{i tied-events at t} x_i  −  Σ_{k=0..d−1} x̄_k(t) )

be the `p`-vector of scaled Schoenfeld residual sums (`x̄_k(t)` is the
risk-set weighted covariate mean of the k-th Efron sub-term), and

    I_ββ = Σ_t V(t)      I_βθ = Σ_t g(t) · V(t)      I_θθ = Σ_t g(t)² · V(t)

the blocks of the extended model's information at `(β̂, 0)`. The score for `β`
is zero there, so the test reduces to the Schur complement

    S = I_θθ − I_βθ' · I_ββ⁻¹ · I_βθ

- **Per covariate**: `chisq_j = U_j² / S_jj`, on 1 degree of freedom for a
  single-column term.
- **Global**: `chisq = U' · S⁻¹ · U`, on `p` degrees of freedom.
- Each p-value is the **upper** tail of the chi-square distribution on those
  degrees of freedom.

`zph_terms` is keyed by **covariate (model term), not by coefficient level**:
a categorical covariate with more than two levels contributes ONE row, on
(levels − 1) degrees of freedom, with `S` and `U` restricted to that covariate's
whole block of columns. `zph_global_p` is `None` if the test cannot be computed
at all (the app wraps it and prints nothing in that case).

`ph_violation` is true when `zph_global_p` < 0.05.

Displayed, whenever `zph_global_p` exists:

    " The proportional-hazards assumption was assessed with scaled Schoenfeld
      residuals (global %s)."

with `%s` rendered by the same p-rule as the table cells — `p<0.001` below
0.001, else `sprintf("p=%.3f", p)`. When `ph_violation` is true, this is
followed in the same sentence by

    " CAUTION: the assumption may not hold (global p<0.05); consider
      stratification, a time-varying effect, or statistical review before
      interpreting these hazard ratios."

The per-covariate p-values are computed and reported but are **not displayed**
in the methods text; only the global one is.

### Events per variable — `epv`, `epv_triggered`

Let `terms` be the number of model coefficients: one per continuous covariate,
and (number of levels − 1) per categorical covariate, levels counted after the
Population filter. Then

    epv = n_event / terms

Note this is the **event count**, not logistic regression's smaller-outcome-group
`min(n_event, n − n_event)` — Cox regression's information comes from events
alone. `epv_triggered` is true when `epv` < 10.

Displayed, when triggered, with **no number in it**:

    " CAUTION: fewer than 10 events per model term (EPV < 10); the adjusted
      estimates may be unstable."

### Separation / collinearity caution — `separation_caution`

True when any displayed cell in **either** column — unadjusted or adjusted —
fails the Reportability rule above. Both columns are inspected because an
unadjusted cell can run away while the adjusted one stays inside the bound, and
the reverse happens too.

Displayed, when triggered:

    " CAUTION: separation or severe collinearity was detected — one or more
      covariates either predict the event (near-)perfectly or duplicate
      information already carried by another covariate, so those hazard ratios
      are not reliably estimated by standard Cox regression and are omitted
      from the forest plot. Consider collapsing sparse categories, dropping or
      combining a redundant covariate, or rescaling one on a clinically
      meaningful unit, and seek statistical review."

**Known sensitivity.** The app additionally forces a cell to
"not reliably estimated" when the `coxph` fit that produced it emitted any
warning at all (e.g. "Loglik converged before variable …; coefficient may be
infinite"), which is an implementation's warning catalogue rather than a
statistical rule and is therefore NOT part of this spec. No shipped case
triggers it. If a future case does, the caution can fire on the app side with
every interval still inside the reportable bound, and that is this known
sensitivity — rule it out before escalating a DIAGNOSTIC_MISMATCH.

### Which tier judges which diagnostic

The exported `.R` script contains the literal call `cox.zph(fit)` on the joint
model it fitted, so the proportional-hazards p-values **have a full-precision
Path A value** (re-evaluating the script's own printed expression on the
script's own `fit`) and are compared at rel 1e-6 / abs 1e-9, plus a script-tier
check that the exported script's global p re-renders the sentence the screen
showed.

The exported script computes **no EPV and no separation check**. Those two have
**no exact-tier Path A value**, and none is manufactured: they are judged
against the DISPLAY tier only — the sentence Figura actually printed.

## Known display nuance
The app's own on-screen table computes its displayed 95% CI by calling R's
`confint()` generic on the fitted joint `coxph` object. The `survival`
package defines no `confint.coxph` method, so this call falls through to
`stats::confint.default`, which uses the exact normal quantile
`qnorm(0.975) = 1.959963985` — not the literal constant `1.96` that this
spec's Reported quantities section requires. Logistic regression has no
such gap: `R/logistic.R`'s displayed cell is hand-computed with the literal
1.96 directly, so its on-screen CI already matches this spec's rule
exactly.

The app's displayed Cox CI and this spec's literal-1.96 rule therefore
differ by roughly `(1.959963985 - 1.96) / 1.96 ≈ 1.8e-5` relative on the z
multiplier itself — almost always invisible after rounding to 2 decimal
places, but occasionally close enough to a `.xx5` rounding boundary that a
bound computed with one z constant rounds to a different displayed digit
than the same bound computed with the other. Do not resolve this by
changing the literal 1.96 anywhere in this pipeline (this spec, the
harvester, or an independent implementation) — 1.96 is the pinned
convention that keeps the exact tier and the script tier self-consistent.
A Cox-only single-digit CI-bound mismatch that lands exactly at a rounding
boundary is this known nuance, not a defect; rule it out before escalating
one.

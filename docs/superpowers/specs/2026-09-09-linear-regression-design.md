# Linear regression — design

**Date:** 2026-09-09
**Status:** Approved for planning
**Related:** `2026-07-17-cox-regression-design.md` (the Table-3 pattern), `docs/superpowers/plans/2026-07-17-logistic-regression.md` (the module this clones), `2026-07-16-r-code-export-design.md`, `docs/superpowers/plans/2026-07-25-statistical-validation.md`, `stats-validation/README.md`

## What this is

A seventh guided analysis: univariable + multivariable **linear regression** for a
continuous outcome, producing the clinical "Table 3" — each covariate's **unadjusted**
coefficient (from its own single-covariate fit) beside its **adjusted** coefficient (from
the joint model), each with a 95% CI and p-value — plus an adjusted-coefficient forest
plot and a two-plot residual diagnostics panel. It completes the regression trio: Cox for
time-to-event, logistic for binary, linear for continuous (length of stay, blood pressure
change, a lab value).

It is the logistic module with a continuous outcome. Structurally the only substitutions
are `glm(family = binomial)` → `lm`, OR → β (no exponentiation, linear axis, null at 0),
and the logistic diagnostics (separation, EPV, C-statistic) → the linear ones (residual
normality, heteroscedasticity, R²). Everything else — prep, reference levels, per-increment
rescaling, the table shape, the forest, the script builder, the guided shell config, the
analyze form — is reused or cloned.

The shipped change includes its **statistical-validation case** (decided in brainstorming):
the public validation page must cover all seven analyses at ship time, not six of seven.

## Non-goals (YAGNI)

- **No outcome transform option.** A skewed outcome is *reported* (residual normality and
  heteroscedasticity advisories), never modelled around. A log-transform checkbox, with its
  percent-change interpretation and its own validation surface, is deferred.
- No robust (HC) standard errors, no interaction terms, no polynomial or spline terms, no
  variable selection, no mixed models. The user picks the covariates; every one enters the
  joint model.
- No new R package. `lm`, `confint`, `summary.lm`, `cooks.distance`, `shapiro.test` are
  base `stats`; the Breusch–Pagan statistic is hand-rolled (no `lmtest`, no `car`). No
  `cowplot`: the plots are separate SVGs stacked in the `svg` field, as logistic already does.
- No second validation case (`linear-dirty`). The CSV-reading parity contract lives in
  `R/script.R` and is figure-independent; `logistic-dirty` already guards it.
- No change to the shared shell, export toolbar, or `modelform.js` semantics beyond one
  readiness option (below).

## Architecture — the parallel keys (per CLAUDE.md "Adding a figure or analysis")

Figure key is **`linear`** everywhere; R function is **`fig_linear`**; nav label is exactly
**`Linear regression`**; landing-page slug is **`linear-regression`**.

1. **`R/linear.R`** — `fig_linear(spec)` returning `list(svg=, text=, code=)`. Reuses
   `.svg_string`, `%||%` (`R/dispatch.R`), `.esc`, `.numeric_col`, `.char_col`
   (`R/summarize.R`), `.km_palette` (`R/km.R`), `.fig_theme` (`R/themes.R`), and the
   `R/script.R` builders (`.script_assemble`, `.script_dep`, `.script_fun`, `.with_citation`).
   Helpers are `.linear_*`; where a logistic helper is a pure function of its inputs and
   would be copied verbatim (term label, most-frequent level, increment parsing, numeric
   detection), the plan may either call the existing `.logistic_*` helper or lift it into a
   shared `.model_*` helper — but never a third copy of the same body.
2. **`R/dispatch.R`** — `linear = fig_linear(spec),` in the `switch`.
3. **`web/worker.js`** — `"linear.R"` in the boot-time fetch loop. **No** `EXTRA_PACKAGES`
   entry (base `stats` + `ggplot2` + `svglite` only).
4. **`web/guided/linear/`** — `guided-linear.js` (`createGuidedShell({...})` →
   `renderGuidedLinear`), `content.js`, `analyze-form.js`, `spec.js`, `demo.js`,
   `demo-data.js` (generated). `web/app.js` imports and registers `linear: renderGuidedLinear`;
   `web/index.html` gets `<button data-figure="linear">` after the logistic button;
   `web/sw.js` bumps `CACHE`.
5. **`DESCRIPTION`** — unchanged (no new import).
6. **`scripts/pages/registry.mjs`** — one `PAGES` entry (`linear-regression`), then
   `npm run build:examples && npm run build:pages`. `fig_linear` appends
   `.with_citation(text, "ggplot2")` with the same `pkgs` it hands `.script_assemble`.

Plus the validation harness keys (section "Statistical validation" below).

## Spec contract

```json
{
  "figure": "linear",
  "data": [ { "los": "6", "arm": "Treated", "age": "64", "stage": "II" }, ... ],
  "roles": { "outcome": "los", "covariates": ["arm", "age", "stage"] },
  "options": {
    "ref_levels": { "arm": "Standard care", "stage": "I" },
    "increments": { "age": 10 },
    "source_filename": "trial.csv",
    "source_roles": { "outcome": "los", "covariates": ["arm", "age", "stage"] }
  }
}
```

- `roles.outcome` — one column; must parse numeric in every non-blank cell (coerced with the
  suppress-then-clear-`stop()` pattern of `.numeric_col`, so a text outcome yields
  "Outcome column 'x' must be numeric", not a leaked coercion warning). There is **no
  `event_value`**.
- `roles.covariates` — one or more columns; each is numeric (every non-blank cell parses)
  or categorical, exactly as logistic decides.
- `options.ref_levels` — per categorical covariate; default and fallback is the most
  frequent level after complete-case filtering, as in logistic.
- `options.increments` — per numeric covariate; positive finite number, default 1; the
  column is divided by k in prep so the coefficient reads "per k units". Rescaling changes
  β and its CI, not the p-value.
- `options.source_filename` present → the script reads the file; absent (demo) → the script
  embeds the data. `source_roles` carries the user's real headers for the script.
- Only mapped columns cross to the worker (no-egress).

## Statistical output — `fig_linear(spec)`

**Prep** (`.linear_prep`) mirrors `.logistic_prep` minus outcome coding: build the working
frame `.y` + covariates, complete cases, count dropped rows, rescale numeric covariates,
factor + relevel categoricals. Hard stops, in this order:

1. No rows / no covariates / no outcome / column not found (same messages as logistic).
2. Outcome not numeric (message names the column).
3. Residual degrees of freedom `n − (1 + number of model terms) < 10` → "Too few
   observations (n = %d) for %d model term(s); at least 10 residual degrees of freedom are
   needed." Checked before covariate structure, for the same reason logistic checks event
   count first.
4. A categorical covariate with one level after complete cases.
5. Outcome constant (zero variance) → "The outcome has no variation after removing
   missing values."
6. After the fits: a **perfect fit** — the joint model's residual variance below
   `summary.lm`'s own "essentially perfect fit" threshold, tested before any `summary()`
   call so that warning can never leak → "The outcome is an exact function of the
   covariates (a perfect fit), so standard errors and p-values are undefined; check for a
   covariate that duplicates or derives from the outcome." The joint model nests every
   univariable model, so checking it alone suffices.

**Fits** (`.linear_fits`): one `stats::lm(.y ~ \`cl\`, data = df)` per covariate and the
joint `stats::lm(.y ~ \`a\` + \`b\` + …, data = df)`, each wrapped by a `withCallingHandlers`
that captures warnings without muffling the fit's meaning (as `.logistic_fit_one` does). No
`suppressWarnings` around `lm`.

**Estimates.** β = coefficient; CI = `stats::confint(fit, level = 0.95)` (t-based, the
standard for `lm`); p = the t-test p-value from `summary(fit)$coefficients`. **Not
exponentiated.**

**Cell format.** `"%.2f (%.2f to %.2f, p)"` — e.g. `−1.23 (−2.10 to −0.36, p=0.006)`,
`p<0.001` below 0.001. The range separator is the word **"to"**, not the en dash logistic
uses: a coefficient can be negative, and "−2.10–−0.36" is unreadable. The minus sign is
R's ASCII hyphen-minus as `sprintf` emits it; the Python formatter mirrors that byte for
byte. A cell reads **"not reliably estimated"** when the coefficient is `NA` (an aliased
column — R drops it from the joint fit) or any of β, lower, upper is non-finite.

**Rows** (`.linear_rows`): the logistic row model — a `"%s (reference: %s)"` header row
with blank cells per categorical covariate, then one row per non-reference level, and one
row per numeric covariate labelled `"%s (per %g units)"` / `"%s (per 1 unit)"`. The reference header row's two effect cells read **"0 (reference)"** in the HTML table only;
in the TSV they stay blank, because the validation parser requires a reference header row
to carry empty cells (logistic leaves both blank).

**Table** (`.linear_table_html`): three columns — `Characteristic`,
`Unadjusted β (95% CI, p)`, `Adjusted β (95% CI, p)` — inside
`<div class="summary-output"><div class="table-scroll">…</div>…</div>`, so the galley-proof
styling applies with no CSS change. The `text` field's TSV uses the same three headers.

**Methods text** (the paragraph after the TSV), in this order:

1. Lead sentence. Multivariable: "Multivariable linear regression (n = %d) of %s adjusted
   for %s. Unadjusted coefficients are from single-covariate models; adjusted coefficients
   are from the joint model (R² = %.3f, adjusted R² = %.3f)." Single covariate: the
   univariable wording logistic uses ("No adjustment was made … the unadjusted and
   adjusted columns report the same model"), with the same R² clause.
2. **Aliased / collinear CAUTION** — fires when any joint-model coefficient is `NA`:
   " CAUTION: one or more covariates were dropped from the adjusted model because they are
   linear combinations of others (their cells read \"not reliably estimated\"); remove a
   redundant variable."
3. **Fit-warning fallback** — the logistic `.logistic_other_warn` pattern: any captured
   `lm` warning not already explained gets one advisory naming the warning text.
4. **Observations per term** — `n / number of model terms < 10`: " CAUTION: about %.1f
   observations per model term (fewer than 10); the adjusted estimates may be unstable and
   are best treated as exploratory."
5. **Residual normality** — `stats::shapiro.test(stats::resid(jfit))` when
   `3 ≤ n ≤ 5000`; if p < 0.05: " Residuals depart from normality (Shapiro–Wilk p=%s);
   with n = %d %s." where the tail is "the coefficient estimates are unaffected, and the confidence intervals are usually robust to this unless the residual plots also show non-constant variance or influential points" for n ≥ 30 and "the confidence intervals may be unreliable; consider transforming the outcome or a non-parametric comparison" for n < 30.
   Neither tail is a verdict: sample size alone does not validate an interval, so the
   large-n tail defers to the variance and influence checks. Outside the size window the
   sentence is omitted (never a stop).
6. **Heteroscedasticity** — Koenker's studentized Breusch–Pagan, hand-rolled: regress
   `resid(jfit)^2` on `fitted(jfit)`, statistic `LM = n · R²` of that auxiliary fit,
   p from `stats::pchisq(LM, df = 1, lower.tail = FALSE)`. If p < 0.05: " CAUTION:
   residual variance is not constant across fitted values (Breusch–Pagan p=%s); the
   standard errors may be misleading, and robust standard errors or an outcome transform
   are worth considering."
7. **VIF > 5** among continuous covariates — reused logic and wording from logistic
   (including the "effectively infinite" case).
8. **Cook's distance > 4/n** — reused wording from logistic.
9. Dropped-row note, then `.with_citation(…, "ggplot2")`.

p-values in advisories print as `p<0.001` or `p=%.3f`, the same rule as the cells.

## Figures (the `svg` field, after the table)

1. **Adjusted-β forest** (`.linear_forest_svg`): one point + 95% CI per non-reference level
   and per numeric term; **linear** x-axis; dashed vertical rule at **0**; y labels
   `"cov: level"` / `"cov (per k units)"` in the table's order; `geom_errorbar(orientation =
   "y")`, `linewidth`, `.fig_theme`, `.km_palette` colour. Inclusion mirrors the cell rule:
   a term whose cell is "not reliably estimated" is omitted from the forest, and a forest
   with no reportable term is omitted entirely (with the table still rendered). Same
   proportion-band height rule as logistic.
2. **Diagnostics pair** (`.linear_diagnostics_svg`), two separate SVGs stacked:
   - *Residuals vs fitted* — `geom_point` of `resid(jfit)` on `fitted(jfit)` with a dashed
     horizontal rule at 0. **No loess smoother** (a `geom_smooth` on a small n warns, and
     the manuscript reader wants the raw scatter).
   - *Normal Q-Q of residuals* — `stat_qq` + `stat_qq_line` on `resid(jfit)`.
   Both carry a one-line italic caption telling the reader what a healthy plot looks like
   ("points scattered evenly around 0 with no funnel", "points along the line"). Each is
   rendered with `.svg_string` at the app's standard width.

The diagnostics are always drawn from the **joint** model.

## Downloadable `.R` script (`.linear_script`)

Mirrors `.logistic_script`: header via `.script_assemble("Linear regression", spec, cols,
"ggplot2", body)`; data section via `.script_data`; prep block reproducing `.linear_prep`
(complete cases, `relevel`, division by increments) with the user's real headers from
`source_roles`; then

```r
m_uni <- lm(.y ~ `arm`, data = dat)                # one per covariate
fit   <- lm(.y ~ `arm` + `age` + `stage`, data = dat)
cbind(coef(fit), confint(fit))
summary(fit)                                       # R², adjusted R², p-values
if (nrow(dat) >= 3 && nrow(dat) <= 5000) shapiro.test(resid(fit))   # same guard as the app
# Breusch–Pagan (Koenker): the same statistic the app reported
aux <- lm(resid(fit)^2 ~ fitted(fit)); bp <- nrow(dat) * summary(aux)$r.squared
pchisq(bp, df = 1, lower.tail = FALSE)
cooks.distance(fit)
# plot(fit, which = 1:2)                      # residuals vs fitted; normal Q-Q
```

followed by an equivalent ggplot2 forest. The model calls are deparsed from the exact
expressions `fig_linear` evaluated, so the script's numbers match the screen by
construction; the header keeps the default "exact calls" honesty line. `plot(fit, which =
1:2)` is emitted **commented out**: a sourced script must not open a graphics device, so
the line is left for the user to uncomment interactively rather than run automatically.

## Web UI

**Guided shell config** (`guided-linear.js`): `title: "Linear regression"`,
`hashPrefix: "linear"`, the six pieces beside it — a direct clone of `guided-logistic.js`.

**Understand** (`content.js`, exports `UNDERSTAND_SECTIONS` for the landing page): what a
coefficient means (a difference in the outcome's own units — "per 10 years", "vs
reference"); why unadjusted and adjusted differ (confounding, with the demo's own story);
what the two diagnostics plots are for and when to worry; what the app checks and what it
does not (no transform, no robust SEs); how to write it up.

**Try an example** (`demo.js`, `demo-data.js`, `data-raw/linear-demo-generator.R`): a
frozen synthetic trial with a **continuous outcome** and a confounder so that the unadjusted
and adjusted arm effects differ visibly — e.g. hospital length of stay (days, right-skewed
enough to be realistic but not enough to trip the advisories on the default selection)
against `arm` (Standard care / Treated), `age` (years; demo reports per 10), and `stage`
(I/II/III), where older, later-stage patients were more often Treated. The experiment
controls are the covariate checkboxes (as logistic), so unticking `age` and `stage` shows
the confounded unadjusted-only story. The demo spec pins `ref_levels` and `increments`
explicitly and omits `source_filename` (script embeds the data). The generator writes
`demo-data.js` **and** the fixture CSV the R tests and the validation case share.

**Analyze your data** (`analyze-form.js`): the logistic form with the event-value picker
**removed** and the outcome dropdown **filtered to numeric columns**; the form rejects an
outcome that is also selected as a covariate via `renderReadiness`'s overlap check
(identical to logistic); per-categorical reference-level dropdowns and
per-numeric increment inputs reused unchanged (same ids pattern: `#linear-config`,
`#linear-refs`, `#linear-increments`, `#linear-render`); dropped-row preview via
`countDroppedRows`. Readiness comes from `modelform.js`'s `renderReadiness` with a new
option **`requireEventValue: false`** (default `true`, so cox and logistic are untouched);
the linear form passes its own `messages.roles` wording ("Choose a numeric outcome column
and at least one covariate…"). Session semantics (remembered selections surviving a
re-upload) come from `retainedSelection`/`reconcileRefLevels` as they do for logistic.

**Spec builder** (`spec.js`): `buildLinearSpec(table, roles, refLevels, increments,
options)` — pure, only mapped columns, `source_roles` without an `event` key.

**Text export**: the toolbar stays `.tsv` for the table + methods and `.R` for the script,
via the existing `data-r-code` contract; nothing in `export.js` changes.

**Copy**: `web/index.html` meta description and `web/about/` (regenerated by `build:pages`)
mention linear regression alongside the other six. The About "what it connects to" text is
unchanged (no new network calls).

## Statistical validation (`stats-validation/`)

One case, **`linear-confounding`**, sharing the demo's data (`cases/linear-confounding/
data.csv` + `case.json` with `"figure": "linear"`, the demo's roles/options, and a **new
display kind `"display": { "kind": "coef_table" }`**. The existing `ratio_table` branch is
bound to the ratio scale end to end — the harvest exponentiates, the cell format uses an
en dash, reportability is the [1e-6, 1e6] window, and it compares an `n_event` count — so
a coefficient table is a sibling kind, not a reuse. It shares the ratio branch's
machinery through keyword parameters (count keys, cell formatter, reportability rule,
cell parser) with the ratio defaults untouched, so cox and logistic cannot move.)
`exact_targets`: `adjusted_beta`, `adjusted_ci`, `adjusted_p`, `n`, `n_dropped`,
`r_squared`, `adj_r_squared`, `shapiro_p`, `bp_p`, `shapiro_note`, `bp_note`,
`obs_per_term_note`, `vif_note`, `cooks_note`, `aliased_note`. R², adjusted R², the
Shapiro–Wilk p and the Breusch–Pagan p have an exact tier because the exported script
computes and prints each of them; VIF, Cook's, observations-per-term and the aliased
caution are judged on the display tier, as logistic's VIF/Cook's/EPV are.

Touch points, each of which currently enumerates figures or kinds by name:

- `Makefile` `CASES`; `harness/build-spec.mjs` (a `linear` builder over
  `buildLinearSpec`); `harness/run-script.R` (`harvest_linear`, registered in
  `HARVESTERS`); `python/validate/cli.py` (a `linear` branch — no event value);
  `build_scorecard.py`'s `ANALYSES`, `KIND_TIERS`, `KIND_NOT_COMPARED`;
  `compare/compare.py` — `coef_table` in `KIND_HANDLERS`, `linear` in
  `DIAGNOSTIC_HANDLERS` and `DIAGNOSTIC_TARGETS`, the new targets in `TARGET_QUANTITIES`;
  `e2e/compare-text.mjs` and `e2e/webr-parity.spec.js` (`coef_table` → the same
  three-column text comparison, a `table` readiness element).
- `spec/linear-confounding.md` — transcribed from `R/linear.R` **by an agent with source
  access**, in the section shape of `spec/logistic-confounding.md` (cell reading,
  population, covariates, models, reported quantities, reportability, display, citation
  paragraph not compared, each diagnostic with its trigger and which tier judges it).
- `python/validate/linear.py` + `python/tests/test_linear.py` + `python/DECISIONS-linear.md`
  — written **by an agent that never reads `R/`**, from the spec and `INTERFACES.md` only,
  against expected values computed in R and pasted into the test file by the spec author.
  The Path B independence rule in CLAUDE.md is absolute here.
- `e2e/webr-parity.spec.js` — a `driveLinear` driver (logistic's minus the event select)
  and a `{ id: "linear-confounding", nav: /linear regression/i, kind: "linear" }` row; the
  spec's case-list assertion then requires it.
- `expected-findings.json` via `make gate-update`, committed with the change that moved
  the evidence. A finding that appears must be dispositioned in `issues/`, never tuned away.

Then `make -C stats-validation all` (expected non-zero: `logistic-dirty` still publishes),
`gate`, `freshness`, and — hand-run before release — `webr`, followed by the rebuild that
publishes its result. Every `web/` commit in this work regenerates `web/validation.html`
via `make all`, per CLAUDE.md.

## Export

No change. PNG/SVG/TSV/`.R` handlers read `#preview`/`#stats` at click time; the forest and
the two diagnostics plots export per-panel like logistic's forest.

## Testing

- **R** (`tests/testthat/test-linear.R`, `devtools::test()`, WARN 0): prep errors (text
  outcome, too few residual df, constant outcome, one-level covariate, column not found);
  coefficients/CI/p equal `lm` + `confint` on the fixture; increment rescaling changes β
  and CI but not p; reference-level override; aliased covariate → "not reliably estimated"
  + CAUTION; each advisory fires on a constructed dataset and stays silent on the demo;
  dropped-row count; TSV/HTML structure; forest omits unreliable terms; script contains the
  exact `lm` calls and the embedded data when `source_filename` is absent; citation sentence
  present with `ggplot2`; `render_figure` round-trip through JSON.
- **JS unit** (appended to `test:unit` in the same commit): `spec.test.mjs`
  (`buildLinearSpec` shape, only mapped columns, no `event` in `source_roles`),
  `analyze-form.test.mjs` (numeric-only outcome filtering, increment normalisation,
  readiness with `requireEventValue: false`), `demo.test.mjs`, plus `modelform.test.mjs`
  gains the new option's cases and the unchanged default for cox/logistic.
- **Playwright** (`tests/e2e/linear-guided.spec.js`): demo renders a table with the three
  headers and three SVGs; analyze path uploads the example CSV, maps roles, sets an
  increment, renders; `smoke.spec.js` counts seven nav items.
- **Pages**: `build.test.mjs` passes with the new registry entry; `build:examples` re-rendered.
- **Validation**: `make -C stats-validation test`, `all`, `gate`, `freshness` green
  (modulo the standing `logistic-dirty` disposition); `webr` run before release.

## Acceptance

1. Seventh nav item "Linear regression" opens the three-stage shell; the demo renders the
   Table-3, forest, and two diagnostics plots with no `EXTRA_PACKAGES` download.
2. Uploading a CSV with a numeric outcome and mixed covariates produces coefficients that
   match `lm` + `confint` in native R to display precision; a non-numeric outcome yields a
   readable error.
3. Each advisory sentence fires on its constructed trigger and is absent otherwise; no
   advisory blocks a fit.
4. The downloaded `.R` script reproduces the table's numbers in a native R session.
5. `/linear-regression/` landing page and sitemap exist; `build.test.mjs` passes.
6. `stats-validation` covers `linear-confounding` on all tiers; the public
   `web/validation.html` lists seven analyses; the webR gate has been run and published.
7. R suite `[ FAIL 0 | WARN 0 ]`, `npm run test:unit` green, e2e green, CI green.

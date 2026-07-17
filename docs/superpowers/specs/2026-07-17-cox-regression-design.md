# Cox proportional-hazards regression — design

**Date:** 2026-07-17
**Status:** Approved for planning
**Related:** `2026-07-16-km-analyze-form-design.md`, `2026-07-16-group-comparison-design.md`, `2026-07-16-r-code-export-design.md`

## What this is

A fifth guided analysis: multivariable **Cox proportional-hazards regression**, producing
the clinical "Table 3" — each covariate's **unadjusted** hazard ratio (from its own
univariable Cox fit) beside its **adjusted** HR (from the joint model) — plus a forest
plot of the adjusted HRs. It completes the survival workflow that Kaplan–Meier began: KM
answers "do the curves differ?", Cox answers "by how much, after adjusting for the other
variables?".

It is a **new sidebar item**, not an extension of KM (decided in brainstorming). KM stays
a single-purpose curve tool; Cox gets its own three-stage guided shell with room for the
multivariable covariate UI.

## Non-goals (YAGNI)

- No stratified Cox, time-varying covariates, frailty, or competing-risks models. A PH
  violation is **reported, not modelled around** — the user is pointed to statistical review.
- No interaction terms, splines, or variable selection (stepwise/LASSO). The user picks the
  covariates; every one they pick enters the joint model.
- No carry-over of roles from a completed KM run (the "hybrid" placement option was declined).
- No new R package. `survival` is already an `EXTRA_PACKAGES` dependency (KM loads it);
  `cox.zph`, `coxph`, `Surv` all live there. No `cowplot` (no risk table to compose).

## Architecture — five parallel keys (per CLAUDE.md "Adding a figure")

1. **`R/cox.R`** — `fig_cox(spec)` returning `list(svg=, text=, code=)`. Reuses `.svg_string`,
   `%||%`, `.numeric_col`, `.char_col`, `.km_palette`, `.fig_theme`, and the `R/script.R`
   builders. No redefinition of shared helpers.
2. **`R/dispatch.R`** — add `cox = fig_cox(spec),` to the `switch`.
3. **`web/worker.js`** — add `"cox.R"` to the boot-time fetch loop; add `cox: ["survival"]`
   to `EXTRA_PACKAGES` and a `cox:` entry to `EXTRA_PACKAGES_MESSAGE`.
4. **`web/guided/cox/`** — a `createGuidedShell({...})` config in `guided-cox.js` plus
   `content.js` / `analyze-form.js` / `spec.js` / `demo.js` / `demo-data.js` beside it,
   mirroring `web/guided/groupcompare/`. `web/app.js` imports `renderGuidedCox` and registers
   `cox:` in the form registry; `web/index.html` adds a `<button data-figure="cox">` under the
   "Statistical analyses" nav group.
5. **`DESCRIPTION`** — no change (survival already in Imports).

## Spec contract

```
{ figure: "cox",
  data: [ {<time col>, <status col>, <covariate cols…>}, … ],   // only mapped columns cross
  roles: { time, status, covariates: [col, …] },
  options: {
    event_value,                       // user-confirmed status value that marks the event
    ref_levels: { <col>: <value>, … }, // reference level per CATEGORICAL covariate (optional)
    source_filename,                   // upload only; demo omits it → script embeds data
    source_roles                       // upload only; real column names + event coding for the .R script
  } }
```

Numeric covariates carry no `ref_levels` entry (per-unit HR). The demo spec omits
`source_filename`/`source_roles`, matching how KM/GroupCompare demos embed data.

## Statistical output — `fig_cox(spec)`

**Prep.** Build a working frame: `time` via `.numeric_col`, `status` recoded to 0/1 in R
from `options$event_value` (string compare, with numeric-equality fallback — the exact
pattern KM's analyze form and `.km_script` use so a numeric status column still codes
events), each covariate coerced by detected type (numeric → `.numeric_col`; categorical →
`.char_col` then `factor`, releveled to `ref_levels[[col]]` when provided, else the most
frequent level as reference). Drop rows with any NA in time/status/used covariates
(complete-case, the `coxph` default); count and report the drop.

**Fitting (expression-first, deparsed into the `.R` script).**
- One `coxph(Surv(time, status) ~ covariate)` per covariate → unadjusted column.
- One `coxph(Surv(time, status) ~ x1 + x2 + …)` joint fit → adjusted column.
- Formulas are built as expressions with explicit bindings (the KM/GroupCompare/Explore
  pattern) and `deparse`d verbatim into the downloadable script, so the user's reproduced
  numbers match by construction.

**`svg` field — HTML `<table>` + forest-plot SVG** (the `fig_summary` precedent: the `svg`
field may carry HTML; the UI injects it identically). One row per covariate *level*
(reference level marked `1 (reference)`, non-reference and numeric rows carry n, events,
unadjusted HR (95% CI, p), adjusted HR (95% CI, p)). Beneath it a **forest plot** of the
adjusted HRs: point + 95% CI on a log x-axis, dashed vertical rule at HR = 1,
`geom_errorbar(orientation = "y")` (never `geom_errorbarh`), `linewidth` (never `size`),
`.km_palette`, `.fig_theme`. Wrapped in the same `<div class="summary-output"><div
class="table-scroll">…</div>…</div>` structure Summary uses so narrow viewports scroll the
table rather than clipping it.

**`text` field — methods + results paragraph.** "Multivariable Cox proportional-hazards
regression (n = N, E events) adjusted for X, Y, Z. [Largest adjusted effect sentence with
HR + CI.] The proportional-hazards assumption was assessed with scaled Schoenfeld residuals
(global p = …)." Plus a copy-pasteable TSV of the table body above the sentence, matching
how Summary's `text` leads with TSV then the methods line.

**PH diagnostics — always computed, never blocking.** `cox.zph()` on the joint fit; the
global and per-covariate p-values feed the `text` sentence. A global p < 0.05 appends a
**non-blocking caution line** to `text` (the stats stay fully visible) naming the
assumption and pointing to stratification / time-varying effects / statistical review —
never an error, never a hidden result.

**Guardrails (readable `stop()`, surfaced by `render_figure`'s `tryCatch`).**
- No covariate selected → "Select at least one covariate."
- Fewer than ~10 events → too few events to fit a reliable model (states the count).
- A covariate constant after NA-drop (single level / zero variance) → names the column.
- Events-per-variable < 10 → **non-blocking** caution in `text` (EPV rule), not a stop.
- `coxph` non-convergence / infinite coefficient (complete separation): captured in R with
  `withCallingHandlers` + `muffleWarning` (the exact KM technique — the worker blanket-
  suppresses warnings, so an unreliable HR must be caught here or it ships silently). The
  affected HR reads "not reliably estimated (likely separation)" instead of a bogus number.

**Warning hygiene (CLAUDE.md WARN-0 gate).** `suppressWarnings()` wraps only library calls
that legitimately warn; model fitting uses `withCallingHandlers`/`muffleWarning` so a real
convergence warning is inspected and re-reported, never leaked to the gate and never
silently swallowed.

## Downloadable `.R` script (`.cox_script`, in `R/cox.R`, using `R/script.R` builders)

Header via `.script_header`; data section via `.script_data` (embeds demo data, or reads
the user's file by name for uploads). Body: the event-recode prep (reading the user's real
column names + event value from `source_roles`, exactly as `.km_script` does), the releveling
of categorical covariates, the deparsed univariable and joint `coxph` calls, `cox.zph(joint)`,
and an equivalent forest-plot ggplot section. Honesty line: statistical calls are the exact
calls the app ran; the plot is an equivalent. Packages: `survival`, `ggplot2`.

## Web UI

**Analyze form** (`web/guided/cox/analyze-form.js`) — the KM analyze-form pattern:
progressive disclosure (heading + privacy line + CSV help + file input; the config stays
hidden until a parse succeeds, re-hides on failure). After a successful parse:
- `renderColumnPicker` roles: `time` (numeric), `status` (any), `covariates`
  (`any`, `multiple: true` — `columnpicker.js` already supports `multiple`/returns an array
  and yields `null` until ≥1 chosen).
- The KM event-value picker (`distinctValues` on the chosen status column, "— choose —"
  placeholder, "all other values count as censored" hint), gated into the Render button's
  enabled state alongside a non-empty covariate selection.
- A **reference-level area** that renders one "reference for {col}" dropdown per selected
  covariate whose detected type is categorical (numeric covariates get none), each defaulting
  to that column's most frequent value. Re-renders when the covariate selection changes.
- Render builds the spec via `buildCoxSpec` and calls `onSubmit`; a dropped-rows note mirrors KM.

**`spec.js`** — `buildCoxSpec(table, roles, eventValue, refLevels, options)` projects rows to
the mapped columns only (no-egress), passes `roles.covariates` through, recodes nothing in JS
(status recoding stays in R, as KM does), and attaches `source_roles` for the script. Exports
`distinctValues` reuse (import from KM's `spec.js` or re-export — decided in planning).

**`demo.js` / `demo-data.js`** — frozen synthetic dataset from a new
`data-raw/cox-demo-generator.R`: a two-arm survival scenario (like KM) plus 2–3 baseline
covariates (treatment arm, age, an ordinal stage/ECOG) engineered so the adjusted HR for the
arm differs visibly from its unadjusted HR — the teaching point of the Understand stage.
Deterministic (`set.seed`), byte-reproducible, versioned, writing both a fixture CSV under
`tests/testthat/fixtures/` and the generated `demo-data.js`, exactly like the other three
generators.

**`content.js`** — Understand copy: what adjustment buys you (confounding, unadjusted vs
adjusted), when Cox is appropriate vs KM, the PH assumption in plain language and how the
tool checks it, per-unit vs per-category HR interpretation, and a "seek statistical review"
section (PH violation, separation, small EPV). `EXAMPLE_INTRO_HTML` describes the demo.
The demo "experiments" (shell `renderExperiments`) let the user toggle which covariates enter
the model to watch the arm's adjusted HR move.

**`guided-cox.js`** — the `createGuidedShell({...})` config wiring the above; no `liveRender`
(matches KM/GroupCompare, which re-fit on an explicit Render/experiment change).

## Export

Cox's `text` is TSV+methods and its `svg` is an HTML table + plot, so the existing
`export-ui.js` handling (Copy/`.tsv`, PNG/SVG driven by `#preview`/`#stats` at click time)
covers it with no change. The `.R` button is enabled because `out.code` is present — the same
path as KM/Summary/GroupCompare (not the Explore `textExportDescriptor` special-case).

## Testing

- **R (`tests/testthat/test-cox.R`)** — univariable+adjusted columns present; a known-effect
  synthetic fit recovers an HR within tolerance (hand-computed constant, the GroupCompare
  pattern); reference row labelled `1 (reference)`; `ref_levels` override changes the reference;
  PH caution line appears on an engineered violation and is absent otherwise; too-few-events and
  constant-covariate errors fire; separation yields the "not reliably estimated" text, not a
  number; `svg` contains both `<table` and `<svg`; WARN 0.
- **R (`tests/testthat/test-cox-demo.R`)** — the frozen demo spec fits and the adjusted arm HR
  sits in the engineered band; fixture CSV matches `demo-data.js` row count.
- **R (`tests/testthat/test-script.R`)** — a Cox `code` script parses and, when sourced against
  the fixture, reproduces the app's HRs (the existing script round-trip pattern).
- **JS unit** — `spec.test.mjs`: `buildCoxSpec` projects only mapped columns, passes covariates
  and `ref_levels`, sets `source_roles`; most-frequent-level default helper is correct.
- **E2E (`tests/e2e/cox-guided.spec.js`)** — Understand renders; Run Example fits and shows a
  table + forest plot + `.R` enabled; the analyze flow (upload fixture → map roles → pick event
  value → pick covariates → set a reference → Render) produces the adjusted table. Runs after
  `rm -rf web/R && cp -R R web/R`.

## Acceptance

- Nav shows Cox regression under "Statistical analyses"; the four existing analyses are
  unchanged.
- `Rscript -e 'devtools::test()'` → `[ FAIL 0 | WARN 0 | … ]`.
- `npm run test:unit` green; full Playwright suite green after the `web/R` copy.
- A Summary-only user still never downloads `survival` (lazy install unchanged); a KM user who
  then opens Cox pays nothing extra (survival already resident, single-flight guard).
- No data egress: only mapped columns enter `data`; the `.R` script travels the filename, never
  the contents.

# Trim to Guided Analyses (KM + Summary Statistics) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the six plain-form analyses (forest, consort, groupcompare, correlation, roc, regression) so the app ships exactly its two guided analyses — Kaplan-Meier and Summary statistics — with the pre-trim state preserved under a git tag.

**Architecture:** Hard delete across every layer (nav, form registry, `web/forms/`, R sources + dispatch switch, worker fetch list + lazy packages, DESCRIPTION, R tests, e2e), preceded by the one real code change: relocating the shared `%||%` helper out of the doomed `R/forest.R` into `R/dispatch.R`. The two keepers are byte-identical apart from that relocation.

**Tech Stack:** git, R package (testthat/devtools), vanilla JS, Playwright.

**Spec:** `docs/superpowers/specs/2026-07-15-trim-to-guided-analyses-design.md` (product-owner decision; dependency audit already done — the spec's keep/remove tables are authoritative).

## Global Constraints

- **Tag before deleting**: `git tag -a pre-trim-8-analyses -m "Last commit with all 8 analyses"` must exist and point at the last 8-analysis commit before any removal commit lands.
- **Keepers unchanged**: `R/km.R`, `R/summarize.R`, `R/themes.R`, `web/forms/km.js` + `km.test.mjs`, all `web/guided/**`, `web/lib/**` are byte-identical after the trim (only `R/dispatch.R` gains `%||%`; `R/forest.R` and five other R files are deleted).
- **WARN 0 hard gate**: `Rscript -e 'devtools::test()'` (never `testthat::test_file()`) must end `[ FAIL 0 | WARN 0 | ... ]` after every task.
- `web/R/` is a gitignored build copy: `rm -rf web/R && cp -R R web/R` before serve/e2e, and before dangling-reference greps over `web/`.
- No behavior changes to keepers; no removal of shared machinery (guided shell, session state, `csv.js`, `columnpicker.js`, form-registry mechanism, `.svg_string`).
- DESCRIPTION Imports become exactly: `ggplot2, survival, cowplot, svglite, jsonlite, grDevices, stats` (knitr has zero callers in `R/`; pROC/gtsummary/broom/broom.helpers belong to removed analyses).
- Worker boot package set becomes exactly `["ggplot2", "svglite", "jsonlite"]`; `EXTRA_PACKAGES` becomes exactly `{ km: ["survival", "cowplot"] }`; fetch list exactly `["dispatch.R", "summarize.R", "km.R", "themes.R"]`.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## File Structure

| File | Action |
|---|---|
| `R/dispatch.R` | Gains `%||%`; switch shrinks to `summary`/`km` |
| `R/forest.R`, `R/consort.R`, `R/groupcompare.R`, `R/correlation.R`, `R/roc.R`, `R/regression.R` | Delete |
| `web/forms/forest.js`, `consort.js`, `groupcompare.js`, `correlation.js`, `roc.js`, `regression.js` | Delete (`km.js`, `km.test.mjs` stay) |
| `web/app.js` | Registry shrinks to 2 entries |
| `web/index.html` | Nav shrinks to 2 buttons under one `Guided analyses` group |
| `web/worker.js` | Fetch list, `EXTRA_PACKAGES`, boot set, stale comments |
| `DESCRIPTION` | Imports trimmed |
| `tests/testthat/test-{forest,consort,groupcompare,correlation,roc,regression}.R` | Delete |
| `tests/e2e/analysis.spec.js`, `tests/e2e/fixtures/groupcompare.csv` | Delete |
| `tests/e2e/smoke.spec.js` | Rewritten as a 2-analysis boot check |
| `README.md`, `CLAUDE.md` | Repositioned around the two guided analyses |

---

### Task 1: Tag the pre-trim state and relocate `%||%` to `R/dispatch.R`

**Files:**
- Modify: `R/dispatch.R:25-31` (append helper)
- Modify: `R/forest.R:35` (remove helper)

**Interfaces:**
- Consumes: nothing.
- Produces: `` `%||%` `` defined in `R/dispatch.R` — Task 2 deletes `R/forest.R` relying on this. Tag `pre-trim-8-analyses`.

- [ ] **Step 1: Tag the pre-trim state**

```bash
git tag -a pre-trim-8-analyses -m "Last commit with all 8 analyses"
git tag -l pre-trim-8-analyses
```

Expected: the tag name prints.

- [ ] **Step 2: Move the helper**

In `R/forest.R`, delete line 35 exactly:

```r
`%||%` <- function(a, b) if (is.null(a)) b else a
```

In `R/dispatch.R`, append after the `.svg_string` function:

```r

#' Null-coalescing helper shared by every figure implementation.
`%||%` <- function(a, b) if (is.null(a)) b else a
```

- [ ] **Step 3: Verify the full suite is green (relocation is behavior-neutral)**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS <n> ]` with the same PASS count as before the edit.

- [ ] **Step 4: Commit**

```bash
git add R/dispatch.R R/forest.R
git commit -m "refactor: relocate %||% to dispatch.R ahead of forest.R removal

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Hard-delete the six analyses across every layer

**Files:**
- Delete: `R/forest.R`, `R/consort.R`, `R/groupcompare.R`, `R/correlation.R`, `R/roc.R`, `R/regression.R`
- Delete: `web/forms/forest.js`, `web/forms/consort.js`, `web/forms/groupcompare.js`, `web/forms/correlation.js`, `web/forms/roc.js`, `web/forms/regression.js`
- Delete: `tests/testthat/test-forest.R`, `test-consort.R`, `test-groupcompare.R`, `test-correlation.R`, `test-roc.R`, `test-regression.R`
- Delete: `tests/e2e/analysis.spec.js`, `tests/e2e/fixtures/groupcompare.csv`
- Modify: `R/dispatch.R:7-17`, `web/app.js:65-73`, `web/index.html:28-39`, `web/worker.js:7-11,24-31`, `DESCRIPTION`

**Interfaces:**
- Consumes: `%||%` in `R/dispatch.R` (Task 1).
- Produces: a 2-analysis app; Task 3 documents it. Nav accessible names stay `Summary statistics` and `Kaplan-Meier` (existing guided e2e selectors depend on them).

- [ ] **Step 1: Delete the files**

```bash
git rm R/forest.R R/consort.R R/groupcompare.R R/correlation.R R/roc.R R/regression.R \
  web/forms/forest.js web/forms/consort.js web/forms/groupcompare.js \
  web/forms/correlation.js web/forms/roc.js web/forms/regression.js \
  tests/testthat/test-forest.R tests/testthat/test-consort.R \
  tests/testthat/test-groupcompare.R tests/testthat/test-correlation.R \
  tests/testthat/test-roc.R tests/testthat/test-regression.R \
  tests/e2e/analysis.spec.js tests/e2e/fixtures/groupcompare.csv
```

- [ ] **Step 2: Shrink the dispatch switch**

In `R/dispatch.R`, replace the `switch` block:

```r
    out <- switch(as.character(fig),
      forest  = fig_forest(spec),
      consort = fig_consort(spec),
      summary = fig_summary(spec),
      km      = fig_km(spec),
      groupcompare = fig_groupcompare(spec),
      correlation = fig_correlation(spec),
      roc     = fig_roc(spec),
      regression = fig_regression(spec),
      stop(sprintf("Unknown figure: %s", fig))
    )
```

with:

```r
    out <- switch(as.character(fig),
      summary = fig_summary(spec),
      km      = fig_km(spec),
      stop(sprintf("Unknown figure: %s", fig))
    )
```

- [ ] **Step 3: Shrink the form registry**

In `web/app.js`, replace the import + registry block (lines 65–73):

```js
import { renderForestForm } from "./forms/forest.js";
import { renderConsortForm } from "./forms/consort.js";
import { renderGuidedSummary } from "./guided/summary/guided-summary.js";
import { renderGroupCompareForm } from "./forms/groupcompare.js";
import { renderCorrelationForm } from "./forms/correlation.js";
import { renderRocForm } from "./forms/roc.js";
import { renderRegressionForm } from "./forms/regression.js";
import { renderGuidedKm } from "./guided/guided-analysis.js";
const forms = { forest: renderForestForm, consort: renderConsortForm, summary: renderGuidedSummary, km: renderGuidedKm, groupcompare: renderGroupCompareForm, correlation: renderCorrelationForm, roc: renderRocForm, regression: renderRegressionForm };
```

with:

```js
import { renderGuidedSummary } from "./guided/summary/guided-summary.js";
import { renderGuidedKm } from "./guided/guided-analysis.js";
const forms = { summary: renderGuidedSummary, km: renderGuidedKm };
```

- [ ] **Step 4: Shrink the nav**

In `web/index.html`, replace the `<nav>` contents (lines 28–39):

```html
      <nav>
        <p class="nav-group">Summary figures</p>
        <button data-figure="forest">Forest plot</button>
        <button data-figure="consort">CONSORT</button>
        <button data-figure="summary">Summary statistics</button>
        <p class="nav-group">CSV analyses</p>
        <button data-figure="km">Kaplan-Meier</button>
        <button data-figure="groupcompare">Group comparison</button>
        <button data-figure="correlation">Correlation</button>
        <button data-figure="roc">ROC / AUC</button>
        <button data-figure="regression">Regression table</button>
      </nav>
```

with:

```html
      <nav>
        <p class="nav-group">Guided analyses</p>
        <button data-figure="summary">Summary statistics</button>
        <button data-figure="km">Kaplan-Meier</button>
      </nav>
```

- [ ] **Step 5: Trim the worker**

In `web/worker.js`:

Replace lines 7–11 (comment + `EXTRA_PACKAGES`):

```js
// Heavy, figure-specific packages are installed LAZILY the first time a figure
// of that type is requested — not at boot — so a user who only makes a forest
// plot never downloads the KM package tree. Boot installs only
// the shared base below. See ensureExtraPackages().
const EXTRA_PACKAGES = { km: ["survival", "cowplot"], roc: ["pROC"], regression: ["gtsummary", "broom", "broom.helpers"] };
```

with:

```js
// Heavy, figure-specific packages are installed LAZILY the first time a figure
// of that type is requested — not at boot — so a Summary-statistics user never
// downloads the KM survival tree. Boot installs only the shared base below.
// See ensureExtraPackages().
const EXTRA_PACKAGES = { km: ["survival", "cowplot"] };
```

Replace the boot-install line:

```js
  await webR.installPackages(["ggplot2", "svglite", "jsonlite", "knitr"], { quiet: true });
```

with:

```js
  await webR.installPackages(["ggplot2", "svglite", "jsonlite"], { quiet: true });
```

Replace the fetch-loop comment + list (lines 28–31):

```js
  // Load the R sources that define render_figure() and the fig_* functions.
  // Only dispatch.R and forest.R exist today; the rest are added by later
  // tasks. Missing files 404, and the `resp.ok` guard skips them.
  for (const f of ["dispatch.R", "forest.R", "consort.R", "summarize.R", "km.R", "groupcompare.R", "correlation.R", "roc.R", "regression.R", "themes.R"]) {
```

with:

```js
  // Load the R sources that define render_figure() and the fig_* functions.
  // Missing files 404, and the `resp.ok` guard skips them.
  for (const f of ["dispatch.R", "summarize.R", "km.R", "themes.R"]) {
```

- [ ] **Step 6: Trim DESCRIPTION**

Replace the Imports line:

```
Imports: ggplot2, survival, cowplot, svglite, jsonlite, knitr, grDevices, stats, pROC, gtsummary, broom, broom.helpers
```

with:

```
Imports: ggplot2, survival, cowplot, svglite, jsonlite, grDevices, stats
```

- [ ] **Step 7: Verify — suites and dangling-reference greps**

```bash
Rscript -e 'devtools::test()'
npm run test:unit
rm -rf web/R && cp -R R web/R
grep -rn "fig_forest\|fig_consort\|fig_groupcompare\|fig_correlation\|fig_roc\|fig_regression" R/ tests/ web/
grep -rn "forms/forest\|forms/consort\|forms/groupcompare\|forms/correlation\|forms/roc\|forms/regression" web/ tests/
```

Expected: R `[ FAIL 0 | WARN 0 | ... ]` (smaller PASS count); unit all ok (its file list is untouched — every entry belongs to a keeper); **both greps print nothing**.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat!: trim app to the two guided analyses (Summary statistics, Kaplan-Meier)

Removes forest, CONSORT, group comparison, correlation, ROC, and regression
across nav/forms/R/dispatch/worker/DESCRIPTION/tests. Pre-trim state is
preserved under the pre-trim-8-analyses tag.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Rewrite smoke e2e, reposition README + CLAUDE.md, full verification

**Files:**
- Modify: `tests/e2e/smoke.spec.js` (full rewrite)
- Modify: `README.md` (full rewrite)
- Modify: `CLAUDE.md` (six targeted edits)

**Interfaces:**
- Consumes: the 2-analysis app (Task 2).
- Produces: nothing further — closing gate.

- [ ] **Step 1: Rewrite the smoke spec**

Replace the entire contents of `tests/e2e/smoke.spec.js` (it was a forest end-to-end; webR end-to-end coverage lives in `km-guided`/`summary-guided`/`km` specs) with:

```js
const { test, expect } = require("@playwright/test");

// Boot check only: the guided specs cover full webR renders. This guards the
// trimmed nav — exactly the two guided analyses, in order, plus the empty state.
test("app boots with exactly the two guided analyses", async ({ page }) => {
  await page.goto("/");
  const nav = page.locator("nav button[data-figure]");
  await expect(nav).toHaveCount(2);
  await expect(nav.nth(0)).toHaveText("Summary statistics");
  await expect(nav.nth(1)).toHaveText("Kaplan-Meier");
  await expect(page.getByText("Select an analysis on the left to begin.")).toBeVisible();
});
```

- [ ] **Step 2: Rewrite README.md**

Replace the entire file with:

```markdown
# Clinical Manuscript Figures

Free, open-source, browser-based clinical analyses for journal manuscripts,
rendered by real R (ggplot2, survival, cowplot) via
[webR](https://docs.r-wasm.org/webr/).

Two **guided analyses**, each a three-stage flow — Understand / Try an
Example / Analyze Your Data — with teaching content and a frozen synthetic
demo dataset:

- **Summary statistics** (the baseline "Table 1"): upload a CSV and tick
  variables; R assesses each continuous variable's normality (Shapiro-Wilk /
  skewness, within study groups) and reports mean ± SD or median (IQR)
  accordingly, with distribution plots (histogram + density, grouped box
  plots, optional Q-Q panels), honest missing-data denominators, no baseline
  p-values, and a copy-pasteable methods sentence.
- **Kaplan-Meier**: survival curves with a number-at-risk table, log-rank
  test, and median survival, from a time/event/group CSV.

**Your data never leaves your browser.** There is no server; all computation
runs client-side in WebAssembly.

## Develop

- R functions live in `R/` and are testable in plain R: `R -q -e 'devtools::test()'`
- The static site is in `web/`. For local dev: `cp -R R web/R && npm run serve`
- End-to-end: `npm run test:e2e`

## Live site

Published via GitHub Pages from `web/` on every push to `main`.
```

- [ ] **Step 3: CLAUDE.md edit 1 — "What this is" package list**

Replace (line 7):

```
Real R packages (ggplot2, survival, pROC, gtsummary, …) run **client-side in the browser via webR (WebAssembly)**
```

with:

```
Real R packages (ggplot2, survival, cowplot, …) run **client-side in the browser via webR (WebAssembly)**
```

- [ ] **Step 4: CLAUDE.md edit 2 — suppressWarnings example**

In the `devtools::test()` bullet (line 15), replace:

```
If a warning genuinely originates inside a library (gtsummary/pROC internals), wrap **only that library call** in `suppressWarnings()`
```

with:

```
If a warning genuinely originates inside a library's internals, wrap **only that library call** in `suppressWarnings()`
```

- [ ] **Step 5: CLAUDE.md edit 3 — input-modes paragraph**

Replace the whole paragraph starting `**Two input modes.**` (line 32) with:

```
**Input.** Both guided analyses take an **uploaded CSV** parsed in-browser. Summary statistics (`summary`) is auto-computed and normality-aware: the user uploads a CSV, ticks a variable checklist, and R decides mean ± SD vs median (IQR) per variable and builds the table + distribution plots — no typed numbers. The shared foundation lives in `web/lib/`: `csv.js` (`parseCsv` → `{columns, rows, types}` with numeric/categorical inference, plus `toCsv`, its guarded inverse) and `columnpicker.js` (`renderColumnPicker` → type-filtered dropdowns mapping columns to analysis roles). Forms send `{figure, data:[...rows], roles:{...}, options:{...}}`; R extracts columns by role. (KM predates `web/lib` and keeps its own fixed-column parser in `web/forms/km.js`; Summary builds on the shared `csv.js` foundation.)
```

- [ ] **Step 6: CLAUDE.md edit 4 — guided-shell paragraph tail**

In the paragraph starting `Kaplan–Meier **and** Table 1 (Summary)` (line 34), replace the final sentence:

```
KM ships a frozen synthetic demo (`data-raw/km-demo-generator.R`); the other analyses keep the plain form registry.
```

with:

```
Both ship frozen synthetic demos (`data-raw/km-demo-generator.R`, `data-raw/summary-demo-generator.R`). The form registry in `web/app.js` still routes nav clicks and is the extension point for future analyses.
```

- [ ] **Step 7: CLAUDE.md edit 5 — lazy-package paragraph**

Replace the whole paragraph starting `**Lazy package install.**` (line 36) with:

```
**Lazy package install.** The worker boots with only the shared packages (`ggplot2, svglite, jsonlite`). Heavy per-figure packages install on first use via `EXTRA_PACKAGES` in `worker.js` (`km → survival/cowplot`), guarded by a single-flight promise so concurrent requests install once. This keeps a Summary-statistics user from downloading the survival tree. `fig_summary` (`R/summarize.R`) uses only base `stats` + `ggplot2`, so it needs **no** `EXTRA_PACKAGES` entry.
```

- [ ] **Step 8a: CLAUDE.md edit 6 — test-filter example**

In the Commands section, replace:

```
- One file: `Rscript -e 'devtools::test(filter = "roc")'` (matches `tests/testthat/test-roc.R`)
```

with:

```
- One file: `Rscript -e 'devtools::test(filter = "km")'` (matches `tests/testthat/test-km.R`)
```

- [ ] **Step 8b: CLAUDE.md edit 7 — dispatcher table sentence**

In the Architecture section, replace:

```
- **`svg`** normally holds an `<svg>`, but `fig_summary` (Table 1) and `fig_regression` put an **HTML `<table>`** in the `svg` field instead — the UI injects it the same way, so tables render with no special-casing.
```

with:

```
- **`svg`** normally holds an `<svg>`, but `fig_summary` (Summary statistics) puts an **HTML `<table>`** (plus sibling distribution-plot SVGs) in the `svg` field instead — the UI injects it the same way, so tables render with no special-casing.
```

- [ ] **Step 8c: CLAUDE.md edit 8 — coercion-pattern and design-docs examples**

In the "Adding a figure" section, replace:

```
For CSV analyses, build the form on `web/lib/csv.js` + `web/lib/columnpicker.js`; coerce spec columns to numeric with a suppress-warning-then-clear-`stop()` pattern (see `R/correlation.R` / `R/roc.R`) so a non-numeric column yields a readable error, not a leaked coercion warning.
```

with:

```
For CSV analyses, build the form on `web/lib/csv.js` + `web/lib/columnpicker.js`; coerce spec columns to numeric with a suppress-warning-then-clear-`stop()` pattern (see `.numeric_col` in `R/summarize.R`) so a non-numeric column yields a readable error, not a leaked coercion warning.
```

In the "Design docs" section, replace:

```
Read the relevant one before extending a feature — they carry the rationale (e.g. why regression is a merged univariable+multivariable "Table 2", why the KM figure ships a built-in number-at-risk table via cowplot).
```

with:

```
Read the relevant one before extending a feature — they carry the rationale (e.g. why the KM figure ships a built-in number-at-risk table via cowplot, why the app was trimmed to the two guided analyses).
```

- [ ] **Step 8d: CLAUDE.md edit 9 — helper locations + stale env bullet**

In the "Adding a figure" list item 1 (line 46), replace:

```
Reuse `.svg_string(plot, w, h)` from `R/dispatch.R` and `%||%` from `R/forest.R` — do **not** redefine them.
```

with:

```
Reuse `.svg_string(plot, w, h)` and `%||%` — both live in `R/dispatch.R` — do **not** redefine them.
```

Delete the now-obsolete environment bullet (line 57):

```
- gtsummary here is 2.x: `as_kable_html` is gone — use `as_kable(tbl, format = "html")`. `broom.helpers` is a gtsummary *Suggests* (not Imports), so it is listed explicitly in this repo's `DESCRIPTION` and `EXTRA_PACKAGES` or regression breaks in a clean install.
```

- [ ] **Step 9: Full verification**

```bash
Rscript -e 'devtools::test()'
npm run test:unit
rm -rf web/R && cp -R R web/R && npm run test:e2e
grep -rniE "forest|consort|groupcompare|correlation|regression|pROC|gtsummary" README.md CLAUDE.md web/index.html web/app.js
```

Expected: R `[ FAIL 0 | WARN 0 | ... ]`; unit all ok; Playwright — remaining specs all pass (smoke boot check + km + km-guided + summary-guided; `analysis.spec.js` is gone); the doc grep prints nothing (no stale analysis references in user-facing docs/UI). ("ROC" is omitted from the grep pattern because it collides with common words; the pROC/gtsummary package names catch the same stale references.)

- [ ] **Step 10: Commit**

```bash
git add tests/e2e/smoke.spec.js README.md CLAUDE.md
git commit -m "docs+test: reposition around the two guided analyses; smoke spec guards the trimmed nav

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

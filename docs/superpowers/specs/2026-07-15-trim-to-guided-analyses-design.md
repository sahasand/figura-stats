# Trim the app to the two guided analyses (Kaplan-Meier + Summary statistics)

**Date:** 2026-07-15
**Status:** Approved
**Decision (product owner):** The app keeps only its two guided analyses — Kaplan-Meier
(`km`) and Summary statistics (`summary`) — and removes the six plain-form analyses:
forest, consort, groupcompare, correlation, roc, regression. The guided pair carries the
product's quality bar (Understand / Try an Example / Analyze Your Data, teaching content,
curated demos); the plain forms don't, and dropping them trims the heavy webR package
trees (pROC, gtsummary/broom), roughly half the R test suite, and the per-figure
maintenance surface.

## Safety net

Before any deletion, tag the pre-trim state:
`git tag -a pre-trim-8-analyses -m "Last commit with all 8 analyses"` .
Revival of any analysis is a checkout away; nothing else (no hidden code paths, no
commented-out blocks) is kept for resurrection.

## Removals, layer by layer

| Layer | Remove | Keep |
|---|---|---|
| Nav (`web/index.html`) | The six `data-figure` buttons and the `Summary figures` / `CSV analyses` group labels — replaced by a single `Guided analyses` group | `summary`, `km` buttons |
| Form registry (`web/app.js`) | Imports + `forms` entries for the six | `summary: renderGuidedSummary`, `km: renderGuidedKm` |
| `web/forms/` | `forest.js`, `consort.js`, `groupcompare.js`, `correlation.js`, `roc.js`, `regression.js` | **`km.js` + `km.test.mjs` stay** — guided KM imports `../forms/km.js` |
| R sources | `R/forest.R`, `R/consort.R`, `R/groupcompare.R`, `R/correlation.R`, `R/roc.R`, `R/regression.R`; their entries in the `render_figure` switch (`R/dispatch.R`) | `dispatch.R`, `km.R`, `summarize.R`, and `themes.R` (**stays** — `R/km.R:59` calls `.fig_theme`) |
| Worker (`web/worker.js`) | Deleted files from the boot fetch list; `roc`/`regression` entries in `EXTRA_PACKAGES`; `knitr` from the boot package set (no `knitr::` call exists in `R/`) | `km: ["survival", "cowplot"]`; boot set `ggplot2, svglite, jsonlite` |
| `DESCRIPTION` | `pROC, gtsummary, broom, broom.helpers, knitr` from Imports | `ggplot2, survival, cowplot, svglite, jsonlite, grDevices, stats` |
| R tests | `test-forest.R`, `test-consort.R`, `test-groupcompare.R`, `test-correlation.R`, `test-roc.R`, `test-regression.R` | `test-summarize.R`, `test-summary-demo.R`, `test-km.R`, `test-km-demo.R`, `test-dispatch.R` (exercises only `summary` + the error contract), `test-themes.R` |
| E2E | `tests/e2e/analysis.spec.js` (covers removed analyses); `smoke.spec.js` rewritten — its forest end-to-end becomes a minimal boot check (page loads, nav shows exactly the two guided analyses); webR end-to-end coverage already lives in `km-guided` / `summary-guided` specs | `km.spec.js`, `km-guided.spec.js`, `summary-guided.spec.js` |
| Fixtures | `tests/e2e/fixtures/groupcompare.csv` | `km.csv`, testthat fixtures used by keepers |

`package.json`'s `test:unit` list is untouched — every listed unit file belongs to a keeper.

## Shared-code relocation (the one real code change)

`%||%` is defined in `R/forest.R` and used by `km.R` and `summarize.R` (among others).
Deleting forest.R without relocating it breaks both keepers. It moves to `R/dispatch.R`
(beside `.svg_string`, the other shared helper), defined once, unchanged. No other shared
helper lives in a removed file (`.km_palette` is in `km.R`; `.svg_string` in `dispatch.R`;
`web/lib/csv.js` / `columnpicker.js` serve the summary form).

## Documentation updates

- **README**: repositioned around the two guided analyses.
- **CLAUDE.md**: "What this is" and Architecture sections updated — two guided analyses,
  the trimmed `EXTRA_PACKAGES` map, `%||%` now in `R/dispatch.R`, the "Adding a figure"
  five-keys example kept (the mechanism is unchanged) but its package examples updated,
  the "Two input modes" paragraph rewritten (typed-form registry now holds no plain
  analyses; the registry mechanism itself stays for future use).
- Historical specs/plans under `docs/superpowers/` are untouched (they are records).

## Non-goals

- No behavior changes to the two keepers (their R code, forms, demos, and tests are
  byte-identical except the `%||%` relocation, which is behavior-neutral).
- The journal-export feature is a separate spec/plan and lands after this trim (its
  km/summary allowlist then simplifies away).
- No removal of the shared machinery the keepers or future analyses use: guided shell,
  session state, `csv.js`, `columnpicker.js`, the form-registry mechanism, `.svg_string`.

## Acceptance

- Nav shows exactly two buttons: Summary statistics, Kaplan-Meier.
- `Rscript -e 'devtools::test()'` → `[ FAIL 0 | WARN 0 | ... ]` (suite is smaller; no
  reference to deleted files remains — `grep -rn "fig_forest\|fig_consort\|fig_groupcompare\|fig_correlation\|fig_roc\|fig_regression"` over `R/ tests/ web/` is empty except `web/R/` build copies).
- `npm run test:unit` green; full Playwright suite green after `rm -rf web/R && cp -R R web/R`.
- A fresh browser session renders both keepers end to end (covered by the guided e2e specs).
- Tag `pre-trim-8-analyses` exists and points at the last 8-analysis commit.

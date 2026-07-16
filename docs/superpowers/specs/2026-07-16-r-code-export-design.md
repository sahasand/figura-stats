# R-code export for KM, Summary statistics, and Group comparison — design

**Date:** 2026-07-16
**Status:** Approved
**Motivation:** Trust. Explore's deparse-the-expression-that-ran pattern is the app's
most trust-dense feature: the user sees (and can rerun) the exact R that produced the
result. This design extends that to the other three guided analyses and makes the
script downloadable, so every result is defensible in the user's own R session.

## Decisions (made with the user)

1. **Fidelity — exact stats, clean plot code.** The statistical calls are built as R
   expressions, evaluated by the app for its own output, and deparsed into the script.
   The numbers a user reproduces are identical *by construction*. The figure section is
   generated clean ggplot2 code that produces an *equivalent* (not pixel-identical)
   figure. The script header states this split honestly.
2. **UI — one `.R` button in the Console toolbar.** No new pane. Explore is unchanged
   (its text pane already is the script).
3. **Data loading — `read.csv` with the real uploaded filename.** For Try-an-Example
   runs the frozen demo CSV is embedded inline (`read.csv(text = "...")`) so the
   example script runs with zero setup. User data contents are never embedded.

## Contract extension

`fig_km`, `fig_summary`, `fig_groupcompare` return `list(svg=, text=, code=)`.

- `code` is a single string: a complete, runnable R script.
- `text` keeps its current meaning (methods sentence / TSV table) — the journal `.tsv`
  workflow is untouched.
- `render_figure` (R/dispatch.R), `worker.js`, and `app.js` pass `code` through as one
  more JSON field; no dispatch changes beyond serialization.
- Explore keeps `list(svg=, text=)` — its `text` is already the script.

## Script anatomy

Shared assembly helpers live in a new `R/script.R` (loaded by the worker boot loop like
every other R file):

1. **Header comment** — analysis name, source data filename (or "embedded example
   data"), the app name, and a version stamp: `R.version.string` plus `packageVersion()` for each package the
   script uses. One honest line: statistics below are the exact calls the app ran;
   the plot code produces an equivalent figure.
2. **Data section** —
   - User upload: `df <- read.csv("<uploaded-filename>", check.names = FALSE)`.
     The filename travels in the spec as new `options.source_filename`, set by each
     analysis's Analyze form at parse time. Only the *name* leaves the form — never
     file contents.
   - Demo run: embed the dataset via `read.csv(text = "...")`, serialized by R from
     the `spec$data` rows it already receives. The rule is explicit: if
     `options.source_filename` is present, the script reads that file; if absent,
     the script embeds the data. Demo spec builders simply never set a filename.
3. **Statistics section (trust core)** — each analysis builds its statistical calls as
   expressions (`bquote`/`as.call`, Explore-style), **evaluates those same expressions**
   to produce its own figures/text, and deparses them into the script:
   - KM: `survfit(Surv(time, event) ~ group, data = df)`, `survdiff`, optional `coxph`
     (hazard-ratio option), landmark estimates when enabled.
   - Summary: per-variable normality decision (reusing `.summary_decide`'s calls:
     `shapiro.test` etc.), `mean`/`sd`/`median`/`quantile` summaries, table assembly in
     base R.
   - Group comparison: the routed test exactly as chosen (`shapiro.test`,
     `t.test`/`wilcox.test`/`aov`/`kruskal.test`/`chisq.test`/`fisher.test`), effect
     size + CI, Tukey/Dunn post-hoc when 3+ groups.
   Refactor rule: where a fig_* currently calls these directly, it switches to
   build-expression → eval → deparse for the *statistical* calls only. Plot internals
   are not refactored.
4. **Figure section** — generated clean ggplot2 code parameterized by the same spec
   options (KM: curves + CI ribbon + censor marks + cowplot risk-table code; Summary:
   the distribution plots when enabled; Group comparison: the comparison plot).
   Equivalent output, not pixel-identical.

## UI

- `textExportDescriptor` (web/lib/export.js) grows a code-export descriptor; a new
  `.R` button renders beside Copy/`.tsv` in the Console toolbar (web/export-ui.js).
- The script is not in the DOM: app.js (or the paint path in guided/shell.js) stashes
  the current result's `code` in module state when painting and clears it on nav
  switch/pane clear — same staleness invariant as the other export handlers.
- Button enabled only when the current result carries `code`. Disabled title explains
  why ("Run an analysis to generate its R script").
- Filename via `exportFilename`: `km-script.R`, `summary-script.R`,
  `groupcompare-script.R`.
- Button title copy: "Download the R script that reproduces this analysis —
  statistics are the exact calls the app ran."

## Testing

- **R (testthat, the meat):** for each analysis, generate the script from the demo
  spec, `parse(text = code)` (syntax gate), evaluate it in a clean environment against
  the demo data, and assert the key numbers (KM: log-rank p, median survival;
  Summary: chosen summaries per variable; Group comparison: p-value + effect size)
  match the app's own `text` output. This is the "script reproduces the analysis"
  regression gate. WARN 0 discipline applies.
- **JS unit:** descriptor shape, filename generation, enabled-state logic.
- **E2E (Playwright):** after a demo render, the `.R` button is enabled and the
  downloaded blob contains the header + a `survfit`/`t.test`/`shapiro.test` call.

## Scope & staging

All three analyses in one feature. Implementation order: **Summary → Group
comparison → KM** — the first two are base-stats and prove the shared `R/script.R`
pattern; KM (risk table, landmarks, cox option) is the big lift and goes last.
Explore is out of scope (already done) except that nothing here may regress its
`.R` export.

## Non-goals

- Pixel-identical figure reproduction (explicitly traded away).
- Embedding user data in scripts.
- A visible in-app code pane for these analyses (may revisit after shipping).

## Implementation deviations (2026-07-16)

- **Script storage.** The generated script is stored on `#stats`'s `data-r-code`
  attribute rather than in module state, matching the existing read-the-DOM-at-
  click-time export idiom (the export toolbar already reads `#preview`/`#stats`
  at click time). The panes are the single source of truth; a nav switch or a
  re-run clears the attribute so a stale script can never download.
- **Summary has no figure section.** The Summary script emits the statistics
  (grouping + per-variable `tapply`/`table` calls) only; the distribution-plot
  section was trimmed at planning and never generated.
- **Summary is parallel-reconstruction, not deparsed calls.** Summary's
  statistics section rebuilds the numbers with the same base-R calls the app
  used (mean/sd/quantile type 7) rather than deparsing evaluated expressions,
  with the per-variable normality decision carried as comments. The header
  honesty line reflects this (per-analysis `honesty` argument on
  `.script_header`/`.script_assemble`); Group comparison and KM keep the default
  exact-calls wording.

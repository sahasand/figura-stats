# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A free, static, **backend-less** clinical-figures + statistics tool for journal manuscripts. Real R packages (ggplot2, survival, cowplot, …) run **client-side in the browser via webR (WebAssembly)** — there is no server, and user data never leaves the browser. The R code is authored and tested as a normal R package (`manuscriptfigures`, see `DESCRIPTION`); webR is only the delivery vehicle. The static site lives in `web/` and is published to GitHub Pages.

## Commands

R is the source of statistical truth and is tested in plain R (no browser needed):

- Full R suite: `Rscript -e 'devtools::test()'`
- One file: `Rscript -e 'devtools::test(filter = "km")'` (matches `tests/testthat/test-km.R`)
- **Always use `devtools::test()`, never `testthat::test_file()`** — `test_file` silently swallows ggplot2 soft-deprecation warnings. **WARN 0 is a hard gate** (`[ FAIL 0 | WARN 0 | ... ]`); a leaked warning must be fixed at the source (ggplot2 4.x: use `linewidth`, not `size`/`label.size`; `geom_errorbar(orientation="y")`, not `geom_errorbarh`). If a warning genuinely originates inside a library's internals, wrap **only that library call** in `suppressWarnings()` — never wrap your own model fitting or data prep.

JS unit tests (plain Node, no framework) and browser end-to-end tests:

- JS unit: `npm run test:unit` (runs `web/lib/*.test.mjs`)
- E2E (Playwright + webR): `rm -rf web/R && cp -R R web/R && npm run test:e2e`
- Serve locally: `rm -rf web/R && cp -R R web/R && npm run serve` (→ http://localhost:8321; non-default port so stale service workers from other localhost PWA projects can't hijack the page)

**`web/R/` is a gitignored build copy of `R/`.** The worker fetches R sources at `R/<file>` relative to the `web/` root, so `R/` must be copied into `web/` before serving or running e2e. Use `rm -rf web/R` first — a bare `cp -R R web/R` nests into an existing dir. The deploy workflow does this copy at publish time.

## Architecture

**One contract, one dispatcher.** `web/app.js` sends a JSON spec to a webR session in a Web Worker (`web/worker.js`); R's `render_figure(json_string)` (`R/dispatch.R`) routes on `spec$figure` to one `fig_<name>(spec)` per figure, each returning `list(svg = <character>, text = <character>)`. `render_figure` is wrapped in `tryCatch` and **never throws** — errors come back as `{"ok":false,"error":...}`. `app.js` injects `out.svg` into `#preview` (as `innerHTML`) and `out.text` into `#stats`.

- **`text`** is a copy-pasteable methods/results sentence (or TSV for tables).
- **`svg`** normally holds an `<svg>`, but `fig_summary` (Summary statistics) puts an **HTML `<table>`** (plus sibling distribution-plot SVGs) in the `svg` field instead — the UI injects it the same way, so tables render with no special-casing.

**Input.** Both guided analyses take an **uploaded CSV** parsed in-browser. Summary statistics (`summary`) is auto-computed and normality-aware: the user uploads a CSV, ticks a variable checklist, and R decides mean ± SD vs median (IQR) per variable and builds the table + distribution plots — no typed numbers. The shared foundation lives in `web/lib/`: `csv.js` (`parseCsv` → `{columns, rows, types}` with numeric/categorical inference, plus `toCsv`, its guarded inverse) and `columnpicker.js` (`renderColumnPicker` → type-filtered dropdowns mapping columns to analysis roles). Forms send `{figure, data:[...rows], roles:{...}, options:{...}}`; R extracts columns by role. (KM predates `web/lib` and keeps its own fixed-column parser in `web/forms/km.js`; Summary builds on the shared `csv.js` foundation.)

Kaplan–Meier **and** Table 1 (Summary) both route through a guided three-stage shell — Understand / Try an Example / Analyze Your Data — built by the shared `createGuidedShell(config)` factory in `web/guided/shell.js`, with session semantics in `web/guided/session-state.js`. A new guided analysis is a **config file** — the `createGuidedShell({...})` config object lives in `web/guided/guided-analysis.js` (KM) and `web/guided/summary/guided-summary.js` (Summary), with each analysis's content/demo pieces beside it in `web/guided/km/` and `web/guided/summary/` — never a copy of the shell. Both ship frozen synthetic demos (`data-raw/km-demo-generator.R`, `data-raw/summary-demo-generator.R`). The form registry in `web/app.js` still routes nav clicks and is the extension point for future analyses.

**Lazy package install.** The worker boots with only the shared packages (`ggplot2, svglite, jsonlite`). Heavy per-figure packages install on first use via `EXTRA_PACKAGES` in `worker.js` (`km → survival/cowplot`), guarded by a single-flight promise so concurrent requests install once. This keeps a Summary-statistics user from downloading the survival tree. `fig_summary` (`R/summarize.R`) uses only base `stats` + `ggplot2`, so it needs **no** `EXTRA_PACKAGES` entry.

**No data egress.** The only network calls are the webR runtime/packages from the CDN and `fetch("R/*.R")`. There is no analytics or upload of user data — this is an invariant, not a preference. All statistics live in R; JS only parses CSVs and marshals columns. Fonts (IBM Plex) are self-hosted in `web/fonts/` for the same reason — never link a font CDN.

**UI tokens.** All chrome styling routes through the CSS variables at the top of `web/styles.css` (teal `--accent`, `--radius*`, warn palette). Data colors in figures (Tol palette, `R/km.R .km_palette`) are deliberately distinct from chrome colors. Known UI/a11y fast-follows live in `.scratch/guided-analysis-km/issues/stage-a-fast-follows.md`.

## Adding a figure or analysis

A new figure `foo` requires **five parallel keys to stay in sync**, or it will pass R tests but 404 / mis-route in the browser:

1. `R/foo.R` — `fig_foo(spec)` returning `list(svg=, text=)`. Reuse `.svg_string(plot, w, h)` and `%||%` — both live in `R/dispatch.R` — do **not** redefine them.
2. `R/dispatch.R` — add `foo = fig_foo(spec),` to the `switch`.
3. `web/worker.js` — add `"foo.R"` to the boot-time R-file fetch loop (every new R file needs this), and add a `foo: [...]` entry to `EXTRA_PACKAGES` **only** if it needs packages beyond the boot set.
4. `web/forms/foo.js` — `renderFooForm(container, onSubmit)`; `web/app.js` — import + register it in the form registry; `web/index.html` — a `<button data-figure="foo">`.
5. If it uses a new R package, add it to `DESCRIPTION` Imports (CI installs deps via `local::.`) **and** to the worker's `EXTRA_PACKAGES` for that figure.

For CSV analyses, build the form on `web/lib/csv.js` + `web/lib/columnpicker.js`; coerce spec columns to numeric with a suppress-warning-then-clear-`stop()` pattern (see `.numeric_col` in `R/summarize.R`) so a non-numeric column yields a readable error, not a leaked coercion warning.

## Environment notes

- Local R is Homebrew R 4.6 (bleeding-edge → CRAN builds packages from source). See the memory note `r-toolchain-homebrew-webr-gotchas` for the system-lib / Anaconda-PATH fixes needed to install the package tree locally.
- CI (`.github/workflows/ci.yml`) runs the R suite and the JS unit tests, but **not** the Playwright e2e (it downloads webR — slow/flaky). Deploy (`deploy.yml`) copies `R/`→`web/R/` and publishes `web/` to Pages on push to `main`.

## Design docs

Specs and implementation plans live in `docs/superpowers/{specs,plans}/`. Read the relevant one before extending a feature — they carry the rationale (e.g. why the KM figure ships a built-in number-at-risk table via cowplot, why the app was trimmed to the two guided analyses).

## Agent skills

### Issue tracker

Issues are tracked as local Markdown files under `.scratch/`; external pull requests are not a request surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the standard `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix` vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.

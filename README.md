# Clinical Manuscript Figures

Free, open-source, browser-based clinical figures for journal manuscripts —
forest plots, CONSORT diagrams, Table 1, and Kaplan-Meier curves — rendered by
real R (ggplot2, survival, knitr) via [webR](https://docs.r-wasm.org/webr/).

**Your data never leaves your browser.** There is no server; all computation
runs client-side in WebAssembly.

## Develop

- R functions live in `R/` and are testable in plain R: `R -q -e 'devtools::test()'`
- The static site is in `web/`. For local dev: `cp -R R web/R && npm run serve`
- End-to-end: `npm run test:e2e`

## Live site

Published via GitHub Pages from `web/` on every push to `main`.

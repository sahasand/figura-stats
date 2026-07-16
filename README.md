# Figura

*Clinical manuscript figures & statistics, computed entirely in your browser.*

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

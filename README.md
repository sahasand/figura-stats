# Clinical Manuscript Figures

Free, open-source, browser-based clinical figures for journal manuscripts —
forest plots, CONSORT diagrams, Table 1, and Kaplan-Meier curves — rendered by
real R (ggplot2, survival, knitr, pROC, gtsummary) via
[webR](https://docs.r-wasm.org/webr/).

It also runs a set of statistical analyses on your own data: **group
comparison** (box/violin plot with a t-test/ANOVA or Mann-Whitney/
Kruskal-Wallis test), **correlation** (scatter plot with Pearson or Spearman
r), **ROC/AUC** (via pROC, with a Youden-optimal cutoff), and a
**regression table** (univariable + multivariable logistic, Cox, or linear regression via
gtsummary — Table 2 style). Unlike the summary-number figures above, these
take an **uploaded CSV**: pick the file, then map its columns to each
analysis's roles (group, value, predictor, outcome, covariates, ...) with an
in-browser column picker.

**Your data never leaves your browser.** There is no server; all computation
runs client-side in WebAssembly.

## Develop

- R functions live in `R/` and are testable in plain R: `R -q -e 'devtools::test()'`
- The static site is in `web/`. For local dev: `cp -R R web/R && npm run serve`
- End-to-end: `npm run test:e2e`

## Live site

Published via GitHub Pages from `web/` on every push to `main`.

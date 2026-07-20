# Figura

*Clinical manuscript figures and statistics, computed entirely in your browser.*

**[Open the app →](https://sahasand.github.io/figura-stats/)**

Free, open-source statistics for journal manuscripts, rendered by real R
(ggplot2, survival, cowplot) running client-side via
[webR](https://docs.r-wasm.org/webr/) — WebAssembly.

**Your data never leaves your browser.** There is no server and no upload
step. You point the page at a CSV, the file is parsed in the tab, and R runs
on your own machine inside the WebAssembly sandbox. The only network requests
the app makes are for the webR runtime and R packages from the r-wasm CDN.
There is no analytics. This is an architectural invariant, not a policy
promise — there is no backend that *could* receive your data.

## Analyses

Each analysis is a three-stage guided flow — **Understand** the method,
**Try an Example** on a frozen synthetic dataset, then **Analyze Your Data**
by mapping your own CSV columns to the roles the method needs.

- **Summary statistics** — the baseline "Table 1". R assesses each continuous
  variable's normality (Shapiro-Wilk and skewness, within study groups) and
  reports mean ± SD or median (IQR) accordingly, with distribution plots,
  honest missing-data denominators, and no baseline p-values.
- **Kaplan-Meier** — survival curves with a number-at-risk table, log-rank
  test, and median survival with confidence intervals.
- **Group comparison** — routes on outcome type and picks parametric vs
  non-parametric for you: t-test/ANOVA or Wilcoxon/Kruskal-Wallis for numeric
  outcomes, chi-square/Fisher for categorical. Reports an effect size with a
  95% CI, plus Tukey or Dunn post-hoc tests for three or more groups.
- **Cox regression** — the "Table 3": unadjusted beside adjusted hazard
  ratios, an adjusted-HR forest plot, and a proportional-hazards check via
  `cox.zph` reported non-blocking.
- **Explore plot** — build a ggplot2 figure interactively. The R shown to you
  is never string-built; the plot is constructed as an expression and the same
  expression is deparsed into the code pane, so the script is literally the
  call that ran.

## Export for submission

Every result downloads from the pane toolbars:

- **PNG** at 300 / 600 / 1200 dpi, with the true resolution written into the
  file's `pHYs` chunk — unstamped canvas PNGs read as 72 dpi to journal
  submission checkers and get rejected.
- **SVG**, stitched or per-panel, for vector-figure requirements.
- **Tables and methods text** as copy-paste or `.tsv` — journals want tables
  as editable text, not images.
- **A runnable `.R` script** whose statistical calls are deparsed from the
  exact expressions the app evaluated, so your methods section and your
  reviewers' reproduction attempt agree.

All exports are generated client-side as Blob URLs. The no-egress guarantee
covers them too.

## Develop

R is the source of statistical truth and is tested in plain R — no browser
required:

```sh
Rscript -e 'devtools::test()'                    # full suite
Rscript -e 'devtools::test(filter = "km")'       # one file
```

`WARN 0` is a hard gate, not a preference.

JavaScript unit tests (plain Node, no framework) and the browser end-to-end
suite:

```sh
npm run test:unit

rm -rf web/R && cp -R R web/R    # required: see below
npm run test:e2e
npm run serve                    # → http://localhost:8321
```

`web/R/` is a gitignored build-time copy of the top-level `R/` sources — the
webR worker fetches R files relative to the `web/` root, so `R/` must be
copied in before serving. Use `rm -rf web/R` first; a bare `cp -R R web/R`
nests into an existing directory. The deploy workflow does this copy at
publish time.

Architecture notes, the figure-contract details, and the checklist for adding
a new analysis are in [`CLAUDE.md`](CLAUDE.md); design rationale lives in
`docs/superpowers/`.

## Deployment

Published to GitHub Pages from `web/` on every push to `main`
(`.github/workflows/deploy.yml`). CI runs the R suite and the JS unit tests on
every push and pull request; the Playwright e2e suite is deliberately excluded
from CI because it downloads the full webR runtime.

## Disclaimer

Figura is a research and manuscript-preparation tool. It is **not** a medical
device and is **not** intended for clinical decision-making, diagnosis, or
treatment. Statistical output is provided without warranty of any kind — see
[LICENSE](LICENSE). You are responsible for confirming that the methods it
selects are appropriate for your study design and that the results are correct
before publication or any other use.

## License

[MIT](LICENSE) © 2026 Sandeep Saha

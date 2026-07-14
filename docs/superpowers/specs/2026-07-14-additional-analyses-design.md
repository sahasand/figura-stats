# Additional Statistical Analyses — Design Spec

**Date:** 2026-07-14
**Status:** Approved design, pre-implementation
**Project:** my-stats (clinical manuscript figures, webR)
**Builds on:** 2026-07-13-clinical-figures-design.md

## Purpose

Add four inferential statistical analyses to the browser-based clinical-figures
tool. The existing figures (forest, CONSORT, Table 1, Kaplan-Meier) are mostly
descriptive or effect-display; the gap is hypothesis-testing analyses that
clinical manuscripts routinely report. All four run client-side in webR, honor
the existing `render_figure` JSON contract, and never send data off the browser.

## Scope — four analyses (one spec, built in this order)

1. **Group comparison** — box/violin plot of a numeric value across a categorical
   group, with the appropriate significance test and p-value.
2. **Correlation scatter** — scatter + fit line with Pearson/Spearman r, 95% CI, p.
3. **ROC curve + AUC** — diagnostic/prognostic accuracy from a predictor and a
   binary outcome (`pROC`).
4. **Regression table (Table 2)** — univariable + multivariable logistic (OR),
   Cox (HR), or linear (β) regression via `gtsummary`.

All four require **raw patient-level data** (unlike the summary-number figures),
so they share a CSV-upload + column-picker foundation, built first.

webR availability confirmed for every needed package (pROC, gtsummary, broom,
and the base-stats path) at repo.r-wasm.org.

## Architecture

Unchanged contract: a JSON spec → `render_figure(json_string)` in R → routes to
one `fig_<name>(spec)` per analysis → returns `list(svg=, text=)` (SVG for plots;
HTML table in the `svg` field for the regression table, as Table 1 already does)
→ worker returns JSON → UI injects `svg`/`text`. `render_figure` never throws.

Heavy packages install lazily on first use of the analysis that needs them
(same single-flight mechanism KM uses): ROC → `pROC`; regression → `gtsummary`
(+ `broom`). Group comparison and correlation use only base R stats + ggplot2 —
no extra download.

### New shared foundation: CSV + column picker

- `web/lib/csv.js` — parse a CSV string into `{columns: [...names], rows:
  [{col: value}...]}`, inferring each column's type: `numeric` (every non-empty
  value parses as a finite number) or `categorical` (otherwise). Tolerates CRLF;
  reports clear errors (empty file, no data rows, duplicate headers).
- `web/lib/columnpicker.js` — `renderColumnPicker(container, roles, table,
  onReady)` renders one labeled `<select>` per declared role. A role declares a
  required type (`numeric` | `categorical` | `any`) and whether it accepts
  multiple columns (for regression covariates). Dropdowns list only
  type-compatible columns. Calls `onReady(rolesMap)` when all required roles are
  chosen, enabling the form's Render button.
- Each new form: shows the CSV file input + "data stays in your browser" note,
  parses via csv.js on upload, renders the column picker for its roles, and on
  Render sends `{figure, data: rows, roles: {...}, options: {...}}`.

The existing KM form keeps its fixed-column parser (no unrelated refactor). The
column-picker foundation is for the four new analyses.

## Components

| Unit | Responsibility | Deps |
|---|---|---|
| `web/lib/csv.js` | Parse CSV + infer column types | none |
| `web/lib/columnpicker.js` | Role→column dropdown UI, type-filtered | csv.js output |
| `R/groupcompare.R` `fig_groupcompare` | Box/violin + test (t/Welch, Mann-Whitney, ANOVA, Kruskal-Wallis) | ggplot2, stats |
| `R/correlation.R` `fig_correlation` | Scatter + fit + cor.test (Pearson/Spearman) | ggplot2, stats |
| `R/roc.R` `fig_roc` | ROC curve, AUC + DeLong CI, Youden cutoff | pROC, ggplot2 (lazy) |
| `R/regression.R` `fig_regression` | Univariable + multivariable regression table | gtsummary, broom (lazy) |
| `web/forms/*.js` (4) | Per-analysis forms on the shared picker | csv/columnpicker |

### Per-analysis detail

**`fig_groupcompare(spec)`** — roles: `value` (numeric), `group` (categorical).
options: `plot` = `"box"`|`"violin"` (default box), `test` =
`"parametric"`|`"nonparametric"` (default parametric). Auto-detects group count:
2 groups → Welch t-test (parametric) or Mann-Whitney/`wilcox.test`
(nonparametric); >2 → one-way ANOVA (`aov`) or Kruskal-Wallis. Errors if <2
groups or value non-numeric. `svg`: ggplot2 boxplot/violin with jittered points.
`text`: group medians/means + test name + p, e.g. "Median value 5.2 (group A)
vs 3.1 (group B); Mann-Whitney p = 0.004."

**`fig_correlation(spec)`** — roles: `x` (numeric), `y` (numeric). options:
`method` = `"pearson"`|`"spearman"` (default pearson). `stats::cor.test` → r,
95% CI (pearson) or rho, p. `svg`: scatter + `geom_smooth(method="lm")`. `text`:
"r = 0.61 (95% CI 0.44–0.74), p < 0.001 (Pearson), n = 120." (Spearman reports
rho without a parametric CI.)

**`fig_roc(spec)`** — roles: `predictor` (numeric), `outcome` (binary:
exactly two distinct values; sorted, the higher level = the positive/case class,
with `pROC::roc(direction = "auto")` so the AUC is reported ≥ 0.5). `pROC::roc`
→ AUC + `ci.auc` (DeLong), optimal cutoff by Youden J. `svg`: ROC curve (1-specificity vs
sensitivity) with diagonal reference, built in ggplot2 from the roc object's
coordinates. `text`: "AUC 0.82 (95% CI 0.74–0.90); optimal cutoff X →
sensitivity Y%, specificity Z%." Errors if outcome not binary or predictor
non-numeric.

**`fig_regression(spec)`** — roles: `covariates` (multiple, any) always; plus
`outcome` (any) for logistic/linear, or `time`+`status` (numeric) for Cox (the
`outcome` role is not used in Cox mode). options: `model` =
`"logistic"`|`"cox"`|`"linear"` (default logistic). Builds the formula from
selected covariates; univariable via `gtsummary::tbl_uvregression` and
multivariable via `tbl_regression(<fit>)`, merged into one table
(`tbl_merge`). Logistic → OR, Cox → HR, linear → β, each with 95% CI and p.
`svg`: HTML table (`as_kable_html` / gtsummary → HTML); `text`: TSV of the same.
Errors clearly: logistic outcome not binary, Cox missing time/status, no
covariates selected.

## Dispatch, worker, UI wiring

- `R/dispatch.R`: add `groupcompare`, `correlation`, `roc`, `regression` cases.
- `web/worker.js` `EXTRA_PACKAGES`: add `roc: ["pROC"]`, `regression:
  ["gtsummary","broom"]`. (groupcompare/correlation need nothing beyond boot.)
  The R-file fetch loop gains the four new filenames.
- `web/index.html`: four new nav buttons (`data-figure="groupcompare"` etc.).
- `web/app.js`: register the four new forms additively.

## Error handling

Each `fig_*` validates inputs and `stop()`s with plain-language messages
surfaced by the existing worker/app error path (`{ok:false, error}` →
`#stats`). Column-picker prevents most type mismatches up front (numeric-only
dropdowns for numeric roles). CSV parse errors are shown before any analysis
runs.

## Testing

- `testthat` per `fig_*` with synthetic data: assert the figure/table is
  produced (`<svg`/`<table`), the `text` contains the expected statistic
  (p-value, AUC, r, OR/HR), and error paths fire (bad types, wrong group/outcome
  cardinality). Pin one known-value case per analysis (e.g. a fixed dataset
  whose Pearson r / AUC is known) so the stat is verified, not just present.
- Full suite stays WARN 0 via `devtools::test()`.
- One Playwright e2e: upload a fixture CSV, pick columns via the shared picker,
  render one column-based analysis (group comparison), assert an `<svg>` appears
  — exercising csv.js + columnpicker.js + a base-stats `fig_*` end-to-end in
  webR. ROC/regression validated by R tests (their lazy webR downloads are
  covered by KM's precedent that lazy install works in-browser).

## Out of scope (this iteration)

- Refactoring the KM form onto the shared column picker.
- Multiple-testing correction, model diagnostics/assumption checks beyond the
  parametric/nonparametric toggle, interaction terms, stepwise selection.
- Paired tests, repeated-measures, mixed models.
- Saving/loading analysis specs (the JSON-spec reproducibility idea from the
  base spec applies but is not built here).

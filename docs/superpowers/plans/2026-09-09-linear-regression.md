# Linear Regression (continuous-outcome Table 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a seventh guided analysis — univariable + multivariable **linear regression** for a continuous outcome — producing a clinical "Table 3" (unadjusted β beside adjusted β, t-based 95% CI, p), an adjusted-β forest plot, a residuals-vs-fitted and Q-Q diagnostics pair, base-R advisories, a downloadable `lm` script, a landing page, and a `linear-confounding` statistical-validation case.

**Architecture:** `R/linear.R` is `R/logistic.R` with `lm` in place of `glm(binomial)`, no exponentiation, and linear-model diagnostics. `web/guided/linear/` is `web/guided/logistic/` with the event-value picker removed and the outcome dropdown filtered to numeric columns. The validation harness gains a sibling display kind `coef_table` that shares the `ratio_table` machinery through keyword parameters whose defaults leave cox/logistic untouched.

**Tech Stack:** R (base `stats::lm`, `confint`, `shapiro.test`, `cooks.distance`, `ggplot2`, `svglite`) as the `manuscriptfigures` package; webR delivery; vanilla-JS guided shell; testthat, plain-Node unit tests, Playwright; Python (`stats-validation/.venv`) for Path B and the comparator.

**Spec:** `docs/superpowers/specs/2026-09-09-linear-regression-design.md`

## Global Constraints

- **Figure key is `linear`** everywhere (dispatch switch, `data-figure` button, form registry, worker fetch list, case.json `figure`, registry `key`). R function is `fig_linear`. Nav label is exactly `Linear regression`. Landing slug is `linear-regression`.
- **No new R package, no `DESCRIPTION` change, no `EXTRA_PACKAGES` entry.** Base `stats` + `ggplot2` + `svglite` only. No `lmtest`, `car`, `cowplot`, `broom`.
- **WARN 0 is a hard gate.** Run the R suite with `Rscript -e 'devtools::test()'` (never `testthat::test_file`). `[ FAIL 0 | WARN 0 | ... ]` required. ggplot2 4.x: `linewidth` not `size`; `geom_errorbar(orientation = "y")` not `geom_errorbarh`. Never wrap your own `lm` call in `suppressWarnings()`.
- **CIs are t-based** from `stats::confint(fit, level = 0.95)`. Coefficients are **not exponentiated**.
- **Cell format** is `"%.2f (%.2f to %.2f, %s)"` with the word `to`, ASCII hyphen-minus for negatives, `p<0.001` / `p=%.3f`. A cell reads `not reliably estimated` when est/lo/hi/p are not all finite. Reference rows' effect cells read `0 (reference)` in HTML.
- **`web/R/` is a gitignored build copy.** Before any e2e/serve: `rm -rf web/R && cp -R R web/R`.
- **Every new `*.test.mjs` is appended to `test:unit` in `package.json` in the same commit that creates it.**
- **A `web/` source change requires `make -C stats-validation all` in the same commit** (it regenerates `web/validation.html`). During Tasks 6–11 the pipeline has no `linear` case yet, so `make all` regenerates the digest only; run it and commit its output with each `web/` commit. It exits non-zero by design (`logistic-dirty`), and that is not a failure.
- **Path B independence.** The Python implementer (Task 14) reads ONLY `stats-validation/spec/linear-confounding.md`, `stats-validation/python/INTERFACES.md`, and `stats-validation/python/tests/test_linear.py`. Never `R/`, never `web/`, never `results/`. State this prohibition verbatim in that subagent's prompt.
- Commit messages end with the attribution trailer in force for the session.

---

## File Structure

**Create:**
- `data-raw/linear-demo-generator.R` — frozen synthetic demo; writes the two generated files below.
- `tests/testthat/fixtures/linear-demo.csv` — GENERATED. Shared by the e2e test and the validation case.
- `web/guided/linear/demo-data.js` — GENERATED (`LINEAR_DEMO`).
- `R/linear.R` — `fig_linear(spec)` + `.linear_*` helpers → `list(svg=, text=, code=)`.
- `tests/testthat/test-linear.R` — R unit tests.
- `web/guided/linear/spec.js` (+ `spec.test.mjs`) — `buildLinearSpec`; re-exports `distinctValues`, `mostFrequent`.
- `web/guided/linear/demo.js` (+ `demo.test.mjs`) — `DEMO_TABLE`, `DEFAULT_DEMO_STATE`, `buildLinearDemoSpec`.
- `web/guided/linear/content.js` — `UNDERSTAND_SECTIONS`, `renderUnderstand`, `EXAMPLE_INTRO_HTML`, `renderLinearExperiments`.
- `web/guided/linear/analyze-form.js` (+ `analyze-form.test.mjs`) — `renderLinearAnalyzeForm`.
- `web/guided/linear/guided-linear.js` — `createGuidedShell` config → `renderGuidedLinear`.
- `tests/e2e/linear-guided.spec.js` — Playwright.
- `stats-validation/cases/linear-confounding/{case.json,data.csv}`.
- `stats-validation/spec/linear-confounding.md` — transcribed from `R/linear.R` (source-access agent).
- `stats-validation/python/tests/test_linear.py` — acceptance tests (source-access agent writes; clean-room agent turns green).
- `stats-validation/python/validate/linear.py`, `stats-validation/python/DECISIONS-linear.md` — clean-room agent.

**Modify:**
- `R/dispatch.R` — `linear = fig_linear(spec),` in the switch.
- `web/lib/modelform.js` (+ `modelform.test.mjs`) — `requireEventValue` option on `renderReadiness`.
- `web/worker.js` — `"linear.R"` in the boot fetch loop.
- `web/app.js`, `web/index.html`, `web/sw.js` (`CACHE` v12 → v13), `scripts/pages/html.mjs` lede, `web/guided/understand-sections.test.mjs`, `tests/e2e/smoke.spec.js`, `package.json`.
- `scripts/pages/registry.mjs` — `linear-regression` entry; then `npm run build:examples && npm run build:pages`.
- `stats-validation/Makefile`, `harness/build-spec.mjs` (+ test), `harness/run-script.R`, `python/validate/cli.py`, `python/INTERFACES.md`, `compare/compare.py` (+ `compare/tests/test_compare.py`), `build_scorecard.py`, `e2e/compare-text.mjs`, `e2e/webr-parity.spec.js`, `expected-findings.json`.
- `CLAUDE.md`.

**Shared helpers reused, never redefined:** `%||%`, `.svg_string`, `.ratio_reportable` (`R/dispatch.R`); `.esc`, `.numeric_col`, `.char_col` (`R/summarize.R`); `.km_palette` (`R/km.R`); `.fig_theme` (`R/themes.R`); `.script_assemble`, `.script_dep`, `.with_citation` (`R/script.R`); and from `R/logistic.R` the pure covariate helpers `.logistic_is_numeric`, `.logistic_term_label`, `.logistic_most_frequent`, `.logistic_increment`, `.logistic_vif` — all package-internal and on the search path.

---

## Task 1: Frozen demo dataset (generator + fixture + demo-data.js)

**Files:**
- Create: `data-raw/linear-demo-generator.R`
- Generate: `tests/testthat/fixtures/linear-demo.csv`, `web/guided/linear/demo-data.js`

**Interfaces:**
- Produces: `LINEAR_DEMO = { version, label, columns: ["arm","age","stage","los"], rows: [...] }` (320 rows), and the CSV with the same four columns. Outcome column is `los` (hospital length of stay, days, one decimal). The generator's `stopifnot` block guarantees: the crude arm 95% CI straddles 0, the adjusted arm CI lies entirely below 0, and neither the Shapiro–Wilk nor the Breusch–Pagan advisory fires on the default model. Tasks 8, 10 and 12 rely on all three.

- [ ] **Step 1: Write the generator**

```r
# data-raw/linear-demo-generator.R
# Frozen linear-regression demo. Continuous outcome `los` (hospital length of
# stay, days), two arms (Standard care / New treatment), baseline age and ordinal
# stage (I/II/III). Engineered so age + stage confound the arm effect: the
# UNADJUSTED arm coefficient is near 0, but adjusting reveals a ~1.5-day shorter
# stay. Byte-reproducible; bump LINEAR_DEMO.version on any change.
#
# Retuning guide. The teaching point is the gap between the crude and adjusted
# arm coefficient, set by: how much older / later-stage the New treatment arm is
# (age shift and the two stage probability vectors); how strongly age and stage
# drive `los` (0.08 and 1.5 below); and the true treatment effect (-1.5). The
# verification block at the end stops the script unless the story holds AND the
# default model is quiet on the residual advisories; if it stops, change the
# seed, never the assertions. Never hand-edit the generated outputs.
set.seed(31)
n_std <- 170
n_new <- 150
n <- n_std + n_new
arm <- c(rep("Standard care", n_std), rep("New treatment", n_new))
treated <- arm == "New treatment"

age <- round(rnorm(n, 60, 9))
age <- round(age + 6 * treated)
stage <- ifelse(treated,
  sample(c("I", "II", "III"), n, replace = TRUE, prob = c(0.22, 0.35, 0.43)),
  sample(c("I", "II", "III"), n, replace = TRUE, prob = c(0.55, 0.32, 0.13)))
stage_idx <- as.integer(factor(stage, levels = c("I", "II", "III")))

los <- 6 + 0.08 * (age - 60) + 1.5 * (stage_idx - 1) - 1.5 * treated + rnorm(n, 0, 2.2)
los <- round(pmax(los, 1), 1)

out <- data.frame(arm = arm, age = age, stage = stage, los = los,
                  stringsAsFactors = FALSE)

# ---- verification: the story the Understand/Example copy tells must hold.
dat <- out
dat$arm <- stats::relevel(factor(dat$arm), ref = "Standard care")
dat$stage <- factor(dat$stage)
crude <- stats::confint(stats::lm(los ~ arm, data = dat))["armNew treatment", ]
fit <- stats::lm(los ~ arm + age + stage, data = dat)
adj <- stats::confint(fit)["armNew treatment", ]
stopifnot(crude[1] < 0, crude[2] > 0)     # crude CI straddles 0
stopifnot(adj[2] < 0)                      # adjusted CI entirely below 0
stopifnot(stats::shapiro.test(stats::resid(fit))$p.value > 0.10)
aux <- stats::lm(stats::resid(fit)^2 ~ stats::fitted(fit))
bp <- nrow(dat) * summary(aux)$r.squared
stopifnot(stats::pchisq(bp, df = 1, lower.tail = FALSE) > 0.10)
cat(sprintf("crude arm: %.2f to %.2f; adjusted arm: %.2f to %.2f\n",
            crude[1], crude[2], adj[1], adj[2]))

stopifnot(!any(grepl('[",\r\n]', unlist(lapply(out, as.character)))))
write.csv(out, "tests/testthat/fixtures/linear-demo.csv",
          row.names = FALSE, quote = FALSE)

rows_list <- lapply(seq_len(nrow(out)), function(i) as.list(out[i, ]))
rows_json <- jsonlite::toJSON(rows_list, auto_unbox = TRUE, digits = NA)
js <- paste0(
  "// GENERATED by data-raw/linear-demo-generator.R — do not hand-edit.\n",
  "export const LINEAR_DEMO = {\n",
  '  version: "1.0.0",\n',
  '  label: "Synthetic demonstration data",\n',
  '  columns: ["arm", "age", "stage", "los"],\n',
  "  rows: ", rows_json, "\n};\n")
dir.create("web/guided/linear", showWarnings = FALSE)
writeLines(js, "web/guided/linear/demo-data.js")
cat("md5(csv):", unname(tools::md5sum("tests/testthat/fixtures/linear-demo.csv")), "\n")
```

- [ ] **Step 2: Run it from the repo root**

Run: `Rscript data-raw/linear-demo-generator.R`
Expected: prints the two CIs and an md5; no `stopifnot` error. If it stops, change `set.seed(31)` to the next integer and rerun until it passes; record the final seed in the commit message.

- [ ] **Step 3: Sanity-check the outputs**

Run: `head -3 tests/testthat/fixtures/linear-demo.csv && wc -l tests/testthat/fixtures/linear-demo.csv && head -c 300 web/guided/linear/demo-data.js`
Expected: header `arm,age,stage,los`, 321 lines, and a JS module beginning with the GENERATED comment.

- [ ] **Step 4: Commit**

```bash
git add data-raw/linear-demo-generator.R tests/testthat/fixtures/linear-demo.csv web/guided/linear/demo-data.js
git commit -m "feat(linear): frozen synthetic demo dataset for linear regression"
```

---

## Task 2: R core — prep, fits, coefficient table, lead sentence, dispatch

**Files:**
- Create: `R/linear.R`
- Create: `tests/testthat/test-linear.R`
- Modify: `R/dispatch.R` (the `switch`)

**Interfaces:**
- Consumes: the shared helpers listed under File Structure.
- Produces: `fig_linear(spec) -> list(svg, text)` (code added in Task 5). `spec$roles$outcome` (one numeric column), `spec$roles$covariates` (list), `spec$options$ref_levels`, `spec$options$increments`. Helpers for later tasks: `.linear_prep(spec) -> list(df, covs, cov_types, ref_levels, incr, n, n_terms, n_dropped)`, `.linear_fits(df, covs) -> list(uni = named list of list(fit, warn), joint = list(fit, warn))`, `.linear_terms(fit) -> named list of list(est, lo, hi, p)`, `.coef_reportable(est, lo, hi)`, `.linear_cell(terms, key)`, `.linear_pfmt(p)`, `.linear_rows(p, fits)`, `.linear_table_html(rows)`.

- [ ] **Step 1: Write the failing tests**

```r
# tests/testthat/test-linear.R
# Continuous outcome with a real arm effect confounded by age. Treated patients
# are older, and age raises the outcome, so the UNADJUSTED arm coefficient is
# pulled towards 0 and only adjusting for age reveals the full -2.0 effect.
mk_lin_rows <- function() {
  set.seed(41)
  n <- 240
  arm <- rep(c("Control", "Treated"), each = n / 2)
  age <- round(rnorm(n, 60, 10) + 6 * (arm == "Treated"), 1)
  y <- round(5 + 0.1 * (age - 60) - 2 * (arm == "Treated") + rnorm(n, 0, 2), 2)
  lapply(seq_len(n), function(i) list(los = y[i], arm = arm[i], age = age[i]))
}
sc_lin <- function(rows, covariates = c("arm", "age"), ref_levels = NULL,
                   increments = NULL, outcome = "los") {
  list(figure = "linear", data = rows,
       roles = list(outcome = outcome, covariates = as.list(covariates)),
       options = list(ref_levels = ref_levels %||% list(),
                      increments = increments %||% list()))
}
tsv_cell <- function(text, label, col) {
  line <- grep(paste0("^", label, "\t"), strsplit(text, "\n")[[1]], value = TRUE)
  expect_length(line, 1)
  strsplit(line, "\t")[[1]][col]
}
tsv_adj_cell <- function(text, label) tsv_cell(text, label, 3)
tsv_unadj_cell <- function(text, label) tsv_cell(text, label, 2)
# The three numbers of a cell "-1.23 (-2.10 to -0.36, p=0.006)".
cell_nums <- function(cell) {
  m <- regmatches(cell, regexec("^(-?[0-9.]+) \\((-?[0-9.]+) to (-?[0-9.]+),", cell))[[1]]
  expect_length(m, 4)
  as.numeric(m[-1])
}

test_that("fig_linear returns an HTML table and text", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_match(out$svg, "Unadjusted β (95% CI, p)", fixed = TRUE)
  expect_true(nzchar(out$text))
})

test_that("cells use the coefficient format with 'to' and a p-value", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  adj <- tsv_adj_cell(out$text, "Treated")
  expect_match(adj, "^-?[0-9]+\\.[0-9]{2} \\(-?[0-9]+\\.[0-9]{2} to -?[0-9]+\\.[0-9]{2}, p[<=][0-9.]+\\)$")
})

test_that("adjusted and unadjusted cells equal lm + confint exactly", {
  rows <- mk_lin_rows()
  out <- fig_linear(sc_lin(rows))
  df <- data.frame(los = sapply(rows, `[[`, "los"),
                   arm = stats::relevel(factor(sapply(rows, `[[`, "arm")), ref = "Control"),
                   age = sapply(rows, `[[`, "age"))
  fit <- stats::lm(los ~ arm + age, data = df)
  ci <- stats::confint(fit)
  expect_equal(cell_nums(tsv_adj_cell(out$text, "Treated")),
               as.numeric(sprintf("%.2f", c(stats::coef(fit)["armTreated"], ci["armTreated", ]))))
  uni <- stats::lm(los ~ age, data = df)
  expect_equal(cell_nums(tsv_unadj_cell(out$text, "age \\(per 1 unit\\)")),
               as.numeric(sprintf("%.2f", c(stats::coef(uni)["age"], stats::confint(uni)["age", ]))))
})

test_that("adjusting for age reveals a larger treatment effect than the crude one", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  adj <- cell_nums(tsv_adj_cell(out$text, "Treated"))[1]
  unadj <- cell_nums(tsv_unadj_cell(out$text, "Treated"))[1]
  expect_true(adj < -1.5 && adj > -2.5)
  expect_true(unadj > adj)
})

test_that("reference level appears, reads 0 (reference) in HTML, and can be overridden", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_match(out$svg, "reference: Control", fixed = TRUE)
  expect_match(out$svg, "0 (reference)", fixed = TRUE)
  expect_false(grepl("1 (reference)", out$svg, fixed = TRUE))
  out2 <- fig_linear(sc_lin(mk_lin_rows(), ref_levels = list(arm = "Treated")))
  expect_match(out2$svg, "reference: Treated", fixed = TRUE)
  expect_match(out2$text, "\nControl\t", fixed = TRUE)
})

test_that("a per-increment rescale multiplies the coefficient and leaves p unchanged", {
  per1 <- fig_linear(sc_lin(mk_lin_rows()))
  per10 <- fig_linear(sc_lin(mk_lin_rows(), increments = list(age = 10)))
  c1 <- tsv_adj_cell(per1$text, "age \\(per 1 unit\\)")
  c10 <- tsv_adj_cell(per10$text, "age \\(per 10 units\\)")
  expect_equal(cell_nums(c10)[1], 10 * cell_nums(c1)[1], tolerance = 0.06)
  expect_equal(sub(".*, (p.*)\\)$", "\\1", c1), sub(".*, (p.*)\\)$", "\\1", c10))
})

test_that("a covariate whose header is not a syntactic R name is estimated", {
  rows <- lapply(mk_lin_rows(), function(r) list(los = r$los, `study arm` = r$arm, age = r$age))
  out <- fig_linear(sc_lin(rows, covariates = c("study arm", "age")))
  expect_match(out$text, "study arm (reference: Control)", fixed = TRUE)
  expect_false(grepl("not reliably estimated", out$text, fixed = TRUE))
})

test_that("lead sentence carries n, R-squared and adjusted R-squared", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_match(out$text, "Multivariable linear regression \\(n = 240\\) of los adjusted for arm, age\\.")
  expect_match(out$text, "\\(R² = 0\\.[0-9]{3}, adjusted R² = -?[0-9]\\.[0-9]{3}\\)")
})

test_that("a single-covariate model is described as univariable, not adjusted", {
  out <- fig_linear(sc_lin(mk_lin_rows(), covariates = "arm"))
  expect_match(out$text, "Univariable linear regression (n = 240) of los with arm as the only covariate.", fixed = TRUE)
  expect_false(grepl("Multivariable", out$text, fixed = TRUE))
})

test_that("a non-numeric outcome errors readably", {
  expect_error(fig_linear(sc_lin(mk_lin_rows(), outcome = "arm", covariates = "age")),
               "Outcome column 'arm' must be numeric")
})

test_that("too few residual degrees of freedom errors readably", {
  expect_error(fig_linear(sc_lin(mk_lin_rows()[c(1:6, 121:126)])),   # both arms, n = 12, 2 terms -> 9 residual df
               "at least 10 residual degrees of freedom")
})

test_that("a constant outcome errors readably", {
  rows <- lapply(mk_lin_rows(), function(r) { r$los <- 3; r })
  expect_error(fig_linear(sc_lin(rows)), "no variation")
})

test_that("a one-level covariate and a missing column error readably", {
  rows <- lapply(mk_lin_rows(), function(r) { r$arm <- "Control"; r })
  expect_error(fig_linear(sc_lin(rows)), "only one level")
  expect_error(fig_linear(sc_lin(mk_lin_rows(), covariates = c("arm", "bmi"))), "not found")
  expect_error(fig_linear(sc_lin(mk_lin_rows(), covariates = character(0))), "at least one covariate")
})

test_that("blank cells are dropped and counted", {
  rows <- mk_lin_rows()
  rows[[1]]$los <- ""; rows[[2]]$age <- ""
  out <- fig_linear(sc_lin(rows))
  expect_match(out$text, "n = 238", fixed = TRUE)
  expect_match(out$text, "2 row(s) with missing values were excluded.", fixed = TRUE)
})

test_that("render_figure routes linear specs and returns ok JSON", {
  js <- jsonlite::toJSON(sc_lin(mk_lin_rows()), auto_unbox = TRUE)
  res <- jsonlite::fromJSON(render_figure(js))
  expect_true(res$ok)
  expect_match(res$svg, "<table", fixed = TRUE)
})

test_that("fig_linear ends with the citation paragraph", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_match(out$text, "\n\nAnalyses were performed with Figura \\(.*ggplot2 package in the browser\\.$")
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "linear")'`
Expected: errors "could not find function fig_linear".

- [ ] **Step 3: Write `R/linear.R` (core) and register the dispatch**

```r
# R/linear.R
# Continuous-outcome linear regression: univariable (unadjusted) coefficient per
# covariate beside the joint-model adjusted coefficient (clinical "Table 3").
# Base stats::lm only — no extra package. CIs are t-based (stats::confint).
#
# The covariate helpers are shared with R/logistic.R (.logistic_is_numeric,
# .logistic_term_label, .logistic_most_frequent, .logistic_increment,
# .logistic_vif): they are pure functions of their inputs and the rule is
# identical here, so they are called, not copied.

# Build the complete-case working frame and covariate metadata.
.linear_prep <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  covs <- unlist(spec$roles$covariates %||% list())
  if (length(covs) == 0) stop("Select at least one covariate.")
  ocol <- spec$roles$outcome
  if (is.null(ocol)) stop("Choose an outcome column.")
  have <- names(rows[[1]])
  for (cl in c(ocol, covs))
    if (!(cl %in% have)) stop(sprintf("Column '%s' not found in the data.", cl))
  # The outcome-specific message: .numeric_col's own wording names a "column",
  # which for the outcome role points the user at the wrong dropdown.
  if (!.logistic_is_numeric(rows, ocol))
    stop(sprintf("Outcome column '%s' must be numeric.", ocol))
  y <- .numeric_col(rows, ocol)

  cov_types <- setNames(
    vapply(covs, function(cl) if (.logistic_is_numeric(rows, cl)) "numeric" else "categorical",
           character(1)), covs)
  ref_levels <- spec$options$ref_levels %||% list()
  increments <- spec$options$increments %||% list()
  incr <- setNames(vapply(covs, function(cl)
    if (cov_types[[cl]] == "numeric") .logistic_increment(increments, cl) else NA_real_,
    numeric(1)), covs)

  cols <- list(.y = y)
  for (cl in covs) {
    if (cov_types[[cl]] == "numeric") cols[[cl]] <- .numeric_col(rows, cl)
    else { v <- .char_col(rows, cl); v[!is.na(v) & v == ""] <- NA; cols[[cl]] <- v }
  }
  df <- as.data.frame(cols, stringsAsFactors = FALSE, check.names = FALSE)
  n_before <- nrow(df)
  df <- df[stats::complete.cases(df), , drop = FALSE]
  n_dropped <- n_before - nrow(df)

  # Sample size is checked before covariate structure: with too few rows every
  # downstream diagnosis is a symptom of the same problem.
  n_terms <- sum(vapply(covs, function(cl)
    if (cov_types[[cl]] == "numeric") 1L else max(0L, length(unique(df[[cl]])) - 1L),
    integer(1)))
  resid_df <- nrow(df) - 1L - n_terms
  if (resid_df < 10) stop(sprintf(paste0(
    "Too few observations (n = %d) for %d model term(s); at least 10 residual ",
    "degrees of freedom are needed."), nrow(df), n_terms))

  for (cl in covs) if (cov_types[[cl]] == "numeric" && incr[[cl]] != 1)
    df[[cl]] <- df[[cl]] / incr[[cl]]

  for (cl in covs) if (cov_types[[cl]] == "categorical") {
    ref <- as.character(ref_levels[[cl]] %||% .logistic_most_frequent(df[[cl]]))
    lv <- unique(df[[cl]])
    if (length(lv) < 2) stop(sprintf("Covariate '%s' has only one level after removing missing values.", cl))
    if (!ref %in% lv) ref <- .logistic_most_frequent(df[[cl]])
    df[[cl]] <- stats::relevel(factor(df[[cl]]), ref = ref)
  }
  if (stats::var(df$.y) == 0)
    stop("The outcome has no variation after removing missing values.")

  list(df = df, covs = covs, cov_types = cov_types, ref_levels = ref_levels,
       incr = incr, n = nrow(df), n_terms = n_terms, n_dropped = n_dropped)
}

# Fit one lm, capturing (not suppressing) fit warnings so an unclean fit can be
# flagged. muffleWarning keeps it off the WARN-0 gate.
.linear_fit_one <- function(formula, df) {
  warn <- NULL
  fit <- withCallingHandlers(
    stats::lm(formula, data = df),
    warning = function(w) { warn <<- conditionMessage(w); invokeRestart("muffleWarning") })
  list(fit = fit, warn = warn)
}

# Univariable lm per covariate + one joint model.
.linear_fits <- function(df, covs) {
  uni <- lapply(covs, function(cl)
    .linear_fit_one(stats::as.formula(sprintf(".y ~ `%s`", cl)), df))
  names(uni) <- covs
  joint_f <- stats::as.formula(paste0(".y ~ ",
    paste(sprintf("`%s`", covs), collapse = " + ")))
  list(uni = uni, joint = .linear_fit_one(joint_f, df))
}

# est / lo / hi / p per non-intercept coefficient, keyed by coefficient name.
# confint.lm is t-based (qt on the residual df). An aliased coefficient (a
# column that is a linear combination of others) is NA in coef() and confint()
# and absent from summary()'s matrix, so every field of it comes back NA.
.linear_terms <- function(fit) {
  cf <- stats::coef(fit)
  ci <- stats::confint(fit, level = 0.95)
  sm <- summary(fit)$coefficients
  keys <- setdiff(names(cf), "(Intercept)")
  out <- lapply(keys, function(k) list(
    est = unname(cf[k]), lo = unname(ci[k, 1]), hi = unname(ci[k, 2]),
    p = if (k %in% rownames(sm)) unname(sm[k, "Pr(>|t|)"]) else NA_real_))
  names(out) <- keys
  out
}

# Is a coefficient reportable? Finite estimate and finite bounds — there is no
# ratio-scale window here (.ratio_reportable is for HR/OR). Vectorised.
.coef_reportable <- function(est, lo, hi) is.finite(est) & is.finite(lo) & is.finite(hi)

.linear_pfmt <- function(p) if (p < 0.001) "p<0.001" else sprintf("p=%.3f", p)

# "%.2f (%.2f to %.2f, p)" — the word "to", because a coefficient can be
# negative and "-2.10–-0.36" is unreadable.
.linear_cell <- function(terms, key) {
  t <- terms[[key]]
  if (is.null(t) || !.coef_reportable(t$est, t$lo, t$hi) || !is.finite(t$p))
    return("not reliably estimated")
  sprintf("%.2f (%.2f to %.2f, %s)", t$est, t$lo, t$hi, .linear_pfmt(t$p))
}

# One display row per covariate LEVEL (reference marked); numeric rows label
# the increment. A term leading with two spaces marks an indented level row.
.linear_rows <- function(p, fits) {
  rows <- list()
  jt <- .linear_terms(fits$joint$fit)
  for (cl in p$covs) {
    ut <- .linear_terms(fits$uni[[cl]]$fit)
    tl <- .logistic_term_label(cl)
    if (p$cov_types[[cl]] == "numeric") {
      k <- p$incr[[cl]]
      unit <- if (k == 1) "per 1 unit" else sprintf("per %g units", k)
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (%s)", cl, unit),
        unadj = .linear_cell(ut, tl), adj = .linear_cell(jt, tl))
    } else {
      lv <- levels(p$df[[cl]])
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (reference: %s)", cl, lv[1]),
        unadj = "", adj = "")
      for (l in lv[-1]) {
        key <- paste0(tl, l)
        rows[[length(rows) + 1]] <- list(term = paste0("  ", l),
          unadj = .linear_cell(ut, key), adj = .linear_cell(jt, key))
      }
    }
  }
  rows
}

# HTML table (reuses .esc). "(reference:" header rows keep blank effect cells;
# any other blank cell reads "0 (reference)" — the null of a difference is 0.
.linear_table_html <- function(disp_rows) {
  header <- "<tr><th>Characteristic</th><th>Unadjusted β (95% CI, p)</th><th>Adjusted β (95% CI, p)</th></tr>"
  body <- vapply(disp_rows, function(r) {
    is_header <- grepl("\\(reference:", r$term)
    indent <- startsWith(r$term, "  ")
    label <- .esc(trimws(r$term))
    if (indent) label <- paste0("<span class=\"lvl\">", label, "</span>")
    if (is_header) { unadj <- ""; adj <- "" }
    else {
      unadj <- if (nzchar(r$unadj)) .esc(r$unadj) else "0 (reference)"
      adj <- if (nzchar(r$adj)) .esc(r$adj) else "0 (reference)"
    }
    sprintf("<tr><td>%s</td><td>%s</td><td>%s</td></tr>", label, unadj, adj)
  }, character(1))
  paste0("<table class=\"table1\"><thead>", header, "</thead><tbody>",
         paste(body, collapse = ""), "</tbody></table>")
}

# The methods paragraph's opening sentence. With a single covariate there is no
# joint model: saying "adjusted for" there would be false in a sentence built
# to be pasted into a manuscript.
.linear_lead <- function(spec, p, jfit) {
  s <- summary(jfit)
  r2 <- sprintf("(R² = %.3f, adjusted R² = %.3f)", s$r.squared, s$adj.r.squared)
  ocol <- spec$roles$outcome
  if (length(p$covs) == 1)
    sprintf(paste0("Univariable linear regression (n = %d) of %s with %s as the only ",
                   "covariate. No adjustment was made for other variables, so the ",
                   "unadjusted and adjusted columns report the same model %s."),
            p$n, ocol, p$covs[[1]], r2)
  else
    sprintf(paste0("Multivariable linear regression (n = %d) of %s adjusted for %s. ",
                   "Unadjusted coefficients are from single-covariate models; adjusted ",
                   "coefficients are from the joint model %s."),
            p$n, ocol, paste(p$covs, collapse = ", "), r2)
}

fig_linear <- function(spec) {
  p <- .linear_prep(spec)
  fits <- .linear_fits(p$df, p$covs)
  disp_rows <- .linear_rows(p, fits)
  jfit <- fits$joint$fit

  table_html <- .linear_table_html(disp_rows)
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div></div>",
                       table_html)
  tsv <- paste(c(paste(c("Characteristic", "Unadjusted β (95% CI, p)",
                         "Adjusted β (95% CI, p)"), collapse = "\t"),
                 vapply(disp_rows, function(r)
                   paste(c(trimws(r$term), r$unadj, r$adj), collapse = "\t"), character(1))),
               collapse = "\n")
  drop_note <- if (p$n_dropped > 0)
    sprintf(" %d row(s) with missing values were excluded.", p$n_dropped) else ""
  methods <- paste0(.linear_lead(spec, p, jfit), drop_note)
  text <- .with_citation(paste0(tsv, "\n\n", methods), "ggplot2")
  list(svg = svg_field, text = text)
}
```

In `R/dispatch.R`, add after the `logistic` line of the `switch`:

```r
      linear  = fig_linear(spec),
```

- [ ] **Step 4: Run the tests**

Run: `Rscript -e 'devtools::test(filter = "linear")'`
Expected: all pass, WARN 0. If the "adjusting for age" test's window fails, the numbers are seed-specific to `set.seed(41)` — do not widen the window; check the model instead (the true effect is -2).

- [ ] **Step 5: Run the full suite**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | ... ]`.

- [ ] **Step 6: Commit**

```bash
git add R/linear.R R/dispatch.R tests/testthat/test-linear.R
git commit -m "feat(linear): fig_linear core — lm Table 3 with t-based CIs"
```

---
## Task 3: R diagnostics — advisory sentences

**Files:**
- Modify: `R/linear.R` (add helpers; replace `fig_linear`)
- Modify: `tests/testthat/test-linear.R` (append)

**Interfaces:**
- Consumes: `.linear_prep`, `.linear_fits`, `.linear_terms`, `.linear_pfmt`, `.linear_lead` (Task 2); `.logistic_vif(df, num_covs)` (`R/logistic.R`).
- Produces: `.linear_other_warn(warns) -> character(1)`, `.linear_bp(fit) -> list(statistic, p)`, and the exact advisory sentences below. Task 13's spec and Task 12's comparator regexes are transcribed from these strings, so they are the contract:
  - aliased: `" CAUTION: one or more covariates were dropped from the adjusted model because they are linear combinations of others (their cells read \"not reliably estimated\"); remove a redundant variable."`
  - other-warn: `" CAUTION: fitting reported a numerical warning (\"<msg>\"); the coefficients above may come from a model that did not fit cleanly. Check the covariates for extreme values, and seek statistical review."`
  - obs/term: `" CAUTION: about %.1f observations per model term (fewer than 10); the adjusted estimates may be unstable and are best treated as exploratory."`
  - Shapiro: `" Residuals depart from normality (Shapiro–Wilk %s); with n = %d the confidence intervals are %s."` where the tail is `still approximately valid by the central limit theorem` (n ≥ 30) or `not reliable; consider transforming the outcome or a non-parametric comparison` (n < 30). Only when 3 ≤ n ≤ 5000 and p < 0.05.
  - BP: `" CAUTION: residual variance is not constant across fitted values (Breusch–Pagan %s); the standard errors may be misleading, and robust standard errors or an outcome transform are worth considering."` when p < 0.05.
  - VIF and Cook's: logistic's exact wording.

- [ ] **Step 1: Append the failing tests**

```r
test_that("an aliased covariate is unreportable in the adjusted column and flagged", {
  rows <- lapply(mk_lin_rows(), function(r) { r$age2 <- r$age * 2; r })
  out <- fig_linear(sc_lin(rows, covariates = c("arm", "age", "age2")))
  expect_equal(tsv_adj_cell(out$text, "age2 \\(per 1 unit\\)"), "not reliably estimated")
  expect_match(tsv_unadj_cell(out$text, "age2 \\(per 1 unit\\)"), "^-?[0-9]")
  expect_match(out$text, "CAUTION: one or more covariates were dropped from the adjusted model", fixed = TRUE)
})

test_that("a well-conditioned model raises no aliased, VIF or observations-per-term caution", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_false(grepl("linear combinations", out$text, fixed = TRUE))
  expect_false(grepl("VIF", out$text, fixed = TRUE))
  expect_false(grepl("observations per model term", out$text, fixed = TRUE))
  expect_false(grepl("numerical warning", out$text, fixed = TRUE))
})

test_that("observations-per-term caution fires under 10 per term", {
  set.seed(9)
  n <- 40
  rows <- lapply(seq_len(n), function(i) list(
    los = round(rnorm(1, 6, 2), 1), arm = c("A", "B")[i %% 2 + 1],
    site = c("s1", "s2", "s3", "s4", "s5")[i %% 5 + 1], age = 50 + i))
  # terms = 1 (arm) + 4 (site) + 1 (age) = 6; 40/6 = 6.7 < 10; residual df = 33.
  out <- fig_linear(sc_lin(rows, covariates = c("arm", "site", "age")))
  expect_match(out$text, "CAUTION: about 6\\.7 observations per model term \\(fewer than 10\\)")
})

test_that("Shapiro-Wilk caution fires on skewed residuals, with the large-n tail", {
  set.seed(5)
  rows <- lapply(mk_lin_rows(), function(r) { r$los <- round(r$los + rexp(1, 0.3), 2); r })
  out <- fig_linear(sc_lin(rows))
  expect_match(out$text, "Residuals depart from normality \\(Shapiro–Wilk p[<=][0-9.]+\\); with n = 240 the confidence intervals are still approximately valid by the central limit theorem\\.")
})

test_that("Shapiro-Wilk caution uses the small-n tail under 30 observations", {
  set.seed(6)
  rows <- lapply(1:25, function(i) list(los = round(rexp(1, 0.2), 2), age = 40 + i))
  out <- fig_linear(sc_lin(rows, covariates = "age"))
  expect_match(out$text, "with n = 25 the confidence intervals are not reliable; consider transforming the outcome", fixed = TRUE)
})

test_that("Breusch-Pagan caution fires on heteroscedastic residuals", {
  set.seed(7)
  rows <- lapply(1:300, function(i) {
    age <- 30 + i / 4
    list(los = round(2 + 0.1 * age + rnorm(1, 0, 0.05 * age), 2), age = age)
  })
  out <- fig_linear(sc_lin(rows, covariates = "age"))
  expect_match(out$text, "CAUTION: residual variance is not constant across fitted values \\(Breusch–Pagan p[<=][0-9.]+\\)")
})

test_that(".linear_bp reproduces n * R^2 of squared residuals on fitted values", {
  df <- data.frame(y = c(1, 3, 2, 5, 4, 6, 8, 7, 9, 12), x = 1:10)
  fit <- stats::lm(y ~ x, data = df)
  aux <- stats::lm(stats::resid(fit)^2 ~ stats::fitted(fit))
  bp <- .linear_bp(fit)
  expect_equal(bp$statistic, 10 * summary(aux)$r.squared)
  expect_equal(bp$p, stats::pchisq(bp$statistic, df = 1, lower.tail = FALSE))
})

test_that("multicollinearity (VIF) is flagged for near-duplicate continuous covariates", {
  set.seed(8)
  rows <- lapply(mk_lin_rows(), function(r) { r$age_dup <- r$age + rnorm(1, 0, 0.3); r })
  out <- fig_linear(sc_lin(rows, covariates = c("arm", "age", "age_dup")))
  expect_match(out$text, "CAUTION: multicollinearity among continuous covariates \\(largest VIF = [0-9.]+, above the usual threshold of 5\\)")
})

test_that("influential observations (Cook's distance) are flagged when present", {
  rows <- mk_lin_rows()
  rows[[1]]$los <- 60
  out <- fig_linear(sc_lin(rows))
  expect_match(out$text, "[0-9]+ observation\\(s\\) were flagged as influential \\(Cook's distance > 4/n\\)")
})

test_that(".linear_other_warn speaks up for a captured fit warning and stays quiet otherwise", {
  expect_equal(.linear_other_warn(list(NULL, NULL)), "")
  msg <- .linear_other_warn(list(NULL, "something odd"))
  expect_match(msg, "CAUTION: fitting reported a numerical warning (\"something odd\")", fixed = TRUE)
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "linear")'`
Expected: the new tests fail (no caution sentences, `.linear_bp` / `.linear_other_warn` not found).

- [ ] **Step 3: Add the helpers and replace `fig_linear`**

Add above `fig_linear` in `R/linear.R`:

```r
# Advisory for any captured lm warning. Returns "" when there is nothing to
# say. Advisory only — it never gates a fit or changes a number.
.linear_other_warn <- function(warns) {
  w <- unlist(warns, use.names = FALSE)
  w <- w[!is.na(w) & nzchar(w)]
  if (length(w) == 0) return("")
  sprintf(paste0(" CAUTION: fitting reported a numerical warning (\"%s\"); the ",
                 "coefficients above may come from a model that did not fit cleanly. ",
                 "Check the covariates for extreme values, and seek statistical review."),
          w[[1]])
}

# Koenker's studentized Breusch-Pagan, hand-rolled: regress the squared residuals
# on the fitted values; LM = n * R^2 of that auxiliary fit; chi-square on 1 df.
# Base stats only (no lmtest).
.linear_bp <- function(fit) {
  r2 <- stats::resid(fit)^2
  fv <- stats::fitted(fit)
  aux <- stats::lm(r2 ~ fv)
  lm_stat <- length(r2) * summary(aux)$r.squared
  list(statistic = lm_stat, p = stats::pchisq(lm_stat, df = 1, lower.tail = FALSE))
}

# Shapiro-Wilk on the residuals, in its supported size window only. NULL means
# "not assessed" (n outside [3, 5000]) or the test could not run (identical
# residuals) — never a stop.
.linear_shapiro <- function(fit) {
  r <- stats::resid(fit)
  if (length(r) < 3 || length(r) > 5000) return(NULL)
  tryCatch(stats::shapiro.test(r)$p.value, error = function(e) NULL)
}
```

Replace `fig_linear` with:

```r
fig_linear <- function(spec) {
  p <- .linear_prep(spec)
  fits <- .linear_fits(p$df, p$covs)
  disp_rows <- .linear_rows(p, fits)
  jfit <- fits$joint$fit

  # ---- Model-quality advisories. Every one appends a sentence to the methods
  # text and never blocks a fit or changes a number.
  jt <- .linear_terms(jfit)
  aliased <- any(vapply(jt, function(t) is.na(t$est), logical(1)))
  aliased_line <- if (aliased)
    paste0(" CAUTION: one or more covariates were dropped from the adjusted model ",
           "because they are linear combinations of others (their cells read ",
           "\"not reliably estimated\"); remove a redundant variable.") else ""

  other_warn_line <- .linear_other_warn(
    c(list(fits$joint$warn), lapply(fits$uni, function(f) f$warn)))

  opt <- p$n / p$n_terms
  opt_line <- if (opt < 10)
    sprintf(paste0(" CAUTION: about %.1f observations per model term (fewer than 10); ",
                   "the adjusted estimates may be unstable and are best treated as ",
                   "exploratory."), opt) else ""

  sw_p <- .linear_shapiro(jfit)
  sw_line <- if (!is.null(sw_p) && sw_p < 0.05)
    sprintf(paste0(" Residuals depart from normality (Shapiro–Wilk %s); with n = %d ",
                   "the confidence intervals are %s."),
            .linear_pfmt(sw_p), p$n,
            if (p$n >= 30) "still approximately valid by the central limit theorem"
            else "not reliable; consider transforming the outcome or a non-parametric comparison")
    else ""

  bp <- .linear_bp(jfit)
  bp_line <- if (is.finite(bp$p) && bp$p < 0.05)
    sprintf(paste0(" CAUTION: residual variance is not constant across fitted values ",
                   "(Breusch–Pagan %s); the standard errors may be misleading, and robust ",
                   "standard errors or an outcome transform are worth considering."),
            .linear_pfmt(bp$p)) else ""

  num_covs <- names(p$cov_types)[p$cov_types == "numeric"]
  vif <- .logistic_vif(p$df, num_covs)
  vif_line <- if (!is.null(vif) && any(vif > 5)) {
    largest <- if (any(!is.finite(vif))) "effectively infinite" else sprintf("%.1f", max(vif))
    sprintf(paste0(" CAUTION: multicollinearity among continuous covariates ",
                   "(largest VIF = %s, above the usual threshold of 5); consider dropping ",
                   "a redundant variable."), largest)
  } else ""

  cd <- stats::cooks.distance(jfit)
  n_infl <- sum(cd > 4 / length(cd), na.rm = TRUE)
  infl_line <- if (n_infl > 0)
    sprintf(paste0(" %d observation(s) were flagged as influential (Cook's distance > 4/n); ",
                   "inspect them for data-entry errors."), n_infl) else ""

  table_html <- .linear_table_html(disp_rows)
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div></div>",
                       table_html)
  tsv <- paste(c(paste(c("Characteristic", "Unadjusted β (95% CI, p)",
                         "Adjusted β (95% CI, p)"), collapse = "\t"),
                 vapply(disp_rows, function(r)
                   paste(c(trimws(r$term), r$unadj, r$adj), collapse = "\t"), character(1))),
               collapse = "\n")
  drop_note <- if (p$n_dropped > 0)
    sprintf(" %d row(s) with missing values were excluded.", p$n_dropped) else ""
  methods <- paste0(.linear_lead(spec, p, jfit), aliased_line, other_warn_line, opt_line,
                    sw_line, bp_line, vif_line, infl_line, drop_note)
  text <- .with_citation(paste0(tsv, "\n\n", methods), "ggplot2")
  list(svg = svg_field, text = text)
}
```

- [ ] **Step 4: Run the tests**

Run: `Rscript -e 'devtools::test(filter = "linear")'`
Expected: all pass, WARN 0. If the aliased test leaks `essentially perfect fit` from `summary()` inside `.logistic_vif`, that helper already muffles exactly that message; do not add any other muffling.

- [ ] **Step 5: Commit**

```bash
git add R/linear.R tests/testthat/test-linear.R
git commit -m "feat(linear): residual, collinearity and influence advisories"
```

---

## Task 4: R figures — adjusted-β forest and diagnostics pair

**Files:**
- Modify: `R/linear.R` (add `.linear_forest_svg`, `.linear_diagnostics_svg`; change `svg_field`)
- Modify: `tests/testthat/test-linear.R` (append)

**Interfaces:**
- Consumes: `.linear_terms`, `.coef_reportable`, `.logistic_term_label`, `.km_palette`, `.fig_theme`, `.svg_string`.
- Produces: `.linear_forest_svg(p, fits) -> character(1)` (empty string when no term is reportable) and `.linear_diagnostics_svg(jfit) -> character(1)` (two `<svg>`s concatenated). The `svg` field becomes `<div class="summary-output"><div class="table-scroll">TABLE</div>FOREST DIAG1 DIAG2</div>`.

- [ ] **Step 1: Append the failing tests**

```r
svg_count <- function(s) lengths(regmatches(s, gregexpr("<svg", s, fixed = TRUE)))

test_that("fig_linear svg holds the table plus forest, residual and Q-Q plots", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_equal(svg_count(out$svg), 3)
  expect_match(out$svg, "Adjusted coefficient (difference in los)", fixed = TRUE)
  expect_match(out$svg, "Fitted values", fixed = TRUE)
  expect_match(out$svg, "Theoretical quantiles", fixed = TRUE)
})

test_that("the forest labels a non-syntactic covariate header without backticks", {
  rows <- lapply(mk_lin_rows(), function(r) list(los = r$los, `study arm` = r$arm, age = r$age))
  out <- fig_linear(sc_lin(rows, covariates = c("study arm", "age")))
  forest <- sub("^.*</table></div>", "", out$svg)
  expect_match(forest, "study arm: Treated", fixed = TRUE)
  expect_false(grepl("`", forest, fixed = TRUE))
})

test_that("the forest omits an aliased term but still draws the others", {
  rows <- lapply(mk_lin_rows(), function(r) { r$age2 <- r$age * 2; r })
  out <- fig_linear(sc_lin(rows, covariates = c("arm", "age", "age2")))
  forest <- sub("^.*</table></div>", "", out$svg)
  expect_match(forest, "age (per 1 unit)", fixed = TRUE)
  expect_false(grepl("age2", forest, fixed = TRUE))
  expect_equal(svg_count(out$svg), 3)
})

.forest_aspect <- function(svg) {
  w <- as.numeric(sub(".*\\bwidth='([0-9.]+)pt'.*", "\\1", substr(svg, 1, 400)))
  h <- as.numeric(sub(".*\\bheight='([0-9.]+)pt'.*", "\\1", substr(svg, 1, 400)))
  h / w
}

test_that("the forest keeps a sane aspect ratio with one term and with many", {
  one <- fig_linear(sc_lin(mk_lin_rows(), covariates = "arm"))
  forest1 <- sub("^.*</table></div>", "", one$svg)
  expect_true(.forest_aspect(forest1) >= 0.5)
  rows <- lapply(mk_lin_rows(), function(r) { r$site <- c("a","b","c","d","e","f")[(floor(r$age) %% 6) + 1]; r })
  many <- fig_linear(sc_lin(rows, covariates = c("arm", "age", "site")))
  forest7 <- sub("^.*</table></div>", "", many$svg)
  expect_true(.forest_aspect(forest7) > .forest_aspect(forest1))
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "linear")'`
Expected: `svg_count` is 0 for every case.

- [ ] **Step 3: Add the plot helpers**

Add to `R/linear.R` above `fig_linear`:

```r
# Forest plot of ADJUSTED coefficients (one point per non-reference level /
# numeric term), linear x-axis, dashed rule at 0. Inclusion mirrors .linear_cell
# exactly (both use .coef_reportable), so the table and the plot can never
# disagree about which terms carry usable information.
.linear_forest_svg <- function(p, fits) {
  jt <- .linear_terms(fits$joint$fit)
  keys <- names(jt)
  if (length(keys) == 0) return("")
  est <- vapply(jt, `[[`, numeric(1), "est")
  lo <- vapply(jt, `[[`, numeric(1), "lo")
  hi <- vapply(jt, `[[`, numeric(1), "hi")
  keep <- .coef_reportable(est, lo, hi)
  if (!any(keep)) return("")
  by_len <- p$covs[order(nchar(vapply(p$covs, .logistic_term_label, character(1))),
                         decreasing = TRUE)]
  labeller <- function(key) {
    for (cl in by_len) {
      tl <- .logistic_term_label(cl)
      if (startsWith(key, tl)) {
        if (p$cov_types[[cl]] == "numeric") {
          k <- p$incr[[cl]]
          return(if (k == 1) sprintf("%s (per 1 unit)", cl) else sprintf("%s (per %g units)", cl, k))
        }
        return(sprintf("%s: %s", cl, substring(key, nchar(tl) + 1)))
      }
    }
    key
  }
  d <- data.frame(term = vapply(keys[keep], labeller, character(1)),
                  est = est[keep], lo = lo[keep], hi = hi[keep],
                  stringsAsFactors = FALSE)
  d$term <- factor(d$term, levels = rev(d$term))
  pal <- .km_palette(nrow(d))
  gg <- ggplot2::ggplot(d, ggplot2::aes(x = est, y = term, color = term)) +
    ggplot2::geom_vline(xintercept = 0, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), orientation = "y",
                           width = 0.2, linewidth = 0.6) +
    ggplot2::geom_point(size = 2.4) +
    ggplot2::scale_color_manual(values = pal, guide = "none") +
    ggplot2::labs(x = sprintf("Adjusted coefficient (difference in %s)", p$outcome_name),
                  y = NULL) +
    .fig_theme("generic")
  .svg_string(gg, width = 6.5, height = max(3.6, 0.9 + 0.7 * nrow(d)))
}

# Residuals vs fitted and a normal Q-Q of the residuals, always from the JOINT
# model. Two separate SVGs (no cowplot). No loess smoother: a geom_smooth on a
# small n warns, and the reader wants the raw scatter.
.linear_diagnostics_svg <- function(jfit) {
  d <- data.frame(fitted = stats::fitted(jfit), resid = stats::resid(jfit))
  col <- .km_palette(1)
  g1 <- ggplot2::ggplot(d, ggplot2::aes(x = fitted, y = resid)) +
    ggplot2::geom_hline(yintercept = 0, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_point(size = 1.8, alpha = 0.7, colour = col) +
    ggplot2::labs(x = "Fitted values", y = "Residuals",
                  caption = "Healthy: points scattered evenly around 0, with no funnel or curve.") +
    .fig_theme("generic")
  g2 <- ggplot2::ggplot(d, ggplot2::aes(sample = resid)) +
    ggplot2::stat_qq_line(linewidth = 0.5, colour = "grey50") +
    ggplot2::stat_qq(size = 1.8, alpha = 0.7, colour = col) +
    ggplot2::labs(x = "Theoretical quantiles", y = "Residual quantiles",
                  caption = "Healthy: points along the line.") +
    .fig_theme("generic")
  paste0(.svg_string(g1, width = 6.5, height = 4.5),
         .svg_string(g2, width = 6.5, height = 4.5))
}
```

`.linear_forest_svg` reads `p$outcome_name`; add it to the list `.linear_prep` returns: `outcome_name = ocol,` beside `covs = covs`.

In `fig_linear`, replace the `svg_field <- ...` assignment with:

```r
  table_html <- .linear_table_html(disp_rows)
  forest_svg <- .linear_forest_svg(p, fits)
  diag_svg <- .linear_diagnostics_svg(jfit)
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s%s</div>",
                       table_html, forest_svg, diag_svg)
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `Rscript -e 'devtools::test(filter = "linear")'` then `Rscript -e 'devtools::test()'`
Expected: all pass, WARN 0. A `stat_qq_line` warning about a missing `linewidth` aesthetic would mean an old ggplot2; this repo targets 4.x.

- [ ] **Step 5: Commit**

```bash
git add R/linear.R tests/testthat/test-linear.R
git commit -m "feat(linear): adjusted-coefficient forest and residual diagnostics plots"
```

---

## Task 5: R script export (`.linear_script`)

**Files:**
- Modify: `R/linear.R` (add `.linear_script`; `fig_linear` returns `code`)
- Modify: `tests/testthat/test-linear.R` (append)

**Interfaces:**
- Consumes: `.script_assemble(analysis, spec, cols, pkgs, body)` (`R/script.R`).
- Produces: `code` — a runnable script defining `dat`, `m_uni` (last univariable model), `fit`, `aux`, `bp`. Task 12's `harvest_linear` reads exactly these names, so they are a contract.

- [ ] **Step 1: Append the failing tests**

```r
test_that("linear code parses as R and mentions lm and confint", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_true(nzchar(out$code))
  expect_silent(parse(text = out$code))
  expect_match(out$code, "lm(.y ~", fixed = TRUE)
  expect_match(out$code, "confint(fit)", fixed = TRUE)
  expect_match(out$code, "shapiro.test(resid(fit))", fixed = TRUE)
  expect_match(out$code, "pchisq(bp, df = 1, lower.tail = FALSE)", fixed = TRUE)
  expect_false(grepl("\nplot(fit", out$code, fixed = TRUE))   # commented out: no device in a sourced run
})

test_that("demo-shape spec embeds data (no read.csv) in the script", {
  out <- fig_linear(sc_lin(mk_lin_rows()))
  expect_match(out$code, "df <- data.frame(los = c(", fixed = TRUE)
  expect_false(grepl("read.csv", out$code, fixed = TRUE))
})

test_that("upload-shape spec reads the user's real column names", {
  spec <- sc_lin(mk_lin_rows())
  spec$options$source_filename <- "mydata.csv"
  spec$options$source_roles <- list(outcome = "los", covariates = as.list(c("arm", "age")))
  out <- fig_linear(spec)
  expect_match(out$code, 'read.csv("mydata.csv"', fixed = TRUE)
  expect_match(out$code, 'df[["los"]]', fixed = TRUE)
})

test_that("the generated script runs and reproduces the app's coefficients", {
  spec <- sc_lin(mk_lin_rows(), ref_levels = list(arm = "Treated"),
                 increments = list(age = 10))
  out <- fig_linear(spec)
  env <- new.env(parent = globalenv())
  expect_silent(eval(parse(text = out$code), env))
  adj <- cbind(stats::coef(env$fit), stats::confint(env$fit))
  expect_equal(sprintf("%.2f", adj["armControl", ]),
               sprintf("%.2f", cell_nums(tsv_adj_cell(out$text, "Control"))))
  expect_equal(sprintf("%.2f", adj["age", ]),
               sprintf("%.2f", cell_nums(tsv_adj_cell(out$text, "age \\(per 10 units\\)"))))
  uni <- cbind(stats::coef(env$m_uni), stats::confint(env$m_uni))
  expect_equal(sprintf("%.2f", uni["age", ]),
               sprintf("%.2f", cell_nums(tsv_unadj_cell(out$text, "age \\(per 10 units\\)"))))
  expect_true(is.numeric(env$bp))
})

test_that("the script runs for a single non-syntactic covariate", {
  rows <- lapply(mk_lin_rows(), function(r) list(los = r$los, `study arm` = r$arm))
  out <- fig_linear(sc_lin(rows, covariates = "study arm"))
  env <- new.env(parent = globalenv())
  expect_silent(eval(parse(text = out$code), env))
  expect_true("fit" %in% ls(env))
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "linear")'`
Expected: `out$code` is NULL → failures.

- [ ] **Step 3: Add `.linear_script` and return `code`**

Add above `fig_linear`:

```r
# Downloadable R script: the univariable + joint lm calls, the residual
# diagnostics the app reported, and an equivalent forest plot. The prep block
# reproduces .linear_prep's pipeline in the SAME order (numeric coercion ->
# complete cases -> increment rescale -> relevel), so the script's coefficients
# match the app's table. For uploads, prep reads the user's REAL column names
# (source_roles), exactly like .logistic_script.
.linear_script <- function(spec, p, fits) {
  opts <- spec$options %||% list()
  qe <- function(s) gsub('"', '\\\\"', s)
  covs <- p$covs
  sr <- if (nzchar(as.character(opts$source_filename %||% ""))) opts$source_roles else NULL
  outcome_name <- if (!is.null(sr)) sr$outcome else spec$roles$outcome
  cov_expr <- function(cl) {
    e <- sprintf('df[["%s"]]', qe(cl))
    if (p$cov_types[[cl]] == "numeric") sprintf("as.numeric(%s)", e) else e
  }
  prep <- c(
    sprintf('dat <- data.frame(.y = as.numeric(df[["%s"]]),', qe(outcome_name)),
    paste0("                  ",
      paste(vapply(covs, function(cl) sprintf('`%s` = %s', qe(cl), cov_expr(cl)),
                   character(1)), collapse = ",\n                  "), ","),
    "                  check.names = FALSE, stringsAsFactors = FALSE)",
    "dat <- dat[complete.cases(dat), ]")
  incr_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "numeric" || p$incr[[cl]] == 1) return(NULL)
    sprintf('dat[["%s"]] <- dat[["%s"]] / %g   # coefficient per %g units',
            qe(cl), qe(cl), p$incr[[cl]], p$incr[[cl]])
  }))
  relevel_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "categorical") return(NULL)
    sprintf('dat[["%s"]] <- relevel(factor(dat[["%s"]]), ref = "%s")',
            qe(cl), qe(cl), qe(levels(p$df[[cl]])[1]))
  }))
  uni_lines <- unlist(lapply(covs, function(cl) c(
    sprintf('# Unadjusted coefficient for %s', cl),
    sprintf('m_uni <- lm(.y ~ `%s`, data = dat)', qe(cl)),
    "summary(m_uni)",
    "cbind(beta = coef(m_uni), confint(m_uni))   # t-based 95% CI",
    "")))
  joint_rhs <- paste(sprintf("`%s`", covs), collapse = " + ")
  joint_lines <- c(
    "# Adjusted (joint) model:",
    sprintf("fit <- lm(.y ~ %s, data = dat)", joint_rhs),
    "summary(fit)                                  # coefficients, R-squared, adjusted R-squared",
    "cbind(beta = coef(fit), confint(fit))         # adjusted coefficients + t-based 95% CI", "",
    "# Residual diagnostics the app reported:",
    "shapiro.test(resid(fit))                      # residual normality (n between 3 and 5000)",
    "aux <- lm(resid(fit)^2 ~ fitted(fit))         # Breusch-Pagan (Koenker): n * R^2 of squared residuals on fitted values",
    "bp <- nrow(dat) * summary(aux)$r.squared",
    "pchisq(bp, df = 1, lower.tail = FALSE)",
    "cooks.distance(fit)                           # influential observations (> 4/n flagged in the app)",
    "# plot(fit, which = 1:2)                      # residuals vs fitted; normal Q-Q", "")
  fig_lines <- c(
    "# Equivalent forest plot of the adjusted coefficients:",
    "library(ggplot2)",
    "co <- cbind(coef(fit), confint(fit))[-1, , drop = FALSE]",
    "fp <- data.frame(term = rownames(co), est = co[, 1], lo = co[, 2], hi = co[, 3])",
    "fp <- fp[is.finite(fp$est), ]",
    "fp$term <- factor(fp$term, levels = rev(fp$term))",
    "p_forest <- ggplot(fp, aes(est, term)) +",
    '  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +',
    '  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0.2) +',
    "  geom_point(size = 2.4) +",
    '  labs(x = "Adjusted coefficient", y = NULL) +',
    "  theme_minimal(base_size = 12)",
    '# print(p_forest)')
  body <- c(prep, "",
            incr_lines, if (length(incr_lines)) "" else NULL,
            relevel_lines, if (length(relevel_lines)) "" else NULL,
            uni_lines, joint_lines, fig_lines)
  .script_assemble("Linear regression", spec, c(spec$roles$outcome, covs), c("ggplot2"), body)
}
```

Change the last line of `fig_linear` to:

```r
  list(svg = svg_field, text = text, code = .linear_script(spec, p, fits))
```

- [ ] **Step 4: Run the tests, then the full suite**

Run: `Rscript -e 'devtools::test(filter = "linear")'` then `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | ... ]`.

- [ ] **Step 5: Commit**

```bash
git add R/linear.R tests/testthat/test-linear.R
git commit -m "feat(linear): downloadable lm script with residual diagnostics"
```

---
## Task 6: `renderReadiness` gains `requireEventValue`

**Files:**
- Modify: `web/lib/modelform.js:44-58`
- Modify: `web/lib/modelform.test.mjs` (append)

**Interfaces:**
- Produces: `renderReadiness({ roles, eventValue }, { outcomeRole, checkOverlap, requireEventValue = true, messages })`. With `requireEventValue: false` the event-value check is skipped. Default unchanged, so cox and logistic are untouched.

- [ ] **Step 1: Append the failing tests**

```js
// --- requireEventValue: false — a continuous-outcome form has no event value --
{
  const r = renderReadiness(
    { roles: { outcome: "los", covariates: ["arm"] }, eventValue: "" },
    { requireEventValue: false });
  assert.equal(r.ready, true, "no event value needed when the option is off");
  assert.equal(r.reason, "");
}
{
  const r = renderReadiness(
    { roles: { outcome: "los", covariates: ["arm", "los"] }, eventValue: "" },
    { requireEventValue: false });
  assert.equal(r.ready, false, "overlap is still rejected");
  assert.match(r.reason, /outcome/i);
}
{
  const r = renderReadiness(
    { roles: { outcome: "los", covariates: ["arm"] }, eventValue: "" },
    { requireEventValue: false, messages: { roles: "Choose a numeric outcome." } });
  assert.equal(r.ready, true, "custom messages do not change the decision");
}
{
  // The default is unchanged: logistic/cox still require the event value.
  const r = renderReadiness({ roles: { outcome: "y", covariates: ["arm"] }, eventValue: "" });
  assert.equal(r.ready, false);
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `node web/lib/modelform.test.mjs`
Expected: the first new block fails (`ready` is false).

- [ ] **Step 3: Implement**

In `web/lib/modelform.js`, change the signature and the event check:

```js
export function renderReadiness({ roles, eventValue },
  { outcomeRole = "outcome", checkOverlap = true, requireEventValue = true,
    messages = {} } = {}) {
  const m = { ...READINESS_MESSAGES, ...messages };
  if (!roles || !roles[outcomeRole]) return { ready: false, reason: m.roles };
  const covs = roles.covariates || [];
  if (covs.length === 0) return { ready: false, reason: m.covariates };
  if (checkOverlap && covs.includes(roles[outcomeRole])) {
    return { ready: false, reason: m.overlap };
  }
  // A continuous-outcome form (linear regression) has no event value to pick.
  if (requireEventValue && !eventValue) return { ready: false, reason: m.eventValue };
  return { ready: true, reason: "" };
}
```

- [ ] **Step 4: Run the unit chain**

Run: `npm run test:unit`
Expected: every suite prints ok.

- [ ] **Step 5: Commit** (with the validation regeneration, since `web/lib/modelform.js` is a shipped source)

```bash
make -C stats-validation all; git add web/lib/modelform.js web/lib/modelform.test.mjs stats-validation/results web/validation.html
git commit -m "feat(modelform): requireEventValue option for continuous-outcome forms"
```

---

## Task 7: Linear spec builder and demo module

**Files:**
- Create: `web/guided/linear/spec.js`, `web/guided/linear/spec.test.mjs`
- Create: `web/guided/linear/demo.js`, `web/guided/linear/demo.test.mjs`
- Modify: `package.json` (`test:unit` chain)

**Interfaces:**
- Consumes: `LINEAR_DEMO` (Task 1); `distinctValues`, `mostFrequent` from `web/guided/logistic/spec.js`.
- Produces: `buildLinearSpec(table, roles, refLevels, increments, options) -> spec`; `DEMO_TABLE`, `DEFAULT_DEMO_STATE()`, `buildLinearDemoSpec(demoState)`. Demo pins `ref_levels: { arm: "Standard care", stage: "I" }`, `increments: { age: 10 }`, no `source_filename`.

- [ ] **Step 1: Write the failing tests**

`web/guided/linear/spec.test.mjs`:

```js
import assert from "node:assert";
import { buildLinearSpec, distinctValues, mostFrequent } from "./spec.js";

const table = {
  columns: ["los", "arm", "age", "note"],
  rows: [
    { los: "6.1", arm: "A", age: "60", note: "x" },
    { los: "7.4", arm: "B", age: "70", note: "y" },
    { los: "5.0", arm: "A", age: "65", note: "z" },
  ],
};
const roles = { outcome: "los", covariates: ["arm", "age"] };

const spec = buildLinearSpec(table, roles, { arm: "B" }, { age: 10 }, { source_filename: "f.csv" });
assert.equal(spec.figure, "linear");
assert.deepEqual(spec.roles, { outcome: "los", covariates: ["arm", "age"] });
assert.ok(!("event_value" in spec.options), "a continuous outcome has no event value");
assert.deepEqual(spec.options.ref_levels, { arm: "B" });
assert.deepEqual(spec.options.increments, { age: 10 });
assert.equal(spec.options.source_filename, "f.csv");
assert.deepEqual(spec.options.source_roles, { outcome: "los", covariates: ["arm", "age"] });
// no-egress: only mapped columns cross
for (const row of spec.data) assert.ok(!("note" in row), "note column must not cross");
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "los"]);
// defensive copies
spec.roles.covariates.push("tampered");
assert.deepEqual(roles.covariates, ["arm", "age"]);
assert.deepEqual(spec.options.source_roles.covariates, ["arm", "age"]);
// demo-shape defaults
const demoSpec = buildLinearSpec(table, roles, null, null, {});
assert.equal(demoSpec.options.source_filename, null);
assert.deepEqual(demoSpec.options.ref_levels, {});
assert.deepEqual(demoSpec.options.increments, {});
// re-exports
assert.deepEqual(distinctValues(table, "arm"), ["A", "B"]);
assert.equal(mostFrequent(table, "arm"), "A");
console.log("ok - linear spec");
```

`web/guided/linear/demo.test.mjs`:

```js
import assert from "node:assert/strict";
import { buildLinearDemoSpec, DEFAULT_DEMO_STATE, DEMO_TABLE } from "./demo.js";
import { LINEAR_DEMO } from "./demo-data.js";
import { EXAMPLE_INTRO_HTML } from "./content.js";

const spec = buildLinearDemoSpec(DEFAULT_DEMO_STATE());
assert.equal(spec.figure, "linear");
assert.equal(spec.roles.outcome, "los");
assert.deepEqual(spec.roles.covariates, ["arm", "age", "stage"]);
assert.equal(spec.data.length, LINEAR_DEMO.rows.length);
assert.equal(LINEAR_DEMO.rows.length, 320);
assert.ok(!("source_filename" in spec.options), "demo spec must omit options.source_filename");
assert.ok(!("event_value" in spec.options));
assert.deepEqual(spec.options.increments, { age: 10 });
assert.equal(spec.options.ref_levels.arm, "Standard care");
assert.equal(spec.options.ref_levels.stage, "I");
assert.equal(spec.options.caption, LINEAR_DEMO.label);
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "los", "stage"]);

const noAge = buildLinearDemoSpec({ covariates: ["arm", "stage"] });
for (const row of noAge.data) {
  assert.ok(!("age" in row), "unselected covariate must not cross");
  assert.ok("los" in row, "outcome must always cross");
}

const a = DEFAULT_DEMO_STATE(), b = DEFAULT_DEMO_STATE();
assert.notEqual(a, b);
assert.notEqual(a.covariates, b.covariates);
const s = buildLinearDemoSpec(a);
s.roles.covariates.push("tampered");
assert.deepEqual(a.covariates, ["arm", "age", "stage"]);

assert.deepEqual(DEMO_TABLE.columns, LINEAR_DEMO.columns);
assert.equal(DEMO_TABLE.types.los, "numeric");
assert.equal(DEMO_TABLE.types.age, "numeric");
assert.equal(DEMO_TABLE.types.stage, "categorical");

// The intro's sample size is derived, never hand-typed.
assert.ok(EXAMPLE_INTRO_HTML.includes(String(LINEAR_DEMO.rows.length)));
console.log("demo.test.mjs OK");
```

- [ ] **Step 2: Run to verify they fail**

Run: `node web/guided/linear/spec.test.mjs; node web/guided/linear/demo.test.mjs`
Expected: module-not-found errors.

- [ ] **Step 3: Write the modules**

`web/guided/linear/spec.js`:

```js
// Pure spec assembly for linear regression. Only mapped columns cross to the
// worker (no-egress); the outcome stays a raw string (R coerces it and errors
// readably if it is not numeric). No event value: the outcome is continuous.
// source_roles lets the .R script read the user's real headers.
import { distinctValues, mostFrequent } from "../logistic/spec.js";
export { distinctValues, mostFrequent };

export function buildLinearSpec(table, roles, refLevels, increments, options) {
  const used = [roles.outcome, ...roles.covariates];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "linear",
    data,
    roles: { outcome: roles.outcome, covariates: roles.covariates.slice() },
    options: {
      ref_levels: refLevels || {},
      increments: increments || {},
      source_filename: options.source_filename ?? null,
      source_roles: { outcome: roles.outcome, covariates: roles.covariates.slice() },
    },
  };
}
```

`web/guided/linear/demo.js`:

```js
import { LINEAR_DEMO } from "./demo-data.js";

export const DEMO_TABLE = {
  columns: LINEAR_DEMO.columns,
  rows: LINEAR_DEMO.rows,
  types: { arm: "categorical", age: "numeric", stage: "categorical", los: "numeric" },
};

// Fresh object each call — the guided session store resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return { covariates: ["arm", "age", "stage"] };
}

// The demo goes through the SAME spec shape + worker + R path as user data.
// ref_levels match the most-frequent default and are stated so the table
// reads the same way every time; age is reported per 10 years. source_filename
// is deliberately ABSENT so the generated .R script embeds the example data.
export function buildLinearDemoSpec(demoState) {
  const used = ["los", ...demoState.covariates];
  const data = LINEAR_DEMO.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "linear",
    data,
    roles: { outcome: "los", covariates: demoState.covariates.slice() },
    options: { ref_levels: { arm: "Standard care", stage: "I" },
               increments: { age: 10 },
               caption: LINEAR_DEMO.label },
  };
}
```

`demo.test.mjs` imports `content.js`, written in Task 8. Until then create a stub `web/guided/linear/content.js` containing only the intro export, replaced entirely in Task 8:

```js
import { LINEAR_DEMO } from "./demo-data.js";
export const EXAMPLE_INTRO_HTML = `<p>${LINEAR_DEMO.rows.length}</p>`;
```

- [ ] **Step 4: Register the tests and run the chain**

In `package.json`, insert after `node web/guided/logistic/demo.test.mjs`:
`&& node web/guided/linear/spec.test.mjs && node web/guided/linear/demo.test.mjs`

Run: `npm run test:unit`
Expected: all ok.

- [ ] **Step 5: Commit**

```bash
make -C stats-validation all; git add web/guided/linear package.json stats-validation/results web/validation.html
git commit -m "feat(linear): spec builder and demo module"
```

---

## Task 8: Understand content, experiments, and the guided-shell config

**Files:**
- Create (replace stub): `web/guided/linear/content.js`
- Create: `web/guided/linear/guided-linear.js`
- Modify: `web/guided/understand-sections.test.mjs`
- Modify: `web/guided/linear/demo.test.mjs` (append the Understand check)

**Interfaces:**
- Consumes: `createGuidedShell` (`web/guided/shell.js`), `renderLinearAnalyzeForm` (Task 9 — until then `guided-linear.js` will fail to import; that is expected and Task 9 closes it).
- Produces: `UNDERSTAND_SECTIONS`, `renderUnderstand(panel)`, `EXAMPLE_INTRO_HTML`, `renderLinearExperiments(panel, ctx, rerun)`, `renderGuidedLinear`.

- [ ] **Step 1: Extend the tests**

In `web/guided/understand-sections.test.mjs` add `import * as linear from "./linear/content.js";` and `linear` to `MODULES`. Append to `demo.test.mjs`:

```js
import { renderUnderstand } from "./content.js";
const fakePanel = { innerHTML: "" };
renderUnderstand(fakePanel);
assert.ok(fakePanel.innerHTML.includes("<h3>"), "Understand renders sections");
assert.ok(/per 10 years/.test(fakePanel.innerHTML), "Understand copy explains the increment");
```

Run: `node web/guided/understand-sections.test.mjs`
Expected: fails (stub has no `UNDERSTAND_SECTIONS`).

- [ ] **Step 2: Write `content.js`**

```js
// web/guided/linear/content.js
import { LINEAR_DEMO } from "./demo-data.js";

export const UNDERSTAND_SECTIONS = [
  { title: "Adjust for what else is going on", html: `
    <p>A group comparison tells you whether a continuous outcome differs between
    groups. Linear regression answers the next question: <em>by how much, after
    accounting for the other things that differ between patients?</em> Each covariate
    gets a coefficient — the change in the outcome, in its own units, per increment
    (for a number) or versus a reference level (for a category).</p>
    <p>Unadjusted coefficients come from one model per covariate. Adjusted coefficients
    come from a single joint model, so each one is the effect of that variable with the
    others held fixed. When a treatment is given more often to sicker patients, the
    unadjusted column carries their longer stays and the adjusted column does not.</p>` },
  { title: "What a coefficient is, and is not", html: `
    <p>A coefficient is a difference in means. For a category it is the mean outcome in
    that level minus the mean in the reference level, holding the other covariates
    fixed. For a number it is the change in the outcome per increment — set the
    increment (for example age per 10 years) so that one step is clinically
    meaningful; the confidence interval scales with it and the p-value does not.</p>
    <p>It is a difference on the outcome's own scale, not a ratio and not a
    percentage. "New treatment: −1.5 (−2.0 to −1.0)" for length of stay means one and a
    half fewer days on average, not 1.5 times anything. A coefficient of 0 is no
    difference, which is why the forest plot's dashed line sits at 0.</p>` },
  { title: "Is linear regression appropriate?", html: `
    <p>Use it when each row is one independent participant, the outcome is a
    <strong>continuous measurement</strong> (days, mmHg, a score), and you have the
    baseline covariates you want to adjust for. The tool needs at least 10 residual
    degrees of freedom before it will fit a model, and it drops rows with a missing
    value in any column you use.</p>
    <p>It checks the residuals for <strong>normality</strong> (Shapiro–Wilk) and for
    <strong>constant variance</strong> across fitted values (Breusch–Pagan), and it draws
    both checks as a residuals-vs-fitted plot and a normal Q-Q plot. It also flags
    <strong>multicollinearity</strong> among numeric covariates, covariates that are
    exact combinations of others, and influential observations. Every check is
    advisory — none blocks a result or changes a number. The tool does not transform
    the outcome, fit robust standard errors, or add interaction terms; if the residual
    checks warn, that is the moment to seek statistical review.</p>` },
  { title: "How to read the result", html: `
    <ul>
      <li><strong>β &lt; 0</strong>: a lower outcome. <strong>β &gt; 0</strong>: higher.
      The units are the outcome's own.</li>
      <li>A numeric covariate's β is <strong>per increment</strong> (for example per 10 years).</li>
      <li>A category's β is <strong>versus its reference level</strong>, shown as "0 (reference)".</li>
      <li>A 95% CI that crosses 0 means the effect is not statistically resolved. It does
      not mean there is no effect.</li>
      <li>R² is the share of the outcome's variance the joint model explains; adjusted R²
      penalises it for the number of terms. A low R² with a precise coefficient is
      common and not a problem — the question is the coefficient, not the fit.</li>
      <li>Adjusted coefficients are adjusted only for the covariates you put in the model.</li>
    </ul>
    <p class="callout">With fewer than about 10 observations per model term, adjusted
    estimates become unstable — the tool warns you when that happens.</p>` },
];

export function renderUnderstand(panel) {
  panel.innerHTML = UNDERSTAND_SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("");
}

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic length-of-stay study</h3>
  <p>This teaching dataset has ${LINEAR_DEMO.rows.length} fictional patients on
  <strong>Standard care</strong> or a <strong>New treatment</strong>, with baseline age
  and disease stage, and their hospital <strong>length of stay</strong> in days. The new
  treatment was given preferentially to older, higher-stage patients — the very patients
  who stay longest anyway.</p>
  <p>The example loads with <code>arm</code>, <code>age</code>, and <code>stage</code>
  all checked. Run it as configured and the adjusted coefficient for the new treatment
  is about −1.5 days, with a confidence interval that stays below 0. Uncheck
  <code>age</code> and <code>stage</code> and the coefficient for <code>arm</code> alone
  sits near 0 with a confidence interval straddling it — adjusting for age and stage
  accounts for the confounding that made the raw comparison look null. Toggle the
  covariates below to watch that happen.</p>
  <p class="callout">When the results text flags a few observations as "influential"
  (Cook's distance), that is expected here and on most datasets — the rule of thumb it
  uses picks out a small percentage of rows routinely. It is a prompt to check those
  patients for data-entry errors, not a sign that anything is wrong.</p>`;

// Experiments: check/uncheck which covariates enter the joint model. `arm` is the
// exposure of interest and is always included (its checkbox is disabled).
export function renderLinearExperiments(panel, ctx, rerun) {
  const host = panel.querySelector("#demo-experiments");
  host.innerHTML = "";
  const ALL = ["arm", "age", "stage"];
  const state = ctx.getSession().demoOptions;
  const fieldset = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = "Covariates in the model";
  fieldset.appendChild(legend);
  for (const c of ALL) {
    const label = document.createElement("label");
    label.className = "inline-check";
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.id = "cov-" + c; cb.value = c;
    cb.checked = state.covariates.includes(c);
    cb.disabled = c === "arm";
    cb.onchange = () => {
      const now = ctx.getSession().demoOptions.covariates.filter((x) => x !== c);
      if (cb.checked) now.push(c);
      ctx.patchDemoOptions({ covariates: ALL.filter((x) => now.includes(x)) });
      rerun();
    };
    label.appendChild(cb);
    label.appendChild(document.createTextNode(" " + c));
    fieldset.appendChild(label);
  }
  host.appendChild(fieldset);
}
```

- [ ] **Step 3: Write `guided-linear.js`**

```js
// web/guided/linear/guided-linear.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderLinearExperiments } from "./content.js";
import { buildLinearDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { LINEAR_DEMO } from "./demo-data.js";
import { renderLinearAnalyzeForm } from "./analyze-form.js";

export const renderGuidedLinear = createGuidedShell({
  title: "Linear regression",
  hashPrefix: "linear",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: LINEAR_DEMO.label,
  buildDemoSpec: buildLinearDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments input",
  renderExperiments: renderLinearExperiments,
  renderAnalyzeForm: renderLinearAnalyzeForm,
});
```

- [ ] **Step 4: Run the unit chain**

Run: `npm run test:unit`
Expected: all ok (`guided-linear.js` is not imported by any test yet).

- [ ] **Step 5: Commit**

```bash
make -C stats-validation all; git add web/guided/linear web/guided/understand-sections.test.mjs stats-validation/results web/validation.html
git commit -m "feat(linear): Understand content, experiments, guided-shell config"
```

---
## Task 9: Analyze form (upload UI)

**Files:**
- Create: `web/guided/linear/analyze-form.js`, `web/guided/linear/analyze-form.test.mjs`
- Modify: `package.json` (`test:unit` chain)

**Interfaces:**
- Consumes: `parseCsv`, `toCsv` (`web/lib/csv.js`), `renderColumnPicker` (`web/lib/columnpicker.js`; role type `"numeric"` filters the dropdown to numeric columns), `retainedSelection`, `reconcileRefLevels`, `renderReadiness`, `countDroppedRows` (`web/lib/modelform.js`), `normalizeIncrement` (`web/guided/logistic/analyze-form.js`), `buildLinearSpec`, `distinctValues`, `mostFrequent` (Task 7), `LINEAR_DEMO`.
- Produces: `renderLinearAnalyzeForm(container, onSubmit, doc)`; DOM ids `#csv`, `#linear-config`, `#cp_outcome`, `#cp_covariates`, `#linear-refs` (`select[data-cov]`, ids `linear-ref-<cov>`), `#linear-increments` (`input[data-cov]`, ids `linear-incr-<cov>`), `#linear-render`, `#linear-ready-hint`, `#linear-dropped-note`; `linearReadiness(roles)` (pure, exported). Tasks 10 and 12 drive these ids.

- [ ] **Step 1: Write the failing test**

```js
// web/guided/linear/analyze-form.test.mjs
// The DOM wiring is exercised by the Playwright e2e test; the decisions live
// in pure helpers tested here.
import { linearReadiness, normalizeIncrement, countDroppedRows } from "./analyze-form.js";
import assert from "node:assert";

{
  const ok = linearReadiness({ outcome: "los", covariates: ["arm", "age"] });
  assert.equal(ok.ready, true);
  assert.equal(ok.reason, "");
}
{
  const r = linearReadiness(null);
  assert.equal(r.ready, false);
  assert.match(r.reason, /numeric outcome/i);
  assert.match(r.reason, /covariate/i);
}
{
  const r = linearReadiness({ outcome: "los", covariates: [] });
  assert.equal(r.ready, false);
  assert.match(r.reason, /covariate/i);
}
{
  const r = linearReadiness({ outcome: "los", covariates: ["arm", "los"] });
  assert.equal(r.ready, false, "outcome cannot also be a covariate");
  assert.match(r.reason, /outcome/i);
}
// Re-exports keep the logistic contract.
assert.equal(normalizeIncrement("10"), 10);
assert.equal(normalizeIncrement("abc"), 1);
assert.equal(countDroppedRows({ rows: [{ a: "1" }, { a: "" }] }, ["a"]), 1);
console.log("ok - linear analyze form");
```

- [ ] **Step 2: Run to verify it fails**

Run: `node web/guided/linear/analyze-form.test.mjs`
Expected: module not found.

- [ ] **Step 3: Write the form**

```js
// web/guided/linear/analyze-form.js
// Progressive-disclosure upload UI for linear regression, on the shared
// csv/columnpicker foundation. Mirrors web/guided/logistic/analyze-form.js with
// the event-value picker REMOVED (the outcome is continuous) and the outcome
// dropdown filtered to numeric columns. Reference-level and increment controls
// are the same; the decision logic stays in web/lib/modelform.js.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildLinearSpec, distinctValues, mostFrequent } from "./spec.js";
import { LINEAR_DEMO } from "./demo-data.js";
import { retainedSelection, reconcileRefLevels, renderReadiness, countDroppedRows }
  from "../../lib/modelform.js";
import { normalizeIncrement } from "../logistic/analyze-form.js";
export { normalizeIncrement, countDroppedRows };

// --- pure decision logic (unit-tested in analyze-form.test.mjs) --------------

export function linearReadiness(roles) {
  return renderReadiness({ roles, eventValue: "" }, {
    requireEventValue: false,
    messages: { roles: "Choose a numeric outcome column and at least one covariate to continue." },
  });
}

// --- DOM wiring (exercised by the Playwright e2e test) ----------------------

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(LINEAR_DEMO.rows, LINEAR_DEMO.columns)], { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderLinearAnalyzeForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A numeric outcome column (days, mmHg, a score, …).</li>
        <li>One or more covariate columns to adjust for (numeric or categorical).</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-linear.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="linear-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#linear-config");
  let table = null, roles = null, fileName = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        fileName = file.name;
        roles = null;
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);

        const refWrap = doc.createElement("div"); refWrap.id = "linear-refs";
        const incrWrap = doc.createElement("div"); incrWrap.id = "linear-increments";
        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "linear-render";
        btn.textContent = "Render linear model"; btn.disabled = true;
        const readyHint = doc.createElement("p");
        readyHint.id = "linear-ready-hint"; readyHint.className = "hint";
        readyHint.setAttribute("role", "status");
        const note = doc.createElement("p");
        note.id = "linear-dropped-note"; note.className = "hint";

        const isNumericCol = (col) => table.types[col] === "numeric";
        const syncReady = () => {
          const { ready, reason } = linearReadiness(roles);
          btn.disabled = !ready;
          readyHint.textContent = reason;
        };
        const chosenRefs = {}, chosenIncrs = {};
        const renderRefs = () => {
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => { chosenRefs[s.dataset.cov] = s.value; });
          refWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          const levels = {};
          const levelsOf = (c) => {
            if (isNumericCol(c)) return null;
            if (!levels[c]) levels[c] = distinctValues(table, c);
            return levels[c];
          };
          const refs = reconcileRefLevels(chosenRefs, roles.covariates, levelsOf,
            (c) => mostFrequent(table, c));
          for (const c of roles.covariates) {
            if (isNumericCol(c)) continue;
            const l = doc.createElement("label");
            l.textContent = `Reference level for ${c} `;
            const s = doc.createElement("select");
            s.id = "linear-ref-" + c; s.dataset.cov = c;
            l.htmlFor = s.id;
            for (const v of levelsOf(c)) {
              const o = doc.createElement("option");
              o.value = v; o.textContent = v;
              s.appendChild(o);
            }
            s.value = refs[c];
            l.appendChild(s); refWrap.appendChild(l);
          }
        };
        const renderIncrements = () => {
          incrWrap.querySelectorAll("input[data-cov]").forEach((i) => { chosenIncrs[i.dataset.cov] = i.value; });
          incrWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          for (const c of roles.covariates) {
            if (!isNumericCol(c)) continue;
            const l = doc.createElement("label");
            l.textContent = `Report ${c} per (increment) `;
            const inp = doc.createElement("input");
            inp.type = "number"; inp.min = "0"; inp.step = "any";
            inp.value = chosenIncrs[c] ?? "1";
            inp.id = "linear-incr-" + c; inp.dataset.cov = c;
            l.htmlFor = inp.id;
            l.appendChild(inp); incrWrap.appendChild(l);
          }
        };

        renderColumnPicker(pick,
          [{ key: "outcome", label: "Numeric outcome", type: "numeric" },
           { key: "covariates", label: "Covariates to adjust for", type: "any", multiple: true }],
          table, (v) => { roles = v; renderRefs(); renderIncrements(); syncReady(); }, doc);

        config.appendChild(refWrap);
        config.appendChild(incrWrap);
        btn.onclick = () => {
          if (!linearReadiness(roles).ready) return;
          const refLevels = {};
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => { refLevels[s.dataset.cov] = s.value; });
          const increments = {};
          incrWrap.querySelectorAll("input[data-cov]").forEach((inp) => {
            increments[inp.dataset.cov] = normalizeIncrement(inp.value);
          });
          const spec = buildLinearSpec(table, roles, refLevels, increments, { source_filename: fileName });
          const dropped = countDroppedRows(table, [roles.outcome, ...roles.covariates]);
          note.textContent = dropped > 0 ? `${dropped} row(s) with missing values will be excluded.` : "";
          onSubmit(spec);
        };
        config.appendChild(btn);
        config.appendChild(readyHint);
        config.appendChild(note);
        syncReady();
        config.hidden = false;
      } catch (err) {
        table = null; roles = null;
        config.hidden = true; config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}
```

Before relying on `type: "numeric"`, confirm in `web/lib/columnpicker.js:10-14` that a role type without a `+` suffix filters to exactly `table.types[c] === "numeric"` (it does: `.replace("+", "")` then the equality filter).

- [ ] **Step 4: Register the test and run the chain**

In `package.json`, after `node web/guided/linear/demo.test.mjs` insert `&& node web/guided/linear/analyze-form.test.mjs`.

Run: `npm run test:unit`
Expected: all ok.

- [ ] **Step 5: Commit**

```bash
make -C stats-validation all; git add web/guided/linear package.json stats-validation/results web/validation.html
git commit -m "feat(linear): analyze form with numeric-outcome picker"
```

---

## Task 10: Wire the analysis into the app, and the Playwright e2e

**Files:**
- Modify: `web/worker.js:42`, `web/app.js:108-113`, `web/index.html:72-76` (button) and `:7` (meta description), `web/sw.js:14`, `tests/e2e/smoke.spec.js`
- Create: `tests/e2e/linear-guided.spec.js`

**Interfaces:**
- Consumes: `renderGuidedLinear` (Task 8); the analyze-form ids (Task 9); `LINEAR_DEMO` story guarantees (Task 1).

- [ ] **Step 1: Update the smoke test first (it fails until the button exists)**

In `tests/e2e/smoke.spec.js` change the count to 7, the title to "exactly the seven guided analyses", and insert after the Logistic line:

```js
  await expect(labels.nth(5)).toHaveText("Linear regression");
  await expect(labels.nth(6)).toHaveText("Explore plot");
```

(removing the old `nth(5)` Explore line).

- [ ] **Step 2: Write the guided e2e**

```js
// tests/e2e/linear-guided.spec.js
// Deliberate near-clone of logistic-guided.spec.js — the duplication is intentional;
// do not extract shared helpers across the guided specs.
const { test, expect } = require("@playwright/test");
const path = require("path");

const DEMO_CSV = path.join(__dirname, "..", "testthat", "fixtures", "linear-demo.csv");

// Table cells read "-1.48 (-1.97 to -0.99, p<0.001)"; returns [est, lo, hi].
async function cellInRow(page, label, column) {
  const row = page.locator("#preview table tbody tr", { hasText: label }).first();
  await expect(row).toBeVisible();
  const text = (await row.locator("td").nth(column).innerText()).trim();
  const m = /^(-?\d+\.\d+) \((-?\d+\.\d+) to (-?\d+\.\d+),/.exec(text);
  expect(m, `cell "${text}" matches the coefficient format`).not.toBeNull();
  return m.slice(1).map(Number);
}

// The confounding story pinned by data-raw/linear-demo-generator.R's stopifnot
// block: the crude arm CI straddles 0; the adjusted arm CI lies entirely below 0.
async function expectConfoundingStory(page) {
  const [, uLo, uHi] = await cellInRow(page, "New treatment", 1);
  expect(uLo).toBeLessThan(0);
  expect(uHi).toBeGreaterThan(0);
  const [aEst, , aHi] = await cellInRow(page, "New treatment", 2);
  expect(aEst).toBeLessThan(-0.5);
  expect(aHi).toBeLessThan(0);
  // age is reported per 10 years; at the default increment of 1 the estimate
  // would be a tenth of this, so the lower bound also pins the increment.
  const [ageEst] = await cellInRow(page, "age (per 10 units)", 2);
  expect(ageEst).toBeGreaterThan(0.4);
}

test("linear shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /linear regression/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#linear/example");
});

test("demo fits a Table-3, forest and diagnostics and enables the .R download", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#linear/example");
  await page.getByRole("button", { name: /linear regression/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#preview svg")).toHaveCount(3);
  await expectConfoundingStory(page);
  await expect(page.locator("#stats")).toContainText("Multivariable linear regression (n = 320) of los");
  await expect(page.locator("#stats")).toContainText(/R² = 0\.\d{3}/);
  await expect(page.locator("#stats")).not.toContainText("Shapiro");
  await expect(page.locator("#stats")).not.toContainText("Breusch");
  await expect(page.locator("#export-r")).toBeEnabled();
  await expect(page.locator("#cov-arm")).toBeDisabled();
  await expect(page.locator("#cov-age")).toBeEnabled();
  await expect(page.locator("#run-demo")).toBeEnabled();
});

test("analyze stage fits an uploaded linear model with adjusted coefficients", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#linear/analyze");
  await page.getByRole("button", { name: /linear regression/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#linear-config")).toBeHidden();
  await page.locator("#csv").setInputFiles(DEMO_CSV);
  await expect(page.locator("#linear-config")).toBeVisible();

  const analyze = page.locator("#panel-analyze");
  // The outcome dropdown is numeric-only: `arm` and `stage` must not be offered.
  await expect(analyze.locator("#cp_outcome option[value='arm']")).toHaveCount(0);
  await analyze.locator("#cp_outcome").selectOption("los");
  await analyze.locator("#cp_covariates").selectOption(["arm", "age", "stage"]);
  await analyze.locator("#linear-ref-arm").selectOption("Standard care");
  await analyze.locator("#linear-ref-stage").selectOption("I");
  await analyze.locator("#linear-incr-age").fill("10");
  await analyze.locator("#linear-render").click();

  await expect(page.locator("#preview table")).toBeVisible({ timeout: 300000 });
  await expectConfoundingStory(page);
  await expect(page.locator("#stats")).toContainText("(n = 320)");
});
```

- [ ] **Step 3: Wire the app**

- `web/worker.js:42`: append `"linear.R"` to the fetch array after `"logistic.R"`.
- `web/app.js`: add `import { renderGuidedLinear } from "./guided/linear/guided-linear.js";` after the logistic import, and `linear: renderGuidedLinear` to `forms` after `logistic`.
- `web/index.html`: after the logistic button insert

```html
        <button data-figure="linear">
          <span class="nav-label">Linear regression</span>
          <span class="nav-desc">Adjusted coefficients — Table 3, forest and residual plots</span>
        </button>
```

  and in the `<meta name="description">` change "Cox regression, logistic regression, Table 1" to "Cox, logistic and linear regression, Table 1".
- `web/sw.js:14`: `const CACHE = "figura-v13";  // v12 -> v13: linear regression analysis.`

- [ ] **Step 4: Run e2e**

Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e -- tests/e2e/smoke.spec.js tests/e2e/linear-guided.spec.js`
Expected: 4 passed. If `#preview svg` count is not 3, check that `fig_linear`'s `svg_field` concatenates forest + two diagnostics (Task 4).

- [ ] **Step 5: Run the whole e2e suite once**

Run: `npm run test:e2e`
Expected: all green (the other guided specs are unaffected; smoke now expects seven).

- [ ] **Step 6: Commit**

```bash
make -C stats-validation all; git add web/worker.js web/app.js web/index.html web/sw.js tests/e2e stats-validation/results web/validation.html
git commit -m "feat(linear): register the seventh guided analysis; e2e"
```

---

## Task 11: Landing page, sitemap, About lede

**Files:**
- Modify: `scripts/pages/registry.mjs` (imports + one `PAGES` entry after logistic), `scripts/pages/html.mjs:125` (lede)
- Generate: `web/linear-regression/{index.html,sample.csv,example.json}`, `web/about/index.html`, `web/sitemap.xml`, `web/robots.txt`

- [ ] **Step 1: Add the registry entry**

Imports, beside their logistic twins:

```js
import { UNDERSTAND_SECTIONS as LINEAR_SECTIONS } from "../../web/guided/linear/content.js";
import { LINEAR_DEMO } from "../../web/guided/linear/demo-data.js";
import { buildLinearDemoSpec, DEFAULT_DEMO_STATE as LINEAR_STATE } from "../../web/guided/linear/demo.js";
```

`PAGES` entry, after the logistic entry:

```js
  { slug: "linear-regression", key: "linear", title: "Linear regression coefficients",
    description: "Univariable and multivariable linear regression from a CSV: unadjusted and adjusted coefficients with t-based 95% CIs, a forest plot, residual and Q-Q diagnostics, per-increment scaling for continuous covariates, and Shapiro–Wilk, Breusch–Pagan, VIF and Cook's-distance checks.",
    lede: "A continuous outcome, a set of covariates, and a Table 3 of coefficients: unadjusted and adjusted side by side in the outcome's own units, a forest plot with its null at 0, residual diagnostics drawn for you, and continuous covariates reported per a clinically meaningful step.",
    sections: LINEAR_SECTIONS, demo: LINEAR_DEMO,
    demoSpec: () => buildLinearDemoSpec(LINEAR_STATE()) },
```

In `scripts/pages/html.mjs:125` change "Cox and logistic regression tables" to "Cox, logistic and linear regression tables".

- [ ] **Step 2: Build**

Run: `npm run build:examples && npm run build:pages`
Expected: `web/linear-regression/` appears with `index.html`, `sample.csv`, `example.json`; `web/sitemap.xml` lists it; `web/about/index.html` is regenerated.

- [ ] **Step 3: Verify**

Run: `node scripts/pages/build.test.mjs && grep -c "linear-regression" web/sitemap.xml && grep -o "Adjusted β" web/linear-regression/index.html | head -1`
Expected: test passes; count ≥ 1; `Adjusted β` printed (the example table rendered through `render_figure`).

- [ ] **Step 4: Commit**

```bash
make -C stats-validation all; git add scripts/pages web/linear-regression web/about web/sitemap.xml web/robots.txt stats-validation/results web/validation.html
git commit -m "pages: linear-regression landing page, sitemap, About lede"
```

---
## Task 12: Validation harness — case, spec builder, harvest, comparator kind `coef_table`, scorecard, webR driver

This task makes every tool in `stats-validation/` understand a `linear` figure and a `coef_table` display kind. It does **not** write Path B (Task 14) or the prose spec (Task 13). Until Task 14 lands, `make all` will stop at the Path B step for `linear-confounding` with `no Path B implementation for figure 'linear'`; that is the expected state at the end of this task, so this task's commit runs `make all` for the digest only and does not add the case to `CASES` yet — Task 15 does.

**Files:**
- Create: `stats-validation/cases/linear-confounding/case.json`, `stats-validation/cases/linear-confounding/data.csv` (copy of `tests/testthat/fixtures/linear-demo.csv`)
- Modify: `stats-validation/harness/build-spec.mjs`, `stats-validation/harness/build-spec.test.mjs`
- Modify: `stats-validation/harness/run-script.R` (`harvest_linear` + `HARVESTERS`)
- Modify: `stats-validation/python/validate/cli.py` (`linear` branch)
- Modify: `stats-validation/compare/compare.py`, `stats-validation/compare/tests/test_compare.py`
- Modify: `stats-validation/build_scorecard.py` (`ANALYSES`, `KIND_TIERS`, `KIND_NOT_COMPARED`)
- Modify: `stats-validation/e2e/compare-text.mjs` (kind map), `stats-validation/e2e/webr-parity.spec.js` (`PREVIEW_ELEMENT`, `CASES`, `driveLinear`, `DRIVERS`)

**Interfaces:**
- Consumes: `buildLinearSpec` (Task 7); the script's `dat`, `fit`, `aux`, `bp` objects (Task 5); the advisory sentence strings (Task 3); the analyze-form ids (Task 9).
- Produces, for Task 13/14: the Path B call `fit_linear(df, outcome, covariates, ref_levels, increments)` and the `python.json` keys the comparator reads — `terms` / `unadjusted` (`{key: {est, se, lo, hi, p}}`), `n`, `n_dropped`, `r_squared`, `adj_r_squared`, and `diagnostics` = `{shapiro_p, shapiro_triggered, bp_p, bp_triggered, obs_per_term, obs_per_term_triggered, vif, vif_triggered, cooks_influential, cooks_triggered, aliased_caution}`.

- [ ] **Step 1: The case**

```bash
mkdir -p stats-validation/cases/linear-confounding
cp tests/testthat/fixtures/linear-demo.csv stats-validation/cases/linear-confounding/data.csv
```

`stats-validation/cases/linear-confounding/case.json`:

```json
{
  "id": "linear-confounding",
  "figure": "linear",
  "roles": { "outcome": "los", "covariates": ["arm", "age", "stage"] },
  "options": {
    "ref_levels": { "arm": "Standard care", "stage": "I" },
    "increments": { "age": 10 }
  },
  "display": { "kind": "coef_table" },
  "exact_targets": [
    "adjusted_beta", "adjusted_ci", "adjusted_p", "n", "n_dropped",
    "r_squared", "adj_r_squared", "shapiro_p", "bp_p",
    "shapiro_note", "bp_note", "obs_per_term_note", "vif_note", "cooks_note", "aliased_note"
  ]
}
```

- [ ] **Step 2: Spec builder + its test**

In `harness/build-spec.mjs` add `import { buildLinearSpec } from "../../web/guided/linear/spec.js";` and a `BUILDERS` entry:

```js
  // linear has no event value: buildLinearSpec(table, roles, refLevels, increments, options).
  linear: (table, c) =>
    buildLinearSpec(
      table,
      { outcome: c.roles.outcome, covariates: c.roles.covariates },
      c.options.ref_levels || {},
      c.options.increments || {},
      { source_filename: "data.csv" }
    ),
```

Append to `harness/build-spec.test.mjs` (which runs from the repo root):

```js
{
  const spec = await buildSpecForCase("stats-validation/cases/linear-confounding");
  assert.equal(spec.figure, "linear");
  assert.deepEqual(spec.roles, { outcome: "los", covariates: ["arm", "age", "stage"] });
  assert.ok(!("event_value" in spec.options), "linear carries no event value");
  assert.deepEqual(spec.options.increments, { age: 10 });
  assert.equal(spec.options.source_filename, "data.csv");
  assert.equal(spec.data.length, 320);
}
```

Run: `node stats-validation/harness/build-spec.test.mjs` → ok.

- [ ] **Step 3: Harvest the exported script**

In `harness/run-script.R`, add above `HARVESTERS` and register `linear = harvest_linear`:

```r
# lm: summary()$coefficients columns are "Estimate" / "Std. Error" / "Pr(>|t|)";
# the CI is confint(fit) (t-based), NOT exp(est ± 1.96 se) — no exponentiation
# anywhere for a linear model. `dat`/`fit`/`aux`/`bp` are the names
# .linear_script in R/linear.R assigns.
#
# DIAGNOSTICS: the script computes and prints summary(fit) (R^2, adjusted R^2),
# shapiro.test(resid(fit)) and pchisq(bp, 1, lower.tail = FALSE), so those four
# have full-precision Path A values and are harvested from the script's own
# objects with the identical expressions. It prints cooks.distance(fit) but never
# counts the > 4/n exceedances, and computes no VIF and no observations-per-term
# ratio, so those are judged on the DISPLAY tier (spec/linear-confounding.md,
# "Which tier judges which diagnostic"). Nothing is invented here.
coef_terms <- function(fit) {
  sm <- summary(fit)$coefficients
  for (cn in c("Estimate", "Std. Error", "Pr(>|t|)"))
    if (!(cn %in% colnames(sm)))
      stop(sprintf("coefficient matrix has no `%s` column", cn))
  ci <- stats::confint(fit, level = 0.95)
  keys <- setdiff(names(stats::coef(fit)), "(Intercept)")
  out <- lapply(keys, function(k) {
    if (!(k %in% rownames(sm)))   # aliased: NA everywhere, reported as such
      return(list(est = NA_real_, se = NA_real_, lo = NA_real_, hi = NA_real_, p = NA_real_))
    list(est = unname(sm[k, "Estimate"]), se = unname(sm[k, "Std. Error"]),
         lo = unname(ci[k, 1]), hi = unname(ci[k, 2]), p = unname(sm[k, "Pr(>|t|)"]))
  })
  names(out) <- keys
  out
}

harvest_linear <- function(env, id) {
  fit <- need(env, "fit", id)
  dat <- need(env, "dat", id)
  bp <- need(env, "bp", id)
  s <- summary(fit)
  r <- stats::resid(fit)
  sw <- if (length(r) >= 3 && length(r) <= 5000)
    tryCatch(stats::shapiro.test(r)$p.value, error = function(e) NA_real_) else NA_real_
  list(terms = coef_terms(fit),
       n = nrow(dat),
       n_dropped = n_dropped_vs_csv(dat),
       diagnostics = list(r_squared = s$r.squared, adj_r_squared = s$adj.r.squared,
                          shapiro_p = sw,
                          bp_p = stats::pchisq(bp, df = 1, lower.tail = FALSE)))
}
```

Check how `n_dropped_vs_csv` reads the CSV (`utils::read.csv("data.csv", check.names = FALSE)`), and how the existing harvesters serialise `NA` (look at the `jsonlite::write_json` call at the bottom of the file — `na = "null"` or the default). Path B's `None` must land on the same JSON `null`.

- [ ] **Step 4: Path B CLI branch**

In `python/validate/cli.py`, add `from .linear import fit_linear` and, inside `run()` just after `covariates = list(case["roles"]["covariates"])`:

```python
    if figure == "linear":
        # No event value: the outcome is continuous. Falls through to the
        # display_terms/display_unadjusted re-keying below like logistic/cox.
        out = fit_linear(
            df,
            case["roles"]["outcome"],
            covariates,
            options.get("ref_levels", {}),
            options.get("increments", {}),
        )
    elif figure == "cox":
```

(turning the existing `if figure == "cox":` into `elif`). The import will fail until Task 14 creates `validate/linear.py`; make it lazy so the other cases keep running:

```python
    if figure == "linear":
        from .linear import fit_linear   # clean-room module, Task 14
```

- [ ] **Step 5: Comparator — write the failing tests first**

Append to `compare/tests/test_compare.py`:

```python
from compare import (format_coef_cell, parse_coef_cell, coef_reportable,
                     _compare_linear_diagnostics, _Targets, compare_coef_table)


def test_format_coef_cell_uses_to_and_ascii_minus():
    assert format_coef_cell(-1.234, -2.1, -0.36, 0.0061) == "-1.23 (-2.10 to -0.36, p=0.006)"
    assert format_coef_cell(0.5, 0.1, 0.9, 0.0001) == "0.50 (0.10 to 0.90, p<0.001)"


def test_parse_coef_cell_round_trips_and_rejects_ratio_format():
    assert parse_coef_cell("-1.23 (-2.10 to -0.36, p=0.006)") == {
        "est": -1.23, "lo": -2.10, "hi": -0.36, "p_text": "p=0.006"}
    assert parse_coef_cell("1.02 (0.63–1.66, p=0.932)") is None


def test_coef_reportable_is_finiteness_only():
    assert coef_reportable({"est": -1e9, "lo": -2e9, "hi": -5e8})
    assert not coef_reportable({"est": float("nan"), "lo": 0.0, "hi": 1.0})


def _linear_python(**over):
    d = {"r_squared": 0.4123, "adj_r_squared": 0.4049,
         "diagnostics": {"shapiro_p": 0.31, "shapiro_triggered": False,
                         "bp_p": 0.52, "bp_triggered": False,
                         "obs_per_term": 64.0, "obs_per_term_triggered": False,
                         "vif": None, "vif_triggered": False,
                         "cooks_influential": 17, "cooks_triggered": True,
                         "aliased_caution": False}}
    d.update(over)
    return d


LEAD = ("Multivariable linear regression (n = 320) of los adjusted for arm, age, stage. "
        "Unadjusted coefficients are from single-covariate models; adjusted coefficients "
        "are from the joint model (R² = 0.412, adjusted R² = 0.405).")
COOKS = " 17 observation(s) were flagged as influential (Cook's distance > 4/n); inspect them for data-entry errors."


def test_linear_diagnostics_agree_when_states_and_values_match():
    exact = {"diagnostics": {"r_squared": 0.4123, "adj_r_squared": 0.4049,
                             "shapiro_p": 0.31, "bp_p": 0.52}}
    targets = _Targets(["r_squared", "adj_r_squared", "shapiro_p", "bp_p", "shapiro_note",
                        "bp_note", "obs_per_term_note", "vif_note", "cooks_note", "aliased_note"])
    findings, compared = _compare_linear_diagnostics(LEAD + COOKS, exact, _linear_python(), targets)
    assert [f for f in findings if f["code"] not in ("PASS",)] == []
    assert compared >= 10
    assert targets.met


def test_linear_diagnostics_flag_a_shapiro_state_disagreement():
    text = LEAD + " Residuals depart from normality (Shapiro–Wilk p=0.012); with n = 320 the confidence intervals are still approximately valid by the central limit theorem." + COOKS
    exact = {"diagnostics": {"r_squared": 0.4123, "adj_r_squared": 0.4049, "shapiro_p": 0.012, "bp_p": 0.52}}
    targets = _Targets(["shapiro_note"])
    findings, _ = _compare_linear_diagnostics(text, exact, _linear_python(), targets)
    codes = {f["code"] for f in findings}
    assert "DIAGNOSTIC_MISMATCH" in codes


def test_linear_diagnostics_flag_an_r_squared_value_defect():
    exact = {"diagnostics": {"r_squared": 0.4123, "adj_r_squared": 0.4049, "shapiro_p": 0.31, "bp_p": 0.52}}
    targets = _Targets(["r_squared"])
    findings, _ = _compare_linear_diagnostics(LEAD + COOKS, exact, _linear_python(r_squared=0.39), targets)
    assert any(f["code"] == "DEFECT" and f["quantity"] == "r_squared" for f in findings)
```

Run: `cd stats-validation/compare && ../.venv/bin/python -m pytest tests/test_compare.py -q -k "coef or linear"`
Expected: ImportError on the new names.

- [ ] **Step 6: Comparator — implement `coef_table`**

In `compare/compare.py`:

(a) Beside `format_ratio_cell` / `CELL_RE` / `parse_ratio_cell` / `reportable` add:

```python
def format_coef_cell(est: float, lo: float, hi: float, p: float) -> str:
    """R/linear.R: `sprintf("%.2f (%.2f to %.2f, %s)", est, lo, hi, pf)`."""
    return f"{est:.2f} ({lo:.2f} to {hi:.2f}, {format_p(p)})"


COEF_CELL_RE = re.compile(
    r"^(?P<est>-?\d+\.\d{2}) \((?P<lo>-?\d+\.\d{2}) to "
    r"(?P<hi>-?\d+\.\d{2}), (?P<p>p<0\.001|p=\d+\.\d{3})\)$")


def parse_coef_cell(cell: str):
    m = COEF_CELL_RE.match(cell)
    if m is None:
        return None
    return {"est": float(m["est"]), "lo": float(m["lo"]), "hi": float(m["hi"]),
            "p_text": m["p"]}


def coef_reportable(cell: dict) -> bool:
    """R/linear.R `.coef_reportable`: finite estimate and bounds, no ratio window."""
    try:
        return all(math.isfinite(float(cell[q])) for q in ("est", "lo", "hi"))
    except (KeyError, TypeError, ValueError):
        return False
```

(b) Give `classify_cell` keyword parameters with the ratio defaults, and use them in place of the three hard-coded names inside it:

```python
def classify_cell(term: str, figura_cell: str, python: dict,
                  quantity: str = "displayed cell", *,
                  fmt=format_ratio_cell, ok=reportable, parse=parse_ratio_cell) -> dict:
```

— every `format_ratio_cell(` in the body becomes `fmt(`, every `reportable(python)` becomes `ok(python)`, and `parse_ratio_cell(figura_cell)` becomes `parse(figura_cell)`.

(c) Give `compare_ratio_table` the same treatment:

```python
def compare_ratio_table(case, figura, exact, python, *,
                        counts=("n", "n_event", "n_dropped"),
                        fmt=format_ratio_cell, ok=reportable, parse=parse_ratio_cell):
```

— the counts loop iterates `counts`; the `classify_cell(...)` call passes `fmt=fmt, ok=ok, parse=parse`; the script-tier `format_ratio_cell(...) if reportable(cell) else UNREPORTABLE` becomes `fmt(...) if ok(cell) else UNREPORTABLE`. Then:

```python
def compare_coef_table(case, figura, exact, python):
    """Linear regression: the ratio branch on the coefficient scale. No
    n_event (the outcome is continuous), no exponentiation, "to" in the cell,
    finiteness as the only reportability rule."""
    return compare_ratio_table(case, figura, exact, python,
                               counts=("n", "n_dropped"),
                               fmt=format_coef_cell, ok=coef_reportable,
                               parse=parse_coef_cell)
```

and `KIND_HANDLERS["coef_table"] = compare_coef_table`.

(d) `TARGET_QUANTITIES` additions:

```python
    "adjusted_beta": ("est",),          # linear's name for the same estimate slot
    "r_squared": ("r_squared",),
    "adj_r_squared": ("adj_r_squared",),
    "shapiro_p": ("shapiro_p",),
    "bp_p": ("bp_p",),
    "shapiro_note": ("Shapiro-Wilk note",),
    "bp_note": ("Breusch-Pagan note",),
    "obs_per_term_note": ("observations-per-term note",),
    "aliased_note": ("aliased note",),
```

`DIAGNOSTIC_TARGETS["linear"] = ("r_squared", "adj_r_squared", "shapiro_p", "bp_p", "shapiro_note", "bp_note", "obs_per_term_note", "vif_note", "cooks_note", "aliased_note")`.

(e) Sentence patterns, beside the logistic ones (restated from `R/linear.R`):

```python
R2_RE = re.compile(r"\(R² = (-?\d\.\d{3}), adjusted R² = (-?\d+\.\d{3})\)")
SHAPIRO_RE = re.compile(r"Residuals depart from normality \(Shapiro" + EN_DASH + r"Wilk (p<0\.001|p=\d\.\d{3})\)")
BP_RE = re.compile(r"\(Breusch" + EN_DASH + r"Pagan (p<0\.001|p=\d\.\d{3})\)")
OBS_PER_TERM_RE = re.compile(r"CAUTION: about (\d+\.\d) observations per model term \(fewer than 10\)")
ALIASED_TEXT = "CAUTION: one or more covariates were dropped from the adjusted model"
R2_HALF_ULP = 0.5 * 10.0 ** -3
```

(f) The handler, registered as `DIAGNOSTIC_HANDLERS["linear"]`:

```python
def _compare_linear_diagnostics(text, exact, python, targets):
    """(findings, comparisons performed) for fig_linear's advisory block plus
    the R² pair in its lead sentence."""
    findings = []
    compared = 0
    py = python.get("diagnostics")
    if not isinstance(py, dict):
        findings.append(finding(
            "MISSING_QUANTITY", "-", "diagnostics", None, py,
            "Path B produced no `diagnostics` block; none of the advisory "
            "diagnostics could be compared", source=SRC_PATH_B))
        return findings, compared
    ex = exact.get("diagnostics") or {}

    mark = len(findings)
    if OTHER_WARN_CLAUSE in text:
        findings.append(finding(
            "MISSING_QUANTITY", "-", "numerical-warning note", OTHER_WARN_CLAUSE, None,
            "the displayed text carries the numerical-warning fallback, which embeds "
            "R's own verbatim warning string; fit_linear's contract does not report "
            "it, so the contract must be extended before this case can be judged"))

    # -- R² and adjusted R²: always printed, 3 dp, in the lead sentence.
    m = R2_RE.search(text)
    for q, grp, py_key in (("r_squared", 1, "r_squared"), ("adj_r_squared", 2, "adj_r_squared")):
        py_v = python.get(py_key)
        if m is None or py_v is None:
            findings.append(finding("MISSING_QUANTITY", "-", q, m.group(0) if m else None, py_v,
                                    "the R² clause or Path B's value is missing"))
            continue
        compared += 1
        _diag_value(findings, "-", q, float(m.group(grp)), float(py_v),
                    f"{float(py_v):.3f}", m.group(grp), R2_HALF_ULP)

    # -- Shapiro-Wilk: state, then the p inside it (p is compared as text).
    m = SHAPIRO_RE.search(text)
    state = _note(findings, targets, "-", "Shapiro-Wilk note", "Shapiro-Wilk note",
                  m is not None, py.get("shapiro_triggered"), m.group(0) if m else None,
                  "Shapiro-Wilk caution")
    compared += state is not None
    if state:
        compared += 1
        if py.get("shapiro_p") is None or format_p(float(py["shapiro_p"])) != m.group(1):
            findings.append(finding("DEFECT", "-", "Shapiro-Wilk note", m.group(1),
                                    None if py.get("shapiro_p") is None else format_p(float(py["shapiro_p"])),
                                    "the p-value inside the sentence differs; a p disagreement is never a display artifact"))

    # -- Breusch-Pagan: same shape.
    m = BP_RE.search(text)
    state = _note(findings, targets, "-", "Breusch-Pagan note", "Breusch-Pagan note",
                  m is not None, py.get("bp_triggered"), m.group(0) if m else None,
                  "Breusch-Pagan caution")
    compared += state is not None
    if state:
        compared += 1
        if py.get("bp_p") is None or format_p(float(py["bp_p"])) != m.group(1):
            findings.append(finding("DEFECT", "-", "Breusch-Pagan note", m.group(1),
                                    None if py.get("bp_p") is None else format_p(float(py["bp_p"])),
                                    "the p-value inside the sentence differs"))

    # -- observations per term: state, then the 1-dp value.
    m = OBS_PER_TERM_RE.search(text)
    state = _note(findings, targets, "-", "observations-per-term note",
                  "observations-per-term note", m is not None,
                  py.get("obs_per_term_triggered"), m.group(0) if m else None,
                  "observations-per-term caution")
    compared += state is not None
    if state:
        compared += 1
        v = py.get("obs_per_term")
        _diag_value(findings, "-", "observations-per-term note", float(m.group(1)),
                    None if v is None else float(v),
                    None if v is None else f"about {float(v):.1f} observations per model term",
                    f"about {m.group(1)} observations per model term", DIAG_1DP_HALF_ULP)

    # -- VIF and Cook's: identical rules to logistic (same R wording).
    m = VIF_RE.search(text)
    py_vif = py.get("vif")
    state = _note(findings, targets, "-", "VIF note", "VIF note", m is not None,
                  py.get("vif_triggered"), m.group(0) if m else None, "VIF caution")
    compared += state is not None
    if state:
        if not isinstance(py_vif, dict) or not py_vif:
            findings.append(finding("MISSING_QUANTITY", "-", "VIF note", m.group(0), py_vif,
                                    "Path B raises the VIF caution but reports no per-covariate VIF map"))
        else:
            compared += 1
            rendered, shown = format_vif_largest(py_vif), m.group(1)
            if rendered != shown:
                if VIF_INFINITE in (rendered, shown):
                    findings.append(finding("DEFECT", "-", "VIF note", shown, rendered,
                                            "one path reports an effectively infinite VIF and the other a finite one"))
                else:
                    _diag_value(findings, "-", "VIF note", float(shown),
                                max(float(v) for v in py_vif.values()), rendered, shown, DIAG_1DP_HALF_ULP)

    m = COOKS_RE.search(text)
    state = _note(findings, targets, "-", "Cook's distance note", "Cook's distance note",
                  m is not None, py.get("cooks_triggered"), m.group(0) if m else None,
                  "Cook's-distance caution")
    compared += state is not None
    if state:
        if py.get("cooks_influential") is None:
            findings.append(finding("MISSING_QUANTITY", "-", "Cook's distance note", m.group(0), None,
                                    "Path B raises the Cook's-distance caution but reports no count"))
        else:
            compared += 1
            if int(py["cooks_influential"]) != int(m.group(1)):
                findings.append(finding("DEFECT", "-", "Cook's distance note", int(m.group(1)),
                                        int(py["cooks_influential"]),
                                        "the two paths flagged different numbers of influential observations"))

    # -- aliased: a fixed sentence, state is the whole claim.
    compared += _note(findings, targets, "-", "aliased note", "aliased note",
                      ALIASED_TEXT in text, py.get("aliased_caution"),
                      ALIASED_TEXT if ALIASED_TEXT in text else None,
                      "aliased-covariate caution") is not None
    _source(findings[mark:], SRC_DISPLAY)

    # -- exact tier: the four diagnostics the exported script computes.
    mark = len(findings)
    for q, py_v in (("r_squared", python.get("r_squared")),
                    ("adj_r_squared", python.get("adj_r_squared")),
                    ("shapiro_p", py.get("shapiro_p")), ("bp_p", py.get("bp_p"))):
        a = ex.get(q)
        if a is None or py_v is None:
            findings.append(finding("MISSING_QUANTITY", "-", q, a, py_v,
                                    f"{'Path A' if a is None else 'Path B'} did not report {q} at full precision"))
            continue
        compared += 1
        targets.credit(q)
        if not close_enough(float(a), float(py_v)):
            findings.append(finding("DEFECT", "-", q, a, py_v, f"beyond rel {REL_TOL} / abs {ABS_TOL}"))
    _source(findings[mark:], SRC_EXACT)

    # -- script tier: does the exported .R's R² re-render the lead sentence?
    mark = len(findings)
    m = R2_RE.search(text)
    if m is not None and ex.get("r_squared") is not None:
        compared += 1
        if f"{float(ex['r_squared']):.3f}" != m.group(1):
            findings.append(finding("SCRIPT_DIVERGENCE", "-", "exported script R²", m.group(1),
                                    f"{float(ex['r_squared']):.3f}",
                                    "the exported .R's R² does not reproduce the value the screen showed"))
    _source(findings[mark:], SRC_SCRIPT)
    return findings, compared
```

Note for the executor: in `compare_ratio_table` the diagnostics dispatch happens through `compare_diagnostics(case, figura, exact, python, targets)`, which keys `DIAGNOSTIC_HANDLERS` on `case["figure"]`; the new handler needs no other wiring. The exact-tier loop compares `est, se, lo, hi, p` per term, so Path B must report `se` (Task 13 puts it in the contract).

- [ ] **Step 7: Run the comparator suite**

Run: `make -C stats-validation test`
Expected: green, including the four new tests and every pre-existing cox/logistic test (the defaults preserved the ratio behaviour byte for byte).

- [ ] **Step 8: Scorecard prose**

In `build_scorecard.py`: add `("linear", "Linear regression")` to `ANALYSES`; add to `KIND_TIERS`:

```python
    "coef_table": (
        "every cell of the rendered coefficient table &mdash; unadjusted and "
        "adjusted, estimate, t-based 95% CI and p-value &mdash; exactly as the app "
        "prints it, plus R&sup2; and the residual advisories",
        "the adjusted cells, R&sup2;, the Shapiro&ndash;Wilk p and the "
        "Breusch&ndash;Pagan p the exported <code>.R</code> produces when it is "
        "re-run in R, rendered through the app's own display rule",
    ),
```

and to `KIND_NOT_COMPARED`:

```python
    "coef_table": (
        "the unadjusted column at full precision (compared as displayed only); "
        "the prose wrapped around the numbers; the rendered forest, residual and "
        "Q&ndash;Q plots, which draw the same fitted model"
    ),
```

Run `grep -n "KIND_TIERS\[\|KIND_NOT_COMPARED\[\|ANALYSIS_NAMES\[" stats-validation/build_scorecard.py` and confirm every lookup is by the case's own kind/figure, so the new keys are reached and nothing else enumerates kinds.

- [ ] **Step 9: webR tier**

`e2e/compare-text.mjs`: add `coef_table: compareText,` to the kind map at the bottom (the three-column parser is column-agnostic and "to" is inside a cell it compares as a string). Run `node stats-validation/e2e/compare-text.test.mjs`; if it asserts the exact kind set, add `coef_table` to that expectation.

`e2e/webr-parity.spec.js`: add `coef_table: "table"` to `PREVIEW_ELEMENT`; add `{ id: "linear-confounding", nav: /linear regression/i, kind: "linear" }` to `CASES` after the logistic rows; add the driver and register `linear: driveLinear` in `DRIVERS`:

```js
async function driveLinear(page, analyze, def, csv) {
  await expect(page.locator("#linear-config")).toBeHidden();
  await analyze.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#linear-config")).toBeVisible();
  await analyze.locator("#cp_outcome").selectOption(def.roles.outcome);
  // No event value for a continuous outcome; reference/increment controls are
  // re-rendered on every column-picker change, so covariates come first.
  await analyze.locator("#cp_covariates").selectOption(def.roles.covariates);
  for (const [cov, level] of Object.entries(def.options.ref_levels || {})) {
    await analyze.locator(`#linear-refs select[data-cov="${cov}"]`).selectOption(level);
  }
  for (const [cov, step] of Object.entries(def.options.increments || {})) {
    await analyze.locator(`#linear-increments input[data-cov="${cov}"]`).fill(String(step));
  }
  await analyze.locator("#linear-render").click();
}
```

Update the spec's own comments that say "eight cases" to nine where they count.

- [ ] **Step 10: Commit** (case not yet in `CASES`; `make all` regenerates the digest only)

```bash
make -C stats-validation test && make -C stats-validation all
git add stats-validation web/validation.html
git commit -m "validation: coef_table display kind, linear harvest/driver, linear-confounding case"
```

---
## Task 13: Spec transcription, interface contract, and acceptance tests (source-access agent)

The agent doing this task READS `R/linear.R` and transcribes it. It must not write `validate/linear.py`.

**Files:**
- Create: `stats-validation/spec/linear-confounding.md`
- Modify: `stats-validation/python/INTERFACES.md` (a `validate/linear.py` section)
- Create: `stats-validation/python/tests/test_linear.py`

**Interfaces:**
- Consumes: `R/linear.R` (every rule), Task 12's `python.json` key list, `spec/logistic-confounding.md` (section shape).
- Produces: the only three documents Task 14 may read.

- [ ] **Step 1: Write `spec/linear-confounding.md`**

Follow `spec/logistic-confounding.md` section for section. Required sections and the normative content each must carry, transcribed from `R/linear.R` (quote no R code — state rules in prose and formulas):

1. **Preamble** — live-app boundary paragraph (as logistic's), input path.
2. **Cell reading** — identical to logistic's (one parser feeds all).
3. **Population** — complete cases over outcome + three covariates; blank is missing; literal `NA` is a value; report the count dropped.
4. **Outcome** — `los`, read as a number; every non-blank cell must parse numerically.
5. **Covariates** — `arm` categorical ref `"Standard care"`; `stage` categorical ref `"I"`; `age` continuous divided by 10 before fitting. Default reference = most frequent level after the Population filter; fallback when the declared reference is absent.
6. **Models** — one ordinary-least-squares fit of `los` on each covariate alone (unadjusted); one on all three jointly (adjusted). Treatment (dummy) coding with the reference as baseline.
7. **Reported quantities** — per term: coefficient β; standard error; 95% CI = β ± t(0.975, n − p) · se where p is the number of estimated coefficients including the intercept and t is the Student quantile (NOT 1.96); two-sided p from the t statistic on n − p df. Also n, n dropped, R² = 1 − RSS/TSS, adjusted R² = 1 − (1 − R²)(n − 1)/(n − p).
8. **Reportability** — a cell is reported only when β, lower and upper are all finite; an aliased coefficient (exactly collinear column) is unreportable. Reads `not reliably estimated`.
9. **Display** — `%.2f (%.2f to %.2f, p=%.3f)` with the word `to`; `p<0.001` below 0.001; reference rows `0 (reference)`; numeric row label `age (per 10 units)`.
10. **Citation paragraph (not compared)** — as logistic's.
11. **Diagnostics (advisory)** — the `diagnostics` block, all on the joint model:
   - `shapiro_p` / `shapiro_triggered`: Shapiro–Wilk W test on the residuals, computed only when 3 ≤ n ≤ 5000 (else `None` / `False`); triggered when p < 0.05.
   - `bp_p` / `bp_triggered`: regress the squared residuals on the fitted values by OLS; LM = n · R² of that auxiliary regression; p = upper tail of χ²(1); triggered when p < 0.05.
   - `obs_per_term` / `obs_per_term_triggered`: n divided by the number of non-intercept coefficients in the joint design (one per continuous covariate, levels − 1 per categorical, levels counted after the Population filter); triggered when < 10.
   - `vif` / `vif_triggered`: identical to logistic's (continuous covariates only; `None` with fewer than two; > 5 triggers; exact duplicate → infinity).
   - `cooks_influential` / `cooks_triggered`: count of rows with Cook's distance > 4/n; Cook's D_i = (e_i² / (p · s²)) · h_ii / (1 − h_ii)² with s² the residual mean square and h_ii the hat-matrix diagonal; non-finite excluded.
   - `aliased_caution`: true when any joint-model coefficient is not estimable (rank-deficient design).
   - State every threshold as a strict inequality.
12. **Which tier judges which diagnostic** — R², adjusted R², Shapiro p and BP p have exact-tier Path A values (the exported script computes and prints them); VIF, Cook's, observations-per-term and aliased are display-tier only.
13. **Two notes deliberately outside this contract** — the numerical-warning fallback and the dropped-row note, as logistic's.

- [ ] **Step 2: Add the `validate/linear.py` section to `INTERFACES.md`**

```markdown
## validate/linear.py

- `fit_linear(df, outcome, covariates, ref_levels, increments) -> dict` with keys:
  - `terms`: `{term: {est, se, lo, hi, p}}` — adjusted (joint-model) coefficients on
    the outcome's own scale (never exponentiated). `se` is REQUIRED. Term naming as
    `fit_logistic`: continuous covariate → the column name; categorical level →
    column name immediately followed by the level string. An aliased term is
    present with every value `float("nan")`, so the comparator sees an
    unreportable cell rather than a missing one.
  - `unadjusted`: same shape, one univariable model per covariate.
  - `n`, `n_dropped`: integers. There is NO `n_event`.
  - `r_squared`, `adj_r_squared`: floats.
  - `diagnostics`: exactly these keys — `shapiro_p` (`float | None`),
    `shapiro_triggered` (bool), `bp_p` (float), `bp_triggered` (bool),
    `obs_per_term` (float), `obs_per_term_triggered` (bool), `vif`
    (`{covariate: float} | None`), `vif_triggered` (bool), `cooks_influential`
    (int), `cooks_triggered` (bool), `aliased_caution` (bool).
- `reportable(cell) -> bool` — finiteness of est/lo/hi per the spec's Reportability rule.

Report all floats at full precision — never round inside the module.
```

- [ ] **Step 3: Compute the R reference values for the acceptance test**

From the repo root:

```r
Rscript -e '
df <- read.csv("stats-validation/cases/linear-confounding/data.csv", check.names = FALSE, na.strings = character(0))
df$arm <- relevel(factor(df$arm), ref = "Standard care"); df$stage <- factor(df$stage)
df$age <- df$age / 10          # per-10 increment, keeping the coefficient name "age"
fit <- lm(los ~ arm + age + stage, data = df)
s <- summary(fit); ci <- confint(fit)
for (k in c("armNew treatment", "age", "stageII", "stageIII"))
  cat(sprintf("%s: est=%.10f se=%.10f lo=%.10f hi=%.10f p=%.10g\n", k,
      coef(fit)[k], s$coefficients[k, 2], ci[k, 1], ci[k, 2], s$coefficients[k, 4]))
cat(sprintf("r2=%.10f adj=%.10f\n", s$r.squared, s$adj.r.squared))
cat(sprintf("shapiro=%.10g\n", shapiro.test(resid(fit))$p.value))
aux <- lm(resid(fit)^2 ~ fitted(fit)); bp <- nrow(df) * summary(aux)$r.squared
cat(sprintf("bp=%.10g cooks=%d\n", pchisq(bp, 1, lower.tail = FALSE), sum(cooks.distance(fit) > 4 / nrow(df))))
'
```

- [ ] **Step 4: Write `python/tests/test_linear.py`**

Paste the printed numbers into `R_REFERENCE` (every value, full precision as printed). The synthetic tests need no R.

```python
import math

import numpy as np
import pandas as pd
from validate.io import load_case
from validate.linear import fit_linear, reportable

# Computed in R (lm + confint + summary) on cases/linear-confounding/data.csv
# with arm ref "Standard care", stage ref "I", age per 10. Pasted from the
# Rscript block in the implementation plan, Task 13 Step 3.
R_REFERENCE = {
    "armNew treatment": {"est": <paste>, "se": <paste>, "lo": <paste>, "hi": <paste>, "p": <paste>},
    "age": {"est": <paste>, "se": <paste>, "lo": <paste>, "hi": <paste>, "p": <paste>},
    "stageII": {"est": <paste>, "se": <paste>, "lo": <paste>, "hi": <paste>, "p": <paste>},
    "stageIII": {"est": <paste>, "se": <paste>, "lo": <paste>, "hi": <paste>, "p": <paste>},
    "r_squared": <paste>, "adj_r_squared": <paste>,
    "shapiro_p": <paste>, "bp_p": <paste>, "cooks_influential": <paste>,
}
CASE = "../cases/linear-confounding"


def _rel(a, b, tol=1e-6):
    return abs(a - b) <= max(1e-9, tol * max(abs(a), abs(b)))


def test_reproduces_r_on_the_shipped_case():
    df, case = load_case(CASE)
    out = fit_linear(df, "los", ["arm", "age", "stage"],
                     {"arm": "Standard care", "stage": "I"}, {"age": 10})
    for key in ("armNew treatment", "age", "stageII", "stageIII"):
        for q in ("est", "se", "lo", "hi", "p"):
            assert _rel(out["terms"][key][q], R_REFERENCE[key][q]), (key, q)
    assert _rel(out["r_squared"], R_REFERENCE["r_squared"])
    assert _rel(out["adj_r_squared"], R_REFERENCE["adj_r_squared"])
    assert _rel(out["diagnostics"]["shapiro_p"], R_REFERENCE["shapiro_p"], 1e-4)
    assert _rel(out["diagnostics"]["bp_p"], R_REFERENCE["bp_p"])
    assert out["diagnostics"]["cooks_influential"] == R_REFERENCE["cooks_influential"]
    assert out["n"] == 320 and out["n_dropped"] == 0
    assert out["diagnostics"]["aliased_caution"] is False


def _frame(seed=7, n=300):
    rng = np.random.default_rng(seed)
    arm = rng.choice(["A", "B"], size=n)
    age = rng.normal(60, 10, n)
    y = 5 + 0.1 * (age - 60) - 2 * (arm == "B") + rng.normal(0, 2, n)
    return pd.DataFrame({"y": y, "arm": arm, "age": age})


def test_recovers_a_known_coefficient_and_uses_the_t_quantile():
    from scipy.stats import t
    df = _frame()
    out = fit_linear(df, "y", ["arm", "age"], {"arm": "A"}, {})
    term = out["terms"]["armB"]
    assert -2.6 < term["est"] < -1.4
    half = t.ppf(0.975, len(df) - 3) * term["se"]
    assert _rel(term["hi"] - term["est"], half) and _rel(term["est"] - term["lo"], half)
    assert abs((term["hi"] - term["est"]) - 1.96 * term["se"]) > 1e-6, "must not be the normal quantile"


def test_increment_rescales_the_coefficient_and_not_p():
    df = _frame()
    per1 = fit_linear(df, "y", ["age"], {}, {})
    per10 = fit_linear(df, "y", ["age"], {}, {"age": 10})
    assert _rel(per10["terms"]["age"]["est"], 10 * per1["terms"]["age"]["est"])
    assert _rel(per10["terms"]["age"]["p"], per1["terms"]["age"]["p"])


def test_counts_and_blank_handling():
    df = _frame()
    df.loc[0, "age"] = ""
    df.loc[1, "y"] = "  "
    out = fit_linear(df, "y", ["arm", "age"], {"arm": "A"}, {})
    assert out["n_dropped"] == 2 and out["n"] == len(df) - 2


def test_aliased_column_is_unreportable_and_flagged():
    df = _frame()
    df["age2"] = df["age"] * 2
    out = fit_linear(df, "y", ["arm", "age", "age2"], {"arm": "A"}, {})
    assert out["diagnostics"]["aliased_caution"] is True
    assert not reportable(out["terms"]["age2"])
    assert reportable(out["terms"]["age"])
    assert reportable(out["unadjusted"]["age2"])


def test_reference_fallback_when_declared_level_is_absent():
    df = _frame()
    out = fit_linear(df, "y", ["arm"], {"arm": "Z"}, {})
    ref = "A" if (df["arm"] == "A").sum() >= (df["arm"] == "B").sum() else "B"
    assert list(out["terms"]) == ["arm" + ("B" if ref == "A" else "A")]


def test_diagnostics_shapes():
    df = _frame()
    d = fit_linear(df, "y", ["arm", "age"], {"arm": "A"}, {})["diagnostics"]
    assert set(d) == {"shapiro_p", "shapiro_triggered", "bp_p", "bp_triggered",
                      "obs_per_term", "obs_per_term_triggered", "vif", "vif_triggered",
                      "cooks_influential", "cooks_triggered", "aliased_caution"}
    assert d["vif"] is None, "fewer than two continuous covariates -> None, not {}"
    assert _rel(d["obs_per_term"], len(df) / 2)
    assert isinstance(d["cooks_influential"], int)


def test_shapiro_is_none_outside_its_size_window():
    rng = np.random.default_rng(1)
    n = 5001
    df = pd.DataFrame({"y": rng.normal(size=n), "x": rng.normal(size=n)})
    d = fit_linear(df, "y", ["x"], {}, {})["diagnostics"]
    assert d["shapiro_p"] is None and d["shapiro_triggered"] is False


def test_breusch_pagan_fires_on_a_funnel():
    rng = np.random.default_rng(3)
    x = np.linspace(1, 100, 400)
    y = 2 + 0.5 * x + rng.normal(0, 0.05 * x)
    d = fit_linear(pd.DataFrame({"y": y, "x": x}), "y", ["x"], {}, {})["diagnostics"]
    assert d["bp_triggered"] is True and d["bp_p"] < 0.05
```

Replace every `<paste>` with the printed value before committing; `grep -c "<paste>" stats-validation/python/tests/test_linear.py` must print 0.

- [ ] **Step 5: Confirm the suite is red for the right reason**

Run: `cd stats-validation/python && ../.venv/bin/python -m pytest tests/test_linear.py -q`
Expected: collection error `No module named 'validate.linear'`.

- [ ] **Step 6: Commit**

```bash
git add stats-validation/spec/linear-confounding.md stats-validation/python/INTERFACES.md stats-validation/python/tests/test_linear.py
git commit -m "validation: linear-confounding spec, interface contract, acceptance tests"
```

---

## Task 14: Path B — the independent Python implementation (clean-room agent)

**Dispatch this to a FRESH subagent whose prompt contains, verbatim:** "You may read ONLY `stats-validation/spec/linear-confounding.md`, `stats-validation/python/INTERFACES.md`, `stats-validation/python/tests/test_linear.py`, and the existing `stats-validation/python/validate/io.py`. You MUST NOT open `R/`, `web/`, `stats-validation/results/`, `stats-validation/harness/`, `stats-validation/compare/`, or any other `validate/*.py`. Resolve every ambiguity from the spec alone and record each choice in `DECISIONS-linear.md`."

**Files:**
- Create: `stats-validation/python/validate/linear.py`
- Create: `stats-validation/python/DECISIONS-linear.md`

**Interfaces:**
- Consumes: `load_case`, `complete_cases`, `to_numeric`, `treatment_dummies` from `validate/io.py` (signatures in `INTERFACES.md`).
- Produces: `fit_linear(df, outcome, covariates, ref_levels, increments) -> dict` and `reportable(cell)` exactly as `INTERFACES.md` pins them.

- [ ] **Step 1: Run the acceptance suite; it is red**

Run: `cd stats-validation/python && ../.venv/bin/python -m pytest tests/test_linear.py -q`

- [ ] **Step 2: Implement from the spec**

Use `numpy` (least squares via the normal equations or `numpy.linalg.lstsq` with an explicit rank check for aliasing), `scipy.stats.t` / `chi2` / `shapiro`, and `pandas`. `statsmodels.api` is broken in the pinned venv (see `DECISIONS-logistic.md`'s environment note); if you use statsmodels import from its submodules. Every float at full precision.

- [ ] **Step 3: Iterate until green**

Run: `cd stats-validation/python && ../.venv/bin/python -m pytest tests/test_linear.py -q`
Expected: all pass. A failure in `test_reproduces_r_on_the_shipped_case` beyond 1e-6 is a modelling difference to resolve from the spec's formulas, never by reading R.

- [ ] **Step 4: Write `DECISIONS-linear.md`**

Headed `# Decisions`, with an "Interpretation choices" list: what "blank" meant, how rank deficiency was detected and which column was declared aliased, the exact t-quantile and χ² calls, how ties/constants were handled in Shapiro, and anything the spec left open.

- [ ] **Step 5: Commit**

```bash
git add stats-validation/python/validate/linear.py stats-validation/python/DECISIONS-linear.md
git commit -m "validation: clean-room Path B linear regression"
```

---

## Task 15: Run the pipeline, disposition findings, gate, docs

**Files:**
- Modify: `stats-validation/Makefile` (`CASES`), `stats-validation/expected-findings.json`, `stats-validation/results/*`, `web/validation.html`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Register the case**

In `stats-validation/Makefile` append `linear-confounding` to `CASES`.

- [ ] **Step 2: Run everything**

```bash
make -C stats-validation test
make -C stats-validation all; echo "exit $?"
```

Expected: exit 1 (the standing `logistic-dirty` disposition). Open `stats-validation/results/scorecard.html` and read the `linear-confounding` row: every tier compared, `targets_met: true`, 0 findings. If it publishes findings:
- `MISSING_QUANTITY` on a `*_note` or on `se` → a contract gap between Tasks 12/13/14; fix the offending side (harvest, spec, or comparator — never Path B by reading R).
- `DEFECT` on `est/se/lo/hi/p` → a real disagreement; write it up in `stats-validation/issues/` before touching anything, per `docs/agents/issue-tracker.md`.
- `DISPLAY_ARTIFACT` → accept; it is dispositioned by the baseline.

- [ ] **Step 3: Baseline and freshness**

```bash
make -C stats-validation gate-update
make -C stats-validation gate
make -C stats-validation freshness
```

Expected: `gate` and `freshness` exit 0.

- [ ] **Step 4: Hand-run webR gate**

```bash
rm -rf web/R && cp -R R web/R
make -C stats-validation webr
make -C stats-validation all
```

Expected: nine cases compared in one booted session; `linear-confounding` shows zero drift. The second `make all` publishes the webR result and clears the staleness box on `web/validation.html`.

- [ ] **Step 5: Update `CLAUDE.md`**

- "All six guided analyses" → seven; add linear to the guided-shell list with `web/guided/linear/guided-linear.js` and `data-raw/linear-demo-generator.R`.
- Add a `fig_linear` paragraph after the `fig_logistic` one: base `stats::lm`, t-based CIs, "to" cell format, `0 (reference)`, the advisories, forest + residual/Q-Q pair, no `EXTRA_PACKAGES`.
- Statistical validation: nine cases; the `coef_table` display kind row in the `display.kind` table (`coef_table` → `compareText`, linear).
- The `renderReadiness` `requireEventValue` option in the `modelform.js` sentence.
- Remove the stale line "six crawlable analysis pages" → seven.

- [ ] **Step 6: Final verification and commit**

```bash
Rscript -e 'devtools::test()'
npm run test:unit
node scripts/pages/build.test.mjs
git add stats-validation CLAUDE.md web/validation.html
git commit -m "validation: register linear-confounding; baseline, webR gate, docs"
```

Expected: `[ FAIL 0 | WARN 0 ]`, all unit suites ok, pages test ok. Then run `/wrap`.

---

## Self-review notes

- **Spec coverage:** prep/stops (T2), estimates/cell/table (T2), advisories (T3), figures (T4), script (T5), form/readiness (T6, T9), spec builder/demo (T7), Understand/experiments/shell (T8), wiring/meta/e2e (T10), landing page/About (T11), validation harness + `coef_table` + webR driver (T12), spec transcription + acceptance tests (T13), clean-room Path B (T14), pipeline/gate/freshness/webR/CLAUDE.md (T15). The spec's "non-goals" need no task.
- **Type consistency:** `.linear_terms` returns `list(est, lo, hi, p)`; the harvest adds `se` (the comparator's exact tier needs it and the display side never does). Path B `terms` carry `se`. `linearReadiness(roles)` is the only readiness entry point the linear form uses. `harvest_linear` reads `fit`, `dat`, `bp` — all assigned by `.linear_script`.
- **Deliberate `<paste>` markers** appear only in Task 13 Step 4 and are replaced within that task by the values Step 3 prints; the step's `grep -c` check enforces it.

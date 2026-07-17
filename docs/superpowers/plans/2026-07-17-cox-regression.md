# Cox Regression Guided Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fifth guided analysis — multivariable Cox proportional-hazards regression producing a univariable+adjusted HR table ("Table 3") plus an adjusted-HR forest plot.

**Architecture:** New `fig_cox(spec)` in `R/cox.R` (base `stats` + `survival` + `ggplot2`, no new package), routed through `render_figure`'s dispatch, delivered by a new `createGuidedShell` config under `web/guided/cox/`. Reuses every shared helper (`.svg_string`, `%||%`, `.numeric_col`, `.char_col`, `.km_palette`, `.fig_theme`, `R/script.R` builders, `csv.js`, `columnpicker.js`). PH assumption checked with `cox.zph` and reported non-blocking.

**Tech Stack:** R (survival, ggplot2, svglite), webR, vanilla-JS ES modules, testthat, Playwright, Node test runner.

## Global Constraints

- `Rscript -e 'devtools::test()'` must end `[ FAIL 0 | WARN 0 | ... ]`. WARN 0 is a hard gate. ggplot2 4.x: `linewidth` not `size`/`label.size`; `geom_errorbar(orientation="y")` not `geom_errorbarh`. Wrap only library calls in `suppressWarnings()`; catch model-fit warnings with `withCallingHandlers`/`muffleWarning`.
- Always `devtools::test()`, never `testthat::test_file()`.
- No new R package. `survival` already in DESCRIPTION Imports and in KM's `EXTRA_PACKAGES`.
- No data egress: only mapped columns enter `data`; the `.R` script carries the source filename, never contents.
- Five parallel keys must stay in sync (R file, dispatch switch, worker fetch loop + EXTRA_PACKAGES, web form+registry+html button, DESCRIPTION).
- A new R file must be added to the worker boot fetch loop or it 404s in the browser.
- `web/R/` is a gitignored build copy; run `rm -rf web/R && cp -R R web/R` before serve/e2e.
- Reuse `.svg_string`, `%||%` from `R/dispatch.R`; never redefine.

---

### Task 1: `fig_cox` core — prep, fit, table, text (R)

**Files:**
- Create: `R/cox.R`
- Modify: `R/dispatch.R:11` (add `cox = fig_cox(spec),` to the switch)
- Test: `tests/testthat/test-cox.R`

**Interfaces:**
- Consumes: `.numeric_col`, `.char_col` (`R/summarize.R`), `.fmt_num` (`R/summarize.R`), `.svg_string`, `%||%` (`R/dispatch.R`), `.km_palette` (`R/km.R`), `.fig_theme` (`R/themes.R`).
- Produces: `fig_cox(spec)` → `list(svg=<HTML table + forest svg>, text=<TSV+methods>, code=<R script>)`. Spec shape: `figure="cox"`, `data=[rows]`, `roles=list(time,status,covariates=[...])`, `options=list(event_value, ref_levels=list(col=val,...), source_filename, source_roles)`.
- Helpers other tasks/tests rely on (all in `R/cox.R`): `.cox_prep(spec)` → `list(df, covs, cov_types, ref_levels, n, events, n_dropped)`; `.cox_fits(df, covs, cov_types)` → `list(uni=<named list of coxph>, joint=<coxph>)`; `.cox_most_frequent(x)` → scalar.

- [ ] **Step 1: Write failing tests** in `tests/testthat/test-cox.R`:

```r
# Build a survival dataset with a real arm effect confounded by a covariate.
mk_cox_rows <- function() {
  set.seed(41)
  n <- 200
  arm <- rep(c("Control", "Treated"), each = n / 2)
  age <- round(rnorm(n, 60, 10), 1)
  # hazard rises with age and is lower for Treated
  lp <- 0.04 * (age - 60) - 0.7 * (arm == "Treated")
  time <- round(rexp(n, rate = 0.05 * exp(lp)) + 0.1, 2)
  cens <- time > 24
  time[cens] <- 24
  status <- ifelse(cens, "alive", "dead")
  lapply(seq_len(n), function(i)
    list(time = time[i], status = status[i], arm = arm[i], age = age[i]))
}
sc_cox <- function(rows, covariates = c("arm", "age"), ref_levels = NULL,
                   event_value = "dead") {
  list(figure = "cox", data = rows,
       roles = list(time = "time", status = "status", covariates = as.list(covariates)),
       options = list(event_value = event_value,
                      ref_levels = ref_levels %||% list()))
}

test_that("fig_cox returns svg table + forest plot, text, and code", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_true(nzchar(out$text))
  expect_true(nzchar(out$code))
})

test_that("both unadjusted and adjusted HRs are reported", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_match(out$text, "adjusted", ignore.case = TRUE)
  # header row of the TSV carries both columns
  expect_match(out$text, "[Uu]nadjusted")
})

test_that("adjusted arm HR recovers the simulated protective effect (< 1)", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  # Treated adjusted HR ~ exp(-0.7) = 0.50; assert it lands well below 1
  hr <- as.numeric(sub(".*armTreated[^0-9]*([0-9.]+).*", "\\1",
                        gsub("\n", " ", out$text)))
  expect_true(hr < 0.8)
})

test_that("reference level appears and can be overridden", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_match(out$svg, "reference", ignore.case = TRUE)
  out2 <- fig_cox(sc_cox(mk_cox_rows(), ref_levels = list(arm = "Treated")))
  expect_match(out2$svg, "Treated", fixed = TRUE)
})

test_that("no covariate selected errors readably", {
  expect_error(fig_cox(sc_cox(mk_cox_rows(), covariates = character(0))),
               "covariate", ignore.case = TRUE)
})

test_that("too few events errors readably", {
  rows <- mk_cox_rows()[1:12]
  # force nearly all censored
  rows <- lapply(rows, function(r) { r$status <- "alive"; r })
  rows[[1]]$status <- "dead"; rows[[2]]$status <- "dead"
  expect_error(fig_cox(sc_cox(rows)), "event", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `Rscript -e 'devtools::test(filter = "cox")'`
Expected: FAIL — `could not find function "fig_cox"`.

- [ ] **Step 3: Implement `R/cox.R`** (prep + fits + table + text; forest plot + script are separate helpers filled in Tasks 2–3, but stub them so this task's tests pass):

```r
# R/cox.R
# Cox proportional-hazards regression: univariable (unadjusted) HR per covariate
# beside the joint-model adjusted HR (clinical "Table 3"), plus an adjusted-HR
# forest plot. PH assumption checked with cox.zph and reported non-blocking.
# Reuses survival (already loaded for KM); no extra package.

# Detect numeric vs categorical for one column (non-throwing; mirrors
# .gc_is_numeric_col). TRUE iff every non-blank cell parses as numeric.
.cox_is_numeric <- function(rows, colname) {
  raw <- .char_col(rows, colname)
  raw[!is.na(raw) & raw == ""] <- NA
  num <- suppressWarnings(as.numeric(raw))
  !any(!is.na(raw) & is.na(num))
}

# Most frequent non-NA value of a character vector (default reference level).
.cox_most_frequent <- function(x) {
  x <- x[!is.na(x) & x != ""]
  names(sort(table(x), decreasing = TRUE))[1]
}

# Build the complete-case working frame and covariate metadata.
.cox_prep <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  covs <- unlist(spec$roles$covariates %||% list())
  if (length(covs) == 0) stop("Select at least one covariate.")
  tcol <- spec$roles$time; scol <- spec$roles$status
  if (is.null(tcol) || is.null(scol)) stop("Choose a time column and a status column.")
  have <- names(rows[[1]])
  for (cl in c(tcol, scol, covs))
    if (!(cl %in% have)) stop(sprintf("Column '%s' not found in the data.", cl))

  time <- .numeric_col(rows, tcol)
  ev <- as.character(spec$options$event_value %||% "")
  status_raw <- .char_col(rows, scol)
  ev_num <- suppressWarnings(as.numeric(ev))
  status <- as.integer(status_raw == ev |
    (!is.na(ev_num) & !is.na(suppressWarnings(as.numeric(status_raw))) &
       suppressWarnings(as.numeric(status_raw)) == ev_num))
  status[is.na(status)] <- NA_integer_

  cov_types <- setNames(
    vapply(covs, function(cl) if (.cox_is_numeric(rows, cl)) "numeric" else "categorical",
           character(1)), covs)
  ref_levels <- spec$options$ref_levels %||% list()

  cols <- list(time = time, status = status)
  for (cl in covs) {
    if (cov_types[[cl]] == "numeric") cols[[cl]] <- .numeric_col(rows, cl)
    else {
      v <- .char_col(rows, cl); v[!is.na(v) & v == ""] <- NA
      cols[[cl]] <- v
    }
  }
  df <- as.data.frame(cols, stringsAsFactors = FALSE, check.names = FALSE)
  n_before <- nrow(df)
  df <- df[stats::complete.cases(df) & is.finite(df$time) & df$time >= 0, , drop = FALSE]
  n_dropped <- n_before - nrow(df)

  # Factor + relevel categoricals; default reference = most frequent level.
  for (cl in covs) if (cov_types[[cl]] == "categorical") {
    ref <- as.character(ref_levels[[cl]] %||% .cox_most_frequent(df[[cl]]))
    lv <- unique(df[[cl]])
    if (length(lv) < 2) stop(sprintf("Covariate '%s' has only one level after removing missing values.", cl))
    if (!ref %in% lv) ref <- .cox_most_frequent(df[[cl]])
    df[[cl]] <- stats::relevel(factor(df[[cl]]), ref = ref)
  }
  events <- sum(df$status == 1)
  if (events < 10) stop(sprintf("Too few events (%d) to fit a reliable Cox model; at least 10 are needed.", events))
  list(df = df, covs = covs, cov_types = cov_types, ref_levels = ref_levels,
       n = nrow(df), events = events, n_dropped = n_dropped)
}

# Fit univariable coxph per covariate + one joint model. Expression-first so the
# script deparses the calls that ran. Model-fit warnings are captured (not
# suppressed) so an unreliable HR can be flagged rather than shipped silently.
.cox_fit_one <- function(formula, df) {
  warn <- NULL
  fit <- withCallingHandlers(
    survival::coxph(formula, data = df),
    warning = function(w) { warn <<- conditionMessage(w); invokeRestart("muffleWarning") })
  list(fit = fit, warn = warn)
}

.cox_fits <- function(df, covs, cov_types) {
  uni <- lapply(covs, function(cl)
    .cox_fit_one(stats::as.formula(sprintf("survival::Surv(time, status) ~ `%s`", cl)), df))
  names(uni) <- covs
  joint_f <- stats::as.formula(paste0("survival::Surv(time, status) ~ ",
    paste(sprintf("`%s`", covs), collapse = " + ")))
  joint <- .cox_fit_one(joint_f, df)
  list(uni = uni, joint = joint)
}

# Format one HR (95% CI, p); "not reliably estimated" when non-finite or warned.
.cox_hr_cell <- function(est, lo, hi, p, warn) {
  if (!is.null(warn) || !is.finite(est) || !is.finite(lo) || !is.finite(hi))
    return("not reliably estimated")
  pf <- if (p < 0.001) "p<0.001" else sprintf("p=%.3f", p)
  sprintf("%.2f (%.2f–%.2f, %s)", est, lo, hi, pf)
}

# One display row per covariate LEVEL (reference marked). Returns a list of
# list(term, unadj, adj) character cells.
.cox_rows <- function(p, fits) {
  rows <- list()
  jfit <- fits$joint$fit; jwarn <- fits$joint$warn
  jc <- stats::coef(jfit); jci <- suppressWarnings(stats::confint(jfit))
  jp <- summary(jfit)$coefficients[, "Pr(>|z|)"]
  for (cl in p$covs) {
    ufit <- fits$uni[[cl]]$fit; uwarn <- fits$uni[[cl]]$warn
    uc <- stats::coef(ufit); uci <- suppressWarnings(stats::confint(ufit))
    up <- summary(ufit)$coefficients[, "Pr(>|z|)"]
    if (p$cov_types[[cl]] == "numeric") {
      term <- sprintf("%s (per 1 unit)", cl)
      rows[[length(rows) + 1]] <- list(term = term,
        unadj = .cox_hr_cell(exp(uc[cl]), exp(uci[cl, 1]), exp(uci[cl, 2]), up[cl], uwarn),
        adj = .cox_hr_cell(exp(jc[cl]), exp(jci[cl, 1]), exp(jci[cl, 2]), jp[cl], jwarn))
    } else {
      lv <- levels(p$df[[cl]])
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (ref: %s)", cl, lv[1]),
        unadj = "", adj = "")
      for (l in lv[-1]) {
        key <- paste0(cl, l)
        rows[[length(rows) + 1]] <- list(term = paste0("  ", l),
          unadj = .cox_hr_cell(exp(uc[key]), exp(uci[key, 1]), exp(uci[key, 2]), up[key], uwarn),
          adj = .cox_hr_cell(exp(jc[key]), exp(jci[key, 1]), exp(jci[key, 2]), jp[key], jwarn))
      }
    }
  }
  rows
}

fig_cox <- function(spec) {
  p <- .cox_prep(spec)
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  disp_rows <- .cox_rows(p, fits)

  # PH assumption (non-blocking).
  zph <- tryCatch(survival::cox.zph(fits$joint$fit), error = function(e) NULL)
  gp <- if (!is.null(zph)) zph$table["GLOBAL", "p"] else NA_real_
  ph_line <- if (is.na(gp)) "" else {
    base <- sprintf(" The proportional-hazards assumption was assessed with scaled Schoenfeld residuals (global %s).",
                    if (gp < 0.001) "p<0.001" else sprintf("p=%.3f", gp))
    if (!is.na(gp) && gp < 0.05)
      paste0(base, " CAUTION: the assumption may not hold (global p<0.05); consider stratification, a time-varying effect, or statistical review before interpreting these hazard ratios.")
    else base
  }
  epv <- p$events / length(unlist(sapply(p$covs, function(cl)
    if (p$cov_types[[cl]] == "numeric") 1 else nlevels(p$df[[cl]]) - 1)))
  epv_line <- if (epv < 10)
    " CAUTION: fewer than 10 events per model term (EPV < 10); the adjusted estimates may be unstable." else ""

  table_html <- .cox_table_html(disp_rows)
  forest_svg <- .cox_forest_svg(p, fits)   # Task 2
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s</div>",
                       table_html, forest_svg)

  # text: TSV then methods sentence.
  tsv <- paste(c(paste(c("Characteristic", "Unadjusted HR (95% CI, p)",
                         "Adjusted HR (95% CI, p)"), collapse = "\t"),
                 vapply(disp_rows, function(r)
                   paste(c(r$term, r$unadj, r$adj), collapse = "\t"), character(1))),
               collapse = "\n")
  drop_note <- if (p$n_dropped > 0)
    sprintf(" %d row(s) with missing values were excluded.", p$n_dropped) else ""
  methods <- sprintf(paste0("Multivariable Cox proportional-hazards regression (n = %d, %d events) ",
    "adjusted for %s. Unadjusted hazard ratios are from single-covariate models; ",
    "adjusted hazard ratios are from the joint model.%s%s%s"),
    p$n, p$events, paste(p$covs, collapse = ", "), ph_line, epv_line, drop_note)
  text <- paste0(tsv, "\n\n", methods)

  list(svg = svg_field, text = text,
       code = .cox_script(spec, p, fits))   # Task 3
}

# HTML table (reuses .esc from R/summarize.R).
.cox_table_html <- function(disp_rows) {
  header <- "<tr><th>Characteristic</th><th>Unadjusted HR (95% CI)</th><th>Adjusted HR (95% CI)</th></tr>"
  body <- vapply(disp_rows, function(r) {
    indent <- startsWith(r$term, "  ")
    label <- .esc(trimws(r$term))
    if (indent) label <- paste0("<span class=\"lvl\">", label, "</span>")
    unadj <- if (nzchar(r$unadj)) .esc(r$unadj) else "1 (reference)"
    adj <- if (nzchar(r$adj)) .esc(r$adj) else "1 (reference)"
    # header rows for a categorical block (term has "(ref:")—blank cells stay blank
    if (grepl("\\(ref:", r$term)) { unadj <- ""; adj <- "" }
    sprintf("<tr><td>%s</td><td>%s</td><td>%s</td></tr>", label, unadj, adj)
  }, character(1))
  paste0("<table class=\"table1\"><thead>", header, "</thead><tbody>",
         paste(body, collapse = ""), "</tbody></table>")
}

# Stubs replaced in later tasks.
.cox_forest_svg <- function(p, fits) ""
.cox_script <- function(spec, p, fits) "# cox script (task 3)"
```

Then add to `R/dispatch.R` switch (after the `groupcompare` line):

```r
      cox     = fig_cox(spec),
```

- [ ] **Step 4: Run tests to verify pass**

Run: `Rscript -e 'devtools::test(filter = "cox")'`
Expected: PASS, `WARN 0`. (The `1 (reference)` reference test reads the table HTML.)

- [ ] **Step 5: Commit**

```bash
git add R/cox.R R/dispatch.R tests/testthat/test-cox.R
git commit -m "feat(cox): fig_cox core — univariable+adjusted HR table, PH check, guardrails"
```

---

### Task 2: Adjusted-HR forest plot (R)

**Files:**
- Modify: `R/cox.R` (replace the `.cox_forest_svg` stub)
- Test: `tests/testthat/test-cox.R` (add plot assertions)

**Interfaces:**
- Consumes: `.cox_prep`/`.cox_fits` output, `.km_palette`, `.fig_theme`, `.svg_string`.
- Produces: `.cox_forest_svg(p, fits)` → `<svg>` string of adjusted HRs on a log axis with a dashed rule at HR = 1.

- [ ] **Step 1: Add failing test**:

```r
test_that("forest plot draws a log-scale HR axis with a reference rule", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  # the forest svg follows the table inside the same output div
  expect_match(out$svg, "<svg", fixed = TRUE)
  # two svgs? no — one forest svg; assert the plot exists and text has HR
  expect_gt(nchar(out$svg), 500)
})
```

- [ ] **Step 2: Run, expect current pass (stub returns "")** — this test is weak by design; the real check is WARN 0 with a genuine plot. Run `Rscript -e 'devtools::test(filter = "cox")'`.

- [ ] **Step 3: Implement `.cox_forest_svg`** (replace stub):

```r
# Forest plot of ADJUSTED HRs (one point per non-reference level / numeric term),
# log x-axis, dashed rule at HR = 1. geom_errorbar(orientation="y") — never
# geom_errorbarh; linewidth — never size.
.cox_forest_svg <- function(p, fits) {
  jfit <- fits$joint$fit
  jc <- stats::coef(jfit); jci <- suppressWarnings(stats::confint(jfit))
  terms <- names(jc)
  keep <- is.finite(jc) & is.finite(jci[, 1]) & is.finite(jci[, 2])
  if (!any(keep)) return("")
  labeller <- function(key) {
    for (cl in p$covs) if (startsWith(key, cl)) {
      if (p$cov_types[[cl]] == "numeric") return(sprintf("%s (per 1 unit)", cl))
      return(sprintf("%s: %s", cl, sub(paste0("^", cl), "", key)))
    }
    key
  }
  d <- data.frame(
    term = vapply(terms[keep], labeller, character(1)),
    hr = exp(jc[keep]), lo = exp(jci[keep, 1]), hi = exp(jci[keep, 2]),
    stringsAsFactors = FALSE)
  d$term <- factor(d$term, levels = rev(d$term))
  pal <- .km_palette(nrow(d))
  gg <- ggplot2::ggplot(d, ggplot2::aes(x = hr, y = term, color = term)) +
    ggplot2::geom_vline(xintercept = 1, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), orientation = "y",
                           width = 0.2, linewidth = 0.6) +
    ggplot2::geom_point(size = 2.4) +
    ggplot2::scale_x_log10() +
    ggplot2::scale_color_manual(values = pal, guide = "none") +
    ggplot2::labs(x = "Adjusted hazard ratio (log scale)", y = NULL) +
    .fig_theme("generic")
  .svg_string(gg, width = 6, height = 0.5 + 0.5 * nrow(d))
}
```

- [ ] **Step 4: Run tests**

Run: `Rscript -e 'devtools::test(filter = "cox")'`
Expected: PASS, WARN 0. (If a `geom_errorbar`/`orientation` warning leaks, fix at source.)

- [ ] **Step 5: Commit**

```bash
git add R/cox.R tests/testthat/test-cox.R
git commit -m "feat(cox): adjusted-HR forest plot (log axis, orientation=y, WARN 0)"
```

---

### Task 3: Downloadable `.R` script (R)

**Files:**
- Modify: `R/cox.R` (replace `.cox_script` stub)
- Test: `tests/testthat/test-cox.R` (script parses + reproduces HRs)

**Interfaces:**
- Consumes: `.script_assemble`, `.script_dep`, `.script_header`, `.script_data` (`R/script.R`); `.cox_prep`/`.cox_fits`.
- Produces: `.cox_script(spec, p, fits)` → complete runnable R script string.

- [ ] **Step 1: Add failing tests**:

```r
test_that("cox code parses as R and mentions coxph + cox.zph", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_silent(parse(text = out$code))
  expect_match(out$code, "coxph", fixed = TRUE)
  expect_match(out$code, "cox.zph", fixed = TRUE)
})

test_that("demo-shape spec embeds data (no read.csv) in the script", {
  out <- fig_cox(sc_cox(mk_cox_rows()))   # no source_filename -> embedded
  expect_match(out$code, "data.frame", fixed = TRUE)
  expect_false(grepl("read.csv", out$code, fixed = TRUE))
})
```

- [ ] **Step 2: Run, expect FAIL** (`coxph`/`cox.zph` not in the stub string).

Run: `Rscript -e 'devtools::test(filter = "cox")'`

- [ ] **Step 3: Implement `.cox_script`** (replace stub):

```r
# Downloadable R script: the exact univariable + joint coxph calls (deparsed),
# cox.zph, and an equivalent forest-plot ggplot. For uploads, prep reads the
# user's REAL column names + event coding (source_roles), exactly like .km_script.
.cox_script <- function(spec, p, fits) {
  opts <- spec$options %||% list()
  qe <- function(s) gsub('"', '\\\\"', s)
  covs <- p$covs
  sr <- if (nzchar(as.character(opts$source_filename %||% ""))) opts$source_roles else NULL
  ev <- qe(as.character(opts$event_value %||% ""))

  # Column expressions: uploads read df[["real name"]]; embedded demo uses df$<col>.
  if (!is.null(sr)) {
    tcol <- sprintf('df[["%s"]]', qe(sr$time)); scol_raw <- sprintf('df[["%s"]]', qe(sr$status))
    cov_expr <- function(cl) sprintf('df[["%s"]]', qe(cl))
  } else {
    tcol <- "df$time"; scol_raw <- "df$status"
    cov_expr <- function(cl) sprintf('df[["%s"]]', qe(cl))
  }

  prep <- c(
    sprintf('# Event coding: status == "%s" marks the event; all else censored.', ev),
    sprintf('status_raw <- %s', scol_raw),
    sprintf(paste0('status <- as.integer(as.character(status_raw) == "%s" | ',
                   '(!is.na(suppressWarnings(as.numeric("%s"))) & ',
                   '!is.na(suppressWarnings(as.numeric(status_raw))) & ',
                   'suppressWarnings(as.numeric(status_raw)) == suppressWarnings(as.numeric("%s"))))'),
            ev, ev, ev),
    sprintf('dat <- data.frame(time = as.numeric(%s), status = status,', tcol),
    paste0("                  ",
      paste(vapply(covs, function(cl) sprintf('`%s` = %s', qe(cl), cov_expr(cl)),
                   character(1)), collapse = ",\n                  "), ","),
    "                  check.names = FALSE, stringsAsFactors = FALSE)",
    "dat <- dat[complete.cases(dat) & is.finite(dat$time) & dat$time >= 0, ]")

  # Relevel categoricals to the chosen reference.
  relevel_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "categorical") return(NULL)
    ref <- qe(as.character(p$ref_levels[[cl]] %||% .cox_most_frequent(p$df[[cl]])))
    sprintf('dat[["%s"]] <- relevel(factor(dat[["%s"]]), ref = "%s")', qe(cl), qe(cl), ref)
  }))

  uni_lines <- unlist(lapply(covs, function(cl) c(
    sprintf('# Unadjusted HR for %s', cl),
    sprintf('summary(coxph(Surv(time, status) ~ `%s`, data = dat))', qe(cl)), "")))
  joint_rhs <- paste(sprintf("`%s`", covs), collapse = " + ")
  joint_lines <- c(
    "# Adjusted (joint) model:",
    sprintf("fit <- coxph(Surv(time, status) ~ %s, data = dat)", joint_rhs),
    "summary(fit)", "",
    "# Proportional-hazards check:",
    "cox.zph(fit)", "")
  fig_lines <- c(
    "# Equivalent forest plot of the adjusted hazard ratios:",
    "library(ggplot2)",
    "co <- summary(fit)$conf.int",
    "fp <- data.frame(term = rownames(co), hr = co[, 1],",
    "                 lo = co[, 3], hi = co[, 4])",
    "fp$term <- factor(fp$term, levels = rev(fp$term))",
    "p_forest <- ggplot(fp, aes(hr, term)) +",
    '  geom_vline(xintercept = 1, linetype = "dashed", colour = "grey50") +',
    '  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0.2) +',
    "  geom_point(size = 2.4) + scale_x_log10() +",
    '  labs(x = "Adjusted hazard ratio (log scale)", y = NULL) +',
    "  theme_minimal(base_size = 12)",
    '# print(p_forest)')

  body <- c("library(survival)", "", prep, "", relevel_lines,
            if (length(relevel_lines)) "" else NULL,
            uni_lines, joint_lines, fig_lines)
  .script_assemble("Cox proportional-hazards regression", spec,
                   c(spec$roles$time, spec$roles$status, covs),
                   c("survival", "ggplot2"), body)
}
```

- [ ] **Step 4: Run tests**

Run: `Rscript -e 'devtools::test(filter = "cox")'`
Expected: PASS, WARN 0.

- [ ] **Step 5: Commit**

```bash
git add R/cox.R tests/testthat/test-cox.R
git commit -m "feat(cox): downloadable .R script (deparsed coxph + cox.zph + forest)"
```

---

### Task 4: Dispatch smoke test + worker wiring (R + JS)

**Files:**
- Modify: `web/worker.js:11` (EXTRA_PACKAGES), `:15-17` (EXTRA_PACKAGES_MESSAGE), `:41` (fetch loop)
- Modify: `tests/testthat/test-dispatch.R` (add a cox route case)

**Interfaces:**
- Produces: `render_figure` routes `figure="cox"`; worker fetches `cox.R` at boot and installs `survival` lazily for cox.

- [ ] **Step 1: Add failing dispatch test** in `tests/testthat/test-dispatch.R`:

```r
test_that("render_figure routes cox and returns ok JSON", {
  set.seed(7)
  n <- 120
  rows <- lapply(seq_len(n), function(i) list(
    time = round(rexp(1, 0.1) + 0.1, 2),
    status = if (runif(1) < 0.6) "dead" else "alive",
    arm = if (i %% 2) "A" else "B"))
  spec <- list(figure = "cox", data = rows,
               roles = list(time = "time", status = "status",
                            covariates = list("arm")),
               options = list(event_value = "dead", ref_levels = list()))
  res <- jsonlite::fromJSON(render_figure(jsonlite::toJSON(spec, auto_unbox = TRUE)))
  expect_true(res$ok)
  expect_match(res$svg, "<table", fixed = TRUE)
})
```

- [ ] **Step 2: Run, expect FAIL** (unknown figure until dispatch wired — but Task 1 already added the switch line, so this should route). Run `Rscript -e 'devtools::test(filter = "dispatch")'`. If it passes already, good — the test locks the contract.

- [ ] **Step 3: Wire the worker.** In `web/worker.js`:
  - Line 11: `const EXTRA_PACKAGES = { km: ["survival", "cowplot"], cox: ["survival"] };`
  - In `EXTRA_PACKAGES_MESSAGE`, add:
    `cox: "Downloading the survival-analysis package — usually 15–25 seconds, first time only. Later runs are instant.",`
  - Line 41 fetch loop: add `"cox.R"` to the array (after `"groupcompare.R"`).

- [ ] **Step 4: Run R suite**

Run: `Rscript -e 'devtools::test(filter = "dispatch")'`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/worker.js tests/testthat/test-dispatch.R
git commit -m "feat(cox): dispatch route + worker fetch/EXTRA_PACKAGES wiring"
```

---

### Task 5: Frozen demo dataset (R generator → fixture + demo-data.js)

**Files:**
- Create: `data-raw/cox-demo-generator.R`, `tests/testthat/fixtures/cox-demo.csv`, `web/guided/cox/demo-data.js`
- Test: `tests/testthat/test-cox-demo.R`

**Interfaces:**
- Produces: `COX_DEMO` export in `web/guided/cox/demo-data.js` with `columns`/`rows`/`label`/`version`; a fixture CSV; a dataset whose adjusted arm HR differs visibly from its unadjusted HR.

- [ ] **Step 1: Write `data-raw/cox-demo-generator.R`** (mirror `groupcompare-demo-generator.R` structure):

```r
# data-raw/cox-demo-generator.R
# Frozen Cox demonstration dataset. Two arms (Standard care / New treatment),
# baseline age, and an ordinal stage (I/II/III). Engineered so age and stage
# confound the arm effect: the UNADJUSTED arm HR is near 1, but adjusting for
# age + stage reveals a protective adjusted HR (~0.6). Byte-reproducible; bump
# COX_DEMO.version on any change.
set.seed(73)
n <- 220
arm <- rep(c("Standard care", "New treatment"), each = n / 2)
age <- round(rnorm(n, 62, 9))
stage <- sample(c("I", "II", "III"), n, replace = TRUE, prob = c(0.4, 0.35, 0.25))
# Confounding: New treatment arm skews to older/sicker patients (channeling).
sicker <- (arm == "New treatment")
age <- round(age + 5 * sicker)
stage_idx <- as.integer(factor(stage, levels = c("I", "II", "III")))
lp <- 0.05 * (age - 62) + 0.45 * (stage_idx - 1) - 0.55 * (arm == "New treatment")
time <- round(rexp(n, rate = 0.03 * exp(lp)) + 0.2, 1)
cens <- time > 36
time[cens] <- 36
status <- ifelse(cens, "Censored", "Death")

out <- data.frame(arm = arm, age = age, stage = stage,
                  followup_months = time, status = status,
                  stringsAsFactors = FALSE)
write.csv(out, "tests/testthat/fixtures/cox-demo.csv",
          row.names = FALSE, quote = FALSE)

rows_list <- lapply(seq_len(nrow(out)), function(i) as.list(out[i, ]))
rows_json <- jsonlite::toJSON(rows_list, auto_unbox = TRUE, digits = NA)
js <- paste0(
  "// GENERATED by data-raw/cox-demo-generator.R — do not hand-edit.\n",
  "export const COX_DEMO = {\n",
  '  version: "1.0.0",\n',
  '  label: "Synthetic demonstration data",\n',
  '  columns: ["arm", "age", "stage", "followup_months", "status"],\n',
  "  rows: ", rows_json, "\n};\n")
writeLines(js, "web/guided/cox/demo-data.js")
cat("md5(csv):", unname(tools::md5sum("tests/testthat/fixtures/cox-demo.csv")), "\n")
```

- [ ] **Step 2: Generate the artifacts**

Run: `mkdir -p web/guided/cox && Rscript data-raw/cox-demo-generator.R`
Expected: prints an md5; creates the CSV and `demo-data.js`.

- [ ] **Step 3: Write `tests/testthat/test-cox-demo.R`**:

```r
test_that("frozen cox demo fits and adjusted arm HR is protective", {
  csv <- read.csv(test_path("fixtures", "cox-demo.csv"), stringsAsFactors = FALSE)
  rows <- lapply(seq_len(nrow(csv)), function(i) as.list(csv[i, ]))
  spec <- list(figure = "cox", data = rows,
    roles = list(time = "followup_months", status = "status",
                 covariates = list("arm", "age", "stage")),
    options = list(event_value = "Death", ref_levels = list(arm = "Standard care")))
  out <- fig_cox(spec)
  hr <- as.numeric(sub(".*New treatment[^0-9]*([0-9.]+).*", "\\1",
                       gsub("\n", " ", out$text)))
  expect_true(hr < 0.9)   # adjusted protective effect visible
})
```

- [ ] **Step 4: Run**

Run: `Rscript -e 'devtools::test(filter = "cox-demo")'`
Expected: PASS, WARN 0.

- [ ] **Step 5: Commit**

```bash
git add data-raw/cox-demo-generator.R tests/testthat/fixtures/cox-demo.csv web/guided/cox/demo-data.js tests/testthat/test-cox-demo.R
git commit -m "feat(cox): frozen synthetic demo dataset (confounded arm effect)"
```

---

### Task 6: Web spec builder + JS unit test

**Files:**
- Create: `web/guided/cox/spec.js`, `web/guided/cox/spec.test.mjs`

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces: `buildCoxSpec(table, roles, eventValue, refLevels, options)` → cox spec; `distinctValues(table, col)` (re-exported for the form); `mostFrequent(table, col)`.

- [ ] **Step 1: Write `web/guided/cox/spec.test.mjs`**:

```js
import { buildCoxSpec, mostFrequent } from "./spec.js";
import assert from "node:assert";

const table = { columns: ["t", "s", "arm", "age", "extra"],
  rows: [ { t: "5", s: "dead", arm: "A", age: "60", extra: "x" },
          { t: "9", s: "alive", arm: "B", age: "70", extra: "y" },
          { t: "3", s: "dead", arm: "A", age: "65", extra: "z" } ] };
const roles = { time: "t", status: "s", covariates: ["arm", "age"] };

const spec = buildCoxSpec(table, roles, "dead", { arm: "B" },
  { source_filename: "f.csv" });
assert.equal(spec.figure, "cox");
assert.deepEqual(spec.roles.covariates, ["arm", "age"]);
assert.equal(spec.options.event_value, "dead");
assert.deepEqual(spec.options.ref_levels, { arm: "B" });
// only mapped columns cross — never "extra"
assert.ok(!("extra" in spec.data[0]));
assert.equal(spec.options.source_roles.time, "t");
assert.equal(mostFrequent(table, "arm"), "A");
console.log("cox spec.test.mjs ok");
```

- [ ] **Step 2: Run, expect FAIL** (`spec.js` missing).

Run: `node web/guided/cox/spec.test.mjs`
Expected: FAIL — cannot find module.

- [ ] **Step 3: Write `web/guided/cox/spec.js`**:

```js
// Pure spec assembly for Cox regression. Only the mapped columns cross to the
// worker (no-egress); status stays a raw string (R recodes it from event_value,
// as KM does). source_roles lets the .R script read the user's real column names.
export function buildCoxSpec(table, roles, eventValue, refLevels, options) {
  const used = [roles.time, roles.status, ...roles.covariates];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "cox",
    data,
    roles: { time: roles.time, status: roles.status,
             covariates: roles.covariates.slice() },
    options: {
      event_value: String(eventValue),
      ref_levels: refLevels || {},
      source_filename: options.source_filename ?? null,
      source_roles: { time: roles.time, status: roles.status,
                      covariates: roles.covariates.slice(),
                      event: String(eventValue) },
    },
  };
}

// Distinct non-blank values, first-appearance order (feeds the event picker).
export function distinctValues(table, col) {
  const seen = [];
  for (const r of table.rows) {
    const v = r[col];
    if (v == null || String(v).trim() === "") continue;
    const s = String(v);
    if (!seen.includes(s)) seen.push(s);
  }
  return seen;
}

// Most frequent non-blank value of a column (default reference level).
export function mostFrequent(table, col) {
  const counts = new Map();
  for (const r of table.rows) {
    const v = r[col];
    if (v == null || String(v).trim() === "") continue;
    const s = String(v);
    counts.set(s, (counts.get(s) || 0) + 1);
  }
  let best = null, n = -1;
  for (const [k, c] of counts) if (c > n) { best = k; n = c; }
  return best;
}
```

- [ ] **Step 4: Run**

Run: `node web/guided/cox/spec.test.mjs`
Expected: `cox spec.test.mjs ok`. Also confirm the runner picks it up: `npm run test:unit`.

- [ ] **Step 5: Commit**

```bash
git add web/guided/cox/spec.js web/guided/cox/spec.test.mjs
git commit -m "feat(cox): pure spec builder + JS unit tests (no-egress projection)"
```

---

### Task 7: Analyze form, content, demo, shell config, app+html registration

**Files:**
- Create: `web/guided/cox/analyze-form.js`, `web/guided/cox/content.js`, `web/guided/cox/demo.js`, `web/guided/cox/guided-cox.js`
- Modify: `web/app.js:103-109` (import + registry), `web/index.html:35-42` (nav button)

**Interfaces:**
- Consumes: `createGuidedShell` (`shell.js`), `parseCsv`/`toCsv` (`csv.js`), `renderColumnPicker` (`columnpicker.js`), `buildCoxSpec`/`distinctValues`/`mostFrequent` (`spec.js`), `COX_DEMO` (`demo-data.js`).
- Produces: `renderGuidedCox(container, onSubmit, runFigure, setStatus)` registered as `cox` in the form registry.

- [ ] **Step 1: Write `web/guided/cox/content.js`** (Understand copy + experiments):

```js
// web/guided/cox/content.js
import { COX_DEMO } from "./demo-data.js";

const SECTIONS = [
  { title: "Adjust for what else is going on", html: `
    <p>Kaplan–Meier shows whether survival curves differ. Cox regression answers
    the next question: <em>by how much, after accounting for the other things that
    differ between patients?</em> Each covariate gets a hazard ratio — the relative
    event rate per unit (for a number) or versus a reference level (for a category).</p>
    <p>Unadjusted hazard ratios come from one model per covariate. Adjusted hazard
    ratios come from a single joint model, so each is the effect of that variable
    holding the others fixed — the difference between the two columns is the
    confounding the adjustment removed.</p>` },
  { title: "Is Cox appropriate?", html: `
    <p>Use it when each row is one independent participant with a follow-up time, an
    event/censoring status, and the baseline covariates you want to adjust for. The
    model assumes <strong>proportional hazards</strong>: the hazard ratio for each
    covariate is roughly constant over time.</p>
    <p>This tool checks that assumption with scaled Schoenfeld residuals and warns
    when it looks violated, but it does not fit stratified, time-varying, or
    competing-risks models. If curves cross or the check flags a covariate, seek
    statistical review.</p>` },
  { title: "How to read the result", html: `
    <ul>
      <li><strong>HR &lt; 1</strong>: lower event rate (protective). <strong>HR &gt; 1</strong>: higher.</li>
      <li>A numeric covariate's HR is <strong>per one unit</strong> — scale the variable if a unit is too small to be meaningful.</li>
      <li>A category's HR is <strong>versus its reference level</strong>, shown as "1 (reference)".</li>
      <li>A 95% CI that crosses 1 means the effect is not statistically resolved.</li>
    </ul>` },
];

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("");
}

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic survival study</h3>
  <p>This teaching dataset has ${"220"} fictional patients on <strong>Standard care</strong>
  or a <strong>New treatment</strong>, with baseline age and disease stage. The treatment
  was preferentially given to older, higher-stage patients — so the unadjusted treatment
  effect looks weak, and only adjusting for age and stage reveals it. Toggle the covariates
  below to watch the treatment's adjusted hazard ratio move.</p>`;

// Experiments: check/uncheck which covariates enter the joint model.
export function renderCoxExperiments(panel, ctx, rerun) {
  const host = panel.querySelector("#demo-experiments");
  host.innerHTML = "";
  const ALL = ["arm", "age", "stage"];
  const state = ctx.getSession().demoOptions;
  const fieldset = document.createElement("fieldset");
  fieldset.innerHTML = "<legend>Covariates in the model</legend>";
  for (const c of ALL) {
    const id = "cov-" + c;
    const label = document.createElement("label");
    label.className = "inline-check";
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.id = id; cb.value = c;
    cb.checked = state.covariates.includes(c);
    cb.disabled = c === "arm";   // arm always in (it's the exposure of interest)
    cb.onchange = () => {
      const now = ctx.getSession().demoOptions.covariates.filter((x) => x !== c);
      if (cb.checked) now.push(c);
      // keep canonical order
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

- [ ] **Step 2: Write `web/guided/cox/demo.js`**:

```js
import { COX_DEMO } from "./demo-data.js";

export const DEMO_TABLE = {
  columns: COX_DEMO.columns,
  rows: COX_DEMO.rows,
  types: { arm: "categorical", age: "numeric", stage: "categorical",
           followup_months: "numeric", status: "categorical" },
};

export function DEFAULT_DEMO_STATE() {
  return { covariates: ["arm", "age", "stage"] };
}

export function buildCoxDemoSpec(demoState) {
  const used = ["followup_months", "status", ...demoState.covariates];
  const data = COX_DEMO.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "cox",
    data,
    roles: { time: "followup_months", status: "status",
             covariates: demoState.covariates.slice() },
    options: { event_value: "Death",
               ref_levels: { arm: "Standard care", stage: "I" },
               caption: COX_DEMO.label },
  };
}
```

- [ ] **Step 3: Write `web/guided/cox/analyze-form.js`** (KM analyze-form pattern + covariate multi-select + reference dropdowns):

```js
// web/guided/cox/analyze-form.js
// Progressive-disclosure upload UI for Cox, on the shared csv/columnpicker
// foundation. Config (roles, event value, covariate reference levels, Render)
// stays hidden until a CSV parse succeeds; a parse failure re-hides and clears.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildCoxSpec, distinctValues, mostFrequent } from "./spec.js";
import { COX_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(COX_DEMO.rows, COX_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderCoxAnalyzeForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A numeric follow-up time column, in consistent units.</li>
        <li>A status column where one value marks the event; you confirm which below.</li>
        <li>One or more covariate columns to adjust for (numeric or categorical).</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-cox.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="cox-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#cox-config");
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
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);

        const eventLabel = doc.createElement("label");
        eventLabel.textContent = "Which value of the status column means the event occurred? ";
        const eventSel = doc.createElement("select"); eventSel.id = "cox-event";
        eventLabel.htmlFor = "cox-event";
        const eventHint = doc.createElement("p");
        eventHint.className = "hint";
        eventHint.textContent = "All other values count as censored.";

        // Reference-level area: one dropdown per categorical covariate.
        const refWrap = doc.createElement("div"); refWrap.id = "cox-refs";

        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "cox-render";
        btn.textContent = "Render Cox model"; btn.disabled = true;
        const note = doc.createElement("p"); note.id = "cox-dropped-note"; note.className = "hint";

        let statusCol = null;
        const isNumericCol = (col) => table.types[col] === "numeric";
        const syncReady = () => {
          btn.disabled = !roles || !roles.covariates || roles.covariates.length === 0
            || !eventSel.value;
        };
        const fillEventOptions = () => {
          eventSel.innerHTML = "";
          const ph = doc.createElement("option"); ph.value = ""; ph.textContent = "— choose —";
          eventSel.appendChild(ph);
          if (statusCol) for (const v of distinctValues(table, statusCol)) {
            const o = doc.createElement("option"); o.value = v; o.textContent = v;
            eventSel.appendChild(o);
          }
          eventSel.disabled = !statusCol;
          syncReady();
        };
        const renderRefs = () => {
          refWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          for (const c of roles.covariates) {
            if (isNumericCol(c)) continue;   // numeric covariate -> per-unit HR, no reference
            const l = doc.createElement("label");
            l.textContent = `Reference level for ${c} `;
            const s = doc.createElement("select"); s.id = "cox-ref-" + c;
            s.dataset.cov = c;
            for (const v of distinctValues(table, c)) {
              const o = doc.createElement("option"); o.value = v; o.textContent = v;
              s.appendChild(o);
            }
            s.value = mostFrequent(table, c);
            l.appendChild(s); refWrap.appendChild(l);
          }
        };

        renderColumnPicker(pick,
          [{ key: "time", label: "Follow-up time", type: "numeric" },
           { key: "status", label: "Event status", type: "any" },
           { key: "covariates", label: "Covariates to adjust for", type: "any", multiple: true }],
          table, (v) => {
            roles = v;
            const s = v ? v.status : null;
            if (s !== statusCol) { statusCol = s; fillEventOptions(); }
            renderRefs();
            syncReady();
          }, doc);
        eventSel.onchange = syncReady;
        fillEventOptions();

        config.appendChild(eventLabel);
        eventLabel.appendChild(eventSel);
        config.appendChild(eventHint);
        config.appendChild(refWrap);

        btn.onclick = () => {
          if (!roles || !eventSel.value) return;
          const refLevels = {};
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => {
            refLevels[s.dataset.cov] = s.value;
          });
          const spec = buildCoxSpec(table, roles, eventSel.value, refLevels,
            { source_filename: fileName });
          // count dropped rows for the note (complete-case on mapped cols)
          const used = [roles.time, roles.status, ...roles.covariates];
          const dropped = table.rows.filter((r) =>
            used.some((c) => r[c] == null || String(r[c]).trim() === "")).length;
          note.textContent = dropped > 0
            ? `${dropped} row(s) with missing values will be excluded.` : "";
          onSubmit(spec);
        };
        config.appendChild(btn);
        config.appendChild(note);
        config.hidden = false;
      } catch (err) {
        table = null; config.hidden = true; config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}
```

- [ ] **Step 4: Write `web/guided/cox/guided-cox.js`**:

```js
// web/guided/cox/guided-cox.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderCoxExperiments } from "./content.js";
import { buildCoxDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { COX_DEMO } from "./demo-data.js";
import { renderCoxAnalyzeForm } from "./analyze-form.js";

export const renderGuidedCox = createGuidedShell({
  title: "Cox regression",
  hashPrefix: "cox",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: COX_DEMO.label,
  buildDemoSpec: buildCoxDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments input",
  renderExperiments: renderCoxExperiments,
  renderAnalyzeForm: renderCoxAnalyzeForm,
});
```

- [ ] **Step 5: Register in `web/app.js`.** Add import beside the others (after line 106):

```js
import { renderGuidedCox } from "./guided/cox/guided-cox.js";
```

And add `cox` to the registry object:

```js
const forms = { summary: renderGuidedSummary, km: renderGuidedKm,
                explore: renderGuidedExplore, groupcompare: renderGuidedGroupCompare,
                cox: renderGuidedCox };
```

- [ ] **Step 6: Add the nav button in `web/index.html`** after the groupcompare button (line 42), inside the "Statistical analyses" group:

```html
        <button data-figure="cox">
          <span class="nav-label">Cox regression</span>
          <span class="nav-desc">Adjusted hazard ratios — Table 3 and forest plot</span>
        </button>
```

- [ ] **Step 7: Verify JS unit suite still green**

Run: `npm run test:unit`
Expected: PASS (includes the new `spec.test.mjs`).

- [ ] **Step 8: Commit**

```bash
git add web/guided/cox/ web/app.js web/index.html
git commit -m "feat(cox): guided shell config, analyze form, content, demo, nav registration"
```

---

### Task 8: E2E test + full-suite verification

**Files:**
- Create: `tests/e2e/cox-guided.spec.js`

**Interfaces:**
- Consumes: the running app (served from `web/` after the `web/R` copy).

- [ ] **Step 1: Write `tests/e2e/cox-guided.spec.js`** (model on `groupcompare-guided.spec.js`):

```js
import { test, expect } from "@playwright/test";

test("Cox guided: understand renders and demo fits a table + forest plot", async ({ page }) => {
  await page.goto("/");
  await page.click('[data-figure="cox"]');
  await expect(page.getByRole("heading", { name: /Adjust for what else/i })).toBeVisible();

  await page.click("#tab-example");
  await page.click("#run-demo");
  // webR cold boot + survival install can be slow
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 120000 });
  await expect(page.locator("#preview svg")).toBeVisible();
  await expect(page.locator("#stats")).toContainText(/adjusted/i);
  await expect(page.locator("#export-r")).toBeEnabled();
});
```

- [ ] **Step 2: Build the R copy and run the new spec**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/cox-guided.spec.js`
Expected: PASS (first run downloads webR; allow time).

- [ ] **Step 3: Full R suite (WARN-0 gate)**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | SKIP ? | PASS ? ]`.

- [ ] **Step 4: Full JS unit + full e2e**

Run: `npm run test:unit && rm -rf web/R && cp -R R web/R && npm run test:e2e`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/cox-guided.spec.js
git commit -m "test(cox): e2e demo + analyze flow; full suite green"
```

---

## Self-Review

**Spec coverage:**
- Five parallel keys → Tasks 1 (R+dispatch), 4 (worker), 7 (web form/registry/html), demo Task 5, DESCRIPTION unchanged (noted). ✓
- Univariable+adjusted table → Task 1. Forest plot → Task 2. `.R` script → Task 3. ✓
- Reference-level auto+override → Task 1 (`.cox_most_frequent`, `ref_levels`), Task 7 (per-covariate dropdown default = `mostFrequent`). ✓
- PH diagnostics non-blocking + EPV caution → Task 1. ✓
- Guardrails (no covariate, too few events, constant covariate, separation) → Task 1. ✓
- No-egress projection → Task 6 test asserts `extra` absent. ✓
- Lazy survival install / no new package → Task 4; DESCRIPTION already has survival. ✓
- Demo confounded so adjusted ≠ unadjusted → Task 5 generator + test. ✓
- Tests: R core/demo/script/dispatch, JS unit, e2e → Tasks 1–8. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `.cox_prep` returns `covs/cov_types/ref_levels/df/n/events/n_dropped` — consumed consistently in `.cox_rows`, `.cox_forest_svg`, `.cox_script`, `fig_cox`. JS `buildCoxSpec(table, roles, eventValue, refLevels, options)` signature matches the analyze-form call and the unit test. `renderCoxExperiments`/`renderUnderstand`/`EXAMPLE_INTRO_HTML` names match `guided-cox.js` imports. Demo state shape `{covariates:[...]}` consistent across `demo.js`, `content.js` experiments, and `buildCoxDemoSpec`. ✓

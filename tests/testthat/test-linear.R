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
  expect_match(out$svg, "<td>0 (reference)</td><td>0 (reference)</td>", fixed = TRUE)
  expect_false(grepl("1 (reference)", out$svg, fixed = TRUE))
  # The TSV header row stays blank: the validation parser's contract.
  expect_match(out$text, "arm (reference: Control)\t\t\n", fixed = TRUE)
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

test_that("a perfect fit stops readably and leaks no summary.lm warning", {
  rows <- lapply(mk_lin_rows(), function(r) { r$los <- 2 * r$age; r })
  expect_error(fig_linear(sc_lin(rows)), "perfect fit")
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

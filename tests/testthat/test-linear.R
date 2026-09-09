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
  expect_match(out$text, "Residuals depart from normality \\(Shapiro–Wilk p[<=][0-9.]+\\); with n = 240 the coefficient estimates are unaffected, and the confidence intervals are usually robust to this unless the residual plots also show non-constant variance or influential points\\.")
})

test_that("Shapiro-Wilk caution uses the small-n tail under 30 observations", {
  set.seed(6)
  rows <- lapply(1:25, function(i) list(los = round(rexp(1, 0.2), 2), age = 40 + i))
  out <- fig_linear(sc_lin(rows, covariates = "age"))
  expect_match(out$text, "with n = 25 the confidence intervals may be unreliable; consider transforming the outcome", fixed = TRUE)
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

test_that("the script runs on 5,001 rows, where the app skips Shapiro-Wilk", {
  # shapiro.test() errors outside 3..5000 observations; the app guards it, and an
  # unguarded export would stop where the app carried on.
  set.seed(12)
  rows <- lapply(1:5001, function(i) list(los = round(rnorm(1, 6, 2), 2), age = 40 + (i %% 50)))
  out <- fig_linear(sc_lin(rows, covariates = "age"))
  expect_false(grepl("Shapiro", out$text, fixed = TRUE))
  env <- new.env(parent = globalenv())
  expect_silent(eval(parse(text = out$code), env))
})

test_that("the script runs for a single non-syntactic covariate", {
  rows <- lapply(mk_lin_rows(), function(r) list(los = r$los, `study arm` = r$arm))
  out <- fig_linear(sc_lin(rows, covariates = "study arm"))
  env <- new.env(parent = globalenv())
  expect_silent(eval(parse(text = out$code), env))
  expect_true("fit" %in% ls(env))
})

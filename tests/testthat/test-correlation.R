mkspec <- function(method = "pearson") {
  set.seed(3); x <- rnorm(80); y <- 0.7 * x + rnorm(80, sd = 0.6)
  data <- lapply(seq_along(x), function(i) list(x = x[i], y = y[i]))
  list(figure = "correlation", data = data, roles = list(x = "x", y = "y"),
       options = list(method = method))
}

test_that("pearson returns an SVG, r, and p", {
  out <- fig_correlation(mkspec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "r =")
  expect_match(out$text, "Pearson", ignore.case = TRUE)
  expect_match(out$text, "p ?=|p ?<")
})

test_that("known-value: r is close to cor()", {
  set.seed(3); x <- rnorm(80); y <- 0.7 * x + rnorm(80, sd = 0.6)
  expected <- round(cor(x, y), 2)
  out <- fig_correlation(mkspec())
  expect_match(out$text, sprintf("r = %.2f", expected))
})

test_that("spearman reports rho", {
  expect_match(fig_correlation(mkspec("spearman"))$text, "rho|Spearman", ignore.case = TRUE)
})

test_that("errors when a column is non-numeric / too few points", {
  bad <- mkspec(); bad$data <- bad$data[1]
  expect_error(fig_correlation(bad), "at least", ignore.case = TRUE)
})

test_that("errors clearly when a column has non-numeric text, without a coercion warning", {
  bad <- mkspec()
  bad$data[[1]]$x <- "not-a-number"
  expect_error(fig_correlation(bad), "numeric", ignore.case = TRUE)
})

test_that("spearman with ties does not warn and reports rho", {
  x <- rep(1:5, 10); y <- rep(1:5, each = 10)
  data <- lapply(seq_along(x), function(i) list(x = x[i], y = y[i]))
  spec <- list(figure = "correlation", data = data, roles = list(x = "x", y = "y"),
               options = list(method = "spearman"))
  expect_no_warning(out <- fig_correlation(spec))
  expect_match(out$text, "rho")
})

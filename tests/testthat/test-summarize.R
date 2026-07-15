test_that("skewness is ~0 for symmetric data and positive for right-skew", {
  set.seed(1)
  expect_lt(abs(.skewness(rnorm(500))), 0.3)
  expect_gt(.skewness(rexp(500)), 1)
})

test_that("approximately normal data (small n) picks mean and cites Shapiro-Wilk", {
  set.seed(42); x <- rnorm(200, mean = 50, sd = 8)
  d <- .summary_decide(x)
  expect_equal(d$kind, "mean")
  expect_match(d$reason, "normal", ignore.case = TRUE)
  expect_match(d$reason, "Shapiro")
})

test_that("right-skewed data (small n) picks median and names the skew direction", {
  set.seed(3); x <- rexp(200, rate = 0.2)
  d <- .summary_decide(x)
  expect_equal(d$kind, "median")
  expect_match(d$reason, "skew", ignore.case = TRUE)
  expect_match(d$reason, "right", ignore.case = TRUE)
})

test_that("a Shapiro p below 0.001 never prints as p = 0.000", {
  set.seed(4); x <- rexp(250, rate = 0.5)
  expect_false(grepl("0.000", .summary_decide(x)$reason, fixed = TRUE))
})

test_that("above n = 300 the decision rests on skewness alone (no Shapiro)", {
  set.seed(5)
  d_sym <- .summary_decide(rnorm(2000))
  expect_equal(d_sym$kind, "mean")
  expect_false(grepl("Shapiro", d_sym$reason))
  expect_match(d_sym$reason, "skew", ignore.case = TRUE)
  d_skew <- .summary_decide(rexp(2000))
  expect_equal(d_skew$kind, "median")
  expect_false(grepl("Shapiro", d_skew$reason))
})

test_that("fewer than 3 values defaults to median without error", {
  d <- .summary_decide(c(2, 5))
  expect_equal(d$kind, "median")
  expect_no_error(.summary_decide(c(2, 5)))
})

test_that("formatting: mean shows ± SD; median shows IQR with an en dash", {
  x <- c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
  expect_match(.fmt_continuous(x, "mean"), "±")
  expect_equal(.fmt_continuous(x, "median"), "5.5 (3.25–7.75)")  # en dash between quartiles
})

test_that("formatting uses 3 significant figures at both scale extremes", {
  expect_equal(.fmt_continuous(c(249000, 250000, 251000), "mean"), "250000 ± 1000")
  expect_false(grepl(".0 ", .fmt_continuous(c(249000, 250000, 251000), "mean"), fixed = TRUE))
  expect_match(.fmt_continuous(c(1.05, 1.13, 1.21), "mean"), "^1\\.13 ± ")
})

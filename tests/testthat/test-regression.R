mkdata <- function(n = 150) {
  set.seed(21)
  age <- round(rnorm(n, 60, 10)); sex <- sample(c("M","F"), n, TRUE)
  lp <- -4 + 0.05 * age + 0.4 * (sex == "M")
  event <- rbinom(n, 1, plogis(lp))
  time <- round(rexp(n, 0.05) + 1, 1)
  lapply(seq_len(n), function(i)
    list(age = age[i], sex = sex[i], event = event[i], time = time[i]))
}

test_that("logistic regression returns an HTML table with OR", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(outcome = "event", covariates = list("age", "sex")),
    options = list(model = "logistic"))
  out <- fig_regression(spec)
  expect_match(out$svg, "<table")
  expect_match(out$text, "OR|Odds", ignore.case = TRUE)
  expect_match(out$svg, "age")
})

test_that("cox regression returns an HTML table with HR", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(time = "time", status = "event", covariates = list("age", "sex")),
    options = list(model = "cox"))
  out <- fig_regression(spec)
  expect_match(out$svg, "<table")
  expect_match(out$text, "HR|Hazard", ignore.case = TRUE)
})

test_that("errors when no covariates selected", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(outcome = "event", covariates = list()),
    options = list(model = "logistic"))
  expect_error(fig_regression(spec), "covariate", ignore.case = TRUE)
})

test_that("errors when logistic outcome is not binary", {
  d <- mkdata(); d[[1]]$event <- 3
  spec <- list(figure = "regression", data = d,
    roles = list(outcome = "event", covariates = list("age")),
    options = list(model = "logistic"))
  expect_error(fig_regression(spec), "two", ignore.case = TRUE)
})

test_that("covariate names with spaces are backtick-escaped in the formula", {
  n <- 150
  set.seed(21)
  bp <- round(rnorm(n, 120, 15)); sex <- sample(c("M", "F"), n, TRUE)
  lp <- -4 + 0.02 * bp + 0.4 * (sex == "M")
  event <- rbinom(n, 1, plogis(lp))
  d <- lapply(seq_len(n), function(i)
    list("blood pressure" = bp[i], sex = sex[i], event = event[i]))
  spec <- list(figure = "regression", data = d,
    roles = list(outcome = "event", covariates = list("blood pressure", "sex")),
    options = list(model = "logistic"))
  out <- fig_regression(spec)
  expect_match(out$svg, "<table")
})

test_that("errors with a clear message when cox time/status roles are unset", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(covariates = list("age", "sex")),
    options = list(model = "cox"))
  expect_error(fig_regression(spec), "time", ignore.case = TRUE)
})

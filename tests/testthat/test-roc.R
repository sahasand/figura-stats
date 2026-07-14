mkspec <- function() {
  set.seed(11); n <- 120
  outcome <- rbinom(n, 1, 0.5)
  predictor <- outcome + rnorm(n, sd = 0.8)  # informative marker
  data <- lapply(seq_len(n), function(i) list(pred = predictor[i], out = outcome[i]))
  list(figure = "roc", data = data, roles = list(predictor = "pred", outcome = "out"))
}

test_that("roc returns an SVG and an AUC with CI and cutoff", {
  out <- fig_roc(mkspec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "AUC")
  expect_match(out$text, "95% CI")
  expect_match(out$text, "sensitivity", ignore.case = TRUE)
})

test_that("AUC is >= 0.5 and plausible for an informative marker", {
  out <- fig_roc(mkspec())
  auc <- as.numeric(sub(".*AUC ([0-9.]+).*", "\\1", out$text))
  expect_gt(auc, 0.6)
})

test_that("errors when outcome is not binary", {
  s <- mkspec(); s$data[[1]]$out <- 2
  expect_error(fig_roc(s), "two", ignore.case = TRUE)
})

test_that("errors clearly when predictor is non-numeric", {
  s <- mkspec(); s$data[[1]]$pred <- "not-a-number"
  expect_error(fig_roc(s), "numeric", ignore.case = TRUE)
})

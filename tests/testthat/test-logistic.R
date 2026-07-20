# Binary-outcome dataset with a real arm effect confounded by age. New treatment
# is channeled to older patients (higher risk), so its UNADJUSTED odds ratio looks
# weak and only adjusting for age reveals the protective effect (~exp(-0.9)=0.41).
mk_logit_rows <- function() {
  set.seed(52)
  n <- 240
  arm <- rep(c("Control", "Treated"), each = n / 2)
  age <- round(rnorm(n, 60, 10) + 6 * (arm == "Treated"), 1)
  lp <- -1 + 0.06 * (age - 60) - 0.9 * (arm == "Treated")
  y <- rbinom(n, 1, plogis(lp))
  outcome <- ifelse(y == 1, "Event", "NoEvent")
  lapply(seq_len(n), function(i)
    list(outcome = outcome[i], arm = arm[i], age = age[i]))
}
sc_logit <- function(rows, covariates = c("arm", "age"), ref_levels = NULL,
                     increments = NULL, event_value = "Event") {
  list(figure = "logistic", data = rows,
       roles = list(outcome = "outcome", covariates = as.list(covariates)),
       options = list(event_value = event_value,
                      ref_levels = ref_levels %||% list(),
                      increments = increments %||% list()))
}

test_that("fig_logistic returns svg table, text, and code", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_true(nzchar(out$text))
  expect_true(!is.null(out$code))
})

test_that("both unadjusted and adjusted ORs are reported", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$text, "adjusted", ignore.case = TRUE)
  expect_match(out$text, "[Uu]nadjusted")
})

test_that("adjusted arm OR recovers the simulated protective effect (< 1)", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  or <- as.numeric(sub(".*Treated[^0-9]*([0-9.]+).*", "\\1",
                       gsub("\n", " ", out$text)))
  expect_true(or < 0.85)
})

test_that("reference level appears and can be overridden", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$svg, "reference", ignore.case = TRUE)
  out2 <- fig_logistic(sc_logit(mk_logit_rows(), ref_levels = list(arm = "Treated")))
  expect_match(out2$svg, "Treated", fixed = TRUE)
})

test_that("no covariate selected errors readably", {
  expect_error(fig_logistic(sc_logit(mk_logit_rows(), covariates = character(0))),
               "covariate", ignore.case = TRUE)
})

test_that("too few events errors readably", {
  rows <- mk_logit_rows()[1:60]
  rows <- lapply(rows, function(r) { r$outcome <- "NoEvent"; r })
  rows[[1]]$outcome <- "Event"; rows[[2]]$outcome <- "Event"
  expect_error(fig_logistic(sc_logit(rows)), "event", ignore.case = TRUE)
})

test_that("constant covariate errors readably", {
  rows <- lapply(mk_logit_rows(), function(r) { r$arm <- "Only"; r })
  expect_error(fig_logistic(sc_logit(rows, covariates = c("arm"))),
               "one level", ignore.case = TRUE)
})

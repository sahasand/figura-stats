make_spec <- function() {
  set.seed(1)
  n <- 60
  grp <- rep(c("A", "B"), each = n / 2)
  time <- round(rexp(n, ifelse(grp == "A", 0.1, 0.2)), 1)
  status <- rbinom(n, 1, 0.7)
  rows <- lapply(seq_len(n), function(i)
    list(time = time[i], status = status[i], group = grp[i]))
  list(figure = "km", data = rows, options = list(time_label = "Months"))
}

test_that("fig_km returns an SVG, a log-rank p, and an HR for two groups", {
  out <- fig_km(make_spec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "log-rank")
  expect_match(out$text, "HR")
})

test_that("fig_km errors when status is not 0/1", {
  s <- make_spec(); s$data[[1]]$status <- 2
  expect_error(fig_km(s), "status", ignore.case = TRUE)
})

# Build a spec from parallel time/status/group vectors (mirrors the JSON shape).
km_spec <- function(time, status, group) {
  rows <- lapply(seq_along(time), function(i)
    list(time = time[i], status = status[i], group = group[i]))
  list(figure = "km", data = rows, options = list(time_label = "Months"))
}

# Two-group fixture with a very strong separation (group A dies fast; events
# concentrated in A). Log-rank p is ~1e-12 and the Cox HR (B vs A) is well
# below 1 and finite — used to pin p-formatting and HR direction.
strong_two_group_spec <- function() {
  set.seed(42)
  nA <- 25; nB <- 25
  tA <- round(rexp(nA, 0.5), 1);  sA <- rep(1L, nA)
  tB <- round(rexp(nB, 0.05), 1); sB <- rbinom(nB, 1, 0.4)
  km_spec(c(tA, tB), c(sA, sB), c(rep("A", nA), rep("B", nB)))
}

test_that("fig_km formats a tiny log-rank p as 'p < 0.001', never '0.000'", {
  out <- fig_km(strong_two_group_spec())
  expect_match(out$text, "p < 0.001", fixed = TRUE)
  expect_false(grepl("0.000", out$text, fixed = TRUE))
})

test_that("fig_km states the HR comparison as non-reference vs reference", {
  out <- fig_km(strong_two_group_spec())
  # Reference is the first factor level ("A"); numerator is "B".
  expect_match(out$text, "B vs A", fixed = TRUE)
  expect_false(grepl("A vs B", out$text, fixed = TRUE))
  # Events concentrated in A => hazard(B)/hazard(A) < 1, so "HR 0.xx".
  expect_match(out$text, "^HR 0")
})

test_that("fig_km withholds a non-convergent HR with a reason but keeps log-rank", {
  # Group Y has zero events -> complete separation -> coxph non-convergence.
  spec <- km_spec(
    time   = c(2, 4, 6, 8, 10, 3, 5, 7, 9, 11),
    status = c(1, 1, 1, 1, 1,  0, 0, 0, 0, 0),
    group  = c(rep("X", 5), rep("Y", 5)))
  # No warning must leak (repo enforces WARN 0 across the suite).
  out <- expect_no_warning(fig_km(spec))
  expect_match(out$text, "Hazard ratio not reported", fixed = TRUE)
  expect_match(out$text, "Log-rank", fixed = TRUE)
  expect_false(grepl("95% CI", out$text, fixed = TRUE))
})

test_that("fig_km errors on negative follow-up time", {
  s <- make_spec(); s$data[[1]]$time <- -1
  expect_error(fig_km(s), "non-negative")
})

test_that("fig_km errors on non-finite follow-up time", {
  s <- make_spec(); s$data[[1]]$time <- Inf
  expect_error(fig_km(s), "non-negative")
})

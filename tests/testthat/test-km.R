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

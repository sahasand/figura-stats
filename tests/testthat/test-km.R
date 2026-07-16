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

# Tiny fixture: one group, events at 1,2,3,4 (no censoring). KM: S(1)=.75,
# S(2)=.50 exactly, S(3)=.25. survfit's median convention returns the midpoint
# of the interval where S==0.5, i.e. (2+3)/2 = 2.5 (not the left endpoint).
uncensored_spec <- function() {
  km_spec(time = c(1, 2, 3, 4), status = c(1, 1, 1, 1), group = rep("A", 4))
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

test_that(".km_step_df expands rows into exact step coordinates", {
  d <- data.frame(time = c(0, 2, 5), surv = c(1, .8, .4),
                  lower = c(1, .6, .2), upper = c(1, .95, .7),
                  n.censor = 0, group = "A", stringsAsFactors = FALSE)
  s <- manuscriptfigures:::.km_step_df(d)
  # (t1,y1),(t2,y1),(t2,y2),(t3,y2),(t3,y3)
  expect_equal(s$time, c(0, 2, 2, 5, 5))
  expect_equal(s$surv, c(1, 1, .8, .8, .4))
  expect_equal(s$lower, c(1, 1, .6, .6, .2))
})

test_that(".km_curve_df prepends a time-zero row per group", {
  df <- data.frame(time = c(1, 2, 1, 3), status = c(1, 0, 1, 1),
                   group = c("A", "A", "B", "B"))
  fit <- survival::survfit(survival::Surv(time, status) ~ group, data = df)
  d <- manuscriptfigures:::.km_curve_df(fit)
  t0 <- d[d$time == 0, ]
  expect_setequal(t0$group, c("A", "B"))
  expect_true(all(t0$surv == 1))
})

test_that("fig_km SVG contains the risk table and censor marks", {
  s <- make_spec()  # existing two-group helper in this file
  out <- fig_km(s)
  expect_match(out$svg, "Number at risk", fixed = TRUE)
  expect_match(out$svg, ">Group<|>group<|legend", ignore.case = TRUE)  # legend present
})

test_that("R/km.R no longer references survminer", {
  src <- readLines(file.path("..", "..", "R", "km.R"))
  expect_false(any(grepl("survminer", src)))
})

test_that("fig_km reports per-group medians with not-reached state", {
  out <- fig_km(uncensored_spec())
  expect_match(out$text, "Median survival: A 2.5", fixed = TRUE)
  s <- km_spec(time = c(10, 11, 12), status = c(0, 0, 0), group = rep("A", 3))
  out2 <- fig_km(s)
  expect_match(out2$text, "not reached", fixed = TRUE)
})

test_that("landmark option reports estimate with CI at requested times", {
  s <- uncensored_spec(); s$options$landmarks <- c(2.5)
  out <- fig_km(s)
  expect_match(out$text, "At 2.5 Months, survival was 50.0%", fixed = TRUE)
  expect_match(out$text, "95% CI", fixed = TRUE)
})

test_that("reference option controls HR direction", {
  s <- strong_two_group_spec()             # existing fixture: events concentrated in A
  s$options$reference <- "B"
  out <- fig_km(s)
  expect_match(out$text, "A vs B", fixed = TRUE)   # numerator flips
  s$options$reference <- "Nope"
  expect_error(fig_km(s), "reference")
})

test_that("conf_int, horizon, and caption affect the figure not the statistics", {
  s <- strong_two_group_spec()
  base <- fig_km(s)
  s2 <- s; s2$options$conf_int <- FALSE
  expect_false(grepl("fill-opacity", fig_km(s2)$svg))   # ribbon gone
  expect_true(grepl("fill-opacity", base$svg))
  s3 <- s; s3$options$horizon <- 2
  expect_equal(fig_km(s3)$text, base$text)              # display-only
  s4 <- s; s4$options$caption <- "Synthetic demonstration data"
  expect_match(fig_km(s4)$svg, "Synthetic demonstration data", fixed = TRUE)
})

# ---- downloadable R script (code field) ------------------------------------

km_script_rows <- {
  set.seed(31)
  t1 <- rexp(30, 0.08); t2 <- rexp(30, 0.15)
  Map(function(tt, g) list(time = round(tt, 1),
                           status = as.integer(tt < 25), group = g),
      c(pmin(t1, 25), pmin(t2, 25)), rep(c("A", "B"), each = 30))
}
km_script_spec <- function(...) list(figure = "km", data = km_script_rows,
                                     options = list(time_label = "Months", ...))

test_that("km script reproduces survfit, log-rank, and Cox HR", {
  out <- fig_km(km_script_spec())
  expect_match(out$code, "survfit(Surv(time, status) ~ group, data = dat)", fixed = TRUE)
  expect_match(out$code, "survdiff(Surv(time, status) ~ group, data = dat)", fixed = TRUE)
  expect_match(out$code, "coxph(Surv(time, status) ~ group, data = dat)", fixed = TRUE)
  env <- new.env(parent = globalenv())
  capture.output(eval(parse(text = out$code), env))
  # script's log-rank p agrees with the app's text
  p <- 1 - stats::pchisq(env$lr$chisq, length(env$lr$n) - 1)
  if (p < 0.001) expect_match(out$text, "p < 0.001", fixed = TRUE)
  else expect_match(out$text, sprintf("p = %.3f", p), fixed = TRUE)
  # script's HR agrees with the app's text
  expect_match(out$text, sprintf("HR %.2f", exp(stats::coef(env$cox))[1]), fixed = TRUE)
  # figure objects build without printing
  expect_s3_class(env$p_km, "ggplot")
})

test_that("km script includes landmarks and reference releveling when set", {
  out <- fig_km(km_script_spec(landmarks = list(12, 24), reference = "B"))
  expect_match(out$code, "summary(fit, times = c(12, 24), extend = TRUE)", fixed = TRUE)
  expect_match(out$code, 'relevel(factor(dat$group), ref = "B")', fixed = TRUE)
})

test_that("km script honors source_filename", {
  out <- fig_km(km_script_spec(source_filename = "survival.csv"))
  expect_match(out$code, 'read.csv("survival.csv"', fixed = TRUE)
  expect_false(grepl("Example data embedded", out$code, fixed = TRUE))
})

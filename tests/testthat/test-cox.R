# Build a survival dataset with a real arm effect confounded by a covariate.
mk_cox_rows <- function() {
  set.seed(41)
  n <- 200
  arm <- rep(c("Control", "Treated"), each = n / 2)
  age <- round(rnorm(n, 60, 10), 1)
  # hazard rises with age and is lower for Treated
  lp <- 0.04 * (age - 60) - 0.7 * (arm == "Treated")
  time <- round(rexp(n, rate = 0.05 * exp(lp)) + 0.1, 2)
  cens <- time > 24
  time[cens] <- 24
  status <- ifelse(cens, "alive", "dead")
  lapply(seq_len(n), function(i)
    list(time = time[i], status = status[i], arm = arm[i], age = age[i]))
}
sc_cox <- function(rows, covariates = c("arm", "age"), ref_levels = NULL,
                   event_value = "dead") {
  list(figure = "cox", data = rows,
       roles = list(time = "time", status = "status", covariates = as.list(covariates)),
       options = list(event_value = event_value,
                      ref_levels = ref_levels %||% list()))
}

test_that("fig_cox returns svg table + forest plot, text, and code", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_true(nzchar(out$text))
  expect_true(nzchar(out$code))
})

test_that("both unadjusted and adjusted HRs are reported", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_match(out$text, "adjusted", ignore.case = TRUE)
  expect_match(out$text, "[Uu]nadjusted")
})

test_that("adjusted arm HR recovers the simulated protective effect (< 1)", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  # Treated adjusted HR ~ exp(-0.7) = 0.50; assert it lands well below 1
  hr <- as.numeric(sub(".*Treated[^0-9]*([0-9.]+).*", "\\1",
                        gsub("\n", " ", out$text)))
  expect_true(hr < 0.8)
})

test_that("reference level appears and can be overridden", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_match(out$svg, "reference", ignore.case = TRUE)
  out2 <- fig_cox(sc_cox(mk_cox_rows(), ref_levels = list(arm = "Treated")))
  expect_match(out2$svg, "Treated", fixed = TRUE)
})

test_that("no covariate selected errors readably", {
  expect_error(fig_cox(sc_cox(mk_cox_rows(), covariates = character(0))),
               "covariate", ignore.case = TRUE)
})

test_that("too few events errors readably", {
  # Span both arms (rows 1:100 are Control, 101:200 Treated) so the covariate
  # keeps two levels and the events check — not the constant-covariate check —
  # is what fires. Only two rows carry the event.
  rows <- c(mk_cox_rows()[1:20], mk_cox_rows()[101:120])
  rows <- lapply(rows, function(r) { r$status <- "alive"; r })
  rows[[1]]$status <- "dead"; rows[[21]]$status <- "dead"
  expect_error(fig_cox(sc_cox(rows)), "event", ignore.case = TRUE)
})

test_that("constant covariate errors readably", {
  rows <- mk_cox_rows()
  rows <- lapply(rows, function(r) { r$arm <- "Only"; r })
  expect_error(fig_cox(sc_cox(rows, covariates = c("arm"))),
               "one level", ignore.case = TRUE)
})

test_that("forest plot is a real (non-trivial) svg", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_gt(nchar(out$svg), 800)
})

test_that("cox code parses as R and mentions coxph + cox.zph", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_silent(parse(text = out$code))
  expect_match(out$code, "coxph", fixed = TRUE)
  expect_match(out$code, "cox.zph", fixed = TRUE)
})

test_that("demo-shape spec embeds data (no read.csv) in the script", {
  out <- fig_cox(sc_cox(mk_cox_rows()))   # no source_filename -> embedded
  expect_match(out$code, "data.frame", fixed = TRUE)
  expect_false(grepl("read.csv", out$code, fixed = TRUE))
})

# --- Issue 01: coefficient keys must respect the backticks the formula used ----

# Same data, but the arm column carries a non-syntactic header (a space), which
# is routine in clinical CSV exports.
mk_cox_rows_spaced <- function() {
  lapply(mk_cox_rows(), function(r)
    list(time = r$time, status = r$status, `study arm` = r$arm, age = r$age))
}

test_that("a covariate whose header has a space still gets estimated HRs", {
  out <- fig_cox(sc_cox(mk_cox_rows_spaced(), covariates = c("study arm", "age")))
  expect_false(grepl("not reliably estimated", out$text, fixed = TRUE))
  hr <- as.numeric(sub(".*Treated[^0-9]*([0-9.]+).*", "\\1",
                        gsub("\n", " ", out$text)))
  expect_true(hr < 0.8)
})

test_that("forest plot labels a space-headered covariate without backticks", {
  p <- .cox_prep(sc_cox(mk_cox_rows_spaced(), covariates = c("study arm", "age")))
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  svg <- .cox_forest_svg(p, fits)
  expect_match(svg, "study arm: Treated", fixed = TRUE)
  expect_false(grepl("`study arm`", svg, fixed = TRUE))
})

test_that("a covariate name that prefixes another does not claim its label", {
  base <- mk_cox_rows()
  set.seed(7)
  noise <- round(rnorm(length(base), 100, 15), 1)   # independent of age
  rows <- lapply(seq_along(base), function(i)
    list(time = base[[i]]$time, status = base[[i]]$status,
         age = base[[i]]$age, age2 = noise[i]))
  p <- .cox_prep(sc_cox(rows, covariates = c("age", "age2")))
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  svg <- .cox_forest_svg(p, fits)
  expect_match(svg, "age2 (per 1 unit)", fixed = TRUE)
})

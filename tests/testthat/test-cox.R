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

# The categorical fixture above only exercises the categorical key
# (`paste0(tl, l)`). confint()/coef() rownames are backticked for a NUMERIC
# non-syntactic term too, so the numeric branch (`uc[tl]`, not `uc[cl]`) needs
# its own fixture: a numeric covariate whose header carries a space.
mk_cox_rows_num_spaced <- function() {
  lapply(mk_cox_rows(), function(r)
    list(time = r$time, status = r$status, arm = r$arm, `age at entry` = r$age))
}

test_that("a NUMERIC covariate whose header has a space still gets estimated HRs", {
  out <- fig_cox(sc_cox(mk_cox_rows_num_spaced(),
                        covariates = c("arm", "age at entry")))
  expect_false(grepl("not reliably estimated", out$text, fixed = TRUE))
  # Pull the numeric row's unadjusted + adjusted cells out of the TSV block and
  # assert both are real numbers, not the "not reliably estimated" placeholder.
  line <- grep("^age at entry \\(per 1 unit\\)\t",
               strsplit(out$text, "\n", fixed = TRUE)[[1]], value = TRUE)
  expect_length(line, 1)
  cells <- strsplit(line, "\t", fixed = TRUE)[[1]][2:3]
  hrs <- as.numeric(sub("^([0-9.]+) .*$", "\\1", cells))
  expect_true(all(is.finite(hrs)))
  # Simulated log-hazard rises 0.04 per year -> HR ~ 1.04 per unit.
  expect_true(all(hrs > 1.01 & hrs < 1.09))
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

# --- Issue 05: the forest plot must honour the same reliability rule as the table

# A covariate level whose members are never observed to have the event and stay
# at risk past the last event time separates the likelihood: coxph converges
# with an effectively infinite coefficient and warns. The warning is captured by
# .cox_fit_one, so .cox_hr_cell renders EVERY adjusted cell — including the
# well-behaved arm term's — as "not reliably estimated".
mk_cox_rows_separated <- function() {
  rows <- mk_cox_rows()
  for (i in seq_along(rows)) rows[[i]]$grp <- "Common"
  for (i in 1:10) {
    rows[[i]]$grp <- "Rare"; rows[[i]]$time <- 30; rows[[i]]$status <- "alive"
  }
  rows
}

test_that("a warned joint fit reports no adjusted HR and plots no forest term", {
  sc <- sc_cox(mk_cox_rows_separated(), covariates = c("arm", "grp"))
  p <- .cox_prep(sc)
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  expect_false(is.null(fits$joint$warn))          # the fixture really does warn

  out <- fig_cox(sc)
  adj <- function(term) {
    line <- grep(paste0("^", term, "\t"), strsplit(out$text, "\n", fixed = TRUE)[[1]],
                 value = TRUE)
    expect_length(line, 1)
    strsplit(line, "\t", fixed = TRUE)[[1]][3]
  }
  # The table declines to report BOTH adjusted cells (the warning is model-level).
  expect_equal(adj("Treated"), "not reliably estimated")
  expect_equal(adj("Rare"), "not reliably estimated")

  # So the forest, which plots adjusted HRs from that same fit, must plot nothing.
  svg <- .cox_forest_svg(p, fits)
  expect_false(grepl("arm: Treated", svg, fixed = TRUE))
  expect_false(grepl("grp: Rare", svg, fixed = TRUE))
  expect_identical(svg, "")
})

# A numeric covariate on a tiny scale (a "wrong units" column) fits cleanly — no
# warning, finite CI — but its adjusted HR runs to ~1e6 with an upper bound of
# ~1e7. On the shared log10 axis that squashes every other term to a hairline.
mk_cox_rows_huge <- function() {
  set.seed(41)
  n <- 200
  arm <- rep(c("Control", "Treated"), each = n / 2)
  x <- round(rnorm(n, 0, 0.05), 4)
  lp <- 15 * x - 0.7 * (arm == "Treated")
  time <- round(rexp(n, rate = 0.05 * exp(lp)) + 0.1, 2)
  cens <- time > 24
  time[cens] <- 24
  status <- ifelse(cens, "alive", "dead")
  lapply(seq_len(n), function(i)
    list(time = time[i], status = status[i], arm = arm[i], x = x[i]))
}

test_that("a term whose CI blows past 1e6 is left off the forest, others stay", {
  sc <- sc_cox(mk_cox_rows_huge(), covariates = c("arm", "x"))
  p <- .cox_prep(sc)
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  expect_null(fits$joint$warn)                    # nothing warned; only the scale is wild
  expect_gt(exp(suppressWarnings(stats::confint(fits$joint$fit))["x", 2]), 1e6)

  svg <- .cox_forest_svg(p, fits)
  expect_false(grepl("x (per 1 unit)", svg, fixed = TRUE))
  expect_match(svg, "arm: Treated", fixed = TRUE)
})

# --- Issue 04: the script must relevel against the reference actually fitted --

test_that("script relevels against the fitted reference, not the requested one", {
  rows <- mk_cox_rows()
  # Ten Treated rows become a third arm level whose age is missing, so
  # complete-case filtering drops every row carrying that level.
  for (i in 101:110) { rows[[i]]$arm <- "Excluded"; rows[[i]]$age <- "" }
  out <- fig_cox(sc_cox(rows, ref_levels = list(arm = "Excluded")))
  # Control (100 rows) outnumbers Treated (90), so prep falls back to Control.
  expect_match(out$svg, "arm (reference: Control)", fixed = TRUE)
  expect_false(grepl('ref = "Excluded"', out$code, fixed = TRUE))
  expect_match(out$code, 'ref = "Control"', fixed = TRUE)
})

# See the note on the matching test in test-logistic.R: the forest SVG is
# width-fitted by the browser, so a short canvas magnifies the theme's fixed
# 12pt type. Keep cox in the same proportion band as its sibling and as the
# other figures in the app.
.cox_forest_aspect <- function(svg) {
  w <- as.numeric(sub(".*\\bwidth='([0-9.]+)pt'.*", "\\1", substr(svg, 1, 400)))
  h <- as.numeric(sub(".*\\bheight='([0-9.]+)pt'.*", "\\1", substr(svg, 1, 400)))
  h / w
}

test_that("the adjusted-HR forest keeps a sane aspect ratio at every term count", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  forest <- sub("^.*</table></div>", "", out$svg)
  expect_gte(.cox_forest_aspect(forest), 0.5)

  out1 <- fig_cox(sc_cox(mk_cox_rows(), covariates = "arm"))
  forest1 <- sub("^.*</table></div>", "", out1$svg)
  expect_gte(.cox_forest_aspect(forest1), 0.5)
})

# --- Issues 08 + 09: one reliability rule, applied to the table AND the plot --
# Before this, cox bounded only the forest plot and only from above: a
# huge-but-finite HR printed a number in Table 3 while being silently absent
# from the figure (09), and an extreme *protective* term passed both bounds and
# flattened the shared log axis (08). The rule is now symmetric — [1e-6, 1e6] —
# and shared by the cell formatter and the plot filter, so the two agree.

test_that("a huge-but-finite HR is unreportable in the table, not just the plot", {
  sc <- sc_cox(mk_cox_rows_huge(), covariates = c("arm", "x"))
  p <- .cox_prep(sc)
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  expect_null(fits$joint$warn)                    # nothing warned; only the scale is wild

  out <- fig_cox(sc)
  # The row exists and is labelled, but its adjusted cell refuses to state a number.
  expect_match(out$svg, "x (per 1 unit)", fixed = TRUE)
  expect_match(out$svg, "not reliably estimated", fixed = TRUE)
  # The healthy covariate is unaffected — this must not become a blanket refusal.
  expect_match(out$text, "arm", fixed = TRUE)
  expect_false(grepl("1e+06", out$svg, fixed = TRUE))
})

# Same shape as mk_cox_rows_huge(), with the sign flipped: an extremely
# PROTECTIVE term. Its CI is finite and sits far below 1e6, so the old
# upper-only bound kept it and let it span ~11 decades of the shared axis.
mk_cox_rows_protective <- function() {
  set.seed(41)
  n <- 200
  arm <- rep(c("Control", "Treated"), each = n / 2)
  x <- round(rnorm(n, 0, 0.05), 4)
  lp <- -15 * x - 0.7 * (arm == "Treated")
  time <- round(rexp(n, rate = 0.05 * exp(lp)) + 0.1, 2)
  cens <- time > 24
  time[cens] <- 24
  status <- ifelse(cens, "alive", "dead")
  lapply(seq_len(n), function(i)
    list(time = time[i], status = status[i], arm = arm[i], x = x[i]))
}

test_that("an extremely protective term is dropped from the forest, others stay", {
  sc <- sc_cox(mk_cox_rows_protective(), covariates = c("arm", "x"))
  p <- .cox_prep(sc)
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  expect_null(fits$joint$warn)                    # finite, unwarned — only the scale is wild
  expect_lt(exp(suppressWarnings(stats::confint(fits$joint$fit))["x", 1]), 1e-6)

  svg <- .cox_forest_svg(p, fits)
  expect_false(grepl("x (per 1 unit)", svg, fixed = TRUE))
  expect_match(svg, "arm: Treated", fixed = TRUE)  # the healthy term keeps a readable axis
})

test_that("the reliability rule is symmetric on the ratio scale", {
  expect_true(.ratio_reportable(1.5, 0.9, 2.2))
  expect_false(.ratio_reportable(Inf, 0.9, 2.2))
  expect_false(.ratio_reportable(1.5, 0.9, 2e6))    # runaway upper limit
  expect_false(.ratio_reportable(1.5, 1e-7, 2.2))   # runaway lower limit
  expect_equal(.ratio_reportable(c(1.5, 1.5), c(0.9, 1e-7), c(2.2, 2.2)),
               c(TRUE, FALSE))                      # vectorised for the plot filters
})

test_that("an unreliable HR cell is explained in the methods text", {
  # With the symmetric rule, a cox cell can refuse to print a number from a fit
  # that raised NO warning at all — so unlike the warned case, nothing else in
  # the text accounts for it. Logistic has said this since it shipped; cox said
  # nothing, leaving "not reliably estimated" in the table unexplained.
  out <- fig_cox(sc_cox(mk_cox_rows_huge(), covariates = c("arm", "x")))
  expect_match(out$svg, "not reliably estimated", fixed = TRUE)
  expect_match(out$text, "separation or severe collinearity", fixed = TRUE)
})

test_that("a healthy model says nothing about separation or collinearity", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  expect_false(grepl("not reliably estimated", out$svg, fixed = TRUE))
  expect_false(grepl("separation or severe collinearity", out$text, fixed = TRUE))
})

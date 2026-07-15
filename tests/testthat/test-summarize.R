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

mk_summary_spec <- function(group = "arm") {
  set.seed(7)
  age <- round(rnorm(80, 60, 10))
  los <- round(rexp(80, 1 / 5) + 1, 1); los[c(2, 5)] <- NA
  sex <- sample(c("Female", "Male"), 80, replace = TRUE)
  arm <- rep(c("A", "B"), 40)
  rows <- lapply(seq_len(80), function(i)
    list(age = age[i], length_of_stay = los[i], sex = sex[i], arm = arm[i]))
  list(figure = "summary", data = rows,
       roles = list(group = group),
       options = list(continuous = c("age", "length_of_stay"),
                      categorical = c("sex"),
                      labels = list(length_of_stay = "Length of stay"),
                      overrides = NULL, show_plots = FALSE))
}

test_that("table has one column per group plus a Missing column", {
  out <- fig_summary(mk_summary_spec())
  expect_true(grepl("<table", out$svg, fixed = TRUE))
  expect_match(out$svg, ">A \\(N=40\\)<")
  expect_match(out$svg, ">B \\(N=40\\)<")
  expect_match(out$svg, "Missing")
})

test_that("group columns keep first-appearance order, not alphabetical", {
  spec <- mk_summary_spec()
  # Flip so B appears first in the data.
  spec$data <- rev(spec$data)
  out <- fig_summary(spec)
  expect_lt(regexpr(">B (N=", out$svg, fixed = TRUE),
            regexpr(">A (N=", out$svg, fixed = TRUE))
})

test_that("continuous rows show the chosen summary and its reason", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$svg, "±")              # age -> mean ± SD
  expect_match(out$svg, "Length of stay")      # display label used
  expect_match(out$svg, "median \\(IQR\\)")    # LOS -> median (IQR)
  expect_match(out$svg, "skew|normal", ignore.case = TRUE)        # reason present
})

test_that("a variable normal within groups but shifted between them still gets mean", {
  set.seed(8)
  v <- c(rnorm(60, 55, 5), rnorm(60, 75, 5))   # pooled = bimodal mixture
  arm <- rep(c("A", "B"), each = 60)
  rows <- lapply(seq_len(120), function(i) list(v = v[i], arm = arm[i]))
  spec <- list(figure = "summary", data = rows, roles = list(group = "arm"),
               options = list(continuous = list("v"), categorical = list(),
                              show_plots = FALSE))
  out <- fig_summary(spec)
  expect_match(out$svg, "v, mean ± SD", fixed = TRUE)
  expect_match(out$svg, "within groups")       # reason names the centering
})

test_that("length_of_stay reports its 2 missing values", {
  expect_match(fig_summary(mk_summary_spec())$svg, ">2<")
})

test_that("categorical rows show n (%) with levels and an honest denominator", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$svg, "Female")
  expect_match(out$svg, "%")
  expect_match(out$svg, "of 80 with data")     # denominator stated on the variable row
})

test_that("blank group cells become an explicit (missing) column", {
  spec <- mk_summary_spec()
  spec$data[[1]]$arm <- ""
  spec$data[[2]]$arm <- NULL
  out <- fig_summary(spec)
  expect_match(out$svg, "(missing)", fixed = TRUE)
})

test_that("a group where a variable has zero non-missing values renders an em-dash cell", {
  spec <- mk_summary_spec()
  for (i in seq_along(spec$data))
    if (identical(spec$data[[i]]$arm, "B")) spec$data[[i]]$length_of_stay <- NA
  out <- fig_summary(spec)
  expect_match(out$svg, ">—<")
})

# Diagnostic Shapiro–Wilk p inside a .why reason is sanctioned; a p-value COLUMN is the forbidden thing.
test_that("no group -> a single Overall column and no p-value anywhere", {
  spec <- mk_summary_spec(group = NULL)
  out <- fig_summary(spec)
  expect_match(out$svg, "Overall")
  expect_false(grepl("p-value", out$svg, ignore.case = TRUE))
  expect_false(grepl("<th>\\s*p\\s*</th>", out$svg, ignore.case = TRUE))
})

test_that("override forces the summary and records that the user chose it", {
  spec <- mk_summary_spec()
  spec$options$overrides <- list(age = "median")
  out <- fig_summary(spec)
  expect_match(out$svg, "you selected", ignore.case = TRUE)
})

test_that("an override value outside mean/median errors clearly", {
  spec <- mk_summary_spec()
  spec$options$overrides <- list(age = "bogus")
  expect_error(fig_summary(spec), "override", ignore.case = TRUE)
})

test_that("zero selected variables errors clearly instead of an empty table", {
  spec <- mk_summary_spec()
  spec$options$continuous <- list(); spec$options$categorical <- list()
  expect_error(fig_summary(spec), "at least one variable", ignore.case = TRUE)
})

test_that("text is TSV with a header row plus a methods sentence", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$text, "^Characteristic\t")   # header line first
  expect_match(out$text, "mean ± SD", fixed = TRUE)
  expect_match(out$text, "median")
  expect_match(out$text, "\t")
})

test_that("grouped run: methods sentence claims within-group normality assessment", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$text, "assessed within groups")
})

test_that("no-group run: methods sentence drops the within-groups claim but keeps Shapiro-Wilk", {
  out <- fig_summary(mk_summary_spec(group = NULL))
  expect_false(grepl("within groups", out$text, fixed = TRUE))
  expect_match(out$text, "Shapiro–Wilk")
})

test_that("a non-numeric value in a continuous column errors clearly, no warning", {
  spec <- mk_summary_spec()
  spec$data[[1]]$age <- "not-a-number"
  expect_no_warning(expect_error(fig_summary(spec), "numeric", ignore.case = TRUE))
})

test_that("a group with a single non-missing continuous value shows the bare value, never NA", {
  # One group has exactly one non-missing value for a continuous variable;
  # sd(n=1) is NA, so the cell must be the bare formatted value, not "x ± NA".
  rows <- c(
    list(list(v = 42, arm = "A")),
    lapply(2:40, function(i) list(v = NA, arm = "A")),
    lapply(1:40, function(i) list(v = round(rnorm(1, 60, 10), 1), arm = "B")))
  spec <- list(figure = "summary", data = rows, roles = list(group = "arm"),
               options = list(continuous = list("v"), categorical = list(),
                              overrides = list(v = "mean"), show_plots = FALSE))
  out <- fig_summary(spec)
  expect_match(out$svg, ">42<")
  expect_false(grepl("NA", out$svg, fixed = TRUE))
})

test_that("show_plots bundles a table AND an inline svg with the teaching legend", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- TRUE
  out <- fig_summary(spec)
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$svg, "plot-legend", fixed = TRUE)
  expect_match(out$svg, "dashed = mean", fixed = TRUE)
  expect_match(out$svg, "lines separate", fixed = TRUE)
})

test_that("caption is rendered when provided", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- TRUE
  spec$options$caption <- "Synthetic demonstration data — not for clinical use."
  expect_match(fig_summary(spec)$svg, "Synthetic demonstration data", fixed = TRUE)
})

test_that("all-missing continuous values render the table with no figure", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- TRUE
  spec$options$continuous <- list("length_of_stay")
  for (i in seq_along(spec$data)) spec$data[[i]]$length_of_stay <- NA
  out <- fig_summary(spec)
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_false(grepl("<figure", out$svg, fixed = TRUE))
})

test_that("plotting continuous data emits no ggplot warning", {
  spec <- mk_summary_spec(); spec$options$show_plots <- TRUE
  expect_no_warning(fig_summary(spec))
})

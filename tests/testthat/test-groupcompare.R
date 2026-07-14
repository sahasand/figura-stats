mkspec <- function(test = "parametric", plot = "box", ngroup = 2) {
  set.seed(7)
  grp <- rep(LETTERS[1:ngroup], each = 20)
  val <- rnorm(length(grp), mean = as.integer(factor(grp)))
  data <- lapply(seq_along(grp), function(i) list(value = val[i], grp = grp[i]))
  list(figure = "groupcompare", data = data,
       roles = list(value = "value", group = "grp"),
       options = list(plot = plot, test = test))
}

test_that("two-group parametric returns an SVG and a t-test p-value", {
  out <- fig_groupcompare(mkspec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "t-test|Welch", ignore.case = TRUE)
  expect_match(out$text, "p ?=|p ?<")
})

test_that("two-group nonparametric uses Mann-Whitney", {
  out <- fig_groupcompare(mkspec(test = "nonparametric"))
  expect_match(out$text, "Mann-Whitney|Wilcoxon", ignore.case = TRUE)
})

test_that("three groups use ANOVA / Kruskal-Wallis", {
  expect_match(fig_groupcompare(mkspec(ngroup = 3))$text, "ANOVA", ignore.case = TRUE)
  expect_match(fig_groupcompare(mkspec(ngroup = 3, test = "nonparametric"))$text,
               "Kruskal", ignore.case = TRUE)
})

test_that("errors when fewer than two groups", {
  expect_error(fig_groupcompare(mkspec(ngroup = 1)), "two groups", ignore.case = TRUE)
})

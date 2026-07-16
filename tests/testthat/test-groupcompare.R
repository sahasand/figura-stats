mkrows <- function(v, g) Map(function(vi, gi) list(val = vi, grp = gi), v, g)

two_norm <- {
  set.seed(11)
  v <- c(rnorm(30, 10, 2), rnorm(30, 13, 2)); g <- rep(c("A", "B"), each = 30)
  mkrows(v, g)
}
three_norm <- {
  set.seed(12)
  v <- c(rnorm(25, 10, 2), rnorm(25, 12, 2), rnorm(25, 15, 2))
  g <- rep(c("A", "B", "C"), each = 25); mkrows(v, g)
}
sc <- function(rows, test = "auto", plot = "box")
  list(figure = "groupcompare", data = rows,
       roles = list(group = "grp", outcome = "val"),
       options = list(test = test, plot = plot))

test_that("two-group normal auto-selects Welch t-test with d, CI, p, and SVG", {
  out <- fig_groupcompare(sc(two_norm))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "t-test", ignore.case = TRUE)
  expect_match(out$text, "Cohen's d", fixed = TRUE)
  expect_match(out$text, "95% CI", fixed = TRUE)
  expect_match(out$text, "p [=<]")
})

test_that("override forces Mann-Whitney with rank-biserial", {
  out <- fig_groupcompare(sc(two_norm, test = "nonparametric"))
  expect_match(out$text, "Mann–Whitney|Mann-Whitney", ignore.case = TRUE)
  expect_match(out$text, "rank-biserial", fixed = TRUE)
})

test_that("three-group parametric uses ANOVA with eta-squared", {
  out <- fig_groupcompare(sc(three_norm, test = "parametric"))
  expect_match(out$text, "ANOVA", ignore.case = TRUE)
  expect_match(out$text, "eta-squared|η²", ignore.case = TRUE)
})

test_that("three-group nonparametric uses Kruskal-Wallis with epsilon-squared", {
  out <- fig_groupcompare(sc(three_norm, test = "nonparametric"))
  expect_match(out$text, "Kruskal", ignore.case = TRUE)
  expect_match(out$text, "epsilon-squared|ε²", ignore.case = TRUE)
})

test_that("Cohen's d value is correct within tolerance", {
  # groups differ by ~3 SD-units of 2 -> d ~ 1.5; check the printed number band
  out <- fig_groupcompare(sc(two_norm, test = "parametric"))
  d <- as.numeric(sub(".*Cohen's d = (-?[0-9.]+).*", "\\1", out$text))
  expect_true(d < -1.0 || d > 1.0)   # sign depends on factor order; magnitude large
})

test_that("violin option renders", {
  out <- fig_groupcompare(sc(two_norm, plot = "violin"))
  expect_match(out$svg, "<svg", fixed = TRUE)
})

test_that("readable errors: <2 groups, non-numeric-in-numeric-role handled by routing", {
  one <- mkrows(rnorm(20, 5), rep("A", 20))
  expect_error(fig_groupcompare(sc(one)), "two groups", ignore.case = TRUE)
})

test_that("a group with <2 values is dropped, remaining comparison runs", {
  v <- c(rnorm(30, 10), rnorm(30, 12), 99); g <- c(rep("A", 30), rep("B", 30), "C")
  out <- fig_groupcompare(sc(mkrows(v, g)))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "dropped|excluded", ignore.case = TRUE)
})

test_that("dispatch routes groupcompare", {
  json <- jsonlite::toJSON(sc(two_norm), auto_unbox = TRUE)
  res <- jsonlite::fromJSON(render_figure(json))
  expect_true(res$ok)
  expect_match(res$svg, "<svg", fixed = TRUE)
})

mkrows2 <- function(out, g) Map(function(o, gi) list(out = o, grp = gi), out, g)
sc2 <- function(rows) list(figure = "groupcompare", data = rows,
  roles = list(group = "grp", outcome = "out"), options = list())

test_that("categorical 2x2 outcome uses chi-square with Cramer's V and odds ratio", {
  set.seed(21)
  g <- rep(c("A", "B"), each = 60)
  out <- c(sample(c("Yes","No"), 60, TRUE, c(0.3,0.7)),
           sample(c("Yes","No"), 60, TRUE, c(0.6,0.4)))
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  expect_match(res$svg, "<svg", fixed = TRUE)
  expect_match(res$text, "chi-square|χ²|Fisher", ignore.case = TRUE)
  expect_match(res$text, "Cramér's V|Cramer's V", ignore.case = TRUE)
  expect_match(res$text, "odds ratio", ignore.case = TRUE)
})

test_that("small expected counts fall back to Fisher", {
  g <- rep(c("A", "B"), each = 6)
  out <- c("Yes", rep("No", 5), rep("Yes", 5), "No")   # tiny cells
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  expect_match(res$text, "Fisher", ignore.case = TRUE)
})

test_that("3+ categorical outcome reports Cramer's V without odds ratio", {
  set.seed(22)
  g <- rep(c("A", "B", "C"), each = 40)
  out <- sample(c("Mild","Moderate","Severe"), 120, TRUE)
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  expect_match(res$text, "Cramér's V|Cramer's V", ignore.case = TRUE)
  expect_no_match(res$text, "odds ratio")
})

test_that("3-group significant ANOVA appends Tukey post-hoc", {
  set.seed(23)
  v <- c(rnorm(30, 10, 1.5), rnorm(30, 14, 1.5), rnorm(30, 18, 1.5))
  g <- rep(c("A", "B", "C"), each = 30)
  out <- fig_groupcompare(list(figure = "groupcompare",
    data = mkrows(v, g), roles = list(group = "grp", outcome = "val"),
    options = list(test = "parametric")))
  expect_match(out$text, "Tukey", ignore.case = TRUE)
})

test_that("3-group significant Kruskal appends Dunn post-hoc", {
  set.seed(24)
  v <- c(rexp(30, 1), rexp(30, 0.4) + 3, rexp(30, 0.2) + 8)
  g <- rep(c("A", "B", "C"), each = 30)
  out <- fig_groupcompare(list(figure = "groupcompare",
    data = mkrows(v, g), roles = list(group = "grp", outcome = "val"),
    options = list(test = "nonparametric")))
  expect_match(out$text, "Dunn", ignore.case = TRUE)
  expect_match(out$text, "BH|Benjamini", ignore.case = TRUE)
})

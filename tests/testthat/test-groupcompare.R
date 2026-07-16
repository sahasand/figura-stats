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
mkrows2 <- function(out, g) Map(function(o, gi) list(out = o, grp = gi), out, g)
sc2 <- function(rows) list(figure = "groupcompare", data = rows,
  roles = list(group = "grp", outcome = "out"), options = list())

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

# --- Fix 1: pin effect-size VALUES against hand-computed constants ---
# Hand-derivation (same seeds/data as the fixtures above), verified via scratch R:
#   set.seed(11); v<-c(rnorm(30,10,2),rnorm(30,13,2)); g<-rep(c("A","B"),each=30)
#   x1<-v[g=="A"]; x2<-v[g=="B"]; n1<-n2<-30
#   sp<-sqrt(((n1-1)*var(x1)+(n2-1)*var(x2))/(n1+n2-2)); d<-(mean(x2)-mean(x1))/sp -> 2.144568
#   W<-wilcox.test(v~g)$statistic (= 68); r<-1-2*W/(n1*n2) -> 0.848889
test_that("Cohen's d matches hand-computed pooled-SD value", {
  out <- fig_groupcompare(sc(two_norm, test = "parametric"))
  d <- as.numeric(sub(".*Cohen's d = (-?[0-9.]+).*", "\\1", out$text))
  expect_equal(d, 2.144568, tolerance = 0.02)   # pooled-SD Cohen's d, (B - A)
  expect_match(out$text, "(B vs A)", fixed = TRUE)  # direction label
})

test_that("rank-biserial r matches hand-computed 1 - 2W/(n1 n2)", {
  out <- fig_groupcompare(sc(two_norm, test = "nonparametric"))
  r <- as.numeric(sub(".*rank-biserial r = (-?[0-9.]+).*", "\\1", out$text))
  expect_equal(r, 0.848889, tolerance = 0.02)   # W = 68, n1 = n2 = 30
  expect_match(out$text, "(B vs A)", fixed = TRUE)
})

# Hand-derivation (three_norm, seed 12):
#   fit<-aov(v~g); ss<-summary(fit)[[1]][,"Sum Sq"]; eta<-ss[1]/sum(ss) -> 0.6569501
#   H<-kruskal.test(v~factor(g))$statistic (= 48.8116); eps<-H/(n-1), n=75 -> 0.6596165
test_that("eta-squared matches SS_between/SS_total", {
  out <- fig_groupcompare(sc(three_norm, test = "parametric"))
  eta <- as.numeric(sub(".*eta-squared = (-?[0-9.]+).*", "\\1", out$text))
  expect_equal(eta, 0.6569501, tolerance = 0.02)
})

test_that("epsilon-squared matches H/(n-1)", {
  out <- fig_groupcompare(sc(three_norm, test = "nonparametric"))
  eps <- as.numeric(sub(".*epsilon-squared = (-?[0-9]+\\.?[0-9]*).*", "\\1", out$text))
  expect_equal(eps, 0.6596165, tolerance = 0.02)   # H = 48.8116, n = 75
})

# Hand-derivation (2x2, seed 21): tab = No/Yes x A/B = [[39,30],[21,30]], n = 120
#   chisq (uncorrected) V = sqrt(chi^2/(n*(min(dim)-1))) -> 0.1517165
#   OR = ad/bc = (39*30)/(30*21) -> 1.857143  (event = No, A vs B)
test_that("Cramér's V and odds ratio match hand-computed 2x2 values", {
  set.seed(21)
  g <- rep(c("A", "B"), each = 60)
  out <- c(sample(c("Yes","No"), 60, TRUE, c(0.3,0.7)),
           sample(c("Yes","No"), 60, TRUE, c(0.6,0.4)))
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  V <- as.numeric(sub(".*Cramér's V = ([0-9.]+).*", "\\1", res$text))
  expect_equal(V, 0.1517165, tolerance = 0.02)
  or <- as.numeric(sub(".*odds ratio for.*= ([0-9.]+) \\(95%.*", "\\1", res$text))
  expect_equal(or, 1.857143, tolerance = 0.02)
  # direction: OR must name the event level and reference group
  expect_match(res$text, "odds ratio for out=No, A vs B", fixed = TRUE)
})

test_that("zero-cell 2x2 gets Haldane-Anscombe correction with finite OR + note", {
  g <- rep(c("A", "B"), each = 10)
  out <- c(rep("No", 10), rep("No", 5), rep("Yes", 5))  # Yes,A cell is 0
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  or <- as.numeric(sub(".*odds ratio for.*= ([0-9.]+) \\(95%.*", "\\1", res$text))
  expect_true(is.finite(or))
  expect_match(res$text, "continuity correction applied", fixed = TRUE)
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

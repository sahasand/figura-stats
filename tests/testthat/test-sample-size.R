ss_spec <- function(method = "two_mean", solve = "n", ...) list(method = method, solve = solve, params = list(...))

test_that("reference t-test designs match stats including both rejection tails", {
  for (type in c("two.sample", "one.sample", "paired")) {
    method <- c(two.sample="two_mean", one.sample="one_mean", paired="paired_mean")[[type]]
    out <- sample_size_plan(ss_spec(method, "power", n=30, delta=.4, sd=1), FALSE)
    ref <- stats::power.t.test(n=30, delta=.4, sd=1, type=type, strict=TRUE)$power
    expect_equal(out$metric, ref, tolerance=1e-10)
  }
  # Familiar independent-groups example: d=.5, two-sided .05, power .8.
  out <- sample_size_plan(ss_spec(delta=.5, sd=1), FALSE)
  expect_equal(out$counts$per_group, c(64,64))
  expect_equal(out$metric, .8014595579, tolerance=1e-9)
})

test_that("all designs round to the smallest passing integer and recompute power", {
  for (m in .ss_methods()) {
    spec <- ss_spec(m)
    if (m %in% c("ni_mean", "equivalence_mean")) spec$params$delta <- 0
    out <- sample_size_plan(spec, FALSE)
    p <- out$params
    n <- out$counts$n
    metric <- out$metric
    if (startsWith(m,"precision_")) {
      expect_lte(metric, p$width)
      if (n>.ss_min_n(p)) expect_gt(.ss_metric(p,n-1),p$width)
    } else {
      expect_gte(metric, p$target)
      if (n>.ss_min_n(p)) expect_lt(.ss_metric(p,n-1),p$target)
    }
    expect_true(is.finite(metric))
  }
})

test_that("unequal allocation and attrition are separate from analyzable power", {
  a <- sample_size_plan(ss_spec(ratio=2,dropout=0), FALSE)
  b <- sample_size_plan(ss_spec(ratio=2,dropout=.2), FALSE)
  expect_equal(a$metric,b$metric)
  expect_equal(b$counts$n2,2*b$counts$n)
  expect_equal(b$counts$recruit_per_group,ceiling(b$counts$per_group/.8))
  expect_equal(b$counts$recruit,sum(b$counts$recruit_per_group))
  expect_silent(sample_size_plan(ss_spec(ratio=.1),FALSE))
})

test_that("null-effect and increasingly informative designs behave correctly", {
  for (m in c("two_mean","paired_mean","one_mean")) {
    out <- sample_size_plan(ss_spec(m,"power",n=40,delta=0),FALSE)
    expect_equal(out$metric,.05,tolerance=1e-10)
    expect_error(sample_size_plan(ss_spec(m,delta=0),FALSE),"exceeds")
  }
  a <- sample_size_plan(ss_spec(delta=.4),FALSE)
  b <- sample_size_plan(ss_spec(delta=.6),FALSE)
  expect_gt(a$counts$n,b$counts$n)
})

test_that("detectable-effect solutions return target power across supported designs", {
  for (m in .ss_methods()) {
    p <- .ss_prepare(ss_spec(m))
    if (is.null(.ss_effect_info(p))) next
    out <- sample_size_plan(ss_spec(m,"effect",n=200),FALSE)
    expect_equal(out$metric,.8,tolerance=1e-6)
    expect_true(is.finite(out$effect$value))
  }
  out <- sample_size_plan(ss_spec("two_proportion","effect",n=200,p1=.5,p2=.3),FALSE)
  expect_lt(out$effect$value,.5)
  expect_error(sample_size_plan(ss_spec("two_proportion","effect",n=2,p1=.99,p2=.995),FALSE),"cannot be reached")
})

test_that("margin power respects NI and joint TOST boundaries", {
  # At the NI null boundary a one-sided normal test rejects with alpha.
  out <- sample_size_plan(ss_spec("ni_mean","power",delta=-.3,margin=.3),FALSE)
  expect_equal(out$metric,.05,tolerance=1e-12)
  expect_error(sample_size_plan(ss_spec("ni_mean",delta=-.3),FALSE),"boundary")
  expect_error(sample_size_plan(ss_spec("equivalence_mean",delta=.3),FALSE),"strictly inside")
  # Symmetric equivalence under true equality: n=2*(z_alpha+z_(1+power)/2)^2*sd²/margin².
  ref <- ceiling(2*(qnorm(.95)+qnorm(.9))^2/.3^2)
  eq <- sample_size_plan(ss_spec("equivalence_mean",delta=0,margin=.3),FALSE)
  expect_equal(eq$counts$n,ref)
})

test_that("survival distinguishes events and participants", {
  out <- sample_size_plan(ss_spec("survival",hr=.7,event_fraction=.6),FALSE)
  required_events <- 4*(qnorm(.975)+qnorm(.8))^2/log(.7)^2
  # Full two-tail power is used, so the conventional leading-tail formula is a close reference.
  expect_equal(out$counts$analyzable,412)
  expect_lt(abs(out$counts$events-required_events),2)
  b <- sample_size_plan(ss_spec("survival",hr=.7,event_fraction=.3),FALSE)
  expect_gt(b$counts$analyzable,out$counts$analyzable)
})

test_that("cluster degrees of freedom and recruitment use clusters", {
  out <- sample_size_plan(ss_spec("cluster_mean",n=12,icc=.05,cluster_size=20),FALSE)
  expect_equal(out$counts$unit,"clusters")
  expect_equal(out$counts$participants,out$counts$recruit*20)
  p <- out$params
  ref <- stats::power.t.test(n=out$counts$n,delta=.5,sd=sqrt(.05+.95/20),strict=TRUE)$power
  expect_equal(out$metric,ref,tolerance=1e-10)
})

test_that("precision uses t and Wilson widths, not Wald at the boundary", {
  out <- sample_size_plan(ss_spec("precision_proportion",p1=.5,width=.05),FALSE)
  expect_equal(out$counts$n,381)
  n <- 100; z <- qnorm(.975)
  a <- sample_size_plan(ss_spec("precision_proportion","precision",n=n,p1=.1),FALSE)
  expect_equal(a$metric,z*sqrt(.1*.9/n+z^2/(4*n*n))/(1+z*z/n),tolerance=1e-12)
})

test_that("invalid inputs fail closed and JSON envelopes preserve errors", {
  expect_error(sample_size_plan(ss_spec(alpha=0)),"alpha")
  expect_error(sample_size_plan(ss_spec(dropout=1)),"dropout")
  expect_error(sample_size_plan(ss_spec(n=2.5)),"integer")
  expect_error(sample_size_plan(ss_spec(sd=0)),"sd")
  expect_error(sample_size_plan(ss_spec("regression","power",n=3,predictors=4)),"at least")
  expect_error(sample_size_plan(ss_spec("precision_mean","effect")),"solver")
  expect_false(jsonlite::fromJSON(sample_size_json('{"method":"unknown"}'))$ok)
})

test_that("exported script recomputes the actual result in a clean environment", {
  spec <- ss_spec("two_mean",ratio=2,dropout=.15,delta=.3)
  expected <- sample_size_plan(spec)
  code <- sample_size_script(spec)
  e <- new.env(parent=baseenv())
  expect_output(eval(parse(text=code),e),"planning model")
  expect_equal(e$result,expected)
})

test_that("rounded unequal allocation does not exclude feasible small designs", {
  out <- sample_size_plan(ss_spec(ratio=.1, delta=100),FALSE)
  expect_equal(out$counts$per_group,c(11,2))
})

test_that("upper-tail model statements do not claim a two-sided test", {
  for (m in c("anova","regression","chi_square")) {
    out <- sample_size_plan(ss_spec(m),FALSE)
    expect_match(out$statement,"upper-tail alpha")
  }
})

test_that("published browser reference fixtures agree with current native R", {
  fixtures <- jsonlite::fromJSON(testthat::test_path("..", "fixtures", "sample-size-reference.json"), simplifyVector=FALSE)
  expect_setequal(vapply(fixtures,function(s)s$spec$method,character(1)),.ss_methods())
  for (s in fixtures) {
    out <- sample_size_plan(s$spec,FALSE)
    expect_equal(out$metric,s$result$metric,tolerance=1e-9)
    expect_equal(out$counts$analyzable,s$result$counts$analyzable)
  }
})

test_that("reported assumptions retain the solved size and bounded effect domain", {
  out <- sample_size_plan(ss_spec(delta=.3),FALSE)
  expect_equal(out$params$n,out$counts$n)
  expect_error(sample_size_plan(ss_spec("two_mean","effect",sd=1e8),FALSE),"cannot be reached")
})

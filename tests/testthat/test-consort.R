spec <- list(figure = "consort",
  nodes = list(list(text = "Assessed (n=200)"), list(text = "Randomized (n=150)")),
  exclusions = list(list(text = "Excluded (n=50)")))

test_that("fig_consort returns an SVG with the node text", {
  out <- fig_consort(spec)
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$svg, "Randomized")
  expect_match(out$text, "Assessed")
})

test_that("fig_consort needs at least two nodes", {
  expect_error(fig_consort(list(figure = "consort", nodes = list())),
               "at least two", ignore.case = TRUE)
})

spec <- list(
  figure = "forest",
  rows = list(
    list(label = "Overall", estimate = 0.72, lower = 0.55, upper = 0.94),
    list(label = "Age < 65", estimate = 0.80, lower = 0.60, upper = 1.07)
  ),
  options = list(effect_label = "Hazard Ratio", null_line = 1)
)

test_that("fig_forest returns an SVG and a results sentence", {
  out <- fig_forest(spec)
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "0.72")
  expect_match(out$text, "0.55")
  expect_match(out$text, "0.94")
})

test_that("fig_forest errors clearly when a CI is inverted", {
  bad <- spec
  bad$rows[[1]]$lower <- 0.99  # lower > upper
  expect_error(fig_forest(bad), "confidence interval", ignore.case = TRUE)
})

test_that("render_figure routes forest specs end to end", {
  out <- jsonlite::fromJSON(render_figure(jsonlite::toJSON(spec, auto_unbox = TRUE)))
  expect_true(out$ok)
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
})

# tests/testthat/test-explore.R
rows_xy <- lapply(1:30, function(i)
  list(age = 40 + i, bmi = 20 + (i %% 7) + i / 10,
       arm = if (i %% 2) "Control" else "Treatment"))

test_that("scatter renders and emits matching standalone code", {
  out <- fig_explore(list(
    data = rows_xy,
    roles = list(x = "age", y = "bmi", color = "arm"),
    options = list(geom = "scatter", point_size = 2, alpha = 0.8,
                   smoother = "lm", se = TRUE)))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "library\\(ggplot2\\)")
  expect_match(out$text, "geom_point", fixed = TRUE)
  expect_match(out$text, "geom_smooth", fixed = TRUE)
  expect_match(out$text, 'aes(x = .data[["age"]]', fixed = TRUE)
  expect_match(out$text, "scale_colour_manual", fixed = TRUE)
  expect_match(out$text, "#4477AA", fixed = TRUE)      # palette inlined
  expect_no_match(out$text, "km_palette")              # never internals
  expect_no_match(out$text, "fig_theme")
})

test_that("adversarial column names and labels survive", {
  rows <- lapply(1:20, function(i)
    list(`age (years)` = 40 + i, `BMI, kg/m²` = 22 + i / 5))
  out <- fig_explore(list(
    data = rows,
    roles = list(x = "age (years)", y = "BMI, kg/m²"),
    options = list(geom = "scatter",
                   title = 'He said "wow"\nline two')))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, '.data[["age (years)"]]', fixed = TRUE)
  expect_match(out$text, '\\"wow\\"', fixed = TRUE)    # deparse-escaped quote
})

test_that("NA rows are excluded with a visible filter line", {
  rows <- c(rows_xy, list(list(age = 99, bmi = NULL, arm = "Control")))
  out <- fig_explore(list(
    data = rows, roles = list(x = "age", y = "bmi"),
    options = list(geom = "scatter")))
  expect_match(out$text, "complete.cases", fixed = TRUE)
  expect_match(out$text, "1 row")
})

test_that("readable errors: unknown geom, missing role, non-numeric column", {
  expect_error(fig_explore(list(data = rows_xy, roles = list(x = "age"),
    options = list(geom = "pie"))), "Unknown chart type")
  expect_error(fig_explore(list(data = rows_xy, roles = list(x = "age"),
    options = list(geom = "scatter"))), "y")
  expect_error(fig_explore(list(data = rows_xy,
    roles = list(x = "arm", y = "bmi"),
    options = list(geom = "scatter"))), "must be numeric")
  expect_error(fig_explore(list(data = rows_xy,
    roles = list(x = "nope", y = "bmi"),
    options = list(geom = "scatter"))), "not found")
})

test_that("dispatch routes explore", {
  json <- jsonlite::toJSON(list(figure = "explore",
    data = rows_xy, roles = list(x = "age", y = "bmi"),
    options = list(geom = "scatter")), auto_unbox = TRUE)
  res <- jsonlite::fromJSON(render_figure(json))
  expect_true(res$ok)
  expect_match(res$svg, "<svg", fixed = TRUE)
})

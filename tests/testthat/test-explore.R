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

demo_rows <- {
  csv <- read.csv(test_path("fixtures", "explore-demo.csv"),
                  stringsAsFactors = FALSE)
  lapply(seq_len(nrow(csv)), function(i) as.list(csv[i, , drop = FALSE]))
}

test_that("line draws per-subject trajectories via the group role", {
  out <- fig_explore(list(data = demo_rows,
    roles = list(x = "visit_month", y = "biomarker",
                 color = "arm", group = "patient_id"),
    options = list(geom = "line", linewidth = 0.8, show_points = TRUE)))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "geom_line(linewidth = 0.8)", fixed = TRUE)
  expect_match(out$text, 'group = .data[["patient_id"]]', fixed = TRUE)
  expect_match(out$text, "geom_point", fixed = TRUE)
})

test_that("boxplot factor()-wraps a numeric-coded x and supports jitter", {
  out <- fig_explore(list(data = demo_rows,
    roles = list(x = "ecog", y = "biomarker"),
    options = list(geom = "boxplot", jitter = TRUE, notch = FALSE)))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, 'factor(.data[["ecog"]])', fixed = TRUE)
  expect_match(out$text, "geom_jitter", fixed = TRUE)
})

test_that("violin renders with inner box", {
  out <- fig_explore(list(data = demo_rows,
    roles = list(x = "arm", y = "biomarker"),
    options = list(geom = "violin", inner_box = TRUE, trim = FALSE)))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "geom_violin", fixed = TRUE)
  expect_match(out$text, "geom_boxplot(width = 0.15", fixed = TRUE)
})

test_that("bar proportions use the specced denominators", {
  no_col <- fig_explore(list(data = demo_rows, roles = list(x = "sex"),
    options = list(geom = "bar", prop = TRUE)))
  expect_match(no_col$text, "after_stat(count/sum(count))", fixed = TRUE)
  expect_match(no_col$text, "proportion of total", fixed = TRUE)
  with_col <- fig_explore(list(data = demo_rows,
    roles = list(x = "sex", color = "arm"),
    options = list(geom = "bar", prop = TRUE)))
  expect_match(with_col$text, 'position = "fill"', fixed = TRUE)
  expect_match(with_col$text, "proportion within sex", fixed = TRUE)
  dodged <- fig_explore(list(data = demo_rows,
    roles = list(x = "sex", color = "arm"),
    options = list(geom = "bar", prop = FALSE, position = "dodge")))
  expect_match(dodged$text, 'position = "dodge"', fixed = TRUE)
  expect_match(dodged$text, "scale_fill_manual", fixed = TRUE)
})

test_that("histogram honours bins and the density toggle", {
  h <- fig_explore(list(data = demo_rows, roles = list(x = "biomarker"),
    options = list(geom = "histogram", bins = 15)))
  expect_match(h$text, "geom_histogram(bins = 15", fixed = TRUE)
  d <- fig_explore(list(data = demo_rows, roles = list(x = "biomarker"),
    options = list(geom = "histogram", density = TRUE)))
  expect_match(d$text, "geom_density", fixed = TRUE)
})

test_that("facet emits facet_wrap(vars(...)) and renders", {
  out <- fig_explore(list(data = demo_rows,
    roles = list(x = "age", y = "biomarker", facet = "sex"),
    options = list(geom = "scatter")))
  expect_match(out$text, 'facet_wrap(vars(.data[["sex"]]))', fixed = TRUE)
  expect_match(out$svg, "<svg", fixed = TRUE)
})

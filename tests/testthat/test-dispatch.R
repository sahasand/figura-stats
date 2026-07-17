test_that("unknown figure returns an ok:false error payload", {
  out <- jsonlite::fromJSON(render_figure('{"figure":"nope"}'))
  expect_false(out$ok)
  expect_match(out$error, "unknown figure", ignore.case = TRUE)
})

test_that("malformed JSON returns an error payload, not a crash", {
  out <- jsonlite::fromJSON(render_figure('{not json'))
  expect_false(out$ok)
})

test_that("summary routes through render_figure and returns a table", {
  spec <- list(figure = "summary",
               data = list(list(age = 50, grp = "A"), list(age = 60, grp = "A"),
                           list(age = 55, grp = "B"), list(age = 65, grp = "B")),
               roles = list(group = "grp"),
               options = list(continuous = list("age"), categorical = list(),
                              show_plots = FALSE))
  out <- jsonlite::fromJSON(render_figure(jsonlite::toJSON(spec, auto_unbox = TRUE)))
  expect_true(out$ok)
  expect_match(out$svg, "<table", fixed = TRUE)
})

test_that("render_figure routes cox and returns ok JSON with a table", {
  set.seed(7)
  n <- 120
  rows <- lapply(seq_len(n), function(i) list(
    time = round(rexp(1, 0.1) + 0.1, 2),
    status = if (runif(1) < 0.6) "dead" else "alive",
    arm = if (i %% 2) "A" else "B"))
  spec <- list(figure = "cox", data = rows,
               roles = list(time = "time", status = "status",
                            covariates = list("arm")),
               options = list(event_value = "dead", ref_levels = list()))
  res <- jsonlite::fromJSON(render_figure(jsonlite::toJSON(spec, auto_unbox = TRUE)))
  expect_true(res$ok)
  expect_match(res$svg, "<table", fixed = TRUE)
})

test_that("the retired table1 figure is no longer routed", {
  out <- jsonlite::fromJSON(render_figure('{"figure":"table1"}'))
  expect_false(out$ok)
  expect_match(out$error, "unknown figure", ignore.case = TRUE)
})

spec <- list(figure = "table1",
  groups = list("Treatment", "Placebo"),
  rows = list(
    list(variable = "Age, mean (SD)", values = list("58 (11)", "57 (12)")),
    list(variable = "Male, n (%)",    values = list("40 (53%)", "38 (51%)"))))

test_that("fig_table1 emits an HTML table and a TSV text version", {
  out <- fig_table1(spec)
  expect_match(out$svg, "<table")
  expect_match(out$svg, "Treatment")
  expect_match(out$text, "Age, mean \\(SD\\)\t58 \\(11\\)\t57 \\(12\\)")
})

test_that("fig_table1 errors when a row's value count != group count", {
  bad <- spec; bad$rows[[1]]$values <- list("58 (11)")
  expect_error(fig_table1(bad), "values", ignore.case = TRUE)
})

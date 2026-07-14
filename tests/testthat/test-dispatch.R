test_that("unknown figure returns an ok:false error payload", {
  out <- jsonlite::fromJSON(render_figure('{"figure":"nope"}'))
  expect_false(out$ok)
  expect_match(out$error, "unknown figure", ignore.case = TRUE)
})

test_that("malformed JSON returns an error payload, not a crash", {
  out <- jsonlite::fromJSON(render_figure('{not json'))
  expect_false(out$ok)
})

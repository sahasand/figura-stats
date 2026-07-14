test_that(".fig_theme returns a ggplot theme for known names and falls back", {
  expect_s3_class(.fig_theme("nejm"), "theme")
  expect_s3_class(.fig_theme("generic"), "theme")
  expect_s3_class(.fig_theme("unknown-name"), "theme")  # falls back, no error
})

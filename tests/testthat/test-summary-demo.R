test_that("frozen summary demo has the pinned teaching properties", {
  csv <- read.csv("fixtures/summary-demo.csv", stringsAsFactors = FALSE,
                  na.strings = "", colClasses = "character")
  expect_equal(nrow(csv), 120)
  expect_equal(sum(is.na(csv$length_of_stay)), 8)

  age <- as.numeric(csv$age)
  los <- as.numeric(csv$length_of_stay)
  # The whole feature turns on these two decisions coming out opposite ways.
  # (Verified against seed 41: age Shapiro p = 0.438, LOS skewness 1.31.)
  expect_equal(.summary_decide(age)$kind, "mean")
  expect_equal(.summary_decide(los)$kind, "median")
})

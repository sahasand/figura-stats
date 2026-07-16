test_that("groupcompare demo fixture has the frozen teaching properties", {
  csv <- read.csv(test_path("fixtures", "groupcompare-demo.csv"),
                  stringsAsFactors = FALSE)
  expect_equal(nrow(csv), 150)
  expect_equal(names(csv),
    c("arm", "biomarker_normal", "los_skewed", "responder"))
  expect_equal(sort(unique(csv$arm)), c("High dose", "Low dose", "Placebo"))
  expect_equal(sum(csv$los_skewed == "" | is.na(csv$los_skewed)), 6)
  expect_setequal(unique(csv$responder), c("No", "Yes"))
  # biomarker rises with dose; responder rate rises with dose (teaching targets)
  m <- tapply(csv$biomarker_normal, csv$arm, mean)
  expect_true(m[["High dose"]] > m[["Placebo"]])
})

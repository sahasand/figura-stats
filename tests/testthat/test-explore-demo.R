test_that("explore demo fixture has the frozen teaching properties", {
  csv <- read.csv(test_path("fixtures", "explore-demo.csv"),
                  stringsAsFactors = FALSE)
  expect_equal(nrow(csv), 120)
  expect_equal(names(csv), c("patient_id", "visit_month", "age", "bmi",
                             "biomarker", "arm", "sex", "ecog"))
  expect_equal(sort(unique(csv$visit_month)), c(0, 3, 6))
  expect_equal(length(unique(csv$patient_id)), 40)
  expect_equal(sum(is.na(csv$bmi)), 5)          # blank cells read as NA
  expect_true(all(csv$ecog %in% 0:2))           # numeric-coded category
  expect_equal(sort(unique(csv$arm)), c("Control", "Treatment"))
})

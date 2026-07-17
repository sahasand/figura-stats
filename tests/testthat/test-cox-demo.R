test_that("frozen cox demo fits and adjusted arm HR is protective", {
  csv <- read.csv(test_path("fixtures", "cox-demo.csv"), stringsAsFactors = FALSE)
  rows <- lapply(seq_len(nrow(csv)), function(i) as.list(csv[i, ]))
  spec <- list(figure = "cox", data = rows,
    roles = list(time = "followup_months", status = "status",
                 covariates = list("arm", "age", "stage")),
    options = list(event_value = "Death", ref_levels = list(arm = "Standard care", stage = "I")))
  out <- fig_cox(spec)
  hr <- as.numeric(sub(".*New treatment[^0-9]*([0-9.]+).*", "\\1",
                       gsub("\n", " ", out$text)))
  expect_true(hr < 0.9)   # adjusted protective effect visible after adjustment
})

test_that("frozen cox demo has the expected shape", {
  csv <- read.csv(test_path("fixtures", "cox-demo.csv"), stringsAsFactors = FALSE)
  expect_equal(nrow(csv), 220)
  expect_setequal(names(csv), c("arm", "age", "stage", "followup_months", "status"))
})

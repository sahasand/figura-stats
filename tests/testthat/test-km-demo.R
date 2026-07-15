demo_df <- function() {
  df <- read.csv(test_path("fixtures", "km-demo.csv"))
  df$event <- as.integer(df$status == "Death")
  df$group <- factor(df$group, levels = c("Standard care", "New treatment"))
  df
}

test_that("demo dataset is frozen (shape and checksum)", {
  expect_equal(unname(tools::md5sum(test_path("fixtures", "km-demo.csv"))),
               "f6559728fcf5429cb199747760f92ebf")
  df <- demo_df()
  expect_equal(nrow(df), 120)
  expect_equal(as.vector(table(df$group)), c(60, 60))
  expect_equal(sum(df$event), 52)   # 30 Standard care + 22 New treatment
})

test_that("demo dataset hits every pinned teaching target", {
  df <- demo_df()
  fit <- survival::survfit(survival::Surv(followup_months, event) ~ group, data = df)
  tab <- summary(fit)$table
  expect_equal(unname(tab["group=Standard care", "median"]), 26.0, tolerance = 1e-6)
  expect_true(is.na(tab["group=New treatment", "median"]))            # not reached
  sd <- survival::survdiff(survival::Surv(followup_months, event) ~ group, data = df)
  p <- 1 - stats::pchisq(sd$chisq, 1)
  expect_equal(unname(sd$chisq), 2.578, tolerance = 1e-3)
  # testthat's `tolerance` arg is relative (via waldo); for a value this close to
  # zero that admits no wiggle room at 4dp, so round to the pinned precision instead.
  expect_equal(round(p, 4), 0.1084)                                   # > 0.05, close
  cox <- survival::coxph(survival::Surv(followup_months, event) ~ group, data = df)
  expect_equal(unname(exp(coef(cox))), 0.6392, tolerance = 1e-4)      # New vs Standard
  ci <- exp(confint(cox))
  expect_equal(unname(ci[1]), 0.3683, tolerance = 1e-4)
  expect_equal(unname(ci[2]), 1.1091, tolerance = 1e-4)               # CI contains 1
  s <- summary(fit, times = c(12, 24), extend = TRUE)
  expect_equal(round(100 * s$surv, 1), c(73.5, 51.2, 84.4, 64.9))     # Std12,Std24,New12,New24
  expect_equal(s$n.risk, c(39, 27, 46, 32))                           # adequate 12/24 support
})

# Binary-outcome dataset with a real arm effect confounded by age. New treatment
# is channeled to older patients (higher risk), so its UNADJUSTED odds ratio looks
# weak and only adjusting for age reveals the protective effect (~exp(-0.9)=0.41).
mk_logit_rows <- function() {
  set.seed(52)
  n <- 240
  arm <- rep(c("Control", "Treated"), each = n / 2)
  age <- round(rnorm(n, 60, 10) + 6 * (arm == "Treated"), 1)
  lp <- -1 + 0.06 * (age - 60) - 0.9 * (arm == "Treated")
  y <- rbinom(n, 1, plogis(lp))
  outcome <- ifelse(y == 1, "Event", "NoEvent")
  lapply(seq_len(n), function(i)
    list(outcome = outcome[i], arm = arm[i], age = age[i]))
}
sc_logit <- function(rows, covariates = c("arm", "age"), ref_levels = NULL,
                     increments = NULL, event_value = "Event") {
  list(figure = "logistic", data = rows,
       roles = list(outcome = "outcome", covariates = as.list(covariates)),
       options = list(event_value = event_value,
                      ref_levels = ref_levels %||% list(),
                      increments = increments %||% list()))
}

test_that("fig_logistic returns svg table, text, and code", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_true(nzchar(out$text))
  expect_true(nzchar(out$code))
})

test_that("both unadjusted and adjusted ORs are reported", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$text, "adjusted", ignore.case = TRUE)
  expect_match(out$text, "[Uu]nadjusted")
})

# Third TSV field (adjusted OR) of the row whose Characteristic is `label`.
tsv_adj_cell <- function(text, label) {
  line <- grep(paste0("^", label, "\t"), strsplit(text, "\n")[[1]], value = TRUE)
  expect_length(line, 1)
  strsplit(line, "\t")[[1]][3]
}
tsv_unadj_cell <- function(text, label) {
  line <- grep(paste0("^", label, "\t"), strsplit(text, "\n")[[1]], value = TRUE)
  expect_length(line, 1)
  strsplit(line, "\t")[[1]][2]
}

test_that("adjusted arm OR recovers the simulated protective effect (< 1)", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  adj <- tsv_adj_cell(out$text, "Treated")
  or <- as.numeric(sub("^([0-9.]+) .*$", "\\1", adj))
  expect_false(is.na(or))
  expect_true(or < 0.85)
})

test_that("reference level appears and can be overridden", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$svg, "reference: Control", fixed = TRUE)
  out2 <- fig_logistic(sc_logit(mk_logit_rows(), ref_levels = list(arm = "Treated")))
  expect_match(out2$svg, "reference: Treated", fixed = TRUE)
  expect_false(grepl("reference: Control", out2$svg, fixed = TRUE))
  expect_match(out2$svg, "<span class=\"lvl\">Control</span>", fixed = TRUE)
  expect_false(grepl("<span class=\"lvl\">Treated</span>", out2$svg, fixed = TRUE))
})

test_that("a covariate whose header is not a syntactic R name is estimated", {
  rows <- lapply(mk_logit_rows(), function(r)
    setNames(list(r$outcome, r$arm, r$age), c("outcome", "study arm", "age at entry")))
  out <- fig_logistic(sc_logit(rows, covariates = c("study arm", "age at entry")))
  expect_false(grepl("not reliably estimated", out$text, fixed = TRUE))
  unadj <- tsv_unadj_cell(out$text, "Treated")
  adj <- tsv_adj_cell(out$text, "Treated")
  expect_false(unadj == "not reliably estimated")
  expect_false(adj == "not reliably estimated")
  expect_match(unadj, "^[0-9.]+ \\([0-9.]+")
  expect_match(adj, "^[0-9.]+ \\([0-9.]+")
  expect_true(as.numeric(sub("^([0-9.]+) .*$", "\\1", adj)) < 0.85)
})

test_that("blank outcome cells are treated as missing, not as non-events", {
  rows <- mk_logit_rows()
  for (i in 1:20) rows[[i]]$outcome <- ""
  out <- fig_logistic(sc_logit(rows))
  expect_match(out$text, "(n = 220", fixed = TRUE)
  expect_match(out$text, "20 row(s) with missing values were excluded.", fixed = TRUE)
})

test_that("an event value matching no row errors with an actionable message", {
  expect_error(fig_logistic(sc_logit(mk_logit_rows(), event_value = "Relapse")),
               "Relapse", fixed = TRUE)
})

test_that("no covariate selected errors readably", {
  expect_error(fig_logistic(sc_logit(mk_logit_rows(), covariates = character(0))),
               "covariate", ignore.case = TRUE)
})

test_that("too few events errors readably", {
  rows <- mk_logit_rows()[1:60]
  rows <- lapply(rows, function(r) { r$outcome <- "NoEvent"; r })
  rows[[1]]$outcome <- "Event"; rows[[2]]$outcome <- "Event"
  expect_error(fig_logistic(sc_logit(rows)), "event", ignore.case = TRUE)
})

test_that("constant covariate errors readably", {
  rows <- lapply(mk_logit_rows(), function(r) { r$arm <- "Only"; r })
  expect_error(fig_logistic(sc_logit(rows, covariates = c("arm"))),
               "one level", ignore.case = TRUE)
})

test_that("fig_logistic svg includes a forest-plot svg", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_gt(nchar(out$svg), 800)
})

test_that("forest plot labels a non-syntactic covariate header without backticks", {
  rows <- lapply(mk_logit_rows(), function(r)
    setNames(list(r$outcome, r$arm, r$age), c("outcome", "study arm", "age at entry")))
  out <- fig_logistic(sc_logit(rows, covariates = c("study arm", "age at entry")))
  # Assert on the forest plot alone, so the table's own labels can't satisfy these.
  forest <- sub("^.*</table></div>", "", out$svg)
  expect_match(forest, "<svg", fixed = TRUE)
  expect_match(forest, "study arm: Treated", fixed = TRUE)
  expect_match(forest, "age at entry (per 1 unit)", fixed = TRUE)
  expect_false(grepl("`", forest, fixed = TRUE))
})

test_that("methods text reports the C-statistic as apparent (in-sample)", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$text, "apparent (in-sample) C-statistic = ", fixed = TRUE)
})

test_that("a well-conditioned model raises no separation, EPV or VIF caution", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_false(grepl("separation", out$text, ignore.case = TRUE))
  expect_false(grepl("EPV", out$text, fixed = TRUE))
  expect_false(grepl("VIF", out$text, fixed = TRUE))
  expect_false(grepl("numerical warning", out$text, fixed = TRUE))
})

test_that("two weakly-correlated continuous covariates raise no VIF caution", {
  # The demo fixture's only continuous covariate is `age`, so .logistic_vif returns
  # NULL there and the `any(vif > 5)` threshold is never consulted. Here two
  # continuous covariates exist (VIF is computed) but are near-orthogonal.
  set.seed(21); n <- 300
  x1 <- rnorm(n)
  x2 <- 0.1 * x1 + rnorm(n)                    # r ~ 0.1 with x1 -> VIF ~ 1.01
  y <- rbinom(n, 1, plogis(0.5 * x1))
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), x1 = x1[i], x2 = x2[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("x1", "x2")))
  expect_false(grepl("VIF", out$text, fixed = TRUE))
})

test_that("EPV warning fires when events per term is under 10", {
  # 6 model terms (5 non-reference levels of `g` + `x`) against 10 events -> EPV < 2.
  set.seed(9); n <- 60
  g <- sample(LETTERS[1:6], n, replace = TRUE)   # 5 non-reference terms
  x <- rnorm(n)
  y <- ifelse(seq_len(n) <= 10, "Event", "NoEvent")
  rows <- lapply(seq_len(n), function(i) list(outcome = y[i], g = g[i], x = x[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("g", "x")))
  expect_match(out$text, "EPV", fixed = TRUE)
})

test_that("separation is detected and flagged, not silently shipped", {
  # `flag` perfectly predicts the outcome -> quasi-complete separation.
  set.seed(3); n <- 120
  y <- rbinom(n, 1, 0.5)
  flag <- ifelse(y == 1, "hi", "lo")           # perfect predictor
  age <- rnorm(n, 60, 10)
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), flag = flag[i], age = age[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("flag", "age")))
  expect_match(out$text, "separation", ignore.case = TRUE)
  expect_match(out$svg, "not reliably estimated", fixed = TRUE)
})

test_that("multicollinearity (VIF) is flagged for near-duplicate covariates", {
  set.seed(7); n <- 300
  x1 <- rnorm(n)
  x2 <- x1 + rnorm(n, 0, 0.05)                 # r ~ 0.99 with x1
  y <- rbinom(n, 1, plogis(0.5 * x1))
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), x1 = x1[i], x2 = x2[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("x1", "x2")))
  expect_match(out$text, "VIF", fixed = TRUE)
})

test_that("an exactly duplicated covariate reports an infinite VIF in words", {
  set.seed(11); n <- 200
  x1 <- rnorm(n)
  y <- rbinom(n, 1, plogis(0.5 * x1))
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), x1 = x1[i], x_copy = x1[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("x1", "x_copy")))
  expect_match(out$text, "VIF = effectively infinite", fixed = TRUE)
  expect_false(grepl("VIF = Inf", out$text, fixed = TRUE))
  # The blown-out CI trips the separation rule here, but the cause is collinearity,
  # so the sentence must name both and must not prescribe only separation remedies.
  expect_match(out$text, "separation or severe collinearity", fixed = TRUE)
  expect_match(out$text, "redundant variable", fixed = TRUE)
})

test_that("an infinite VIF is reported in words even when a finite VIF also exists", {
  # x1 and x_copy are exactly collinear (VIF = Inf) while x3 is independent
  # (VIF ~ 1.0). Reporting the largest FINITE VIF here would print
  # "largest VIF = 1.0, above the usual threshold of 5" — self-contradictory.
  set.seed(13); n <- 200
  x1 <- rnorm(n); x3 <- rnorm(n)
  y <- rbinom(n, 1, plogis(0.5 * x1))
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"),
         x1 = x1[i], x_copy = x1[i], x3 = x3[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("x1", "x_copy", "x3")))
  expect_match(out$text, "VIF = effectively infinite", fixed = TRUE)
  expect_false(grepl("VIF = 1.0", out$text, fixed = TRUE))
})

test_that(".logistic_fit_one captures the separation warning rather than leaking it", {
  # The only consumer of the warning-capture seam is fig_logistic's `sep_warn`, which
  # greps "fitted probabilities"; pin the captured message's shape directly. A
  # continuous perfect predictor raises BOTH glm warnings and the capture keeps the
  # last one, which is the "fitted probabilities" message sep_warn looks for.
  set.seed(5); n <- 120
  x <- rnorm(n)
  df <- data.frame(.y = as.integer(x > 0), x = x, check.names = FALSE)
  res <- .logistic_fit_one(stats::as.formula(".y ~ `x`"), df)
  expect_false(is.null(res$warn))
  expect_match(res$warn, "fitted probabilities numerically 0 or 1 occurred", fixed = TRUE)
  expect_s3_class(res$fit, "glm")
})

test_that(".logistic_other_warn speaks up for a non-separation fit warning", {
  # The separation message has its own dedicated sentence, so it must NOT also
  # produce the generic advisory; anything else must never be discarded silently.
  expect_identical(.logistic_other_warn(list(NULL, NULL)), "")
  expect_identical(
    .logistic_other_warn(list("glm.fit: fitted probabilities numerically 0 or 1 occurred")),
    "")
  msg <- .logistic_other_warn(list(NULL, "glm.fit: algorithm did not converge"))
  expect_match(msg, "CAUTION", fixed = TRUE)
  expect_match(msg, "glm.fit: algorithm did not converge", fixed = TRUE)
  expect_match(msg, "seek statistical review", fixed = TRUE)
})

test_that("a separation-only fit does not also raise the generic warning advisory", {
  set.seed(3); n <- 120
  y <- rbinom(n, 1, 0.5)
  flag <- ifelse(y == 1, "hi", "lo")
  age <- rnorm(n, 60, 10)
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), flag = flag[i], age = age[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("flag", "age")))
  expect_match(out$text, "separation", ignore.case = TRUE)
  expect_false(grepl("numerical warning", out$text, fixed = TRUE))
})

test_that("an unreliable UNADJUSTED cell is explained in the methods text", {
  # x is explained away by z: its crude effect is large (and, at a per-15-unit
  # increment, blows the Wald CI past the 1e6 reliability threshold) while the
  # adjusted effect is near zero and stays inside it. Only the unadjusted column
  # reads "not reliably estimated", so a check on the adjusted column alone would
  # leave that cell in the table with nothing explaining it.
  set.seed(101); n <- 400
  z <- rnorm(n)
  x <- z + rnorm(n, 0, 0.3)
  y <- rbinom(n, 1, plogis(-0.5 + 1.2 * z))
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), x = x[i], z = z[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("x", "z"),
                               increments = list(x = 15)))
  label <- "x \\(per 15 units\\)"
  expect_identical(tsv_unadj_cell(out$text, label), "not reliably estimated")
  expect_false(tsv_adj_cell(out$text, label) == "not reliably estimated")
  expect_match(out$text, "separation or severe collinearity", fixed = TRUE)
})

test_that("a single-covariate model is described as univariable, not adjusted", {
  out <- fig_logistic(sc_logit(mk_logit_rows(), covariates = c("arm")))
  expect_match(out$text, "Univariable logistic regression (n = 240", fixed = TRUE)
  expect_match(out$text, "arm as the only covariate", fixed = TRUE)
  expect_match(out$text, "No adjustment was made for other variables", fixed = TRUE)
  expect_false(grepl("Multivariable", out$text, fixed = TRUE))
  expect_false(grepl("adjusted for arm", out$text, fixed = TRUE))
})

test_that("a multi-covariate model keeps the multivariable wording", {
  out <- fig_logistic(sc_logit(mk_logit_rows(), covariates = c("arm", "age")))
  expect_match(out$text, "Multivariable logistic regression (n = 240", fixed = TRUE)
  expect_match(out$text, "adjusted for arm, age", fixed = TRUE)
  expect_false(grepl("Univariable logistic regression", out$text, fixed = TRUE))
})

test_that("influential observations (Cook's distance) are flagged when present", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$text, "flagged as influential (Cook's distance > 4/n)", fixed = TRUE)
})

test_that("logistic code parses as R and mentions glm(binomial)", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_silent(parse(text = out$code))
  expect_match(out$code, "glm(", fixed = TRUE)
  expect_match(out$code, "binomial", fixed = TRUE)
})

test_that("demo-shape spec embeds data (no read.csv) in the script", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))   # no source_filename -> embedded
  # The embed literal specifically — the read.csv path also emits "data.frame"
  # further down, so the bare word could never fail this test.
  expect_match(out$code, "df <- data.frame(outcome = c(\"", fixed = TRUE)
  expect_false(grepl("read.csv", out$code, fixed = TRUE))
})

test_that("upload-shape spec reads the user's real column names", {
  spec <- sc_logit(mk_logit_rows())
  spec$options$source_filename <- "mydata.csv"
  spec$options$source_roles <- list(outcome = "outcome",
    covariates = as.list(c("arm", "age")), event = "Event")
  out <- fig_logistic(spec)
  expect_match(out$code, "read.csv", fixed = TRUE)
  expect_match(out$code, "mydata.csv", fixed = TRUE)
})

# The three numbers of an OR cell "1.23 (0.45–2.34, p=0.010)".
tsv_cell_nums <- function(cell) {
  m <- regmatches(cell, regexec("^([0-9.]+) \\(([0-9.]+)–([0-9.]+),", cell))[[1]]
  expect_length(m, 4)
  as.numeric(m[-1])
}

test_that("the generated script runs and reproduces the app's odds ratios", {
  # Both awkward cases at once: a non-default reference level and a non-1
  # increment. If the script's prep pipeline diverges from .logistic_prep in
  # either content or ORDER, these numbers stop matching.
  spec <- sc_logit(mk_logit_rows(), ref_levels = list(arm = "Treated"),
                   increments = list(age = 10))
  out <- fig_logistic(spec)
  env <- new.env(parent = globalenv())
  expect_silent(eval(parse(text = out$code), env))

  adj <- exp(cbind(stats::coef(env$fit), stats::confint.default(env$fit)))
  expect_equal(sprintf("%.2f", adj["armControl", ]),
               sprintf("%.2f", tsv_cell_nums(tsv_adj_cell(out$text, "Control"))))
  expect_equal(sprintf("%.2f", adj["age", ]),
               sprintf("%.2f", tsv_cell_nums(tsv_adj_cell(out$text, "age \\(per 10 units\\)"))))

  # m_uni holds the LAST univariable model the script fitted (age).
  uni <- exp(cbind(stats::coef(env$m_uni), stats::confint.default(env$m_uni)))
  expect_equal(sprintf("%.2f", uni["age", ]),
               sprintf("%.2f", tsv_cell_nums(tsv_unadj_cell(out$text, "age \\(per 10 units\\)"))))
})

test_that("the script runs for a single non-syntactic covariate", {
  rows <- lapply(mk_logit_rows(), function(r)
    setNames(list(r$outcome, r$arm, r$age), c("outcome", "study arm", "age at entry")))
  out <- fig_logistic(sc_logit(rows, covariates = c("study arm")))
  env <- new.env(parent = globalenv())
  expect_silent(eval(parse(text = out$code), env))
  adj <- exp(cbind(stats::coef(env$fit), stats::confint.default(env$fit)))
  expect_equal(sprintf("%.2f", adj["`study arm`Treated", ]),
               sprintf("%.2f", tsv_cell_nums(tsv_adj_cell(out$text, "Treated"))))
})

test_that("no influential-point sentence when no observation exceeds 4/n", {
  # Perfectly balanced, effect-free design: every Cook's distance sits under 4/n.
  n <- 200
  x <- rep(seq(-1, 1, length.out = n / 2), 2)
  y <- rep(c(0, 1), each = n / 2)
  rows <- lapply(seq_len(n), function(i)
    list(outcome = ifelse(y[i] == 1, "Event", "NoEvent"), x = x[i]))
  out <- fig_logistic(sc_logit(rows, covariates = c("x")))
  expect_false(grepl("influential", out$text, fixed = TRUE))
  expect_false(grepl("Cook", out$text, fixed = TRUE))
})

test_that("render_figure routes logistic specs and returns ok JSON", {
  spec <- sc_logit(mk_logit_rows())
  js <- jsonlite::toJSON(spec, auto_unbox = TRUE)
  res <- jsonlite::fromJSON(render_figure(js))
  expect_true(res$ok)
  expect_match(res$svg, "<table", fixed = TRUE)
  expect_true(nzchar(res$code))
})

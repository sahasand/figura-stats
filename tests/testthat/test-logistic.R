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
  expect_true(!is.null(out$code))
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

test_that("methods text reports the C-statistic (discrimination)", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_match(out$text, "C-statistic", fixed = TRUE)
})

test_that("a well-conditioned model raises none of the quality cautions", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_false(grepl("separation", out$text, ignore.case = TRUE))
  expect_false(grepl("EPV", out$text, fixed = TRUE))
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
})

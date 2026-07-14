#' Univariable + multivariable regression table (logistic/Cox/linear).
fig_regression <- function(spec) {
  covs <- unlist(spec$roles$covariates)
  if (length(covs) == 0) stop("Select at least one covariate.")
  model <- spec$options$model %||% "logistic"
  rows <- spec$data

  col <- function(name, numeric = TRUE) {
    raw <- vapply(rows, function(r) {
      x <- r[[name]]; if (is.null(x)) NA_character_ else as.character(x)
    }, character(1))
    if (!numeric) return(raw)
    num <- suppressWarnings(as.numeric(raw))
    failed <- !is.na(raw) & raw != "" & is.na(num)
    if (any(failed)) stop(sprintf("Column '%s' must be numeric.", name))
    num
  }
  df <- data.frame(lapply(covs, function(c) {
    raw <- vapply(rows, function(r) as.character(r[[c]] %||% ""), character(1))
    num <- suppressWarnings(as.numeric(raw))
    if (all(!is.na(num) | raw == "")) num else raw   # numeric if it all parses
  }), stringsAsFactors = FALSE)
  names(df) <- covs

  rhs <- paste(sprintf("`%s`", covs), collapse = " + ")

  build <- function() {
    if (model == "cox") {
      if (is.null(spec$roles$time) || is.null(spec$roles$status))
        stop("Cox regression needs a time column and a 0/1 status column.")
      df$.time <- col(spec$roles$time); df$.status <- col(spec$roles$status)
      if (any(is.na(df$.time)) || !all(df$.status %in% c(0, 1)))
        stop("Cox regression needs numeric time and a 0/1 status column.")
      fml <- stats::as.formula(paste("survival::Surv(.time, .status) ~", rhs))
      survival::coxph(fml, data = df)
    } else if (model == "linear") {
      if (is.null(spec$roles$outcome)) stop("Select an outcome column.")
      df$.y <- col(spec$roles$outcome)
      stats::lm(stats::as.formula(paste(".y ~", rhs)), data = df)
    } else {
      if (is.null(spec$roles$outcome)) stop("Select an outcome column.")
      y <- col(spec$roles$outcome, numeric = FALSE)
      if (length(unique(y[!is.na(y) & y != ""])) != 2) stop("Logistic regression needs a binary (two-value) outcome.")
      df$.y <- as.integer(factor(y)) - 1L
      stats::glm(stats::as.formula(paste(".y ~", rhs)),
                 data = df, family = stats::binomial())
    }
  }
  fit <- build()
  tbl <- suppressWarnings(gtsummary::tbl_regression(fit, exponentiate = (model != "linear")))
  html <- suppressWarnings(gtsummary::as_kable(tbl, format = "html"))
  # Plain-text (TSV-ish) rendering for pasting.
  txtdf <- as.data.frame(tbl$table_body[, intersect(c("label", "estimate", "conf.low", "conf.high", "p.value"),
                                                     names(tbl$table_body))])
  effect_word <- switch(model, cox = "HR", linear = "beta", "OR")
  tsv <- paste0(effect_word, " table\n",
                paste(apply(txtdf, 1, function(r) paste(r, collapse = "\t")), collapse = "\n"))
  list(svg = as.character(html), text = tsv)
}

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

  # Prepare the modelling frame (adds .y or .time/.status to df) and fit the
  # multivariable model. Returns the fit; `df` is augmented in the parent frame
  # so the same columns are available to the univariable models below.
  build <- function() {
    if (model == "cox") {
      if (is.null(spec$roles$time) || is.null(spec$roles$status))
        stop("Cox regression needs a time column and a 0/1 status column.")
      df$.time <<- col(spec$roles$time); df$.status <<- col(spec$roles$status)
      if (any(is.na(df$.time)) || !all(df$.status %in% c(0, 1)))
        stop("Cox regression needs numeric time and a 0/1 status column.")
      fml <- stats::as.formula(paste("survival::Surv(.time, .status) ~", rhs))
      survival::coxph(fml, data = df)
    } else if (model == "linear") {
      if (is.null(spec$roles$outcome)) stop("Select an outcome column.")
      df$.y <<- col(spec$roles$outcome)
      stats::lm(stats::as.formula(paste(".y ~", rhs)), data = df)
    } else {
      if (is.null(spec$roles$outcome)) stop("Select an outcome column.")
      y <- col(spec$roles$outcome, numeric = FALSE)
      if (length(unique(y[!is.na(y) & y != ""])) != 2) stop("Logistic regression needs a binary (two-value) outcome.")
      df$.y <<- as.integer(factor(y)) - 1L
      stats::glm(stats::as.formula(paste(".y ~", rhs)),
                 data = df, family = stats::binomial())
    }
  }
  fit <- build()
  exp <- (model != "linear")

  # MULTIVARIABLE (adjusted) — the existing table.
  mv <- suppressWarnings(gtsummary::tbl_regression(fit, exponentiate = exp))

  # UNIVARIABLE (unadjusted) — one model per covariate via tbl_uvregression.
  uv <- suppressWarnings(
    if (model == "cox") {
      gtsummary::tbl_uvregression(
        data = df[c(covs, ".time", ".status")],
        y = survival::Surv(.time, .status),
        method = survival::coxph, exponentiate = TRUE,
        include = gtsummary::all_of(covs))
    } else if (model == "linear") {
      gtsummary::tbl_uvregression(
        data = df[c(covs, ".y")], y = .y,
        method = stats::lm, exponentiate = FALSE,
        include = gtsummary::all_of(covs))
    } else {
      gtsummary::tbl_uvregression(
        data = df[c(covs, ".y")], y = .y,
        method = stats::glm, method.args = list(family = stats::binomial),
        exponentiate = TRUE, include = gtsummary::all_of(covs))
    })

  # MERGE univariable + multivariable under two spanners.
  merged <- suppressWarnings(gtsummary::tbl_merge(
    list(uv, mv),
    tab_spanner = c("**Univariable**", "**Multivariable**")))
  html <- suppressWarnings(gtsummary::as_kable(merged, format = "html"))
  html <- add_spanner_row(merged, as.character(html))

  # Plain-text (TSV-ish) rendering for pasting — based on the adjusted
  # (multivariable) estimates, keeping the effect-word label.
  txtdf <- as.data.frame(mv$table_body[, intersect(c("label", "estimate", "conf.low", "conf.high", "p.value"),
                                                    names(mv$table_body))])
  effect_word <- switch(model, cox = "HR", linear = "beta", "OR")
  tsv <- paste0(effect_word, " table (multivariable)\n",
                paste(apply(txtdf, 1, function(r) paste(r, collapse = "\t")), collapse = "\n"))
  list(svg = html, text = tsv)
}

# as_kable(format="html") drops gtsummary's tab_spanner header row, so inject it
# from the merged table's spanning-header metadata. Emits a <tr> of colspanned
# <th> cells (blank for ungrouped leading columns) at the top of <thead>.
add_spanner_row <- function(merged, html) {
  html <- as.character(html)
  hdr <- merged$table_styling$header
  vis <- hdr$column[!hdr$hide]
  sp <- merged$table_styling$spanning_header
  if (is.null(sp) || !length(vis)) return(html)
  strip <- function(x) trimws(gsub("\\*", "", x))
  spanners <- vapply(vis, function(cl) {
    hit <- sp$spanning_header[sp$column == cl]
    if (length(hit)) strip(hit[1]) else ""
  }, character(1))
  cells <- character(0); i <- 1L; n <- length(spanners)
  while (i <= n) {
    j <- i
    while (j < n && spanners[j + 1L] == spanners[i]) j <- j + 1L
    span <- j - i + 1L
    txt <- spanners[i]
    if (nzchar(txt))
      cells <- c(cells, sprintf('<th style="text-align:center;border-bottom:1px solid;" colspan="%d">%s</th>', span, txt))
    else
      cells <- c(cells, sprintf('<th colspan="%d"></th>', span))
    i <- j + 1L
  }
  row <- paste0("  <tr>\n   ", paste(cells, collapse = "\n   "), "\n  </tr>\n")
  sub("(<thead>\\s*\\n)", paste0("\\1", row), html)
}

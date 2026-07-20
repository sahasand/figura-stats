# R/logistic.R
# Binary-outcome logistic regression: univariable (unadjusted) odds ratio per
# covariate beside the joint-model adjusted OR (clinical "Table 3").
# Base stats::glm only — no extra package. Wald CIs: exp(est +/- 1.96 se),
# stable under separation.

# TRUE iff every non-blank cell of a column parses as numeric (mirrors .cox_is_numeric).
.logistic_is_numeric <- function(rows, colname) {
  raw <- .char_col(rows, colname)
  raw[!is.na(raw) & raw == ""] <- NA
  num <- suppressWarnings(as.numeric(raw))
  !any(!is.na(raw) & is.na(num))
}

# The term label R uses for a column inside a formula, and therefore the prefix of
# its coefficient names. A syntactic name appears bare (`arm` -> "armTreated"); a
# non-syntactic one (a header with a space, common in clinical CSV exports) keeps
# the backticks the formula was written with ("`study arm`Treated").
.logistic_term_label <- function(cl) {
  if (identical(make.names(cl), cl)) cl else sprintf("`%s`", cl)
}

# Most frequent non-NA value of a character vector (default reference level).
.logistic_most_frequent <- function(x) {
  x <- x[!is.na(x) & x != ""]
  names(sort(table(x), decreasing = TRUE))[1]
}

# Per-covariate positive increment (default 1); non-numeric/invalid -> 1.
.logistic_increment <- function(increments, cl) {
  k <- suppressWarnings(as.numeric(increments[[cl]] %||% 1))
  if (length(k) != 1 || is.na(k) || !is.finite(k) || k <= 0) 1 else k
}

# Build the complete-case working frame and covariate metadata.
.logistic_prep <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  covs <- unlist(spec$roles$covariates %||% list())
  if (length(covs) == 0) stop("Select at least one covariate.")
  ocol <- spec$roles$outcome
  if (is.null(ocol)) stop("Choose an outcome column.")
  have <- names(rows[[1]])
  for (cl in c(ocol, covs))
    if (!(cl %in% have)) stop(sprintf("Column '%s' not found in the data.", cl))

  ev <- as.character(spec$options$event_value %||% "")
  outcome_raw <- .char_col(rows, ocol)
  # A blank outcome cell is missing, not a non-event: NA here so complete.cases
  # drops the row instead of silently counting it in the non-event group.
  outcome_raw[!is.na(outcome_raw) & outcome_raw == ""] <- NA
  ev_num <- suppressWarnings(as.numeric(ev))
  y <- as.integer(outcome_raw == ev |
    (!is.na(ev_num) & !is.na(suppressWarnings(as.numeric(outcome_raw))) &
       suppressWarnings(as.numeric(outcome_raw)) == ev_num))

  cov_types <- setNames(
    vapply(covs, function(cl) if (.logistic_is_numeric(rows, cl)) "numeric" else "categorical",
           character(1)), covs)
  ref_levels <- spec$options$ref_levels %||% list()
  increments <- spec$options$increments %||% list()
  incr <- setNames(vapply(covs, function(cl)
    if (cov_types[[cl]] == "numeric") .logistic_increment(increments, cl) else NA_real_,
    numeric(1)), covs)

  cols <- list(.y = y)
  for (cl in covs) {
    if (cov_types[[cl]] == "numeric") cols[[cl]] <- .numeric_col(rows, cl)
    else { v <- .char_col(rows, cl); v[!is.na(v) & v == ""] <- NA; cols[[cl]] <- v }
  }
  df <- as.data.frame(cols, stringsAsFactors = FALSE, check.names = FALSE)
  n_before <- nrow(df)
  df <- df[stats::complete.cases(df), , drop = FALSE]
  n_dropped <- n_before - nrow(df)

  # Outcome size is checked before covariate structure: with too few events every
  # downstream diagnosis (a constant covariate included) is a symptom of the same
  # problem, and "too few events" is the actionable message.
  n_event <- sum(df$.y == 1)
  n_min <- min(n_event, nrow(df) - n_event)
  # No match at all is a column/value mix-up, not a sample-size problem — say so,
  # otherwise "too few events (0 ...)" points the user at the wrong cause.
  if (n_event == 0) stop(sprintf(
    "No rows have outcome '%s' in column '%s'; check the event value you selected.",
    ev, ocol))
  if (n_min < 10) stop(sprintf("Too few events (%d in the smaller outcome group) to fit a reliable logistic model; at least 10 are needed.", n_min))

  # Rescale numeric covariates to the chosen increment (per-k OR = exp(k*beta));
  # this changes OR and CI but NOT the p-value (Wald statistic is scale-invariant).
  for (cl in covs) if (cov_types[[cl]] == "numeric" && incr[[cl]] != 1)
    df[[cl]] <- df[[cl]] / incr[[cl]]

  # Factor + relevel categoricals; default reference = most frequent level.
  for (cl in covs) if (cov_types[[cl]] == "categorical") {
    ref <- as.character(ref_levels[[cl]] %||% .logistic_most_frequent(df[[cl]]))
    lv <- unique(df[[cl]])
    if (length(lv) < 2) stop(sprintf("Covariate '%s' has only one level after removing missing values.", cl))
    if (!ref %in% lv) ref <- .logistic_most_frequent(df[[cl]])
    df[[cl]] <- stats::relevel(factor(df[[cl]]), ref = ref)
  }
  list(df = df, covs = covs, cov_types = cov_types, ref_levels = ref_levels,
       incr = incr, n = nrow(df), n_event = n_event, n_min = n_min, n_dropped = n_dropped)
}

# Fit one glm, capturing (not suppressing) fit warnings so an unreliable OR can be
# flagged. muffleWarning keeps it off the WARN-0 gate. The "fitted probabilities
# numerically 0 or 1" warning is the separation signal, read in fig_logistic.
.logistic_fit_one <- function(formula, df) {
  warn <- NULL
  fit <- withCallingHandlers(
    stats::glm(formula, data = df, family = stats::binomial()),
    warning = function(w) { warn <<- conditionMessage(w); invokeRestart("muffleWarning") })
  list(fit = fit, warn = warn)
}

# Univariable glm per covariate + one joint model.
.logistic_fits <- function(df, covs, cov_types) {
  uni <- lapply(covs, function(cl)
    .logistic_fit_one(stats::as.formula(sprintf(".y ~ `%s`", cl)), df))
  names(uni) <- covs
  joint_f <- stats::as.formula(paste0(".y ~ ",
    paste(sprintf("`%s`", covs), collapse = " + ")))
  joint <- .logistic_fit_one(joint_f, df)
  list(uni = uni, joint = joint)
}

# Wald OR (95% CI, p) for one coefficient key from a summary() matrix. Returns
# "not reliably estimated" when non-finite or the CI blows up past OR 1e6
# (the separation signature).
.logistic_or_cell <- function(smat, key) {
  if (!(key %in% rownames(smat))) return("not reliably estimated")
  est <- smat[key, "Estimate"]; se <- smat[key, "Std. Error"]
  p <- smat[key, "Pr(>|z|)"]
  or <- exp(est); lo <- exp(est - 1.96 * se); hi <- exp(est + 1.96 * se)
  if (!is.finite(or) || !is.finite(lo) || !is.finite(hi) || hi > 1e6)
    return("not reliably estimated")
  pf <- if (p < 0.001) "p<0.001" else sprintf("p=%.3f", p)
  sprintf("%.2f (%.2f–%.2f, %s)", or, lo, hi, pf)
}

# One display row per covariate LEVEL (reference marked). Numeric rows label the
# increment. `term` leading with two spaces marks an indented level row.
.logistic_rows <- function(p, fits) {
  rows <- list()
  jsm <- summary(fits$joint$fit)$coefficients
  for (cl in p$covs) {
    usm <- summary(fits$uni[[cl]]$fit)$coefficients
    tl <- .logistic_term_label(cl)
    if (p$cov_types[[cl]] == "numeric") {
      k <- p$incr[[cl]]
      unit <- if (k == 1) "per 1 unit" else sprintf("per %g units", k)
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (%s)", cl, unit),
        unadj = .logistic_or_cell(usm, tl), adj = .logistic_or_cell(jsm, tl))
    } else {
      lv <- levels(p$df[[cl]])
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (reference: %s)", cl, lv[1]),
        unadj = "", adj = "")
      for (l in lv[-1]) {
        key <- paste0(tl, l)
        rows[[length(rows) + 1]] <- list(term = paste0("  ", l),
          unadj = .logistic_or_cell(usm, key), adj = .logistic_or_cell(jsm, key))
      }
    }
  }
  rows
}

# HTML table (reuses .esc). Mirrors .cox_table_html: "(reference:" header rows keep
# blank effect cells; other blank cells read "1 (reference)".
.logistic_table_html <- function(disp_rows) {
  header <- "<tr><th>Characteristic</th><th>Unadjusted OR (95% CI)</th><th>Adjusted OR (95% CI)</th></tr>"
  body <- vapply(disp_rows, function(r) {
    is_header <- grepl("\\(reference:", r$term)
    indent <- startsWith(r$term, "  ")
    label <- .esc(trimws(r$term))
    if (indent) label <- paste0("<span class=\"lvl\">", label, "</span>")
    if (is_header) { unadj <- ""; adj <- "" }
    else {
      unadj <- if (nzchar(r$unadj)) .esc(r$unadj) else "1 (reference)"
      adj <- if (nzchar(r$adj)) .esc(r$adj) else "1 (reference)"
    }
    sprintf("<tr><td>%s</td><td>%s</td><td>%s</td></tr>", label, unadj, adj)
  }, character(1))
  paste0("<table class=\"table1\"><thead>", header, "</thead><tbody>",
         paste(body, collapse = ""), "</tbody></table>")
}

# Forest plot of ADJUSTED ORs (one point per non-reference level / numeric term),
# log x-axis, dashed rule at OR = 1. geom_errorbar(orientation="y") — never
# geom_errorbarh; linewidth — never size. Inclusion mirrors .logistic_or_cell's
# reliability rule: drop non-finite terms and CIs that blow up past OR 1e6.
.logistic_forest_svg <- function(p, fits) {
  sm <- summary(fits$joint$fit)$coefficients
  keys <- setdiff(rownames(sm), "(Intercept)")
  if (length(keys) == 0) return("")
  est <- sm[keys, "Estimate"]; se <- sm[keys, "Std. Error"]
  or <- exp(est); lo <- exp(est - 1.96 * se); hi <- exp(est + 1.96 * se)
  keep <- is.finite(or) & is.finite(lo) & is.finite(hi) & hi <= 1e6
  if (!any(keep)) return("")
  # Coefficient names carry the formula's term label, which is backticked for a
  # non-syntactic header ("`study arm`Treated"), so match and strip that prefix
  # literally — a bare-name regex would miss it and leak the raw coefficient name.
  # Longest term label first, so a covariate whose name prefixes another's
  # ("age" vs "age2") cannot claim the other's coefficients.
  by_len <- p$covs[order(nchar(vapply(p$covs, .logistic_term_label, character(1))),
                         decreasing = TRUE)]
  labeller <- function(key) {
    for (cl in by_len) {
      tl <- .logistic_term_label(cl)
      if (startsWith(key, tl)) {
        if (p$cov_types[[cl]] == "numeric") {
          k <- p$incr[[cl]]
          return(if (k == 1) sprintf("%s (per 1 unit)", cl) else sprintf("%s (per %g units)", cl, k))
        }
        return(sprintf("%s: %s", cl, substring(key, nchar(tl) + 1)))
      }
    }
    key
  }
  d <- data.frame(term = vapply(keys[keep], labeller, character(1)),
                  or = or[keep], lo = lo[keep], hi = hi[keep],
                  stringsAsFactors = FALSE)
  d$term <- factor(d$term, levels = rev(d$term))
  pal <- .km_palette(nrow(d))
  gg <- ggplot2::ggplot(d, ggplot2::aes(x = or, y = term, color = term)) +
    ggplot2::geom_vline(xintercept = 1, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), orientation = "y",
                           width = 0.2, linewidth = 0.6) +
    ggplot2::geom_point(size = 2.4) +
    ggplot2::scale_x_log10() +
    ggplot2::scale_color_manual(values = pal, guide = "none") +
    ggplot2::labs(x = "Adjusted odds ratio (log scale)", y = NULL) +
    .fig_theme("generic")
  .svg_string(gg, width = 6, height = 0.5 + 0.5 * nrow(d))
}

fig_logistic <- function(spec) {
  p <- .logistic_prep(spec)
  fits <- .logistic_fits(p$df, p$covs, p$cov_types)
  disp_rows <- .logistic_rows(p, fits)

  table_html <- .logistic_table_html(disp_rows)
  forest_svg <- .logistic_forest_svg(p, fits)
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s</div>",
                       table_html, forest_svg)

  tsv <- paste(c(paste(c("Characteristic", "Unadjusted OR (95% CI, p)",
                         "Adjusted OR (95% CI, p)"), collapse = "\t"),
                 vapply(disp_rows, function(r)
                   paste(c(trimws(r$term), r$unadj, r$adj), collapse = "\t"), character(1))),
               collapse = "\n")
  drop_note <- if (p$n_dropped > 0)
    sprintf(" %d row(s) with missing values were excluded.", p$n_dropped) else ""
  methods <- sprintf(paste0("Multivariable logistic regression (n = %d, %d events) ",
    "adjusted for %s. Unadjusted odds ratios are from single-covariate models; ",
    "adjusted odds ratios are from the joint model.%s"),
    p$n, p$n_event, paste(p$covs, collapse = ", "), drop_note)
  text <- paste0(tsv, "\n\n", methods)

  list(svg = svg_field, text = text, code = "")
}

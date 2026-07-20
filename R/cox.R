# R/cox.R
# Cox proportional-hazards regression: univariable (unadjusted) HR per covariate
# beside the joint-model adjusted HR (clinical "Table 3"), plus an adjusted-HR
# forest plot. PH assumption checked with cox.zph and reported non-blocking.
# Reuses survival (already loaded for KM); no extra package.

# Detect numeric vs categorical for one column (non-throwing; mirrors
# .gc_is_numeric_col). TRUE iff every non-blank cell parses as numeric.
.cox_is_numeric <- function(rows, colname) {
  raw <- .char_col(rows, colname)
  raw[!is.na(raw) & raw == ""] <- NA
  num <- suppressWarnings(as.numeric(raw))
  !any(!is.na(raw) & is.na(num))
}

# The term label R uses for a column inside a formula, and therefore the prefix of
# its coefficient names. .cox_fits writes every column backticked, so a syntactic
# name appears bare ("armTreated") while a non-syntactic one — a header with a
# space, routine in clinical CSV exports — keeps the backticks
# ("`study arm`Treated"). Mirrors .logistic_term_label.
.cox_term_label <- function(cl) {
  if (identical(make.names(cl), cl)) cl else sprintf("`%s`", cl)
}

# Most frequent non-NA value of a character vector (default reference level).
.cox_most_frequent <- function(x) {
  x <- x[!is.na(x) & x != ""]
  names(sort(table(x), decreasing = TRUE))[1]
}

# Build the complete-case working frame and covariate metadata.
.cox_prep <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  covs <- unlist(spec$roles$covariates %||% list())
  if (length(covs) == 0) stop("Select at least one covariate.")
  tcol <- spec$roles$time; scol <- spec$roles$status
  if (is.null(tcol) || is.null(scol)) stop("Choose a time column and a status column.")
  have <- names(rows[[1]])
  for (cl in c(tcol, scol, covs))
    if (!(cl %in% have)) stop(sprintf("Column '%s' not found in the data.", cl))

  time <- .numeric_col(rows, tcol)
  ev <- as.character(spec$options$event_value %||% "")
  status_raw <- .char_col(rows, scol)
  ev_num <- suppressWarnings(as.numeric(ev))
  status <- as.integer(status_raw == ev |
    (!is.na(ev_num) & !is.na(suppressWarnings(as.numeric(status_raw))) &
       suppressWarnings(as.numeric(status_raw)) == ev_num))
  status[is.na(status)] <- NA_integer_

  cov_types <- setNames(
    vapply(covs, function(cl) if (.cox_is_numeric(rows, cl)) "numeric" else "categorical",
           character(1)), covs)
  ref_levels <- spec$options$ref_levels %||% list()

  cols <- list(time = time, status = status)
  for (cl in covs) {
    if (cov_types[[cl]] == "numeric") cols[[cl]] <- .numeric_col(rows, cl)
    else {
      v <- .char_col(rows, cl); v[!is.na(v) & v == ""] <- NA
      cols[[cl]] <- v
    }
  }
  df <- as.data.frame(cols, stringsAsFactors = FALSE, check.names = FALSE)
  n_before <- nrow(df)
  df <- df[stats::complete.cases(df) & is.finite(df$time) & df$time >= 0, , drop = FALSE]
  n_dropped <- n_before - nrow(df)

  # Factor + relevel categoricals; default reference = most frequent level.
  for (cl in covs) if (cov_types[[cl]] == "categorical") {
    ref <- as.character(ref_levels[[cl]] %||% .cox_most_frequent(df[[cl]]))
    lv <- unique(df[[cl]])
    if (length(lv) < 2) stop(sprintf("Covariate '%s' has only one level after removing missing values.", cl))
    if (!ref %in% lv) ref <- .cox_most_frequent(df[[cl]])
    df[[cl]] <- stats::relevel(factor(df[[cl]]), ref = ref)
  }
  events <- sum(df$status == 1)
  if (events < 10) stop(sprintf("Too few events (%d) to fit a reliable Cox model; at least 10 are needed.", events))
  list(df = df, covs = covs, cov_types = cov_types, ref_levels = ref_levels,
       n = nrow(df), events = events, n_dropped = n_dropped)
}

# Fit one coxph, capturing (not suppressing) model-fit warnings so an unreliable
# HR can be flagged rather than shipped silently. muffleWarning keeps the warning
# off the WARN-0 gate. Bindings are explicit so nothing depends on the search path.
.cox_fit_one <- function(formula, df) {
  warn <- NULL
  fit <- withCallingHandlers(
    survival::coxph(formula, data = df),
    warning = function(w) { warn <<- conditionMessage(w); invokeRestart("muffleWarning") })
  list(fit = fit, warn = warn)
}

# Univariable coxph per covariate + one joint model.
.cox_fits <- function(df, covs, cov_types) {
  uni <- lapply(covs, function(cl)
    .cox_fit_one(stats::as.formula(sprintf("survival::Surv(time, status) ~ `%s`", cl)), df))
  names(uni) <- covs
  joint_f <- stats::as.formula(paste0("survival::Surv(time, status) ~ ",
    paste(sprintf("`%s`", covs), collapse = " + ")))
  joint <- .cox_fit_one(joint_f, df)
  list(uni = uni, joint = joint)
}

# Format one HR (95% CI, p); "not reliably estimated" when the fit warned or the
# interval fails the shared reliability rule (.ratio_reportable, R/dispatch.R).
# That rule is what .cox_forest_svg filters on too, so a hazard ratio the figure
# refuses to draw can never print here as though it were a finding.
.cox_hr_cell <- function(est, lo, hi, p, warn) {
  if (!is.null(warn) || !.ratio_reportable(est, lo, hi))
    return("not reliably estimated")
  pf <- if (p < 0.001) "p<0.001" else sprintf("p=%.3f", p)
  sprintf("%.2f (%.2f–%.2f, %s)", est, lo, hi, pf)
}

# One display row per covariate LEVEL (reference marked). Returns a list of
# list(term, unadj, adj) character cells. `term` leading with two spaces marks
# an indented level row.
.cox_rows <- function(p, fits) {
  rows <- list()
  jfit <- fits$joint$fit; jwarn <- fits$joint$warn
  jc <- stats::coef(jfit); jci <- suppressWarnings(stats::confint(jfit))
  # Index the coefficient matrix by [key, "Pr(>|z|)"] — subsetting a single-row
  # matrix to a bare column drops the names, so `pmat[, "Pr(>|z|)"][key]` is NA.
  jpm <- summary(jfit)$coefficients
  pval <- function(pmat, key) if (key %in% rownames(pmat)) pmat[key, "Pr(>|z|)"] else NA_real_
  for (cl in p$covs) {
    ufit <- fits$uni[[cl]]$fit; uwarn <- fits$uni[[cl]]$warn
    uc <- stats::coef(ufit); uci <- suppressWarnings(stats::confint(ufit))
    upm <- summary(ufit)$coefficients
    tl <- .cox_term_label(cl)
    if (p$cov_types[[cl]] == "numeric") {
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (per 1 unit)", cl),
        unadj = .cox_hr_cell(exp(uc[tl]), exp(uci[tl, 1]), exp(uci[tl, 2]), pval(upm, tl), uwarn),
        adj = .cox_hr_cell(exp(jc[tl]), exp(jci[tl, 1]), exp(jci[tl, 2]), pval(jpm, tl), jwarn))
    } else {
      lv <- levels(p$df[[cl]])
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (reference: %s)", cl, lv[1]),
        unadj = "", adj = "")
      for (l in lv[-1]) {
        key <- paste0(tl, l)
        rows[[length(rows) + 1]] <- list(term = paste0("  ", l),
          unadj = .cox_hr_cell(exp(uc[key]), exp(uci[key, 1]), exp(uci[key, 2]), pval(upm, key), uwarn),
          adj = .cox_hr_cell(exp(jc[key]), exp(jci[key, 1]), exp(jci[key, 2]), pval(jpm, key), jwarn))
      }
    }
  }
  rows
}

fig_cox <- function(spec) {
  p <- .cox_prep(spec)
  fits <- .cox_fits(p$df, p$covs, p$cov_types)
  disp_rows <- .cox_rows(p, fits)

  # PH assumption (non-blocking).
  zph <- tryCatch(survival::cox.zph(fits$joint$fit), error = function(e) NULL)
  gp <- if (!is.null(zph)) zph$table["GLOBAL", "p"] else NA_real_
  ph_line <- if (is.na(gp)) "" else {
    base <- sprintf(" The proportional-hazards assumption was assessed with scaled Schoenfeld residuals (global %s).",
                    if (gp < 0.001) "p<0.001" else sprintf("p=%.3f", gp))
    if (gp < 0.05)
      paste0(base, " CAUTION: the assumption may not hold (global p<0.05); consider stratification, a time-varying effect, or statistical review before interpreting these hazard ratios.")
    else base
  }
  n_terms <- sum(vapply(p$covs, function(cl)
    if (p$cov_types[[cl]] == "numeric") 1L else nlevels(p$df[[cl]]) - 1L, integer(1)))
  epv <- p$events / n_terms
  epv_line <- if (epv < 10)
    " CAUTION: fewer than 10 events per model term (EPV < 10); the adjusted estimates may be unstable." else ""

  # A cell that refuses to print a number needs a sentence saying why, or the
  # user is left reading "not reliably estimated" with nothing to act on. Both
  # columns are inspected: an UNADJUSTED cell can run away while the adjusted
  # one stays inside the bound (a crude effect that is explained away), and the
  # reverse happens too. Mirrors .logistic_or_cell's sibling advisory; both
  # causes are named because both trip the same rule.
  unrel_cell <- any(vapply(disp_rows, function(r)
    identical(r$adj, "not reliably estimated") ||
      identical(r$unadj, "not reliably estimated"), logical(1)))
  unrel_line <- if (unrel_cell)
    paste0(" CAUTION: separation or severe collinearity was detected — one or more ",
           "covariates either predict the event (near-)perfectly or duplicate ",
           "information already carried by another covariate, so those hazard ratios ",
           "are not reliably estimated by standard Cox regression and are omitted from ",
           "the forest plot. Consider collapsing sparse categories, dropping or ",
           "combining a redundant covariate, or rescaling one on a clinically ",
           "meaningful unit, and seek statistical review.") else ""

  table_html <- .cox_table_html(disp_rows)
  forest_svg <- .cox_forest_svg(p, fits)
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s</div>",
                       table_html, forest_svg)

  # text: TSV then methods sentence.
  tsv <- paste(c(paste(c("Characteristic", "Unadjusted HR (95% CI, p)",
                         "Adjusted HR (95% CI, p)"), collapse = "\t"),
                 vapply(disp_rows, function(r)
                   paste(c(trimws(r$term), r$unadj, r$adj), collapse = "\t"), character(1))),
               collapse = "\n")
  drop_note <- if (p$n_dropped > 0)
    sprintf(" %d row(s) with missing values were excluded.", p$n_dropped) else ""
  methods <- sprintf(paste0("Multivariable Cox proportional-hazards regression (n = %d, %d events) ",
    "adjusted for %s. Unadjusted hazard ratios are from single-covariate models; ",
    "adjusted hazard ratios are from the joint model.%s%s%s%s"),
    p$n, p$events, paste(p$covs, collapse = ", "), unrel_line, ph_line, epv_line,
    drop_note)
  text <- paste0(tsv, "\n\n", methods)

  list(svg = svg_field, text = text, code = .cox_script(spec, p, fits))
}

# HTML table (reuses .esc from R/summarize.R). A "(reference:" header row for a
# categorical block keeps blank effect cells; other blank cells read "1 (reference)".
.cox_table_html <- function(disp_rows) {
  header <- "<tr><th>Characteristic</th><th>Unadjusted HR (95% CI)</th><th>Adjusted HR (95% CI)</th></tr>"
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

# Forest plot of ADJUSTED HRs (one point per non-reference level / numeric term),
# log x-axis, dashed rule at HR = 1. geom_errorbar(orientation="y") — never
# geom_errorbarh; linewidth — never size. Inclusion mirrors .cox_hr_cell's
# reliability rule so the plot can never contradict the table beside it: a
# warned joint fit makes EVERY adjusted cell read "not reliably estimated"
# (the warning is model-level, so .cox_rows passes it to all of them), hence a
# warned fit plots nothing at all; and, as in .logistic_forest_svg, a CI that
# runs away in EITHER direction is dropped rather than flattening the shared
# log axis (.ratio_reportable, R/dispatch.R — the same rule .cox_hr_cell uses).
.cox_forest_svg <- function(p, fits) {
  if (!is.null(fits$joint$warn)) return("")
  jfit <- fits$joint$fit
  jc <- stats::coef(jfit); jci <- suppressWarnings(stats::confint(jfit))
  terms <- names(jc)
  keep <- .ratio_reportable(exp(jc), exp(jci[, 1]), exp(jci[, 2]))
  if (!any(keep)) return("")
  # Coefficient names carry the formula's term label, which is backticked for a
  # non-syntactic header ("`study arm`Treated"), so match and strip that prefix
  # literally — a bare-name regex would miss it and leak the raw coefficient name.
  # Longest term label first, so a covariate whose name prefixes another's
  # ("age" vs "age2") cannot claim the other's coefficients.
  by_len <- p$covs[order(nchar(vapply(p$covs, .cox_term_label, character(1))),
                         decreasing = TRUE)]
  labeller <- function(key) {
    for (cl in by_len) {
      tl <- .cox_term_label(cl)
      if (startsWith(key, tl)) {
        if (p$cov_types[[cl]] == "numeric") return(sprintf("%s (per 1 unit)", cl))
        return(sprintf("%s: %s", cl, substring(key, nchar(tl) + 1)))
      }
    }
    key
  }
  d <- data.frame(
    term = vapply(terms[keep], labeller, character(1)),
    hr = exp(jc[keep]), lo = exp(jci[keep, 1]), hi = exp(jci[keep, 2]),
    stringsAsFactors = FALSE)
  d$term <- factor(d$term, levels = rev(d$term))
  pal <- .km_palette(nrow(d))
  gg <- ggplot2::ggplot(d, ggplot2::aes(x = hr, y = term, color = term)) +
    ggplot2::geom_vline(xintercept = 1, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), orientation = "y",
                           width = 0.2, linewidth = 0.6) +
    ggplot2::geom_point(size = 2.4) +
    ggplot2::scale_x_log10() +
    ggplot2::scale_color_manual(values = pal, guide = "none") +
    ggplot2::labs(x = "Adjusted hazard ratio (log scale)", y = NULL) +
    .fig_theme("generic")
  # The browser width-fits this SVG (`#preview svg { max-width: 100% }`), so the
  # canvas proportion — not the point size — decides how large the type reads. A
  # short canvas is scaled up further and leaves less plot around the same 12pt
  # text. Grow with the term count, but never below the 3.6in floor, which keeps
  # a one- or two-term forest in the same proportion band as the other figures.
  # Kept in step with `.logistic_forest_svg`.
  .svg_string(gg, width = 6.5, height = max(3.6, 0.9 + 0.7 * nrow(d)))
}

# Downloadable R script: the exact univariable + joint coxph calls (deparsed),
# cox.zph, and an equivalent forest-plot ggplot. For uploads, prep reads the
# user's REAL column names + event coding (source_roles), exactly like .km_script.
.cox_script <- function(spec, p, fits) {
  opts <- spec$options %||% list()
  qe <- function(s) gsub('"', '\\\\"', s)
  covs <- p$covs
  sr <- if (nzchar(as.character(opts$source_filename %||% ""))) opts$source_roles else NULL
  ev <- qe(as.character(opts$event_value %||% ""))

  # Both the embedded-demo and upload cases read columns by their real names:
  # .script_data embeds columns named by roles (time/status/covariates), and an
  # upload's file has the user's original headers (carried in source_roles).
  time_name <- if (!is.null(sr)) sr$time else spec$roles$time
  status_name <- if (!is.null(sr)) sr$status else spec$roles$status
  tcol <- sprintf('df[["%s"]]', qe(time_name))
  scol_raw <- sprintf('df[["%s"]]', qe(status_name))
  cov_expr <- function(cl) sprintf('df[["%s"]]', qe(cl))

  prep <- c(
    sprintf('# Event coding: status == "%s" marks the event; all else censored.', ev),
    sprintf('status_raw <- %s', scol_raw),
    sprintf(paste0('status <- as.integer(as.character(status_raw) == "%s" | ',
                   '(!is.na(suppressWarnings(as.numeric("%s"))) & ',
                   '!is.na(suppressWarnings(as.numeric(status_raw))) & ',
                   'suppressWarnings(as.numeric(status_raw)) == suppressWarnings(as.numeric("%s"))))'),
            ev, ev, ev),
    sprintf('dat <- data.frame(time = as.numeric(%s), status = status,', tcol),
    paste0("                  ",
      paste(vapply(covs, function(cl) sprintf('`%s` = %s', qe(cl), cov_expr(cl)),
                   character(1)), collapse = ",\n                  "), ","),
    "                  check.names = FALSE, stringsAsFactors = FALSE)",
    "dat <- dat[complete.cases(dat) & is.finite(dat$time) & dat$time >= 0, ]")

  # levels(p$df[[cl]])[1] is the reference the app ACTUALLY fitted with, which is
  # not always options$ref_levels: .cox_prep falls back to the most frequent level
  # when the requested reference is absent from the complete-case data.
  relevel_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "categorical") return(NULL)
    sprintf('dat[["%s"]] <- relevel(factor(dat[["%s"]]), ref = "%s")',
            qe(cl), qe(cl), qe(levels(p$df[[cl]])[1]))
  }))

  uni_lines <- unlist(lapply(covs, function(cl) c(
    sprintf('# Unadjusted HR for %s', cl),
    sprintf('summary(coxph(Surv(time, status) ~ `%s`, data = dat))', qe(cl)), "")))
  joint_rhs <- paste(sprintf("`%s`", covs), collapse = " + ")
  joint_lines <- c(
    "# Adjusted (joint) model:",
    sprintf("fit <- coxph(Surv(time, status) ~ %s, data = dat)", joint_rhs),
    "summary(fit)", "",
    "# Proportional-hazards check:",
    "cox.zph(fit)", "")
  fig_lines <- c(
    "# Equivalent forest plot of the adjusted hazard ratios:",
    "library(ggplot2)",
    "co <- summary(fit)$conf.int",
    "fp <- data.frame(term = rownames(co), hr = co[, 1],",
    "                 lo = co[, 3], hi = co[, 4])",
    "fp$term <- factor(fp$term, levels = rev(fp$term))",
    "p_forest <- ggplot(fp, aes(hr, term)) +",
    '  geom_vline(xintercept = 1, linetype = "dashed", colour = "grey50") +',
    '  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0.2) +',
    "  geom_point(size = 2.4) + scale_x_log10() +",
    '  labs(x = "Adjusted hazard ratio (log scale)", y = NULL) +',
    "  theme_minimal(base_size = 12)",
    '# print(p_forest)')

  body <- c("library(survival)", "", prep, "",
            relevel_lines, if (length(relevel_lines)) "" else NULL,
            uni_lines, joint_lines, fig_lines)
  .script_assemble("Cox proportional-hazards regression", spec,
                   c(spec$roles$time, spec$roles$status, covs),
                   c("survival", "ggplot2"), body)
}

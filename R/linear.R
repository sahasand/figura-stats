# Continuous-outcome linear regression: univariable (unadjusted) coefficient per
# covariate beside the joint-model adjusted coefficient (clinical "Table 3").
# Base stats::lm only — no extra package. CIs are t-based (stats::confint).
#
# The covariate helpers are shared with R/logistic.R (.logistic_is_numeric,
# .logistic_term_label, .logistic_most_frequent, .logistic_increment,
# .logistic_vif): they are pure functions of their inputs and the rule is
# identical here, so they are called, not copied.

# Build the complete-case working frame and covariate metadata.
.linear_prep <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  covs <- unlist(spec$roles$covariates %||% list())
  if (length(covs) == 0) stop("Select at least one covariate.")
  ocol <- spec$roles$outcome
  if (is.null(ocol)) stop("Choose an outcome column.")
  have <- names(rows[[1]])
  for (cl in c(ocol, covs))
    if (!(cl %in% have)) stop(sprintf("Column '%s' not found in the data.", cl))
  # The outcome-specific message: .numeric_col's own wording names a "column",
  # which for the outcome role points the user at the wrong dropdown.
  if (!.logistic_is_numeric(rows, ocol))
    stop(sprintf("Outcome column '%s' must be numeric.", ocol))
  y <- .numeric_col(rows, ocol)

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

  # Sample size is checked before covariate structure: with too few rows every
  # downstream diagnosis is a symptom of the same problem.
  n_terms <- sum(vapply(covs, function(cl)
    if (cov_types[[cl]] == "numeric") 1L else max(0L, length(unique(df[[cl]])) - 1L),
    integer(1)))
  resid_df <- nrow(df) - 1L - n_terms
  if (resid_df < 10) stop(sprintf(paste0(
    "Too few observations (n = %d) for %d model term(s); at least 10 residual ",
    "degrees of freedom are needed."), nrow(df), n_terms))

  for (cl in covs) if (cov_types[[cl]] == "numeric" && incr[[cl]] != 1)
    df[[cl]] <- df[[cl]] / incr[[cl]]

  for (cl in covs) if (cov_types[[cl]] == "categorical") {
    ref <- as.character(ref_levels[[cl]] %||% .logistic_most_frequent(df[[cl]]))
    lv <- unique(df[[cl]])
    if (length(lv) < 2) stop(sprintf("Covariate '%s' has only one level after removing missing values.", cl))
    if (!ref %in% lv) ref <- .logistic_most_frequent(df[[cl]])
    df[[cl]] <- stats::relevel(factor(df[[cl]]), ref = ref)
  }
  if (stats::var(df$.y) == 0)
    stop("The outcome has no variation after removing missing values.")

  list(df = df, covs = covs, cov_types = cov_types, ref_levels = ref_levels,
       incr = incr, n = nrow(df), n_terms = n_terms, n_dropped = n_dropped,
       outcome_name = ocol)
}

# Fit one lm, capturing (not suppressing) fit warnings so an unclean fit can be
# flagged. muffleWarning keeps it off the WARN-0 gate.
.linear_fit_one <- function(formula, df) {
  warn <- NULL
  fit <- withCallingHandlers(
    stats::lm(formula, data = df),
    warning = function(w) { warn <<- conditionMessage(w); invokeRestart("muffleWarning") })
  list(fit = fit, warn = warn)
}

# Univariable lm per covariate + one joint model.
.linear_fits <- function(df, covs) {
  uni <- lapply(covs, function(cl)
    .linear_fit_one(stats::as.formula(sprintf(".y ~ `%s`", cl)), df))
  names(uni) <- covs
  joint_f <- stats::as.formula(paste0(".y ~ ",
    paste(sprintf("`%s`", covs), collapse = " + ")))
  list(uni = uni, joint = .linear_fit_one(joint_f, df))
}

# est / lo / hi / p per non-intercept coefficient, keyed by coefficient name.
# confint.lm is t-based (qt on the residual df). An aliased coefficient (a
# column that is a linear combination of others) is NA in coef() and confint()
# and absent from summary()'s matrix, so every field of it comes back NA.
.linear_terms <- function(fit) {
  cf <- stats::coef(fit)
  ci <- stats::confint(fit, level = 0.95)
  sm <- summary(fit)$coefficients
  keys <- setdiff(names(cf), "(Intercept)")
  out <- lapply(keys, function(k) list(
    est = unname(cf[k]), lo = unname(ci[k, 1]), hi = unname(ci[k, 2]),
    p = if (k %in% rownames(sm)) unname(sm[k, "Pr(>|t|)"]) else NA_real_))
  names(out) <- keys
  out
}

# Is a coefficient reportable? Finite estimate and finite bounds — there is no
# ratio-scale window here (.ratio_reportable is for HR/OR). Vectorised.
.coef_reportable <- function(est, lo, hi) is.finite(est) & is.finite(lo) & is.finite(hi)

.linear_pfmt <- function(p) if (p < 0.001) "p<0.001" else sprintf("p=%.3f", p)

# summary.lm's own "essentially perfect fit" test, evaluated BEFORE any summary()
# call so its warning can never fire (that warning would leak from
# .linear_terms, .linear_lead, .linear_bp and .logistic_vif — seven times on a
# y = x upload). A fit this exact has undefined standard errors and p-values,
# and it is always a data problem: a covariate that duplicates or derives from
# the outcome. Checking the joint model suffices — it nests every univariable
# model, so its residual sum of squares is the smallest of all of them.
.linear_perfect_fit <- function(fit) {
  r <- stats::resid(fit); f <- stats::fitted(fit)
  resvar <- sum(r^2) / fit$df.residual
  is.finite(resvar) && resvar < (mean(f)^2 + stats::var(c(f))) * 1e-30
}

# "%.2f (%.2f to %.2f, p)" — the word "to", because a coefficient can be
# negative and "-2.10–-0.36" is unreadable.
.linear_cell <- function(terms, key) {
  t <- terms[[key]]
  if (is.null(t) || !.coef_reportable(t$est, t$lo, t$hi) || !is.finite(t$p))
    return("not reliably estimated")
  sprintf("%.2f (%.2f to %.2f, %s)", t$est, t$lo, t$hi, .linear_pfmt(t$p))
}

# One display row per covariate LEVEL (reference marked); numeric rows label
# the increment. A term leading with two spaces marks an indented level row.
.linear_rows <- function(p, fits) {
  rows <- list()
  jt <- .linear_terms(fits$joint$fit)
  for (cl in p$covs) {
    ut <- .linear_terms(fits$uni[[cl]]$fit)
    tl <- .logistic_term_label(cl)
    if (p$cov_types[[cl]] == "numeric") {
      k <- p$incr[[cl]]
      unit <- if (k == 1) "per 1 unit" else sprintf("per %g units", k)
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (%s)", cl, unit),
        unadj = .linear_cell(ut, tl), adj = .linear_cell(jt, tl))
    } else {
      lv <- levels(p$df[[cl]])
      rows[[length(rows) + 1]] <- list(term = sprintf("%s (reference: %s)", cl, lv[1]),
        unadj = "", adj = "")
      for (l in lv[-1]) {
        key <- paste0(tl, l)
        rows[[length(rows) + 1]] <- list(term = paste0("  ", l),
          unadj = .linear_cell(ut, key), adj = .linear_cell(jt, key))
      }
    }
  }
  rows
}

# HTML table (reuses .esc). The "(reference: X)" header row is where a reader
# looks for the reference level's effect, so its two effect cells read
# "0 (reference)" — the null of a difference is 0 — in the HTML ONLY. The TSV
# keeps them blank: the validation parser (stats-validation/compare/compare.py,
# parse_ratio_tsv) requires a reference header row to carry empty cells, and
# every level row below it always carries a real cell.
.linear_table_html <- function(disp_rows) {
  header <- "<tr><th>Characteristic</th><th>Unadjusted β (95% CI, p)</th><th>Adjusted β (95% CI, p)</th></tr>"
  body <- vapply(disp_rows, function(r) {
    is_header <- grepl("\\(reference:", r$term)
    indent <- startsWith(r$term, "  ")
    label <- .esc(trimws(r$term))
    if (indent) label <- paste0("<span class=\"lvl\">", label, "</span>")
    if (is_header) { unadj <- "0 (reference)"; adj <- "0 (reference)" }
    else { unadj <- .esc(r$unadj); adj <- .esc(r$adj) }
    sprintf("<tr><td>%s</td><td>%s</td><td>%s</td></tr>", label, unadj, adj)
  }, character(1))
  paste0("<table class=\"table1\"><thead>", header, "</thead><tbody>",
         paste(body, collapse = ""), "</tbody></table>")
}

# The methods paragraph's opening sentence. With a single covariate there is no
# joint model: saying "adjusted for" there would be false in a sentence built
# to be pasted into a manuscript.
.linear_lead <- function(spec, p, jfit) {
  s <- summary(jfit)
  r2 <- sprintf("(R² = %.3f, adjusted R² = %.3f)", s$r.squared, s$adj.r.squared)
  ocol <- spec$roles$outcome
  if (length(p$covs) == 1)
    sprintf(paste0("Univariable linear regression (n = %d) of %s with %s as the only ",
                   "covariate. No adjustment was made for other variables, so the ",
                   "unadjusted and adjusted columns report the same model %s."),
            p$n, ocol, p$covs[[1]], r2)
  else
    sprintf(paste0("Multivariable linear regression (n = %d) of %s adjusted for %s. ",
                   "Unadjusted coefficients are from single-covariate models; adjusted ",
                   "coefficients are from the joint model %s."),
            p$n, ocol, paste(p$covs, collapse = ", "), r2)
}

# Advisory for any captured lm warning. Returns "" when there is nothing to
# say. Advisory only — it never gates a fit or changes a number.
.linear_other_warn <- function(warns) {
  w <- unlist(warns, use.names = FALSE)
  w <- w[!is.na(w) & nzchar(w)]
  if (length(w) == 0) return("")
  sprintf(paste0(" CAUTION: fitting reported a numerical warning (\"%s\"); the ",
                 "coefficients above may come from a model that did not fit cleanly. ",
                 "Check the covariates for extreme values, and seek statistical review."),
          w[[1]])
}

# Koenker's studentized Breusch-Pagan, hand-rolled: regress the squared residuals
# on the fitted values; LM = n * R^2 of that auxiliary fit; chi-square on 1 df.
# Base stats only (no lmtest).
.linear_bp <- function(fit) {
  r2 <- stats::resid(fit)^2
  fv <- stats::fitted(fit)
  aux <- stats::lm(r2 ~ fv)
  lm_stat <- length(r2) * summary(aux)$r.squared
  list(statistic = lm_stat, p = stats::pchisq(lm_stat, df = 1, lower.tail = FALSE))
}

# Shapiro-Wilk on the residuals, in its supported size window only. NULL means
# "not assessed" (n outside [3, 5000]) or the test could not run (identical
# residuals) — never a stop.
.linear_shapiro <- function(fit) {
  r <- stats::resid(fit)
  if (length(r) < 3 || length(r) > 5000) return(NULL)
  tryCatch(stats::shapiro.test(r)$p.value, error = function(e) NULL)
}

# Forest plot of ADJUSTED coefficients (one point per non-reference level /
# numeric term), linear x-axis, dashed rule at 0. Inclusion mirrors .linear_cell
# exactly (both use .coef_reportable), so the table and the plot can never
# disagree about which terms carry usable information.
.linear_forest_svg <- function(p, fits) {
  jt <- .linear_terms(fits$joint$fit)
  keys <- names(jt)
  if (length(keys) == 0) return("")
  est <- vapply(jt, `[[`, numeric(1), "est")
  lo <- vapply(jt, `[[`, numeric(1), "lo")
  hi <- vapply(jt, `[[`, numeric(1), "hi")
  keep <- .coef_reportable(est, lo, hi)
  if (!any(keep)) return("")
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
                  est = est[keep], lo = lo[keep], hi = hi[keep],
                  stringsAsFactors = FALSE)
  d$term <- factor(d$term, levels = rev(d$term))
  pal <- .km_palette(nrow(d))
  gg <- ggplot2::ggplot(d, ggplot2::aes(x = est, y = term, color = term)) +
    ggplot2::geom_vline(xintercept = 0, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lo, xmax = hi), orientation = "y",
                           width = 0.2, linewidth = 0.6) +
    ggplot2::geom_point(size = 2.4) +
    ggplot2::scale_color_manual(values = pal, guide = "none") +
    ggplot2::labs(x = sprintf("Adjusted coefficient (difference in %s)", p$outcome_name),
                  y = NULL) +
    .fig_theme("generic")
  .svg_string(gg, width = 6.5, height = max(3.6, 0.9 + 0.7 * nrow(d)))
}

# Residuals vs fitted and a normal Q-Q of the residuals, always from the JOINT
# model. Two separate SVGs (no cowplot). No loess smoother: a geom_smooth on a
# small n warns, and the reader wants the raw scatter.
.linear_diagnostics_svg <- function(jfit) {
  d <- data.frame(fitted = stats::fitted(jfit), resid = stats::resid(jfit))
  col <- .km_palette(1)
  g1 <- ggplot2::ggplot(d, ggplot2::aes(x = fitted, y = resid)) +
    ggplot2::geom_hline(yintercept = 0, linetype = "dashed", linewidth = 0.5,
                        colour = "grey50") +
    ggplot2::geom_point(size = 1.8, alpha = 0.7, colour = col) +
    ggplot2::labs(x = "Fitted values", y = "Residuals",
                  caption = "Healthy: points scattered evenly around 0, with no funnel or curve.") +
    .fig_theme("generic")
  g2 <- ggplot2::ggplot(d, ggplot2::aes(sample = resid)) +
    ggplot2::stat_qq_line(linewidth = 0.5, colour = "grey50") +
    ggplot2::stat_qq(size = 1.8, alpha = 0.7, colour = col) +
    ggplot2::labs(x = "Theoretical quantiles", y = "Residual quantiles",
                  caption = "Healthy: points along the line.") +
    .fig_theme("generic")
  paste0(.svg_string(g1, width = 6.5, height = 4.5),
         .svg_string(g2, width = 6.5, height = 4.5))
}

# Downloadable R script: the univariable + joint lm calls, the residual
# diagnostics the app reported, and an equivalent forest plot. The prep block
# reproduces .linear_prep's pipeline in the SAME order (numeric coercion ->
# complete cases -> increment rescale -> relevel), so the script's coefficients
# match the app's table. For uploads, prep reads the user's REAL column names
# (source_roles), exactly like .logistic_script.
.linear_script <- function(spec, p, fits) {
  opts <- spec$options %||% list()
  qe <- function(s) gsub('"', '\\\\"', s)
  covs <- p$covs
  sr <- if (nzchar(as.character(opts$source_filename %||% ""))) opts$source_roles else NULL
  outcome_name <- if (!is.null(sr)) sr$outcome else spec$roles$outcome
  cov_expr <- function(cl) {
    e <- sprintf('df[["%s"]]', qe(cl))
    if (p$cov_types[[cl]] == "numeric") sprintf("as.numeric(%s)", e) else e
  }
  prep <- c(
    sprintf('dat <- data.frame(.y = as.numeric(df[["%s"]]),', qe(outcome_name)),
    paste0("                  ",
      paste(vapply(covs, function(cl) sprintf('`%s` = %s', qe(cl), cov_expr(cl)),
                   character(1)), collapse = ",\n                  "), ","),
    "                  check.names = FALSE, stringsAsFactors = FALSE)",
    "dat <- dat[complete.cases(dat), ]")
  incr_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "numeric" || p$incr[[cl]] == 1) return(NULL)
    sprintf('dat[["%s"]] <- dat[["%s"]] / %g   # coefficient per %g units',
            qe(cl), qe(cl), p$incr[[cl]], p$incr[[cl]])
  }))
  relevel_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "categorical") return(NULL)
    sprintf('dat[["%s"]] <- relevel(factor(dat[["%s"]]), ref = "%s")',
            qe(cl), qe(cl), qe(levels(p$df[[cl]])[1]))
  }))
  uni_lines <- unlist(lapply(covs, function(cl) c(
    sprintf('# Unadjusted coefficient for %s', cl),
    sprintf('m_uni <- lm(.y ~ `%s`, data = dat)', qe(cl)),
    "summary(m_uni)",
    "cbind(beta = coef(m_uni), confint(m_uni))   # t-based 95% CI",
    "")))
  joint_rhs <- paste(sprintf("`%s`", covs), collapse = " + ")
  joint_lines <- c(
    "# Adjusted (joint) model:",
    sprintf("fit <- lm(.y ~ %s, data = dat)", joint_rhs),
    "summary(fit)                                  # coefficients, R-squared, adjusted R-squared",
    "cbind(beta = coef(fit), confint(fit))         # adjusted coefficients + t-based 95% CI", "",
    "# Residual diagnostics the app reported:",
    "if (nrow(dat) >= 3 && nrow(dat) <= 5000) shapiro.test(resid(fit))   # residual normality; the app skips it outside this range, and so must the script",
    "aux <- lm(resid(fit)^2 ~ fitted(fit))         # Breusch-Pagan (Koenker): n * R^2 of squared residuals on fitted values",
    "bp <- nrow(dat) * summary(aux)$r.squared",
    "pchisq(bp, df = 1, lower.tail = FALSE)",
    "cooks.distance(fit)                           # influential observations (> 4/n flagged in the app)",
    "# plot(fit, which = 1:2)                      # residuals vs fitted; normal Q-Q", "")
  fig_lines <- c(
    "# Equivalent forest plot of the adjusted coefficients:",
    "library(ggplot2)",
    "co <- cbind(coef(fit), confint(fit))[-1, , drop = FALSE]",
    "fp <- data.frame(term = rownames(co), est = co[, 1], lo = co[, 2], hi = co[, 3])",
    "fp <- fp[is.finite(fp$est), ]",
    "fp$term <- factor(fp$term, levels = rev(fp$term))",
    "p_forest <- ggplot(fp, aes(est, term)) +",
    '  geom_vline(xintercept = 0, linetype = "dashed", colour = "grey50") +',
    '  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0.2) +',
    "  geom_point(size = 2.4) +",
    '  labs(x = "Adjusted coefficient", y = NULL) +',
    "  theme_minimal(base_size = 12)",
    '# print(p_forest)')
  body <- c(prep, "",
            incr_lines, if (length(incr_lines)) "" else NULL,
            relevel_lines, if (length(relevel_lines)) "" else NULL,
            uni_lines, joint_lines, fig_lines)
  .script_assemble("Linear regression", spec, c(spec$roles$outcome, covs), c("ggplot2"), body)
}

fig_linear <- function(spec) {
  p <- .linear_prep(spec)
  fits <- .linear_fits(p$df, p$covs)
  if (.linear_perfect_fit(fits$joint$fit)) stop(paste0(
    "The outcome is an exact function of the covariates (a perfect fit), so standard ",
    "errors and p-values are undefined; check for a covariate that duplicates or ",
    "derives from the outcome."))
  disp_rows <- .linear_rows(p, fits)
  jfit <- fits$joint$fit

  # ---- Model-quality advisories. Every one appends a sentence to the methods
  # text and never blocks a fit or changes a number.
  jt <- .linear_terms(jfit)
  aliased <- any(vapply(jt, function(t) is.na(t$est), logical(1)))
  aliased_line <- if (aliased)
    paste0(" CAUTION: one or more covariates were dropped from the adjusted model ",
           "because they are linear combinations of others (their cells read ",
           "\"not reliably estimated\"); remove a redundant variable.") else ""

  other_warn_line <- .linear_other_warn(
    c(list(fits$joint$warn), lapply(fits$uni, function(f) f$warn)))

  opt <- p$n / p$n_terms
  opt_line <- if (opt < 10)
    sprintf(paste0(" CAUTION: about %.1f observations per model term (fewer than 10); ",
                   "the adjusted estimates may be unstable and are best treated as ",
                   "exploratory."), opt) else ""

  sw_p <- .linear_shapiro(jfit)
  sw_line <- if (!is.null(sw_p) && sw_p < 0.05)
    # Conditional guidance, not a verdict: n alone does not validate an interval,
    # so the large-n tail defers to the variance and influence checks below.
    sprintf(" Residuals depart from normality (Shapiro–Wilk %s); with n = %d %s.",
            .linear_pfmt(sw_p), p$n,
            if (p$n >= 30) paste0("the coefficient estimates are unaffected, and the confidence intervals are usually robust to this unless the residual plots also show non-constant variance or influential points")
            else "the confidence intervals may be unreliable; consider transforming the outcome or a non-parametric comparison")
    else ""

  bp <- .linear_bp(jfit)
  bp_line <- if (is.finite(bp$p) && bp$p < 0.05)
    sprintf(paste0(" CAUTION: residual variance is not constant across fitted values ",
                   "(Breusch–Pagan %s); the standard errors may be misleading, and robust ",
                   "standard errors or an outcome transform are worth considering."),
            .linear_pfmt(bp$p)) else ""

  num_covs <- names(p$cov_types)[p$cov_types == "numeric"]
  vif <- .logistic_vif(p$df, num_covs)
  vif_line <- if (!is.null(vif) && any(vif > 5)) {
    largest <- if (any(!is.finite(vif))) "effectively infinite" else sprintf("%.1f", max(vif))
    sprintf(paste0(" CAUTION: multicollinearity among continuous covariates ",
                   "(largest VIF = %s, above the usual threshold of 5); consider dropping ",
                   "a redundant variable."), largest)
  } else ""

  cd <- stats::cooks.distance(jfit)
  n_infl <- sum(cd > 4 / length(cd), na.rm = TRUE)
  infl_line <- if (n_infl > 0)
    sprintf(paste0(" %d observation(s) were flagged as influential (Cook's distance > 4/n); ",
                   "inspect them for data-entry errors."), n_infl) else ""

  table_html <- .linear_table_html(disp_rows)
  forest_svg <- .linear_forest_svg(p, fits)
  diag_svg <- .linear_diagnostics_svg(jfit)
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s%s</div>",
                       table_html, forest_svg, diag_svg)
  tsv <- paste(c(paste(c("Characteristic", "Unadjusted β (95% CI, p)",
                         "Adjusted β (95% CI, p)"), collapse = "\t"),
                 vapply(disp_rows, function(r)
                   paste(c(trimws(r$term), r$unadj, r$adj), collapse = "\t"), character(1))),
               collapse = "\n")
  drop_note <- if (p$n_dropped > 0)
    sprintf(" %d row(s) with missing values were excluded.", p$n_dropped) else ""
  methods <- paste0(.linear_lead(spec, p, jfit), aliased_line, other_warn_line, opt_line,
                    sw_line, bp_line, vif_line, infl_line, drop_note)
  text <- .with_citation(paste0(tsv, "\n\n", methods), "ggplot2")
  list(svg = svg_field, text = text, code = .linear_script(spec, p, fits))
}

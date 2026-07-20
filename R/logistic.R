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

# Advisory for any captured glm warning that is NOT the recognized separation
# signal ("fitted probabilities numerically 0 or 1"), which has its own dedicated
# sentence. Without this, a warning such as "glm.fit: algorithm did not converge"
# would be captured, muffled, and then silently discarded, leaving the user with
# odds ratios from a bad fit and no caution at all. Returns "" when there is
# nothing to say. Advisory only — it never gates a fit or changes a number.
.logistic_other_warn <- function(warns) {
  w <- unlist(warns, use.names = FALSE)
  w <- w[!is.na(w) & nzchar(w) & !grepl("fitted probabilities", w)]
  if (length(w) == 0) return("")
  sprintf(paste0(" CAUTION: fitting reported a numerical warning (\"%s\"); the odds ",
                 "ratios above may come from a model that did not fit cleanly. Check ",
                 "the covariates for sparse categories or extreme values, and seek ",
                 "statistical review."), w[[1]])
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
  # The browser width-fits this SVG (`#preview svg { max-width: 100% }`), so the
  # canvas proportion — not the point size — decides how large the type reads. A
  # short canvas is scaled up further and leaves less plot around the same 12pt
  # text. Grow with the term count, but never below the 3.6in floor, which keeps
  # a one- or two-term forest in the same proportion band as the other figures.
  .svg_string(gg, width = 6.5, height = max(3.6, 0.9 + 0.7 * nrow(d)))
}

# C-statistic (AUC) == normalized Mann-Whitney U from fitted probabilities.
# Base stats only; rank() midranks handle ties. NA if a class is empty.
.logistic_auc <- function(prob, y) {
  n1 <- sum(y == 1); n0 <- sum(y == 0)
  if (n1 == 0 || n0 == 0) return(NA_real_)
  (sum(rank(prob)[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}

# VIF per CONTINUOUS predictor via base lm: VIF_j = 1/(1 - R^2_j), R^2_j from
# regressing predictor j on the other continuous predictors. Valid only for
# single-df (continuous) terms — categorical collinearity (which needs GVIF) is
# not assessed. NULL when fewer than 2 continuous covariates.
.logistic_vif <- function(df, num_covs) {
  if (length(num_covs) < 2) return(NULL)
  vapply(num_covs, function(v) {
    others <- setdiff(num_covs, v)
    f <- stats::as.formula(sprintf("`%s` ~ %s", v,
      paste(sprintf("`%s`", others), collapse = " + ")))
    lmfit <- stats::lm(f, data = df)
    # An exactly-duplicated covariate makes summary.lm emit "essentially perfect
    # fit"; that is precisely the case the r2 >= 1 branch below reports, so muffle
    # that one library-internal message. Anything else is re-raised untouched — a
    # blanket muffle here would hide future regressions from the WARN-0 gate. The
    # handler wraps summary() only, so lm() itself can never be silenced.
    r2 <- withCallingHandlers(summary(lmfit)$r.squared,
      warning = function(w) {
        if (grepl("essentially perfect fit", conditionMessage(w), fixed = TRUE))
          invokeRestart("muffleWarning")
      })
    if (!is.finite(r2) || r2 >= 1) Inf else 1 / (1 - r2)
  }, numeric(1))
}

# Downloadable R script: the univariable + joint glm calls, the C-statistic, and
# an equivalent forest plot. The prep block reproduces .logistic_prep's pipeline
# in the SAME order (recode -> complete cases -> increment rescale -> relevel),
# so the script's odds ratios match the app's table. For uploads, prep reads the
# user's REAL column names + event coding (source_roles), exactly like .cox_script.
.logistic_script <- function(spec, p, fits) {
  opts <- spec$options %||% list()
  qe <- function(s) gsub('"', '\\\\"', s)
  covs <- p$covs
  sr <- if (nzchar(as.character(opts$source_filename %||% ""))) opts$source_roles else NULL
  ev <- qe(as.character(opts$event_value %||% ""))
  # Embedded-demo data is written out under the role column names; an upload's
  # file carries the user's original headers (travelling in source_roles).
  outcome_name <- if (!is.null(sr)) sr$outcome else spec$roles$outcome
  ocol_raw <- sprintf('df[["%s"]]', qe(outcome_name))
  # as.numeric mirrors .numeric_col: a numeric column read back from a CSV with
  # blank cells arrives as character, and the increment divide below needs numeric.
  cov_expr <- function(cl) {
    e <- sprintf('df[["%s"]]', qe(cl))
    if (p$cov_types[[cl]] == "numeric") sprintf("as.numeric(%s)", e) else e
  }

  prep <- c(
    sprintf('# Event coding: outcome == "%s" is the event (y = 1); all else y = 0.', ev),
    sprintf('outcome_raw <- %s', ocol_raw),
    sprintf(paste0('y <- as.integer(as.character(outcome_raw) == "%s" | ',
                   '(!is.na(suppressWarnings(as.numeric("%s"))) & ',
                   '!is.na(suppressWarnings(as.numeric(outcome_raw))) & ',
                   'suppressWarnings(as.numeric(outcome_raw)) == suppressWarnings(as.numeric("%s"))))'),
            ev, ev, ev),
    'dat <- data.frame(.y = y,',
    paste0("                  ",
      paste(vapply(covs, function(cl) sprintf('`%s` = %s', qe(cl), cov_expr(cl)),
                   character(1)), collapse = ",\n                  "), ","),
    "                  check.names = FALSE, stringsAsFactors = FALSE)",
    "dat <- dat[complete.cases(dat), ]")

  incr_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "numeric" || p$incr[[cl]] == 1) return(NULL)
    sprintf('dat[["%s"]] <- dat[["%s"]] / %g   # per-%g-unit odds ratio',
            qe(cl), qe(cl), p$incr[[cl]], p$incr[[cl]])
  }))

  # levels(p$df[[cl]])[1] is the reference the app ACTUALLY fitted with, which is
  # not always options$ref_levels: .logistic_prep falls back to the most frequent
  # level when the requested reference is absent from the complete-case data.
  relevel_lines <- unlist(lapply(covs, function(cl) {
    if (p$cov_types[[cl]] != "categorical") return(NULL)
    sprintf('dat[["%s"]] <- relevel(factor(dat[["%s"]]), ref = "%s")',
            qe(cl), qe(cl), qe(levels(p$df[[cl]])[1]))
  }))

  uni_lines <- unlist(lapply(covs, function(cl) c(
    sprintf('# Unadjusted OR for %s', cl),
    sprintf('m_uni <- glm(.y ~ `%s`, family = binomial, data = dat)', qe(cl)),
    "summary(m_uni)",
    "exp(cbind(OR = coef(m_uni), confint.default(m_uni)))   # Wald 95% CI",
    "")))
  joint_rhs <- paste(sprintf("`%s`", covs), collapse = " + ")
  joint_lines <- c(
    "# Adjusted (joint) model:",
    sprintf("fit <- glm(.y ~ %s, family = binomial, data = dat)", joint_rhs),
    "summary(fit)",
    "exp(cbind(OR = coef(fit), confint.default(fit)))   # adjusted ORs + Wald 95% CI", "",
    "# Overall discrimination (C-statistic):",
    "prob <- fitted(fit); n1 <- sum(dat$.y == 1); n0 <- sum(dat$.y == 0)",
    "(sum(rank(prob)[dat$.y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)", "")
  fig_lines <- c(
    "# Equivalent forest plot of the adjusted odds ratios:",
    "library(ggplot2)",
    "co <- exp(cbind(coef(fit), confint.default(fit)))[-1, , drop = FALSE]",
    "fp <- data.frame(term = rownames(co), or = co[, 1], lo = co[, 2], hi = co[, 3])",
    "fp$term <- factor(fp$term, levels = rev(fp$term))",
    "p_forest <- ggplot(fp, aes(or, term)) +",
    '  geom_vline(xintercept = 1, linetype = "dashed", colour = "grey50") +',
    '  geom_errorbar(aes(xmin = lo, xmax = hi), orientation = "y", width = 0.2) +',
    "  geom_point(size = 2.4) + scale_x_log10() +",
    '  labs(x = "Adjusted odds ratio (log scale)", y = NULL) +',
    "  theme_minimal(base_size = 12)",
    '# print(p_forest)')

  body <- c(prep, "",
            incr_lines, if (length(incr_lines)) "" else NULL,
            relevel_lines, if (length(relevel_lines)) "" else NULL,
            uni_lines, joint_lines, fig_lines)
  .script_assemble("Logistic regression", spec,
                   c(spec$roles$outcome, covs), c("ggplot2"), body)
}

fig_logistic <- function(spec) {
  p <- .logistic_prep(spec)
  fits <- .logistic_fits(p$df, p$covs, p$cov_types)
  disp_rows <- .logistic_rows(p, fits)

  # ---- Model-quality guards. Every one of these is advisory: it appends a
  # sentence to the methods text and never blocks a fit or changes a number.
  jfit <- fits$joint$fit

  # Separation: glm's captured "fitted probabilities 0/1" warning, or any adjusted
  # OR that blew past the reliability threshold. Flagged, never auto-corrected.
  sep_warn <- !is.null(fits$joint$warn) && grepl("fitted probabilities", fits$joint$warn)
  # Both columns are inspected: an UNADJUSTED cell can blow past the reliability
  # threshold while the adjusted one stays finite (a covariate whose crude effect is
  # explained away), and that cell would otherwise appear in the table with no
  # explanatory sentence anywhere in the methods text.
  sep_cell <- any(vapply(disp_rows, function(r)
    identical(r$adj, "not reliably estimated") ||
      identical(r$unadj, "not reliably estimated"), logical(1)))
  # Both causes are named because both can trip this rule: a covariate that predicts
  # the outcome (near-)perfectly, and one that duplicates another covariate — the
  # latter blows the CI past the same threshold without any separation at all.
  sep_line <- if (sep_warn || sep_cell)
    paste0(" CAUTION: separation or severe collinearity was detected — one or more ",
           "covariates either predict the outcome (near-)perfectly or duplicate ",
           "information already carried by another covariate, so those odds ratios are ",
           "not reliably estimated by standard logistic regression. Consider collapsing ",
           "sparse categories, dropping or combining a redundant variable, or a penalized ",
           "(Firth) fit, and seek statistical review.") else ""

  # Fallback advisory for any captured fit warning (joint model or any univariable
  # one) that no other caution already explains. Separation frequently surfaces as
  # "glm.fit: algorithm did not converge" rather than the fitted-probabilities
  # message, so when the separation sentence is already being printed it covers the
  # warning and this stays quiet; otherwise the warning would be muffled and then
  # thrown away, leaving an unconverged fit's odds ratios with no caution at all.
  other_warn_line <- if (nzchar(sep_line)) "" else .logistic_other_warn(
    c(list(fits$joint$warn), lapply(fits$uni, function(f) f$warn)))

  # EPV (events per variable): soft advisory heuristic, never a gate.
  n_terms <- sum(vapply(p$covs, function(cl)
    if (p$cov_types[[cl]] == "numeric") 1L else nlevels(p$df[[cl]]) - 1L, integer(1)))
  epv <- p$n_min / n_terms
  epv_line <- if (epv < 10)
    sprintf(paste0(" CAUTION: about %.1f events per model term (EPV < 10); the adjusted ",
                   "estimates may be unstable and are best treated as exploratory."), epv) else ""

  # Discrimination: one overall C-statistic (base-R AUC), not per covariate.
  auc <- .logistic_auc(stats::fitted(jfit), p$df$.y)
  auc_line <- if (is.finite(auc))
    # "apparent" because it is measured on the same rows the model was fitted to,
    # with no split-sample or bootstrap correction — it is optimistically biased.
    sprintf(" Overall model discrimination: apparent (in-sample) C-statistic = %.2f.",
            auc) else ""

  # Multicollinearity: VIF for continuous predictors only.
  num_covs <- names(p$cov_types)[p$cov_types == "numeric"]
  vif <- .logistic_vif(p$df, num_covs)
  vif_line <- if (!is.null(vif) && any(vif > 5)) {
    # An exactly-duplicated covariate gives R^2 = 1, so a VIF can be infinite; say so
    # in words rather than printing "Inf". Keyed off the presence of a non-finite VIF,
    # not off the absence of finite ones: with a third, independent covariate a finite
    # VIF of ~1.0 also exists, and reporting it would read "largest VIF = 1.0, above
    # the usual threshold of 5".
    largest <- if (any(!is.finite(vif))) "effectively infinite"
      else sprintf("%.1f", max(vif))
    sprintf(paste0(" CAUTION: multicollinearity among continuous covariates ",
                   "(largest VIF = %s, above the usual threshold of 5); consider dropping ",
                   "a redundant variable."), largest)
  } else ""

  # Influential observations: Cook's distance above the conventional 4/n cut-off.
  cd <- stats::cooks.distance(jfit)
  n_infl <- sum(cd > 4 / length(cd), na.rm = TRUE)
  infl_line <- if (n_infl > 0)
    sprintf(paste0(" %d observation(s) were flagged as influential (Cook's distance > 4/n); ",
                   "inspect them for data-entry errors."), n_infl) else ""

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
  # With a single covariate there is no joint model to speak of: the fit is
  # univariable, nothing is adjusted for, and the two table columns are the same
  # model. Claiming "multivariable ... adjusted for X" there would be false in a
  # sentence built to be pasted into a manuscript.
  lead <- if (length(p$covs) == 1)
    sprintf(paste0("Univariable logistic regression (n = %d, %d events) with %s as the ",
                   "only covariate. No adjustment was made for other variables, so the ",
                   "unadjusted and adjusted columns report the same model."),
            p$n, p$n_event, p$covs[[1]])
  else
    sprintf(paste0("Multivariable logistic regression (n = %d, %d events) adjusted for ",
                   "%s. Unadjusted odds ratios are from single-covariate models; ",
                   "adjusted odds ratios are from the joint model."),
            p$n, p$n_event, paste(p$covs, collapse = ", "))
  methods <- paste0(lead, sep_line, other_warn_line, epv_line, auc_line, vif_line,
                    infl_line, drop_note)
  text <- paste0(tsv, "\n\n", methods)

  list(svg = svg_field, text = text, code = .logistic_script(spec, p, fits))
}

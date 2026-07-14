#' Kaplan-Meier curve + log-rank p (+ Cox HR when exactly two groups).
fig_km <- function(spec) {
  rows <- spec$data
  if (length(rows) < 2) stop("KM needs at least two rows.")
  df <- data.frame(
    time   = vapply(rows, function(r) as.numeric(r$time), numeric(1)),
    status = vapply(rows, function(r) as.integer(r$status), integer(1)),
    group  = vapply(rows, function(r) as.character(r$group), character(1)),
    stringsAsFactors = FALSE)
  if (!all(df$status %in% c(0L, 1L))) stop("status must be 0 (censored) or 1 (event).")
  if (any(!is.finite(df$time)) || any(df$time < 0))
    stop("KM: 'time' must be non-negative and numeric for every row.")

  fit <- survival::survfit(survival::Surv(time, status) ~ group, data = df)
  lr  <- survival::survdiff(survival::Surv(time, status) ~ group, data = df)
  p   <- 1 - stats::pchisq(lr$chisq, length(lr$n) - 1)
  time_label <- spec$options$time_label %||% "Time"

  # Report a p-value without the impossible-looking "p = 0.000": show
  # "p < 0.001" below three-decimal resolution, otherwise three decimals.
  fmt_p <- function(p) if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)

  # survminer::ggsurvplot emits its own internal deprecation/aesthetic warnings
  # (originating inside survminer/ggpubr, not this code). Wrap ONLY the plot
  # construction in suppressWarnings so the WARN-0 test gate holds. The stats
  # calls above (survfit/survdiff) and coxph below are NOT wrapped.
  gg <- suppressWarnings(
    survminer::ggsurvplot(fit, data = df, risk.table = TRUE,
                          xlab = time_label, ylab = "Survival probability",
                          legend.title = "Group"))
  plot_obj <- gg$plot
  plot_obj <- plot_obj + .fig_theme(spec$options$theme)

  txt <- sprintf("Log-rank %s.", fmt_p(p))
  if (length(unique(df$group)) == 2) {
    # Capture coxph's own warnings (non-convergence, infinite coefficient from
    # complete separation, etc.) here in R — the browser worker blanket-
    # suppresses warnings, so an unreliable HR would otherwise ship silently.
    # muffleWarning stops the captured warning from leaking to the WARN-0 gate.
    cox_warn <- NULL
    cox <- withCallingHandlers(
      survival::coxph(survival::Surv(time, status) ~ group, data = df),
      warning = function(w) {
        cox_warn <<- conditionMessage(w)
        invokeRestart("muffleWarning")
      })
    # Reference is the first factor level; the fitted coefficient is for the
    # other (non-reference) level, so the HR reads "<non-ref> vs <ref>".
    lv  <- cox$xlevels$group
    ref <- lv[1]; num <- lv[2]
    hr  <- exp(stats::coef(cox))[1]
    ci  <- exp(stats::confint(cox))[1, ]
    if (!is.null(cox_warn) || !is.finite(hr) || !all(is.finite(ci))) {
      reason <- cox_warn %||% "estimate is not finite (likely complete separation)"
      txt <- sprintf("Hazard ratio not reported: %s. Log-rank %s.", reason, fmt_p(p))
    } else {
      txt <- sprintf("HR %.2f (%s vs %s; 95%% CI %.2f–%.2f); log-rank %s.",
                     hr, num, ref, ci[1], ci[2], fmt_p(p))
    }
  }
  list(svg = .svg_string(plot_obj, width = 7, height = 5), text = txt)
}

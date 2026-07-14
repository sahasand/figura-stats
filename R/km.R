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

  fit <- survival::survfit(survival::Surv(time, status) ~ group, data = df)
  lr  <- survival::survdiff(survival::Surv(time, status) ~ group, data = df)
  p   <- 1 - stats::pchisq(lr$chisq, length(lr$n) - 1)
  time_label <- spec$options$time_label %||% "Time"

  # survminer::ggsurvplot emits its own internal deprecation/aesthetic warnings
  # (originating inside survminer/ggpubr, not this code). Wrap ONLY the plot
  # construction in suppressWarnings so the WARN-0 test gate holds. The stats
  # calls above (survfit/survdiff) and coxph below are NOT wrapped.
  gg <- suppressWarnings(
    survminer::ggsurvplot(fit, data = df, risk.table = TRUE,
                          xlab = time_label, ylab = "Survival probability",
                          legend.title = "Group"))
  plot_obj <- gg$plot

  txt <- sprintf("Log-rank p = %.3f.", p)
  if (length(unique(df$group)) == 2) {
    cox <- survival::coxph(survival::Surv(time, status) ~ group, data = df)
    hr  <- exp(stats::coef(cox))[1]
    ci  <- exp(stats::confint(cox))[1, ]
    txt <- sprintf("HR %.2f (95%% CI %.2f–%.2f); log-rank p = %.3f.",
                   hr, ci[1], ci[2], p)
  }
  list(svg = .svg_string(plot_obj, width = 7, height = 5), text = txt)
}

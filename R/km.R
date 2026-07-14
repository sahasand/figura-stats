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

  # Relevel BEFORE any model fit so survfit/survdiff/coxph all agree on the
  # reference group (the caller-chosen reference becomes the first factor level,
  # which the HR-direction code below reads back from cox$xlevels$group).
  opts <- spec$options %||% list()
  ref <- opts$reference
  if (!is.null(ref)) {
    if (!ref %in% df$group) stop(sprintf("reference '%s' is not one of the groups.", ref))
    df$group <- stats::relevel(factor(df$group), ref = ref)
  }
  n_groups <- length(unique(df$group))

  fit <- survival::survfit(survival::Surv(time, status) ~ group, data = df)
  time_label <- opts$time_label %||% "Time"

  # Report a p-value without the impossible-looking "p = 0.000": show
  # "p < 0.001" below three-decimal resolution, otherwise three decimals.
  fmt_p <- function(p) if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)

  curve_df <- .km_curve_df(fit)
  step_df  <- .km_step_df(curve_df)
  censor_df <- curve_df[curve_df$n.censor > 0, , drop = FALSE]
  pal <- .km_palette(n_groups)
  x_max <- max(curve_df$time)
  breaks <- pretty(c(0, x_max), n = 6)
  x_scale <- ggplot2::scale_x_continuous(limits = range(breaks), breaks = breaks,
                                         expand = ggplot2::expansion(mult = c(0.01, 0.02)))

  # Add the CI ribbon (when requested) BEFORE the step curves so it draws
  # underneath them — ggplot2 renders layers in the order they are added.
  conf_int <- opts$conf_int %||% TRUE
  main <- ggplot2::ggplot(curve_df,
      ggplot2::aes(x = time, y = surv, color = group, linetype = group))
  if (isTRUE(conf_int)) main <- main + ggplot2::geom_ribbon(
      data = step_df[!is.na(step_df$lower), , drop = FALSE],
      ggplot2::aes(ymin = lower, ymax = upper, fill = group),
      alpha = 0.15, color = NA, show.legend = FALSE)
  main <- main +
    ggplot2::geom_step(linewidth = 0.7) +
    ggplot2::geom_point(data = censor_df, shape = 3, size = 1.8, show.legend = FALSE) +
    x_scale +
    ggplot2::scale_y_continuous(limits = c(0, 1)) +
    ggplot2::scale_color_manual(values = pal) +
    ggplot2::scale_fill_manual(values = pal) +
    ggplot2::labs(x = time_label, y = "Survival probability",
                  color = "Group", linetype = "Group") +
    .fig_theme(spec$options$theme)
  if (n_groups == 1) main <- main + ggplot2::theme(legend.position = "none")
  if (!is.null(opts$caption)) main <- main + ggplot2::labs(caption = opts$caption)

  r <- summary(fit, times = breaks, extend = TRUE)
  risk_df <- data.frame(
    time = r$time, n.risk = r$n.risk,
    group = if (is.null(r$strata)) "All" else sub("^group=", "", as.character(r$strata)))
  risk_tab <- ggplot2::ggplot(risk_df,
      ggplot2::aes(x = time, y = group, label = n.risk)) +
    ggplot2::geom_text(size = 3.1) +
    x_scale +
    ggplot2::labs(title = "Number at risk", x = NULL, y = NULL) +
    ggplot2::theme_minimal(base_size = 10) +
    ggplot2::theme(panel.grid = ggplot2::element_blank(),
                   axis.text.x = ggplot2::element_blank(),
                   plot.title = ggplot2::element_text(size = 9, face = "bold"))

  # Display-only x cutoff: coord_cartesian zooms both panels without dropping
  # data, so no statistic or text below changes. One coord per plot (adding a
  # second coord would emit "replacing coordinate system").
  horizon <- opts$horizon
  if (!is.null(horizon)) {
    xlim <- c(0, as.numeric(horizon))
    main     <- main     + ggplot2::coord_cartesian(xlim = xlim)
    risk_tab <- risk_tab + ggplot2::coord_cartesian(xlim = xlim)
  }

  plot_obj <- cowplot::plot_grid(main, risk_tab, ncol = 1,
                                 rel_heights = c(0.78, 0.22),
                                 align = "v", axis = "lr")

  txt <- ""
  if (n_groups >= 2) {
    lr <- survival::survdiff(survival::Surv(time, status) ~ group, data = df)
    p  <- 1 - stats::pchisq(lr$chisq, length(lr$n) - 1)
    txt <- sprintf("Log-rank %s.", fmt_p(p))
  }
  if (n_groups == 2) {
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

  # Per-group median survival, appended from full-precision values (format once,
  # never re-parse display strings). NA median => the curve never reached 0.5.
  fmt1 <- function(x) sprintf("%.1f", x)
  med_tab <- summary(fit)$table
  if (is.null(dim(med_tab))) med_tab <- t(as.matrix(med_tab))  # single-group case
  med_lines <- vapply(seq_len(nrow(med_tab)), function(i) {
    g <- sub("^group=", "", rownames(med_tab)[i] %||% as.character(unique(df$group)[i]))
    m <- med_tab[i, "median"]
    if (is.na(m)) sprintf("%s not reached", g)
    else sprintf("%s %s %s", g, fmt1(m), time_label)
  }, character(1))
  txt <- paste0(txt, if (nzchar(txt)) " " else "",
                "Median survival: ", paste(med_lines, collapse = "; "), ".")

  # Optional landmark survival estimates at caller-requested times.
  landmarks <- opts$landmarks %||% numeric(0)
  if (length(landmarks) > 0) {
    lm <- summary(fit, times = as.numeric(landmarks), extend = TRUE)
    lg <- if (is.null(lm$strata)) rep(as.character(unique(df$group)[1]), length(lm$time))
          else sub("^group=", "", as.character(lm$strata))
    lm_lines <- sprintf("At %s %s, survival was %s%% (95%% CI %s%%–%s%%) in %s",
                        fmt1(lm$time), time_label, fmt1(100 * lm$surv),
                        fmt1(100 * lm$lower), fmt1(100 * lm$upper), lg)
    txt <- paste0(txt, " ", paste(lm_lines, collapse = "; "), ".")
  }

  list(svg = .svg_string(plot_obj, width = 7, height = 6), text = txt)
}

# Rows of (time, surv, lower, upper, n.censor, group) per stratum, with a
# time-zero row so every curve starts at S(0) = 1 with a degenerate CI.
.km_curve_df <- function(fit) {
  s <- summary(fit, censored = TRUE)
  grp <- if (is.null(s$strata)) "All" else sub("^group=", "", as.character(s$strata))
  d <- data.frame(time = s$time, surv = s$surv,
                  lower = ifelse(is.na(s$lower), NA_real_, s$lower),
                  upper = ifelse(is.na(s$upper), NA_real_, s$upper),
                  n.censor = s$n.censor, group = grp, stringsAsFactors = FALSE)
  t0 <- data.frame(time = 0, surv = 1, lower = 1, upper = 1, n.censor = 0,
                   group = unique(grp), stringsAsFactors = FALSE)
  rbind(t0, d)
}

# Duplicate points so ribbons/lines through them reproduce step geometry:
# (t1,y1),(t2,y1),(t2,y2),(t3,y2),...,(tn,yn)
.km_step_df <- function(d) {
  do.call(rbind, lapply(split(d, d$group), function(g) {
    g <- g[order(g$time), ]
    n <- nrow(g)
    if (n < 2) return(g)
    val_idx  <- rep(seq_len(n), each = 2)[-(2 * n)]  # 1,1,2,2,...,n-1,n-1,n
    time_idx <- rep(seq_len(n), each = 2)[-1]        # 1,2,2,3,3,...,n,n
    out <- g[val_idx, , drop = FALSE]
    out$time <- g$time[time_idx]
    out
  }))
}

# Accessible qualitative palette (Tol bright); hcl fallback beyond 6 groups.
.km_palette <- function(n) {
  tol <- c("#4477AA", "#CC6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377")
  if (n <= length(tol)) tol[seq_len(n)] else grDevices::hcl.colors(n, "Dark 2")
}

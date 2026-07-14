#' Forest plot from summary effect estimates + CIs.
fig_forest <- function(spec) {
  rows <- spec$rows
  if (length(rows) == 0) stop("Forest plot needs at least one row.")
  df <- data.frame(
    label    = vapply(rows, function(r) as.character(r$label), character(1)),
    estimate = vapply(rows, function(r) as.numeric(r$estimate), numeric(1)),
    lower    = vapply(rows, function(r) as.numeric(r$lower), numeric(1)),
    upper    = vapply(rows, function(r) as.numeric(r$upper), numeric(1)),
    stringsAsFactors = FALSE
  )
  if (any(df$lower > df$upper)) {
    stop("Each confidence interval lower bound must be <= its upper bound.")
  }
  effect_label <- spec$options$effect_label %||% "Effect"
  null_line    <- spec$options$null_line %||% 1
  df$label <- factor(df$label, levels = rev(df$label))

  p <- ggplot2::ggplot(df, ggplot2::aes(x = estimate, y = label)) +
    ggplot2::geom_vline(xintercept = null_line, linetype = "dashed",
                        colour = "grey50") +
    ggplot2::geom_point(size = 2.5) +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = lower, xmax = upper),
                           width = 0.2, orientation = "y") +
    ggplot2::labs(x = effect_label, y = NULL) +
    ggplot2::theme_minimal(base_size = 12)

  first <- df[1, ]
  txt <- sprintf("%s %.2f (95%% CI %.2f–%.2f)",
                 effect_label, first$estimate, first$lower, first$upper)
  list(svg = .svg_string(p, width = 6, height = 0.6 * nrow(df) + 1.5),
       text = txt)
}

`%||%` <- function(a, b) if (is.null(a)) b else a

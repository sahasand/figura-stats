#' Scatter plot + correlation (Pearson or Spearman) with r/rho, CI, p.
fig_correlation <- function(spec) {
  xcol <- spec$roles$x; ycol <- spec$roles$y
  rows <- spec$data
  x <- vapply(rows, function(r) as.numeric(r[[xcol]]), numeric(1))
  y <- vapply(rows, function(r) as.numeric(r[[ycol]]), numeric(1))
  ok <- !is.na(x) & !is.na(y)
  x <- x[ok]; y <- y[ok]
  if (length(x) < 3) stop("Correlation needs at least 3 complete point pairs.")

  method <- spec$options$method %||% "pearson"
  ct <- stats::cor.test(x, y, method = method)
  p <- ct$p.value
  pfmt <- if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)
  df <- data.frame(x = x, y = y)
  gg <- ggplot2::ggplot(df, ggplot2::aes(x = x, y = y)) +
    ggplot2::geom_point(alpha = 0.6, size = 1.5) +
    ggplot2::geom_smooth(method = "lm", formula = y ~ x, se = TRUE, colour = "black") +
    ggplot2::labs(x = xcol, y = ycol) +
    ggplot2::theme_minimal(base_size = 12)

  if (identical(method, "pearson")) {
    ci <- ct$conf.int
    txt <- sprintf("r = %.2f (95%% CI %.2f-%.2f), %s (Pearson), n = %d.",
                   ct$estimate, ci[1], ci[2], pfmt, length(x))
  } else {
    txt <- sprintf("rho = %.2f, %s (Spearman), n = %d.", ct$estimate, pfmt, length(x))
  }
  list(svg = .svg_string(gg, width = 5.5, height = 4.5), text = txt)
}

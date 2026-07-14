#' CONSORT-style vertical flow diagram (boxes + arrows), pure layout.
fig_consort <- function(spec) {
  nodes <- vapply(spec$nodes, function(n) as.character(n$text), character(1))
  if (length(nodes) < 2) stop("CONSORT diagram needs at least two nodes.")
  excl <- if (length(spec$exclusions))
    vapply(spec$exclusions, function(n) as.character(n$text), character(1)) else character(0)

  n <- length(nodes)
  ys <- seq(n, 1)
  boxes <- data.frame(x = 1, y = ys, label = nodes)
  p <- ggplot2::ggplot() +
    ggplot2::geom_label(data = boxes, ggplot2::aes(x, y, label = label),
      fill = "white", linewidth = 0.4, size = 3.5) +
    ggplot2::geom_segment(
      data = data.frame(x = 1, xend = 1, y = ys[-n] - 0.2, yend = ys[-1] + 0.2),
      ggplot2::aes(x, y, xend = xend, yend = yend),
      arrow = ggplot2::arrow(length = ggplot2::unit(0.15, "cm"))) +
    ggplot2::theme_void()
  if (length(excl)) {
    ex <- data.frame(x = 2, y = ys[seq_along(excl)] - 0.5, label = excl)
    p <- p + ggplot2::geom_label(data = ex, ggplot2::aes(x, y, label = label),
      fill = "grey95", size = 3) +
      ggplot2::xlim(0.5, 3)
  } else {
    p <- p + ggplot2::xlim(0.5, 1.5)
  }
  list(svg = .svg_string(p, width = 7, height = 0.9 * n + 1),
       text = paste(nodes, collapse = " -> "))
}

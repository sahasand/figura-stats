#' Return a ggplot2 theme for a named journal preset (falls back to generic).
.fig_theme <- function(name = "generic") {
  if (is.null(name)) name <- "generic"
  base <- ggplot2::theme_minimal(base_size = 12)
  switch(as.character(name),
    nejm = base + ggplot2::theme(
      text = ggplot2::element_text(family = "sans"),
      panel.grid.minor = ggplot2::element_blank(),
      axis.line = ggplot2::element_line(colour = "black")),
    jama = base + ggplot2::theme(
      panel.grid.major.x = ggplot2::element_blank(),
      panel.grid.minor = ggplot2::element_blank()),
    base
  )
}

#' Compare a numeric value across groups: box/violin plot + significance test.
fig_groupcompare <- function(spec) {
  vcol <- spec$roles$value; gcol <- spec$roles$group
  rows <- spec$data
  value <- vapply(rows, function(r) as.numeric(r[[vcol]]), numeric(1))
  group <- vapply(rows, function(r) as.character(r[[gcol]]), character(1))
  df <- data.frame(value = value, group = group, stringsAsFactors = FALSE)
  df <- df[!is.na(df$value) & df$group != "", ]
  ng <- length(unique(df$group))
  if (ng < 2) stop("Group comparison needs at least two groups.")

  nonpar <- identical(spec$options$test %||% "parametric", "nonparametric")
  if (ng == 2) {
    if (nonpar) { ht <- stats::wilcox.test(value ~ group, data = df); tname <- "Mann-Whitney U test" }
    else { ht <- stats::t.test(value ~ group, data = df); tname <- "Welch t-test" }
  } else {
    if (nonpar) { ht <- stats::kruskal.test(value ~ group, data = df); tname <- "Kruskal-Wallis test" }
    else { ht <- stats::oneway.test(value ~ group, data = df); tname <- "one-way ANOVA (Welch)" }
  }
  p <- ht$p.value
  pfmt <- if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)

  plot_kind <- spec$options$plot %||% "box"
  base <- ggplot2::ggplot(df, ggplot2::aes(x = group, y = value))
  layer <- if (identical(plot_kind, "violin"))
    ggplot2::geom_violin(fill = "grey90") else ggplot2::geom_boxplot(fill = "grey90", outlier.shape = NA)
  gg <- base + layer +
    ggplot2::geom_jitter(width = 0.15, alpha = 0.5, size = 1) +
    ggplot2::labs(x = NULL, y = vcol) +
    ggplot2::theme_minimal(base_size = 12)

  meds <- tapply(df$value, df$group, stats::median)
  summ <- paste(sprintf("%s %.2f", names(meds), meds), collapse = ", ")
  txt <- sprintf("Median %s by group: %s. %s: %s.", vcol, summ, tname, pfmt)
  list(svg = .svg_string(gg, width = 6, height = 4.5), text = txt)
}

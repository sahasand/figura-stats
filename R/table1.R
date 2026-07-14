#' Format a demographics "Table 1" from pre-summarized values.
fig_table1 <- function(spec) {
  groups <- vapply(spec$groups, as.character, character(1))
  g <- length(groups)
  vars <- vapply(spec$rows, function(r) as.character(r$variable), character(1))
  mat <- t(vapply(spec$rows, function(r) {
    v <- vapply(r$values, as.character, character(1))
    if (length(v) != g) stop(sprintf("Row '%s' has %d values but there are %d groups.",
                                      r$variable, length(v), g))
    v
  }, character(g)))
  df <- data.frame(Characteristic = vars, mat, check.names = FALSE,
                   stringsAsFactors = FALSE)
  colnames(df)[-1] <- groups

  html <- knitr::kable(df, format = "html", table.attr = 'class="table1"')
  tsv <- paste(apply(cbind(vars, mat), 1, paste, collapse = "\t"), collapse = "\n")
  list(svg = as.character(html), text = tsv)
}

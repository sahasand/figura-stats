#' Render a figure from a JSON spec string. Never throws; always returns JSON.
render_figure <- function(json_string) {
  result <- tryCatch({
    spec <- jsonlite::fromJSON(json_string, simplifyVector = FALSE)
    fig <- spec$figure
    if (is.null(fig)) fig <- "(none)"
    out <- switch(as.character(fig),
      forest  = fig_forest(spec),
      consort = fig_consort(spec),
      table1  = fig_table1(spec),
      km      = fig_km(spec),
      groupcompare = fig_groupcompare(spec),
      correlation = fig_correlation(spec),
      stop(sprintf("Unknown figure: %s", fig))
    )
    list(ok = TRUE, svg = out$svg, text = out$text)
  }, error = function(e) {
    list(ok = FALSE, error = conditionMessage(e))
  })
  jsonlite::toJSON(result, auto_unbox = TRUE)
}

#' Render a ggplot to an SVG string (no file on disk).
.svg_string <- function(plot, width = 7, height = 5) {
  s <- svglite::svgstring(width = width, height = height)
  print(plot)
  grDevices::dev.off()
  paste(s(), collapse = "")
}

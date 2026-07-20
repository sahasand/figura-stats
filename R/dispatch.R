#' Render a figure from a JSON spec string. Never throws; always returns JSON.
render_figure <- function(json_string) {
  result <- tryCatch({
    spec <- jsonlite::fromJSON(json_string, simplifyVector = FALSE)
    fig <- spec$figure
    if (is.null(fig)) fig <- "(none)"
    out <- switch(as.character(fig),
      summary = fig_summary(spec),
      km      = fig_km(spec),
      explore = fig_explore(spec),
      groupcompare = fig_groupcompare(spec),
      cox     = fig_cox(spec),
      logistic = fig_logistic(spec),
      stop(sprintf("Unknown figure: %s", fig))
    )
    res <- list(ok = TRUE, svg = out$svg, text = out$text)
    if (!is.null(out$code)) res$code <- out$code
    res
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

#' Null-coalescing helper shared by every figure implementation.
`%||%` <- function(a, b) if (is.null(a)) b else a

#' Is a ratio estimate (HR, OR) reportable, on the RATIO scale?
#'
#' The whole interval must be finite and stay inside [1e-6, 1e6]. Both tails
#' matter and for the same reason: a runaway limit is the signature of a fit
#' that carries no usable information about that term (separation, severe
#' collinearity, a wildly mis-scaled covariate), and on the forest plot's shared
#' log axis it flattens every healthy covariate to a hairline. The protective
#' tail was missed at first — bounded above only, an effect of 1e-11 sailed
#' through and did exactly what a 1e11 one does.
#'
#' Cox and logistic share this so their tables and plots can never disagree:
#' `.cox_hr_cell`/`.logistic_or_cell` use it to decide whether to print a
#' number, and `.cox_forest_svg`/`.logistic_forest_svg` use it to decide whether
#' to draw a row. Vectorised (`&`, not `&&`), since the plot filters apply it
#' across all terms at once; scalar arguments return a length-1 logical.
.ratio_reportable <- function(est, lo, hi) {
  is.finite(est) & is.finite(lo) & is.finite(hi) & hi <= 1e6 & lo >= 1e-6
}

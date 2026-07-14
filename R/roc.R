#' ROC curve + AUC (DeLong CI) + Youden-optimal cutoff.
fig_roc <- function(spec) {
  pcol <- spec$roles$predictor; ocol <- spec$roles$outcome
  rows <- spec$data
  predictor_raw <- vapply(rows, function(r) {
    v <- r[[pcol]]
    if (is.null(v)) NA_character_ else as.character(v)
  }, character(1))
  predictor <- suppressWarnings(as.numeric(predictor_raw))
  failed <- !is.na(predictor_raw) & predictor_raw != "" & is.na(predictor)
  if (any(failed)) {
    stop(sprintf("Column '%s' must be numeric.", pcol))
  }
  outcome_raw <- vapply(rows, function(r) as.character(r[[ocol]]), character(1))
  ok <- !is.na(predictor) & !is.na(outcome_raw) & outcome_raw != ""
  predictor <- predictor[ok]; outcome_raw <- outcome_raw[ok]
  levs <- sort(unique(outcome_raw))
  if (length(levs) != 2) stop("ROC needs an outcome with exactly two distinct values.")

  roc <- pROC::roc(response = outcome_raw, predictor = predictor,
                   levels = levs, direction = "auto", quiet = TRUE)
  auc <- as.numeric(pROC::auc(roc))
  ci <- as.numeric(pROC::ci.auc(roc))            # c(lower, auc, upper)
  best <- pROC::coords(roc, "best", best.method = "youden",
                       ret = c("threshold", "sensitivity", "specificity"))
  best <- as.data.frame(best)[1, ]

  crd <- pROC::coords(roc, "all", ret = c("specificity", "sensitivity"))
  crd <- as.data.frame(crd)
  gg <- ggplot2::ggplot(crd, ggplot2::aes(x = 1 - specificity, y = sensitivity)) +
    ggplot2::geom_abline(slope = 1, intercept = 0, linetype = "dashed", colour = "grey60") +
    ggplot2::geom_path(linewidth = 0.8) +
    ggplot2::coord_equal() +
    ggplot2::labs(x = "1 - specificity", y = "Sensitivity") +
    ggplot2::theme_minimal(base_size = 12)

  txt <- sprintf(
    "AUC %.2f (95%% CI %.2f-%.2f). Optimal cutoff %.2f: sensitivity %.0f%%, specificity %.0f%%.",
    auc, ci[1], ci[3], best$threshold, 100 * best$sensitivity, 100 * best$specificity)
  list(svg = .svg_string(gg, width = 5, height = 5), text = txt)
}

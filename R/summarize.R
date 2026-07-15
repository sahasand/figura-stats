# Population skewness of the non-missing values; NA if fewer than 3; 0 if zero spread.
.skewness <- function(x) {
  x <- x[!is.na(x)]
  n <- length(x)
  if (n < 3) return(NA_real_)
  m <- mean(x); s <- sqrt(mean((x - m)^2))
  if (s == 0) return(0)
  mean((x - m)^3) / s^3
}

# Decide mean ± SD vs median (IQR) for one numeric variable, with a defensible
# reason.
#
#   n < 3 or < 3 distinct ──▶ median ("too few distinct values")
#   n <= 300 ──▶ Shapiro–Wilk AND |skewness| < 1 both pass ──▶ mean
#   n >  300 ──▶ |skewness| < 1 alone decides (Shapiro over-rejects trivial
#                departures at large n — citing p = 0.003 on visually normal
#                registry data is indefensible, so above 300 the reason cites
#                skewness and n instead).
#
# Callers pass group-mean-centered values when a group role exists (see
# fig_summary): pooling group-shifted normals yields a mixture that falsely
# fails normality. Ties/degenerate spread fall through to median, the safer
# default for summarizing.
.summary_decide <- function(x) {
  x <- x[!is.na(x)]
  n <- length(x)
  sk <- .skewness(x)
  fmt_p <- function(p) if (p < 0.001) "Shapiro–Wilk p < 0.001"
                       else sprintf("Shapiro–Wilk p = %.3f", p)
  skew_phrase <- function() {
    dir <- if (sk > 0) "right" else "left"
    sprintf("%s-skewed (skewness %.1f)", dir, sk)
  }
  if (n < 3 || length(unique(x)) < 3) {
    return(list(kind = "median",
                reason = "too few distinct values to assess normality; using median (IQR)"))
  }
  if (n > 300) {
    if (abs(sk) < 1)
      return(list(kind = "mean",
                  reason = sprintf("approximately symmetric (skewness %.1f, n = %d)", sk, n)))
    return(list(kind = "median", reason = sprintf("%s, n = %d", skew_phrase(), n)))
  }
  p <- suppressWarnings(stats::shapiro.test(x)$p.value)
  if (p >= 0.05 && abs(sk) < 1)
    return(list(kind = "mean",
                reason = sprintf("approximately normal (%s)", fmt_p(p))))
  # Not normal: lead with whichever signal is more legible.
  if (abs(sk) >= 1)
    return(list(kind = "median", reason = sprintf("%s; %s", skew_phrase(), fmt_p(p))))
  list(kind = "median", reason = sprintf("departs from normal (%s)", fmt_p(p)))
}

# One number, 3 significant figures, plain notation, no trailing zeros:
# 250000 -> "250000", 1.125 -> "1.13", 0.00123 -> "0.00123".
.fmt_num <- function(v) {
  format(signif(v, 3), trim = TRUE, scientific = FALSE, drop0trailing = TRUE)
}

# Format a continuous summary. mean -> "M ± SD"; median -> "Q2 (Q1–Q3)".
.fmt_continuous <- function(x, kind) {
  x <- x[!is.na(x)]
  if (identical(kind, "mean"))
    return(sprintf("%s ± %s", .fmt_num(mean(x)), .fmt_num(stats::sd(x))))
  q <- stats::quantile(x, c(0.25, 0.5, 0.75), names = FALSE, type = 7)
  sprintf("%s (%s–%s)", .fmt_num(q[2]), .fmt_num(q[1]), .fmt_num(q[3]))
}

# Minimal HTML escaper for user-supplied column values and labels.
.esc <- function(s) {
  s <- as.character(s)
  s <- gsub("&", "&amp;", s, fixed = TRUE)
  s <- gsub("<", "&lt;", s, fixed = TRUE)
  gsub(">", "&gt;", s, fixed = TRUE)
}

# Coerce one named column across all data rows to numeric, erroring (without a
# leaked coercion warning) if any non-blank cell is non-numeric. Mirrors the
# pattern in R/correlation.R / R/roc.R.
.numeric_col <- function(rows, colname) {
  raw <- vapply(rows, function(r) {
    v <- r[[colname]]
    if (is.null(v)) NA_character_ else as.character(v)
  }, character(1))
  num <- suppressWarnings(as.numeric(raw))
  failed <- !is.na(raw) & raw != "" & is.na(num)
  if (any(failed)) stop(sprintf("Column '%s' must be numeric.", colname))
  num
}

.char_col <- function(rows, colname) {
  vapply(rows, function(r) {
    v <- r[[colname]]
    if (is.null(v)) NA_character_ else as.character(v)
  }, character(1))
}

# Build the HTML table from prepared cell matrices.
# `rows` is a list of list(label=, why=<char|NULL>, cells=<character vector>,
# missing=<character>, indent=<logical>).
.summary_table_html <- function(group_headers, rows) {
  th <- paste0("<th>", .esc(group_headers), "</th>", collapse = "")
  header <- sprintf("<tr><th>Characteristic</th>%s<th>Missing</th></tr>", th)
  body <- vapply(rows, function(r) {
    label <- .esc(r$label)
    if (isTRUE(r$indent)) label <- paste0("<span class=\"lvl\">", label, "</span>")
    why <- if (!is.null(r$why) && nzchar(r$why))
      sprintf("<div class=\"why\">%s</div>", .esc(r$why)) else ""
    cells <- paste0("<td>", .esc(r$cells), "</td>", collapse = "")
    sprintf("<tr><td>%s%s</td>%s<td>%s</td></tr>", label, why, cells, .esc(r$missing))
  }, character(1))
  paste0("<table class=\"table1\"><thead>", header, "</thead><tbody>",
         paste(body, collapse = ""), "</tbody></table>")
}

# ---- Distribution figure ----------------------------------------------------
# The figure is a stack of SIBLING <svg> elements (histogram+density, box+
# jitter, and an opt-in Q-Q row) inside one <figure> block. fig_summary's svg
# field already carries HTML, so no composition package is needed and the
# summary analysis keeps its no-extra-download property.

# Long data frame of plottable values: one row per non-missing observation
# with its display label and group. NULL when nothing is plottable. Variable
# order follows the user's selection; group order is first-appearance.
.summary_plot_df <- function(rows, continuous, labels, grp, levels_g) {
  disp <- function(col) as.character((labels %||% list())[[col]] %||% col)
  parts <- lapply(continuous, function(col) {
    x <- .numeric_col(rows, col)
    keep <- !is.na(x)
    if (!any(keep)) return(NULL)
    data.frame(variable = disp(col), value = x[keep], group = grp[keep],
               stringsAsFactors = FALSE)
  })
  df <- do.call(rbind, parts[!vapply(parts, is.null, logical(1))])
  if (is.null(df) || nrow(df) == 0) return(NULL)
  df$variable <- factor(df$variable, levels = unique(df$variable))
  df$group <- factor(df$group, levels = levels_g)
  df
}

# Row 1: faceted histogram on a density scale with a smoothed density curve
# and dashed-mean / solid-median reference lines (pooled values), so the
# reader sees why each variable got its summary.
.summary_hist_svg <- function(df) {
  refs <- do.call(rbind, lapply(split(df, df$variable), function(d)
    data.frame(variable = d$variable[1], mean = mean(d$value),
               median = stats::median(d$value))))
  gg <- ggplot2::ggplot(df, ggplot2::aes(x = value)) +
    ggplot2::geom_histogram(ggplot2::aes(y = ggplot2::after_stat(density)),
                            bins = 20, fill = "grey85", colour = "white",
                            linewidth = 0.2) +
    ggplot2::geom_density(colour = "grey40", linewidth = 0.4) +
    ggplot2::geom_vline(data = refs, ggplot2::aes(xintercept = mean),
                        linetype = "dashed", linewidth = 0.5, colour = "#2b6cb0") +
    ggplot2::geom_vline(data = refs, ggplot2::aes(xintercept = median),
                        linetype = "solid", linewidth = 0.5, colour = "#c05621") +
    ggplot2::facet_wrap(~ variable, scales = "free") +
    ggplot2::labs(x = NULL, y = "Density") +
    ggplot2::theme_minimal(base_size = 11)
  .svg_string(gg, width = 7, height = 2.6 * ceiling(nlevels(df$variable) / 2))
}

# Row 2: box plot per variable with the individual observations jittered on
# top. X axis is the group (a single "Overall" category when no group role,
# matching the table's column header), so the panel reads as a group
# comparison. Boxplot outliers are hidden because the jitter layer already
# draws every point once. Fills reuse the Tol data palette (.km_palette),
# deliberately distinct from chrome colors.
.summary_box_svg <- function(df) {
  gg <- ggplot2::ggplot(df, ggplot2::aes(x = group, y = value)) +
    ggplot2::geom_boxplot(ggplot2::aes(fill = group), outlier.shape = NA,
                          linewidth = 0.3, alpha = 0.6, show.legend = FALSE) +
    ggplot2::geom_jitter(width = 0.15, height = 0, size = 0.6, alpha = 0.35,
                         colour = "grey30") +
    ggplot2::scale_fill_manual(values = .km_palette(nlevels(df$group))) +
    ggplot2::facet_wrap(~ variable, scales = "free_y") +
    ggplot2::labs(x = NULL, y = NULL) +
    ggplot2::theme_minimal(base_size = 11)
  .svg_string(gg, width = 7, height = 2.6 * ceiling(nlevels(df$variable) / 2))
}

# Row 3 (opt-in via options$show_qq): normal Q-Q per variable — per group when
# grouped, mirroring how the mean-vs-median decision assesses normality
# (within groups). Points near the line support mean ± SD; a tail curving
# away supports median (IQR).
.summary_qq_svg <- function(df, grouped) {
  gg <- ggplot2::ggplot(df, ggplot2::aes(sample = value)) +
    ggplot2::stat_qq(size = 0.6, alpha = 0.5, colour = "grey30") +
    ggplot2::stat_qq_line(linewidth = 0.4, colour = "#2b6cb0") +
    ggplot2::labs(x = "Theoretical quantiles", y = "Sample quantiles") +
    ggplot2::theme_minimal(base_size = 11)
  if (grouped) {
    gg <- gg + ggplot2::facet_grid(group ~ variable, scales = "free")
    .svg_string(gg, width = 7, height = 2.2 * nlevels(df$group))
  } else {
    gg <- gg + ggplot2::facet_wrap(~ variable, scales = "free")
    .svg_string(gg, width = 7, height = 2.6 * ceiling(nlevels(df$variable) / 2))
  }
}

#' Auto-computed Table 1 with normality-aware continuous summaries.
fig_summary <- function(spec) {
  rows <- spec$data
  if (length(rows) == 0) stop("No data rows.")
  opt <- spec$options
  gcol <- spec$roles$group
  labels <- opt$labels %||% list()
  overrides <- opt$overrides %||% list()
  continuous <- unlist(opt$continuous %||% list())
  categorical <- unlist(opt$categorical %||% list())
  if (length(continuous) == 0 && length(categorical) == 0)
    stop("Select at least one variable to summarize.")
  for (col in names(overrides))
    if (!overrides[[col]] %in% c("mean", "median"))
      stop(sprintf("Unknown override '%s' for column '%s' (use \"mean\" or \"median\").",
                   overrides[[col]], col))

  disp <- function(col) as.character(labels[[col]] %||% col)

  # Group membership -> levels in FIRST-APPEARANCE order (preserves Control-first
  # and dose ordering as arranged in the file). Null/absent group => "Overall".
  if (is.null(gcol)) {
    grp <- rep("Overall", length(rows)); levels_g <- "Overall"
  } else {
    grp <- .char_col(rows, gcol); grp[is.na(grp) | grp == ""] <- "(missing)"
    levels_g <- unique(grp)
  }
  group_n <- vapply(levels_g, function(g) sum(grp == g), integer(1))
  headers <- sprintf("%s (N=%d)", levels_g, group_n)

  # Values fed to the normality decision: group-mean-centered when groups exist.
  # Pooling group-shifted normals yields a bimodal mixture that falsely fails
  # normality; centering tests the within-group shape, which is what the table
  # summarizes. One decision per variable keeps rows consistent across columns.
  decide_values <- function(x) {
    if (is.null(gcol)) return(x)
    centered <- x
    for (g in levels_g) {
      idx <- grp == g & !is.na(x)
      if (any(idx)) centered[idx] <- x[idx] - mean(x[idx])
    }
    centered
  }

  out_rows <- list()

  for (col in continuous) {
    x <- .numeric_col(rows, col)
    d <- .summary_decide(decide_values(x))
    if (!is.null(gcol)) d$reason <- paste0(d$reason, "; assessed within groups")
    ov <- overrides[[col]]
    kind <- if (!is.null(ov)) as.character(ov) else d$kind
    why <- if (!is.null(ov))
      sprintf("you selected %s; data suggested %s",
              if (kind == "mean") "mean ± SD" else "median (IQR)", d$reason)
    else d$reason
    cells <- vapply(levels_g, function(g) {
      xg <- x[grp == g]; xg <- xg[!is.na(xg)]
      # sd(n=1) is NA, so a single-value group cannot form "M ± SD"; show the
      # bare value instead. Empty group -> em-dash.
      if (length(xg) == 0) "—"
      else if (length(xg) == 1) .fmt_num(xg)
      else .fmt_continuous(xg, kind)
    }, character(1))
    label <- sprintf("%s, %s", disp(col), if (kind == "mean") "mean ± SD" else "median (IQR)")
    out_rows[[length(out_rows) + 1]] <- list(
      label = label, why = why, cells = cells,
      missing = as.character(sum(is.na(x))), indent = FALSE)
  }

  # Categorical variables: a header row stating the ACTUAL percentage
  # denominator (the non-missing count — the column header's N= includes
  # missing rows and must not be claimed as the denominator), then one
  # indented n (%) row per level. Percentages use each group's own
  # non-missing count.
  for (col in categorical) {
    v <- .char_col(rows, col)
    n_data <- sum(!is.na(v) & v != "")
    miss_total <- length(v) - n_data
    out_rows[[length(out_rows) + 1]] <- list(
      label = disp(col), why = sprintf("n (%%) of %d with data", n_data),
      cells = rep("", length(levels_g)),
      missing = as.character(miss_total), indent = FALSE)
    lev <- sort(unique(v[!is.na(v) & v != ""]))
    for (l in lev) {
      cells <- vapply(levels_g, function(g) {
        vg <- v[grp == g]; denom <- sum(!is.na(vg) & vg != "")
        k <- sum(vg == l, na.rm = TRUE)
        if (denom == 0) "—" else sprintf("%d (%.0f%%)", k, 100 * k / denom)
      }, character(1))
      out_rows[[length(out_rows) + 1]] <- list(
        label = l, why = NULL, cells = cells, missing = "", indent = TRUE)
    }
  }

  table_html <- .summary_table_html(headers, out_rows)

  # Optional distribution figure: stacked sibling SVGs inside one <figure>.
  # show_plots gates the histogram+density and box+jitter rows as a pair;
  # show_qq independently adds the Q-Q row. The teaching legend and synthetic
  # caption are HTML (styleable), not ggplot in-SVG text. No <figure> at all
  # when nothing is plottable.
  figure_html <- ""
  want_plots <- isTRUE(opt$show_plots)
  want_qq <- isTRUE(opt$show_qq)
  if ((want_plots || want_qq) && length(continuous) > 0) {
    df <- .summary_plot_df(rows, continuous, labels, grp, levels_g)
    if (!is.null(df)) {
      svgs <- c(
        if (want_plots) c(.summary_hist_svg(df), .summary_box_svg(df)),
        if (want_qq) .summary_qq_svg(df, grouped = !is.null(gcol)))
      legend_bits <- c(
        if (want_plots) c(paste0(
          "<span class=\"mean-key\">dashed = mean</span> · ",
          "<span class=\"median-key\">solid = median</span> · curve = density",
          " — when the lines separate, the variable is skewed (or, in grouped data, shifted between groups)"),
          "box = median and IQR, whiskers to 1.5 × IQR, dots = individual observations"),
        if (want_qq)
          "Q–Q: points near the line support mean ± SD; a curved tail supports median (IQR)")
      legend_html <- paste0("<div class=\"plot-legend\">",
                            paste(legend_bits, collapse = "<br>"), "</div>")
      cap <- opt$caption %||% ""
      cap_html <- if (nzchar(cap))
        sprintf("<figcaption class=\"synthetic\">%s</figcaption>", .esc(cap)) else ""
      figure_html <- sprintf("<figure class=\"dist-plot\">%s%s%s</figure>",
                             paste(svgs, collapse = ""), legend_html, cap_html)
    }
  }
  # Scroll wrapper: on narrow viewports the table scrolls inside its own
  # container instead of clipping the pane (styles.css .table-scroll).
  svg_field <- sprintf(
    "<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s</div>",
    table_html, figure_html)

  # Copy-pasteable TSV of the same body, WITH a header row so pasted text is
  # self-describing, + an explicit methods sentence.
  tsv_header <- paste(c("Characteristic", headers, "Missing"), collapse = "\t")
  tsv_lines <- vapply(out_rows, function(r)
    paste(c(r$label, r$cells, r$missing), collapse = "\t"), character(1))
  normality_clause <- if (!is.null(gcol))
    "normality was assessed within groups with the Shapiro–Wilk test (n ≤ 300) and skewness."
  else
    "normality was assessed with the Shapiro–Wilk test (n ≤ 300) and skewness."
  methods <- paste(
    "Continuous variables are summarized as mean ± SD when approximately normal",
    "and as median (IQR) otherwise;", normality_clause, "Categorical variables are n (%)",
    "with the non-missing count as the denominator. Missing values are reported",
    "per variable. No hypothesis tests are reported for baseline characteristics.")
  text <- paste0(paste(c(tsv_header, tsv_lines), collapse = "\n"), "\n\n", methods)

  list(svg = svg_field, text = text)
}

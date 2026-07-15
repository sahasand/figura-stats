# Population skewness of the non-missing values; NA if fewer than 3 or zero spread.
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
  # Scroll wrapper: on narrow viewports the table scrolls inside its own
  # container instead of clipping the pane (styles.css .table-scroll).
  svg_field <- sprintf("<div class=\"summary-output\"><div class=\"table-scroll\">%s</div></div>",
                       table_html)

  # Copy-pasteable TSV of the same body, WITH a header row so pasted text is
  # self-describing, + an explicit methods sentence.
  tsv_header <- paste(c("Characteristic", headers, "Missing"), collapse = "\t")
  tsv_lines <- vapply(out_rows, function(r)
    paste(c(r$label, r$cells, r$missing), collapse = "\t"), character(1))
  methods <- paste(
    "Continuous variables are summarized as mean ± SD when approximately normal",
    "and as median (IQR) otherwise; normality was assessed within groups with the",
    "Shapiro–Wilk test (n ≤ 300) and skewness. Categorical variables are n (%)",
    "with the non-missing count as the denominator. Missing values are reported",
    "per variable. No hypothesis tests are reported for baseline characteristics.")
  text <- paste0(paste(c(tsv_header, tsv_lines), collapse = "\n"), "\n\n", methods)

  list(svg = svg_field, text = text)
}

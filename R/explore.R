# R/explore.R
# Explore-plot figure: an interactive ggplot2 builder. The plot is built as an
# R EXPRESSION (base call() construction — never string interpolation), then
# evaluated; the SAME components are deparsed for the copy-pasteable code pane,
# so the displayed code is what ran. Column names, titles, and labels are
# arbitrary user strings; .data[["col"]] mappings and deparse() escaping keep
# any of them safe.

.EXPLORE_GEOMS <- c("scatter", "line", "boxplot", "violin", "bar", "histogram")
.EXPLORE_BLUE <- "#4477AA"   # first Tol colour, for un-mapped fills

# .data[["col"]] pronoun call — safe for any column name.
.aes_col <- function(col) call("[[", quote(.data), col)

# Read a column as numeric when every non-blank cell parses, else character.
# Categorical roles accept numeric-coded columns (0/1/2 arms); the numeric
# result is factor()-wrapped in the aes by the caller.
.flex_col <- function(rows, colname) {
  raw <- .char_col(rows, colname)
  raw[!is.na(raw) & raw == ""] <- NA
  num <- suppressWarnings(as.numeric(raw))
  if (any(!is.na(raw) & is.na(num))) raw else num
}

# The emitted code assumes an interactive session (library(ggplot2) attached,
# stats in the search path). Evaluation here happens inside the package, where
# neither is guaranteed — so the eval env parents the ggplot2 namespace (all
# ggplot2 functions resolve) and binds complete.cases explicitly.
.explore_eval_env <- function(df) {
  e <- new.env(parent = getNamespace("ggplot2"))
  e$df <- df
  e$complete.cases <- stats::complete.cases
  e
}

fig_explore <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  roles <- spec$roles %||% list()
  opt <- spec$options %||% list()
  geom <- as.character(opt$geom %||% "")
  if (!(geom %in% .EXPLORE_GEOMS))
    stop(sprintf("Unknown chart type: '%s'.", geom))

  needs_y <- geom %in% c("scatter", "line", "boxplot", "violin")
  if (is.null(roles$x)) stop("Choose a column for the x axis.")
  if (needs_y && is.null(roles$y)) stop("This chart type needs a y column.")

  used <- Filter(Negate(is.null),
    list(x = roles$x, y = if (needs_y) roles$y else NULL,
         color = roles$color, facet = roles$facet,
         group = if (geom == "line") roles$group else NULL))
  have <- names(rows[[1]])
  absent <- setdiff(unique(unlist(used)), have)
  if (length(absent) > 0)
    stop(sprintf("Column '%s' not found in the data.", absent[[1]]))

  numeric_roles <- switch(geom,
    scatter = c("x", "y"), line = c("x", "y"),
    boxplot = "y", violin = "y", histogram = "x", bar = character(0))
  df <- list()
  for (rname in names(used)) {
    col <- used[[rname]]
    df[[col]] <- if (rname %in% numeric_roles) .numeric_col(rows, col)
                 else .flex_col(rows, col)
  }
  df <- as.data.frame(df, check.names = FALSE, stringsAsFactors = FALSE)

  n_drop <- nrow(df) - sum(stats::complete.cases(df))
  if (n_drop == nrow(df)) stop("All rows have missing values in the selected columns.")
  prep_expr <- NULL
  if (n_drop > 0) {
    cols_call <- as.call(c(quote(c), as.list(names(df))))
    prep_expr <- bquote(df <- df[complete.cases(df[, .(cols_call)]), ])
  }

  # factor()-wrap numeric columns used in categorical positions.
  wrap_cat <- function(col)
    if (is.numeric(df[[col]])) call("factor", .aes_col(col)) else .aes_col(col)

  aes_args <- list()
  aes_args$x <- if (geom %in% c("boxplot", "violin", "bar")) wrap_cat(roles$x)
                else .aes_col(roles$x)
  if (needs_y) aes_args$y <- .aes_col(roles$y)
  color_aes <- if (geom %in% c("scatter", "line")) "colour" else "fill"
  if (!is.null(roles$color)) aes_args[[color_aes]] <- wrap_cat(roles$color)
  if (!is.null(used$group)) aes_args$group <- wrap_cat(roles$group)
  base_call <- call("ggplot", quote(df), as.call(c(quote(aes), aes_args)))

  layers <- .explore_layers(geom, opt, roles)

  scale_call <- NULL
  if (!is.null(roles$color)) {
    v <- df[[roles$color]]
    pal <- .km_palette(length(unique(v[!is.na(v)])))
    fun <- if (color_aes == "colour") "scale_colour_manual" else "scale_fill_manual"
    scale_call <- as.call(list(as.name(fun),
      values = as.call(c(quote(c), as.list(pal)))))
  }
  facet_call <- if (!is.null(roles$facet))
    as.call(list(quote(facet_wrap), as.call(list(quote(vars), wrap_cat(roles$facet)))))

  chr1 <- function(v) { v <- as.character(v %||% "")
                        if (length(v) == 1 && nzchar(v)) v else NULL }
  default_y <- switch(geom,
    bar = if (isTRUE(opt$prop) && !is.null(roles$color))
            sprintf("proportion within %s", roles$x)
          else if (isTRUE(opt$prop)) "proportion of total" else "count",
    histogram = if (isTRUE(opt$density)) "density" else "count",
    roles$y)
  labs_args <- list(x = chr1(opt$xlab) %||% roles$x,
                    y = chr1(opt$ylab) %||% default_y)
  if (!is.null(roles$color)) labs_args[[color_aes]] <- roles$color
  if (!is.null(chr1(opt$title))) labs_args$title <- chr1(opt$title)
  if (!is.null(chr1(opt$caption))) labs_args$caption <- chr1(opt$caption)

  components <- c(list(base_call), layers,
    if (!is.null(scale_call)) list(scale_call),
    if (!is.null(facet_call)) list(facet_call),
    list(as.call(c(quote(labs), labs_args)),
         quote(theme_minimal(base_size = 12))))

  env <- .explore_eval_env(df)
  if (!is.null(prep_expr)) eval(prep_expr, env)
  p <- eval(Reduce(function(a, b) call("+", a, b), components), env)

  dep <- function(e) paste(deparse(e, width.cutoff = 60L), collapse = "\n    ")
  code <- c("library(ggplot2)", "",
    "# Load your data (edit the path):",
    '# df <- read.csv("your-data.csv", check.names = FALSE)', "")
  if (!is.null(prep_expr)) code <- c(code,
    sprintf("# %d row%s with missing values in the selected columns excluded:",
            n_drop, if (n_drop == 1) "" else "s"),
    dep(prep_expr), "")
  code <- c(code, paste(vapply(components, dep, character(1)),
                        collapse = " +\n  "))
  list(svg = .svg_string(p, width = 7, height = 4.5),
       text = paste(code, collapse = "\n"))
}

# One list of geom-layer calls per chart type. Kept separate from fig_explore
# so each geom's options stay readable.
.explore_layers <- function(geom, opt, roles) {
  num1 <- function(v, d) { v <- suppressWarnings(as.numeric(v %||% d))
                           if (length(v) != 1 || !is.finite(v)) d else v }
  has_col <- !is.null(roles$color)
  switch(geom,
    scatter = {
      l <- list(as.call(list(quote(geom_point),
        size = num1(opt$point_size, 2), alpha = num1(opt$alpha, 0.8))))
      sm <- as.character(opt$smoother %||% "none")
      if (sm %in% c("lm", "loess"))
        l <- c(l, list(as.call(list(quote(geom_smooth), method = sm,
          formula = quote(y ~ x), se = isTRUE(opt$se %||% TRUE)))))
      l
    },
    line = {
      l <- list(as.call(list(quote(geom_line),
        linewidth = num1(opt$linewidth, 0.8))))
      if (isTRUE(opt$show_points))
        l <- c(l, list(as.call(list(quote(geom_point), size = 1.5))))
      l
    },
    boxplot = {
      l <- list(as.call(list(quote(geom_boxplot), notch = isTRUE(opt$notch))))
      if (isTRUE(opt$jitter))
        l <- c(l, list(as.call(list(quote(geom_jitter),
          width = 0.2, size = 1, alpha = 0.5))))
      l
    },
    violin = {
      l <- list(as.call(list(quote(geom_violin), trim = isTRUE(opt$trim))))
      if (isTRUE(opt$inner_box))
        l <- c(l, list(as.call(list(quote(geom_boxplot),
          width = 0.15, outlier.size = 0.8))))
      l
    },
    bar = {
      prop <- isTRUE(opt$prop)
      if (prop && has_col)
        list(as.call(list(quote(geom_bar), position = "fill")))
      else if (prop)
        list(as.call(list(quote(geom_bar), mapping = as.call(list(quote(aes),
          y = quote(after_stat(count / sum(count))))))))
      else if (has_col) {
        pos <- as.character(opt$position %||% "dodge")
        if (!pos %in% c("dodge", "stack")) pos <- "dodge"
        list(as.call(list(quote(geom_bar), position = pos)))
      } else
        list(as.call(list(quote(geom_bar), fill = .EXPLORE_BLUE)))
    },
    histogram = {
      if (isTRUE(opt$density)) {
        if (has_col) list(as.call(list(quote(geom_density), alpha = 0.6)))
        else list(as.call(list(quote(geom_density),
          fill = .EXPLORE_BLUE, alpha = 0.6)))
      } else {
        b <- as.integer(num1(opt$bins, 30)); if (b < 1) b <- 30
        b <- as.numeric(b)   # emit plain `bins = 15`, not `15L`, in teaching code
        if (has_col) list(as.call(list(quote(geom_histogram),
          bins = b, position = "identity", alpha = 0.7)))
        else list(as.call(list(quote(geom_histogram),
          bins = b, fill = .EXPLORE_BLUE, colour = "white")))
      }
    },
    stop(sprintf("Unknown chart type: '%s'.", geom))
  )
}

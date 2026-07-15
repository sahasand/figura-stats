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

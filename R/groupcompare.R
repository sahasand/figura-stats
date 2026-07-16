# R/groupcompare.R
# Group comparison: compare an outcome across 2+ groups. Routes on outcome type
# (numeric -> t/ANOVA family, categorical -> chi-square/Fisher; the categorical
# branch and post-hoc live in the same file, added alongside). Test selection is
# normality-aware via the shared .summary_decide. Every result carries an effect
# size + 95% CI + p-value, all hand-computed in base R (no extra packages).

# Non-throwing type detector (mirrors .flex_col in R/explore.R): TRUE iff every
# non-blank cell parses as numeric. .numeric_col (R/summarize.R) THROWS on a bad
# cell, so it can't be used to *detect* type — only to extract once numeric is chosen.
.gc_is_numeric_col <- function(rows, colname) {
  raw <- .char_col(rows, colname)
  raw[!is.na(raw) & raw == ""] <- NA
  num <- suppressWarnings(as.numeric(raw))
  !any(!is.na(raw) & is.na(num))
}

# Build the numeric working frame: coerce outcome, read group, drop NA/blank
# rows and groups with <2 values. Returns the frame, the surviving group names,
# a count of dropped-small-group rows, and the count of NA-outcome rows removed.
.gc_prep <- function(spec) {
  vcol <- spec$roles$outcome; gcol <- spec$roles$group
  rows <- spec$data
  value <- .numeric_col(rows, vcol)
  group <- .char_col(rows, gcol)
  group[!is.na(group) & group == ""] <- NA
  keep <- !is.na(value) & !is.na(group)
  n_na <- sum(!keep)
  df <- data.frame(value = value[keep], group = group[keep],
                   stringsAsFactors = FALSE)
  tab <- table(df$group)
  small <- names(tab)[tab < 2]
  n_small <- sum(df$group %in% small)
  df <- df[!(df$group %in% small), , drop = FALSE]
  list(df = df, groups = sort(unique(df$group)),
       n_na = n_na, n_small = n_small, vcol = vcol)
}

# --- effect-size helpers, each returns a one-line "<name> = <v> (95% CI a to b)" ---
.gc_ci_phrase <- function(est, lo, hi, name)
  sprintf("%s = %s (95%% CI %s to %s)", name, .fmt_num(est), .fmt_num(lo), .fmt_num(hi))

.gc_effect_t <- function(df) {
  g <- df$group; y <- df$value; lv <- sort(unique(g))
  x1 <- y[g == lv[1]]; x2 <- y[g == lv[2]]
  n1 <- length(x1); n2 <- length(x2)
  sp <- sqrt(((n1 - 1) * stats::var(x1) + (n2 - 1) * stats::var(x2)) / (n1 + n2 - 2))
  d <- (mean(x2) - mean(x1)) / sp
  se <- sqrt((n1 + n2) / (n1 * n2) + d^2 / (2 * (n1 + n2)))
  # Sign is (second sorted group - first); state the reference direction.
  paste0(.gc_ci_phrase(d, d - 1.96 * se, d + 1.96 * se, "Cohen's d"),
         sprintf(" (%s vs %s)", lv[2], lv[1]))
}

.gc_effect_wilcox <- function(df, U) {
  g <- df$group; lv <- sort(unique(g))
  n1 <- sum(g == lv[1]); n2 <- sum(g == lv[2])
  r <- 1 - 2 * U / (n1 * n2)              # rank-biserial
  z <- atanh(max(min(r, 0.999999), -0.999999))
  se <- 1 / sqrt(n1 + n2 - 3)
  lo <- tanh(z - 1.96 * se); hi <- tanh(z + 1.96 * se)
  # Sign is (second sorted group - first); state the reference direction.
  paste0(.gc_ci_phrase(r, lo, hi, "rank-biserial r"),
         sprintf(" (%s vs %s)", lv[2], lv[1]))
}

.gc_effect_anova <- function(df) {
  fit <- stats::aov(value ~ group, data = df)
  s <- summary(fit)[[1]]
  ss <- s[, "Sum Sq"]
  eta <- ss[1] / sum(ss)                  # eta-squared
  # CI via noncentral-F (Steiger): invert F to a lambda CI, map to eta^2.
  Fv <- s[1, "F value"]; df1 <- s[1, "Df"]; df2 <- s[2, "Df"]
  ci <- .gc_eta_ci(Fv, df1, df2)
  .gc_ci_phrase(eta, ci[1], ci[2], "eta-squared")
}

# Noncentral-F confidence limits for eta-squared (Steiger 2004). Returns c(lo,hi),
# clamped to [0,1]; falls back to c(0,1) if the root-finder can't bracket.
.gc_eta_ci <- function(Fv, df1, df2, conf = 0.95) {
  lam_to_eta <- function(lam) lam / (lam + df1 + df2 + 1)
  find <- function(target_p) {
    f <- function(lam) stats::pf(Fv, df1, df2, ncp = lam) - target_p
    lo <- 0; hi <- 1
    if (f(lo) < 0) return(0)
    while (f(hi) > 0 && hi < 1e6) hi <- hi * 2
    if (f(hi) > 0) return(NA_real_)
    stats::uniroot(f, c(lo, hi))$root
  }
  a <- (1 - conf) / 2
  hiL <- tryCatch(find(a),     error = function(e) NA_real_)
  loL <- tryCatch(find(1 - a), error = function(e) NA_real_)
  lo <- if (is.na(loL)) 0 else lam_to_eta(loL)
  hi <- if (is.na(hiL)) 1 else lam_to_eta(hiL)
  c(max(0, lo), min(1, hi))
}

.gc_effect_kruskal <- function(H, n) {
  eps <- H / (n - 1)                      # epsilon-squared (no standard CI)
  sprintf("epsilon-squared = %s", .fmt_num(eps))
}

# --- numeric-branch plot ---
.gc_numeric_plot <- function(df, vcol, plot_kind) {
  pal <- .km_palette(length(unique(df$group)))
  base <- ggplot2::ggplot(df, ggplot2::aes(x = group, y = value, fill = group))
  layer <- if (identical(plot_kind, "violin"))
    ggplot2::geom_violin(trim = FALSE, colour = "grey30")
  else ggplot2::geom_boxplot(outlier.shape = NA, colour = "grey30")
  base + layer +
    ggplot2::geom_jitter(width = 0.15, alpha = 0.5, size = 1) +
    ggplot2::scale_fill_manual(values = pal, guide = "none") +
    ggplot2::labs(x = NULL, y = vcol) +
    .fig_theme("generic")
}

# --- numeric branch orchestrator ---
.gc_numeric <- function(spec) {
  p <- .gc_prep(spec)
  df <- p$df; ng <- length(p$groups)
  if (ng < 2) stop("Group comparison needs at least two groups.")

  override <- spec$options$test %||% "auto"
  # Decide parametric vs non-parametric ONCE on pooled group-mean-centered values,
  # reusing Summary's normality logic; override wins if set.
  if (override == "auto") {
    centered <- df$value - stats::ave(df$value, df$group)
    dec <- .summary_decide(centered)
    nonpar <- dec$kind == "median"
    reason <- sprintf(" (%s)", dec$reason)
  } else {
    nonpar <- override == "nonparametric"
    reason <- " (user-selected)"
  }

  if (ng == 2) {
    if (nonpar) { test_expr <- quote(wilcox.test(value ~ group, data = dat))
                  tname <- "Mann–Whitney U test" }
    else        { test_expr <- quote(t.test(value ~ group, data = dat))
                  tname <- "Welch t-test" }
  } else {
    if (nonpar) { test_expr <- quote(kruskal.test(value ~ group, data = dat))
                  tname <- "Kruskal–Wallis test" }
    else        { test_expr <- quote(oneway.test(value ~ group, data = dat))
                  tname <- "one-way ANOVA (Welch)" }
  }
  # Evaluate the SAME expression the script will show. Bindings are explicit
  # so nothing depends on the search path; suppressWarnings wraps only this
  # library call (wilcox.test warns on ties).
  ht <- suppressWarnings(eval(test_expr, list(dat = df,
    t.test = stats::t.test, wilcox.test = stats::wilcox.test,
    kruskal.test = stats::kruskal.test, oneway.test = stats::oneway.test)))
  eff <- if (ng == 2 && !nonpar) .gc_effect_t(df)
    else if (ng == 2) .gc_effect_wilcox(df, unname(ht$statistic))
    else if (!nonpar) .gc_effect_anova(df)
    else .gc_effect_kruskal(unname(ht$statistic), nrow(df))
  pv <- ht$p.value
  pfmt <- if (pv < 0.001) "p < 0.001" else sprintf("p = %.3f", pv)

  # Per-group summary in the same mean/median idiom as Summary.
  kind <- if (nonpar) "median" else "mean"
  summ <- vapply(p$groups, function(gname)
    sprintf("%s %s", gname, .fmt_continuous(df$value[df$group == gname], kind)),
    character(1))
  notes <- ""
  if (p$n_small > 0) notes <- paste0(notes, sprintf(
    " %d row(s) in groups with <2 values were dropped.", p$n_small))
  if (p$n_na > 0) notes <- paste0(notes, sprintf(
    " %d row(s) with missing values were excluded.", p$n_na))

  posthoc <- .gc_posthoc(df, ng, nonpar, pv)   # "" until Task 3; then a sentence

  txt <- sprintf("%s across groups: %s. %s%s: %s, %s.%s%s",
    p$vcol, paste(summ, collapse = "; "), tname, reason, pfmt, eff, posthoc, notes)
  gg <- .gc_numeric_plot(df, p$vcol, spec$options$plot %||% "box")
  list(svg = .svg_string(gg, width = 6, height = 4.5), text = txt,
       code = .gc_script_numeric(spec, test_expr, tname, reason, nonpar, ng))
}

# --- categorical branch: contingency table -> chi-square/Fisher + effect size ---
.gc_categorical <- function(spec) {
  gcol <- spec$roles$group; vcol <- spec$roles$outcome
  rows <- spec$data
  grp <- .char_col(rows, gcol); out <- .char_col(rows, vcol)
  grp[!is.na(grp) & grp == ""] <- NA
  out[!is.na(out) & out == ""] <- NA
  keep <- !is.na(grp) & !is.na(out)
  n_na <- sum(!keep)
  grp <- grp[keep]; out <- out[keep]
  if (length(unique(grp)) < 2) stop("Group comparison needs at least two groups.")
  tab <- table(outcome = out, group = grp)
  n <- sum(tab)

  # Expected-count rule: any expected cell < 5 -> Fisher.
  suppressWarnings({ chi <- stats::chisq.test(tab, correct = FALSE) })
  use_fisher <- any(chi$expected < 5)
  if (use_fisher) {
    test_expr <- quote(fisher.test(tab)); tname <- "Fisher's exact test"
    ht <- eval(test_expr, list(tab = tab, fisher.test = stats::fisher.test))
  } else {
    # chi was computed above with this exact call; the deparsed expression in
    # the script is therefore still the call that ran.
    test_expr <- quote(chisq.test(tab, correct = FALSE))
    ht <- chi; tname <- "Pearson chi-square test"
  }
  pv <- ht$p.value
  pfmt <- if (pv < 0.001) "p < 0.001" else sprintf("p = %.3f", pv)

  # Cramér's V from the (unconditional) chi-square statistic.
  V <- sqrt(unname(chi$statistic) / (n * (min(dim(tab)) - 1)))
  eff <- sprintf("Cramér's V = %s", .fmt_num(V))
  # Odds ratio + CI only for 2x2.
  if (all(dim(tab) == 2)) {
    a <- tab[1,1]; b <- tab[1,2]; c <- tab[2,1]; d <- tab[2,2]
    # Haldane-Anscombe: a zero cell makes OR/CI Inf/NaN; add 0.5 to all cells.
    corrected <- any(c(a, b, c, d) == 0)
    if (corrected) { a <- a + 0.5; b <- b + 0.5; c <- c + 0.5; d <- d + 0.5 }
    or <- (a * d) / (b * c)
    se <- sqrt(1/a + 1/b + 1/c + 1/d)
    lo <- exp(log(or) - 1.96 * se); hi <- exp(log(or) + 1.96 * se)
    # State the event level and reference group the OR is FOR (built from tab[1,1]).
    or_name <- sprintf("odds ratio for %s=%s, %s vs %s",
      vcol, rownames(tab)[1], colnames(tab)[1], colnames(tab)[2])
    or_phrase <- .gc_ci_phrase(or, lo, hi, or_name)
    if (corrected) or_phrase <- paste0(or_phrase, " (0.5 continuity correction applied)")
    eff <- paste0(eff, "; ", or_phrase)
  }

  # Proportion bar chart of the contingency table.
  dfp <- as.data.frame(tab, stringsAsFactors = FALSE)  # cols: outcome, group, Freq
  pal <- .km_palette(length(unique(dfp$outcome)))
  gg <- ggplot2::ggplot(dfp,
      ggplot2::aes(x = group, y = Freq, fill = outcome)) +
    ggplot2::geom_col(position = "fill") +
    ggplot2::scale_fill_manual(values = pal) +
    ggplot2::labs(x = NULL, y = "proportion", fill = vcol) +
    .fig_theme("generic")

  notes <- if (n_na > 0) sprintf(" %d row(s) with missing values were excluded.", n_na) else ""
  txt <- sprintf("%s by group (n = %d): %s: %s, %s.%s",
    vcol, n, tname, pfmt, eff, notes)
  list(svg = .svg_string(gg, width = 6, height = 4.5), text = txt,
       code = .gc_script_categorical(spec, test_expr, tname,
                                     is_2x2 = all(dim(tab) == 2)))
}

# Post-hoc for 3+ groups when the omnibus test is significant (p < 0.05).
# Parametric -> Tukey HSD; non-parametric -> hand-computed Dunn with BH adjust.
.gc_posthoc <- function(df, ng, nonpar, pv) {
  if (ng < 3 || pv >= 0.05) return("")
  lv <- sort(unique(df$group))
  if (!nonpar) {
    tk <- stats::TukeyHSD(stats::aov(value ~ group, data = df))$group
    sig <- rownames(tk)[tk[, "p adj"] < 0.05]
    if (length(sig) == 0) return(" Tukey HSD: no pairwise differences at 0.05.")
    return(sprintf(" Tukey HSD, significant pairs: %s.", paste(sig, collapse = ", ")))
  }
  # Dunn's test: pairwise rank-sum z from the SHARED overall ranking.
  r <- rank(df$value); N <- nrow(df)
  # tie correction for the variance term
  ties <- table(df$value); tie_term <- sum(ties^3 - ties)
  Rbar <- tapply(r, df$group, mean); nvec <- tapply(r, df$group, length)
  pairs <- utils::combn(lv, 2, simplify = FALSE)
  zp <- lapply(pairs, function(pr) {
    i <- pr[1]; j <- pr[2]
    sigma <- sqrt((N * (N + 1) / 12 - tie_term / (12 * (N - 1))) *
                    (1 / nvec[[i]] + 1 / nvec[[j]]))
    z <- (Rbar[[i]] - Rbar[[j]]) / sigma
    list(pair = paste(i, j, sep = "-"), p = 2 * stats::pnorm(-abs(z)))
  })
  praw <- vapply(zp, function(x) x$p, numeric(1))
  padj <- stats::p.adjust(praw, method = "BH")
  sig <- vapply(zp, function(x) x$pair, character(1))[padj < 0.05]
  if (length(sig) == 0) return(" Dunn's test (BH-adjusted): no pairwise differences at 0.05.")
  sprintf(" Dunn's test (BH-adjusted), significant pairs: %s.", paste(sig, collapse = ", "))
}

fig_groupcompare <- function(spec) {
  rows <- spec$data
  if (is.null(rows) || length(rows) == 0) stop("No data rows provided.")
  gcol <- spec$roles$group; vcol <- spec$roles$outcome
  if (is.null(gcol) || is.null(vcol)) stop("Choose a group column and an outcome column.")
  have <- names(rows[[1]])
  if (!(gcol %in% have)) stop(sprintf("Column '%s' not found in the data.", gcol))
  if (!(vcol %in% have)) stop(sprintf("Column '%s' not found in the data.", vcol))
  if (.gc_is_numeric_col(rows, vcol)) .gc_numeric(spec) else .gc_categorical(spec)
}

# --- downloadable R script builders ------------------------------------------

# Prep lines shared by both branches: build `dat` from the role columns.
.gc_script_prep <- function(spec, outcome_numeric) {
  qe <- function(s) gsub('"', '\\\\"', s)
  coerce <- if (outcome_numeric) "as.numeric" else "as.character"
  c("# Prepare: outcome + group, drop rows with missing values",
    sprintf('dat <- data.frame(value = %s(df[["%s"]]),',
            coerce, qe(spec$roles$outcome)),
    sprintf('                  group = as.character(df[["%s"]]),',
            qe(spec$roles$group)),
    "                  stringsAsFactors = FALSE)",
    "dat <- dat[!is.na(dat$value) & !is.na(dat$group), ]")
}

.gc_script_numeric <- function(spec, test_expr, tname, reason, nonpar, ng) {
  # Effect-size helpers embedded verbatim (dependency order matters).
  helpers <- c(.script_fun(".fmt_num", .fmt_num),
               .script_fun(".gc_ci_phrase", .gc_ci_phrase))
  if (ng == 2 && !nonpar) {
    helpers <- c(helpers, .script_fun(".gc_effect_t", .gc_effect_t))
    eff_call <- ".gc_effect_t(dat)"
  } else if (ng == 2) {
    helpers <- c(helpers, .script_fun(".gc_effect_wilcox", .gc_effect_wilcox))
    eff_call <- ".gc_effect_wilcox(dat, unname(ht$statistic))"
  } else if (!nonpar) {
    helpers <- c(helpers, .script_fun(".gc_eta_ci", .gc_eta_ci),
                 .script_fun(".gc_effect_anova", .gc_effect_anova))
    eff_call <- ".gc_effect_anova(dat)"
  } else {
    helpers <- c(helpers, .script_fun(".gc_effect_kruskal", .gc_effect_kruskal))
    eff_call <- ".gc_effect_kruskal(unname(ht$statistic), nrow(dat))"
  }
  posthoc <- if (ng >= 3)
    c(.script_fun(".gc_posthoc", .gc_posthoc),
      sprintf("cat(.gc_posthoc(dat, %d, nonpar = %s, pv = ht$p.value), \"\\n\")",
              ng, if (nonpar) "TRUE" else "FALSE"), "")
    else character(0)
  violin <- identical(spec$options$plot %||% "box", "violin")
  qe <- function(s) gsub('"', '\\\\"', s)
  body <- c(.gc_script_prep(spec, outcome_numeric = TRUE),
    "# groups with fewer than 2 values cannot be compared",
    "dat <- dat[dat$group %in% names(which(table(dat$group) >= 2)), ]", "",
    sprintf("# %s%s", tname, reason),
    paste0("ht <- ", .script_dep(test_expr)), "ht", "",
    "# Effect size (the app's own computation, embedded verbatim):",
    helpers,
    paste0("cat(", eff_call, ", \"\\n\")"), "",
    posthoc,
    "# Equivalent figure:",
    "library(ggplot2)",
    "p <- ggplot(dat, aes(x = group, y = value, fill = group)) +",
    if (violin) '  geom_violin(trim = FALSE, colour = "grey30") +'
    else '  geom_boxplot(outlier.shape = NA, colour = "grey30") +',
    "  geom_jitter(width = 0.15, alpha = 0.5, size = 1) +",
    '  guides(fill = "none") +',
    sprintf('  labs(x = NULL, y = "%s") +', qe(spec$roles$outcome)),
    "  theme_minimal(base_size = 12)",
    '# print(p)   # or: ggsave("comparison.pdf", p, width = 6, height = 4.5)')
  .script_assemble("Group comparison", spec,
                   c(spec$roles$group, spec$roles$outcome), "ggplot2", body)
}

.gc_script_categorical <- function(spec, test_expr, tname, is_2x2) {
  or_lines <- if (is_2x2) c(
    "# Odds ratio (2x2 only; 0.5 added to every cell if any cell is zero):",
    "n11 <- tab[1, 1]; n12 <- tab[1, 2]; n21 <- tab[2, 1]; n22 <- tab[2, 2]",
    "if (any(c(n11, n12, n21, n22) == 0)) { n11 <- n11 + 0.5; n12 <- n12 + 0.5; n21 <- n21 + 0.5; n22 <- n22 + 0.5 }",
    "or <- (n11 * n22) / (n12 * n21)",
    "se <- sqrt(1/n11 + 1/n12 + 1/n21 + 1/n22)",
    "c(or = or, lo = exp(log(or) - 1.96 * se), hi = exp(log(or) + 1.96 * se))", "")
    else character(0)
  body <- c(.gc_script_prep(spec, outcome_numeric = FALSE), "",
    "tab <- table(outcome = dat$value, group = dat$group)",
    "tab", "",
    "# Expected-count rule the app applied: any expected cell < 5 -> Fisher",
    "suppressWarnings(chisq.test(tab, correct = FALSE))$expected", "",
    sprintf("# %s", tname),
    paste0("ht <- ", .script_dep(test_expr)), "ht", "",
    "# Cramér's V from the (unconditional) chi-square statistic:",
    "V <- sqrt(unname(suppressWarnings(chisq.test(tab, correct = FALSE))$statistic) /",
    "  (sum(tab) * (min(dim(tab)) - 1)))",
    "V", "",
    or_lines,
    "# Equivalent figure:",
    "library(ggplot2)",
    "dfp <- as.data.frame(tab, stringsAsFactors = FALSE)",
    "p <- ggplot(dfp, aes(x = group, y = Freq, fill = outcome)) +",
    '  geom_col(position = "fill") +',
    '  labs(x = NULL, y = "proportion") +',
    "  theme_minimal(base_size = 12)",
    '# print(p)   # or: ggsave("comparison.pdf", p, width = 6, height = 4.5)')
  .script_assemble("Group comparison", spec,
                   c(spec$roles$group, spec$roles$outcome), "ggplot2", body)
}

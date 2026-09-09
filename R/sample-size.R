# Sample-size planning. Independent of the figure dispatcher so the planner can
# boot with stats, pwr and jsonlite only. All n arguments are ANALYZABLE units.
# Catalogue/unit contracts: docs/superpowers/specs/2026-09-09-sample-size-workspace.md

.ss_methods <- function() c("two_mean", "paired_mean", "one_mean", "anova",
  "correlation", "regression", "chi_square", "two_proportion", "one_proportion",
  "ni_mean", "equivalence_mean", "survival", "cluster_mean",
  "precision_mean", "precision_proportion")

.ss_number <- function(p, key, default, min = -Inf, max = Inf, integer = FALSE) {
  x <- p[[key]]
  if (is.null(x)) x <- default
  if (!is.numeric(x) || length(x) != 1L || !is.finite(x) || x < min || x > max ||
      (integer && x != floor(x))) stop(sprintf("%s must be %sa number between %s and %s.",
        key, if (integer) "an integer; " else "", min, max), call. = FALSE)
  x
}

.ss_prepare <- function(spec) {
  if (!is.list(spec) || !is.character(spec$method) || length(spec$method) != 1 ||
      !spec$method %in% .ss_methods()) stop("Choose a supported study design.", call. = FALSE)
  m <- spec$method
  p <- spec$params
  if (is.null(p)) p <- list()
  if (!is.list(p)) stop("Parameters must be an object.", call. = FALSE)
  out <- list(method = m,
    alpha = .ss_number(p, "alpha", .05, .00001, .25),
    target = .ss_number(p, "target", .8, .5, .9999),
    dropout = .ss_number(p, "dropout", 0, 0, .8),
    n = .ss_number(p, "n", 64, 2, 1e7, TRUE),
    sides = .ss_number(p, "sides", 2, 1, 2, TRUE),
    ratio = .ss_number(p, "ratio", 1, .1, 10))
  # Validate only parameters applicable to the selected design; unrelated UI
  # state cannot accidentally change the model.
  if (m %in% c("two_mean", "paired_mean", "one_mean", "ni_mean", "equivalence_mean", "cluster_mean"))
    out$delta <- .ss_number(p, "delta", .5, -1e6, 1e6)
  if (m %in% c("two_mean", "paired_mean", "one_mean", "ni_mean", "equivalence_mean", "cluster_mean", "precision_mean"))
    out$sd <- .ss_number(p, "sd", 1, 1e-8, 1e8)
  if (m %in% c("ni_mean", "equivalence_mean")) {
    out$margin <- .ss_number(p, "margin", .3, 1e-8, 1e6)
    out$sides <- 1
  }
  if (m == "anova") {
    out$groups <- .ss_number(p, "groups", 3, 2, 100, TRUE)
    out$f <- .ss_number(p, "f", .25, 0, 10)
  }
  if (m == "correlation") out$r <- .ss_number(p, "r", .3, -.999, .999)
  if (m == "regression") {
    out$predictors <- .ss_number(p, "predictors", 3, 1, 100, TRUE)
    out$f2 <- .ss_number(p, "f2", .15, 0, 100)
  }
  if (m == "chi_square") {
    out$df <- .ss_number(p, "df", 2, 1, 1000, TRUE)
    out$w <- .ss_number(p, "w", .3, 0, 10)
  }
  if (m %in% c("one_proportion", "two_proportion", "precision_proportion"))
    out$p1 <- .ss_number(p, "p1", .5, .0001, .9999)
  if (m %in% c("one_proportion", "two_proportion"))
    out$p2 <- .ss_number(p, "p2", .65, .0001, .9999)
  if (m == "survival") {
    out$hr <- .ss_number(p, "hr", .7, .01, 100)
    out$event_fraction <- .ss_number(p, "event_fraction", .6, .001, 1)
  }
  if (m == "cluster_mean") {
    out$cluster_size <- .ss_number(p, "cluster_size", 20, 2, 1e5, TRUE)
    out$icc <- .ss_number(p, "icc", .05, 0, .99)
  }
  if (m %in% c("precision_mean", "precision_proportion")) {
    out$width <- .ss_number(p, "width", if (m == "precision_mean") .2 else .05, 1e-6, 1e6)
    out$sides <- 2
    if (m == "precision_proportion" && out$width >= .5)
      stop("A proportion interval half-width must be less than 0.5.", call. = FALSE)
  }
  out
}

.ss_min_n <- function(p) {
  if (p$method %in% c("two_mean", "two_proportion", "cluster_mean"))
    return(max(2, floor(1 / p$ratio) + 1))
  switch(p$method, correlation = 4, regression = p$predictors + 3, 2)
}

.ss_two_groups <- function(m) m %in% c("two_mean", "two_proportion", "ni_mean",
  "equivalence_mean", "survival", "cluster_mean")

.ss_metric <- function(p, n) {
  m <- p$method
  n2 <- ceiling(n * p$ratio)
  a <- p$alpha
  alternative <- if (p$sides == 2) "two.sided" else "greater"
  if (m == "two_mean") return(pwr::pwr.t2n.test(n1 = n, n2 = n2,
    d = abs(p$delta) / p$sd, sig.level = a, alternative = alternative)$power)
  if (m %in% c("paired_mean", "one_mean")) return(pwr::pwr.t.test(n = n,
    d = abs(p$delta) / p$sd, sig.level = a,
    type = if (m == "paired_mean") "paired" else "one.sample", alternative = alternative)$power)
  if (m == "anova") return(pwr::pwr.anova.test(k = p$groups, n = n, f = p$f, sig.level = a)$power)
  if (m == "correlation") return(pwr::pwr.r.test(n = n, r = abs(p$r), sig.level = a, alternative = alternative)$power)
  if (m == "regression") return(pwr::pwr.f2.test(u = p$predictors,
    v = n - p$predictors - 1, f2 = p$f2, sig.level = a)$power)
  if (m == "chi_square") return(pwr::pwr.chisq.test(N = n, w = p$w, df = p$df, sig.level = a)$power)
  if (m %in% c("one_proportion", "two_proportion")) {
    h <- abs(pwr::ES.h(p$p2, p$p1))
    if (m == "one_proportion") return(pwr::pwr.p.test(n = n, h = h,
      sig.level = a, alternative = alternative)$power)
    return(pwr::pwr.2p2n.test(n1 = n, n2 = n2, h = h,
      sig.level = a, alternative = alternative)$power)
  }
  if (m %in% c("ni_mean", "equivalence_mean")) {
    se <- p$sd * sqrt(1 / n + 1 / n2)
    z <- stats::qnorm(1 - a)
    if (m == "ni_mean") return(stats::pnorm((p$delta + p$margin) / se - z))
    return(max(0, stats::pnorm((p$margin - p$delta) / se - z) -
      stats::pnorm((-p$margin - p$delta) / se + z)))
  }
  if (m == "survival") {
    allocation <- n2 / (n + n2)
    events <- (n + n2) * p$event_fraction
    drift <- abs(log(p$hr)) * sqrt(events * allocation * (1 - allocation))
    z <- stats::qnorm(1 - a / p$sides)
    return(stats::pnorm(drift - z) + if (p$sides == 2) stats::pnorm(-drift - z) else 0)
  }
  if (m == "cluster_mean") {
    cluster_sd <- p$sd * sqrt(p$icc + (1 - p$icc) / p$cluster_size)
    return(pwr::pwr.t2n.test(n1 = n, n2 = n2, d = abs(p$delta) / cluster_sd,
      sig.level = a, alternative = alternative)$power)
  }
  if (m == "precision_mean") return(stats::qt(1 - a / 2, n - 1) * p$sd / sqrt(n))
  if (m == "precision_proportion") {
    z <- stats::qnorm(1 - a / 2)
    return(z / (1 + z^2 / n) * sqrt(p$p1 * (1 - p$p1) / n + z^2 / (4 * n^2)))
  }
  stop("Unsupported method.", call. = FALSE)
}

.ss_size <- function(p) {
  precision <- startsWith(p$method, "precision_")
  passes <- function(n) {
    value <- .ss_metric(p, n)
    if (!is.finite(value)) stop("The calculation is not finite under these assumptions.", call. = FALSE)
    if (precision) value <= p$width else value >= p$target
  }
  lo <- .ss_min_n(p)
  if (passes(lo)) return(lo)
  hi <- lo
  while (!passes(hi)) {
    if (hi >= 1e7) stop("The required size exceeds 10 million planning units. Revisit the assumptions.", call. = FALSE)
    hi <- min(1e7, hi * 2)
  }
  # Integer search with the real rounded allocation at every candidate.
  while (hi - lo > 1) {
    mid <- floor((lo + hi) / 2)
    if (passes(mid)) hi <- mid else lo <- mid
  }
  hi
}

.ss_effect_info <- function(p) {
  m <- p$method
  if (m %in% c("two_mean", "paired_mean", "one_mean", "cluster_mean"))
    return(list(key = "delta", label = "Difference in outcome units", upper = min(1e6, p$sd * 100),
      direction = if (p$delta < 0) -1 else 1))
  if (m == "correlation") return(list(key = "r", label = "Pearson correlation", upper = .999,
    direction = if (p$r < 0) -1 else 1))
  if (m == "anova") return(list(key = "f", label = "Cohen's f", upper = 10, direction = 1))
  if (m == "regression") return(list(key = "f2", label = "Cohen's f²", upper = 100, direction = 1))
  if (m == "chi_square") return(list(key = "w", label = "Cohen's w", upper = 10, direction = 1))
  if (m %in% c("one_proportion", "two_proportion")) return(list(key = "p2",
    label = if (m == "one_proportion") "Alternative proportion" else "Group 2 proportion",
    upper = if (p$p2 >= p$p1) .9999 - p$p1 else p$p1 - .0001,
    direction = if (p$p2 >= p$p1) 1 else -1))
  if (m == "survival") return(list(key = "hr", label = "Hazard ratio", upper = log(100),
    direction = if (p$hr <= 1) -1 else 1))
  NULL
}

.ss_set_effect <- function(p, x, info) {
  p[[info$key]] <- if (info$key == "p2") p$p1 + info$direction * x else
    if (info$key == "hr") exp(info$direction * x) else info$direction * x
  p
}

.ss_counts <- function(p, n) {
  m <- p$method
  n2 <- if (.ss_two_groups(m)) ceiling(n * p$ratio) else NULL
  k <- if (m == "anova") p$groups else if (!is.null(n2)) 2 else 1
  sizes <- if (m == "anova") rep(n, k) else if (!is.null(n2)) c(n, n2) else n
  recruit <- ceiling(sizes / (1 - p$dropout))
  list(n = n, n2 = n2, groups = k, analyzable = sum(sizes), recruit = sum(recruit),
    per_group = sizes, recruit_per_group = recruit,
    unit = if (m == "cluster_mean") "clusters" else if (m == "paired_mean") "complete pairs" else "participants",
    participants = if (m == "cluster_mean") sum(recruit) * p$cluster_size else sum(recruit),
    events = if (m == "survival") ceiling(sum(sizes) * p$event_fraction) else NULL)
}

.ss_reference <- function(m) {
  if (m == "survival") return(list(label = "Schoenfeld (1983), proportional-hazards approximation",
    url = "https://www.biostat.wisc.edu/~chappell/641/papers/paper31.pdf"))
  if (m %in% c("ni_mean", "equivalence_mean")) return(list(
    label = "Normal approximation; independent means with common planning SD",
    url = paste0("https://www.sealedenvelope.com/power/continuous-",
      if (m == "ni_mean") "noninferior/" else "equivalence/")))
  if (m == "precision_proportion") return(list(label = "Wilson score interval, planning half-width",
    url = "https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm"))
  if (m == "precision_mean") return(list(label = "Student t confidence interval, planning SD",
    url = "https://stat.ethz.ch/R-manual/R-devel/library/stats/html/t.test.html"))
  list(label = if (m == "cluster_mean") "Cluster-mean t-test; common ICC and equal cluster sizes" else
    "pwr: Cohen (1988) power calculations", url = "https://cran.r-project.org/web/packages/pwr/pwr.pdf")
}

.ss_notes <- function(p) {
  common <- c("Planning calculations depend on the stated effect, variability and design assumptions; they do not establish those assumptions.",
    "Use an effect justified by prior evidence or scientific importance. Changing assumptions to obtain a convenient sample size changes the design question.")
  specific <- switch(p$method,
    two_mean = "Independent observations, common population SD and a two-sample t-test. Unequal variances require a different planning model.",
    paired_mean = "n counts complete pairs. SD is the SD of within-pair differences, not the SD of either occasion. This is not a repeated-measures interaction or mixed-model calculation.",
    one_mean = "Independent observations and a one-sample t-test against a specified reference mean.",
    anova = "Balanced, independent groups; common within-group SD. Omnibus one-way ANOVA power is not power for individual post-hoc contrasts or repeated measures.",
    correlation = "Pearson correlation against zero, using pwr's Fisher-z approximation with its small-sample adjustment; independent bivariate-normal pairs.",
    regression = "Omnibus fixed-model F-test of all listed slope parameters against zero. f² = R²/(1−R²); this does not power an individual predictor or a multilevel model.",
    chi_square = "Noncentral chi-square approximation. Specify Cohen's w from expected and alternative cell probabilities, and the test's degrees of freedom. Sparse expected cells can invalidate the approximation.",
    two_proportion = "Independent groups; Cohen's arcsine-transformed normal approximation, without continuity correction. This is not Fisher's exact-test power.",
    one_proportion = "One-sample arcsine-transformed normal approximation against the reference proportion. This is not exact binomial-test power.",
    ni_mean = "Higher outcomes are better. The null boundary is difference = −margin. Uses a one-sided normal approximation with a common planning SD; justify the margin scientifically.",
    equivalence_mean = "Equivalence bounds are −margin and +margin. Power is the joint probability of both one-sided z tests rejecting at the displayed per-test alpha; common planning SD. It is not power for a nonsignificant superiority test.",
    survival = "Two groups and proportional hazards. The event fraction is the expected proportion with an observed event by analysis; accrual, competing risks and time-varying effects are not modelled. Do not count event censoring again as generic attrition.",
    cluster_mean = "A cluster-level t-test for equal fixed cluster sizes, common ICC and independent clusters. Cluster-mean SD = individual SD × sqrt(ICC + (1−ICC)/cluster size). Attrition here means loss of whole clusters.",
    precision_mean = "Half-width of a two-sided t interval using the assumed SD. Realized SD and interval width vary; this is not an assurance calculation.",
    precision_proportion = "Wilson interval half-width at the anticipated proportion, which can be fractional at a proposed n. This is not a guarantee of realized width or an assurance calculation.")
  notes <- c(specific, common)
  if (p$sides == 1 && !p$method %in% c("ni_mean", "equivalence_mean", "anova", "regression", "chi_square"))
    notes <- c(notes, "The one-sided alternative is in the direction of the specified effect; choose that direction before observing results.")
  if (p$method %in% c("one_proportion", "two_proportion") &&
      min(p$p1, p$p2, 1 - p$p1, 1 - p$p2) < .05)
    notes <- c(notes, "A planning proportion is close to 0 or 1. Assess an exact or simulation-based design before using this approximation.")
  notes
}

# Public pure R API. Schema 1 plans can be saved/reopened; no patient data.
sample_size_plan <- function(spec, include_curve = TRUE) {
  p <- .ss_prepare(spec)
  precision <- startsWith(p$method, "precision_")
  solve <- spec$solve
  if (is.null(solve)) solve <- "n"
  allowed <- if (precision) c("n", "precision") else if (is.null(.ss_effect_info(p))) c("n", "power") else c("n", "power", "effect")
  if (!is.character(solve) || length(solve) != 1 || !solve %in% allowed)
    stop("This solver is not supported for the selected design.", call. = FALSE)
  if (solve != "n" && p$n < .ss_min_n(p)) stop(sprintf("This design needs at least %d analyzable units.", .ss_min_n(p)), call. = FALSE)
  if (p$method == "ni_mean" && p$delta <= -p$margin && solve == "n")
    stop("The anticipated difference must exceed the noninferiority boundary −margin.", call. = FALSE)
  if (p$method == "equivalence_mean" && abs(p$delta) >= p$margin && solve == "n")
    stop("The anticipated difference must lie strictly inside the equivalence bounds.", call. = FALSE)
  solved_effect <- NULL
  if (solve == "effect") {
    info <- .ss_effect_info(p)
    objective <- function(x) .ss_metric(.ss_set_effect(p, x, info), p$n) - p$target
    if (objective(info$upper) < 0) stop("The target power cannot be reached within the supported effect range at this sample size.", call. = FALSE)
    value <- stats::uniroot(objective, c(0, info$upper), tol = 1e-10)$root
    p <- .ss_set_effect(p, value, info)
    solved_effect <- list(label = info$label, value = p[[info$key]], key = info$key)
  }
  n <- if (solve == "n") .ss_size(p) else p$n
  p$n <- n
  metric <- .ss_metric(p, n)
  counts <- .ss_counts(p, n)
  ns <- unique(pmax(.ss_min_n(p), round(seq(max(.ss_min_n(p), n * .35), min(1e7, n * 1.8), length.out = 45))))
  curve <- if (include_curve) lapply(ns, function(x) {
    cts <- .ss_counts(p, x)
    list(n = x, total = cts$analyzable, value = .ss_metric(p, x))
  }) else list()
  reference <- .ss_reference(p$method)
  side <- if (precision) sprintf("%.3g%% confidence", 100 * (1 - p$alpha)) else
    if (p$method == "equivalence_mean") sprintf("per-test alpha %.4g", p$alpha) else
      if (p$method %in% c("anova", "regression", "chi_square")) sprintf("upper-tail alpha %.4g", p$alpha) else
      sprintf("%s alpha %.4g", if (p$sides == 2) "two-sided" else "one-sided", p$alpha)
  statement <- sprintf("Under the specified %s planning model (%s), %s analyzable %s gives %s. Recruitment after %.3g%% %s attrition is %s %s. All assumptions are recorded in the accompanying plan. Calculation: %s; R %s; pwr %s.",
    gsub("_", " ", p$method), side, counts$analyzable, counts$unit,
    if (precision) sprintf("a planned interval half-width of %.5g", metric) else sprintf("%.2f%% power", metric * 100),
    p$dropout * 100, if (p$method == "cluster_mean") "cluster" else if (p$method == "paired_mean") "pair" else "participant",
    counts$recruit, counts$unit, reference$label, getRversion(), utils::packageVersion("pwr"))
  list(schema = 1, method = p$method, solve = solve, params = p,
    counts = counts, metric = metric, metric_kind = if (precision) "precision" else "power",
    target = if (precision) p$width else p$target, effect = solved_effect,
    curve = curve, notes = as.list(.ss_notes(p)), reference = reference, statement = statement,
    engine = list(R = as.character(getRversion()), pwr = as.character(utils::packageVersion("pwr"))))
}

sample_size_script <- function(spec) {
  fns <- c(".ss_methods", ".ss_number", ".ss_prepare", ".ss_min_n", ".ss_two_groups",
    ".ss_metric", ".ss_size", ".ss_effect_info", ".ss_set_effect", ".ss_counts",
    ".ss_reference", ".ss_notes", "sample_size_plan")
  definitions <- vapply(fns, function(nm) paste0(nm, " <- ",
    paste(deparse(get(nm, envir = environment(sample_size_plan)), width.cutoff = 100), collapse = "\n")), character(1))
  paste(c("# Figura sample-size planning: complete reproducible R script.",
    "# Uses the same engine functions as the browser; assumptions are not verified by recomputation.",
    paste0("# Generated using R ", getRversion(), "; pwr ", utils::packageVersion("pwr")),
    'if (!requireNamespace("pwr", quietly = TRUE)) stop("Install the CRAN package pwr before running this script.")',
    definitions, paste0("spec <- ", paste(deparse(spec, width.cutoff = 100), collapse = "\n")),
    "result <- sample_size_plan(spec)", "print(result$counts)", "cat(result$statement, '\\n')",
    "print(result$params)"), collapse = "\n\n")
}

sample_size_json <- function(input) {
  tryCatch({
    spec <- jsonlite::fromJSON(input, simplifyVector = FALSE)
    out <- sample_size_plan(spec)
    out$script <- sample_size_script(spec)
    jsonlite::toJSON(list(ok = TRUE, result = out), auto_unbox = TRUE, digits = 12, null = "null")
  }, error = function(e) jsonlite::toJSON(list(ok = FALSE, error = conditionMessage(e)), auto_unbox = TRUE))
}

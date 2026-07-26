# Path A, FULL PRECISION. Runs the .R script Figura itself exported, in a clean
# environment, from the case directory (so its `read.csv("data.csv")` resolves),
# then harvests the model's UNROUNDED estimates. One artifact, two claims: the
# numbers behind the rounded screen cells, and proof the exported script
# reproduces what the screen showed.
#
# usage (from the repo root):
#   Rscript stats-validation/harness/run-script.R <id> <figura.json> <case-dir> <out.json>
#
# Output: {id, figure, terms: {term: {est, se, lo, hi, p}}, n, n_event, n_dropped}
# Ratio scale, Wald, literal 1.96 — the pinned convention. `se` is the RAW
# log-scale standard error (lo/hi are derived from it and kept for convenience);
# a checker that wants a different interval can rebuild it from est + se.
#
# ---------------------------------------------------------------------------
# CONTRACT FOR LATER ANALYSIS TASKS
#
# The harvest is per figure, dispatched on `figure` in <case-dir>/case.json.
# To add one: write `harvest_<figure>(env, id)` and register it in HARVESTERS.
# The function receives the environment the exported script was sourced into
# (the process cwd is the case dir while it runs, so `read.csv("data.csv")` and
# friends work) and returns a NAMED LIST that is merged into the payload beside
# `id` and `figure`. Unregistered figures stop loudly — never harvest a figure
# through another figure's assumptions.
#
#   cox          — coxph. Harvest summary(fit)$coefficients BY COLUMN NAME:
#                  "coef" / "se(coef)" / "Pr(>|z|)" (NOT glm's "Estimate" /
#                  "Std. Error"). Same terms/counts shape as logistic.
#   km           — add `curve`: per stratum {t, surv, at_risk} from
#                  summary(survfit); strip the "group=" prefix off strata names.
#   groupcompare — the test object's `ht$p.value` / `ht$statistic`, plus counts.
#   summary      — counts only.
#
# HARVEST BY COLUMN NAME, NEVER BY POSITION. Column order differs between model
# classes and a positional harvest returns a plausible wrong number in silence;
# ratio_terms() below stops instead when a named column is absent.
# ---------------------------------------------------------------------------

# ---- shared helpers -------------------------------------------------------

# Write Figura's exported code to a temp file and source it into a clean
# environment. parent = globalenv() so the script's library() calls resolve,
# while nothing this harness defines can shadow a name the script relies on.
source_export <- function(code, id) {
  if (is.null(code) || length(code) != 1L || is.na(code) || !nzchar(code))
    stop(sprintf("no exported code for %s", id))
  script_file <- file.path(tempdir(), sprintf("%s-export.R", id))
  writeLines(code, script_file)
  env <- new.env(parent = globalenv())
  source(script_file, local = env, echo = FALSE)
  env
}

# Fetch an object the exported script must have defined. inherits = FALSE: a
# name that leaked in from globalenv() is not evidence about the script.
need <- function(env, nm, id) {
  if (!exists(nm, envir = env, inherits = FALSE))
    stop(sprintf("exported script for %s defined no `%s` object", id, nm))
  get(nm, envir = env, inherits = FALSE)
}

# Ratio-scale Wald terms from a coefficient matrix, addressed BY COLUMN NAME.
# The intercept is dropped; term names are the rownames as-is (they are the
# coefficient keys the app's own table is built from, so they stay comparable).
ratio_terms <- function(sm, est_col, se_col, p_col) {
  for (cn in c(est_col, se_col, p_col))
    if (!(cn %in% colnames(sm)))
      stop(sprintf("coefficient matrix has no `%s` column (columns: %s)",
                   cn, paste(colnames(sm), collapse = ", ")))
  keys <- setdiff(rownames(sm), "(Intercept)")
  out <- lapply(keys, function(k) {
    est <- unname(sm[k, est_col]); se <- unname(sm[k, se_col])
    list(est = exp(est), se = se,
         lo = exp(est - 1.96 * se), hi = exp(est + 1.96 * se),
         p = unname(sm[k, p_col]))
  })
  names(out) <- keys
  out
}

# Rows the exported script's complete.cases step removed. Read the raw CSV the
# same way the script does — we are already in the case dir when this runs.
n_dropped_vs_csv <- function(dat) {
  raw <- utils::read.csv("data.csv", check.names = FALSE)
  nrow(raw) - nrow(dat)
}

# ---- per-figure harvesters ------------------------------------------------

# glm: summary()$coefficients columns are "Estimate" / "Std. Error" /
# "Pr(>|z|)". `dat` is the script's complete-case frame; `.y` is its 0/1 outcome
# (both names come from .logistic_script in R/logistic.R).
harvest_logistic <- function(env, id) {
  fit <- need(env, "fit", id)
  dat <- need(env, "dat", id)
  sm <- summary(fit)$coefficients
  list(terms = ratio_terms(sm, "Estimate", "Std. Error", "Pr(>|z|)"),
       n = nrow(dat),
       n_event = sum(dat$.y == 1),
       n_dropped = n_dropped_vs_csv(dat))
}

# coxph: summary()$coefficients columns are "coef" / "se(coef)" / "Pr(>|z|)"
# (NOT glm's "Estimate" / "Std. Error"). `dat` is the script's complete-case
# frame with a 0/1 `status` column (both names come from .cox_script in
# R/cox.R, verified against its `dat <- data.frame(time = ..., status = ...)`
# and `fit <- coxph(Surv(time, status) ~ ..., data = dat)`).
#
# KNOWN DISPLAY NUANCE (cox only): ratio_terms() above derives lo/hi with the
# literal 1.96, per the pinned convention this whole file follows. The APP's
# own on-screen cell (.cox_hr_cell / .cox_rows in R/cox.R) instead calls
# `stats::confint()` on the joint coxph fit, and `survival` defines no
# `confint.coxph` method, so that call falls through to `confint.default`,
# which uses the exact normal quantile qnorm(0.975) = 1.959963985 — not
# 1.96. (Logistic has no such gap: R/logistic.R hand-computes its displayed
# CI with the literal 1.96 directly.) The two z constants agree to ~1.8e-5
# relative, almost always invisible after 2-dp rounding, but a bound sitting
# right at a `.xx5` boundary can round to a different digit under each
# constant — which would surface here as a spurious SCRIPT_DIVERGENCE
# (compare.py's script tier does an exact string compare of this harvest's
# rendered cell against the app's displayed cell). Do NOT change the literal
# 1.96 here to "fix" that; see spec/cox-adjusted.md's "Known display
# nuance" section.
harvest_cox <- function(env, id) {
  fit <- need(env, "fit", id)
  dat <- need(env, "dat", id)
  sm <- summary(fit)$coefficients
  list(terms = ratio_terms(sm, "coef", "se(coef)", "Pr(>|z|)"),
       n = nrow(dat),
       n_event = sum(dat$status == 1),
       n_dropped = n_dropped_vs_csv(dat))
}

# survfit + survdiff. Verified against R/km.R's .km_script (both the
# source_roles branch, used here since our case sets source_filename, and the
# embedded-demo branch) before writing this: it always assigns `fit <-
# survfit(Surv(time, status) ~ group, data = dat)` and `dat <-
# data.frame(time = ..., status = ..., group = ..., stringsAsFactors = FALSE)`
# with columns literally named time/status/group — never the user's real
# column names, which only ever appear in the PREP lines that build `dat`.
# Whenever the script's group count is >= 2 (always true for a real two-arm
# km case, and true here) it ALSO assigns `lr <- survdiff(Surv(time, status)
# ~ group, data = dat)` — but the log-rank P-VALUE itself is only ever a bare
# printed expression in the exported script (`1 - pchisq(lr$chisq, ...)`,
# never assigned to a name), so this harvester recomputes it from `lr` with
# the IDENTICAL formula fig_km itself uses. If a future single-group km case
# ever reaches this harvester, `lr` will not exist (fig_km never computes a
# log-rank stat for one group either); logrank_p is harvested as NA (-> JSON
# null) rather than failing loudly, since there is genuinely nothing to
# harvest, not a bug.
# Group label(s) for one survfit summary object, shared by BOTH the curve
# (per-point strata) and the medians table (per-row rownames) so the two can
# never disagree about a group's key. `x` is `sf$strata` (curve; NULL for a
# single-group fit) or `rownames(med_tab)` (medians; ALSO NULL for a
# single-group fit — `summary(fit)$table` for one group is a plain named
# vector with no per-group name at all, and the `t(as.matrix(...))` reshape
# below that gives it a `dim` carries the reshape's OWN row/col labels, not a
# group name, so `rownames(med_tab)` stays NULL after it too). Genuinely
# mirrors fig_km's own median-line fallback (R/km.R:140:
# `rownames(med_tab)[i] %||% as.character(unique(df$group)[i])`) rather than
# a synthetic sentinel like "Overall": the real, single group value carried
# in the exported script's complete-case frame, so a one-group case's curve
# and medians share the SAME key the app's own displayed line would use —
# and that key is one of the "literal group-column strings" the interface
# contract (INTERFACES.md) requires, which "Overall" would not be.
.km_group_labels <- function(x, group_col, n = 1L) {
  if (is.null(x)) rep(as.character(unique(group_col))[1], n)
  else sub("^group=", "", as.character(x))
}

harvest_km <- function(env, id) {
  fit <- need(env, "fit", id)
  dat <- need(env, "dat", id)

  # summary(fit) WITHOUT censored = TRUE returns event times only (its
  # default) — exactly the spec's "every distinct EVENT time" requirement.
  # (fig_km's OWN plot data instead calls summary(fit, censored = TRUE), for
  # the censoring tick marks on the curve — that is a display-only need this
  # harvest does not share.)
  sf <- summary(fit)
  strata <- .km_group_labels(sf$strata, dat$group, length(sf$time))
  curve_rows <- data.frame(t = sf$time, surv = sf$surv, at_risk = sf$n.risk)
  # Build each point as a PLAIN named list, not a 1-row data.frame slice:
  # jsonlite always serialises a data.frame (even one row) as an ARRAY of
  # row-objects, so `lapply(split(d, seq_len(nrow(d))), identity)` on 1-row
  # frames double-wraps every point as `[{...}]` instead of `{...}` — caught
  # by actually running this harvester end to end and reading the JSON, not
  # by inspection. A named list of scalars auto-unboxes to a bare object,
  # which is the {t, surv, at_risk} shape the interface contract requires.
  curve <- lapply(split(curve_rows, strata), function(d) {
    lapply(seq_len(nrow(d)), function(i)
      list(t = unname(d$t[i]), surv = unname(d$surv[i]),
           at_risk = unname(d$at_risk[i])))
  })

  # summary(fit)$table: a plain named vector for a single stratum, a matrix
  # (one row per stratum) for two or more — mirrored from fig_km's own
  # median-line code (R/km.R:136-144) so this harvest can never disagree
  # with the app's own reading of the same object, INCLUDING its `%||%`
  # single-group fallback: after the single-vs-matrix reshape below,
  # `rownames(med_tab)` is NULL for a one-group fit (the reshape gives the
  # object a `dim` but no row name), exactly like `sf$strata` is NULL for
  # the curve above — .km_group_labels() resolves both the same way, so a
  # single-group case's curve and medians can never come out keyed
  # differently (previously: curve keyed "Overall", medians keyed literal
  # NA, via `setNames(list(...), character(0))` recycling a name-less
  # vector — a real, verified bug, caught by generating and reading this
  # exact JSON, not by inspection). NA (median not reached) -> JSON null via
  # jsonlite's `na = "null"` (see main(), below); never rewritten to a
  # sentinel here.
  med_tab <- summary(fit)$table
  if (is.null(dim(med_tab))) med_tab <- t(as.matrix(med_tab))
  med_names <- .km_group_labels(rownames(med_tab), dat$group, nrow(med_tab))
  medians <- setNames(as.list(unname(med_tab[, "median"])), med_names)

  logrank_p <- NA_real_
  if (exists("lr", envir = env, inherits = FALSE)) {
    lr <- get("lr", envir = env, inherits = FALSE)
    logrank_p <- 1 - stats::pchisq(lr$chisq, length(lr$n) - 1)
  }

  list(curve = curve, medians = medians, logrank_p = logrank_p,
       n = nrow(dat), n_event = sum(dat$status == 1),
       n_dropped = n_dropped_vs_csv(dat))
}

# Group comparison. Verified against R/groupcompare.R's TWO script builders
# (.gc_script_numeric and .gc_script_categorical) by generating and reading the
# real exported script for all three gc cases before writing this: BOTH
# branches assign exactly two objects this harvest needs, under the same two
# names —
#   `dat` — the complete-case frame, columns literally `value`/`group` (never
#           the user's real column names, which appear only in the prep lines
#           that BUILD dat). The numeric branch adds one further filter line
#           (`dat[dat$group %in% names(which(table(dat$group) >= 2)), ]`); the
#           categorical branch has no such line, mirroring .gc_categorical,
#           which likewise never drops a small group. Either way `dat` is the
#           frame the test actually ran on, so counts come from it, not from a
#           re-derivation.
#   `ht`  — the htest object from the ONE test the app selected and ran
#           (oneway.test / kruskal.test / t.test / wilcox.test / chisq.test /
#           fisher.test). `.gc_numeric`/`.gc_categorical` evaluate the SAME
#           quoted expression they deparse into the script, so `ht` here is
#           the same call, not a reconstruction.
#
# `ht$statistic` is present for five of the six tests (F / Kruskal-Wallis
# chi-squared / t / W / X-squared) but **stats::fisher.test returns an htest
# with NO `statistic` component at all** — Fisher's exact test has no test
# statistic to report, it works directly on the hypergeometric probability of
# the table. That is a structural property of the test, not a missing harvest,
# so it is emitted as NA (-> JSON null via na = "null" in main()) and the
# comparator encodes the matching rule: a null statistic is "not applicable"
# for Fisher's exact test, and MISSING_QUANTITY for anything else.
#
# The post-hoc significant-pair set is deliberately NOT harvested: the
# exported script only ever `cat()`s `.gc_posthoc(...)`'s sentence, never
# assigns it, and the sentence is a DISPLAY artifact — the comparator checks
# the pair set on the display tier (Path A's `text` vs Path B's
# posthoc$significant_pairs) rather than re-running an embedded helper here.
harvest_groupcompare <- function(env, id) {
  ht <- need(env, "ht", id)
  dat <- need(env, "dat", id)
  counts <- table(dat$group)
  list(test_p = unname(ht$p.value),
       # unname(): R names the component after the test ("F", "X-squared",
       # ...), which would serialise as a one-element named object instead of
       # a bare number.
       test_statistic = if (is.null(ht$statistic)) NA_real_
                        else unname(ht$statistic),
       n = nrow(dat),
       n_per_group = as.list(setNames(as.integer(counts), names(counts))),
       n_dropped = n_dropped_vs_csv(dat))
}

# Summary (Table 1). Verified against R/summarize.R's `.summary_script` by
# generating and sourcing the real exported script for the summary-table1 case
# before writing this. The script leaves SIX objects in the environment:
#
#   df            the read.csv frame (all columns, all 120 rows — Summary has no
#                 complete-case filter at all, so this is the whole file).
#   .grp          the group vector, "Overall" when there is no group role.
#   s1..sN        one per CONTINUOUS variable, in selection order:
#                 `tapply(df[[col]], .grp, ...)` — a list keyed by group level.
#                 Its element NAMES say which statistic the app chose:
#                 c("mean","sd") for a mean variable, c("25%","50%","75%") for a
#                 median one. That makes the harvest self-describing about the
#                 DECISION, which is the whole point of Table 1: the script
#                 re-expresses the app's mean-vs-median choice, so the comparator
#                 can check the choice as well as the numbers.
#   t1..tM        one per CATEGORICAL variable, in selection order:
#                 `table(df[[col]], .grp)` — levels x groups, NA excluded, so
#                 colSums() is the app's own per-group percentage denominator.
#
# The exact tier for table1 is therefore NOT count-level only: the script leaves
# per-variable, per-group statistics at FULL PRECISION (unrounded mean/sd and
# unrounded type-7 quartiles), which is strictly more than the 3-significant-
# figure screen shows. That harvest powers the script tier — Path A against
# itself, the check that the .R the user downloaded reproduces the table they
# saw, including which statistic it chose.
#
# WHY case.json IS READ HERE. `s1`/`t1` carry the group levels in their own
# dimnames but NOT the variable they summarise (`table(df[["sex"]], .grp)`'s
# dimnames names are "" and ".grp", verified — not the column name). The only
# way to name them is the selection order, so this harvester reads the case's
# declared roles (cwd is the case dir while it runs, so "case.json" resolves)
# and re-derives the order the way buildSummarySpec does: CSV COLUMN ORDER
# filtered to the selected variables, taken from the script's own `df`.
#
# WHAT THE CHECK BELOW ACTUALLY CATCHES, stated exactly. A mismatch between the
# case's declared split and what the app really classified would mis-key every
# s/t object. The check here compares ARITY: it stops loudly when the script
# defines an s/t object the declared roles do not account for (a variable moved
# INTO continuous, or an extra one selected), and `need()` stops when a declared
# variable has no object at all. It does NOT catch a SAME-ARITY SWAP — one
# variable moving from continuous to categorical while another moves the other
# way, leaving the counts unchanged. That case is caught upstream instead, by
# harness/build-spec.test.mjs, which asserts the app's own classifyColumns split
# equals the case's declared roles.continuous/roles.categorical. Two checks, and
# the pair covers the failure; neither covers it alone.
harvest_summary <- function(env, id) {
  df <- need(env, "df", id)
  grp <- need(env, ".grp", id)

  case <- jsonlite::fromJSON("case.json", simplifyVector = TRUE)
  # NOT `%||%`: this file never load_all()s the package, so R/dispatch.R's
  # infix is not in scope here (base R has had one since 4.4, but this harness
  # must not silently depend on the interpreter's minor version).
  declared <- function(x) if (is.null(x)) character(0) else as.character(x)
  cols <- names(df)
  continuous <- cols[cols %in% declared(case$roles$continuous)]
  categorical <- cols[cols %in% declared(case$roles$categorical)]

  s_names <- sprintf("s%d", seq_along(continuous))
  t_names <- sprintf("t%d", seq_along(categorical))
  present <- ls(env)
  extra_s <- setdiff(grep("^s[0-9]+$", present, value = TRUE), s_names)
  extra_t <- setdiff(grep("^t[0-9]+$", present, value = TRUE), t_names)
  if (length(extra_s) > 0 || length(extra_t) > 0)
    stop(sprintf(paste0("exported script for %s defines %s, which the case's ",
                        "declared continuous/categorical roles do not account ",
                        "for — the s/t objects cannot be keyed to variables"),
                 id, paste(c(extra_s, extra_t), collapse = ", ")))

  levels_g <- unique(as.character(grp))

  # Per-variable, per-group statistics at full precision. `kind` is read off the
  # element names, never assumed, so a script that computed the OTHER statistic
  # is detected instead of silently relabelled.
  cont <- lapply(seq_along(continuous), function(i) {
    col <- continuous[[i]]
    s <- need(env, s_names[[i]], id)
    kinds <- unique(vapply(levels_g, function(g) {
      nm <- names(s[[g]])
      if (identical(nm, c("mean", "sd"))) "mean"
      else if (identical(nm, c("25%", "50%", "75%"))) "median"
      else "unknown"
    }, character(1)))
    if (length(kinds) != 1L || identical(kinds, "unknown"))
      stop(sprintf("exported script for %s: `%s` (%s) carries statistics this harvester cannot name",
                   id, s_names[[i]], col))
    stats <- lapply(levels_g, function(g) as.list(s[[g]]))
    names(stats) <- levels_g
    # A group whose values are all NA yields NaN/NA here; na = "null" in main()
    # turns that into JSON null, which the comparator reads as "no statistic",
    # never as a number.
    list(kind = kinds, stats = stats,
         n_missing = sum(is.na(df[[col]])))
  })
  names(cont) <- continuous

  cat_out <- lapply(seq_along(categorical), function(j) {
    col <- categorical[[j]]
    tt <- need(env, t_names[[j]], id)
    lev <- rownames(tt)
    counts <- lapply(levels_g, function(g) as.list(setNames(as.integer(tt[, g]), lev)))
    names(counts) <- levels_g
    denom <- as.list(setNames(as.integer(colSums(tt))[match(levels_g, colnames(tt))],
                              levels_g))
    list(levels = lev, counts = counts, denom = denom,
         n_missing = sum(is.na(df[[col]])))
  })
  names(cat_out) <- categorical

  n_per_group <- as.list(setNames(
    vapply(levels_g, function(g) sum(as.character(grp) == g), integer(1)), levels_g))

  list(levels = levels_g, n_per_group = n_per_group,
       continuous = cont, categorical = cat_out,
       n = nrow(df),
       # Summary has no complete-case filter, so this is structurally 0. It is
       # still measured against the raw CSV rather than hard-coded: a future
       # change that starts dropping rows must show up here.
       n_dropped = n_dropped_vs_csv(df))
}

HARVESTERS <- list(logistic = harvest_logistic, cox = harvest_cox,
                   km = harvest_km, groupcompare = harvest_groupcompare,
                   summary = harvest_summary)

# ---- harvest orchestration -------------------------------------------------

# Source and harvest with the case dir as the working directory; on.exit puts
# the process back where it started so out_path stays repo-root relative.
harvest_in_case_dir <- function(harvest, code, id, case_dir) {
  old <- setwd(case_dir)
  on.exit(setwd(old), add = TRUE)
  env <- source_export(code, id)
  # A future harvester might only need counts and never touch `env`'s
  # contents (e.g. a summary-only figure). Function arguments are lazy
  # promises in R, so `harvest(env, id)` alone would let such a harvester
  # skip sourcing the exported script entirely — and re-running that script
  # is a correctness check in its own right (it is what proves the script
  # the user downloaded still reproduces the model), independent of what
  # gets harvested from it. force() makes the source_export() side effect
  # unconditional, regardless of what the harvester goes on to read.
  force(env)
  harvest(env, id)
}

# ---- run ------------------------------------------------------------------
# Wrapped in main() so args/case/figure/... never become globalenv() bindings
# themselves: source_export() sources the exported script with
# parent = globalenv(), and a harness variable sitting in globalenv() would
# be silently visible to that script's own lookups (e.g. if it happened to
# reference a bare `id` or `case`) instead of raising "object not found" the
# way a genuinely undefined name should. Only function defs (and the
# HARVESTERS registry above) stay at top level.
main <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  stopifnot(length(args) == 4L)
  id <- args[[1]]; figura_path <- args[[2]]; case_dir <- args[[3]]; out_path <- args[[4]]

  case <- jsonlite::fromJSON(file.path(case_dir, "case.json"), simplifyVector = TRUE)
  figure <- case$figure
  if (is.null(figure) || length(figure) != 1L || is.na(figure) || !nzchar(figure))
    stop(sprintf("%s/case.json declares no `figure`", case_dir))

  harvest <- HARVESTERS[[figure]]
  # Loud by design: a figure with no harvester must fail here, not be squeezed
  # through another figure's summary layout.
  if (is.null(harvest))
    stop(sprintf("no harvester for figure: %s — added by its analysis task", figure))

  fj <- jsonlite::fromJSON(figura_path, simplifyVector = TRUE)
  payload <- c(list(id = id, figure = figure),
               harvest_in_case_dir(harvest, fj$code, id, case_dir))

  # digits = NA is load-bearing: jsonlite truncates to 4 significant digits by
  # default, which would silently cap this file far below the precision the
  # comparison gate needs. na = "null" is load-bearing too (added for km's
  # not-reached medians / no-second-group logrank_p, verified empirically —
  # jsonlite's OWN default for a bare NA is the STRING "NA", not JSON null):
  # a Python reader's `json.loads` must see `null` (-> None), never the
  # 2-character string "NA", or every not-reached comparison downstream would
  # silently compare a string against a float instead of None against None.
  # This is applied to EVERY harvester's payload, not just km's — verified
  # empirically that na = "null" ALSO remaps Inf/-Inf/NaN to JSON null (their
  # own default serialisation is likewise the literal strings "Inf"/"-Inf"/
  # "NaN", the identical failure mode one level up), so cox/logistic pick up
  # the same protection for free: a complete-separation fit whose harvested
  # `est`/`hi` lands on Inf now reads as Python `None`/`math.inf`-comparable
  # null instead of a string a numeric comparison would silently choke on or
  # miscompare. No regression for either: neither cox-adjusted nor
  # logistic-confounding's real harvest ever emits NA/Inf/NaN, re-confirmed
  # by re-running both full pipelines after this argument was added.
  jsonlite::write_json(payload, out_path, auto_unbox = TRUE, digits = NA,
                       pretty = TRUE, na = "null")
  cat(sprintf("wrote %s\n", out_path))
}

main()

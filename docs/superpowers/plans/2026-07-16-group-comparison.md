# Group Comparison (guided analysis) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fourth guided analysis, `groupcompare`, that compares an outcome across 2+ groups — routing on outcome type (numeric → t/ANOVA family, categorical → chi-square/Fisher), auto-selecting parametric vs non-parametric by normality, and reporting an effect size + 95% CI + p-value with post-hoc for 3+ groups — all in base R.

**Architecture:** `fig_groupcompare(spec)` extracts a group column + outcome column, detects the outcome type, runs the appropriate test with hand-computed effect sizes/CIs, and returns `list(svg=, text=)` (box/violin for numeric, bar for categorical). The UI is a `createGuidedShell` config (classic submit-driven path, not liveRender) mirroring `web/guided/summary/`.

**Tech Stack:** R (base `stats` + `ggplot2` only — no new packages), vanilla ES modules, plain-Node unit tests, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-07-16-group-comparison-design.md` — read it first.

## Global Constraints

- R tests: `Rscript -e 'devtools::test(filter = "groupcompare")'` — never `testthat::test_file()`. `[ FAIL 0 | WARN 0 ]` is a hard gate; fix leaked warnings at the source, or wrap ONLY a library call (e.g. `chisq.test`) in `suppressWarnings()` — never your own computation.
- ggplot2 4.x: `linewidth` not `size` for lines; no deprecated geoms/args.
- Spec option keys are snake_case. `options.test` ∈ {`"auto"`,`"parametric"`,`"nonparametric"`}; `options.plot` ∈ {`"box"`,`"violin"`}.
- No new packages: `DESCRIPTION` and `EXTRA_PACKAGES` untouched. No network calls, no fonts/CDNs, no localStorage.
- Reuse, do not redefine: `.svg_string(plot,w,h)` and `%||%` from `R/dispatch.R`; `.summary_decide(x)`, `.numeric_col(rows,col)`, `.char_col(rows,col)`, `.fmt_num(v)`, `.fmt_continuous(x,kind)` from `R/summarize.R`; `.km_palette(n)` from `R/km.R`; `.fig_theme(name)` from `R/themes.R`; `.flex_col`-style detection pattern from `R/explore.R`.
- All CSV-derived strings are DOM-built, never `innerHTML` (match `web/guided/summary/analyze-form.js`).
- No-egress: rows projected to the group + outcome columns only before crossing to the worker.
- E2E prep: `rm -rf web/R && cp -R R web/R` before `npm run test:e2e` or `npm run serve`.
- JS unit runner: each new `*.test.mjs` must be appended to the `test:unit` chain in `package.json`.
- Submit-driven, classic shell path — `liveRender` is NOT set on this config.

## Reuse reference (exact signatures, verified against the tree)

```r
# R/dispatch.R
.svg_string <- function(plot, width = 7, height = 5)   # returns <svg> string
`%||%` <- function(a, b)                                # null-coalesce
# R/summarize.R
.summary_decide <- function(x)        # -> list(kind = "mean"|"median", reason = <chr>); x = numeric vector
.numeric_col   <- function(rows, colname)  # -> numeric; stop()s (no warning) if any non-blank cell non-numeric
.char_col      <- function(rows, colname)  # -> character (NA for NULL cells)
.fmt_num       <- function(v)              # 3 sig figs, plain notation
.fmt_continuous<- function(x, kind)        # "M ± SD" (kind="mean") or "Q2 (Q1–Q3)" (kind="median")
# R/km.R
.km_palette <- function(n)   # Tol bright up to 6, hcl fallback beyond
# R/themes.R
.fig_theme  <- function(name = "generic")  # ggplot2 theme object
```

Note `.numeric_col` THROWS on a non-numeric cell, so it cannot be used to *detect* type. Task 2 defines a local non-throwing detector `.gc_is_numeric_col(rows, colname)` (mirrors `.flex_col` in `R/explore.R`) and only calls `.numeric_col` once the numeric route is chosen.

---

### Task 1: Frozen demo dataset (generator + artifacts + tests)

**Files:**
- Create: `data-raw/groupcompare-demo-generator.R`
- Create (generated): `tests/testthat/fixtures/groupcompare-demo.csv`, `web/guided/groupcompare/demo-data.js`
- Create: `tests/testthat/test-groupcompare-demo.R`, `web/guided/groupcompare/demo-data.test.mjs`
- Modify: `package.json` (append unit test)

**Interfaces:**
- Produces: `GROUPCOMPARE_DEMO = { version, label, columns, rows }` from `web/guided/groupcompare/demo-data.js`. Columns exactly: `arm, biomarker_normal, los_skewed, responder`. 150 rows (3 arms × 50: `Placebo`, `Low dose`, `High dose`). `biomarker_normal` ≈ normal with a real arm effect (→ ANOVA finds a difference). `los_skewed` right-skewed (→ non-parametric). `responder` categorical `Yes`/`No` with an arm-dependent rate (→ chi-square finds an association). 6 fixed rows have blank `los_skewed` (missing-data path).

- [ ] **Step 1: Write the generator**

```r
# data-raw/groupcompare-demo-generator.R
# Deterministic generator for the frozen Group-comparison demonstration dataset.
# Engineered so biomarker_normal reads approximately normal WITH a real arm
# effect (-> ANOVA/Tukey find a difference), los_skewed is right-skewed
# (-> Kruskal-Wallis/Dunn), and responder is a Yes/No outcome whose rate rises
# with dose (-> chi-square association). 6 fixed rows have blank los_skewed to
# exercise missing-data handling. Rerunning MUST reproduce the committed
# artifacts byte-for-byte; if you change anything, bump GROUPCOMPARE_DEMO.version.
set.seed(59)
per <- 50
arm <- rep(c("Placebo", "Low dose", "High dose"), each = per)
arm_idx <- as.integer(factor(arm, levels = c("Placebo", "Low dose", "High dose")))
biomarker_normal <- round(rnorm(3 * per, mean = 40 + 6 * arm_idx, sd = 8), 1)
los_skewed <- round(rexp(3 * per, rate = 1 / (3 + arm_idx)) + 1, 1)  # right-skewed, >=1
resp_p <- c(0.25, 0.45, 0.7)[arm_idx]
responder <- ifelse(runif(3 * per) < resp_p, "Yes", "No")

miss_idx <- c(4, 33, 61, 88, 117, 140)
los_chr <- format(los_skewed, trim = TRUE)
los_chr[miss_idx] <- ""

out <- data.frame(arm = arm, biomarker_normal = biomarker_normal,
                  los_skewed = los_chr, responder = responder,
                  stringsAsFactors = FALSE)
write.csv(out, "tests/testthat/fixtures/groupcompare-demo.csv",
          row.names = FALSE, quote = FALSE)

rows_list <- lapply(seq_len(nrow(out)), function(i) {
  list(arm = arm[i], biomarker_normal = biomarker_normal[i],
       los_skewed = if (los_chr[i] == "") NA else los_skewed[i],
       responder = responder[i])
})
rows_json <- jsonlite::toJSON(rows_list, auto_unbox = TRUE, na = "null", digits = NA)
js <- paste0(
  "// GENERATED by data-raw/groupcompare-demo-generator.R — do not hand-edit.\n",
  "export const GROUPCOMPARE_DEMO = {\n",
  '  version: "1.0.0",\n',
  '  label: "Synthetic demonstration data \\u2014 not for clinical use.",\n',
  '  columns: ["arm", "biomarker_normal", "los_skewed", "responder"],\n',
  "  rows: ", rows_json, "\n};\n")
writeLines(js, "web/guided/groupcompare/demo-data.js")
cat("md5(csv):", unname(tools::md5sum("tests/testthat/fixtures/groupcompare-demo.csv")), "\n")
```

- [ ] **Step 2: Run the generator**

Run: `mkdir -p web/guided/groupcompare && Rscript data-raw/groupcompare-demo-generator.R`
Expected: prints `md5(csv): <hash>`; both artifacts exist.

- [ ] **Step 3: Write the R frozen-properties test**

```r
# tests/testthat/test-groupcompare-demo.R
test_that("groupcompare demo fixture has the frozen teaching properties", {
  csv <- read.csv(test_path("fixtures", "groupcompare-demo.csv"),
                  stringsAsFactors = FALSE)
  expect_equal(nrow(csv), 150)
  expect_equal(names(csv),
    c("arm", "biomarker_normal", "los_skewed", "responder"))
  expect_equal(sort(unique(csv$arm)), c("High dose", "Low dose", "Placebo"))
  expect_equal(sum(csv$los_skewed == "" | is.na(csv$los_skewed)), 6)
  expect_setequal(unique(csv$responder), c("No", "Yes"))
  # biomarker rises with dose; responder rate rises with dose (teaching targets)
  m <- tapply(csv$biomarker_normal, csv$arm, mean)
  expect_true(m[["High dose"]] > m[["Placebo"]])
})
```

- [ ] **Step 4: Run it**

Run: `Rscript -e 'devtools::test(filter = "groupcompare-demo")'`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS 6 ]`

- [ ] **Step 5: Write the JS frozen-artifact test**

```js
// web/guided/groupcompare/demo-data.test.mjs
import assert from "node:assert/strict";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";

assert.equal(GROUPCOMPARE_DEMO.rows.length, 150);
assert.deepEqual(GROUPCOMPARE_DEMO.columns,
  ["arm", "biomarker_normal", "los_skewed", "responder"]);
assert.equal(GROUPCOMPARE_DEMO.rows.filter((r) => r.los_skewed === null).length, 6);
assert.ok(GROUPCOMPARE_DEMO.label.includes("not for clinical use"));
assert.ok(GROUPCOMPARE_DEMO.rows.every((r) =>
  ["Placebo", "Low dose", "High dose"].includes(r.arm)));
assert.ok(GROUPCOMPARE_DEMO.rows.every((r) => ["Yes", "No"].includes(r.responder)));
console.log("demo-data.test.mjs OK");
```

- [ ] **Step 6: Register in package.json and run**

In `package.json`, append to the `test:unit` chain:
`&& node web/guided/groupcompare/demo-data.test.mjs`

Run: `npm run test:unit`
Expected: all suites pass, ends with `demo-data.test.mjs OK`.

- [ ] **Step 7: Commit**

```bash
git add data-raw/groupcompare-demo-generator.R tests/testthat/fixtures/groupcompare-demo.csv \
  web/guided/groupcompare/demo-data.js web/guided/groupcompare/demo-data.test.mjs \
  tests/testthat/test-groupcompare-demo.R package.json
git commit -m "feat(groupcompare): frozen synthetic demo dataset + generator"
```

---

### Task 2: R numeric branch — routing, test selection, effect sizes, plot

**Files:**
- Create: `R/groupcompare.R`
- Modify: `R/dispatch.R` (switch)
- Create: `tests/testthat/test-groupcompare.R`

**Interfaces:**
- Consumes: `.svg_string`, `%||%` (R/dispatch.R); `.summary_decide`, `.numeric_col`, `.char_col`, `.fmt_num`, `.fmt_continuous` (R/summarize.R); `.km_palette` (R/km.R); `.fig_theme` (R/themes.R).
- Produces: `fig_groupcompare(spec)` → `list(svg=, text=)`. Spec: `figure="groupcompare"`, `data=[rows]`, `roles={group, outcome}`, `options={plot, test}`. Numeric branch complete here; Task 3 adds the categorical branch and post-hoc.
- Produces helpers Task 3 consumes: `.gc_is_numeric_col(rows, colname)` → logical; `.gc_prep(spec)` → `list(df=<data.frame value,group>, groups=<chr>, ng=<int>)` for the numeric path; `.gc_effect_t`, `.gc_effect_wilcox`, `.gc_effect_anova`, `.gc_effect_kruskal` (documented below).

- [ ] **Step 1: Write failing tests (numeric branch + routing + errors)**

```r
# tests/testthat/test-groupcompare.R
mkrows <- function(v, g) Map(function(vi, gi) list(val = vi, grp = gi), v, g)

two_norm <- {
  set.seed(11)
  v <- c(rnorm(30, 10, 2), rnorm(30, 13, 2)); g <- rep(c("A", "B"), each = 30)
  mkrows(v, g)
}
three_norm <- {
  set.seed(12)
  v <- c(rnorm(25, 10, 2), rnorm(25, 12, 2), rnorm(25, 15, 2))
  g <- rep(c("A", "B", "C"), each = 25); mkrows(v, g)
}
sc <- function(rows, test = "auto", plot = "box")
  list(figure = "groupcompare", data = rows,
       roles = list(group = "grp", outcome = "val"),
       options = list(test = test, plot = plot))

test_that("two-group normal auto-selects Welch t-test with d, CI, p, and SVG", {
  out <- fig_groupcompare(sc(two_norm))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "t-test", ignore.case = TRUE)
  expect_match(out$text, "Cohen's d", fixed = TRUE)
  expect_match(out$text, "95% CI", fixed = TRUE)
  expect_match(out$text, "p [=<]")
})

test_that("override forces Mann-Whitney with rank-biserial", {
  out <- fig_groupcompare(sc(two_norm, test = "nonparametric"))
  expect_match(out$text, "Mann–Whitney|Mann-Whitney", ignore.case = TRUE)
  expect_match(out$text, "rank-biserial", fixed = TRUE)
})

test_that("three-group parametric uses ANOVA with eta-squared", {
  out <- fig_groupcompare(sc(three_norm, test = "parametric"))
  expect_match(out$text, "ANOVA", ignore.case = TRUE)
  expect_match(out$text, "eta-squared|η²", ignore.case = TRUE)
})

test_that("three-group nonparametric uses Kruskal-Wallis with epsilon-squared", {
  out <- fig_groupcompare(sc(three_norm, test = "nonparametric"))
  expect_match(out$text, "Kruskal", ignore.case = TRUE)
  expect_match(out$text, "epsilon-squared|ε²", ignore.case = TRUE)
})

test_that("Cohen's d value is correct within tolerance", {
  # groups differ by ~3 SD-units of 2 -> d ~ 1.5; check the printed number band
  out <- fig_groupcompare(sc(two_norm, test = "parametric"))
  d <- as.numeric(sub(".*Cohen's d = (-?[0-9.]+).*", "\\1", out$text))
  expect_true(d < -1.0 || d > 1.0)   # sign depends on factor order; magnitude large
})

test_that("violin option renders", {
  out <- fig_groupcompare(sc(two_norm, plot = "violin"))
  expect_match(out$svg, "<svg", fixed = TRUE)
})

test_that("readable errors: <2 groups, non-numeric-in-numeric-role handled by routing", {
  one <- mkrows(rnorm(20, 5), rep("A", 20))
  expect_error(fig_groupcompare(sc(one)), "two groups", ignore.case = TRUE)
})

test_that("a group with <2 values is dropped, remaining comparison runs", {
  v <- c(rnorm(30, 10), rnorm(30, 12), 99); g <- c(rep("A", 30), rep("B", 30), "C")
  out <- fig_groupcompare(sc(mkrows(v, g)))
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$text, "dropped|excluded", ignore.case = TRUE)
})

test_that("dispatch routes groupcompare", {
  json <- jsonlite::toJSON(sc(two_norm), auto_unbox = TRUE)
  res <- jsonlite::fromJSON(render_figure(json))
  expect_true(res$ok)
  expect_match(res$svg, "<svg", fixed = TRUE)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `Rscript -e 'devtools::test(filter = "^groupcompare$")'`
Expected: FAIL — `could not find function "fig_groupcompare"`.

- [ ] **Step 3: Implement `R/groupcompare.R` (numeric branch)**

```r
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
  .gc_ci_phrase(d, d - 1.96 * se, d + 1.96 * se, "Cohen's d")
}

.gc_effect_wilcox <- function(df, U) {
  g <- df$group; lv <- sort(unique(g))
  n1 <- sum(g == lv[1]); n2 <- sum(g == lv[2])
  r <- 1 - 2 * U / (n1 * n2)              # rank-biserial
  z <- atanh(max(min(r, 0.999999), -0.999999))
  se <- 1 / sqrt(n1 + n2 - 3)
  lo <- tanh(z - 1.96 * se); hi <- tanh(z + 1.96 * se)
  .gc_ci_phrase(r, lo, hi, "rank-biserial r")
}

.gc_effect_anova <- function(df) {
  fit <- stats::aov(value ~ group, data = df)
  ss <- summary(fit)[[1]][, "Sum Sq"]
  eta <- ss[1] / sum(ss)                  # eta-squared
  # CI via noncentral-F (Steiger): invert F to a lambda CI, map to eta^2.
  s <- summary(fit)[[1]]
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
    if (nonpar) {
      ht <- suppressWarnings(stats::wilcox.test(value ~ group, data = df))
      tname <- "Mann–Whitney U test"; eff <- .gc_effect_wilcox(df, unname(ht$statistic))
    } else {
      ht <- stats::t.test(value ~ group, data = df)
      tname <- "Welch t-test"; eff <- .gc_effect_t(df)
    }
  } else {
    if (nonpar) {
      ht <- stats::kruskal.test(value ~ group, data = df)
      tname <- "Kruskal–Wallis test"
      eff <- .gc_effect_kruskal(unname(ht$statistic), nrow(df))
    } else {
      ht <- stats::oneway.test(value ~ group, data = df)  # Welch ANOVA
      tname <- "one-way ANOVA (Welch)"; eff <- .gc_effect_anova(df)
    }
  }
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
  list(svg = .svg_string(gg, width = 6, height = 4.5), text = txt)
}

# Post-hoc sentence; filled in Task 3. Numeric-branch orchestrator calls it now
# so the wiring exists; returns "" until 3+ group significant configs are handled.
.gc_posthoc <- function(df, ng, nonpar, pv) ""

# --- categorical branch; implemented in Task 3 ---
.gc_categorical <- function(spec) stop("categorical outcome not yet implemented")

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
```

- [ ] **Step 4: Register in the dispatch switch**

In `R/dispatch.R`, add to the switch (after `explore`):

```r
      groupcompare = fig_groupcompare(spec),
```

- [ ] **Step 5: Run tests to verify pass**

Run: `Rscript -e 'devtools::test(filter = "^groupcompare$")'`
Expected: `[ FAIL 0 | WARN 0 | ... ]`. If a WARN leaks, fix at source (wilcox ties warning is already suppressed; t/ANOVA on this data should be clean).

- [ ] **Step 6: Run the full R suite (no regressions)**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | ... ]`

- [ ] **Step 7: Commit**

```bash
git add R/groupcompare.R R/dispatch.R tests/testthat/test-groupcompare.R
git commit -m "feat(groupcompare): numeric branch — routing, auto test, effect sizes, plot"
```

---

### Task 3: R categorical branch + post-hoc (Tukey / Dunn)

**Files:**
- Modify: `R/groupcompare.R` (`.gc_categorical`, `.gc_posthoc`)
- Modify: `tests/testthat/test-groupcompare.R` (append)

**Interfaces:**
- Consumes: Task 2's `fig_groupcompare`, `.char_col`, `.fmt_num`, `.km_palette`, `.fig_theme`, `.svg_string`, `.gc_ci_phrase`.
- Produces: categorical branch renders a bar chart + chi-square/Fisher with Cramér's V (and odds ratio + CI when 2×2); `.gc_posthoc` returns a Tukey (parametric) or Dunn (non-parametric) sentence when omnibus p < 0.05 for 3+ groups.

- [ ] **Step 1: Write failing tests (categorical + post-hoc)**

Append to `tests/testthat/test-groupcompare.R`:

```r
mkrows2 <- function(out, g) Map(function(o, gi) list(out = o, grp = gi), out, g)
sc2 <- function(rows) list(figure = "groupcompare", data = rows,
  roles = list(group = "grp", outcome = "out"), options = list())

test_that("categorical 2x2 outcome uses chi-square with Cramer's V and odds ratio", {
  set.seed(21)
  g <- rep(c("A", "B"), each = 60)
  out <- c(sample(c("Yes","No"), 60, TRUE, c(0.3,0.7)),
           sample(c("Yes","No"), 60, TRUE, c(0.6,0.4)))
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  expect_match(res$svg, "<svg", fixed = TRUE)
  expect_match(res$text, "chi-square|χ²|Fisher", ignore.case = TRUE)
  expect_match(res$text, "Cramér's V|Cramer's V", ignore.case = TRUE)
  expect_match(res$text, "odds ratio", ignore.case = TRUE)
})

test_that("small expected counts fall back to Fisher", {
  g <- rep(c("A", "B"), each = 6)
  out <- c("Yes", rep("No", 5), rep("Yes", 5), "No")   # tiny cells
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  expect_match(res$text, "Fisher", ignore.case = TRUE)
})

test_that("3+ categorical outcome reports Cramer's V without odds ratio", {
  set.seed(22)
  g <- rep(c("A", "B", "C"), each = 40)
  out <- sample(c("Mild","Moderate","Severe"), 120, TRUE)
  res <- fig_groupcompare(sc2(mkrows2(out, g)))
  expect_match(res$text, "Cramér's V|Cramer's V", ignore.case = TRUE)
  expect_no_match(res$text, "odds ratio")
})

test_that("3-group significant ANOVA appends Tukey post-hoc", {
  set.seed(23)
  v <- c(rnorm(30, 10, 1.5), rnorm(30, 14, 1.5), rnorm(30, 18, 1.5))
  g <- rep(c("A", "B", "C"), each = 30)
  out <- fig_groupcompare(list(figure = "groupcompare",
    data = mkrows(v, g), roles = list(group = "grp", outcome = "val"),
    options = list(test = "parametric")))
  expect_match(out$text, "Tukey", ignore.case = TRUE)
})

test_that("3-group significant Kruskal appends Dunn post-hoc", {
  set.seed(24)
  v <- c(rexp(30, 1), rexp(30, 0.4) + 3, rexp(30, 0.2) + 8)
  g <- rep(c("A", "B", "C"), each = 30)
  out <- fig_groupcompare(list(figure = "groupcompare",
    data = mkrows(v, g), roles = list(group = "grp", outcome = "val"),
    options = list(test = "nonparametric")))
  expect_match(out$text, "Dunn", ignore.case = TRUE)
  expect_match(out$text, "BH|Benjamini", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `Rscript -e 'devtools::test(filter = "^groupcompare$")'`
Expected: FAIL — "categorical outcome not yet implemented" and no Tukey/Dunn text.

- [ ] **Step 3: Implement the categorical branch and post-hoc**

Replace `.gc_categorical` and `.gc_posthoc` in `R/groupcompare.R`:

```r
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
  suppressWarnings({ chi <- stats::chisq.test(tab) })
  use_fisher <- any(chi$expected < 5)
  if (use_fisher) {
    ht <- stats::fisher.test(tab); tname <- "Fisher's exact test"
  } else {
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
    or <- (a * d) / (b * c)
    se <- sqrt(1/a + 1/b + 1/c + 1/d)
    lo <- exp(log(or) - 1.96 * se); hi <- exp(log(or) + 1.96 * se)
    eff <- paste0(eff, "; ", .gc_ci_phrase(or, lo, hi, "odds ratio"))
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
  list(svg = .svg_string(gg, width = 6, height = 4.5), text = txt)
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
```

- [ ] **Step 4: Run tests, then the full suite**

Run: `Rscript -e 'devtools::test(filter = "^groupcompare$")'` then `Rscript -e 'devtools::test()'`
Expected: both `[ FAIL 0 | WARN 0 | ... ]`

- [ ] **Step 5: Commit**

```bash
git add R/groupcompare.R tests/testthat/test-groupcompare.R
git commit -m "feat(groupcompare): categorical branch + Tukey/Dunn post-hoc"
```

---

### Task 4: Worker registration + JS spec builder + demo builder

**Files:**
- Modify: `web/worker.js` (boot fetch loop)
- Create: `web/guided/groupcompare/spec.js`, `web/guided/groupcompare/spec.test.mjs`
- Create: `web/guided/groupcompare/demo.js`, `web/guided/groupcompare/demo.test.mjs`
- Modify: `package.json` (append two tests)

**Interfaces:**
- Consumes: `GROUPCOMPARE_DEMO` (Task 1).
- Produces:
  - `buildGroupCompareSpec(table, roles, options)` → `{figure:"groupcompare", data:[projected rows], roles:{group,outcome}, options:{plot,test}}`; rows projected to the group + outcome columns only.
  - `DEMO_TABLE` (csv.js shape), `DEFAULT_DEMO_STATE()` → `{roles:{group:"arm",outcome:"biomarker_normal"}, options:{plot:"box",test:"auto"}}` (fresh objects each call), `buildGroupCompareDemoSpec(demoState)`.

- [ ] **Step 1: Add `groupcompare.R` to the worker boot fetch**

In `web/worker.js`, extend the boot fetch loop:

```js
  for (const f of ["dispatch.R", "summarize.R", "km.R", "themes.R", "explore.R", "groupcompare.R"]) {
```

(No `EXTRA_PACKAGES` entry — base `stats` + `ggplot2` only.)

- [ ] **Step 2: Write failing tests for the spec + demo builders**

```js
// web/guided/groupcompare/spec.test.mjs
import assert from "node:assert/strict";
import { buildGroupCompareSpec } from "./spec.js";

const table = {
  columns: ["arm", "crp", "sex", "note"],
  types: { arm: "categorical", crp: "numeric", sex: "categorical", note: "categorical" },
  rows: [
    { arm: "A", crp: 5.1, sex: "M", note: "x" },
    { arm: "B", crp: 7.4, sex: "F", note: "y" },
  ],
};

{
  const spec = buildGroupCompareSpec(table,
    { group: "arm", outcome: "crp" }, { plot: "violin", test: "auto" });
  assert.equal(spec.figure, "groupcompare");
  assert.deepEqual(spec.roles, { group: "arm", outcome: "crp" });
  assert.deepEqual(spec.options, { plot: "violin", test: "auto" });
  // rows projected to group + outcome only — no sex/note egress
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["arm", "crp"]);
}
console.log("spec.test.mjs OK");
```

```js
// web/guided/groupcompare/demo.test.mjs
import assert from "node:assert/strict";
import { buildGroupCompareDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";

const spec = buildGroupCompareDemoSpec(DEFAULT_DEMO_STATE());
assert.equal(spec.figure, "groupcompare");
assert.equal(spec.roles.group, "arm");
assert.equal(spec.roles.outcome, "biomarker_normal");
assert.equal(spec.data.length, GROUPCOMPARE_DEMO.rows.length);
// projected to arm + biomarker_normal only
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["arm", "biomarker_normal"]);
const a = DEFAULT_DEMO_STATE(), b = DEFAULT_DEMO_STATE();
assert.notEqual(a.roles, b.roles);
assert.notEqual(a.options, b.options);
console.log("demo.test.mjs OK");
```

- [ ] **Step 3: Run to verify failure**

Run: `node web/guided/groupcompare/spec.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `spec.js` and `demo.js`**

```js
// web/guided/groupcompare/spec.js
// Pure spec assembly for group comparison. Rows are projected to the group +
// outcome columns only, so no other column crosses to the worker (no-egress).
export function buildGroupCompareSpec(table, roles, options) {
  const used = [roles.group, roles.outcome];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "groupcompare",
    data,
    roles: { group: roles.group, outcome: roles.outcome },
    options: { plot: options.plot, test: options.test },
  };
}
```

```js
// web/guided/groupcompare/demo.js
import { GROUPCOMPARE_DEMO } from "./demo-data.js";
import { buildGroupCompareSpec } from "./spec.js";

export const DEMO_TABLE = {
  columns: GROUPCOMPARE_DEMO.columns,
  rows: GROUPCOMPARE_DEMO.rows,
  types: { arm: "categorical", biomarker_normal: "numeric",
           los_skewed: "numeric", responder: "categorical" },
};

// Fresh nested objects each call — the guided session store resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return { roles: { group: "arm", outcome: "biomarker_normal" },
           options: { plot: "box", test: "auto" } };
}

export function buildGroupCompareDemoSpec(demoState) {
  return buildGroupCompareSpec(DEMO_TABLE, demoState.roles, demoState.options);
}
```

- [ ] **Step 5: Register both tests and run**

Append to `test:unit` in `package.json`:
`&& node web/guided/groupcompare/spec.test.mjs && node web/guided/groupcompare/demo.test.mjs`

Run: `npm run test:unit`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/worker.js web/guided/groupcompare/spec.js web/guided/groupcompare/spec.test.mjs \
  web/guided/groupcompare/demo.js web/guided/groupcompare/demo.test.mjs package.json
git commit -m "feat(groupcompare): worker registration + spec/demo builders"
```

---

### Task 5: Guided shell wiring — content, experiments, analyze form, config, registration

**Files:**
- Create: `web/guided/groupcompare/content.js`, `web/guided/groupcompare/analyze-form.js`, `web/guided/groupcompare/guided-groupcompare.js`
- Modify: `web/app.js`, `web/index.html`

**Interfaces:**
- Consumes: `createGuidedShell` (web/guided/shell.js), `buildGroupCompareDemoSpec`/`DEFAULT_DEMO_STATE`/`DEMO_TABLE` (demo.js), `buildGroupCompareSpec` (spec.js), `parseCsv`/`toCsv` (web/lib/csv.js), `renderColumnPicker` (web/lib/columnpicker.js), `GROUPCOMPARE_DEMO` (demo-data.js).
- Produces: `renderGuidedGroupCompare(container, onSubmit, runFigure, setStatus)` registered as `groupcompare` in the app.js `forms` map; nav button.

- [ ] **Step 1: `content.js` (Understand stage + example intro + demo experiments)**

```js
// web/guided/groupcompare/content.js
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { DEMO_TABLE } from "./demo.js";

export function renderUnderstand(panel) {
  panel.innerHTML = `
    <h3>Is the difference between groups real?</h3>
    <p>A group comparison asks whether an outcome differs across two or more
      groups — a biomarker between treatment arms, a complication rate between
      centres. Pick the grouping column and the outcome; the tool chooses the
      right test.</p>
    <h3>The tool picks the test for you</h3>
    <ul>
      <li><strong>A number</strong> (e.g. CRP) compared across groups uses a
        t-test or ANOVA when it looks normal, and their rank-based cousins
        (Mann–Whitney, Kruskal–Wallis) when it is skewed — decided the same way
        the Summary table decides mean vs median.</li>
      <li><strong>A category</strong> (e.g. responder yes/no) uses a chi-square
        test, falling back to Fisher's exact when counts are small.</li>
    </ul>
    <h3>Report more than a p-value</h3>
    <p>A p-value tells you whether a difference is detectable, not how big it is.
      Every result here also reports an <strong>effect size with a 95% confidence
      interval</strong> — what reviewers increasingly ask for. With three or more
      groups, a significant test is followed by pairwise comparisons so you can
      see <em>which</em> groups differ.</p>`;
}

export const EXAMPLE_INTRO_HTML = `
  <p>This synthetic trial has three arms (Placebo, Low dose, High dose) with a
    roughly normal biomarker, a right-skewed length of stay, and a yes/no
    responder outcome. Change the outcome below to see the test switch.</p>`;

// The demo "experiments" are the analysis controls: outcome column, plot, test.
export function renderGroupCompareExperiments(panel, ctx, rerun) {
  const host = panel.querySelector("#demo-experiments");
  host.innerHTML = "";
  const state = ctx.getSession().demoOptions;

  const outWrap = document.createElement("div");
  host.appendChild(outWrap);
  renderColumnPicker(outWrap,
    [{ key: "group", label: "Groups", type: "categorical+" },
     { key: "outcome", label: "Outcome (number or category)", type: "any" }],
    DEMO_TABLE, (v) => {
      if (!v) return;
      ctx.patchDemoOptions({ roles: { group: v.group, outcome: v.outcome } });
      rerun();
    });
  // preselect current roles
  const gsel = outWrap.querySelector("#cp_group"); if (gsel) gsel.value = state.roles.group;
  const osel = outWrap.querySelector("#cp_outcome"); if (osel) osel.value = state.roles.outcome;

  const mk = (id, label, choices, cur, key) => {
    const l = document.createElement("label"); l.textContent = label + " ";
    const s = document.createElement("select"); s.id = id;
    for (const [val, txt] of choices) {
      const o = document.createElement("option"); o.value = val; o.textContent = txt;
      s.appendChild(o);
    }
    s.value = cur;
    // Read the CURRENT session at change time — `state` is a render-time
    // snapshot, so spreading it here would drop an earlier control's change.
    s.onchange = () => {
      const now = ctx.getSession().demoOptions.options;
      ctx.patchDemoOptions({ options: { ...now, [key]: s.value } });
      rerun();
    };
    l.appendChild(s); host.appendChild(l);
  };
  mk("demo-plot", "Plot", [["box", "Box"], ["violin", "Violin"]], state.options.plot, "plot");
  mk("demo-test", "Test", [["auto", "Auto (by normality)"],
    ["parametric", "Parametric"], ["nonparametric", "Non-parametric"]],
    state.options.test, "test");
}
```

Note: `DEFAULT_DEMO_STATE` stores `{roles, options}`; `patchDemoOptions` shallow-merges, and each patch passes a fresh nested object, so `_demoDefaults` is never mutated (same contract Explore relies on).

- [ ] **Step 2: `analyze-form.js` (upload + pickers + Render)**

```js
// web/guided/groupcompare/analyze-form.js
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildGroupCompareSpec } from "./spec.js";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(GROUPCOMPARE_DEMO.rows, GROUPCOMPARE_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderGroupCompareForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A column naming each participant's group or arm.</li>
        <li>An outcome column — a number (e.g. a measurement) or a category
          (e.g. yes/no).</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-groups.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="gc-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#gc-config");
  let table = null, roles = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);
        renderColumnPicker(pick,
          [{ key: "group", label: "Groups", type: "categorical+" },
           { key: "outcome", label: "Outcome (number or category)", type: "any" }],
          table, (v) => { roles = v; btn.disabled = !v; }, doc);

        const mkSel = (id, label, choices) => {
          const l = doc.createElement("label"); l.textContent = label + " ";
          const s = doc.createElement("select"); s.id = id;
          for (const [val, txt] of choices) {
            const o = doc.createElement("option"); o.value = val; o.textContent = txt;
            s.appendChild(o);
          }
          l.appendChild(s); config.appendChild(l); return s;
        };
        const plotSel = mkSel("gc-plot", "Plot (numeric outcomes)",
          [["box", "Box"], ["violin", "Violin"]]);
        const testSel = mkSel("gc-test", "Test",
          [["auto", "Auto (by normality)"], ["parametric", "Parametric"],
           ["nonparametric", "Non-parametric"]]);

        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "gc-render"; btn.textContent = "Render comparison";
        btn.disabled = true;
        btn.onclick = () => {
          if (!roles) return;
          onSubmit(buildGroupCompareSpec(table, roles,
            { plot: plotSel.value, test: testSel.value }));
        };
        config.appendChild(btn);
        config.hidden = false;
      } catch (err) {
        table = null; config.hidden = true; config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}
```

- [ ] **Step 3: `guided-groupcompare.js` (shell config)**

```js
// web/guided/groupcompare/guided-groupcompare.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderGroupCompareExperiments }
  from "./content.js";
import { buildGroupCompareDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";
import { renderGroupCompareForm } from "./analyze-form.js";

export const renderGuidedGroupCompare = createGuidedShell({
  title: "Group comparison",
  hashPrefix: "groupcompare",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: GROUPCOMPARE_DEMO.label,
  buildDemoSpec: buildGroupCompareDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments select",
  renderExperiments: renderGroupCompareExperiments,
  renderAnalyzeForm: renderGroupCompareForm,
});
```

(No `liveRender` — classic submit-driven path.)

- [ ] **Step 4: Register in app.js + index.html**

`web/app.js` — extend imports and the forms map:

```js
import { renderGuidedGroupCompare } from "./guided/groupcompare/guided-groupcompare.js";
const forms = { summary: renderGuidedSummary, km: renderGuidedKm,
                explore: renderGuidedExplore, groupcompare: renderGuidedGroupCompare };
```

`web/index.html` — add after the Explore button:

```html
        <button data-figure="groupcompare">Group comparison</button>
```

- [ ] **Step 5: Manual smoke check**

```bash
rm -rf web/R && cp -R R web/R && npm run serve
```

Visit http://localhost:8321 → Group comparison → Try an Example → Run Example Analysis. Verify: box plot renders with a t-test/ANOVA line and an effect size + CI; switch outcome to `responder` → bar chart + chi-square; switch to `los_skewed` → non-parametric test. Kill the server.

- [ ] **Step 6: Run all unit tests**

Run: `npm run test:unit`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add web/guided/groupcompare/content.js web/guided/groupcompare/analyze-form.js \
  web/guided/groupcompare/guided-groupcompare.js web/app.js web/index.html
git commit -m "feat(groupcompare): guided analysis — understand, demo experiments, analyze form"
```

---

### Task 6: E2E tests, docs, full verification

**Files:**
- Create: `tests/e2e/groupcompare-guided.spec.js`
- Modify: `CLAUDE.md` (architecture notes)

- [ ] **Step 1: Write the e2e spec**

```js
// tests/e2e/groupcompare-guided.spec.js
const { test, expect } = require("@playwright/test");

test("groupcompare shows three tabs and syncs the hash", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#groupcompare/example");
});

test("demo: numeric outcome renders a plot with test + effect size; categorical switches to chi-square", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#groupcompare/example");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText(/ANOVA|t-test/);
  await expect(page.locator("#stats")).toContainText("95% CI");

  // Switch the outcome to the categorical responder column -> chi-square.
  await page.locator("#cp_outcome").selectOption("responder");
  await expect(page.locator("#stats")).toContainText(/chi-square|Fisher/, { timeout: 120000 });
  await expect(page.locator("#preview svg")).toBeVisible();
});

test("analyze stage renders an uploaded comparison with a real p-value", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#groupcompare/analyze");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#gc-config")).toBeHidden();
  const csv = "arm,score\n" + Array.from({ length: 40 }, (_, i) =>
    `${i % 2 ? "A" : "B"},${(10 + (i % 2) * 4 + (i % 5)).toFixed(1)}`).join("\n");
  await page.locator("#csv").setInputFiles({
    name: "g.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await expect(page.locator("#gc-config")).toBeVisible();
  await page.locator("#cp_group").selectOption("arm");
  await page.locator("#cp_outcome").selectOption("score");
  await page.locator("#gc-render").click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 300000 });
  await expect(page.locator("#stats")).toContainText(/p [=<]/);
});
```

- [ ] **Step 2: Run the e2e suite**

```bash
rm -rf web/R && cp -R R web/R && npm run test:e2e
```

Expected: all specs pass, including the pre-existing KM/Summary/Explore/export specs (regression gate).

- [ ] **Step 3: Update CLAUDE.md**

In the Architecture section: change the guided-analyses sentence to name all four analyses (add Group comparison, `web/guided/groupcompare/guided-groupcompare.js`), add `data-raw/groupcompare-demo-generator.R` to the frozen-demos list, and append one sentence: Group comparison (`R/groupcompare.R`) routes on outcome type (numeric → t/ANOVA family, categorical → chi-square/Fisher), auto-selects parametric vs non-parametric by reusing `.summary_decide`, and reports an effect size + 95% CI + p-value with Tukey/Dunn post-hoc for 3+ groups — all base-R, no `EXTRA_PACKAGES` entry.

- [ ] **Step 4: Full verification sweep**

```bash
Rscript -e 'devtools::test()'      # [ FAIL 0 | WARN 0 ]
npm run test:unit
rm -rf web/R && cp -R R web/R && npm run test:e2e
```

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/groupcompare-guided.spec.js CLAUDE.md
git commit -m "test(groupcompare): e2e — numeric/categorical routing, post-hoc, uploaded comparison"
```

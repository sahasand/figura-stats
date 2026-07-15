# Guided Summary Statistics (Table 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revision note:** This is the post-review rewrite (2026-07-15). The engineering review (amendments A1–A12) and design review (A13) decisions are merged directly into the task bodies below — there is no separate amendments layer to cross-reference. Review provenance: see the GSTACK REVIEW REPORT at the end of this file.

**Goal:** Replace the typed-numbers Table 1 with a guided upload→auto-computed Table 1 that tests each numeric variable for normality (assessed within groups), picks mean±SD or median (IQR) with a one-line defensible reason, reports per-variable n / missing with explicit denominators, bundles a distribution plot with a teaching legend beside the table, lets the user choose which columns to include via a smart-default checklist, and omits baseline p-values with a teaching note — all in the same Understand / Try an Example / Analyze Your Data guided shell used by Kaplan–Meier, which this plan extracts into a shared factory.

**Architecture:** Static vanilla-JS + webR, unchanged `{figure, data, options}` → `{ok, svg, text}` worker contract. R (`fig_summary`) is the only source of statistics: it decides the summary per variable (Shapiro–Wilk for n ≤ 300, skewness alone above; decided on group-mean-centered values when a group role exists), formats the table, and renders a faceted distribution plot. The result bundles the HTML `<table>` and the inline distribution `<svg>` together in the `svg` field (injected as `innerHTML` into `#preview`, exactly as `fig_regression` already injects HTML tables); the `text` field carries copy-pasteable TSV (with a header row) plus a methods sentence. The guided shell is extracted from the KM copy into a shared `createGuidedShell(config)` factory (`web/guided/shell.js`); KM becomes consumer #1 with byte-identical behavior (its e2e suite is the regression gate), and the summary shell is a small config file. The new analysis needs **no packages beyond the boot set** (`ggplot2, svglite, jsonlite, knitr`) — `shapiro.test`, `median`, `quantile`, `sd` are all base `stats`.

**Tech Stack:** R (`stats`, `ggplot2`, `svglite`, base string building), vanilla ES modules, plain-Node unit tests, Playwright e2e.

## Global Constraints

- No framework, backend, account, analytics, or browser persistence — memory-only state; reload starts clean.
- No transmission of user data; the only network calls are the webR CDN and `fetch("R/*.R")`.
- JavaScript never computes statistics; R/webR is the only source of estimates and figure coordinates. JS only parses the CSV, infers column types, and marshals columns.
- Full R suite must end `[ FAIL 0 | WARN 0 | ... ]` — WARN 0 is a hard gate, **at every commit in this plan** (task boundaries are commit boundaries; no commit may ship a red suite). Run via `Rscript -e 'devtools::test()'`, never `testthat::test_file`. ggplot2 4.x: use `linewidth`, never `size`/`label.size`.
- `web/R/` is a gitignored build copy: `rm -rf web/R && cp -R R web/R` before any browser test; never commit it.
- The other seven analyses (forest, consort, km, groupcompare, correlation, roc, regression) keep their exact current behavior. KM's *implementation* is refactored onto the shared shell in Task 7, but its behavior is byte-identical and its unit + e2e suites are the gate. Only the retired `table1` figure changes.
- **One name per analysis:** the nav button, form registry key, URL hash prefix, and R figure key are all `summary` (the visible button label stays "Table 1"), matching the `km` convention.
- Reuse `%||%` (defined in `R/forest.R`) and `.svg_string()` (in `R/dispatch.R`); do not redefine either.
- Never emit SEM. Continuous dispersion is always SD, labeled unambiguously as `mean ± SD`.
- No p-value column on baseline characteristics — this is a hard product rule, not a default (the Table 1 fallacy; CONSORT 2025 discourages baseline p-values in RCTs). Do not add one.
- Synthetic-data labeling, exact string, baked into the result and shown in the UI banner: **"Synthetic demonstration data — not for clinical use."** Teaching intro blockquote, exact string: **"Synthetic teaching data — this is not evidence about a real population."** Neither may be paraphrased.
- P-value formatting rule inherited from the codebase (three decimals, `p < 0.001` below that) applies to any Shapiro–Wilk p shown in a reason string: never print `p = 0.000`.

## Data Flow

```
CSV ─FileReader─▶ parseCsv ─▶ {columns, rows, types}
                                   │
                ┌──────────────────┴───────────────────┐
                ▼                                      ▼
      variable checklist                      group picker (columnpicker,
      ≤5-distinct numeric→categorical;         optional role, categorical only)
      all-unique-integer ("ID") and                    │
      >20-level columns → unticked                     │
                └────────────────┬─────────────────────┘
                                 ▼
              buildSummarySpec (pure; rows projected to
              selected + group columns only)
                                 ▼ postMessage
              worker.js ─▶ render_figure ─▶ fig_summary
                                 │
        ┌────────────────────────┼──────────────────────────┐
        ▼                        ▼                          ▼
 .summary_decide           .fmt_continuous            .summary_plot_svg
 (group-centered            (3 significant            (facets, mean/median
  values; Shapiro n≤300,     figures)                  reference lines)
  skewness above)
        └───────────────┬────────┴──────────────┬───────────┘
                        ▼                       ▼
          svg: <div class="summary-output"><div class="table-scroll"><table…></div>
               <figure class="dist-plot"><svg…><div class="plot-legend"…>
               <figcaption class="synthetic"…></figure></div>
          text: TSV with header row + methods sentence
```

## Approved Mockups

| Screen/Section | Mockup Path | Direction | Notes |
|----------------|-------------|-----------|-------|
| Table 1 results composite | `~/.gstack/projects/my-stats/designs/summary-table1-results-20260715/design-sketch.html` (Sketch A; `sketch.png`) | Journal table + why-lines + faceted histogram strip + warn-palette synthetic caption, all on existing tokens | Numeric cells right-aligned tabular; `.why` is subordinate (11px slate) |
| Analyze form with variable checklist | same file (Sketch B) | Progressive-disclosure form; bordered checklist with type chips and warn-palette excluded notes; teal primary action | Pre-upload state = heading + privacy line + file input only |

## NOT in scope (accepted trade-offs)

- **Typed summary-numbers entry is retired with no replacement**: users holding only
  aggregate numbers lose typed Table 1 entry. Deliberate — the tool's premise is
  computing defensible statistics from data. The old form lives in git history; a
  future "I only have summary numbers" mode is recorded in `TODOS.md`.
- **No manual numeric↔categorical type toggle** in the checklist: the ≤5-distinct
  heuristic plus re-ticking covers the common cases; a per-column type editor is a
  different feature.
- **No DESIGN.md yet** — the styles.css token system is the working design authority
  (`/design-consultation` TODO recorded).
- E2E boot-sharing across guided suites and unifying `app.js render()` with the shared
  shell's `runAndShow` are follow-ups in `TODOS.md`, not part of this plan.

Verified during review: seed 41 reproduces the teaching pins in real R (age → mean,
Shapiro p = 0.438; LOS → median, skew 1.31; CRP → median, skew 3.11; 8 missing), and
the pins survive group-centering (demo n = 120 keeps Shapiro active).

## File Structure

```
data-raw/summary-demo-generator.R           # deterministic generator (seeded) — writes the two frozen artifacts
tests/testthat/fixtures/summary-demo.csv    # frozen demo dataset (canonical, versioned)
web/guided/shell.js                         # createGuidedShell(config) — shared guided-shell factory
web/guided/summary/demo-data.js             # same rows embedded as a JS module (generated, do not hand-edit)
web/guided/summary/demo-data.test.mjs       # shape/label guard for the generated module
web/guided/summary/content.js               # approved teaching copy (Understand stage) + callouts
web/guided/summary/demo.js                  # buildSummaryDemoSpec(options) -> worker spec
web/guided/summary/demo.test.mjs            # demo spec builder tests
web/guided/summary/analyze-form.js          # upload CSV + variable checklist + group picker -> spec
web/guided/summary/analyze-form.test.mjs    # classification/selection/projection tests
web/guided/summary/guided-summary.js        # summary config for createGuidedShell (~50 lines)
R/summarize.R                               # .skewness, .summary_decide, .fmt_continuous, fig_summary
tests/testthat/test-summarize.R             # decision-engine + table + plot unit tests
tests/testthat/test-summary-demo.R          # frozen-demo teaching-target pins
tests/e2e/summary-guided.spec.js            # end-to-end guided flow
```

Existing files modified: `web/guided/guided-analysis.js` (becomes the KM config for the shared factory), `web/guided/session-state.js` (additive generic factory), `web/guided/session-state.test.mjs` (test the addition), `web/lib/columnpicker.js` (+ its test — additive optional-role support), `web/app.js` (register `summary`; drop the typed form import), `web/index.html` (`data-figure="summary"`), `web/styles.css` (results-composite + checklist styling), `web/worker.js` (add `summarize.R` to the boot loop; drop `table1.R`), `R/dispatch.R` (add `summary` case; drop `table1` case), `package.json` (append new unit tests), `CLAUDE.md` (note the replacement).

Retired (deleted): `web/forms/table1.js`, `R/table1.R`, `tests/testthat/test-table1.R`.

---

### Task 1: Freeze the Summary demonstration dataset

A fixed, versioned synthetic dataset engineered to teach the core decision: one approximately-normal continuous variable (age → mean±SD), two right-skewed continuous variables (length of stay, CRP → median (IQR)), two categoricals (sex, diabetes), a two-arm group column, and deterministic missingness (exactly 8 missing length-of-stay values) so the missing-data reporting has something to show. Never generated at runtime.

**Files:**
- Create: `data-raw/summary-demo-generator.R`
- Create: `tests/testthat/fixtures/summary-demo.csv` (by running the generator)
- Create: `web/guided/summary/demo-data.js` (by running the generator)
- Create: `web/guided/summary/demo-data.test.mjs`
- Modify: `package.json` (append the new unit test)

**Interfaces:**
- Produces: `SUMMARY_DEMO` (JS named export): `{ version: "1.0.0", label: "Synthetic demonstration data — not for clinical use.", columns: [...], rows: [{ age, length_of_stay, crp, sex, diabetes, arm }] }` — consumed by Task 9's `buildSummaryDemoSpec`. `length_of_stay` is `null` for the 8 missing rows.
- Produces: `tests/testthat/fixtures/summary-demo.csv` with header `age,length_of_stay,crp,sex,diabetes,arm` and empty cells for missing length-of-stay — consumed by Task 2's teaching-target test and Task 13's e2e upload.

(The teaching-target R test `tests/testthat/test-summary-demo.R` is written and committed in **Task 2**, because it calls `.summary_decide` — committing it here would ship a red R suite, violating the green-at-every-commit gate.)

- [ ] **Step 1: Write the generator**

```r
# data-raw/summary-demo-generator.R
# Deterministic generator for the frozen Summary (Table 1) demonstration dataset.
# Engineered so age reads approximately normal (-> mean ± SD) while length_of_stay
# and crp are right-skewed (-> median (IQR)), with exactly 8 missing length_of_stay
# values to exercise missing-data reporting. Rerunning MUST reproduce the committed
# artifacts byte-for-byte; if you change anything here, bump SUMMARY_DEMO.version
# and re-check the teaching targets in tests/testthat/test-summary-demo.R.
set.seed(41)
n <- 60  # per arm; 120 total
arm <- rep(c("Control", "Treatment"), each = n)
age <- round(rnorm(2 * n, mean = 58, sd = 11))
length_of_stay <- round(rexp(2 * n, rate = 1 / 5) + 1, 1)   # right-skewed, >= 1 day
crp <- round(rlnorm(2 * n, meanlog = 1.6, sdlog = 0.9), 1)  # right-skewed biomarker
sex <- sample(c("Female", "Male"), 2 * n, replace = TRUE)
diabetes <- sample(c("No", "Yes"), 2 * n, replace = TRUE, prob = c(0.7, 0.3))

# Deterministic missingness: 8 fixed rows have unknown length of stay.
miss_idx <- c(3, 17, 24, 38, 51, 66, 89, 104)
los_chr <- format(length_of_stay, trim = TRUE)
los_chr[miss_idx] <- ""   # empty cell in the CSV -> null in JS

out <- data.frame(
  age = age,
  length_of_stay = los_chr,
  crp = crp,
  sex = sex,
  diabetes = diabetes,
  arm = arm,
  stringsAsFactors = FALSE)
write.csv(out, "tests/testthat/fixtures/summary-demo.csv", row.names = FALSE, quote = FALSE)

# JS module: emit length_of_stay as null where the CSV cell is empty.
rows_list <- lapply(seq_len(nrow(out)), function(i) {
  list(age = age[i],
       length_of_stay = if (los_chr[i] == "") NA else length_of_stay[i],
       crp = crp[i], sex = sex[i], diabetes = diabetes[i], arm = arm[i])
})
rows_json <- jsonlite::toJSON(rows_list, auto_unbox = TRUE, na = "null", digits = NA)
js <- paste0(
  "// GENERATED by data-raw/summary-demo-generator.R — do not hand-edit.\n",
  "export const SUMMARY_DEMO = {\n",
  '  version: "1.0.0",\n',
  '  label: "Synthetic demonstration data \\u2014 not for clinical use.",\n',
  '  columns: ["age", "length_of_stay", "crp", "sex", "diabetes", "arm"],\n',
  "  rows: ", rows_json, "\n};\n")
writeLines(js, "web/guided/summary/demo-data.js")
cat("md5(csv):", unname(tools::md5sum("tests/testthat/fixtures/summary-demo.csv")), "\n")
```

- [ ] **Step 2: Create the output directory and run the generator**

Run:
```bash
mkdir -p web/guided/summary
Rscript data-raw/summary-demo-generator.R
```
Expected: prints `md5(csv): <hash>` and creates both `tests/testthat/fixtures/summary-demo.csv` and `web/guided/summary/demo-data.js`.

- [ ] **Step 3: Write the JS module shape/label guard**

```js
// web/guided/summary/demo-data.test.mjs
import { SUMMARY_DEMO } from "./demo-data.js";
import assert from "node:assert";

assert.equal(SUMMARY_DEMO.version, "1.0.0");
assert.equal(SUMMARY_DEMO.label, "Synthetic demonstration data — not for clinical use.");
assert.deepEqual(SUMMARY_DEMO.columns, ["age", "length_of_stay", "crp", "sex", "diabetes", "arm"]);
assert.equal(SUMMARY_DEMO.rows.length, 120, "demo has 120 rows");
const missing = SUMMARY_DEMO.rows.filter((r) => r.length_of_stay === null).length;
assert.equal(missing, 8, "exactly 8 missing length_of_stay");
assert.deepEqual([...new Set(SUMMARY_DEMO.rows.map((r) => r.arm))].sort(), ["Control", "Treatment"]);
console.log("ok - summary demo-data");
```

- [ ] **Step 4: Append the unit test to package.json**

In `package.json`, extend the `test:unit` script by appending ` && node web/guided/summary/demo-data.test.mjs` to the end of its command string.

- [ ] **Step 5: Run the new test**

Run:
```bash
node web/guided/summary/demo-data.test.mjs
```
Expected: `ok - summary demo-data`

- [ ] **Step 6: Commit**

```bash
git add data-raw/summary-demo-generator.R tests/testthat/fixtures/summary-demo.csv \
        web/guided/summary/demo-data.js web/guided/summary/demo-data.test.mjs \
        package.json
git commit -m "feat(summary): freeze synthetic Table 1 demonstration dataset"
```

---

### Task 2: R normality decision engine

The heart of the feature: given a numeric vector, decide `mean±SD` vs `median (IQR)` and produce a one-line reason a reviewer would accept. Pure, deterministic, fully unit-tested before any table exists. Calibration: Shapiro–Wilk is well calibrated only at small n — at a few hundred observations it flags trivial departures — so the test runs only for 3–300 observations and the decision rests on |skewness| < 1 alone above that. Formatting uses 3 significant figures so lab values are sane at both scale extremes (`250000 ± 31000`, `1.13 (1.05–1.21)`), never a hardcoded decimal.

**Files:**
- Create: `R/summarize.R` (this task adds only the helpers below)
- Create: `tests/testthat/test-summarize.R` (decision-engine tests only for now)
- Create: `tests/testthat/test-summary-demo.R` (frozen-demo teaching-target pins — moved here from Task 1 so every commit's R suite is green)

**Interfaces:**
- Produces: `.skewness(x)` → single numeric (population skewness of the non-missing values; `NA` if fewer than 3).
- Produces: `.summary_decide(x)` → `list(kind = "mean" | "median", reason = <character>)`. `kind` drives formatting; `reason` is the defensible one-liner. Consumed by Task 3 (`fig_summary`) and the demo pins test. Callers are responsible for group-centering (Task 3).
- Produces: `.fmt_continuous(x, kind)` → single character, e.g. `"58.2 ± 10.9"` or `"4.9 (2.4–8.7)"`, 3 significant figures per number. Consumed by Task 3.

- [ ] **Step 1: Write the failing decision-engine tests**

```r
# tests/testthat/test-summarize.R
test_that("skewness is ~0 for symmetric data and positive for right-skew", {
  set.seed(1)
  expect_lt(abs(.skewness(rnorm(500))), 0.3)
  expect_gt(.skewness(rexp(500)), 1)
})

test_that("approximately normal data (small n) picks mean and cites Shapiro-Wilk", {
  set.seed(42); x <- rnorm(200, mean = 50, sd = 8)  # seed verified: Shapiro p = 0.946 (seed 2 draws p = 0.021)
  d <- .summary_decide(x)
  expect_equal(d$kind, "mean")
  expect_match(d$reason, "normal", ignore.case = TRUE)
  expect_match(d$reason, "Shapiro")
})

test_that("right-skewed data (small n) picks median and names the skew direction", {
  set.seed(3); x <- rexp(200, rate = 0.2)
  d <- .summary_decide(x)
  expect_equal(d$kind, "median")
  expect_match(d$reason, "skew", ignore.case = TRUE)
  expect_match(d$reason, "right", ignore.case = TRUE)
})

test_that("a Shapiro p below 0.001 never prints as p = 0.000", {
  set.seed(4); x <- rexp(250, rate = 0.5)
  expect_false(grepl("0.000", .summary_decide(x)$reason, fixed = TRUE))
})

test_that("above n = 300 the decision rests on skewness alone (no Shapiro)", {
  set.seed(5)
  d_sym <- .summary_decide(rnorm(2000))
  expect_equal(d_sym$kind, "mean")
  expect_false(grepl("Shapiro", d_sym$reason))
  expect_match(d_sym$reason, "skew", ignore.case = TRUE)
  d_skew <- .summary_decide(rexp(2000))
  expect_equal(d_skew$kind, "median")
  expect_false(grepl("Shapiro", d_skew$reason))
})

test_that("fewer than 3 values defaults to median without error", {
  d <- .summary_decide(c(2, 5))
  expect_equal(d$kind, "median")
  expect_no_error(.summary_decide(c(2, 5)))
})

test_that("formatting: mean shows ± SD; median shows IQR with an en dash", {
  x <- c(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
  expect_match(.fmt_continuous(x, "mean"), "±")
  expect_equal(.fmt_continuous(x, "median"), "5.5 (3.25–7.75)")  # en dash; quantile type 7 (R default)
})

test_that("formatting uses 3 significant figures at both scale extremes", {
  expect_equal(.fmt_continuous(c(249000, 250000, 251000), "mean"), "250000 ± 1000")
  expect_false(grepl(".0 ", .fmt_continuous(c(249000, 250000, 251000), "mean"), fixed = TRUE))
  expect_match(.fmt_continuous(c(1.05, 1.13, 1.21), "mean"), "^1\\.13 ± ")
})
```

- [ ] **Step 2: Write the frozen-demo teaching-target test (also failing)**

```r
# tests/testthat/test-summary-demo.R
test_that("frozen summary demo has the pinned teaching properties", {
  csv <- read.csv("fixtures/summary-demo.csv", stringsAsFactors = FALSE,
                  na.strings = "", colClasses = "character")
  expect_equal(nrow(csv), 120)
  expect_equal(sum(is.na(csv$length_of_stay)), 8)

  age <- as.numeric(csv$age)
  los <- as.numeric(csv$length_of_stay)
  # The whole feature turns on these two decisions coming out opposite ways.
  # (Verified against seed 41: age Shapiro p = 0.438, LOS skewness 1.31.)
  expect_equal(.summary_decide(age)$kind, "mean")
  expect_equal(.summary_decide(los)$kind, "median")
})
```

- [ ] **Step 3: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "summar")'`
Expected: FAIL — `.skewness`/`.summary_decide`/`.fmt_continuous` not found.

- [ ] **Step 4: Write the helpers**

```r
# R/summarize.R

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
```

- [ ] **Step 5: Run to verify everything passes (including the demo pins)**

Run: `Rscript -e 'devtools::test(filter = "summar")'`
Expected: PASS, `[ FAIL 0 | WARN 0 | ... ]` — age → `mean`, length_of_stay → `median`.

- [ ] **Step 6: Commit**

```bash
git add R/summarize.R tests/testthat/test-summarize.R tests/testthat/test-summary-demo.R
git commit -m "feat(summary): normality-aware mean/SD vs median/IQR decision engine"
```

---

### Task 3: R table builder (`fig_summary` — table + text only)

Assemble the Table 1 body: one column per group in **first-appearance order** (or a single `Overall` column), a `Missing` count column, continuous rows formatted per the decision engine with the reason shown, categorical rows as `n (%)` with the actual non-missing denominator stated on the variable's own row, and honoring a per-variable override (validated). The normality decision is made **once per variable on group-mean-centered values** so a variable reads consistently across group columns and group-shifted normals aren't misclassified. No plot yet; no p-values ever. This task returns the table (in its scroll wrapper) in `svg` and header-rowed TSV + methods in `text`; Task 4 adds the plot bundle.

**Files:**
- Modify: `R/summarize.R` (add `.esc`, `.numeric_col`, `.char_col`, `.summary_table_html`, `fig_summary`)
- Modify: `tests/testthat/test-summarize.R` (add `fig_summary` tests)

**Interfaces:**
- Consumes: `.summary_decide`, `.fmt_continuous` (Task 2); `%||%` (from `R/forest.R`).
- Spec shape `fig_summary` accepts:
  `{ figure: "summary", data: [ {col: value, ...}, ... ],
     roles: { group: <colname> | null },
     options: { continuous: [<colname>...], categorical: [<colname>...],
                labels: { <colname>: <display label> } | null,
                overrides: { <colname>: "mean" | "median" } | null,
                show_plots: true | false,
                caption: <character> | null } }`
- Produces: `fig_summary(spec)` → `list(svg = <html string>, text = <TSV + methods sentence>)`. Task 4 extends the `svg` assembly to bundle the plot; the `text` contract is unchanged after this task.
- Errors (all readable, no leaked warnings): empty data; non-numeric value in a continuous column; **no variables selected**; **override value outside mean/median**.

- [ ] **Step 1: Write the failing table tests**

```r
# append to tests/testthat/test-summarize.R
mk_summary_spec <- function(group = "arm") {
  set.seed(7)
  age <- round(rnorm(80, 60, 10))
  los <- round(rexp(80, 1 / 5) + 1, 1); los[c(2, 5)] <- NA
  sex <- sample(c("Female", "Male"), 80, replace = TRUE)
  arm <- rep(c("A", "B"), 40)
  rows <- lapply(seq_len(80), function(i)
    list(age = age[i], length_of_stay = los[i], sex = sex[i], arm = arm[i]))
  list(figure = "summary", data = rows,
       roles = list(group = group),
       options = list(continuous = c("age", "length_of_stay"),
                      categorical = c("sex"),
                      labels = list(length_of_stay = "Length of stay"),
                      overrides = NULL, show_plots = FALSE))
}

test_that("table has one column per group plus a Missing column", {
  out <- fig_summary(mk_summary_spec())
  expect_true(grepl("<table", out$svg, fixed = TRUE))
  expect_match(out$svg, ">A \\(N=40\\)<")
  expect_match(out$svg, ">B \\(N=40\\)<")
  expect_match(out$svg, "Missing")
})

test_that("group columns keep first-appearance order, not alphabetical", {
  spec <- mk_summary_spec()
  # Flip so B appears first in the data.
  spec$data <- rev(spec$data)
  out <- fig_summary(spec)
  expect_lt(regexpr(">B (N=", out$svg, fixed = TRUE),
            regexpr(">A (N=", out$svg, fixed = TRUE))
})

test_that("continuous rows show the chosen summary and its reason", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$svg, "±")              # age -> mean ± SD
  expect_match(out$svg, "Length of stay")      # display label used
  expect_match(out$svg, "median \\(IQR\\)")    # LOS -> median (IQR)
  expect_match(out$svg, "skew|normal", ignore.case = TRUE)        # reason present
})

test_that("a variable normal within groups but shifted between them still gets mean", {
  set.seed(8)
  v <- c(rnorm(60, 55, 5), rnorm(60, 75, 5))   # pooled = bimodal mixture
  arm <- rep(c("A", "B"), each = 60)
  rows <- lapply(seq_len(120), function(i) list(v = v[i], arm = arm[i]))
  spec <- list(figure = "summary", data = rows, roles = list(group = "arm"),
               options = list(continuous = list("v"), categorical = list(),
                              show_plots = FALSE))
  out <- fig_summary(spec)
  expect_match(out$svg, "v, mean ± SD", fixed = TRUE)
  expect_match(out$svg, "within groups")       # reason names the centering
})

test_that("length_of_stay reports its 2 missing values", {
  expect_match(fig_summary(mk_summary_spec())$svg, ">2<")
})

test_that("categorical rows show n (%) with levels and an honest denominator", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$svg, "Female")
  expect_match(out$svg, "%")
  expect_match(out$svg, "of 80 with data")     # denominator stated on the variable row
})

test_that("blank group cells become an explicit (missing) column", {
  spec <- mk_summary_spec()
  spec$data[[1]]$arm <- ""
  spec$data[[2]]$arm <- NULL
  out <- fig_summary(spec)
  expect_match(out$svg, "(missing)", fixed = TRUE)
})

test_that("a group where a variable has zero non-missing values renders an em-dash cell", {
  spec <- mk_summary_spec()
  for (i in seq_along(spec$data))
    if (identical(spec$data[[i]]$arm, "B")) spec$data[[i]]$length_of_stay <- NA
  out <- fig_summary(spec)
  expect_match(out$svg, ">—<")
})

test_that("no group -> a single Overall column and no p-value anywhere", {
  spec <- mk_summary_spec(group = NULL)
  out <- fig_summary(spec)
  expect_match(out$svg, "Overall")
  expect_false(grepl("p-value", out$svg, ignore.case = TRUE))
  expect_false(grepl("p =", out$svg, fixed = TRUE))
})

test_that("override forces the summary and records that the user chose it", {
  spec <- mk_summary_spec()
  spec$options$overrides <- list(age = "median")
  out <- fig_summary(spec)
  expect_match(out$svg, "you selected", ignore.case = TRUE)
})

test_that("an override value outside mean/median errors clearly", {
  spec <- mk_summary_spec()
  spec$options$overrides <- list(age = "bogus")
  expect_error(fig_summary(spec), "override", ignore.case = TRUE)
})

test_that("zero selected variables errors clearly instead of an empty table", {
  spec <- mk_summary_spec()
  spec$options$continuous <- list(); spec$options$categorical <- list()
  expect_error(fig_summary(spec), "at least one variable", ignore.case = TRUE)
})

test_that("text is TSV with a header row plus a methods sentence", {
  out <- fig_summary(mk_summary_spec())
  expect_match(out$text, "^Characteristic\t")   # header line first
  expect_match(out$text, "mean ± SD", fixed = TRUE)
  expect_match(out$text, "median")
  expect_match(out$text, "\t")
})

test_that("a non-numeric value in a continuous column errors clearly, no warning", {
  spec <- mk_summary_spec()
  spec$data[[1]]$age <- "not-a-number"
  expect_no_warning(expect_error(fig_summary(spec), "numeric", ignore.case = TRUE))
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: FAIL — `fig_summary` not found.

- [ ] **Step 3: Write `.esc`, the column helpers, the table builder, and `fig_summary`**

```r
# append to R/summarize.R

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
      if (length(xg) == 0) "—" else .fmt_continuous(xg, kind)
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: PASS, `[ FAIL 0 | WARN 0 | ... ]`.

- [ ] **Step 5: Commit**

```bash
git add R/summarize.R tests/testthat/test-summarize.R
git commit -m "feat(summary): fig_summary table builder (groups, missing, n%, overrides, no p-values)"
```

---

### Task 4: R distribution plot + bundle table with plot

Add a faceted small-multiples distribution plot (one panel per continuous variable, pooled) with vertical mean (dashed) and median (solid) reference lines so the mean-vs-median choice is *visible, not asserted*. The legend is an **HTML teaching line** (`<div class="plot-legend">` — "dashed = mean · solid = median — when the lines separate, the variable is skewed"), styleable by the token system, not ggplot's tiny in-SVG caption. Bundle the plot inside the `svg` field's `.summary-output` wrapper, gated by `options$show_plots`; the synthetic caption renders as a `figcaption` **below** the plot in the warn register.

**Files:**
- Modify: `R/summarize.R` (add `.summary_plot_svg`; extend `fig_summary` to bundle)
- Modify: `tests/testthat/test-summarize.R` (add plot/bundle tests)

**Interfaces:**
- Consumes: `.svg_string` (from `R/dispatch.R`), `ggplot2`.
- Produces: `.summary_plot_svg(rows, continuous, labels)` → single character holding an `<svg>` (empty string if no plottable values); extends `fig_summary` so that when `options$show_plots` is `TRUE` and the plot is non-empty, the `svg` field is `<div class="summary-output"><div class="table-scroll"><table…></div><figure class="dist-plot"><svg…><div class="plot-legend">…</div><figcaption class="synthetic">…</figcaption></figure></div>`. `text` is unchanged.

- [ ] **Step 1: Write the failing plot/bundle tests**

```r
# append to tests/testthat/test-summarize.R
test_that("show_plots bundles a table AND an inline svg with the teaching legend", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- TRUE
  out <- fig_summary(spec)
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_match(out$svg, "<svg", fixed = TRUE)
  expect_match(out$svg, "plot-legend", fixed = TRUE)
  expect_match(out$svg, "dashed = mean", fixed = TRUE)
  expect_match(out$svg, "lines separate", fixed = TRUE)
})

test_that("caption is rendered when provided", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- TRUE
  spec$options$caption <- "Synthetic demonstration data — not for clinical use."
  expect_match(fig_summary(spec)$svg, "Synthetic demonstration data", fixed = TRUE)
})

test_that("all-missing continuous values render the table with no figure", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- TRUE
  spec$options$continuous <- list("length_of_stay")
  for (i in seq_along(spec$data)) spec$data[[i]]$length_of_stay <- NA
  out <- fig_summary(spec)
  expect_match(out$svg, "<table", fixed = TRUE)
  expect_false(grepl("<figure", out$svg, fixed = TRUE))
})

test_that("plotting continuous data emits no ggplot warning", {
  spec <- mk_summary_spec(); spec$options$show_plots <- TRUE
  expect_no_warning(fig_summary(spec))
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: FAIL — no `<svg` / no `plot-legend` in the bundled output.

- [ ] **Step 3: Add the plot helper and bundle in `fig_summary`**

Add the helper to `R/summarize.R`:

```r
# Faceted distribution plot: one panel per continuous variable (pooled values),
# with dashed mean and solid median reference lines so the reader sees why each
# variable got its summary. The legend is emitted as HTML by fig_summary (a
# styleable .plot-legend div), NOT as a ggplot caption. Returns an inline <svg>
# string, or "" when nothing is plottable.
.summary_plot_svg <- function(rows, continuous, labels) {
  disp <- function(col) as.character((labels %||% list())[[col]] %||% col)
  parts <- lapply(continuous, function(col) {
    x <- .numeric_col(rows, col); x <- x[!is.na(x)]
    if (length(x) == 0) return(NULL)
    data.frame(variable = disp(col), value = x,
               mean = mean(x), median = stats::median(x),
               stringsAsFactors = FALSE)
  })
  df <- do.call(rbind, parts[!vapply(parts, is.null, logical(1))])
  if (is.null(df) || nrow(df) == 0) return("")
  refs <- unique(df[c("variable", "mean", "median")])
  gg <- ggplot2::ggplot(df, ggplot2::aes(x = value)) +
    ggplot2::geom_histogram(bins = 20, fill = "grey85", colour = "white", linewidth = 0.2) +
    ggplot2::geom_vline(data = refs, ggplot2::aes(xintercept = mean),
                        linetype = "dashed", linewidth = 0.5, colour = "#2b6cb0") +
    ggplot2::geom_vline(data = refs, ggplot2::aes(xintercept = median),
                        linetype = "solid", linewidth = 0.5, colour = "#c05621") +
    ggplot2::facet_wrap(~ variable, scales = "free") +
    ggplot2::labs(x = NULL, y = "Count") +
    ggplot2::theme_minimal(base_size = 11)
  .svg_string(gg, width = 7, height = 2.6 * ceiling(length(continuous) / 2))
}
```

Then replace the `svg_field <- sprintf(...)` assembly in `fig_summary` (leave the TSV/`text` assembly untouched) with:

```r
  table_html <- .summary_table_html(headers, out_rows)

  figure_html <- ""
  if (isTRUE(opt$show_plots) && length(continuous) > 0) {
    plot_svg <- .summary_plot_svg(rows, continuous, labels)
    if (nzchar(plot_svg)) {
      legend_html <- paste0(
        "<div class=\"plot-legend\">",
        "<span class=\"mean-key\">dashed = mean</span> · ",
        "<span class=\"median-key\">solid = median</span>",
        " — when the lines separate, the variable is skewed</div>")
      cap <- opt$caption %||% ""
      cap_html <- if (nzchar(cap))
        sprintf("<figcaption class=\"synthetic\">%s</figcaption>", .esc(cap)) else ""
      figure_html <- sprintf("<figure class=\"dist-plot\">%s%s%s</figure>",
                             plot_svg, legend_html, cap_html)
    }
  }
  svg_field <- sprintf(
    "<div class=\"summary-output\"><div class=\"table-scroll\">%s</div>%s</div>",
    table_html, figure_html)
```

- [ ] **Step 4: Run to verify they pass**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: PASS, `[ FAIL 0 | WARN 0 | ... ]`.

- [ ] **Step 5: Commit**

```bash
git add R/summarize.R tests/testthat/test-summarize.R
git commit -m "feat(summary): faceted distribution plot with mean/median lines and HTML teaching legend"
```

---

### Task 5: Wire `summary` into dispatch and the worker; retire `table1` in R

Route the new figure and stop shipping the old one. `fig_summary` needs no packages beyond the boot set, so `EXTRA_PACKAGES` is untouched.

**Files:**
- Modify: `R/dispatch.R` (add `summary` case; remove `table1` case)
- Modify: `web/worker.js` (add `summarize.R` to the boot fetch loop; remove `table1.R`)
- Delete: `R/table1.R`, `tests/testthat/test-table1.R`
- Modify: `tests/testthat/test-dispatch.R` (add a round-trip test for `summary`)

**Interfaces:**
- Consumes: `fig_summary` (Task 3/4).
- Produces: `render_figure('{"figure":"summary",...}')` returns an `ok:true` payload; `render_figure('{"figure":"table1",...}')` now returns `ok:false` "Unknown figure".

- [ ] **Step 1: Write the failing dispatch test**

```r
# append to tests/testthat/test-dispatch.R
test_that("summary routes through render_figure and returns a table", {
  spec <- list(figure = "summary",
               data = list(list(age = 50, grp = "A"), list(age = 60, grp = "A"),
                           list(age = 55, grp = "B"), list(age = 65, grp = "B")),
               roles = list(group = "grp"),
               options = list(continuous = list("age"), categorical = list(),
                              show_plots = FALSE))
  out <- jsonlite::fromJSON(render_figure(jsonlite::toJSON(spec, auto_unbox = TRUE)))
  expect_true(out$ok)
  expect_match(out$svg, "<table", fixed = TRUE)
})

test_that("the retired table1 figure is no longer routed", {
  out <- jsonlite::fromJSON(render_figure('{"figure":"table1"}'))
  expect_false(out$ok)
  expect_match(out$error, "unknown figure", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "dispatch")'`
Expected: FAIL — `summary` unknown; `table1` still routes.

- [ ] **Step 3: Edit `R/dispatch.R`**

In the `switch`, remove the line `table1  = fig_table1(spec),` and add `summary = fig_summary(spec),` (place it where `table1` was, keeping alignment).

- [ ] **Step 4: Delete the retired R figure and its test**

Run:
```bash
git rm R/table1.R tests/testthat/test-table1.R
```

- [ ] **Step 5: Edit `web/worker.js` boot loop**

In the `for (const f of [...])` file list, remove `"table1.R"` and add `"summarize.R"`.

- [ ] **Step 6: Run the R suite (whole thing — checks nothing else broke)**

Run: `Rscript -e 'devtools::test()'`
Expected: PASS, `[ FAIL 0 | WARN 0 | ... ]`, with no `table1` tests remaining.

- [ ] **Step 7: Commit**

```bash
git add R/dispatch.R web/worker.js tests/testthat/test-dispatch.R
git commit -m "feat(summary): route summary figure; retire table1 in R and worker"
```

---

### Task 6: Generalize the guided session store (additive)

The KM session store is already almost generic — only the demo-options default is KM-specific. Add a generic factory so any guided shell gets identical stage/context/reset/generation semantics without touching KM's behavior. KM's `session-state.test.mjs` and e2e are the guard.

**Files:**
- Modify: `web/guided/session-state.js` (add `createSession`; make `createKmSession` delegate)
- Modify: `web/guided/session-state.test.mjs` (add a test for `createSession`)

**Interfaces:**
- Produces: `createSession(demoOptions)` → `{ stage: "understand", results: { demo: null, user: null }, demoOptions, demoGeneration: 0 }`. `resetDemo` must reset `demoOptions` back to the value the session was created with, so it captures the default via `_demoDefaults` held on the session.
- Unchanged exports: `STAGES`, `setStage`, `storeResult`, `getResult`, `setDemoOptions`, `resetDemo`, `getDemoGeneration`, `isDemoGenerationCurrent`, `createKmSession`.

- [ ] **Step 1: Write the failing test**

```js
// append to web/guided/session-state.test.mjs
import { createSession } from "./session-state.js";
{
  const s = createSession({ groupBy: null, showPlots: true });
  assert.equal(s.stage, "understand");
  assert.deepEqual(s.results, { demo: null, user: null });
  assert.deepEqual(s.demoOptions, { groupBy: null, showPlots: true });
  const s2 = setDemoOptions(s, { showPlots: false });
  const s3 = resetDemo(s2);
  assert.deepEqual(s3.demoOptions, { groupBy: null, showPlots: true },
    "resetDemo restores the created defaults");
  assert.equal(s3.demoGeneration, 1, "resetDemo bumps generation");
  console.log("ok - createSession generic factory");
}
```

(Ensure `setDemoOptions` and `resetDemo` are among the imports at the top of the test file; add them if the existing import list omits either.)

- [ ] **Step 2: Run to verify it fails**

Run: `node web/guided/session-state.test.mjs`
Expected: FAIL — `createSession` is not exported.

- [ ] **Step 3: Refactor `session-state.js`**

Replace the `createKmSession` / `resetDemo` definitions so the default is captured per session:

```js
export function createSession(demoOptions) {
  return { stage: "understand", results: { demo: null, user: null },
           demoOptions, _demoDefaults: { ...demoOptions }, demoGeneration: 0 };
}
const DEFAULT_DEMO_OPTIONS = () => ({ conf_int: true, landmarks: [], horizon: null });
export function createKmSession() { return createSession(DEFAULT_DEMO_OPTIONS()); }

export function resetDemo(session) {
  // Bumping the generation invalidates any demo run started before this reset:
  // its async result must neither store nor paint (see isDemoGenerationCurrent).
  return { ...session, results: { ...session.results, demo: null },
           demoOptions: { ...session._demoDefaults },
           demoGeneration: session.demoGeneration + 1 };
}
```

Leave `STAGES`, `setStage`, `storeResult`, `getResult`, `setDemoOptions`, `getDemoGeneration`, `isDemoGenerationCurrent` exactly as they are.

- [ ] **Step 4: Run both session tests to verify pass + no KM regression**

Run: `node web/guided/session-state.test.mjs`
Expected: PASS, including the pre-existing KM assertions and `ok - createSession generic factory`.

- [ ] **Step 5: Commit**

```bash
git add web/guided/session-state.js web/guided/session-state.test.mjs
git commit -m "refactor(guided): add generic createSession factory (KM unchanged)"
```

---

### Task 7: Extract the shared guided shell (`createGuidedShell`); convert KM

`web/guided/guided-analysis.js` holds ~150 lines of subtle logic (run/paint gating, reset-mid-run generation guard, in-flight control freezing, hash sync) that the summary shell would otherwise duplicate character-for-character. Extract it once into a parameterized factory; KM becomes consumer #1 with **byte-identical behavior**. Each factory instance owns its own session (a closure — never a shared module-level singleton), so KM and Summary can never bleed stage state into each other. The full KM unit + e2e suites gate this task **before any summary UI lands on top**.

**Files:**
- Create: `web/guided/shell.js`
- Modify: `web/guided/guided-analysis.js` (becomes the KM config + `renderGuidedKm` export)

**Interfaces:**
- Produces: `createGuidedShell(config)` → `renderGuidedShell(container, onSubmit, runFigure, setStatus)` (the 4-arg form-registry signature). Config:
  `{ title, hashPrefix, renderUnderstand(panel), exampleIntroHtml, demoLabel,
     buildDemoSpec(demoOptions), defaultDemoOptions() -> object,
     experimentControlsSelector, renderExperiments(panel, ctx, rerun),
     renderAnalyzeForm(panel, onSpec) }`
- Consumes: `createSession`, `setStage`, `storeResult`, `getResult`, `setDemoOptions`, `resetDemo`, `getDemoGeneration`, `isDemoGenerationCurrent`, `STAGES` (Task 6).
- Unchanged export: `renderGuidedKm` (same name, same signature — `app.js` untouched by this task).

- [ ] **Step 1: Write `web/guided/shell.js`** (the body is `guided-analysis.js`'s logic, parameterized; move its explanatory comments here — they document the shared logic now)

```js
// web/guided/shell.js
// Shared guided-analysis shell: Understand / Try an Example / Analyze Your Data
// stages with hash sync, per-context result caching, and demo race guards.
// Each createGuidedShell(config) instance owns its OWN session closure — two
// guided analyses never share stage state.
import { createSession, setStage, storeResult, getResult, setDemoOptions, resetDemo,
  getDemoGeneration, isDemoGenerationCurrent, STAGES } from "./session-state.js";

const STAGE_LABELS = { understand: "Understand", example: "Try an Example", analyze: "Analyze Your Data" };
// The result context each stage is allowed to paint into the shared #preview/#stats.
// A run that resolves may repaint only if its context still matches the selected
// stage; "understand" paints nothing (null never equals a context key).
const CONTEXT_FOR_STAGE = { understand: null, example: "demo", analyze: "user" };

export function createGuidedShell(cfg) {
  // Module-level per-analysis session: survives switching to another analysis
  // and back within the tab; page reload starts clean by construction.
  let session = null;
  const hashRe = new RegExp("^#" + cfg.hashPrefix + "/(\\w+)$");

  return function renderGuidedShell(container, onSubmit, runFigure, setStatus) {
    const status = setStatus || (() => {});
    session = session || createSession(cfg.defaultDemoOptions());
    // URL hash carries analysis+stage ONLY — never inputs, filenames, results.
    const fromHash = (location.hash.match(hashRe) || [])[1];
    if (fromHash && STAGES.includes(fromHash)) session = setStage(session, fromHash);

    container.innerHTML = `
      <h2>${cfg.title}</h2>
      <div class="stage-tabs" role="tablist" aria-label="Guided stages">
        ${STAGES.map((s) => `
          <button type="button" role="tab" data-stage="${s}"
            id="tab-${s}" aria-controls="panel-${s}"
            aria-selected="${s === session.stage}">${STAGE_LABELS[s]}</button>`).join("")}
      </div>
      ${STAGES.map((s) => `
        <section role="tabpanel" id="panel-${s}" aria-labelledby="tab-${s}"
          data-stage-panel="${s}" ${s === session.stage ? "" : "hidden"}></section>`).join("")}`;

    function runAndShow(spec, context) {
      const preview = document.getElementById("preview");
      const stats = document.getElementById("stats");
      preview.innerHTML = "Rendering… (first run downloads R packages)";
      stats.textContent = "";
      stats.classList.remove("error");
      status("busy", "R: working…");
      // Snapshot the demo generation so a Reset Example landing mid-run can be
      // detected on resolve and the stale result fully dropped.
      const startGen = getDemoGeneration(session);
      return runFigure(spec).then((out) => {
        // The chip reports the R session's state, not the visible pane's — set it
        // on every completion, even for results that are dropped or not painted.
        status(out.ok ? "ready" : "error", out.ok ? "R: ready" : "R: error");
        // Reset-mid-run: a demo run invalidated by Reset Example neither stores nor paints.
        if (context === "demo" && !isDemoGenerationCurrent(session, startGen)) return out;
        // Tab-switch-mid-run: paint only when this context is still the one the
        // selected stage owns. A stale-but-valid result is still stored below so it
        // reappears when its own tab is reselected.
        const shouldPaint = CONTEXT_FOR_STAGE[session.stage] === context;
        if (!out.ok) {
          if (shouldPaint) {
            preview.innerHTML = "";
            stats.textContent = "Error: " + out.error;
            stats.classList.add("error");
          }
          return out;
        }
        session = storeResult(session, context, out);
        if (shouldPaint) showStored(context);
        return out;
      });
    }

    function showStored(context) {
      const out = getResult(session, context);
      const preview = document.getElementById("preview");
      const stats = document.getElementById("stats");
      if (!out) { preview.innerHTML = ""; stats.textContent = ""; return; }
      preview.innerHTML = out.svg;
      stats.textContent = out.text;
      stats.classList.remove("error");
    }

    function selectStage(stage) {
      session = setStage(session, stage);
      history.replaceState(null, "", "#" + cfg.hashPrefix + "/" + stage);
      container.querySelectorAll("[role=tab]").forEach((t) =>
        t.setAttribute("aria-selected", String(t.dataset.stage === stage)));
      container.querySelectorAll("[data-stage-panel]").forEach((p) =>
        p.hidden = p.dataset.stagePanel !== stage);
      // Restore the context-appropriate result (demo for example stage,
      // user for analyze; understand keeps whatever is showing).
      if (stage === "example") showStored("demo");
      if (stage === "analyze") showStored("user");
    }

    container.querySelectorAll("[role=tab]").forEach((t) =>
      t.addEventListener("click", () => selectStage(t.dataset.stage)));

    const ctx = { onSubmit, runAndShow,
      getSession: () => session,
      patchDemoOptions: (patch) => { session = setDemoOptions(session, patch); },
      resetDemoState: () => { session = resetDemo(session); showStored("demo"); } };

    cfg.renderUnderstand(container.querySelector('[data-stage-panel="understand"]'));
    renderExample(container.querySelector('[data-stage-panel="example"]'), ctx);
    const analyzePanel = container.querySelector('[data-stage-panel="analyze"]');
    analyzePanel.innerHTML = "";
    cfg.renderAnalyzeForm(analyzePanel, (spec) => ctx.runAndShow(spec, "user"));
    selectStage(session.stage);
  };

  // The synthetic label is mandatory and appears TWICE: as the visible banner here
  // and, via options.caption in the demo spec builder, baked into the rendered
  // figure. Both use cfg.demoLabel directly — never a retyped copy. webR is not
  // warmed up here; the worker only boots on the first Run Example click.
  function renderExample(panel, ctx) {
    panel.innerHTML = `
      ${cfg.exampleIntroHtml}
      <div class="demo-banner" role="note">${cfg.demoLabel}</div>
      <div class="demo-actions">
        <button type="button" id="run-demo">Run Example Analysis</button>
        <button type="button" id="reset-demo">Reset Example</button>
      </div>
      <div id="demo-experiments"></div>`;
    const runBtn = panel.querySelector("#run-demo");

    // Controls that must be frozen for the duration of a run: the Run and Reset
    // buttons plus the analysis's experiment inputs. Worker requests aren't
    // serialized, so toggling an experiment mid-run could let a stale response
    // land last and silently mismatch the visible control state; disabling Reset
    // closes the reset-mid-run path at the UI (the generation counter guards it
    // in state).
    function inFlightControls() {
      return [runBtn, panel.querySelector("#reset-demo"),
        ...panel.querySelectorAll(cfg.experimentControlsSelector)];
    }

    // Shared run path: the Run button always calls this, and the experiment
    // controls call it too (conditionally) so both go through one place.
    async function runDemo() {
      const controls = inFlightControls();
      controls.forEach((el) => { el.disabled = true; });   // no duplicate/overlapping runs
      try { await ctx.runAndShow(cfg.buildDemoSpec(ctx.getSession().demoOptions), "demo"); }
      finally { controls.forEach((el) => { el.disabled = false; }); }
    }

    runBtn.addEventListener("click", runDemo);
    panel.querySelector("#reset-demo").addEventListener("click", () => {
      ctx.resetDemoState();
      renderExample(panel, ctx);                    // clears result + restores default controls
    });

    // An experiment change only reruns if a demo result already exists;
    // before the first Run click it just patches the pending options.
    cfg.renderExperiments(panel, ctx, () => {
      if (ctx.getSession().results.demo) runDemo();
    });
  }
}
```

- [ ] **Step 2: Rewrite `web/guided/guided-analysis.js` as the KM config**

```js
// web/guided/guided-analysis.js
// KM's guided shell = the shared factory + KM content/demo/form/experiments.
// Behavior must be byte-identical to the pre-factory shell; the KM unit and
// e2e suites are the regression gate.
import { createGuidedShell } from "./shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, CALLOUTS } from "./km/content.js";
import { buildDemoSpec } from "./km/demo.js";
import { KM_DEMO } from "./km/demo-data.js";
import { renderKmForm } from "../forms/km.js";

function renderKmExperiments(panel, ctx, rerun) {
  const o = ctx.getSession().demoOptions;
  panel.querySelector("#demo-experiments").innerHTML = `
    <h4>Optional experiments</h4>
    <label><input type="checkbox" id="exp-ci" ${o.conf_int ? "checked" : ""}>
      Show 95% confidence bands</label>
    <p class="callout">${CALLOUTS.confidenceBands}</p>
    <label><input type="checkbox" id="exp-landmarks" ${o.landmarks.length ? "checked" : ""}>
      Report survival at 12 and 24 months</label>
    <p class="callout">${CALLOUTS.landmarks}</p>
    <label>Displayed horizon
      <select id="exp-horizon">
        <option value="" ${o.horizon === null ? "selected" : ""}>Full follow-up (36 months)</option>
        <option value="24" ${o.horizon === 24 ? "selected" : ""}>24 months</option>
      </select></label>
    <p class="callout">${CALLOUTS.horizon}</p>`;
  panel.querySelector("#exp-ci").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ conf_int: e.target.checked }); rerun();
  });
  panel.querySelector("#exp-landmarks").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ landmarks: e.target.checked ? [12, 24] : [] }); rerun();
  });
  panel.querySelector("#exp-horizon").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ horizon: e.target.value ? Number(e.target.value) : null }); rerun();
  });
}

export const renderGuidedKm = createGuidedShell({
  title: "Kaplan–Meier",
  hashPrefix: "km",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: KM_DEMO.label,
  buildDemoSpec,
  defaultDemoOptions: () => ({ conf_int: true, landmarks: [], horizon: null }),
  experimentControlsSelector: "#exp-ci, #exp-landmarks, #exp-horizon",
  renderExperiments: renderKmExperiments,
  renderAnalyzeForm: renderKmForm,
});
```

- [ ] **Step 3: Run the JS unit suite**

Run: `npm run test:unit`
Expected: all `ok - …` lines print, exit 0.

- [ ] **Step 4: Run the KM e2e suites (the regression gate for this refactor)**

Run:
```bash
rm -rf web/R && cp -R R web/R && npx playwright test km
```
Expected: `km.spec.js` and `km-guided.spec.js` fully pass — tabs, hash, demo run, landmark experiment + Reset, context isolation, all byte-identical to before.

- [ ] **Step 5: Commit**

```bash
git add web/guided/shell.js web/guided/guided-analysis.js
git commit -m "refactor(guided): extract shared createGuidedShell factory; KM converted, behavior identical"
```

---

### Task 8: Summary teaching content (Understand stage)

Approved teaching copy that maps each documented error to a section: choosing mean/SD vs median/IQR, SD-not-SEM, missing data & denominators, reproducibility, and the Table 1 fallacy (why there are no baseline p-values). Static; verified by presence in the e2e. Note the denominator wording: the percentage denominator is the **non-missing count, stated on the variable's own row** — never claim it is "in the column header" (the header's N= includes missing rows).

**Files:**
- Create: `web/guided/summary/content.js`

**Interfaces:**
- Produces: `renderUnderstand(panel)`, `EXAMPLE_INTRO_HTML`, `CALLOUTS` (named exports) — consumed by Task 11's shell config. `CALLOUTS` keys: `groupBy`, `showPlots`, `forceMean`.

- [ ] **Step 1: Write the content module**

```js
// web/guided/summary/content.js
// Teaching copy for the guided Summary (Table 1) analysis. Each section maps to a
// documented descriptive-statistics reporting error.
const SECTIONS = [
  { title: "What a Table 1 is for", html: `
    <p>A baseline characteristics table (“Table 1”) describes who was in the study:
    the distribution of each variable, overall and — when relevant — by study group. It is a
    <em>description</em>, not a hypothesis test.</p>` },
  { title: "Mean ± SD or median (IQR)?", html: `
    <p>Report <strong>mean ± SD</strong> only when a continuous variable is approximately
    normally distributed. For skewed variables — length of stay, cost, many biomarkers —
    report the <strong>median with interquartile range</strong>. Reporting a mean for a skewed
    variable is the single most-cited descriptive-statistics error in manuscript review.</p>
    <p>This tool checks each numeric variable for you (Shapiro–Wilk test for small samples,
    skewness for large ones, assessed within your study groups), picks the appropriate
    summary, and shows a one-line reason next to the row so you can defend the choice —
    and shows the distribution so you can see it.</p>` },
  { title: "SD, never SEM", html: `
    <p>The standard deviation (SD) describes how spread out the data are. The standard error of
    the mean (SEM) is smaller and describes the precision of the mean — it is not a measure of
    dispersion. This tool always reports SD, labeled unambiguously, and never SEM.</p>` },
  { title: "Missing data and denominators", html: `
    <p>Reporting guidelines (STROBE) ask for the number of observations per variable and the
    count of missing values, with percentages computed on an unambiguous denominator. This tool
    reports a per-variable missing count and computes each percentage on the non-missing count,
    stated on the variable’s own row — the column header’s N includes rows with missing values,
    so it is never used as the percentage denominator.</p>` },
  { title: "Why there are no p-values here", html: `
    <p>In a randomized trial, any baseline difference between arms is by definition due to chance,
    so a p-value testing baseline balance answers a question no one is asking — the “Table 1
    fallacy.” CONSORT explicitly discourages baseline significance tests. This tool does not
    produce them. Describe the groups; test your outcomes elsewhere.</p>` },
];

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic baseline table</h3>
  <p>This teaching dataset contains 120 fictional participants in two arms. It deliberately mixes
  an approximately normal variable (age), two right-skewed variables (length of stay, CRP), two
  categorical variables (sex, diabetes), and some missing length-of-stay values — so you can watch
  the tool pick mean ± SD for the normal variable and median (IQR) for the skewed ones.</p>
  <blockquote><strong>Synthetic teaching data — this is not evidence about a real population.</strong></blockquote>`;

export const CALLOUTS = {
  groupBy: "Grouping splits each row into one column per arm. Percentages use the non-missing count within each arm as the denominator. Note there is still no p-value column — see “Why there are no p-values here.”",
  showPlots: "The distribution panels show each continuous variable with a dashed mean and a solid median line. When the two lines separate, the variable is skewed and median (IQR) is the honest summary.",
  forceMean: "Forcing mean ± SD on every variable reproduces the most common Table 1 error. Watch the skewed variables: the mean is pulled toward the long tail and misrepresents a typical patient.",
};

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("")
    + `<details><summary>Sources and methodology</summary>
         <p>This workflow uses base R statistics (Shapiro–Wilk normality testing, quantiles)
         and ggplot2 inside your browser. Its reporting choices follow established
         clinical-reporting guidance; the sources support the presentation principles and do not
         make this app a substitute for a study statistician.</p>
         <ul>
           <li><a href="https://www.strobe-statement.org/">STROBE Statement</a></li>
           <li><a href="https://www.bmj.com/content/389/bmj-2024-081124">CONSORT 2025 Explanation and Elaboration</a></li>
           <li><a href="https://www.equator-network.org/wp-content/uploads/2013/03/SAMPL-Guidelines-3-13-13.pdf">SAMPL Guidelines</a></li>
         </ul>
       </details>`;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/guided/summary/content.js
git commit -m "feat(summary): Understand-stage teaching content and callouts"
```

---

### Task 9: Demo spec builder

Translate the frozen demo + experiment options into a `summary` worker spec, going through the same request path as user data.

**Files:**
- Create: `web/guided/summary/demo.js`
- Create: `web/guided/summary/demo.test.mjs`
- Modify: `package.json` (append the new unit test)

**Interfaces:**
- Consumes: `SUMMARY_DEMO` (Task 1).
- Produces: `buildSummaryDemoSpec(demoOptions)` where `demoOptions = { groupBy: "arm"|null, showPlots: bool, forceMean: bool }` → a `{ figure: "summary", data, roles, options }` spec. `data` is `SUMMARY_DEMO.rows`; `roles.group` is `demoOptions.groupBy`; `options.continuous = ["age","length_of_stay","crp"]`, `options.categorical = ["sex","diabetes"]`, `options.labels` provides display names, `options.overrides` forces every continuous variable to `"mean"` when `forceMean`, `options.caption = SUMMARY_DEMO.label`.

- [ ] **Step 1: Write the failing test**

```js
// web/guided/summary/demo.test.mjs
import { buildSummaryDemoSpec } from "./demo.js";
import { SUMMARY_DEMO } from "./demo-data.js";
import assert from "node:assert";

{
  const spec = buildSummaryDemoSpec({ groupBy: "arm", showPlots: true, forceMean: false });
  assert.equal(spec.figure, "summary");
  assert.equal(spec.roles.group, "arm");
  assert.equal(spec.data.length, 120);
  assert.deepEqual(spec.options.continuous, ["age", "length_of_stay", "crp"]);
  assert.deepEqual(spec.options.categorical, ["sex", "diabetes"]);
  assert.equal(spec.options.caption, SUMMARY_DEMO.label);
  assert.equal(spec.options.show_plots, true);
  assert.ok(!spec.options.overrides || Object.keys(spec.options.overrides).length === 0);
}
{
  const spec = buildSummaryDemoSpec({ groupBy: null, showPlots: false, forceMean: true });
  assert.equal(spec.roles.group, null);
  assert.equal(spec.options.overrides.length_of_stay, "mean");
  assert.equal(spec.options.overrides.age, "mean");
  assert.equal(spec.options.show_plots, false);
}
console.log("ok - buildSummaryDemoSpec");
```

- [ ] **Step 2: Run to verify it fails**

Run: `node web/guided/summary/demo.test.mjs`
Expected: FAIL — cannot find `./demo.js`.

- [ ] **Step 3: Write the builder**

```js
// web/guided/summary/demo.js
import { SUMMARY_DEMO } from "./demo-data.js";

const CONTINUOUS = ["age", "length_of_stay", "crp"];
const CATEGORICAL = ["sex", "diabetes"];
const LABELS = { length_of_stay: "Length of stay", crp: "CRP",
  age: "Age", sex: "Sex", diabetes: "Diabetes" };

// Same request path as user data: the tutorial demonstrates the real workflow.
// The synthetic label rides along as options.caption so it is baked INTO the
// rendered figure, not only shown in the surrounding UI.
export function buildSummaryDemoSpec(demoOptions) {
  const overrides = {};
  if (demoOptions.forceMean) for (const c of CONTINUOUS) overrides[c] = "mean";
  return {
    figure: "summary",
    data: SUMMARY_DEMO.rows,
    roles: { group: demoOptions.groupBy },
    options: {
      continuous: CONTINUOUS,
      categorical: CATEGORICAL,
      labels: LABELS,
      overrides,
      show_plots: demoOptions.showPlots,
      caption: SUMMARY_DEMO.label,
    },
  };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node web/guided/summary/demo.test.mjs`
Expected: `ok - buildSummaryDemoSpec`

- [ ] **Step 5: Append to package.json and commit**

Append ` && node web/guided/summary/demo.test.mjs` to the `test:unit` script, then:
```bash
git add web/guided/summary/demo.js web/guided/summary/demo.test.mjs package.json
git commit -m "feat(summary): demo spec builder"
```

---

### Task 10: Analyze-Your-Data form (variable checklist)

Upload a CSV and configure the table through **progressive disclosure**: pre-upload, the panel shows only the heading, the privacy line, and the file input — no dead controls. On a successful parse, the panel reveals a **variable checklist** (one checkbox per column, smart defaults), an optional **group picker** (reusing `columnpicker.js`, which gains additive optional-role support), a distribution-plot toggle, and the Render button.

Classification and defaults:
- A numeric column with **≤ 5 distinct non-missing values is treated as categorical** (0/1-coded binaries become n (%), not a nonsense median).
- A column where every non-missing value is unique **and** the values are integers or strings starts **unticked** with a "looks like an ID — excluded" note (decimal-valued measurements are exempt — they are often all-unique legitimately).
- A categorical column with **> 20 levels** starts unticked with a "too many categories — excluded" note.
- Everything else starts ticked. Re-ticking any row overrides the default.

Safety and a11y: **all dynamic UI is built with DOM APIs** (`createElement`) — CSV-derived strings are never interpolated into `innerHTML`. Every checkbox gets a real `<label for>`; every row's note (type chip + optional flag) has an id and is tied to its checkbox via `aria-describedby`. Error paths: on parse failure, the stored table is cleared, the config section hides again (back to pre-upload state), and the message gets the `.error` class — a failed re-upload can never render the previous file's data. A cancelled file dialog (no `files[0]`) returns silently.

`buildSummarySpec` **projects rows down to selected + group columns** — unticked data never crosses to the worker.

**Files:**
- Modify: `web/lib/columnpicker.js` (additive `optional: true` role support)
- Modify: `web/lib/columnpicker.test.mjs` (test the optional role)
- Create: `web/guided/summary/analyze-form.js`
- Create: `web/guided/summary/analyze-form.test.mjs`
- Modify: `package.json` (append the new unit test)

**Interfaces:**
- Consumes: `parseCsv` (from `web/lib/csv.js`), `renderColumnPicker` (from `web/lib/columnpicker.js`).
- Produces: `classifyColumns(table)` → `{ kinds: {col: "continuous"|"categorical"}, flags: {col: "id"|"many-levels"|null} }` — pure, unit-testable.
- Produces: `buildSummarySpec(table, { groupBy, showPlots, selected })` → a `summary` spec; `selected` is an array of column names; rows are projected to `selected` + group; the group column is excluded from the variable lists.
- Produces: `renderSummaryForm(container, onSubmit, doc = document)` — the progressive-disclosure upload UI; calls `onSubmit(buildSummarySpec(...))` on Render.
- columnpicker: a role with `optional: true` renders a "— none —" blank choice; `current()` maps a blank optional to `null` instead of returning `null` for the whole map. Existing forms (no `optional` flag) are unaffected.

- [ ] **Step 1: Add optional-role support to columnpicker (failing test first)**

```js
// append to web/lib/columnpicker.test.mjs
{
  const table = { columns: ["a", "g"], rows: [{ a: "1", g: "x" }],
                  types: { a: "numeric", g: "categorical" } };
  let last;
  const picker = renderColumnPicker(
    mkContainer(), // reuse the file's existing fake-DOM container helper
    [{ key: "group", label: "Group by", type: "categorical", optional: true }],
    table, (v) => { last = v; });
  assert.deepEqual(last, { group: null }, "blank optional role maps to null, not an incomplete map");
  console.log("ok - columnpicker optional role");
}
```

Then in `web/lib/columnpicker.js`: the blank `<option>` label becomes `role.optional ? "— none —" : "— choose —"`, and in `current()` the single-select branch becomes:

```js
      } else {
        if (!sel.value) {
          if (!role.optional) return null;
          map[role.key] = null;
        } else {
          map[role.key] = sel.value;
        }
      }
```

Run `node web/lib/columnpicker.test.mjs` — expected: PASS including the pre-existing assertions.

- [ ] **Step 2: Write the failing analyze-form tests**

```js
// web/guided/summary/analyze-form.test.mjs
import { classifyColumns, buildSummarySpec } from "./analyze-form.js";
import assert from "node:assert";

const table = {
  columns: ["age", "crp", "diabetes", "patient_id", "site", "arm"],
  rows: Array.from({ length: 30 }, (_, i) => ({
    age: String(40 + (i % 12)),            // numeric, 12 distinct -> continuous
    crp: (1 + i * 0.37).toFixed(1),        // numeric decimals, all unique -> continuous, NOT id
    diabetes: String(i % 2),               // numeric, 2 distinct -> categorical (0/1)
    patient_id: String(1000 + i),          // integers, all unique -> id flag
    site: "S" + (i % 25),                  // categorical, 25 levels -> many-levels flag
    arm: i % 2 ? "A" : "B",
  })),
  types: { age: "numeric", crp: "numeric", diabetes: "numeric",
           patient_id: "numeric", site: "categorical", arm: "categorical" },
};

{
  const { kinds, flags } = classifyColumns(table);
  assert.equal(kinds.age, "continuous");
  assert.equal(kinds.diabetes, "categorical", "0/1-coded binary is categorical");
  assert.equal(flags.patient_id, "id", "all-unique integers flagged as ID");
  assert.equal(flags.crp, null, "all-unique decimals are NOT flagged as ID");
  assert.equal(flags.site, "many-levels", ">20 levels flagged");
  assert.equal(flags.age, null);
}
{
  const spec = buildSummarySpec(table, {
    groupBy: "arm", showPlots: true, selected: ["age", "crp", "diabetes"] });
  assert.equal(spec.figure, "summary");
  assert.equal(spec.roles.group, "arm");
  assert.deepEqual(spec.options.continuous, ["age", "crp"]);
  assert.deepEqual(spec.options.categorical, ["diabetes"]);
  assert.equal(spec.options.show_plots, true);
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "crp", "diabetes"],
    "rows are projected to selected + group columns only");
}
{
  const spec = buildSummarySpec(table, { groupBy: null, showPlots: false, selected: ["age"] });
  assert.equal(spec.roles.group, null);
  assert.deepEqual(Object.keys(spec.data[0]), ["age"]);
}
console.log("ok - classifyColumns + buildSummarySpec");
```

- [ ] **Step 3: Run to verify it fails**

Run: `node web/guided/summary/analyze-form.test.mjs`
Expected: FAIL — cannot find `./analyze-form.js`.

- [ ] **Step 4: Write the form module**

```js
// web/guided/summary/analyze-form.js
import { parseCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";

// Pure: classify every column and flag ones that should start unticked.
//   kinds: numeric with <=5 distinct non-missing values -> "categorical"
//          (0/1-coded binaries), otherwise numeric -> "continuous".
//   flags: "id" when every non-missing value is unique AND values are integers
//          or strings (all-unique DECIMALS are legitimate measurements);
//          "many-levels" when a categorical has > 20 levels.
export function classifyColumns(table) {
  const kinds = {}, flags = {};
  for (const c of table.columns) {
    const vals = table.rows.map((r) => r[c]).filter((v) => v !== "" && v != null);
    const distinct = new Set(vals).size;
    const numeric = table.types[c] === "numeric";
    kinds[c] = numeric && distinct > 5 ? "continuous" : "categorical";
    const allInt = numeric && vals.every((v) => Number.isInteger(Number(v)));
    if (vals.length > 1 && distinct === vals.length && (!numeric || allInt)) {
      flags[c] = "id";
    } else if (kinds[c] === "categorical" && distinct > 20) {
      flags[c] = "many-levels";
    } else {
      flags[c] = null;
    }
  }
  return { kinds, flags };
}

// Pure: assemble the spec. Rows are projected to selected + group columns so
// unticked data never crosses to the worker.
export function buildSummarySpec(table, { groupBy, showPlots, selected }) {
  const { kinds } = classifyColumns(table);
  const vars = table.columns.filter((c) => c !== groupBy && selected.includes(c));
  const keep = groupBy ? [...vars, groupBy] : vars;
  const data = table.rows.map((r) =>
    Object.fromEntries(keep.map((c) => [c, r[c]])));
  return {
    figure: "summary",
    data,
    roles: { group: groupBy },
    options: {
      continuous: vars.filter((c) => kinds[c] === "continuous"),
      categorical: vars.filter((c) => kinds[c] !== "continuous"),
      labels: null, overrides: {},
      show_plots: !!showPlots,
    },
  };
}

const FLAG_NOTES = { id: "looks like an ID — excluded",
                     "many-levels": "too many categories — excluded" };

// Progressive-disclosure upload UI. Pre-upload: heading + privacy line + file
// input ONLY. The config section (checklist, group picker, plot toggle, Render)
// exists but stays hidden until a parse succeeds; a parse failure re-hides it
// and clears state so a failed re-upload can never render the previous file.
// All dynamic UI is DOM-built — CSV-derived strings never touch innerHTML.
export function renderSummaryForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="summary-config" hidden></div>`;
  const config = container.querySelector("#summary-config");
  let table = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  function idFor(col) { return "var-" + col.replace(/[^A-Za-z0-9_-]/g, "_"); }

  function buildConfig() {
    config.innerHTML = "";
    const { kinds, flags } = classifyColumns(table);

    const varsLabel = doc.createElement("label");
    varsLabel.textContent = `Variables to include (${table.columns.length} columns found)`;
    config.appendChild(varsLabel);

    const list = doc.createElement("div");
    list.className = "var-list"; list.id = "summary-vars";
    const boxes = {};
    for (const c of table.columns) {
      const row = doc.createElement("div"); row.className = "var-row";
      const box = doc.createElement("input");
      box.type = "checkbox"; box.id = idFor(c); box.checked = flags[c] === null;
      const label = doc.createElement("label");
      label.htmlFor = box.id; label.className = "var-name"; label.textContent = c;
      const note = doc.createElement("span");
      note.id = box.id + "-note";
      note.className = flags[c] ? "var-note flag" : "var-note";
      note.textContent = flags[c] ? `${kinds[c]} · ${FLAG_NOTES[flags[c]]}` : kinds[c];
      box.setAttribute("aria-describedby", note.id);
      row.append(box, label, note);
      list.appendChild(row);
      boxes[c] = box;
    }
    config.appendChild(list);

    // Group picker: shared columnpicker with the new optional role. Only
    // categorical columns make sensible grouping variables.
    const groupWrap = doc.createElement("div");
    config.appendChild(groupWrap);
    let groupChoice = { group: null };
    renderColumnPicker(groupWrap,
      [{ key: "group", label: "Group by (optional)", type: "categorical", optional: true }],
      table, (v) => { groupChoice = v || { group: null }; }, doc);

    const plotsLabel = doc.createElement("label");
    const plots = doc.createElement("input");
    plots.type = "checkbox"; plots.id = "showplots"; plots.checked = true;
    plotsLabel.append(plots, doc.createTextNode(" Show distribution plots"));
    config.appendChild(plotsLabel);

    const btn = doc.createElement("button");
    btn.type = "button"; btn.id = "render"; btn.textContent = "Render Table 1";
    btn.onclick = () => {
      const selected = table.columns.filter((c) => boxes[c].checked && c !== groupChoice.group);
      onSubmit(buildSummarySpec(table, {
        groupBy: groupChoice.group, showPlots: plots.checked, selected }));
    };
    config.appendChild(btn);
  }

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;                       // cancelled dialog: no-op
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        buildConfig();
        config.hidden = false;
        doc.getElementById("stats").classList.remove("error");
      } catch (err) {
        table = null;                        // never render a previous file's data
        config.hidden = true;
        config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `node web/guided/summary/analyze-form.test.mjs`
Expected: `ok - classifyColumns + buildSummarySpec`

- [ ] **Step 6: Append to package.json and commit**

Append ` && node web/guided/summary/analyze-form.test.mjs` to the `test:unit` script, then:
```bash
git add web/lib/columnpicker.js web/lib/columnpicker.test.mjs \
        web/guided/summary/analyze-form.js web/guided/summary/analyze-form.test.mjs package.json
git commit -m "feat(summary): checklist upload form with smart defaults, projection, optional group role"
```

---

### Task 11: Guided summary shell (factory config)

The summary analysis's guided shell is a config file consuming `createGuidedShell` (Task 7) — no shell logic is duplicated. Default demo options: `{ groupBy: "arm", showPlots: true, forceMean: false }`.

**Files:**
- Create: `web/guided/summary/guided-summary.js`

**Interfaces:**
- Consumes: `createGuidedShell` (Task 7); `renderUnderstand`, `EXAMPLE_INTRO_HTML`, `CALLOUTS` (Task 8); `buildSummaryDemoSpec` (Task 9); `SUMMARY_DEMO` (Task 1); `renderSummaryForm` (Task 10).
- Produces: `renderGuidedSummary(container, onSubmit, runFigure, setStatus)` — the same 4-arg form-registry signature `renderGuidedKm` uses.

- [ ] **Step 1: Write the config**

```js
// web/guided/summary/guided-summary.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, CALLOUTS } from "./content.js";
import { buildSummaryDemoSpec } from "./demo.js";
import { SUMMARY_DEMO } from "./demo-data.js";
import { renderSummaryForm } from "./analyze-form.js";

function renderSummaryExperiments(panel, ctx, rerun) {
  const o = ctx.getSession().demoOptions;
  panel.querySelector("#demo-experiments").innerHTML = `
    <h4>Optional experiments</h4>
    <label><input type="checkbox" id="exp-group" ${o.groupBy ? "checked" : ""}>
      Group by study arm</label>
    <p class="callout">${CALLOUTS.groupBy}</p>
    <label><input type="checkbox" id="exp-plots" ${o.showPlots ? "checked" : ""}>
      Show distribution plots</label>
    <p class="callout">${CALLOUTS.showPlots}</p>
    <label><input type="checkbox" id="exp-forcemean" ${o.forceMean ? "checked" : ""}>
      Force mean ± SD on every variable</label>
    <p class="callout">${CALLOUTS.forceMean}</p>`;
  panel.querySelector("#exp-group").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ groupBy: e.target.checked ? "arm" : null }); rerun();
  });
  panel.querySelector("#exp-plots").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ showPlots: e.target.checked }); rerun();
  });
  panel.querySelector("#exp-forcemean").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ forceMean: e.target.checked }); rerun();
  });
}

export const renderGuidedSummary = createGuidedShell({
  title: "Table 1 — Summary statistics",
  hashPrefix: "summary",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: SUMMARY_DEMO.label,
  buildDemoSpec: buildSummaryDemoSpec,
  defaultDemoOptions: () => ({ groupBy: "arm", showPlots: true, forceMean: false }),
  experimentControlsSelector: "#exp-group, #exp-plots, #exp-forcemean",
  renderExperiments: renderSummaryExperiments,
  renderAnalyzeForm: renderSummaryForm,
});
```

- [ ] **Step 2: Commit**

```bash
git add web/guided/summary/guided-summary.js
git commit -m "feat(summary): guided three-stage shell as createGuidedShell config"
```

---

### Task 12: Wire the app; retire the typed form; style the new surfaces

Rename the nav key so button/registry/hash/R all say `summary` (visible label stays "Table 1"), register the guided shell, delete the typed form, and add the approved styling for the results composite and checklist. The visual reference is the approved sketch (see Approved Mockups above) — build to it.

**Files:**
- Modify: `web/index.html` (button `data-figure="table1"` → `data-figure="summary"`; label text unchanged)
- Modify: `web/app.js` (registry entry; imports)
- Modify: `web/styles.css` (results composite + checklist rules)
- Delete: `web/forms/table1.js`

**Interfaces:**
- Consumes: `renderGuidedSummary` (Task 11).

- [ ] **Step 1: Edit `web/index.html`**

Change `<button data-figure="table1">Table 1</button>` to `<button data-figure="summary">Table 1</button>`.

- [ ] **Step 2: Edit `web/app.js`**

Remove the import line `import { renderTable1Form } from "./forms/table1.js";` and add `import { renderGuidedSummary } from "./guided/summary/guided-summary.js";`.

In the `forms` registry object, remove the `table1:` entry and add `summary: renderGuidedSummary` (place it where `table1` was).

- [ ] **Step 3: Delete the typed form**

Run:
```bash
git rm web/forms/table1.js
```

- [ ] **Step 4: Append the new styles to `web/styles.css`**

All values come from existing tokens — no new colors, radii, or type sizes beyond the established scale:

```css
/* ---- Guided summary (Table 1): results composite + variable checklist ----
   Visual reference: ~/.gstack/projects/my-stats/designs/summary-table1-results-20260715/ */
.summary-output { display: flex; flex-direction: column; gap: 1rem; }
.summary-output .table-scroll { overflow-x: auto; }  /* narrow viewports scroll the table, not the page */
#preview table.table1 td:not(:first-child),
#preview table.table1 th:not(:first-child) { text-align: right; font-variant-numeric: tabular-nums; }
table.table1 .why { font-size: .6875rem; color: var(--slate); margin-top: .125rem; }
table.table1 .lvl { padding-left: 1.25rem; display: inline-block; }
figure.dist-plot { margin: 0; }
figure.dist-plot svg { max-width: 100%; height: auto; }  /* KM containment pattern */
.plot-legend { font-size: .6875rem; color: var(--slate); margin-top: .35rem; }
.plot-legend .mean-key { color: #2b6cb0; }
.plot-legend .median-key { color: #c05621; }
figcaption.synthetic {
  margin-top: .6rem; background: var(--warn-bg); border: 1px solid var(--warn-border);
  color: var(--warn-ink); border-radius: var(--radius-ctl); padding: .4rem .75rem;
  font-size: .75rem;
}
.var-list {
  border: 1px solid var(--line-soft); border-radius: var(--radius-ctl);
  padding: .25rem; max-width: 28rem;
}
.var-list .var-row {
  display: flex; align-items: center; gap: .6rem;
  padding: .45rem .6rem; border-radius: 5px; min-height: 28px;
}
.var-list .var-row:hover { background: var(--console-bg); }
.var-list input[type="checkbox"] { width: auto; accent-color: var(--accent); margin: 0; }
.var-list .var-name { font: .8125rem var(--mono); }
.var-list .var-note {
  font-size: .6875rem; color: var(--slate); background: var(--console-bg);
  border-radius: 4px; padding: .05rem .4rem;
}
.var-list .var-note.flag {
  color: var(--warn-ink); background: var(--warn-bg); border: 1px solid var(--warn-border);
}
@media (pointer: coarse) { .var-list .var-row { min-height: 44px; } }  /* touch targets */
```

- [ ] **Step 5: Run the unit suite (guards the wiring imports resolve)**

Run: `npm run test:unit`
Expected: all `ok - …` lines print, process exits 0.

- [ ] **Step 6: Manual smoke via serve (recommended)**

Run:
```bash
rm -rf web/R && cp -R R web/R && npm run serve
```
Then in a browser at `http://localhost:8321`: click **Table 1** → three tabs render. **Try an Example → Run Example Analysis** shows a right-aligned journal table with an `Age, mean ± SD` row (reason line beneath, in small slate type), a `Length of stay, median (IQR)` row, the distribution plot with the HTML legend line, and the amber synthetic caption. **Analyze Your Data** shows only the file input before upload. Compare against the approved sketch. Stop the server when done.

- [ ] **Step 7: Commit**

```bash
git add web/index.html web/app.js web/styles.css
git commit -m "feat(summary): wire guided summary as 'summary' nav key; retire typed form; style composite + checklist"
```

---

### Task 13: End-to-end guided flow

Playwright coverage of the summary-specific behavior: tabs + hash, the teaching content, the real demo computation (table + plot + legend + decisions), the force-mean experiment, separate demo/user contexts, progressive disclosure, the checklist (untick → row disappears; a11y association), and the malformed-CSV error path. Shell-generic behavior (Reset Example, reset-mid-run) is covered by the KM suite against the same shared factory — not duplicated here.

**Files:**
- Create: `tests/e2e/summary-guided.spec.js`

**Interfaces:**
- Consumes: the running app (`web/`), `tests/testthat/fixtures/summary-demo.csv` as the user upload.

- [ ] **Step 1: Write the e2e spec**

```js
// tests/e2e/summary-guided.spec.js
const { test, expect } = require("@playwright/test");
const path = require("path");

test("guided summary shows three tabs, syncs the hash, starts on Understand", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Try an Example" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analyze Your Data" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Understand" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#summary/example");
  expect(page.url()).not.toContain("csv");
});

test("Understand teaches the Table 1 fallacy and mean-vs-median", async ({ page }) => {
  await page.goto("/#summary/understand");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.getByRole("heading", { name: /Mean .* median/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /no p-values/i })).toBeVisible();
  await expect(page.getByText("SD, never SEM")).toBeVisible();
});

test("Analyze tab is progressive: no checklist or Render before a file is chosen", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.locator("#csv")).toBeVisible();
  await expect(page.locator("#summary-vars")).toBeHidden();
  await expect(page.locator("#render")).toBeHidden();
});

test("malformed CSV shows a styled error and keeps the form pre-upload", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /table 1/i }).click();
  await page.locator("#csv").setInputFiles({
    name: "bad.csv", mimeType: "text/csv",
    buffer: Buffer.from("a,b\n1,2,3\n"),   // row wider than header -> parseCsv throws
  });
  await expect(page.locator("#stats")).toHaveClass(/error/);
  await expect(page.locator("#render")).toBeHidden();
});

test("Run Example computes the real Table 1 with the right decisions, plot, and legend", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /table 1/i }).click();
  await expect(page.getByText("Synthetic demonstration data — not for clinical use.")).toBeVisible();
  await expect(page.locator("#preview table")).toHaveCount(0);
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  const preview = page.locator("#preview");
  await expect(preview).toContainText("Age, mean ± SD");                // normal -> mean±SD
  await expect(preview).toContainText("Length of stay, median (IQR)"); // skewed -> median
  await expect(preview).toContainText("Missing");
  await expect(page.locator("#preview svg")).toBeVisible();             // bundled distribution plot
  await expect(page.locator("#preview .plot-legend")).toContainText("dashed = mean");
  await expect(preview).not.toContainText("p-value");                  // Table 1 fallacy guardrail
});

test("Force mean ± SD experiment rewrites the skewed row", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /table 1/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await page.locator("#exp-forcemean").check();
  await expect(page.locator("#preview")).toContainText("Length of stay, mean ± SD",
    { timeout: 120000 });
  await expect(page.locator("#preview")).toContainText("you selected mean ± SD");
});

test("demo and user results are separate contexts; checklist controls the table", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /table 1/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await expect(page.locator("#preview table")).toHaveCount(0);   // user context empty
  await page.locator("#csv").setInputFiles(
    path.join(__dirname, "..", "testthat", "fixtures", "summary-demo.csv"));
  await expect(page.locator("#summary-vars")).toBeVisible();     // progressive reveal
  // Checklist a11y: each checkbox is described by its note.
  await expect(page.locator("#var-age")).toHaveAttribute("aria-describedby", "var-age-note");
  // Untick a variable -> its row must not render.
  await page.locator("#var-crp").uncheck();
  await page.locator("#render").click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 120000 });
  await expect(page.locator("#preview")).not.toContainText("crp");
  await page.getByRole("tab", { name: "Try an Example" }).click();
  await expect(page.locator("#preview")).toContainText("Age, mean ± SD");  // demo restored
});
```

- [ ] **Step 2: Run the full e2e suite**

Run:
```bash
rm -rf web/R && cp -R R web/R && npm run test:e2e
```
Expected: the new `summary-guided` tests pass, and the existing KM/analysis/smoke specs still pass (KM is the shared-shell regression gate).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/summary-guided.spec.js
git commit -m "test(summary): end-to-end guided flow (checklist, disclosure, a11y, decisions)"
```

---

### Task 14: Documentation

Update `CLAUDE.md` to record that Table 1 is now a guided CSV analysis (not typed numbers), that guided analyses share `createGuidedShell`, and that `fig_summary` needs no packages beyond the boot set.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Edit `CLAUDE.md`**

In the "Two input modes" / architecture area: move Table 1 from the summary-number figures to the CSV-data analyses (auto-computed, normality-aware, variable checklist); note that Kaplan–Meier and Summary statistics both route through the shared guided shell factory (`web/guided/shell.js` — a new guided analysis is a config file, never a copy of the shell), with session semantics in `web/guided/session-state.js`. Add a one-line note that `fig_summary` (`R/summarize.R`) uses only base `stats` + `ggplot2`, so it needs no `EXTRA_PACKAGES` entry. Update the "five parallel keys" example if it references `table1`.

- [ ] **Step 2: Run the full verification sweep**

Run:
```bash
Rscript -e 'devtools::test()' && npm run test:unit
```
Expected: R suite `[ FAIL 0 | WARN 0 | ... ]`; all unit `ok - …` lines print.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: Table 1 is now a guided normality-aware CSV analysis on the shared shell"
```

---

## Self-Review

**Spec coverage (against the five documented pains):**
1. Mean/SD vs median/IQR + defensible one-line why + distribution plot — Tasks 2 (decision engine: within-group centering, Shapiro n≤300, skewness above), 3 (reason shown in row), 4 (plot with mean/median lines + HTML teaching legend). ✓
2. SD not SEM, unambiguously labeled — Task 2 (`.fmt_continuous` mean branch → `mean ± SD`; SEM never computed), Task 8 (teaching). ✓
3. Missing data + denominators — Task 3 (per-variable Missing column; categorical % on the non-missing denominator, stated honestly on the variable's own row). ✓
4. Single upload → table + plot, no copy-paste/scripting, guardrails — Task 10 (checklist form with smart defaults + projection), Task 4 (bundled table+plot), Task 3 (auto decision + validations). ✓
5. Table 1 fallacy — no p-value column (hard rule enforced in Task 3, tested; teaching in Task 8; e2e asserts absence in Task 13). ✓

Replace the typed table1 — Tasks 5 (R) + 12 (JS/form; loss recorded in NOT-in-scope + TODOS.md). ✓ Guided three-stage workflow shared with KM — Tasks 6–7 (factory, KM converted) + 11 (summary config). ✓ Design spec — Task 12 styles from the approved sketch; progressive disclosure + a11y in Task 10; responsive scroll wrapper emitted by Task 3/4 and styled in Task 12. ✓

**Green-suite-at-every-commit check:** Task 1 commits only the dataset + JS guard (no R test referencing unbuilt helpers); `test-summary-demo.R` lands with `.summary_decide` in Task 2; Task 7's shell refactor is gated by the KM suites before any summary UI stacks on it. ✓

**Placeholder scan:** No TBD/TODO; every code step carries complete code; every test step names the command and expected result.

**Type consistency:** Spec option keys are consistent across tasks — R reads `options$continuous`, `options$categorical`, `options$labels`, `options$overrides`, `options$show_plots`, `options$caption`, `roles$group` (Tasks 3/4); JS `buildSummaryDemoSpec` (Task 9) and `buildSummarySpec` (Task 10) both emit exactly those keys (`show_plots` snake_case on the wire, `showPlots` only in JS-internal options). `.summary_decide` returns `{kind, reason}` used identically in Tasks 2, 3. `createGuidedShell(config)` (Task 7) is consumed with the same config shape by KM (Task 7) and summary (Task 11). `renderGuidedSummary(container, onSubmit, runFigure, setStatus)` matches the registry call in Task 12. `classifyColumns` kinds drive both the checklist notes (Task 10 UI) and the spec split (`buildSummarySpec`), so what the user sees is what R receives.

---

**Plan reviewed, amended, and rewritten clean 2026-07-15. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found → resolved | 10 findings (Claude-subagent outside voice; Codex CLI binary broken): 8 accepted, 1 mandatory red-commit fix, 1 partial→TODO |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 8 issues, 0 critical gaps — all resolved (shared shell, checklist, group-centered normality, Shapiro n≤300, validations, branch tests, one-name rename, green-commit sequencing) |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAR (FULL) | score: 6/10 → 9/10, 5 decisions — approved token-based sketch became the visual spec (styles, progressive disclosure, responsive/a11y, HTML teaching legend) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **CROSS-MODEL:** Eng review: two genuine tensions, both resolved in the outside voice's favor with user approval: pooled normality decision → group-centered residuals; Shapiro n≤5000 gate → skewness-only above n=300. Remaining outside-voice findings were additive — no unresolved disagreement. Design review ran scoped to the two new surfaces (user's choice); design outside voices were not run (Codex CLI broken; sketch approval served as the reference gate).
- **VERDICT:** ENG + DESIGN CLEARED — ready to implement (reviews at commit b230a56, 2026-07-15). All review decisions are merged directly into the task bodies of this rewrite (2026-07-15); there is no separate amendments layer. Approved visual reference: `~/.gstack/projects/my-stats/designs/summary-table1-results-20260715/`.

NO UNRESOLVED DECISIONS

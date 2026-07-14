# Guided Kaplan–Meier — Stage A (Demo + Education) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the educational + demonstration layer of the Guided Analysis KM pilot — Understand / Try an Example / Analyze Your Data tabs, a frozen synthetic demo running through the real webR pipeline, reversible learning experiments, and a publication-grade figure (CI bands + censor marks + aligned risk table) — while cutting the KM cold-load roughly in half by dropping survminer.

**Architecture:** Static vanilla-JS + webR. JS owns navigation, session state, and presentation; R (`fig_km`) remains the only source of statistical values and figure geometry. The existing `{figure, data, options}` worker contract and `{ok, svg, text}` response are unchanged — Stage A adds *options* to the KM spec, not a new result schema. KM's plot is rebuilt in plain ggplot2 from `survfit` output and composed with an aligned number-at-risk table via cowplot, replacing survminer (~65 MB → ~10 MB of lazy KM packages).

**Tech Stack:** R (`survival`, `ggplot2`, `cowplot`, `svglite`), vanilla ES modules, plain-Node unit tests, Playwright e2e.

**Canonical spec:** `.scratch/guided-analysis-km/PRD.md` (this plan implements its Understand/Try-an-Example scope plus figure quality; see "Deferred to Stage B" at the end for the explicit non-goals). Teaching copy source: `.scratch/guided-analysis-km/content/km-learning-journey.md`.

## Global Constraints

- No framework, backend, account, analytics, or browser persistence (memory-only state; reload starts clean).
- No transmission of user data; the only network calls are the webR CDN and `fetch("R/*.R")`.
- JavaScript never computes statistics; R/webR is the only source of estimates, tests, and figure coordinates.
- Full R suite must end `[ FAIL 0 | WARN 0 | ... ]` — WARN 0 is a hard gate; run via `Rscript -e 'devtools::test()'`, never `testthat::test_file`.
- `web/R/` is a gitignored build copy: `rm -rf web/R && cp -R R web/R` before any browser test; never commit it.
- The other seven analyses must keep their exact current behavior (their forms, dispatch, and tests unchanged).
- Reuse `%||%` (defined in `R/forest.R`) and `.svg_string()` (in `R/dispatch.R`); do not redefine either.
- Mandatory demo labeling, exact strings: result caption/banner **"Synthetic demonstration data — not for clinical use."**; teaching intro blockquote **"Synthetic teaching data—this is not evidence about a real treatment."** These may not be paraphrased.
- P-values: three decimals, `p < 0.001` below that; never `p = 0.000` (already enforced by Stage 0 — do not regress).
- The worktree contains unrelated in-progress edits (`web/app.js`, `web/index.html`, `web/styles.css`, `CLAUDE.md`, `.gitignore`, `playwright.config.js`); commit only the files each task names.

## File Structure

```
data-raw/km-demo-generator.R        # deterministic generator (seed 23) — writes the two frozen artifacts
tests/testthat/fixtures/km-demo.csv # frozen 120-row demo (canonical, versioned)
web/guided/km/demo-data.js          # same rows embedded as a JS module (generated, do not hand-edit)
web/guided/km/demo.js               # buildDemoSpec(options) -> worker spec
web/guided/km/content.js            # approved teaching copy (verbatim from content doc)
web/guided/km/teaching-visual.js    # labeled non-data illustration (inline SVG)
web/guided/session-state.js         # pure in-memory KM session store
web/guided/guided-analysis.js       # tabbed shell: stages, hash sync, run-and-show
R/km.R                              # pure-ggplot2 figure + risk table + new options
```

Existing files modified: `R/km.R`, `DESCRIPTION`, `web/worker.js`, `web/app.js`, `web/index.html`, `web/styles.css`, `package.json` (test glob only), `tests/e2e/km.spec.js`, `tests/testthat/test-km.R`, `CLAUDE.md`.

---

### Task 0: Commit the Stage 0 hardening already in the worktree

Stage 0 (safe p formatting, explicit HR direction, withheld unreliable HRs, strict time validation in R and JS) is complete, verified (R suite 85 pass / WARN 0, unit green, KM e2e green) but uncommitted.

- [ ] **Step 1: Commit exactly the Stage 0 files**

```bash
git add R/km.R tests/testthat/test-km.R web/forms/km.js web/forms/km.test.mjs package.json
git commit -m "fix: harden KM statistical reporting (safe p, explicit HR direction, withheld unreliable HR, strict parsing)"
git diff --check
```

Note: `package.json` also carries the pre-existing serve-port edit (8080→8321); committing it here is intended — it matches `playwright.config.js`'s expected port.

---

### Task 1: Freeze the Demonstration Dataset

Fixed, versioned, never generated at runtime (PRD: Demonstration Dataset contract). Seed 23 of the generator below is already verified to hit every pinned teaching target.

**Files:**
- Create: `data-raw/km-demo-generator.R`
- Create: `tests/testthat/fixtures/km-demo.csv` (by running the generator)
- Create: `web/guided/km/demo-data.js` (by running the generator)
- Create: `web/guided/km/demo-data.test.mjs`
- Create: `tests/testthat/test-km-demo.R`
- Modify: `package.json` (append the new unit test)

**Interfaces:**
- Produces: `KM_DEMO` (JS named export): `{ version: "1.0.0", label: "Synthetic demonstration data — not for clinical use.", columns: [...], rows: [{ participant_id, followup_months, status /* "Death"|"Censored" */, group /* "Standard care"|"New treatment" */ }] }` — consumed by Task 6's `buildDemoSpec`.
- Produces: `tests/testthat/fixtures/km-demo.csv` with header `participant_id,followup_months,status,group` — consumed by Task 3's R tests.

- [ ] **Step 1: Write the generator**

```r
# data-raw/km-demo-generator.R
# Deterministic generator for the frozen KM Demonstration Dataset.
# Seed 23 is verified against the pinned teaching targets (see test-km-demo.R).
# Rerunning MUST reproduce the committed artifacts byte-for-byte; if you change
# anything here, bump KM_DEMO.version and re-pin every expected value.
set.seed(23)
n <- 60
t_std <- rexp(n, rate = log(2) / 26)
t_new <- rexp(n, rate = log(2) / 40)
drop_std <- rexp(n, rate = log(2) / 70)
drop_new <- rexp(n, rate = log(2) / 70)
admin_std <- runif(n, 24, 36)
admin_new <- runif(n, 24, 36)
time_std <- pmin(t_std, drop_std, admin_std)
time_new <- pmin(t_new, drop_new, admin_new)
df <- data.frame(
  followup_months = round(c(time_std, time_new), 1),
  event = c(as.integer(t_std <= pmin(drop_std, admin_std)),
            as.integer(t_new <= pmin(drop_new, admin_new))),
  group = rep(c("Standard care", "New treatment"), each = n))
df$followup_months[df$followup_months < 0.1] <- 0.1
out <- data.frame(
  participant_id = sprintf("P%03d", seq_len(nrow(df))),
  followup_months = df$followup_months,
  status = ifelse(df$event == 1, "Death", "Censored"),
  group = df$group)
write.csv(out, "tests/testthat/fixtures/km-demo.csv", row.names = FALSE, quote = FALSE)

rows_json <- jsonlite::toJSON(out, dataframe = "rows", digits = NA)
js <- paste0(
  "// GENERATED by data-raw/km-demo-generator.R — do not hand-edit.\n",
  "export const KM_DEMO = {\n",
  '  version: "1.0.0",\n',
  '  label: "Synthetic demonstration data \\u2014 not for clinical use.",\n',
  '  columns: ["participant_id", "followup_months", "status", "group"],\n',
  "  rows: ", rows_json, "\n};\n")
writeLines(js, "web/guided/km/demo-data.js")
cat("md5(csv):", unname(tools::md5sum("tests/testthat/fixtures/km-demo.csv")), "\n")
```

- [ ] **Step 2: Run it and check the checksum**

Run: `mkdir -p web/guided/km && Rscript data-raw/km-demo-generator.R`
Expected: `md5(csv): f6559728fcf5429cb199747760f92ebf`
(If the md5 differs, STOP — the generator no longer reproduces the verified dataset; do not re-pin numbers to make tests pass.)

- [ ] **Step 3: Write the failing R test pinning the teaching targets**

```r
# tests/testthat/test-km-demo.R
demo_df <- function() {
  df <- read.csv(test_path("fixtures", "km-demo.csv"))
  df$event <- as.integer(df$status == "Death")
  df$group <- factor(df$group, levels = c("Standard care", "New treatment"))
  df
}

test_that("demo dataset is frozen (shape and checksum)", {
  expect_equal(unname(tools::md5sum(test_path("fixtures", "km-demo.csv"))),
               "f6559728fcf5429cb199747760f92ebf")
  df <- demo_df()
  expect_equal(nrow(df), 120)
  expect_equal(as.vector(table(df$group)), c(60, 60))
  expect_equal(sum(df$event), 52)   # 30 Standard care + 22 New treatment
})

test_that("demo dataset hits every pinned teaching target", {
  df <- demo_df()
  fit <- survival::survfit(survival::Surv(followup_months, event) ~ group, data = df)
  tab <- summary(fit)$table
  expect_equal(unname(tab["group=Standard care", "median"]), 26.0, tolerance = 1e-6)
  expect_true(is.na(tab["group=New treatment", "median"]))            # not reached
  sd <- survival::survdiff(survival::Surv(followup_months, event) ~ group, data = df)
  p <- 1 - stats::pchisq(sd$chisq, 1)
  expect_equal(unname(sd$chisq), 2.578, tolerance = 1e-3)
  expect_equal(p, 0.1084, tolerance = 1e-4)                           # > 0.05, close
  cox <- survival::coxph(survival::Surv(followup_months, event) ~ group, data = df)
  expect_equal(unname(exp(coef(cox))), 0.6392, tolerance = 1e-4)      # New vs Standard
  ci <- exp(confint(cox))
  expect_equal(unname(ci[1]), 0.3683, tolerance = 1e-4)
  expect_equal(unname(ci[2]), 1.1091, tolerance = 1e-4)               # CI contains 1
  s <- summary(fit, times = c(12, 24), extend = TRUE)
  expect_equal(round(100 * s$surv, 1), c(73.5, 51.2, 84.4, 64.9))     # Std12,Std24,New12,New24
  expect_equal(s$n.risk, c(39, 27, 46, 32))                           # adequate 12/24 support
})
```

- [ ] **Step 4: Run R tests**

Run: `Rscript -e 'devtools::test(filter = "km-demo")'`
Expected: PASS (the artifacts exist from Step 2, so these pass immediately — their job is to freeze the contract).

- [ ] **Step 5: Write the JS fixture test**

```js
// web/guided/km/demo-data.test.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { KM_DEMO } from "./demo-data.js";

assert.equal(KM_DEMO.version, "1.0.0");
assert.equal(KM_DEMO.label, "Synthetic demonstration data — not for clinical use.");
assert.equal(KM_DEMO.rows.length, 120);
assert.deepEqual(KM_DEMO.columns, ["participant_id", "followup_months", "status", "group"]);
const groups = KM_DEMO.rows.reduce((m, r) => (m[r.group] = (m[r.group] || 0) + 1, m), {});
assert.deepEqual(groups, { "Standard care": 60, "New treatment": 60 });
for (const r of KM_DEMO.rows) {
  assert.match(r.participant_id, /^P\d{3}$/);
  assert.equal(typeof r.followup_months, "number");
  assert.ok(r.followup_months >= 0.1);
  assert.ok(["Death", "Censored"].includes(r.status));
}
// JS module and R fixture must be the same data
const csv = readFileSync("tests/testthat/fixtures/km-demo.csv", "utf8").trim().split("\n");
assert.equal(csv.length - 1, 120);
const first = csv[1].split(",");
assert.equal(first[0], KM_DEMO.rows[0].participant_id);
assert.equal(Number(first[1]), KM_DEMO.rows[0].followup_months);
console.log("demo-data.test.mjs OK");
```

- [ ] **Step 6: Wire into test:unit and run**

In `package.json`, extend the script:

```json
"test:unit": "node web/lib/csv.test.mjs && node web/lib/columnpicker.test.mjs && node web/forms/km.test.mjs && node web/guided/km/demo-data.test.mjs"
```

Run: `npm run test:unit`
Expected: all four `... OK` lines.

- [ ] **Step 7: Commit**

```bash
git add data-raw/km-demo-generator.R tests/testthat/fixtures/km-demo.csv \
  web/guided/km/demo-data.js web/guided/km/demo-data.test.mjs \
  tests/testthat/test-km-demo.R package.json
git commit -m "feat: freeze versioned KM demonstration dataset with pinned targets"
```

---

### Task 2: Rebuild the KM figure in plain ggplot2 with an aligned risk table (drop survminer)

Replaces `survminer::ggsurvplot` with a hand-built plot from `survfit` output plus a cowplot-composed number-at-risk table. Motivation (measured 2026-07-14): the KM lazy-package download falls from ~65 MB (survminer + ggpubr + rstatix + car…) to ~10 MB (`survival` 7.4 MB + `cowplot`), roughly halving demo cold-load; and the risk table — silently dropped since the 2026-07-13 plan — becomes real. Composition via `cowplot::plot_grid(..., align = "v", axis = "lr")` is spike-verified (risk counts land at the exact axis-tick x-coordinates).

**Files:**
- Modify: `R/km.R`
- Modify: `DESCRIPTION` (Imports: remove `survminer`, add `cowplot`)
- Modify: `web/worker.js` (`EXTRA_PACKAGES.km`)
- Modify: `tests/testthat/test-km.R`

**Interfaces:**
- Consumes: existing spec shape `{figure:"km", data:[{time,status,group}], options:{time_label, theme}}`.
- Produces: same `{svg, text}` contract; internal helpers `.km_curve_df(fit)` and `.km_step_df(d)` (tested directly via `manuscriptfigures:::`). SVG now always contains CI bands, censor marks, and a "Number at risk" table.

- [ ] **Step 1: Write failing unit tests for the step-geometry helpers**

Append to `tests/testthat/test-km.R`:

```r
test_that(".km_step_df expands rows into exact step coordinates", {
  d <- data.frame(time = c(0, 2, 5), surv = c(1, .8, .4),
                  lower = c(1, .6, .2), upper = c(1, .95, .7),
                  n.censor = 0, group = "A", stringsAsFactors = FALSE)
  s <- manuscriptfigures:::.km_step_df(d)
  # (t1,y1),(t2,y1),(t2,y2),(t3,y2),(t3,y3)
  expect_equal(s$time, c(0, 2, 2, 5, 5))
  expect_equal(s$surv, c(1, 1, .8, .8, .4))
  expect_equal(s$lower, c(1, 1, .6, .6, .2))
})

test_that(".km_curve_df prepends a time-zero row per group", {
  df <- data.frame(time = c(1, 2, 1, 3), status = c(1, 0, 1, 1),
                   group = c("A", "A", "B", "B"))
  fit <- survival::survfit(survival::Surv(time, status) ~ group, data = df)
  d <- manuscriptfigures:::.km_curve_df(fit)
  t0 <- d[d$time == 0, ]
  expect_setequal(t0$group, c("A", "B"))
  expect_true(all(t0$surv == 1))
})

test_that("fig_km SVG contains the risk table and censor marks", {
  s <- make_spec()  # existing two-group helper in this file
  out <- fig_km(s)
  expect_match(out$svg, "Number at risk", fixed = TRUE)
  expect_match(out$svg, ">Group<|>group<|legend", ignore.case = TRUE)  # legend present
})

test_that("R/km.R no longer references survminer", {
  src <- readLines(file.path("..", "..", "R", "km.R"))
  expect_false(any(grepl("survminer", src)))
})
```

- [ ] **Step 2: Run to verify failure**

Run: `Rscript -e 'devtools::test(filter = "km")'`
Expected: FAIL — `.km_step_df` not found; survminer grep fails.

- [ ] **Step 3: Rewrite the figure portion of `R/km.R`**

Keep the Stage 0 validation, `fmt_p`, coxph handling, and text assembly EXACTLY as they are. Replace only the plotting block (`gg <- suppressWarnings(survminer::ggsurvplot(...)); plot_obj <- gg$plot ...`) and add the helpers:

```r
# Rows of (time, surv, lower, upper, n.censor, group) per stratum, with a
# time-zero row so every curve starts at S(0) = 1 with a degenerate CI.
.km_curve_df <- function(fit) {
  s <- summary(fit, censored = TRUE)
  grp <- if (is.null(s$strata)) "All" else sub("^group=", "", as.character(s$strata))
  d <- data.frame(time = s$time, surv = s$surv,
                  lower = ifelse(is.na(s$lower), NA_real_, s$lower),
                  upper = ifelse(is.na(s$upper), NA_real_, s$upper),
                  n.censor = s$n.censor, group = grp, stringsAsFactors = FALSE)
  t0 <- data.frame(time = 0, surv = 1, lower = 1, upper = 1, n.censor = 0,
                   group = unique(grp), stringsAsFactors = FALSE)
  rbind(t0, d)
}

# Duplicate points so ribbons/lines through them reproduce step geometry:
# (t1,y1),(t2,y1),(t2,y2),(t3,y2),...,(tn,yn)
.km_step_df <- function(d) {
  do.call(rbind, lapply(split(d, d$group), function(g) {
    g <- g[order(g$time), ]
    n <- nrow(g)
    if (n < 2) return(g)
    val_idx  <- rep(seq_len(n), each = 2)[-(2 * n)]  # 1,1,2,2,...,n-1,n-1,n
    time_idx <- rep(seq_len(n), each = 2)[-1]        # 1,2,2,3,3,...,n,n
    out <- g[val_idx, , drop = FALSE]
    out$time <- g$time[time_idx]
    out
  }))
}

# Accessible qualitative palette (Tol bright); hcl fallback beyond 6 groups.
.km_palette <- function(n) {
  tol <- c("#4477AA", "#CC6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377")
  if (n <= length(tol)) tol[seq_len(n)] else grDevices::hcl.colors(n, "Dark 2")
}
```

And the plot block (inside `fig_km`, after `fit`/`lr`/`p` are computed):

```r
  curve_df <- .km_curve_df(fit)
  step_df  <- .km_step_df(curve_df)
  censor_df <- curve_df[curve_df$n.censor > 0, , drop = FALSE]
  n_groups <- length(unique(curve_df$group))
  pal <- .km_palette(n_groups)
  x_max <- max(curve_df$time)
  breaks <- pretty(c(0, x_max), n = 6)
  x_scale <- ggplot2::scale_x_continuous(limits = range(breaks), breaks = breaks,
                                         expand = ggplot2::expansion(mult = c(0.01, 0.02)))

  main <- ggplot2::ggplot(curve_df,
      ggplot2::aes(x = time, y = surv, color = group, linetype = group)) +
    ggplot2::geom_ribbon(data = step_df,
      ggplot2::aes(ymin = lower, ymax = upper, fill = group),
      alpha = 0.15, color = NA, show.legend = FALSE) +
    ggplot2::geom_step(linewidth = 0.7) +
    ggplot2::geom_point(data = censor_df, shape = 3, size = 1.8, show.legend = FALSE) +
    x_scale +
    ggplot2::scale_y_continuous(limits = c(0, 1)) +
    ggplot2::scale_color_manual(values = pal) +
    ggplot2::scale_fill_manual(values = pal) +
    ggplot2::labs(x = time_label, y = "Survival probability",
                  color = "Group", linetype = "Group") +
    .fig_theme(spec$options$theme)
  if (n_groups == 1) main <- main + ggplot2::theme(legend.position = "none")

  r <- summary(fit, times = breaks, extend = TRUE)
  risk_df <- data.frame(
    time = r$time, n.risk = r$n.risk,
    group = if (is.null(r$strata)) "All" else sub("^group=", "", as.character(r$strata)))
  risk_tab <- ggplot2::ggplot(risk_df,
      ggplot2::aes(x = time, y = group, label = n.risk)) +
    ggplot2::geom_text(size = 3.1) +
    x_scale +
    ggplot2::labs(title = "Number at risk", x = NULL, y = NULL) +
    ggplot2::theme_minimal(base_size = 10) +
    ggplot2::theme(panel.grid = ggplot2::element_blank(),
                   axis.text.x = ggplot2::element_blank(),
                   plot.title = ggplot2::element_text(size = 9, face = "bold"))

  plot_obj <- cowplot::plot_grid(main, risk_tab, ncol = 1,
                                 rel_heights = c(0.78, 0.22),
                                 align = "v", axis = "lr")
```

At the end, change the SVG height for the taller composed figure:

```r
  list(svg = .svg_string(plot_obj, width = 7, height = 6), text = txt)
```

Remove the now-dead `suppressWarnings(survminer::ggsurvplot(...))` block and its comment entirely.

- [ ] **Step 4: Run KM tests, then the full suite**

Run: `Rscript -e 'devtools::test(filter = "km")'` then `Rscript -e 'devtools::test()'`
Expected: all PASS, WARN 0. If ggplot2 warns about the ribbon's NA CI rows in sparse tails, drop NA-CI rows from `step_df` before plotting (`step_df[!is.na(step_df$lower), ]`) — never blanket-suppress.

- [ ] **Step 5: Swap the package wiring**

`DESCRIPTION` Imports — remove `survminer`, add `cowplot`:

```
Imports: ggplot2, survival, cowplot, svglite, jsonlite, knitr, grDevices, stats, pROC, gtsummary, broom, broom.helpers
```

`web/worker.js`:

```js
const EXTRA_PACKAGES = { km: ["survival", "cowplot"], roc: ["pROC"], regression: ["gtsummary", "broom", "broom.helpers"] };
```

Also update the two comments in worker.js that name survminer ("survminer's large dependency tree") to say "the KM package tree".

- [ ] **Step 6: Verify in a real browser**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/km.spec.js`
Expected: 1 passed. (This exercises the cowplot install path in webR.)

- [ ] **Step 7: Commit**

```bash
git add R/km.R DESCRIPTION web/worker.js tests/testthat/test-km.R
git commit -m "feat: pure-ggplot2 KM figure with aligned risk table; drop survminer (~55 MB lighter)"
```

---

### Task 3: KM analysis options — conf_int, landmarks, horizon, reference, caption + median reporting

The three Guided Experiments (Task 7) and the demo's explicit reference direction are R capabilities, not UI tricks. All are equally useful to real users.

**Files:**
- Modify: `R/km.R`
- Modify: `tests/testthat/test-km.R`

**Interfaces:**
- Consumes: helpers from Task 2.
- Produces: `spec$options` gains `conf_int` (logical, default TRUE), `landmarks` (numeric vector, default empty), `horizon` (number, display-only x cutoff), `reference` (group label string → Cox reference level), `caption` (string → figure caption). Text gains per-group median sentences and, when landmarks are requested, per-group landmark sentences. Task 6/7 build specs against exactly these names.

- [ ] **Step 1: Write failing tests**

Append to `tests/testthat/test-km.R`:

```r
# Tiny hand-computable fixture: one group, events at 1,2,3,4 (no censoring).
# KM: S(1)=.75, S(2)=.50, S(2.5)=.50 — median = 2.
uncensored_spec <- function() {
  km_spec(time = c(1, 2, 3, 4), status = c(1, 1, 1, 1), group = rep("A", 4))
}

test_that("fig_km reports per-group medians with not-reached state", {
  out <- fig_km(uncensored_spec())
  expect_match(out$text, "Median survival: A 2.0", fixed = TRUE)
  s <- km_spec(time = c(10, 11, 12), status = c(0, 0, 0), group = rep("A", 3))
  out2 <- fig_km(s)
  expect_match(out2$text, "not reached", fixed = TRUE)
})

test_that("landmark option reports estimate with CI at requested times", {
  s <- uncensored_spec(); s$options$landmarks <- c(2.5)
  out <- fig_km(s)
  expect_match(out$text, "At 2.5 Months, survival was 50.0%", fixed = TRUE)
  expect_match(out$text, "95% CI", fixed = TRUE)
})

test_that("reference option controls HR direction", {
  s <- strong_two_group_spec()             # existing fixture: events concentrated in A
  s$options$reference <- "B"
  out <- fig_km(s)
  expect_match(out$text, "A vs B", fixed = TRUE)   # numerator flips
  s$options$reference <- "Nope"
  expect_error(fig_km(s), "reference")
})

test_that("conf_int, horizon, and caption affect the figure not the statistics", {
  s <- strong_two_group_spec()
  base <- fig_km(s)
  s2 <- s; s2$options$conf_int <- FALSE
  expect_false(grepl("fill-opacity", fig_km(s2)$svg))   # ribbon gone
  expect_true(grepl("fill-opacity", base$svg))
  s3 <- s; s3$options$horizon <- 2
  expect_equal(fig_km(s3)$text, base$text)              # display-only
  s4 <- s; s4$options$caption <- "Synthetic demonstration data"
  expect_match(fig_km(s4)$svg, "Synthetic demonstration data", fixed = TRUE)
})
```

- [ ] **Step 2: Run to verify failure**

Run: `Rscript -e 'devtools::test(filter = "km")'` — Expected: new tests FAIL (options ignored, no median text).

- [ ] **Step 3: Implement in `R/km.R`**

Early in `fig_km`, after building `df`:

```r
  opts <- spec$options %||% list()
  ref <- opts$reference
  if (!is.null(ref)) {
    if (!ref %in% df$group) stop(sprintf("reference '%s' is not one of the groups.", ref))
    df$group <- stats::relevel(factor(df$group), ref = ref)
  }
```

Median + landmark text, inserted after the existing log-rank/HR text assembly (append to `txt`; use full-precision values, format at the end — never parse display strings back):

```r
  fmt1 <- function(x) sprintf("%.1f", x)
  med_tab <- summary(fit)$table
  if (is.null(dim(med_tab))) med_tab <- t(as.matrix(med_tab))  # single-group case
  med_lines <- vapply(seq_len(nrow(med_tab)), function(i) {
    g <- sub("^group=", "", rownames(med_tab)[i] %||% unique(df$group)[i])
    m <- med_tab[i, "median"]
    if (is.na(m)) sprintf("%s not reached", g)
    else sprintf("%s %s %s", g, fmt1(m), time_label)
  }, character(1))
  txt <- paste0(txt, " Median survival: ", paste(med_lines, collapse = "; "), ".")

  landmarks <- opts$landmarks %||% numeric(0)
  if (length(landmarks) > 0) {
    lm <- summary(fit, times = as.numeric(landmarks), extend = TRUE)
    lg <- if (is.null(lm$strata)) rep(unique(df$group)[1], length(lm$time))
          else sub("^group=", "", as.character(lm$strata))
    lm_lines <- sprintf("At %s %s, survival was %s%% (95%% CI %s%%–%s%%) in %s",
                        fmt1(lm$time), time_label, fmt1(100 * lm$surv),
                        fmt1(100 * lm$lower), fmt1(100 * lm$upper), lg)
    txt <- paste0(txt, " ", paste(lm_lines, collapse = "; "), ".")
  }
```

Figure options (in the Task 2 plot block):

```r
  conf_int <- opts$conf_int %||% TRUE
  # build `main` without the ribbon, then add it conditionally:
  if (isTRUE(conf_int)) main <- main + ggplot2::geom_ribbon(data = step_df,
      ggplot2::aes(ymin = lower, ymax = upper, fill = group),
      alpha = 0.15, color = NA, show.legend = FALSE)
  if (!is.null(opts$caption)) main <- main + ggplot2::labs(caption = opts$caption)
  horizon <- opts$horizon
  if (!is.null(horizon)) {
    main <- main + ggplot2::coord_cartesian(xlim = c(0, as.numeric(horizon)))
    risk_tab <- risk_tab + ggplot2::coord_cartesian(xlim = c(0, as.numeric(horizon)))
  }
```

(Refactor note: move the `geom_ribbon` out of the base `main` construction so the conditional is the only place it is added. Layer order — add the ribbon *before* `geom_step` so curves draw on top: build `main` as `ggplot(...) + x_scale + ...`, then `if (conf_int) main <- main + ribbon`, then `main <- main + geom_step + geom_point + scales + labs + theme`. ggplot2 draws layers in addition order, so add ribbon first.)

- [ ] **Step 4: Run KM tests, then the full suite**

Run: `Rscript -e 'devtools::test(filter = "km")'` then `Rscript -e 'devtools::test()'`
Expected: all PASS, WARN 0. Update any Stage 0 text assertions if the appended median sentence changed exact-match expectations (`expect_match` with `fixed = TRUE` on substrings should be unaffected).

- [ ] **Step 5: Commit**

```bash
git add R/km.R tests/testthat/test-km.R
git commit -m "feat: KM options (CI bands, landmarks, display horizon, reference, caption) and median reporting"
```

---

### Task 4: Session state and the guided tab shell

**Files:**
- Create: `web/guided/session-state.js`
- Create: `web/guided/session-state.test.mjs`
- Create: `web/guided/guided-analysis.js`
- Modify: `web/app.js`, `web/index.html`, `web/styles.css`, `package.json` (test glob)
- Create: `tests/e2e/km-guided.spec.js`

**Interfaces:**
- Produces: `createKmSession()`, `setStage(session, stage)`, `storeResult(session, context, result)`, `getResult(session, context)`, `setDemoOptions(session, patch)`, `resetDemo(session)` — pure functions over a plain object; `STAGES = ["understand", "example", "analyze"]`.
- Produces: `renderGuidedKm(container, onSubmit, runFigure)` registered in `web/app.js`'s form registry for `km` only. `runFigure(spec) -> Promise<{ok, svg?, text?, error?}>` is `app.js`'s existing export, passed in to avoid a circular import.
- Produces: stage panels carry `data-stage-panel="<stage>"`; Tasks 5–8 render INTO these panels via functions the shell calls: `renderUnderstand(panel)` (Task 5), `renderExample(panel, session, runAndShow)` (Task 6/7), `renderAnalyze(panel, onSubmit)` (Task 8). Until those tasks land, the shell shows built-in placeholder text per panel.
- Produces: `runAndShow(spec, context)` on the shell — sends the spec through `runFigure`, writes `#preview`/`#stats` exactly like `app.js`'s `render()` (busy text, error class, status chip), stores the result via `storeResult`, and re-shows the stored result for a context when its tab is re-selected.

- [ ] **Step 1: Write failing state tests**

```js
// web/guided/session-state.test.mjs
import assert from "node:assert/strict";
import { createKmSession, setStage, storeResult, getResult, setDemoOptions, resetDemo, STAGES }
  from "./session-state.js";

assert.deepEqual(STAGES, ["understand", "example", "analyze"]);
let s = createKmSession();
assert.equal(s.stage, "understand");
s = setStage(s, "example");
assert.equal(s.stage, "example");
assert.throws(() => setStage(s, "bogus"), /stage/);

s = storeResult(s, "demo", { svg: "<svg/>", text: "demo text" });
s = storeResult(s, "user", { svg: "<svg2/>", text: "user text" });
assert.equal(getResult(s, "demo").text, "demo text");     // contexts isolated
assert.equal(getResult(s, "user").text, "user text");

assert.deepEqual(s.demoOptions, { conf_int: true, landmarks: [], horizon: null });
s = setDemoOptions(s, { landmarks: [12, 24] });
assert.deepEqual(s.demoOptions.landmarks, [12, 24]);
assert.equal(s.demoOptions.conf_int, true);               // patch, not replace

s = resetDemo(s);
assert.equal(getResult(s, "demo"), null);                 // demo result cleared
assert.deepEqual(s.demoOptions, { conf_int: true, landmarks: [], horizon: null });
assert.equal(getResult(s, "user").text, "user text");     // user context untouched
console.log("session-state.test.mjs OK");
```

- [ ] **Step 2: Run to verify failure**

Run: `node web/guided/session-state.test.mjs` — Expected: FAIL (module missing).

- [ ] **Step 3: Implement the store**

```js
// web/guided/session-state.js
// In-memory only — no localStorage/IndexedDB anywhere in this module (privacy
// invariant: reload starts a clean Analysis Session).
export const STAGES = ["understand", "example", "analyze"];
const DEFAULT_DEMO_OPTIONS = () => ({ conf_int: true, landmarks: [], horizon: null });

export function createKmSession() {
  return { stage: "understand", results: { demo: null, user: null },
           demoOptions: DEFAULT_DEMO_OPTIONS() };
}
export function setStage(session, stage) {
  if (!STAGES.includes(stage)) throw new Error(`Unknown stage: ${stage}`);
  return { ...session, stage };
}
export function storeResult(session, context, result) {
  return { ...session, results: { ...session.results, [context]: result } };
}
export function getResult(session, context) {
  return session.results[context] ?? null;
}
export function setDemoOptions(session, patch) {
  return { ...session, demoOptions: { ...session.demoOptions, ...patch } };
}
export function resetDemo(session) {
  return { ...session, results: { ...session.results, demo: null },
           demoOptions: DEFAULT_DEMO_OPTIONS() };
}
```

- [ ] **Step 4: Run unit test, add to test:unit glob, run all**

Append `&& node web/guided/session-state.test.mjs` to `test:unit` in `package.json`.
Run: `npm run test:unit` — Expected: all OK lines.

- [ ] **Step 5: Implement the shell**

```js
// web/guided/guided-analysis.js
import { createKmSession, setStage, storeResult, getResult, setDemoOptions, resetDemo, STAGES }
  from "./session-state.js";

const STAGE_LABELS = { understand: "Understand", example: "Try an Example", analyze: "Analyze Your Data" };
// Module-level session: survives switching to another analysis and back
// within the tab (PRD story 3/4); page reload starts clean by construction.
let session = null;

export function renderGuidedKm(container, onSubmit, runFigure) {
  session = session || createKmSession();
  // URL hash carries analysis+stage ONLY — never inputs, filenames, results.
  const fromHash = (location.hash.match(/^#km\/(\w+)$/) || [])[1];
  if (fromHash && STAGES.includes(fromHash)) session = setStage(session, fromHash);

  container.innerHTML = `
    <h2>Kaplan–Meier</h2>
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
    return runFigure(spec).then((out) => {
      if (!out.ok) {
        preview.innerHTML = "";
        stats.textContent = "Error: " + out.error;
        stats.classList.add("error");
        return out;
      }
      session = storeResult(session, context, out);
      showStored(context);
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
    history.replaceState(null, "", "#km/" + stage);
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

  renderPanels(container, { onSubmit, runAndShow,
    getSession: () => session,
    patchDemoOptions: (patch) => { session = setDemoOptions(session, patch); },
    resetDemoState: () => { session = resetDemo(session); showStored("demo"); } });
  selectStage(session.stage);
}

// Panels are filled in by Tasks 5, 6/7, and 8. Placeholders until then.
function renderPanels(container, ctx) {
  container.querySelector('[data-stage-panel="understand"]').textContent =
    "Understand — coming in Task 5.";
  container.querySelector('[data-stage-panel="example"]').textContent =
    "Try an Example — coming in Task 6.";
  container.querySelector('[data-stage-panel="analyze"]').textContent =
    "Analyze Your Data — coming in Task 8.";
}
```

In `web/app.js`: import the shell, register it for km only, and pass `runFigure` through the registry:

```js
import { renderGuidedKm } from "./guided/guided-analysis.js";
const forms = { forest: renderForestForm, consort: renderConsortForm, table1: renderTable1Form,
  km: renderGuidedKm, groupcompare: renderGroupCompareForm, correlation: renderCorrelationForm,
  roc: renderRocForm, regression: renderRegressionForm };
```

and in the click handler change the invocation to `(forms[kind] || (() => {}))(container, render, runFigure);` (existing forms ignore the third argument). Remove the now-unused `renderKmForm` import from app.js ONLY when Task 8 rehomes it (until then km no longer references it — leave the import in place so the file keeps working, and let Task 8 clean up).

In `web/styles.css` add:

```css
.stage-tabs { display: flex; gap: 0.25rem; margin: 0 0 0.75rem; }
.stage-tabs [role="tab"] { padding: 0.4rem 0.8rem; }
.stage-tabs [role="tab"][aria-selected="true"] { font-weight: 700; border-bottom: 2px solid currentColor; }
```

- [ ] **Step 6: Write the e2e for tab navigation**

```js
// tests/e2e/km-guided.spec.js
const { test, expect } = require("@playwright/test");

test("guided KM shows three stage tabs, syncs the hash, and starts on Understand", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByRole("tab", { name: "Understand" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Try an Example" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analyze Your Data" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Understand" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Try an Example" }).click();
  expect(page.url()).toContain("#km/example");
  expect(page.url()).not.toContain("csv");           // no data in URL, ever
  // keyboard reachable
  await page.getByRole("tab", { name: "Understand" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("tab", { name: "Understand" })).toHaveAttribute("aria-selected", "true");
});
```

- [ ] **Step 7: Run unit + e2e**

Run: `npm run test:unit && rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/km-guided.spec.js`
Expected: unit OK; 1 e2e passed (no webR needed — no render happens).

- [ ] **Step 8: Commit**

```bash
git add web/guided/session-state.js web/guided/session-state.test.mjs \
  web/guided/guided-analysis.js web/app.js web/styles.css package.json \
  tests/e2e/km-guided.spec.js
git commit -m "feat: guided KM stage tabs with in-memory session state and hash sync"
```

---

### Task 5: Understand stage — teaching content and Teaching Visual

**Files:**
- Create: `web/guided/km/content.js`
- Create: `web/guided/km/teaching-visual.js`
- Modify: `web/guided/guided-analysis.js` (replace the understand placeholder)
- Modify: `tests/e2e/km-guided.spec.js`

**Interfaces:**
- Consumes: the shell's `renderPanels` hook (Task 4).
- Produces: `renderUnderstand(panel)` (named export from `content.js`); `TEACHING_VISUAL_SVG` and `TEACHING_VISUAL_ALT` (named exports from `teaching-visual.js`); `EXAMPLE_INTRO_HTML` and `CALLOUTS` (object keyed by callout name) also exported from `content.js` for Task 6/7.

- [ ] **Step 1: Build `content.js` from the approved copy**

Copy the user-facing text VERBATIM from `.scratch/guided-analysis-km/content/km-learning-journey.md` — it is approved copy; do not edit, "improve", or summarize it. Structure:

```js
// web/guided/km/content.js
// Teaching copy is APPROVED text from
// .scratch/guided-analysis-km/content/km-learning-journey.md — change it there first.
import { TEACHING_VISUAL_SVG, TEACHING_VISUAL_ALT } from "./teaching-visual.js";

const SECTIONS = [
  { title: "Estimate survival over time", html: `
    <p>Kaplan–Meier analysis estimates how the probability of remaining alive—or
    remaining free of a defined event—changes over follow-up. It can include participants
    whose complete event time is unknown because they were still event-free when follow-up
    ended; these observations are censored.</p>
    <p>Each downward step marks an observed event. Censor marks show where follow-up ended
    without the event. Confidence bands show uncertainty, and the risk table shows how many
    participants still support each part of the curve.</p>` },
  { title: "Is Kaplan–Meier appropriate?", html: /* verbatim "Suitability" body,
      two <p> elements, from the source doc */ `...` },
  { title: "What data do you need?", html: /* verbatim "Required data" body: the four-item
      <ul> (Follow-up time / Event status / Study group (optional) / Participant ID (optional))
      plus the closing <p> */ `...` },
  { title: "How should you read the result?", html: /* verbatim "Interpretation" body */ `...` },
  { title: "When should you seek statistical review?", html: /* verbatim "Escalation" body */ `...` },
];

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic survival study</h3>
  <p>This teaching dataset contains 120 fictional participants randomized equally to
  <strong>Standard care</strong> or <strong>New treatment</strong>. Follow-up begins at
  randomization and continues for up to 36 months. The endpoint is all-cause death;
  participants still alive at last contact or the data cutoff are censored.</p>
  <p>The result is intentionally uncertain. Use it to practice reading estimates, confidence
  intervals, censoring, and diminishing risk sets—not to discover whether a real
  treatment works.</p>
  <blockquote><strong>Synthetic teaching data—this is not evidence about a real
  treatment.</strong></blockquote>`;

export const CALLOUTS = {
  confidenceBands: "The shaded 95% pointwise confidence bands show uncertainty around each curve. Wider bands mean less precise estimates; overlap alone does not decide whether groups differ.",
  landmarks: "Prespecified landmark estimates describe survival probability at meaningful times with confidence intervals. Do not search the completed curve for the time point that creates the most favorable comparison.",
  horizon: "The 24-month view focuses on a better-supported region of the same analysis. The underlying data and estimates are unchanged; only the displayed horizon changes.",
  medianStatus: "Median survival is the time when the estimated curve reaches 50%. “Not reached” means the curve did not fall to 50% during supported follow-up; it is not the maximum observed time.",
  logRank: "The ordinary log-rank test evaluates evidence of an overall difference between curves. Its p-value does not measure the size or clinical importance of that difference, and a value above 0.05 does not prove the groups are the same.",
  hazardRatio: "The optional unadjusted hazard ratio compares instantaneous death rates for New treatment versus Standard care among participants still alive. It is not a risk ratio or survival-time ratio and depends on the proportional-hazards assumption.",
};

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("")
    + `<figure class="teaching-visual" aria-label="${TEACHING_VISUAL_ALT}">
         ${TEACHING_VISUAL_SVG}
         <figcaption><strong>Illustration—not computed data.</strong></figcaption>
       </figure>
       <details><summary>Sources and methodology</summary>
         <p>This workflow uses R's <code>survival</code> methods inside your browser. Its
         reporting safeguards draw on established clinical-reporting guidance and
         survival-plot research. Sources support the method and presentation principles;
         they do not make this app a substitute for a study statistician or analysis plan.</p>
         <ul>
           <li><a href="https://www.bmj.com/content/389/bmj-2024-081124">CONSORT 2025 Explanation and Elaboration</a></li>
           <li><a href="https://www.equator-network.org/wp-content/uploads/2013/03/SAMPL-Guidelines-3-13-13.pdf">SAMPL Guidelines</a></li>
           <li><a href="https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survfit.formula.html">R survival documentation</a></li>
           <li><a href="https://bmjopen.bmj.com/content/9/9/e030215">KMunicate</a></li>
           <li><a href="https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf">ASA Statement on p-values</a></li>
         </ul>
       </details>`;
}
```

The `/* verbatim ... */ \`...\`` slots above are copy-transcription work, not design decisions: open the source doc, copy each named section's body, wrap paragraphs in `<p>`. Every section listed must be present; no section may be dropped or reworded.

- [ ] **Step 2: Author the Teaching Visual**

A deliberately schematic annotated illustration — hand-authored SVG, obviously not a data plot:

```js
// web/guided/km/teaching-visual.js
export const TEACHING_VISUAL_ALT =
  "Annotated illustration of a Kaplan-Meier plot: downward steps are observed events; " +
  "small crosses are censored follow-up; the shaded band is the 95% pointwise confidence " +
  "interval; the dashed line at 50% shows where median survival is read; a number-at-risk " +
  "row underneath shows how many participants still support the curve.";

export const TEACHING_VISUAL_SVG = `
<svg viewBox="0 0 560 330" role="img" xmlns="http://www.w3.org/2000/svg"
     style="max-width:100%;height:auto;font-family:system-ui,sans-serif">
  <text x="16" y="20" font-size="13" font-weight="bold" fill="#88400a">Illustration — not computed data</text>
  <g stroke="#333" stroke-width="1">
    <line x1="50" y1="40" x2="50" y2="240"/><line x1="50" y1="240" x2="520" y2="240"/>
  </g>
  <text x="20" y="145" font-size="11" transform="rotate(-90 20 145)">Survival probability</text>
  <text x="260" y="262" font-size="11">Time since time zero</text>
  <path d="M50 60 L150 60 L150 95 L240 95 L240 140 L360 140 L360 185 L470 185"
        fill="none" stroke="#4477AA" stroke-width="2.5"/>
  <path d="M50 55 L150 55 L150 80 L240 80 L240 120 L360 120 L360 155 L470 155
           L470 215 L360 215 L360 165 L240 165 L240 112 L150 112 L150 68 L50 68 Z"
        fill="#4477AA" fill-opacity="0.14" stroke="none"/>
  <g stroke="#4477AA" stroke-width="2">
    <line x1="195" y1="90" x2="195" y2="100"/><line x1="200" y1="90" x2="200" y2="100"/>
    <line x1="300" y1="135" x2="300" y2="145"/>
  </g>
  <line x1="50" y1="150" x2="520" y2="150" stroke="#999" stroke-dasharray="5 4"/>
  <text x="474" y="147" font-size="10" fill="#666">50% → median</text>
  <g font-size="10.5" fill="#88400a">
    <text x="155" y="52">↓ step = observed event</text>
    <text x="255" y="112">+ = censored (follow-up ended, no event)</text>
    <text x="368" y="132">shaded band = 95% CI</text>
  </g>
  <g font-size="11">
    <text x="16" y="292" font-weight="bold">Number at risk</text>
    <text x="50" y="310">120</text><text x="150" y="310">96</text><text x="240" y="310">71</text>
    <text x="360" y="310">38</text><text x="470" y="310">9</text>
    <text x="490" y="310" font-size="10" fill="#88400a">← sparse tail: read cautiously</text>
  </g>
</svg>`;
```

- [ ] **Step 3: Wire into the shell**

In `guided-analysis.js`, replace the understand placeholder inside `renderPanels`:

```js
import { renderUnderstand } from "./km/content.js";
// in renderPanels:
renderUnderstand(container.querySelector('[data-stage-panel="understand"]'));
```

- [ ] **Step 4: Extend the e2e**

Append to `tests/e2e/km-guided.spec.js`:

```js
test("Understand teaches the method with a labeled non-data visual", async ({ page }) => {
  await page.goto("/#km/understand");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByRole("heading", { name: "Estimate survival over time" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /appropriate/i })).toBeVisible();
  await expect(page.getByText("Illustration—not computed data")).toBeVisible();
  await expect(page.getByText("Sources and methodology")).toBeVisible();
});
```

- [ ] **Step 5: Run e2e and commit**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/km-guided.spec.js`
Expected: 2 passed.

```bash
git add web/guided/km/content.js web/guided/km/teaching-visual.js \
  web/guided/guided-analysis.js tests/e2e/km-guided.spec.js
git commit -m "feat: KM Understand stage with approved teaching copy and labeled teaching visual"
```

---

### Task 6: Try an Example — real demo run with mandatory synthetic labeling

**Files:**
- Create: `web/guided/km/demo.js`
- Create: `web/guided/km/demo.test.mjs`
- Modify: `web/guided/guided-analysis.js` (replace the example placeholder)
- Modify: `web/styles.css` (banner style)
- Modify: `tests/e2e/km-guided.spec.js`
- Modify: `package.json` (test glob)

**Interfaces:**
- Consumes: `KM_DEMO` (Task 1), `EXAMPLE_INTRO_HTML` (Task 5), shell context `{ runAndShow, getSession, patchDemoOptions, resetDemoState }` (Task 4), KM options contract (Task 3).
- Produces: `buildDemoSpec(options)` → worker spec; `renderExample(panel, ctx)`.

- [ ] **Step 1: Write the failing spec-builder test**

```js
// web/guided/km/demo.test.mjs
import assert from "node:assert/strict";
import { buildDemoSpec } from "./demo.js";
import { KM_DEMO } from "./demo-data.js";

const spec = buildDemoSpec({ conf_int: true, landmarks: [], horizon: null });
assert.equal(spec.figure, "km");
assert.equal(spec.data.length, 120);
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["group", "status", "time"]);
const d0 = KM_DEMO.rows[0];
assert.equal(spec.data[0].time, d0.followup_months);
assert.equal(spec.data[0].status, d0.status === "Death" ? 1 : 0);
assert.equal(spec.options.reference, "Standard care");        // HR direction: New vs Standard
assert.equal(spec.options.caption, KM_DEMO.label);            // synthetic label INSIDE the SVG
assert.equal(spec.options.time_label, "Months since randomization");
assert.equal(spec.options.conf_int, true);

const spec2 = buildDemoSpec({ conf_int: false, landmarks: [12, 24], horizon: 24 });
assert.equal(spec2.options.conf_int, false);
assert.deepEqual(spec2.options.landmarks, [12, 24]);
assert.equal(spec2.options.horizon, 24);
console.log("demo.test.mjs OK");
```

- [ ] **Step 2: Run to verify failure, then implement**

Run: `node web/guided/km/demo.test.mjs` — Expected: FAIL (module missing). Then:

```js
// web/guided/km/demo.js
import { KM_DEMO } from "./demo-data.js";

// The demo goes through the SAME request builder + worker + R path as user
// data (PRD: the tutorial demonstrates the real workflow, not a canned output).
export function buildDemoSpec(demoOptions) {
  return {
    figure: "km",
    data: KM_DEMO.rows.map((r) => ({
      time: r.followup_months,
      status: r.status === "Death" ? 1 : 0,
      group: r.group,
    })),
    options: {
      time_label: "Months since randomization",
      theme: "generic",
      caption: KM_DEMO.label,
      reference: "Standard care",
      conf_int: demoOptions.conf_int,
      landmarks: demoOptions.landmarks,
      ...(demoOptions.horizon ? { horizon: demoOptions.horizon } : {}),
    },
  };
}
```

Run the test again — Expected: PASS. Add `&& node web/guided/km/demo.test.mjs` to `test:unit`; run `npm run test:unit`.

- [ ] **Step 3: Render the Example stage**

In `guided-analysis.js`'s `renderPanels`, replace the example placeholder:

```js
import { buildDemoSpec } from "./km/demo.js";
import { KM_DEMO } from "./km/demo-data.js";
import { EXAMPLE_INTRO_HTML } from "./km/content.js";

function renderExample(panel, ctx) {
  panel.innerHTML = `
    ${EXAMPLE_INTRO_HTML}
    <div class="demo-banner" role="note">${KM_DEMO.label}</div>
    <div class="demo-actions">
      <button type="button" id="run-demo">Run Example Analysis</button>
      <button type="button" id="reset-demo">Reset Example</button>
    </div>
    <div id="demo-experiments"></div>`;
  const runBtn = panel.querySelector("#run-demo");
  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;                       // no duplicate runs
    try { await ctx.runAndShow(buildDemoSpec(ctx.getSession().demoOptions), "demo"); }
    finally { runBtn.disabled = false; }
  });
  panel.querySelector("#reset-demo").addEventListener("click", () => {
    ctx.resetDemoState();
    renderExample(panel, ctx);                    // restores default controls (Task 7)
  });
}
```

and call `renderExample(container.querySelector('[data-stage-panel="example"]'), ctx);`.
webR is not initialized until Run Example Analysis is clicked — the worker already boots lazily on first message, and nothing in this panel posts a message before the click (PRD requirement; do not add any warm-up call).

`web/styles.css`:

```css
.demo-banner { background: #fff3e0; border: 1px solid #e0a960; padding: 0.5rem 0.75rem;
  margin: 0.5rem 0; font-weight: 600; }
.demo-actions { display: flex; gap: 0.5rem; margin: 0.5rem 0 1rem; }
```

- [ ] **Step 4: e2e — the full real demo run with pinned statistics**

Append to `tests/e2e/km-guided.spec.js`:

```js
test("Run Example Analysis computes the real pinned demo result", async ({ page }) => {
  test.setTimeout(360000); // first run installs survival+cowplot in webR
  await page.goto("/#km/example");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByText("Synthetic demonstration data — not for clinical use.")).toBeVisible();
  await expect(page.locator("#preview svg")).toHaveCount(0);   // nothing before the click
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
  const stats = page.locator("#stats");
  await expect(stats).toContainText("p = 0.108");              // pinned log-rank
  await expect(stats).toContainText("HR 0.64 (New treatment vs Standard care");
  await expect(stats).toContainText("not reached");            // New treatment median
  await expect(page.locator("#preview")).toContainText("Number at risk");
  await expect(page.locator("#preview")).toContainText("Synthetic demonstration data");
});
```

- [ ] **Step 5: Run e2e and commit**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/km-guided.spec.js`
Expected: 3 passed.

```bash
git add web/guided/km/demo.js web/guided/km/demo.test.mjs \
  web/guided/guided-analysis.js web/styles.css package.json tests/e2e/km-guided.spec.js
git commit -m "feat: run guided KM demonstration end to end with pinned results"
```

---

### Task 7: Guided Experiments — three reversible learning controls

**Files:**
- Modify: `web/guided/guided-analysis.js` (fill `#demo-experiments`)
- Modify: `tests/e2e/km-guided.spec.js`

**Interfaces:**
- Consumes: `patchDemoOptions` / `resetDemoState` (Task 4), `CALLOUTS` (Task 5), options contract (Task 3).

- [ ] **Step 1: Implement the experiment controls**

Inside `renderExample` (Task 6), fill `#demo-experiments`:

```js
import { CALLOUTS } from "./km/content.js";

function renderExperiments(panel, ctx, rerun) {
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
```

`rerun` is the same function the Run button uses (`runAndShow(buildDemoSpec(...), "demo")`); an experiment change reruns only if a demo result already exists (`if (ctx.getSession().results.demo) rerun()` — before the first run, changes just set options). Add `.callout { color:#555; font-size:0.85rem; margin:0.15rem 0 0.6rem; }` to `web/styles.css`.

- [ ] **Step 2: e2e for one experiment round-trip**

```js
test("landmark experiment adds 12/24-month estimates and Reset restores defaults", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#km/example");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 330000 });
  await page.locator("#exp-landmarks").check();
  await expect(page.locator("#stats")).toContainText("At 12.0 Months since randomization, survival was 73.5%",
    { timeout: 120000 });   // packages cached now; rerun is fast
  await page.getByRole("button", { name: "Reset Example" }).click();
  await expect(page.locator("#exp-landmarks")).not.toBeChecked();
  await expect(page.locator("#preview svg")).toHaveCount(0);   // demo result cleared
});
```

- [ ] **Step 3: Run e2e and commit**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/km-guided.spec.js`
Expected: 4 passed.

```bash
git add web/guided/guided-analysis.js web/styles.css tests/e2e/km-guided.spec.js
git commit -m "feat: reversible KM guided experiments (CI bands, landmarks, horizon)"
```

---

### Task 8: Analyze Your Data stage, regression sweep, and release gate

**Files:**
- Modify: `web/guided/guided-analysis.js` (replace the analyze placeholder)
- Modify: `web/app.js` (drop the now-unused direct `renderKmForm` import)
- Modify: `tests/e2e/km.spec.js` (route through the new tab)
- Modify: `CLAUDE.md` (architecture note)

**Interfaces:**
- Consumes: `renderKmForm(container, onSubmit)` unchanged from `web/forms/km.js`; the shell's `runAndShow(spec, "user")`.

- [ ] **Step 1: Embed the existing form**

In `renderPanels`:

```js
import { renderKmForm } from "../forms/km.js";
// analyze panel: the existing (Stage 0-hardened) CSV form, submitting through
// the shell so the user result is cached per-context like the demo's.
const analyzePanel = container.querySelector('[data-stage-panel="analyze"]');
analyzePanel.innerHTML = "";
renderKmForm(analyzePanel, (spec) => ctx.runAndShow(spec, "user"));
```

Remove the `renderKmForm` import and `km:` registry use of it from `web/app.js` if any remains (the registry entry became `renderGuidedKm` in Task 4).

- [ ] **Step 2: Update the legacy KM e2e to go through the tab**

In `tests/e2e/km.spec.js`, after clicking the Kaplan-Meier button add:

```js
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
```

(the rest of the test — `#csv` upload, Render, SVG visible — is unchanged).

- [ ] **Step 3: Add the context-isolation e2e**

Append to `tests/e2e/km-guided.spec.js`:

```js
const path = require("path");
test("demo and user results are separate contexts", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#km/example");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#stats")).toContainText("p = 0.108", { timeout: 330000 });
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await expect(page.locator("#preview svg")).toHaveCount(0);   // user context empty
  await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 120000 });
  await page.getByRole("tab", { name: "Try an Example" }).click();
  await expect(page.locator("#stats")).toContainText("p = 0.108");  // demo restored
});
```

- [ ] **Step 4: Full verification sweep**

```bash
npm run test:unit
Rscript -e 'devtools::test()'
rm -rf web/R && cp -R R web/R && npx playwright test
git diff --check
```

Expected: unit all OK; R `[ FAIL 0 | WARN 0 | ... ]`; ALL Playwright tests pass (including the untouched forest/consort/table1/groupcompare/correlation/roc/regression specs — this is the no-regression gate for the other seven analyses); clean diff check.

- [ ] **Step 5: Update CLAUDE.md**

In the Architecture section, adjust two facts: KM's `EXTRA_PACKAGES` entry is now `km → survival/cowplot` (not survminer), and add one sentence: "Kaplan–Meier routes through a guided three-stage shell (`web/guided/`) — Understand / Try an Example / Analyze Your Data — with a frozen synthetic demo (`data-raw/km-demo-generator.R`); the other analyses keep the plain form registry." Also update the "why the KM risk-table is a deferred follow-up" parenthetical in Design docs — the risk table now ships.

- [ ] **Step 6: Manual QA (record results in the commit message body)**

Serve (`rm -rf web/R && cp -R R web/R && npm run serve`) and check by hand: cold demo run on a throttled connection (devtools "Fast 4G") shows the progress message and completes; tab keyboard navigation; 320px viewport tabs usable; demo banner and SVG caption both show the synthetic sentence; Reset Example restores all three controls.

- [ ] **Step 7: Commit**

```bash
git add web/guided/guided-analysis.js web/app.js tests/e2e/km.spec.js \
  tests/e2e/km-guided.spec.js CLAUDE.md
git commit -m "feat: complete guided KM Stage A (analyze tab, context isolation, release gate)"
```

---

## Deferred to Stage B (explicitly out of scope here — PRD sections remain canonical)

Decide after Stage A has external viewers. Each item maps to the PRD/original plan (`docs/superpowers/plans/2026-07-14-guided-analysis-km.md`):

- **Role-mapped CSV + Analysis Preflight** (PRD "Data and validation"; WP3) — arbitrary columns, event-value mapping, Blocker/Confirmation/Notice findings, 5 MB/50k cap, transactional replacement, Clear My Data. The analyze tab keeps the fixed `time,status,group` contract until then.
- **Structured Analysis Result schema + result document** (PRD "Computation contract", "Result and handoff"; WP1/WP5) — versioned result object, provenance header, findings-beside-statistics, out-of-date status, Interpretation Guidance templates.
- **Analysis Handoff** (WP5) — Download SVG, Copy Methods/Results/Complete Handoff, figure-use note, filename policy.
- **Full quality bar** (WP6) — WCAG 2.2 AA audit, screen-reader pass, privacy sentinel e2e, slow/failing-worker chaos hooks. (Stage A still uses semantic tabs/roles and keyboard-reachable controls — the audit and chaos testing are what's deferred.)
- **Generic method-module contract** (WP1's shell abstraction) — deliberately NOT built with N=1; extract it when a second guided method (likely ROC) is instantiated.
- Withheld-comparison presentation beyond Stage 0's text form, omnibus multi-group labeling, KMunicate extended risk table, RMST.

## Execution notes

- Tasks 1→8 are strictly ordered except Task 5 (Understand content), which can run any time after Task 4.
- Task 6's e2e is the expensive one (~2–4 min real webR). Run the focused file, not the whole suite, until Task 8.
- If a pinned demo number ever disagrees with a fresh run, the dataset or generator changed — investigate; never re-pin to green.

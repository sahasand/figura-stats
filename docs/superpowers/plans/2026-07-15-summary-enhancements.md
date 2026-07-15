# Summary Statistics Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the user-facing "Table 1" surfaces to "Summary statistics", enrich the shared distribution figure with box+jitter and optional Q–Q panels (plus a density curve on the histograms), and add upload guidance with a downloadable example CSV.

**Architecture:** The summary figure's `svg` field already carries free-form HTML, so the multi-panel figure is a stack of **sibling `<svg>` elements** (each its own ggplot rendered via the existing `.svg_string`) inside one `<figure class="dist-plot">` — no cowplot/patchwork, no new webR packages. A new boolean spec option `options.show_qq` gates the Q–Q row; the existing `options.show_plots` gates the histogram+density and box+jitter rows as a pair. The demo and upload paths share this one R function, so both get the new panels.

**Tech Stack:** R (base stats + ggplot2 4.x, tested with testthat via devtools), vanilla ES modules with plain-Node unit tests, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-07-15-summary-enhancements-design.md`

## Global Constraints

- **WARN 0 is a hard gate**: run `Rscript -e 'devtools::test()'` (never `testthat::test_file()`); result line must read `[ FAIL 0 | WARN 0 | ... ]`. Fix leaked warnings at the source.
- ggplot2 4.x: use `linewidth`, never `size`, for line widths (point `size` in `geom_jitter`/`stat_qq` is fine — it is a point aesthetic, not a line width).
- **No new R packages**: `fig_summary` stays on the boot set (base `stats` + ggplot2). No `DESCRIPTION` change, no `EXTRA_PACKAGES` entry, no `worker.js` change (no new R file is created).
- **No data egress**: the example-CSV download must be a client-side Blob object URL — no network request, no font/CDN links.
- `web/R/` is a gitignored build copy: before `npm run serve` or `npm run test:e2e`, run `rm -rf web/R && cp -R R web/R`.
- Teaching copy keeps the term "Table 1" (it is the clinical jargon being explained); only nav button, shell title, and Render button are renamed.
- JS unit tests are plain Node scripts run by `npm run test:unit`; they use `node:assert` and `console.log("ok - ...")` on success.
- Commit after every task; commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

## File Structure

| File | Role in this plan |
|---|---|
| `web/index.html` | Nav button rename (modify one line) |
| `web/guided/summary/guided-summary.js` | Shell title rename; new `#exp-qq` experiment checkbox; `showQq` default |
| `web/guided/summary/content.js` | Section-title tweak; updated `CALLOUTS.showPlots`; new `CALLOUTS.showQq` |
| `web/guided/summary/demo.js` | Pass `show_qq` into the demo spec |
| `web/guided/summary/demo.test.mjs` | Assert `show_qq` passthrough |
| `web/guided/summary/analyze-form.js` | Render-button rename; Q–Q checkbox; upload-guidance block + example-CSV download; `buildSummarySpec` gains `showQq` |
| `web/guided/summary/analyze-form.test.mjs` | Assert `show_qq` in built spec |
| `web/guided/summary/demo-data.test.mjs` | Example-CSV round-trip test |
| `web/lib/csv.js` | New pure `toCsv(rows, columns)` |
| `web/lib/csv.test.mjs` | `toCsv` unit tests |
| `R/summarize.R` | Sibling-SVG plot builder: `.summary_plot_df`, `.summary_hist_svg`, `.summary_box_svg`, `.summary_qq_svg`; `fig_summary` figure block rewrite |
| `tests/testthat/test-summarize.R` | New plot/`show_qq` tests |
| `tests/e2e/summary-guided.spec.js` | Renamed selectors; guidance-block and Q–Q toggle tests |

No files are created or deleted; `worker.js`, `DESCRIPTION`, `R/dispatch.R`, and the shared `web/guided/shell.js` are untouched.

---

### Task 1: Rename user-facing "Table 1" surfaces to "Summary statistics"

**Files:**
- Modify: `web/index.html:32`
- Modify: `web/guided/summary/guided-summary.js:33`
- Modify: `web/guided/summary/analyze-form.js:120`
- Modify: `web/guided/summary/content.js:5`
- Modify: `tests/e2e/summary-guided.spec.js` (all nav-button selectors)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the nav button's accessible name becomes `Summary statistics` — Task 9's new e2e tests use `page.getByRole("button", { name: /summary statistics/i })`.

- [ ] **Step 1: Rename the nav button**

In `web/index.html`, change:

```html
        <button data-figure="summary">Table 1</button>
```

to:

```html
        <button data-figure="summary">Summary statistics</button>
```

- [ ] **Step 2: Rename the guided-shell title**

In `web/guided/summary/guided-summary.js`, change:

```js
  title: "Table 1 — Summary statistics",
```

to:

```js
  title: "Summary statistics",
```

- [ ] **Step 3: Rename the Render button**

In `web/guided/summary/analyze-form.js`, change:

```js
    btn.type = "button"; btn.id = "render"; btn.textContent = "Render Table 1";
```

to:

```js
    btn.type = "button"; btn.id = "render"; btn.textContent = "Render summary table";
```

- [ ] **Step 4: Lead the teaching copy with the plain name**

In `web/guided/summary/content.js`, change the first section title:

```js
  { title: "What a Table 1 is for", html: `
```

to:

```js
  { title: "What this table (a clinical “Table 1”) is for", html: `
```

The rest of the teaching copy keeps "Table 1" — it is the jargon being explained.

- [ ] **Step 5: Update the e2e nav selectors**

In `tests/e2e/summary-guided.spec.js`, replace **all 7** occurrences of:

```js
  await page.getByRole("button", { name: /table 1/i }).click();
```

with:

```js
  await page.getByRole("button", { name: /summary statistics/i }).click();
```

(The test titled `"Run Example computes the real Table 1 …"` keeps its name — test titles are not UI.)

- [ ] **Step 6: Verify no stale UI reference remains**

Run: `grep -rn "Table 1" web/index.html web/guided/summary/guided-summary.js web/guided/summary/analyze-form.js`
Expected: no output.

Run: `grep -c "summary statistics/i" tests/e2e/summary-guided.spec.js`
Expected: `7`

- [ ] **Step 7: Run JS unit tests (guard against typos breaking imports)**

Run: `npm run test:unit`
Expected: every file prints its `ok`/`OK` line, exit code 0.

- [ ] **Step 8: Commit**

```bash
git add web/index.html web/guided/summary/guided-summary.js web/guided/summary/analyze-form.js web/guided/summary/content.js tests/e2e/summary-guided.spec.js
git commit -m "feat(summary): rename user-facing Table 1 surfaces to Summary statistics

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `toCsv` serializer in `web/lib/csv.js`

**Files:**
- Modify: `web/lib/csv.js`
- Test: `web/lib/csv.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: `export function toCsv(rows, columns) -> string`. `rows` is an array of plain objects (values may be string/number/null/undefined), `columns` an array of column-name strings. Returns header line + one line per row, `\n`-separated with a trailing `\n`; `null`/`undefined` become empty cells. **Throws** `Error` if any column name or value contains a comma, double quote, CR, or LF — `parseCsv` has no quoting rules, so such values are unrepresentable. Task 8 calls `toCsv(SUMMARY_DEMO.rows, SUMMARY_DEMO.columns)`.

- [ ] **Step 1: Write the failing tests**

Append to `web/lib/csv.test.mjs` (and change its import line from `import { parseCsv } from "./csv.js";` to `import { parseCsv, toCsv } from "./csv.js";`):

```js
// toCsv: header + rows, null/undefined -> empty cell, round-trips through parseCsv.
const tRows = [{ age: 61, arm: "A", note: null }, { age: 72, arm: "B", note: "ok" }];
const tText = toCsv(tRows, ["age", "arm", "note"]);
assert.equal(tText, "age,arm,note\n61,A,\n72,B,ok\n");
const tBack = parseCsv(tText);
assert.deepEqual(tBack.columns, ["age", "arm", "note"]);
assert.equal(tBack.rows.length, 2);
assert.equal(tBack.rows[0].age, "61");
assert.equal(tBack.rows[0].note, "", "null serializes as an empty (missing) cell");
assert.equal(tBack.types.age, "numeric");

// parseCsv has no quoting rules -> unrepresentable values must throw, not corrupt.
assert.throws(() => toCsv([{ a: "x,y" }], ["a"]), /comma/i);
assert.throws(() => toCsv([{ a: 'say "hi"' }], ["a"]), /quote/i);
assert.throws(() => toCsv([{ a: "line\nbreak" }], ["a"]), /line break/i);
assert.throws(() => toCsv([{ "b,ad": 1 }], ["b,ad"]), /comma/i);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node web/lib/csv.test.mjs`
Expected: FAIL — `SyntaxError: The requested module './csv.js' does not provide an export named 'toCsv'`

- [ ] **Step 3: Implement `toCsv`**

Append to `web/lib/csv.js`:

```js
// Serialize row objects back to a CSV string for the given columns — the
// inverse of parseCsv for the values it supports. parseCsv has no quoting
// rules, so any column name or value containing a comma, double quote, or
// line break is unrepresentable and throws rather than silently emitting a
// file the app's own parser cannot read. null/undefined become empty cells.
export function toCsv(rows, columns) {
  const cell = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    if (/[",\r\n]/.test(s))
      throw new Error(`Cannot write a CSV value containing a comma, quote, or line break: ${JSON.stringify(s)}.`);
    return s;
  };
  const lines = [columns.map(cell).join(",")];
  for (const r of rows) lines.push(columns.map((c) => cell(r[c])).join(","));
  return lines.join("\n") + "\n";
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node web/lib/csv.test.mjs`
Expected: `csv.test.mjs OK`, exit 0. Then run the full set: `npm run test:unit` — all files pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/csv.js web/lib/csv.test.mjs
git commit -m "feat(csv): toCsv serializer, the guarded inverse of parseCsv

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: R — sibling-SVG plot architecture + density curve on the histogram row

**Files:**
- Modify: `R/summarize.R` (replace `.summary_plot_svg`, lines 117–144, and the figure block in `fig_summary`, lines 243–261)
- Test: `tests/testthat/test-summarize.R`

**Interfaces:**
- Consumes: existing `.numeric_col`, `.svg_string(plot, width, height)` (from `R/dispatch.R`), `%||%` (from `R/forest.R`).
- Produces: `.summary_plot_df(rows, continuous, labels, grp, levels_g)` → long `data.frame(variable=<factor>, value=<numeric>, group=<factor>)` or `NULL` when nothing is plottable; `.summary_hist_svg(df)` → svg string. Tasks 4–5 add `.summary_box_svg(df)` and `.summary_qq_svg(df, grouped)` and extend the `svgs`/`legend_bits` vectors that this task introduces in `fig_summary`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/testthat/test-summarize.R`:

```r
# Count sibling <svg> elements inside the bundled HTML output.
n_svgs <- function(html) sum(gregexpr("<svg", html, fixed = TRUE)[[1]] > 0)

test_that("histogram row is density-scaled with a density curve, warning-free", {
  spec <- mk_summary_spec(); spec$options$show_plots <- TRUE
  out <- expect_no_warning(fig_summary(spec))
  expect_gte(n_svgs(out$svg), 1)   # Task 4 raises the exact count to 2
  expect_match(out$svg, "curve = density", fixed = TRUE)
  expect_match(out$svg, "dashed = mean", fixed = TRUE)
  expect_match(out$svg, "lines separate", fixed = TRUE)
})
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: 1 failure — `curve = density` not matched. All pre-existing tests still pass.

- [ ] **Step 3: Replace `.summary_plot_svg` with the sibling-SVG builders**

In `R/summarize.R`, replace the whole `.summary_plot_svg` function **and its comment block** (lines 117–144) with:

```r
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
```

- [ ] **Step 4: Rewrite the figure block in `fig_summary`**

Replace the current block (from `figure_html <- ""` through the `}` that closes `if (isTRUE(opt$show_plots) …`, lines 243–261) with:

```r
  # Optional distribution figure: stacked sibling SVGs inside one <figure>.
  # show_plots gates the histogram+density row (Tasks 4-5 add box+jitter and
  # the show_qq-gated Q-Q row). The teaching legend and synthetic caption are
  # HTML (styleable), not ggplot in-SVG text. No <figure> at all when nothing
  # is plottable.
  figure_html <- ""
  want_plots <- isTRUE(opt$show_plots)
  if (want_plots && length(continuous) > 0) {
    df <- .summary_plot_df(rows, continuous, labels, grp, levels_g)
    if (!is.null(df)) {
      svgs <- c(.summary_hist_svg(df))
      legend_bits <- c(paste0(
        "<span class=\"mean-key\">dashed = mean</span> · ",
        "<span class=\"median-key\">solid = median</span> · curve = density",
        " — when the lines separate, the variable is skewed"))
      legend_html <- paste0("<div class=\"plot-legend\">",
                            paste(legend_bits, collapse = "<br>"), "</div>")
      cap <- opt$caption %||% ""
      cap_html <- if (nzchar(cap))
        sprintf("<figcaption class=\"synthetic\">%s</figcaption>", .esc(cap)) else ""
      figure_html <- sprintf("<figure class=\"dist-plot\">%s%s%s</figure>",
                             paste(svgs, collapse = ""), legend_html, cap_html)
    }
  }
```

- [ ] **Step 5: Run the full R suite**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS <n> ]`. In particular `"show_plots bundles a table AND an inline svg…"`, `"all-missing continuous values render the table with no figure"`, and `"caption is rendered when provided"` must still pass.

- [ ] **Step 6: Commit**

```bash
git add R/summarize.R tests/testthat/test-summarize.R
git commit -m "refactor(summary): sibling-SVG distribution figure; density curve on histograms

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: R — box + jitter row

**Files:**
- Modify: `R/summarize.R`
- Test: `tests/testthat/test-summarize.R`

**Interfaces:**
- Consumes: `.summary_plot_df` output (Task 3); `.km_palette(n)` from `R/km.R` (accessible qualitative Tol palette — same package namespace, and the worker fetches every `R/*.R` at boot, so it is available in webR too).
- Produces: `.summary_box_svg(df)` → svg string; the figure block now emits two sibling SVGs when `show_plots`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/testthat/test-summarize.R`:

```r
test_that("show_plots yields histogram and box rows as sibling SVGs", {
  spec <- mk_summary_spec(); spec$options$show_plots <- TRUE
  out <- expect_no_warning(fig_summary(spec))
  expect_equal(n_svgs(out$svg), 2)
  expect_match(out$svg, "individual observations", fixed = TRUE)
})

test_that("ungrouped box row renders warning-free with a single Overall category", {
  spec <- mk_summary_spec(group = NULL); spec$options$show_plots <- TRUE
  out <- expect_no_warning(fig_summary(spec))
  expect_equal(n_svgs(out$svg), 2)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: both new tests fail on `n_svgs(out$svg) == 2` (actual 1).

- [ ] **Step 3: Add `.summary_box_svg`**

In `R/summarize.R`, insert after `.summary_hist_svg`:

```r
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
```

- [ ] **Step 4: Wire the row into the figure block**

In `fig_summary`, change:

```r
      svgs <- c(.summary_hist_svg(df))
      legend_bits <- c(paste0(
        "<span class=\"mean-key\">dashed = mean</span> · ",
        "<span class=\"median-key\">solid = median</span> · curve = density",
        " — when the lines separate, the variable is skewed"))
```

to:

```r
      svgs <- c(.summary_hist_svg(df), .summary_box_svg(df))
      legend_bits <- c(paste0(
        "<span class=\"mean-key\">dashed = mean</span> · ",
        "<span class=\"median-key\">solid = median</span> · curve = density",
        " — when the lines separate, the variable is skewed"),
        "box = median and IQR, whiskers to 1.5 × IQR, dots = individual observations")
```

Also update the block's lead comment line `# show_plots gates the histogram+density row (Tasks 4-5 add box+jitter and` to `# show_plots gates the histogram+density and box+jitter rows as a pair`.

- [ ] **Step 5: Run the full R suite**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | … ]`.

- [ ] **Step 6: Commit**

```bash
git add R/summarize.R tests/testthat/test-summarize.R
git commit -m "feat(summary): grouped box plots with jittered observations as a second panel row

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: R — opt-in Q–Q row (`options.show_qq`)

**Files:**
- Modify: `R/summarize.R`
- Test: `tests/testthat/test-summarize.R`

**Interfaces:**
- Consumes: `.summary_plot_df` (Task 3).
- Produces: `.summary_qq_svg(df, grouped)` → svg string; spec option `options.show_qq` (boolean; absent/false = no Q–Q row; independent of `show_plots`). Tasks 6–7 set this option from the UI.

- [ ] **Step 1: Write the failing tests**

Append to `tests/testthat/test-summarize.R`:

```r
test_that("show_qq is off by default and adds a Q-Q row when on", {
  spec <- mk_summary_spec(); spec$options$show_plots <- TRUE
  expect_false(grepl("Q–Q", fig_summary(spec)$svg, fixed = TRUE))
  spec$options$show_qq <- TRUE
  out <- expect_no_warning(fig_summary(spec))
  expect_equal(n_svgs(out$svg), 3)
  expect_match(out$svg, "Q–Q", fixed = TRUE)
})

test_that("show_qq alone renders one svg with the Q-Q legend only", {
  spec <- mk_summary_spec()
  spec$options$show_plots <- FALSE; spec$options$show_qq <- TRUE
  out <- expect_no_warning(fig_summary(spec))
  expect_equal(n_svgs(out$svg), 1)
  expect_match(out$svg, "curved tail", fixed = TRUE)
  expect_false(grepl("dashed = mean", out$svg, fixed = TRUE))
})

test_that("ungrouped show_qq facets by variable only, warning-free", {
  spec <- mk_summary_spec(group = NULL)
  spec$options$show_plots <- FALSE; spec$options$show_qq <- TRUE
  out <- expect_no_warning(fig_summary(spec))
  expect_equal(n_svgs(out$svg), 1)
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "summarize")'`
Expected: the three new tests fail (no Q–Q output; `show_plots FALSE` currently yields no figure at all).

- [ ] **Step 3: Add `.summary_qq_svg`**

In `R/summarize.R`, insert after `.summary_box_svg`:

```r
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
```

- [ ] **Step 4: Gate the figure block on either flag**

In `fig_summary`, replace the figure block introduced in Tasks 3–4 with:

```r
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
          " — when the lines separate, the variable is skewed"),
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
```

- [ ] **Step 5: Run the full R suite**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | … ]`.

- [ ] **Step 6: Commit**

```bash
git add R/summarize.R tests/testthat/test-summarize.R
git commit -m "feat(summary): opt-in Q-Q normality panels via options.show_qq

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Demo — Q–Q experiment checkbox and callouts

**Files:**
- Modify: `web/guided/summary/demo.js`
- Modify: `web/guided/summary/guided-summary.js`
- Modify: `web/guided/summary/content.js`
- Test: `web/guided/summary/demo.test.mjs`

**Interfaces:**
- Consumes: `options.show_qq` (Task 5); shell config contract of `createGuidedShell` (`defaultDemoOptions`, `experimentControlsSelector`, `renderExperiments(panel, ctx, rerun)`).
- Produces: demo option key `showQq` (boolean) in `demoOptions`; checkbox id `#exp-qq` (Task 9's e2e checks it); `CALLOUTS.showQq` string.

- [ ] **Step 1: Write the failing test**

In `web/guided/summary/demo.test.mjs`, extend both blocks:

In the first block (after the `show_plots` assertion) change the build call to include `showQq: true` and assert it:

```js
  const spec = buildSummaryDemoSpec({ groupBy: "arm", showPlots: true, forceMean: false, showQq: true });
```

and add after `assert.equal(spec.options.show_plots, true);`:

```js
  assert.equal(spec.options.show_qq, true);
```

In the second block (options object without `showQq`) add after `assert.equal(spec.options.show_plots, false);`:

```js
  assert.equal(spec.options.show_qq, false, "absent showQq must serialize as false, not undefined");
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node web/guided/summary/demo.test.mjs`
Expected: FAIL — `spec.options.show_qq` is `undefined`.

- [ ] **Step 3: Pass `show_qq` through the demo spec**

In `web/guided/summary/demo.js`, add one line to the `options` object after `show_plots: demoOptions.showPlots,`:

```js
      show_qq: !!demoOptions.showQq,
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node web/guided/summary/demo.test.mjs`
Expected: `ok - buildSummaryDemoSpec`

- [ ] **Step 5: Add the experiment checkbox and default**

In `web/guided/summary/guided-summary.js`:

In `renderSummaryExperiments`, insert between the `exp-plots` label/callout pair and the `exp-forcemean` label:

```js
    <label><input type="checkbox" id="exp-qq" ${o.showQq ? "checked" : ""}>
      Show Q–Q normality panels</label>
    <p class="callout">${CALLOUTS.showQq}</p>
```

After the `#exp-plots` change listener, add:

```js
  panel.querySelector("#exp-qq").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ showQq: e.target.checked }); rerun();
  });
```

Change the config defaults and freeze-list selector:

```js
  defaultDemoOptions: () => ({ groupBy: "arm", showPlots: true, forceMean: false, showQq: false }),
  experimentControlsSelector: "#exp-group, #exp-plots, #exp-qq, #exp-forcemean",
```

- [ ] **Step 6: Update the callouts**

In `web/guided/summary/content.js`, replace the `showPlots` entry and add `showQq` (keep `groupBy` and `forceMean` untouched):

```js
  showPlots: "The distribution panels show each continuous variable two ways: a histogram with a smoothed density curve (dashed mean, solid median — when the two lines separate, the variable is skewed and median (IQR) is the honest summary) and a box plot per group with every individual observation jittered on top.",
  showQq: "A Q–Q plot compares your data against a perfect normal distribution, within each study group — exactly how this tool assesses normality. Points hugging the line support mean ± SD; a tail curving away supports median (IQR).",
```

- [ ] **Step 7: Run all JS unit tests**

Run: `npm run test:unit`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add web/guided/summary/demo.js web/guided/summary/demo.test.mjs web/guided/summary/guided-summary.js web/guided/summary/content.js
git commit -m "feat(summary): Q-Q normality experiment in the guided demo

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Upload form — Q–Q checkbox and spec passthrough

**Files:**
- Modify: `web/guided/summary/analyze-form.js`
- Test: `web/guided/summary/analyze-form.test.mjs`

**Interfaces:**
- Consumes: `options.show_qq` (Task 5).
- Produces: `buildSummarySpec(table, { groupBy, showPlots, showQq, selected })` — new optional `showQq` key, emitted as `options.show_qq` (boolean, `false` when absent); checkbox id `#showqq` in the config section (Task 9's e2e checks its default).

- [ ] **Step 1: Write the failing test**

In `web/guided/summary/analyze-form.test.mjs`, in the first `buildSummarySpec` block change the call to include `showQq: true`:

```js
  const spec = buildSummarySpec(table, {
    groupBy: "arm", showPlots: true, showQq: true, selected: ["age", "crp", "diabetes"] });
```

and add after `assert.equal(spec.options.show_plots, true);`:

```js
  assert.equal(spec.options.show_qq, true);
```

In the second block (which passes no `showQq`) add after `assert.equal(spec.roles.group, null);`:

```js
  assert.equal(spec.options.show_qq, false, "absent showQq must serialize as false");
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node web/guided/summary/analyze-form.test.mjs`
Expected: FAIL — `show_qq` is `undefined`.

- [ ] **Step 3: Implement**

In `web/guided/summary/analyze-form.js`:

`buildSummarySpec` — destructure and emit the new option:

```js
export function buildSummarySpec(table, { groupBy, showPlots, showQq, selected }) {
```

and in its `options` object after `show_plots: !!showPlots,`:

```js
      show_qq: !!showQq,
```

In `buildConfig`, after the `plotsLabel` block, add:

```js
    const qqLabel = doc.createElement("label");
    const qq = doc.createElement("input");
    qq.type = "checkbox"; qq.id = "showqq";
    qqLabel.append(qq, doc.createTextNode(" Show Q–Q normality plots"));
    config.appendChild(qqLabel);
```

and pass it from the Render click handler:

```js
      onSubmit(buildSummarySpec(table, {
        groupBy: groupChoice.group, showPlots: plots.checked, showQq: qq.checked, selected }));
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm run test:unit`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add web/guided/summary/analyze-form.js web/guided/summary/analyze-form.test.mjs
git commit -m "feat(summary): Q-Q toggle in the upload form

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Upload guidance block + downloadable example CSV

**Files:**
- Modify: `web/guided/summary/analyze-form.js`
- Test: `web/guided/summary/demo-data.test.mjs`

**Interfaces:**
- Consumes: `toCsv` (Task 2), `SUMMARY_DEMO` (`web/guided/summary/demo-data.js`).
- Produces: pre-upload guidance markup with anchor id `#example-csv` (`download="example-baseline.csv"`) — Task 9's e2e asserts both.

- [ ] **Step 1: Write the failing round-trip test**

In `web/guided/summary/demo-data.test.mjs`, add the import:

```js
import { parseCsv, toCsv } from "../../lib/csv.js";
```

and append before the final `console.log`:

```js
// The downloadable example CSV must reparse cleanly through the app's own parser.
const csvText = toCsv(SUMMARY_DEMO.rows, SUMMARY_DEMO.columns);
const roundTrip = parseCsv(csvText);
assert.deepEqual(roundTrip.columns, SUMMARY_DEMO.columns);
assert.equal(roundTrip.rows.length, 120);
assert.equal(roundTrip.types.age, "numeric");
assert.equal(roundTrip.types.arm, "categorical");
assert.equal(roundTrip.rows[2].length_of_stay, "", "null serializes as an empty (missing) cell");
```

- [ ] **Step 2: Run the test — it should PASS already**

Run: `node web/guided/summary/demo-data.test.mjs`
Expected: PASS (`toCsv` exists since Task 2 and the demo data contains no commas/quotes). This test is a regression guard on the demo generator's output, not a driver — the failing-first step for this task is the e2e in Task 9; proceed.

- [ ] **Step 3: Add the guidance block and download link**

In `web/guided/summary/analyze-form.js`:

Add imports at the top:

```js
import { parseCsv, toCsv } from "../../lib/csv.js";
import { SUMMARY_DEMO } from "./demo-data.js";
```

(`parseCsv` is already imported — merge into the one import statement.)

Add a module-level lazy Blob URL (created once per page lifetime, only when the form renders — never a network request):

```js
let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(SUMMARY_DEMO.rows, SUMMARY_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}
```

In `renderSummaryForm`, replace the `container.innerHTML` template with:

```js
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>The first row holds the column names.</li>
        <li>Leave a cell empty when a value is missing.</li>
        <li>To compare groups, include a column naming each participant’s group or arm.</li>
        <li>Keep numbers plain — no units, no thousands separators.</li>
      </ul>
      <p><a id="example-csv" download="example-baseline.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="summary-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
```

- [ ] **Step 4: Run all JS unit tests**

Run: `npm run test:unit`
Expected: all pass (the new markup is static; `getExampleCsvUrl` only runs when `renderSummaryForm` is invoked, which no unit test does).

- [ ] **Step 5: Commit**

```bash
git add web/guided/summary/analyze-form.js web/guided/summary/demo-data.test.mjs
git commit -m "feat(summary): CSV-format guidance and downloadable example in the upload form

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: E2E coverage + full verification

**Files:**
- Modify: `tests/e2e/summary-guided.spec.js`

**Interfaces:**
- Consumes: renamed nav button (Task 1), two-sibling-SVG output (Task 4), `#exp-qq` (Task 6), `#showqq` (Task 7), `#example-csv` (Task 8).
- Produces: nothing further — this is the closing verification gate.

- [ ] **Step 1: Fix the now-strict-mode-violating svg assertion**

In the test `"Run Example computes the real Table 1 with the right decisions, plot, and legend"`, the output now contains **two** sibling SVGs, so `toBeVisible()` on `#preview svg` violates Playwright strict mode. Change:

```js
  await expect(page.locator("#preview svg")).toBeVisible();             // bundled distribution plot
```

to:

```js
  await expect(page.locator("#preview svg")).toHaveCount(2);            // histogram+density and box+jitter rows
```

- [ ] **Step 2: Add the new tests**

Append to `tests/e2e/summary-guided.spec.js`:

```js
test("Analyze tab explains the expected CSV and offers an example download", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await expect(page.getByText("What your CSV should look like")).toBeVisible();
  await expect(page.locator("#example-csv")).toHaveAttribute("download", "example-baseline.csv");
  const href = await page.locator("#example-csv").getAttribute("href");
  expect(href).toMatch(/^blob:/);                       // client-side Blob — no network egress
});

test("Q–Q experiment adds a third distribution panel and its legend", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await expect(page.locator("#preview svg")).toHaveCount(2);
  await expect(page.locator("#exp-qq")).not.toBeChecked();       // default off
  await page.locator("#exp-qq").check();
  await expect(page.locator("#preview svg")).toHaveCount(3, { timeout: 120000 });
  await expect(page.locator("#preview .plot-legend")).toContainText("curved tail");
});

test("upload form has the Q–Q toggle, default off", async ({ page }) => {
  await page.goto("/#summary/analyze");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await page.locator("#csv").setInputFiles(
    path.join(__dirname, "..", "testthat", "fixtures", "summary-demo.csv"));
  await expect(page.locator("#summary-vars")).toBeVisible();
  await expect(page.locator("#showqq")).not.toBeChecked();
});
```

- [ ] **Step 3: Run the full verification suite**

```bash
Rscript -e 'devtools::test()'
npm run test:unit
rm -rf web/R && cp -R R web/R && npm run test:e2e
```

Expected: R suite `[ FAIL 0 | WARN 0 | … ]`; all unit files print ok; all Playwright tests pass (the webR download makes e2e slow — this is normal).

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/summary-guided.spec.js
git commit -m "test(summary): e2e for renamed surfaces, Q-Q toggle, upload guidance

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

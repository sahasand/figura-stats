# Additional Statistical Analyses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four inferential analyses — group comparison, correlation scatter, ROC/AUC, and a regression table (Table 2) — to the webR clinical-figures app, on a shared CSV-upload + column-picker foundation.

**Architecture:** Each analysis is one `R/<name>.R` function returning `list(svg=, text=)`, routed by the existing `render_figure(json_string)` dispatcher, with a matching `web/forms/<name>.js` built on two new shared JS modules (`web/lib/csv.js`, `web/lib/columnpicker.js`). Group comparison and correlation use base R stats (no extra webR download); ROC and regression lazy-install `pROC` and `gtsummary` via the worker's existing single-flight mechanism.

**Tech Stack:** R (ggplot2, stats, pROC, gtsummary, broom, svglite, jsonlite), testthat, webR, vanilla JS (no framework/build step), Playwright.

## Global Constraints

- **No backend; no user data leaves the browser.** Only network I/O is the webR CDN + local R/asset fetches.
- **R is the single source of statistical truth** — no statistics in JS. JS only parses the CSV, infers column types, and marshals the selected columns.
- **Every R figure function returns exactly `list(svg = <character>, text = <character>)`** and is testable in plain R (no browser). Plot analyses put an `<svg>` in `svg`; the regression table puts an HTML `<table>` in `svg` (same convention as `fig_table1`).
- **UI↔R contract is JSON:** JS sends `{figure, data:[{col:val}...], roles:{...}, options:{...}}`; R parses with `jsonlite::fromJSON(..., simplifyVector = FALSE)`; `render_figure` returns a JSON string and NEVER throws (errors become `{"ok":false,"error":...}`).
- **Test command is `Rscript -e 'devtools::test()'`** (or `filter=`). NOT `test_file()` — it silently swallows ggplot soft-deprecation warnings. **WARN 0 is a hard gate**; fix any deprecated ggplot arg at the source.
- **No deprecated ggplot2 args** (this repo runs ggplot2 4.x): use `linewidth` not `size`/`label.size` for lines, `geom_errorbar(orientation="y")` not `geom_errorbarh`, `linewidth` in `element_line`.
- **`web/R/` is a gitignored build copy** of `R/`; regenerate before serving/testing with `rm -rf web/R && cp -R R web/R` (the `rm -rf` avoids `cp` nesting into an existing dir). Never commit `web/R/`.
- **Additive UI wiring:** new `app.js`/`index.html`/`worker.js` edits must not disturb existing figures (forest/consort/table1/km).
- Reuse `.svg_string(plot, width, height)` from `R/dispatch.R`; reuse the `%||%` helper (defined in `R/forest.R`) — do not redefine either.

## Current-state facts (verified)

- `R/dispatch.R` `render_figure()` switches on `spec$figure` (`forest`/`consort`/`table1`/`km`) with `if (is.null(fig)) fig <- "(none)"` and a `stop("Unknown figure: ...")` default, wrapped in `tryCatch`.
- `web/worker.js`: boot installs `["ggplot2","svglite","jsonlite","knitr"]`; `EXTRA_PACKAGES = { km: ["survival","survminer"] }`; a single-flight `ensureExtraPackages` installs per-figure extras once; the R-file fetch loop lists `dispatch/forest/consort/table1/km/themes.R`; eval uses `shelter.evalR("as.character(suppressWarnings(render_figure(figure_input)))", { env: { figure_input: json }, captureConditions:false, captureStreams:false })`.
- `web/app.js`: `runFigure(spec)` posts `{id, json}`; a form registry maps `data-figure` keys to `render<Name>Form(container, render)`; `render(spec)` sets `#preview.innerHTML = out.svg` and `#stats.textContent = out.text` (or `out.error`).
- `web/index.html`: nav has four `<button data-figure="...">`.
- DESCRIPTION Imports: `ggplot2, survival, survminer, svglite, jsonlite, knitr, grDevices, stats`.

## File structure

```
web/lib/csv.js            NEW  parseCsv(text) -> {columns, rows, types}
web/lib/columnpicker.js   NEW  renderColumnPicker(container, roles, table, onReady)
R/groupcompare.R          NEW  fig_groupcompare(spec)
R/correlation.R           NEW  fig_correlation(spec)
R/roc.R                   NEW  fig_roc(spec)
R/regression.R            NEW  fig_regression(spec)
web/forms/groupcompare.js NEW
web/forms/correlation.js  NEW
web/forms/roc.js          NEW
web/forms/regression.js   NEW
R/dispatch.R              EDIT add 4 switch cases
web/worker.js             EDIT EXTRA_PACKAGES + R-file list
web/index.html            EDIT 4 nav buttons
web/app.js                EDIT register 4 forms
DESCRIPTION               EDIT add pROC, gtsummary, broom to Imports
tests/testthat/test-*.R   NEW one per fig_*
tests/e2e/*               EDIT one column-picker e2e + fixture
```

---

### Task 1: Shared CSV parser (`web/lib/csv.js`)

**Files:**
- Create: `web/lib/csv.js`
- Test: `web/lib/csv.test.mjs` (plain Node assertions — no framework)

**Interfaces:**
- Produces: `parseCsv(text)` → `{ columns: string[], rows: Array<Record<string,string>>, types: Record<string,"numeric"|"categorical"> }`. A column is `numeric` iff every non-empty cell in it parses as a finite number; else `categorical`. Throws `Error` with a clear message on: empty file, header-only (no data rows), duplicate header names.

- [ ] **Step 1: Write the failing test**

`web/lib/csv.test.mjs`:
```js
import assert from "node:assert";
import { parseCsv } from "./csv.js";

const csv = "age,arm,resp\r\n61,A,1\n72,B,0\n55,A,1\n";
const out = parseCsv(csv);
assert.deepEqual(out.columns, ["age", "arm", "resp"]);
assert.equal(out.rows.length, 3);
assert.equal(out.rows[0].age, "61");
assert.equal(out.types.age, "numeric");
assert.equal(out.types.arm, "categorical");
assert.equal(out.types.resp, "numeric");

assert.throws(() => parseCsv("a,b\n"), /no data rows/i);
assert.throws(() => parseCsv(""), /empty/i);
assert.throws(() => parseCsv("x,x\n1,2\n"), /duplicate/i);

console.log("csv.test.mjs OK");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node web/lib/csv.test.mjs`
Expected: FAIL — cannot find module `./csv.js` / `parseCsv` not a function.

- [ ] **Step 3: Write minimal implementation**

`web/lib/csv.js`:
```js
// Parse a CSV string into columns, row objects, and inferred per-column types.
// Statistics never happen here — this only shapes data for the R layer.
export function parseCsv(text) {
  if (!text || !text.trim()) throw new Error("The CSV file is empty.");
  const [head, ...lines] = text.trim().split(/\r?\n/);
  const columns = head.split(",").map((s) => s.trim());
  const seen = new Set();
  for (const c of columns) {
    if (seen.has(c)) throw new Error(`Duplicate column name: "${c}".`);
    seen.add(c);
  }
  const dataLines = lines.filter((l) => l.trim() !== "");
  if (dataLines.length === 0) throw new Error("The CSV has no data rows.");
  const rows = dataLines.map((l, i) => {
    const cells = l.split(",");
    if (cells.length < columns.length)
      throw new Error(`Row ${i + 1}: expected ${columns.length} columns, found ${cells.length}.`);
    const row = {};
    columns.forEach((c, j) => { row[c] = (cells[j] ?? "").trim(); });
    return row;
  });
  const types = {};
  for (const c of columns) {
    const isNum = rows.every((r) => {
      const v = r[c];
      return v === "" || (v !== "" && Number.isFinite(Number(v)));
    }) && rows.some((r) => r[c] !== "");
    types[c] = isNum ? "numeric" : "categorical";
  }
  return { columns, rows, types };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node web/lib/csv.test.mjs`
Expected: `csv.test.mjs OK`

- [ ] **Step 5: Commit**

```bash
git add web/lib/csv.js web/lib/csv.test.mjs
git commit -m "feat: shared CSV parser with column type inference"
```

---

### Task 2: Shared column picker (`web/lib/columnpicker.js`)

**Files:**
- Create: `web/lib/columnpicker.js`
- Test: `web/lib/columnpicker.test.mjs`

**Interfaces:**
- Consumes: the `{columns, rows, types}` shape from Task 1.
- Produces: `renderColumnPicker(container, roles, table, onReady)`.
  - `roles`: `Array<{ key: string, label: string, type: "numeric"|"categorical"|"any", multiple?: boolean }>`.
  - Renders one labeled `<select>` per role (a `<select multiple>` when `multiple`), listing only columns whose inferred type matches (`any` lists all).
  - Calls `onReady(rolesMap | null)`: `rolesMap` maps each role `key` → selected column name (or `string[]` when `multiple`) once every required role has a valid selection; `null` while incomplete.
  - Returns `{ value: () => rolesMap|null }`.
  - Because tests run in Node (no DOM), the module MUST work against a minimal injected document. Accept an optional 5th arg `doc = globalThis.document`; the test passes a tiny fake. Do NOT import anything browser-only at module top level.

- [ ] **Step 1: Write the failing test**

`web/lib/columnpicker.test.mjs`:
```js
import assert from "node:assert";
import { renderColumnPicker } from "./columnpicker.js";

// Minimal fake DOM: elements track children, value, options, and change handler.
function makeDoc() {
  const mk = (tag) => ({
    tag, children: [], style: {}, options: [], value: "", multiple: false,
    textContent: "", onchange: null, appendChild(c) { this.children.push(c); },
    querySelectorAll() { return []; },
    add(o) { this.options.push(o); },
  });
  return { createElement: mk };
}

const table = {
  columns: ["age", "arm", "resp"],
  rows: [{ age: "61", arm: "A", resp: "1" }],
  types: { age: "numeric", arm: "categorical", resp: "numeric" },
};
const container = { children: [], innerHTML: "", appendChild(c) { this.children.push(c); } };
const roles = [
  { key: "value", label: "Value", type: "numeric" },
  { key: "group", label: "Group", type: "categorical" },
];
let ready = "unset";
const picker = renderColumnPicker(container, roles, table, (m) => { ready = m; }, makeDoc());

// Numeric role must offer only numeric columns; categorical only categorical.
const selects = container.children.filter((c) => c.tag === "select");
assert.equal(selects.length, 2);
assert.deepEqual(selects[0].options.map((o) => o.value).filter(Boolean), ["age", "resp"]);
assert.deepEqual(selects[1].options.map((o) => o.value).filter(Boolean), ["arm"]);

// Simulate the user choosing both roles.
selects[0].value = "age"; selects[0].onchange();
selects[1].value = "arm"; selects[1].onchange();
assert.deepEqual(picker.value(), { value: "age", group: "arm" });
assert.deepEqual(ready, { value: "age", group: "arm" });

console.log("columnpicker.test.mjs OK");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node web/lib/columnpicker.test.mjs`
Expected: FAIL — module/function not found.

- [ ] **Step 3: Write minimal implementation**

`web/lib/columnpicker.js`:
```js
// Render role->column dropdowns filtered by inferred column type.
// No statistics here; this only lets the user map CSV columns to analysis roles.
export function renderColumnPicker(container, roles, table, onReady, doc = globalThis.document) {
  container.innerHTML = "";
  const selects = {};
  const compatible = (role) =>
    table.columns.filter((c) => role.type === "any" || table.types[c] === role.type);

  const current = () => {
    const map = {};
    for (const role of roles) {
      const sel = selects[role.key];
      if (role.multiple) {
        const chosen = Array.from(sel.options).filter((o) => o.selected && o.value).map((o) => o.value);
        if (chosen.length === 0) return null;
        map[role.key] = chosen;
      } else {
        if (!sel.value) return null;
        map[role.key] = sel.value;
      }
    }
    return map;
  };

  for (const role of roles) {
    const label = doc.createElement("label");
    label.textContent = role.label + (role.multiple ? " (pick one or more)" : "");
    container.appendChild(label);
    const sel = doc.createElement("select");
    sel.multiple = !!role.multiple;
    if (!role.multiple) {
      const blank = doc.createElement("option");
      blank.value = ""; blank.textContent = "— choose —";
      sel.add ? sel.add(blank) : sel.appendChild(blank);
    }
    for (const col of compatible(role)) {
      const opt = doc.createElement("option");
      opt.value = col; opt.textContent = col;
      sel.add ? sel.add(opt) : sel.appendChild(opt);
    }
    sel.onchange = () => onReady(current());
    selects[role.key] = sel;
    container.appendChild(sel);
  }
  onReady(current());
  return { value: current };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node web/lib/columnpicker.test.mjs`
Expected: `columnpicker.test.mjs OK`

- [ ] **Step 5: Commit**

```bash
git add web/lib/columnpicker.js web/lib/columnpicker.test.mjs
git commit -m "feat: shared column picker with type-filtered dropdowns"
```

---

### Task 3: Group comparison (`R/groupcompare.R` + form + wiring)

**Files:**
- Create: `R/groupcompare.R`, `web/forms/groupcompare.js`
- Modify: `R/dispatch.R` (add case), `web/index.html` (nav button), `web/app.js` (register form)
- Test: `tests/testthat/test-groupcompare.R`

**Interfaces:**
- Consumes: `.svg_string` (dispatch.R), `%||%` (forest.R), Task 1/2 modules.
- Produces: `fig_groupcompare(spec)` → `list(svg=, text=)`. Spec: `{figure:"groupcompare", data:[{...}], roles:{value:"col", group:"col"}, options:{plot:"box"|"violin", test:"parametric"|"nonparametric"}}`.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-groupcompare.R`:
```r
mkspec <- function(test = "parametric", plot = "box", ngroup = 2) {
  set.seed(7)
  grp <- rep(LETTERS[1:ngroup], each = 20)
  val <- rnorm(length(grp), mean = as.integer(factor(grp)))
  data <- lapply(seq_along(grp), function(i) list(value = val[i], grp = grp[i]))
  list(figure = "groupcompare", data = data,
       roles = list(value = "value", group = "grp"),
       options = list(plot = plot, test = test))
}

test_that("two-group parametric returns an SVG and a t-test p-value", {
  out <- fig_groupcompare(mkspec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "t-test|Welch", ignore.case = TRUE)
  expect_match(out$text, "p ?=|p ?<")
})

test_that("two-group nonparametric uses Mann-Whitney", {
  out <- fig_groupcompare(mkspec(test = "nonparametric"))
  expect_match(out$text, "Mann-Whitney|Wilcoxon", ignore.case = TRUE)
})

test_that("three groups use ANOVA / Kruskal-Wallis", {
  expect_match(fig_groupcompare(mkspec(ngroup = 3))$text, "ANOVA", ignore.case = TRUE)
  expect_match(fig_groupcompare(mkspec(ngroup = 3, test = "nonparametric"))$text,
               "Kruskal", ignore.case = TRUE)
})

test_that("errors when fewer than two groups", {
  expect_error(fig_groupcompare(mkspec(ngroup = 1)), "two groups", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Rscript -e 'devtools::test(filter = "groupcompare")'`
Expected: FAIL — `fig_groupcompare` not found.

- [ ] **Step 3: Write minimal implementation**

`R/groupcompare.R`:
```r
#' Compare a numeric value across groups: box/violin plot + significance test.
fig_groupcompare <- function(spec) {
  vcol <- spec$roles$value; gcol <- spec$roles$group
  rows <- spec$data
  value <- vapply(rows, function(r) as.numeric(r[[vcol]]), numeric(1))
  group <- vapply(rows, function(r) as.character(r[[gcol]]), character(1))
  df <- data.frame(value = value, group = group, stringsAsFactors = FALSE)
  df <- df[!is.na(df$value) & df$group != "", ]
  ng <- length(unique(df$group))
  if (ng < 2) stop("Group comparison needs at least two groups.")

  nonpar <- identical(spec$options$test %||% "parametric", "nonparametric")
  if (ng == 2) {
    if (nonpar) { ht <- stats::wilcox.test(value ~ group, data = df); tname <- "Mann-Whitney U test" }
    else { ht <- stats::t.test(value ~ group, data = df); tname <- "Welch t-test" }
  } else {
    if (nonpar) { ht <- stats::kruskal.test(value ~ group, data = df); tname <- "Kruskal-Wallis test" }
    else { ht <- stats::oneway.test(value ~ group, data = df); tname <- "one-way ANOVA (Welch)" }
  }
  p <- ht$p.value
  pfmt <- if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)

  plot_kind <- spec$options$plot %||% "box"
  base <- ggplot2::ggplot(df, ggplot2::aes(x = group, y = value))
  layer <- if (identical(plot_kind, "violin"))
    ggplot2::geom_violin(fill = "grey90") else ggplot2::geom_boxplot(fill = "grey90", outlier.shape = NA)
  gg <- base + layer +
    ggplot2::geom_jitter(width = 0.15, alpha = 0.5, size = 1) +
    ggplot2::labs(x = NULL, y = vcol) +
    ggplot2::theme_minimal(base_size = 12)

  meds <- tapply(df$value, df$group, stats::median)
  summ <- paste(sprintf("%s %.2f", names(meds), meds), collapse = ", ")
  txt <- sprintf("Median %s by group: %s. %s: %s.", vcol, summ, tname, pfmt)
  list(svg = .svg_string(gg, width = 6, height = 4.5), text = txt)
}
```
Then in `R/dispatch.R`, add to the `switch`: `groupcompare = fig_groupcompare(spec),` (place it alongside the existing cases).

- [ ] **Step 4: Run test to verify it passes**

Run: `Rscript -e 'devtools::test(filter = "groupcompare")'`
Expected: PASS (4 tests), WARN 0.

- [ ] **Step 5: Add the form + nav button + registration**

`web/forms/groupcompare.js`:
```js
import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderGroupCompareForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Group comparison</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <div id="picker"></div>
    <label for="plot">Plot</label>
    <select id="plot"><option value="box">Box</option><option value="violin">Violin</option></select>
    <label for="test">Test</label>
    <select id="test"><option value="parametric">Parametric (t-test / ANOVA)</option>
      <option value="nonparametric">Non-parametric (Mann-Whitney / Kruskal-Wallis)</option></select>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        renderColumnPicker(container.querySelector("#picker"),
          [{ key: "value", label: "Value (numeric)", type: "numeric" },
           { key: "group", label: "Group", type: "categorical" }],
          table, (m) => { roles = m; btn.disabled = !m; });
      } catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "groupcompare", data: table.rows, roles,
    options: { plot: container.querySelector("#plot").value,
               test: container.querySelector("#test").value } });
}
```
In `web/index.html`, add to the nav (after the km button):
```html
    <button data-figure="groupcompare">Group comparison</button>
```
In `web/app.js`, add the import and registry entry (additively, next to the others):
```js
import { renderGroupCompareForm } from "./forms/groupcompare.js";
// in the forms registry object: groupcompare: renderGroupCompareForm,
```

- [ ] **Step 6: Verify wiring + full suite, then commit**

Run: `Rscript -e 'devtools::test()'` → all pass, WARN 0.
Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e` → existing e2e still pass (no new e2e yet).
```bash
git add R/groupcompare.R tests/testthat/test-groupcompare.R web/forms/groupcompare.js R/dispatch.R web/index.html web/app.js
git commit -m "feat: group comparison analysis (box/violin + significance test)"
```

---

### Task 4: Correlation scatter (`R/correlation.R` + form + wiring)

**Files:**
- Create: `R/correlation.R`, `web/forms/correlation.js`
- Modify: `R/dispatch.R`, `web/index.html`, `web/app.js`
- Test: `tests/testthat/test-correlation.R`

**Interfaces:**
- Produces: `fig_correlation(spec)` → `list(svg=, text=)`. Spec: `{figure:"correlation", data:[...], roles:{x:"col", y:"col"}, options:{method:"pearson"|"spearman"}}`.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-correlation.R`:
```r
mkspec <- function(method = "pearson") {
  set.seed(3); x <- rnorm(80); y <- 0.7 * x + rnorm(80, sd = 0.6)
  data <- lapply(seq_along(x), function(i) list(x = x[i], y = y[i]))
  list(figure = "correlation", data = data, roles = list(x = "x", y = "y"),
       options = list(method = method))
}

test_that("pearson returns an SVG, r, and p", {
  out <- fig_correlation(mkspec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "r =")
  expect_match(out$text, "Pearson", ignore.case = TRUE)
  expect_match(out$text, "p ?=|p ?<")
})

test_that("known-value: r is close to cor()", {
  set.seed(3); x <- rnorm(80); y <- 0.7 * x + rnorm(80, sd = 0.6)
  expected <- round(cor(x, y), 2)
  out <- fig_correlation(mkspec())
  expect_match(out$text, sprintf("r = %.2f", expected))
})

test_that("spearman reports rho", {
  expect_match(fig_correlation(mkspec("spearman"))$text, "rho|Spearman", ignore.case = TRUE)
})

test_that("errors when a column is non-numeric / too few points", {
  bad <- mkspec(); bad$data <- bad$data[1]
  expect_error(fig_correlation(bad), "at least", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Rscript -e 'devtools::test(filter = "correlation")'`
Expected: FAIL — `fig_correlation` not found.

- [ ] **Step 3: Write minimal implementation**

`R/correlation.R`:
```r
#' Scatter plot + correlation (Pearson or Spearman) with r/rho, CI, p.
fig_correlation <- function(spec) {
  xcol <- spec$roles$x; ycol <- spec$roles$y
  rows <- spec$data
  x <- vapply(rows, function(r) as.numeric(r[[xcol]]), numeric(1))
  y <- vapply(rows, function(r) as.numeric(r[[ycol]]), numeric(1))
  ok <- !is.na(x) & !is.na(y)
  x <- x[ok]; y <- y[ok]
  if (length(x) < 3) stop("Correlation needs at least 3 complete point pairs.")

  method <- spec$options$method %||% "pearson"
  ct <- stats::cor.test(x, y, method = method)
  p <- ct$p.value
  pfmt <- if (p < 0.001) "p < 0.001" else sprintf("p = %.3f", p)
  df <- data.frame(x = x, y = y)
  gg <- ggplot2::ggplot(df, ggplot2::aes(x = x, y = y)) +
    ggplot2::geom_point(alpha = 0.6, size = 1.5) +
    ggplot2::geom_smooth(method = "lm", formula = y ~ x, se = TRUE, colour = "black") +
    ggplot2::labs(x = xcol, y = ycol) +
    ggplot2::theme_minimal(base_size = 12)

  if (identical(method, "pearson")) {
    ci <- ct$conf.int
    txt <- sprintf("r = %.2f (95%% CI %.2f-%.2f), %s (Pearson), n = %d.",
                   ct$estimate, ci[1], ci[2], pfmt, length(x))
  } else {
    txt <- sprintf("rho = %.2f, %s (Spearman), n = %d.", ct$estimate, pfmt, length(x))
  }
  list(svg = .svg_string(gg, width = 5.5, height = 4.5), text = txt)
}
```
Then add to `R/dispatch.R` switch: `correlation = fig_correlation(spec),`.

- [ ] **Step 4: Run test to verify it passes**

Run: `Rscript -e 'devtools::test(filter = "correlation")'`
Expected: PASS (4 tests), WARN 0. (If `geom_smooth` warns, the explicit `formula = y ~ x` prevents the usual message; keep it.)

- [ ] **Step 5: Add the form + nav button + registration**

`web/forms/correlation.js`:
```js
import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderCorrelationForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Correlation</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <div id="picker"></div>
    <label for="method">Method</label>
    <select id="method"><option value="pearson">Pearson</option><option value="spearman">Spearman</option></select>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        renderColumnPicker(container.querySelector("#picker"),
          [{ key: "x", label: "X (numeric)", type: "numeric" },
           { key: "y", label: "Y (numeric)", type: "numeric" }],
          table, (m) => { roles = m; btn.disabled = !m; });
      } catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "correlation", data: table.rows, roles,
    options: { method: container.querySelector("#method").value } });
}
```
`web/index.html` nav: `<button data-figure="correlation">Correlation</button>`.
`web/app.js`: `import { renderCorrelationForm } from "./forms/correlation.js";` + registry `correlation: renderCorrelationForm,`.

- [ ] **Step 6: Verify + commit**

Run: `Rscript -e 'devtools::test()'` → all pass, WARN 0.
```bash
git add R/correlation.R tests/testthat/test-correlation.R web/forms/correlation.js R/dispatch.R web/index.html web/app.js
git commit -m "feat: correlation scatter analysis (Pearson/Spearman)"
```

---

### Task 5: ROC / AUC (`R/roc.R` + form + wiring + lazy pROC)

**Files:**
- Create: `R/roc.R`, `web/forms/roc.js`
- Modify: `R/dispatch.R`, `web/index.html`, `web/app.js`, `web/worker.js` (EXTRA_PACKAGES), `DESCRIPTION` (Imports: pROC)
- Test: `tests/testthat/test-roc.R`

**Interfaces:**
- Produces: `fig_roc(spec)` → `list(svg=, text=)`. Spec: `{figure:"roc", data:[...], roles:{predictor:"col", outcome:"col"}}`. Outcome must have exactly two distinct values.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-roc.R`:
```r
mkspec <- function() {
  set.seed(11); n <- 120
  outcome <- rbinom(n, 1, 0.5)
  predictor <- outcome + rnorm(n, sd = 0.8)  # informative marker
  data <- lapply(seq_len(n), function(i) list(pred = predictor[i], out = outcome[i]))
  list(figure = "roc", data = data, roles = list(predictor = "pred", outcome = "out"))
}

test_that("roc returns an SVG and an AUC with CI and cutoff", {
  out <- fig_roc(mkspec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "AUC")
  expect_match(out$text, "95% CI")
  expect_match(out$text, "sensitivity", ignore.case = TRUE)
})

test_that("AUC is >= 0.5 and plausible for an informative marker", {
  out <- fig_roc(mkspec())
  auc <- as.numeric(sub(".*AUC ([0-9.]+).*", "\\1", out$text))
  expect_gt(auc, 0.6)
})

test_that("errors when outcome is not binary", {
  s <- mkspec(); s$data[[1]]$out <- 2
  expect_error(fig_roc(s), "two", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Rscript -e 'devtools::test(filter = "roc")'`
Expected: FAIL — `fig_roc` not found.

- [ ] **Step 3: Write minimal implementation**

`R/roc.R`:
```r
#' ROC curve + AUC (DeLong CI) + Youden-optimal cutoff.
fig_roc <- function(spec) {
  pcol <- spec$roles$predictor; ocol <- spec$roles$outcome
  rows <- spec$data
  predictor <- vapply(rows, function(r) as.numeric(r[[pcol]]), numeric(1))
  outcome_raw <- vapply(rows, function(r) as.character(r[[ocol]]), character(1))
  ok <- !is.na(predictor) & outcome_raw != ""
  predictor <- predictor[ok]; outcome_raw <- outcome_raw[ok]
  levs <- sort(unique(outcome_raw))
  if (length(levs) != 2) stop("ROC needs an outcome with exactly two distinct values.")

  roc <- pROC::roc(response = outcome_raw, predictor = predictor,
                   levels = levs, direction = "auto", quiet = TRUE)
  auc <- as.numeric(pROC::auc(roc))
  ci <- as.numeric(pROC::ci.auc(roc))            # c(lower, auc, upper)
  best <- pROC::coords(roc, "best", best.method = "youden",
                       ret = c("threshold", "sensitivity", "specificity"))
  best <- as.data.frame(best)[1, ]

  crd <- pROC::coords(roc, "all", ret = c("specificity", "sensitivity"))
  crd <- as.data.frame(crd)
  gg <- ggplot2::ggplot(crd, ggplot2::aes(x = 1 - specificity, y = sensitivity)) +
    ggplot2::geom_abline(slope = 1, intercept = 0, linetype = "dashed", colour = "grey60") +
    ggplot2::geom_path(linewidth = 0.8) +
    ggplot2::coord_equal() +
    ggplot2::labs(x = "1 - specificity", y = "Sensitivity") +
    ggplot2::theme_minimal(base_size = 12)

  txt <- sprintf(
    "AUC %.2f (95%% CI %.2f-%.2f). Optimal cutoff %.2f: sensitivity %.0f%%, specificity %.0f%%.",
    auc, ci[1], ci[3], best$threshold, 100 * best$sensitivity, 100 * best$specificity)
  list(svg = .svg_string(gg, width = 5, height = 5), text = txt)
}
```
Then:
- `R/dispatch.R` switch: `roc = fig_roc(spec),`.
- `DESCRIPTION` Imports: append `, pROC`.

- [ ] **Step 4: Run test to verify it passes**

Run: `Rscript -e 'devtools::test(filter = "roc")'`
Expected: PASS (3 tests), WARN 0. (pROC is installed locally.)

- [ ] **Step 5: Form + nav + registration + lazy install**

`web/forms/roc.js`:
```js
import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderRocForm(container, onSubmit) {
  container.innerHTML = `
    <h2>ROC / AUC</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <div id="picker"></div>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        renderColumnPicker(container.querySelector("#picker"),
          [{ key: "predictor", label: "Predictor (numeric)", type: "numeric" },
           { key: "outcome", label: "Outcome (2 levels)", type: "any" }],
          table, (m) => { roles = m; btn.disabled = !m; });
      } catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "roc", data: table.rows, roles, options: {} });
}
```
`web/index.html` nav: `<button data-figure="roc">ROC / AUC</button>`.
`web/app.js`: `import { renderRocForm } from "./forms/roc.js";` + registry `roc: renderRocForm,`.
`web/worker.js`: extend `EXTRA_PACKAGES` to `{ km: ["survival","survminer"], roc: ["pROC"] }`, and add `"roc.R"` to the R-file fetch loop list.

- [ ] **Step 6: Verify + commit**

Run: `Rscript -e 'devtools::test()'` → all pass, WARN 0.
Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e` → existing e2e still pass.
```bash
git add R/roc.R tests/testthat/test-roc.R web/forms/roc.js R/dispatch.R web/index.html web/app.js web/worker.js DESCRIPTION
git commit -m "feat: ROC/AUC analysis (pROC, lazy-installed)"
```

---

### Task 6: Regression table (`R/regression.R` + form + wiring + lazy gtsummary)

**Files:**
- Create: `R/regression.R`, `web/forms/regression.js`
- Modify: `R/dispatch.R`, `web/index.html`, `web/app.js`, `web/worker.js`, `DESCRIPTION` (Imports: gtsummary, broom)
- Test: `tests/testthat/test-regression.R`

**Interfaces:**
- Produces: `fig_regression(spec)` → `list(svg=, text=)` where `svg` is an HTML `<table>` (like `fig_table1`) and `text` is a TSV. Spec: `{figure:"regression", data:[...], roles:{outcome:"col"?, covariates:["c1","c2"], time:"col"?, status:"col"?}, options:{model:"logistic"|"cox"|"linear"}}`.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-regression.R`:
```r
mkdata <- function(n = 150) {
  set.seed(21)
  age <- round(rnorm(n, 60, 10)); sex <- sample(c("M","F"), n, TRUE)
  lp <- -4 + 0.05 * age + 0.4 * (sex == "M")
  event <- rbinom(n, 1, plogis(lp))
  time <- round(rexp(n, 0.05) + 1, 1)
  lapply(seq_len(n), function(i)
    list(age = age[i], sex = sex[i], event = event[i], time = time[i]))
}

test_that("logistic regression returns an HTML table with OR", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(outcome = "event", covariates = list("age", "sex")),
    options = list(model = "logistic"))
  out <- fig_regression(spec)
  expect_match(out$svg, "<table")
  expect_match(out$text, "OR|Odds", ignore.case = TRUE)
  expect_match(out$svg, "age")
})

test_that("cox regression returns an HTML table with HR", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(time = "time", status = "event", covariates = list("age", "sex")),
    options = list(model = "cox"))
  out <- fig_regression(spec)
  expect_match(out$svg, "<table")
  expect_match(out$text, "HR|Hazard", ignore.case = TRUE)
})

test_that("errors when no covariates selected", {
  spec <- list(figure = "regression", data = mkdata(),
    roles = list(outcome = "event", covariates = list()),
    options = list(model = "logistic"))
  expect_error(fig_regression(spec), "covariate", ignore.case = TRUE)
})

test_that("errors when logistic outcome is not binary", {
  d <- mkdata(); d[[1]]$event <- 3
  spec <- list(figure = "regression", data = d,
    roles = list(outcome = "event", covariates = list("age")),
    options = list(model = "logistic"))
  expect_error(fig_regression(spec), "two", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `Rscript -e 'devtools::test(filter = "regression")'`
Expected: FAIL — `fig_regression` not found.

- [ ] **Step 3: Write minimal implementation**

`R/regression.R`:
```r
#' Univariable + multivariable regression table (logistic/Cox/linear).
fig_regression <- function(spec) {
  covs <- unlist(spec$roles$covariates)
  if (length(covs) == 0) stop("Select at least one covariate.")
  model <- spec$options$model %||% "logistic"
  rows <- spec$data

  col <- function(name, numeric = TRUE) {
    v <- vapply(rows, function(r) {
      x <- r[[name]]; if (is.null(x)) NA else if (numeric) as.numeric(x) else as.character(x)
    }, if (numeric) numeric(1) else character(1))
    v
  }
  df <- data.frame(lapply(covs, function(c) {
    raw <- vapply(rows, function(r) as.character(r[[c]] %||% ""), character(1))
    num <- suppressWarnings(as.numeric(raw))
    if (all(!is.na(num) | raw == "")) num else raw   # numeric if it all parses
  }), stringsAsFactors = FALSE)
  names(df) <- covs

  build <- function() {
    if (model == "cox") {
      df$.time <- col(spec$roles$time); df$.status <- col(spec$roles$status)
      if (any(is.na(df$.time)) || !all(df$.status %in% c(0, 1)))
        stop("Cox regression needs numeric time and a 0/1 status column.")
      fml <- stats::as.formula(paste("survival::Surv(.time, .status) ~", paste(covs, collapse = " + ")))
      survival::coxph(fml, data = df)
    } else if (model == "linear") {
      df$.y <- col(spec$roles$outcome)
      stats::lm(stats::as.formula(paste(".y ~", paste(covs, collapse = " + "))), data = df)
    } else {
      y <- col(spec$roles$outcome)
      if (length(unique(y[!is.na(y)])) != 2) stop("Logistic regression needs a binary (two-value) outcome.")
      df$.y <- as.integer(factor(y)) - 1L
      stats::glm(stats::as.formula(paste(".y ~", paste(covs, collapse = " + "))),
                 data = df, family = stats::binomial())
    }
  }
  fit <- build()
  tbl <- gtsummary::tbl_regression(fit, exponentiate = (model != "linear"))
  html <- gtsummary::as_kable_html(tbl)
  # Plain-text (TSV-ish) rendering for pasting.
  txtdf <- as.data.frame(tbl$table_body[, intersect(c("label", "estimate", "conf.low", "conf.high", "p.value"),
                                                     names(tbl$table_body))])
  effect_word <- switch(model, cox = "HR", linear = "beta", "OR")
  tsv <- paste0(effect_word, " table\n",
                paste(apply(txtdf, 1, function(r) paste(r, collapse = "\t")), collapse = "\n"))
  list(svg = as.character(html), text = tsv)
}
```
Then:
- `R/dispatch.R` switch: `regression = fig_regression(spec),`.
- `DESCRIPTION` Imports: append `, gtsummary, broom`.

- [ ] **Step 4: Run test to verify it passes**

Run: `Rscript -e 'devtools::test(filter = "regression")'`
Expected: PASS (4 tests), WARN 0. (gtsummary/broom installed locally. If gtsummary emits a soft-deprecation WARN, wrap the `tbl_regression`/`as_kable_html` calls in `suppressWarnings()` — gtsummary internals, not our code — to hold the WARN-0 gate, and note it.)

- [ ] **Step 5: Form + nav + registration + lazy install**

`web/forms/regression.js`:
```js
import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderRegressionForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Regression table (Table 2)</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <label for="model">Model</label>
    <select id="model">
      <option value="logistic">Logistic (odds ratios)</option>
      <option value="cox">Cox (hazard ratios)</option>
      <option value="linear">Linear (beta)</option></select>
    <div id="picker"></div>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  const model = container.querySelector("#model");
  const rebuild = () => {
    if (!table) return;
    const isCox = model.value === "cox";
    const rolesDef = isCox
      ? [{ key: "time", label: "Time (numeric)", type: "numeric" },
         { key: "status", label: "Status (0/1)", type: "numeric" },
         { key: "covariates", label: "Covariates", type: "any", multiple: true }]
      : [{ key: "outcome", label: "Outcome", type: "any" },
         { key: "covariates", label: "Covariates", type: "any", multiple: true }];
    renderColumnPicker(container.querySelector("#picker"), rolesDef, table,
      (m) => { roles = m; btn.disabled = !m; });
  };
  model.onchange = rebuild;
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try { table = parseCsv(reader.result); rebuild(); }
      catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "regression", data: table.rows, roles,
    options: { model: model.value } });
}
```
`web/index.html` nav: `<button data-figure="regression">Regression table</button>`.
`web/app.js`: `import { renderRegressionForm } from "./forms/regression.js";` + registry `regression: renderRegressionForm,`.
`web/worker.js`: extend `EXTRA_PACKAGES` to include `regression: ["gtsummary","broom"]`, and add `"regression.R"` to the R-file fetch loop list.

- [ ] **Step 6: Verify + commit**

Run: `Rscript -e 'devtools::test()'` → all pass, WARN 0.
Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e` → existing e2e still pass.
```bash
git add R/regression.R tests/testthat/test-regression.R web/forms/regression.js R/dispatch.R web/index.html web/app.js web/worker.js DESCRIPTION
git commit -m "feat: regression table analysis (logistic/Cox/linear via gtsummary, lazy)"
```

---

### Task 7: End-to-end test for the column-picker path + JS unit tests in CI

**Files:**
- Create: `tests/e2e/fixtures/groupcompare.csv`, `tests/e2e/analysis.spec.js`
- Modify: `.github/workflows/ci.yml` (run the JS unit tests), `package.json` (test:unit script)

**Interfaces:**
- Consumes: the group-comparison form + shared picker + `fig_groupcompare`.

- [ ] **Step 1: Write the fixture and failing e2e test**

`tests/e2e/fixtures/groupcompare.csv`:
```
value,arm
5.1,A
6.2,A
4.8,A
5.5,A
7.1,B
8.0,B
6.6,B
7.4,B
5.9,A
8.3,B
```

`tests/e2e/analysis.spec.js`:
```js
const { test, expect } = require("@playwright/test");
const path = require("path");

test("group comparison renders an SVG via the column picker", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /group comparison/i }).click();
  await page.setInputFiles("#csv", path.join(__dirname, "fixtures/groupcompare.csv"));
  // Column picker appears after parse; choose value + group.
  await page.locator("#picker select").first().selectOption("value");
  await page.locator("#picker select").nth(1).selectOption("arm");
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 200000 });
});
```

- [ ] **Step 2: Run to verify it fails (before wiring is served)**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/analysis.spec.js`
Expected: initially FAIL if run before Task 3 shipped; after Task 3 it should PASS. (If Tasks 3-6 are already merged, it PASSES now — that's fine, it's the regression guard.)

- [ ] **Step 3: Add JS unit tests to CI**

`package.json` — add to `scripts`:
```json
"test:unit": "node web/lib/csv.test.mjs && node web/lib/columnpicker.test.mjs"
```

`.github/workflows/ci.yml` — add a second job (after the existing `r-tests` job, same `jobs:` map):
```yaml
  js-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci || npm install
      - run: npm run test:unit
```

- [ ] **Step 4: Run the unit tests locally**

Run: `npm run test:unit`
Expected: `csv.test.mjs OK` and `columnpicker.test.mjs OK`.

- [ ] **Step 5: Run the e2e test**

Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e`
Expected: all e2e pass (forest, km, and the new group-comparison analysis).

- [ ] **Step 6: Commit**

```bash
git add tests/e2e/fixtures/groupcompare.csv tests/e2e/analysis.spec.js package.json .github/workflows/ci.yml
git commit -m "test: e2e for column-picker analysis path + JS unit tests in CI"
```

---

### Task 8: README + spec-diagram touch-up

**Files:**
- Modify: `README.md`

**Interfaces:** none (docs).

- [ ] **Step 1: Update the README feature list**

In `README.md`, extend the figure/analysis list to include the four new analyses (group comparison, correlation, ROC/AUC, regression table) and note that analyses take an uploaded CSV with an in-browser column picker. Keep the "your data never leaves your browser" framing. Add `pROC` and `gtsummary` to the packages sentence.

- [ ] **Step 2: Verify build + full suites one last time**

Run: `Rscript -e 'devtools::test()'` → all pass, WARN 0.
Run: `npm run test:unit` → both OK.
Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e` → all pass.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the four new statistical analyses"
```

---

## Self-Review Notes

- **Spec coverage:** shared CSV parser (T1) + column picker (T2); group comparison (T3), correlation (T4), ROC (T5), regression (T6); dispatch cases, worker EXTRA_PACKAGES + R-file list, nav buttons, app.js registry all folded into T3–T6; error handling via `stop()` in each `fig_*`; testing per function + one column-picker e2e (T7); README (T8). All spec sections map to a task.
- **Contract consistency:** every `fig_*` returns `list(svg=, text=)`; regression uses HTML-in-`svg` like `fig_table1`; specs use `roles`/`data`/`options`; dispatch keys (`groupcompare`/`correlation`/`roc`/`regression`) match `data-figure` attributes, form registry keys, `EXTRA_PACKAGES` keys, and R filenames.
- **WARN-0 risks flagged:** `geom_smooth` (explicit `formula`), gtsummary internals (suppressWarnings fallback noted in T6). `linewidth` used in `geom_path`.
- **Lazy deps:** ROC → pROC (T5), regression → gtsummary+broom (T6); group comparison & correlation add nothing to boot. DESCRIPTION Imports updated in the tasks that introduce each package (so CI's `local::.` installs them).
- **Deferred (documented in spec Out-of-scope):** KM-form refactor onto the picker; multiplicity correction; model diagnostics; paired/mixed models; spec save/load.

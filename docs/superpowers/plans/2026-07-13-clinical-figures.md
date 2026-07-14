# Clinical Manuscript Figures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free, static, browser-based tool that renders publication-ready clinical figures (forest plot, CONSORT diagram, Table 1, Kaplan-Meier curve) plus copyable statistics text, using real R packages running client-side via webR.

**Architecture:** A static single-page app. All computation happens in the browser: a thin vanilla-JS UI sends a JSON spec to an R session (webR/WebAssembly) running in a Web Worker; R renders an SVG and a results sentence and returns them. No backend, no data upload. The R code is authored and tested as a plain R package on a laptop — webR is only the delivery vehicle — so every figure function has a fast, browser-free test cycle.

**Tech Stack:** R (ggplot2, survival, survminer, gtsummary, svglite, jsonlite), testthat for R tests, webR (WASM) loaded from CDN, vanilla HTML/CSS/JS (no framework, no build step), Playwright for one end-to-end smoke test, GitHub Actions + GitHub Pages for CI and hosting.

## Global Constraints

- **No backend.** No user data may leave the browser via any network call.
- **No JS framework, no build step for the UI.** Plain HTML/CSS/JS served as static files.
- **R is the single source of statistical truth.** No statistics reimplemented in JS.
- **Every R figure function is testable in plain R** (no browser) and returns the exact same contract: a list `list(svg = <character>, text = <character>)`.
- **UI↔R contract is JSON.** JS sends a JSON string; R parses with `jsonlite::fromJSON(..., simplifyVector = FALSE)`; R replies with a JSON string.
- **Dispatch entry point** is `render_figure(json_string)` returning a JSON string `{"ok":true,"svg":...,"text":...}` or `{"ok":false,"error":...}`.
- **webR packages must exist as WASM builds** in the webR CDN repo — verify ggplot2, survival, survminer, gtsummary, svglite, jsonlite at Task 3 start before wiring.
- Repo layout: `R/` (figure functions), `tests/testthat/` (R tests), `web/` (static site), `.github/workflows/` (CI).

---

### Task 1: Repo scaffold and dispatch skeleton

**Files:**
- Create: `DESCRIPTION`
- Create: `R/dispatch.R`
- Create: `tests/testthat.R`
- Create: `tests/testthat/test-dispatch.R`
- Create: `.gitignore`

**Interfaces:**
- Produces: `render_figure(json_string)` → JSON string. On unknown `figure`, returns `{"ok":false,"error":"..."}`. Routes known figures to `fig_<name>(spec)` where `spec` is the parsed list and each `fig_*` returns `list(svg=, text=)`.
- Produces: `.svg_string(plot, width, height)` helper → character SVG.

- [ ] **Step 1: Write `.gitignore` and `DESCRIPTION`**

`.gitignore`:
```
.Rproj.user
.Rhistory
.RData
node_modules/
web/webr/
*.DS_Store
```

`DESCRIPTION` (makes `R/` loadable via `devtools::load_all()` / `pkgload`):
```
Package: manuscriptfigures
Title: Publication-ready clinical figures via webR
Version: 0.0.0.9000
Description: R figure functions rendered client-side in the browser.
Encoding: UTF-8
Imports: ggplot2, survival, survminer, gtsummary, svglite, jsonlite
Suggests: testthat (>= 3.0.0)
Config/testthat/edition: 3
```

- [ ] **Step 2: Write the failing test**

`tests/testthat.R`:
```r
library(testthat)
library(manuscriptfigures)
test_check("manuscriptfigures")
```

`tests/testthat/test-dispatch.R`:
```r
test_that("unknown figure returns an ok:false error payload", {
  out <- jsonlite::fromJSON(render_figure('{"figure":"nope"}'))
  expect_false(out$ok)
  expect_match(out$error, "unknown figure", ignore.case = TRUE)
})

test_that("malformed JSON returns an error payload, not a crash", {
  out <- jsonlite::fromJSON(render_figure('{not json'))
  expect_false(out$ok)
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `R -q -e 'devtools::test()'`
Expected: FAIL — `render_figure` not found.

- [ ] **Step 4: Write minimal implementation**

`R/dispatch.R`:
```r
#' Render a figure from a JSON spec string. Never throws; always returns JSON.
render_figure <- function(json_string) {
  result <- tryCatch({
    spec <- jsonlite::fromJSON(json_string, simplifyVector = FALSE)
    fig <- spec$figure
    out <- switch(as.character(fig),
      forest  = fig_forest(spec),
      consort = fig_consort(spec),
      table1  = fig_table1(spec),
      km      = fig_km(spec),
      stop(sprintf("Unknown figure: %s", fig))
    )
    list(ok = TRUE, svg = out$svg, text = out$text)
  }, error = function(e) {
    list(ok = FALSE, error = conditionMessage(e))
  })
  jsonlite::toJSON(result, auto_unbox = TRUE)
}

#' Render a ggplot to an SVG string (no file on disk).
.svg_string <- function(plot, width = 7, height = 5) {
  s <- svglite::svgstring(width = width, height = height)
  print(plot)
  grDevices::dev.off()
  paste(s(), collapse = "")
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `R -q -e 'devtools::test()'`
Expected: PASS (2 tests). `unknown figure` matches the `Unknown figure:` message.

- [ ] **Step 6: Commit**

```bash
git add DESCRIPTION R/dispatch.R tests/ .gitignore
git commit -m "feat: repo scaffold and JSON dispatch skeleton"
```

---

### Task 2: Forest plot figure function

**Files:**
- Create: `R/forest.R`
- Test: `tests/testthat/test-forest.R`

**Interfaces:**
- Consumes: `.svg_string()` from Task 1.
- Produces: `fig_forest(spec)` → `list(svg=, text=)`. Spec shape:
  `{"figure":"forest","rows":[{"label":"Overall","estimate":0.72,"lower":0.55,"upper":0.94}, ...],"options":{"effect_label":"Hazard Ratio","null_line":1}}`.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-forest.R`:
```r
spec <- list(
  figure = "forest",
  rows = list(
    list(label = "Overall", estimate = 0.72, lower = 0.55, upper = 0.94),
    list(label = "Age < 65", estimate = 0.80, lower = 0.60, upper = 1.07)
  ),
  options = list(effect_label = "Hazard Ratio", null_line = 1)
)

test_that("fig_forest returns an SVG and a results sentence", {
  out <- fig_forest(spec)
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "0.72")
  expect_match(out$text, "0.55")
  expect_match(out$text, "0.94")
})

test_that("fig_forest errors clearly when a CI is inverted", {
  bad <- spec
  bad$rows[[1]]$lower <- 0.99  # lower > upper
  expect_error(fig_forest(bad), "confidence interval", ignore.case = TRUE)
})

test_that("render_figure routes forest specs end to end", {
  out <- jsonlite::fromJSON(render_figure(jsonlite::toJSON(spec, auto_unbox = TRUE)))
  expect_true(out$ok)
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `R -q -e 'devtools::test(filter = "forest")'`
Expected: FAIL — `fig_forest` not found.

- [ ] **Step 3: Write minimal implementation**

`R/forest.R`:
```r
#' Forest plot from summary effect estimates + CIs.
fig_forest <- function(spec) {
  rows <- spec$rows
  if (length(rows) == 0) stop("Forest plot needs at least one row.")
  df <- data.frame(
    label    = vapply(rows, function(r) as.character(r$label), character(1)),
    estimate = vapply(rows, function(r) as.numeric(r$estimate), numeric(1)),
    lower    = vapply(rows, function(r) as.numeric(r$lower), numeric(1)),
    upper    = vapply(rows, function(r) as.numeric(r$upper), numeric(1)),
    stringsAsFactors = FALSE
  )
  if (any(df$lower > df$upper)) {
    stop("Each confidence interval lower bound must be <= its upper bound.")
  }
  effect_label <- spec$options$effect_label %||% "Effect"
  null_line    <- spec$options$null_line %||% 1
  df$label <- factor(df$label, levels = rev(df$label))

  p <- ggplot2::ggplot(df, ggplot2::aes(x = estimate, y = label)) +
    ggplot2::geom_vline(xintercept = null_line, linetype = "dashed",
                        colour = "grey50") +
    ggplot2::geom_point(size = 2.5) +
    ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper),
                            height = 0.2) +
    ggplot2::labs(x = effect_label, y = NULL) +
    ggplot2::theme_minimal(base_size = 12)

  first <- df[df$label == df$label[nrow(df)], ][1, ]
  txt <- sprintf("%s %.2f (95%% CI %.2f–%.2f)",
                 effect_label, first$estimate, first$lower, first$upper)
  list(svg = .svg_string(p, width = 6, height = 0.6 * nrow(df) + 1.5),
       text = txt)
}

`%||%` <- function(a, b) if (is.null(a)) b else a
```

- [ ] **Step 4: Run test to verify it passes**

Run: `R -q -e 'devtools::test(filter = "forest")'`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add R/forest.R tests/testthat/test-forest.R
git commit -m "feat: forest plot figure function"
```

---

### Task 3: App shell, webR worker, forest wired end-to-end

**Files:**
- Create: `web/index.html`
- Create: `web/app.js`
- Create: `web/worker.js`
- Create: `web/styles.css`
- Create: `web/forms/forest.js`
- Create: `package.json`
- Create: `playwright.config.js`
- Test: `tests/e2e/smoke.spec.js`

**Interfaces:**
- Consumes: `render_figure(json_string)` from Task 1 (loaded into webR).
- Produces: `runFigure(specObject)` in `app.js` → resolves to `{ok, svg, text}` by round-tripping JSON through the worker.
- Produces: `renderForestForm(container, onSubmit)` in `forms/forest.js` — builds the forest input form and calls `onSubmit(specObject)`.
- Produces: worker message protocol — `postMessage({id, json})` → `postMessage({id, result})`.

- [ ] **Step 0: Verify webR package availability**

Run: `R -q -e 'cat("check webR repo for: ggplot2 survival survminer gtsummary svglite jsonlite\n")'`
Then open https://repo.r-wasm.org/ and confirm each package has a WASM build. If any is missing, stop and report before proceeding.

- [ ] **Step 1: Write the failing smoke test**

`package.json`:
```json
{
  "name": "manuscript-figures-web",
  "private": true,
  "scripts": {
    "serve": "python3 -m http.server 8080 --directory web",
    "test:e2e": "playwright test"
  },
  "devDependencies": { "@playwright/test": "^1.45.0" }
}
```

`playwright.config.js`:
```js
module.exports = {
  testDir: "tests/e2e",
  timeout: 120000,
  webServer: { command: "npm run serve", url: "http://localhost:8080", reuseExistingServer: true },
  use: { baseURL: "http://localhost:8080" }
};
```

`tests/e2e/smoke.spec.js`:
```js
const { test, expect } = require("@playwright/test");

test("forest plot renders an SVG end to end", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /forest/i }).click();
  await page.getByLabel(/effect label/i).fill("Hazard Ratio");
  await page.getByRole("button", { name: /add row/i }).click();
  await page.getByLabel(/label/i).first().fill("Overall");
  await page.getByLabel(/estimate/i).first().fill("0.72");
  await page.getByLabel(/lower/i).first().fill("0.55");
  await page.getByLabel(/upper/i).first().fill("0.94");
  await page.getByRole("button", { name: /render/i }).click();
  await expect(page.locator("#preview svg")).toBeVisible({ timeout: 90000 });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm install && npx playwright install chromium && npm run test:e2e`
Expected: FAIL — no page / elements yet.

- [ ] **Step 3: Write the worker**

`web/worker.js`:
```js
importScripts("https://webr.r-wasm.org/latest/webr.mjs");
let webRReady;

async function boot() {
  const { WebR } = await import("https://webr.r-wasm.org/latest/webr.mjs");
  const webR = new WebR();
  await webR.init();
  await webR.installPackages(
    ["ggplot2", "survival", "survminer", "gtsummary", "svglite", "jsonlite"],
    { quiet: true }
  );
  // Load all R source files that define fig_* and render_figure.
  for (const f of ["dispatch.R", "forest.R", "consort.R", "table1.R", "km.R", "themes.R"]) {
    const resp = await fetch(`R/${f}`);
    if (resp.ok) await webR.evalRVoid(await resp.text());
  }
  return webR;
}

self.onmessage = async (e) => {
  const { id, json } = e.data;
  try {
    webRReady = webRReady || boot();
    const webR = await webRReady;
    const shelter = await new webR.Shelter();
    const res = await shelter.evalR("render_figure(input)", { env: { input: json } });
    const out = await res.toString();
    shelter.purge();
    self.postMessage({ id, result: out });
  } catch (err) {
    self.postMessage({ id, result: JSON.stringify({ ok: false, error: String(err) }) });
  }
};
```

Note: the R source files must be reachable from the deployed site. In this plan they are copied into `web/R/` by the CI build (Task 8); for local dev, symlink or copy `R/` to `web/R/`.

- [ ] **Step 4: Write app.js (worker bridge + figure picker)**

`web/app.js`:
```js
const worker = new Worker("worker.js");
const pending = new Map();
let nextId = 1;

worker.onmessage = (e) => {
  const { id, result } = e.data;
  const resolve = pending.get(id);
  if (resolve) { pending.delete(id); resolve(JSON.parse(result)); }
};

export function runFigure(spec) {
  return new Promise((resolve) => {
    const id = nextId++;
    pending.set(id, resolve);
    worker.postMessage({ id, json: JSON.stringify(spec) });
  });
}

async function render(spec) {
  const preview = document.getElementById("preview");
  const stats = document.getElementById("stats");
  preview.innerHTML = "Rendering… (first run downloads R, ~30s)";
  const out = await runFigure(spec);
  if (!out.ok) { preview.innerHTML = ""; stats.textContent = "Error: " + out.error; return; }
  preview.innerHTML = out.svg;
  stats.textContent = out.text;
}

import { renderForestForm } from "./forms/forest.js";
const forms = { forest: renderForestForm };

document.querySelectorAll("[data-figure]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = btn.dataset.figure;
    const container = document.getElementById("form");
    container.innerHTML = "";
    (forms[kind] || (() => {}))(container, render);
  });
});
```

- [ ] **Step 5: Write index.html + styles.css + forest form**

`web/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Clinical Manuscript Figures</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <header><h1>Clinical Manuscript Figures</h1>
    <p>Publication figures + stats, computed in your browser. Data never leaves this page.</p>
  </header>
  <nav>
    <button data-figure="forest">Forest plot</button>
    <button data-figure="consort">CONSORT</button>
    <button data-figure="table1">Table 1</button>
    <button data-figure="km">Kaplan-Meier</button>
  </nav>
  <main>
    <section id="form"></section>
    <section><div id="preview"></div><pre id="stats"></pre></section>
  </main>
  <script type="module" src="app.js"></script>
</body>
</html>
```

`web/styles.css`:
```css
body { font-family: system-ui, sans-serif; margin: 0; color: #1a1a1a; }
header, nav, main { padding: 1rem 1.5rem; }
nav button { margin-right: .5rem; padding: .5rem 1rem; cursor: pointer; }
main { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
#preview svg { max-width: 100%; height: auto; border: 1px solid #eee; }
#stats { white-space: pre-wrap; background: #f6f6f6; padding: 1rem; }
label { display: block; margin: .4rem 0 .1rem; font-size: .85rem; }
input { padding: .3rem; width: 8rem; }
@media (max-width: 800px) { main { grid-template-columns: 1fr; } }
```

`web/forms/forest.js`:
```js
export function renderForestForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Forest plot</h2>
    <label for="effect">Effect label</label>
    <input id="effect" value="Hazard Ratio" />
    <div id="rows"></div>
    <button type="button" id="addRow">Add row</button>
    <button type="button" id="render">Render</button>`;
  const rows = container.querySelector("#rows");
  function addRow() {
    const i = rows.children.length;
    const div = document.createElement("div");
    div.innerHTML = `
      <label for="lbl${i}">Label</label><input id="lbl${i}" class="lbl" />
      <label for="est${i}">Estimate</label><input id="est${i}" class="est" />
      <label for="lo${i}">Lower</label><input id="lo${i}" class="lo" />
      <label for="hi${i}">Upper</label><input id="hi${i}" class="hi" />`;
    rows.appendChild(div);
  }
  container.querySelector("#addRow").onclick = addRow;
  container.querySelector("#render").onclick = () => {
    const spec = { figure: "forest",
      options: { effect_label: container.querySelector("#effect").value, null_line: 1 },
      rows: [...rows.children].map((d) => ({
        label: d.querySelector(".lbl").value,
        estimate: parseFloat(d.querySelector(".est").value),
        lower: parseFloat(d.querySelector(".lo").value),
        upper: parseFloat(d.querySelector(".hi").value)
      })) };
    onSubmit(spec);
  };
  addRow();
}
```

- [ ] **Step 6: Copy R into web for local dev, run smoke test**

Run:
```bash
cp -R R web/R
npm run test:e2e
```
Expected: PASS — `#preview svg` becomes visible. (First run is slow; timeout is 90s.)

- [ ] **Step 7: Commit**

```bash
git add web package.json playwright.config.js tests/e2e
git commit -m "feat: app shell, webR worker, forest plot wired end to end"
```

---

### Task 4: CONSORT flow diagram

**Files:**
- Create: `R/consort.R`
- Create: `web/forms/consort.js`
- Modify: `web/app.js` (register consort form)
- Test: `tests/testthat/test-consort.R`

**Interfaces:**
- Consumes: `.svg_string()`.
- Produces: `fig_consort(spec)` → `list(svg=, text=)`. Spec: `{"figure":"consort","nodes":[{"text":"Assessed for eligibility (n=200)"},{"text":"Randomized (n=150)"}],"exclusions":[{"text":"Excluded (n=50)"}]}`. Pure layout, no statistics; `text` echoes a plain-text disposition summary.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-consort.R`:
```r
spec <- list(figure = "consort",
  nodes = list(list(text = "Assessed (n=200)"), list(text = "Randomized (n=150)")),
  exclusions = list(list(text = "Excluded (n=50)")))

test_that("fig_consort returns an SVG with the node text", {
  out <- fig_consort(spec)
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$svg, "Randomized")
  expect_match(out$text, "Assessed")
})

test_that("fig_consort needs at least two nodes", {
  expect_error(fig_consort(list(figure = "consort", nodes = list())),
               "at least two", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `R -q -e 'devtools::test(filter = "consort")'`
Expected: FAIL — `fig_consort` not found.

- [ ] **Step 3: Write minimal implementation**

`R/consort.R`:
```r
#' CONSORT-style vertical flow diagram (boxes + arrows), pure layout.
fig_consort <- function(spec) {
  nodes <- vapply(spec$nodes, function(n) as.character(n$text), character(1))
  if (length(nodes) < 2) stop("CONSORT diagram needs at least two nodes.")
  excl <- if (length(spec$exclusions))
    vapply(spec$exclusions, function(n) as.character(n$text), character(1)) else character(0)

  n <- length(nodes)
  ys <- seq(n, 1)
  boxes <- data.frame(x = 1, y = ys, label = nodes)
  p <- ggplot2::ggplot() +
    ggplot2::geom_label(data = boxes, ggplot2::aes(x, y, label = label),
      fill = "white", label.size = 0.4, size = 3.5) +
    ggplot2::geom_segment(
      data = data.frame(x = 1, xend = 1, y = ys[-n] - 0.2, yend = ys[-1] + 0.2),
      ggplot2::aes(x, y, xend = xend, yend = yend),
      arrow = ggplot2::arrow(length = ggplot2::unit(0.15, "cm"))) +
    ggplot2::theme_void()
  if (length(excl)) {
    ex <- data.frame(x = 2, y = ys[seq_along(excl)] - 0.5, label = excl)
    p <- p + ggplot2::geom_label(data = ex, ggplot2::aes(x, y, label = label),
      fill = "grey95", size = 3) +
      ggplot2::xlim(0.5, 3)
  } else {
    p <- p + ggplot2::xlim(0.5, 1.5)
  }
  list(svg = .svg_string(p, width = 7, height = 0.9 * n + 1),
       text = paste(nodes, collapse = " -> "))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `R -q -e 'devtools::test(filter = "consort")'`
Expected: PASS (2 tests).

- [ ] **Step 5: Add the CONSORT form and register it**

`web/forms/consort.js`:
```js
export function renderConsortForm(container, onSubmit) {
  container.innerHTML = `
    <h2>CONSORT diagram</h2>
    <p>One node per line (main flow):</p>
    <textarea id="nodes" rows="6" cols="40">Assessed for eligibility (n=200)
Randomized (n=150)
Allocated to treatment (n=75)</textarea>
    <p>Exclusions (one per line, optional):</p>
    <textarea id="excl" rows="3" cols="40">Excluded (n=50)</textarea>
    <button type="button" id="render">Render</button>`;
  const lines = (id) => container.querySelector(id).value
    .split("\n").map((s) => s.trim()).filter(Boolean).map((t) => ({ text: t }));
  container.querySelector("#render").onclick = () =>
    onSubmit({ figure: "consort", nodes: lines("#nodes"), exclusions: lines("#excl") });
}
```

In `web/app.js`, extend the imports and registry:
```js
import { renderForestForm } from "./forms/forest.js";
import { renderConsortForm } from "./forms/consort.js";
const forms = { forest: renderForestForm, consort: renderConsortForm };
```

- [ ] **Step 6: Verify end to end manually, then commit**

Run: `cp -R R web/R && npm run serve` then click CONSORT → Render; confirm a diagram appears.

```bash
git add R/consort.R tests/testthat/test-consort.R web/forms/consort.js web/app.js
git commit -m "feat: CONSORT flow diagram"
```

---

### Task 5: Demographics Table 1

**Files:**
- Create: `R/table1.R`
- Create: `web/forms/table1.js`
- Modify: `web/app.js` (register table1 form)
- Test: `tests/testthat/test-table1.R`

**Interfaces:**
- Produces: `fig_table1(spec)` → `list(svg=, text=)` where for a table the `svg` field carries an **HTML** table (gtsummary → kable HTML) rather than an `<svg>`; `text` carries a tab-separated version for pasting into Word/Excel. Spec supplies already-summarized rows:
  `{"figure":"table1","groups":["Treatment","Placebo"],"rows":[{"variable":"Age, mean (SD)","values":["58 (11)","57 (12)"]},{"variable":"Male, n (%)","values":["40 (53%)","38 (51%)"]}]}`.

Note: v1 Table 1 formats summary values the writer already has (per the spec's summary-first scope). Computing Table 1 from patient-level data is a later phase.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-table1.R`:
```r
spec <- list(figure = "table1",
  groups = list("Treatment", "Placebo"),
  rows = list(
    list(variable = "Age, mean (SD)", values = list("58 (11)", "57 (12)")),
    list(variable = "Male, n (%)",    values = list("40 (53%)", "38 (51%)"))))

test_that("fig_table1 emits an HTML table and a TSV text version", {
  out <- fig_table1(spec)
  expect_match(out$svg, "<table")
  expect_match(out$svg, "Treatment")
  expect_match(out$text, "Age, mean \\(SD\\)\t58 \\(11\\)\t57 \\(12\\)")
})

test_that("fig_table1 errors when a row's value count != group count", {
  bad <- spec; bad$rows[[1]]$values <- list("58 (11)")
  expect_error(fig_table1(bad), "values", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `R -q -e 'devtools::test(filter = "table1")'`
Expected: FAIL — `fig_table1` not found.

- [ ] **Step 3: Write minimal implementation**

`R/table1.R`:
```r
#' Format a demographics "Table 1" from pre-summarized values.
fig_table1 <- function(spec) {
  groups <- vapply(spec$groups, as.character, character(1))
  g <- length(groups)
  vars <- vapply(spec$rows, function(r) as.character(r$variable), character(1))
  mat <- t(vapply(spec$rows, function(r) {
    v <- vapply(r$values, as.character, character(1))
    if (length(v) != g) stop(sprintf("Row '%s' has %d values but there are %d groups.",
                                      r$variable, length(v), g))
    v
  }, character(g)))
  df <- data.frame(Characteristic = vars, mat, check.names = FALSE,
                   stringsAsFactors = FALSE)
  colnames(df)[-1] <- groups

  html <- knitr::kable(df, format = "html", table.attr = 'class="table1"')
  tsv <- paste(apply(cbind(vars, mat), 1, paste, collapse = "\t"), collapse = "\n")
  list(svg = as.character(html), text = tsv)
}
```
(Add `knitr` to `DESCRIPTION` Imports and to the worker's `installPackages` list.)

- [ ] **Step 4: Run test to verify it passes**

Run: `R -q -e 'devtools::test(filter = "table1")'`
Expected: PASS (2 tests).

- [ ] **Step 5: Add the Table 1 form and register it**

`web/forms/table1.js`:
```js
export function renderTable1Form(container, onSubmit) {
  container.innerHTML = `
    <h2>Table 1</h2>
    <label for="groups">Group names (comma separated)</label>
    <input id="groups" value="Treatment, Placebo" style="width:20rem" />
    <p>One row per line as: <code>Variable | val1 | val2</code></p>
    <textarea id="rows" rows="6" cols="50">Age, mean (SD) | 58 (11) | 57 (12)
Male, n (%) | 40 (53%) | 38 (51%)</textarea>
    <button type="button" id="render">Render</button>`;
  container.querySelector("#render").onclick = () => {
    const groups = container.querySelector("#groups").value.split(",").map((s) => s.trim());
    const rows = container.querySelector("#rows").value.split("\n")
      .map((l) => l.trim()).filter(Boolean).map((l) => {
        const parts = l.split("|").map((s) => s.trim());
        return { variable: parts[0], values: parts.slice(1) };
      });
    onSubmit({ figure: "table1", groups, rows });
  };
}
```

In `web/app.js`:
```js
import { renderTable1Form } from "./forms/table1.js";
// add to registry: table1: renderTable1Form
```

Because Table 1 returns HTML (not SVG), the `render()` function in `app.js` already sets `preview.innerHTML = out.svg`, so HTML tables render correctly with no change.

- [ ] **Step 6: Verify manually and commit**

```bash
git add R/table1.R tests/testthat/test-table1.R web/forms/table1.js web/app.js DESCRIPTION
git commit -m "feat: demographics Table 1 formatter"
```

---

### Task 6: Kaplan-Meier curve from CSV

**Files:**
- Create: `R/km.R`
- Create: `web/forms/km.js`
- Modify: `web/app.js` (register km form)
- Test: `tests/testthat/test-km.R`

**Interfaces:**
- Consumes: `.svg_string()`.
- Produces: `fig_km(spec)` → `list(svg=, text=)`. Spec carries patient-level rows parsed from CSV in the browser:
  `{"figure":"km","data":[{"time":5,"status":1,"group":"A"}, ...],"options":{"time_label":"Months"}}`.
  Computes KM curves per group, log-rank p, and (for exactly two groups) the Cox HR. `text` is the methods/results sentence.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-km.R`:
```r
make_spec <- function() {
  set.seed(1)
  n <- 60
  grp <- rep(c("A", "B"), each = n / 2)
  time <- round(rexp(n, ifelse(grp == "A", 0.1, 0.2)), 1)
  status <- rbinom(n, 1, 0.7)
  rows <- lapply(seq_len(n), function(i)
    list(time = time[i], status = status[i], group = grp[i]))
  list(figure = "km", data = rows, options = list(time_label = "Months"))
}

test_that("fig_km returns an SVG, a log-rank p, and an HR for two groups", {
  out <- fig_km(make_spec())
  expect_true(grepl("<svg", out$svg, fixed = TRUE))
  expect_match(out$text, "log-rank")
  expect_match(out$text, "HR")
})

test_that("fig_km errors when status is not 0/1", {
  s <- make_spec(); s$data[[1]]$status <- 2
  expect_error(fig_km(s), "status", ignore.case = TRUE)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `R -q -e 'devtools::test(filter = "km")'`
Expected: FAIL — `fig_km` not found.

- [ ] **Step 3: Write minimal implementation**

`R/km.R`:
```r
#' Kaplan-Meier curve + log-rank p (+ Cox HR when exactly two groups).
fig_km <- function(spec) {
  rows <- spec$data
  if (length(rows) < 2) stop("KM needs at least two rows.")
  df <- data.frame(
    time   = vapply(rows, function(r) as.numeric(r$time), numeric(1)),
    status = vapply(rows, function(r) as.integer(r$status), integer(1)),
    group  = vapply(rows, function(r) as.character(r$group), character(1)),
    stringsAsFactors = FALSE)
  if (!all(df$status %in% c(0L, 1L))) stop("status must be 0 (censored) or 1 (event).")

  fit <- survival::survfit(survival::Surv(time, status) ~ group, data = df)
  lr  <- survival::survdiff(survival::Surv(time, status) ~ group, data = df)
  p   <- 1 - stats::pchisq(lr$chisq, length(lr$n) - 1)
  time_label <- spec$options$time_label %||% "Time"

  gg <- survminer::ggsurvplot(fit, data = df, risk.table = TRUE,
                              xlab = time_label, ylab = "Survival probability",
                              legend.title = "Group")
  plot_obj <- gg$plot

  txt <- sprintf("Log-rank p = %.3f.", p)
  if (length(unique(df$group)) == 2) {
    cox <- survival::coxph(survival::Surv(time, status) ~ group, data = df)
    hr  <- exp(stats::coef(cox))[1]
    ci  <- exp(stats::confint(cox))[1, ]
    txt <- sprintf("HR %.2f (95%% CI %.2f–%.2f); log-rank p = %.3f.",
                   hr, ci[1], ci[2], p)
  }
  list(svg = .svg_string(plot_obj, width = 7, height = 5), text = txt)
}
```
Note: the risk table is dropped from the SVG in this minimal version (only `gg$plot` is rendered). Rendering the combined curve+risk-table via `survminer::arrange_ggsurvplots` into one SVG is a refinement; capture it as a follow-up TODO in the repo issue tracker, not inline here.

- [ ] **Step 4: Run test to verify it passes**

Run: `R -q -e 'devtools::test(filter = "km")'`
Expected: PASS (2 tests).

- [ ] **Step 5: Add the KM form (CSV drop-zone) and register it**

`web/forms/km.js`:
```js
function parseCsv(text) {
  const [head, ...lines] = text.trim().split("\n");
  const cols = head.split(",").map((s) => s.trim());
  const idx = (name) => cols.indexOf(name);
  if (idx("time") < 0 || idx("status") < 0 || idx("group") < 0)
    throw new Error("CSV needs columns: time, status, group");
  return lines.filter(Boolean).map((l) => {
    const c = l.split(",");
    return { time: parseFloat(c[idx("time")]), status: parseInt(c[idx("status")], 10),
             group: c[idx("group")].trim() };
  });
}

export function renderKmForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Kaplan-Meier</h2>
    <p>Upload a CSV with columns <code>time, status, group</code> (status: 1=event, 0=censored).
       Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <label for="tlabel">Time axis label</label>
    <input id="tlabel" value="Months" />
    <button type="button" id="render" disabled>Render</button>`;
  let data = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files[0];
    const reader = new FileReader();
    reader.onload = () => {
      try { data = parseCsv(reader.result); btn.disabled = false; }
      catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(file);
  };
  btn.onclick = () => onSubmit({ figure: "km", data,
    options: { time_label: container.querySelector("#tlabel").value } });
}
```

In `web/app.js`:
```js
import { renderKmForm } from "./forms/km.js";
// add to registry: km: renderKmForm
```

- [ ] **Step 6: Extend the smoke test with KM (optional but recommended)**

Add to `tests/e2e/smoke.spec.js` a test that uploads a small fixture CSV (`tests/e2e/fixtures/km.csv`) and asserts `#preview svg` visible. Create the fixture with ~20 rows across two groups.

- [ ] **Step 7: Commit**

```bash
git add R/km.R tests/testthat/test-km.R web/forms/km.js web/app.js tests/e2e
git commit -m "feat: Kaplan-Meier curve from client-side CSV"
```

---

### Task 7: Journal theme presets

**Files:**
- Create: `R/themes.R`
- Modify: `R/forest.R`, `R/km.R`, `R/consort.R` (apply selected theme)
- Modify: `web/forms/forest.js`, `web/forms/km.js`, `web/forms/consort.js` (theme dropdown)
- Test: `tests/testthat/test-themes.R`

**Interfaces:**
- Produces: `.fig_theme(name)` → a ggplot2 theme object. Names: `"generic"` (default), `"nejm"`, `"jama"`. Selected via `spec$options$theme`.

- [ ] **Step 1: Write the failing test**

`tests/testthat/test-themes.R`:
```r
test_that(".fig_theme returns a ggplot theme for known names and falls back", {
  expect_s3_class(.fig_theme("nejm"), "theme")
  expect_s3_class(.fig_theme("generic"), "theme")
  expect_s3_class(.fig_theme("unknown-name"), "theme")  # falls back, no error
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `R -q -e 'devtools::test(filter = "themes")'`
Expected: FAIL — `.fig_theme` not found.

- [ ] **Step 3: Write minimal implementation**

`R/themes.R`:
```r
#' Return a ggplot2 theme for a named journal preset (falls back to generic).
.fig_theme <- function(name = "generic") {
  base <- ggplot2::theme_minimal(base_size = 12)
  switch(as.character(name),
    nejm = base + ggplot2::theme(
      text = ggplot2::element_text(family = "sans"),
      panel.grid.minor = ggplot2::element_blank(),
      axis.line = ggplot2::element_line(colour = "black")),
    jama = base + ggplot2::theme(
      panel.grid.major.x = ggplot2::element_blank(),
      panel.grid.minor = ggplot2::element_blank()),
    base
  )
}
```

Then in `R/forest.R` replace `ggplot2::theme_minimal(base_size = 12)` with `.fig_theme(spec$options$theme)`. In `R/km.R`, add `plot_obj <- plot_obj + .fig_theme(spec$options$theme)`. In `R/consort.R` leave `theme_void()` (a flow diagram has no axes to theme).

- [ ] **Step 4: Run test to verify it passes**

Run: `R -q -e 'devtools::test()'`
Expected: PASS (all suites, including unchanged forest/km tests).

- [ ] **Step 5: Add theme dropdown to forms**

In each of `forms/forest.js` and `forms/km.js`, add before the render button:
```html
<label for="theme">Journal style</label>
<select id="theme"><option value="generic">Generic</option>
<option value="nejm">NEJM</option><option value="jama">JAMA</option></select>
```
and include `theme: container.querySelector("#theme").value` in each spec's `options`.

- [ ] **Step 6: Verify and commit**

```bash
git add R/themes.R R/forest.R R/km.R tests/testthat/test-themes.R web/forms
git commit -m "feat: journal theme presets"
```

---

### Task 8: CI and GitHub Pages deploy

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/deploy.yml`
- Create: `README.md`

**Interfaces:**
- CI runs R tests on push. Deploy copies `R/` into `web/R/` and publishes `web/` to GitHub Pages.

- [ ] **Step 1: Write the CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  r-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: r-lib/actions/setup-r@v2
      - uses: r-lib/actions/setup-r-dependencies@v2
        with: { extra-packages: any::testthat, local::. }
      - run: R -q -e 'devtools::test(stop_on_failure = TRUE)'
```

- [ ] **Step 2: Write the deploy workflow**

`.github/workflows/deploy.yml`:
```yaml
name: Deploy
on:
  push: { branches: [main] }
permissions: { contents: read, pages: write, id-token: write }
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    environment: { name: github-pages, url: "${{ steps.deploy.outputs.page_url }}" }
    steps:
      - uses: actions/checkout@v4
      - run: cp -R R web/R
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with: { path: web }
      - id: deploy
        uses: actions/deploy-pages@v4
```

- [ ] **Step 3: Write the README**

`README.md`:
```markdown
# Clinical Manuscript Figures

Free, open-source, browser-based clinical figures for journal manuscripts —
forest plots, CONSORT diagrams, Table 1, and Kaplan-Meier curves — rendered by
real R (ggplot2, survival, gtsummary) via [webR](https://docs.r-wasm.org/webr/).

**Your data never leaves your browser.** There is no server; all computation
runs client-side in WebAssembly.

## Develop

- R functions live in `R/` and are testable in plain R: `R -q -e 'devtools::test()'`
- The static site is in `web/`. For local dev: `cp -R R web/R && npm run serve`
- End-to-end: `npm run test:e2e`

## Live site

Published via GitHub Pages from `web/` on every push to `main`.
```

- [ ] **Step 4: Verify CI locally, then commit**

Run: `R -q -e 'devtools::test(stop_on_failure = TRUE)'`
Expected: PASS across all suites.

```bash
git add .github README.md
git commit -m "ci: R tests and GitHub Pages deploy"
```

- [ ] **Step 5: Enable Pages**

In GitHub repo settings → Pages → Source: "GitHub Actions". Push to `main` and confirm the deployed URL renders the forest plot.

---

## Self-Review Notes

- **Spec coverage:** Forest (T2), CONSORT (T4), Table 1 (T5), KM (T6) all present. Copyable stats text: every `fig_*` returns `text`. Journal presets: T7. Zero-data / static / no-backend: enforced by architecture, verified by absence of network calls. Testing (unit + statistical-correctness + one E2E): T2–T8. Error handling in plain language: each `fig_*` uses `stop()` with human messages, surfaced by `render()` in `app.js`.
- **Deferred (documented, not silently dropped):** KM risk-table in the combined SVG (T6 note → repo issue); PNG export (svglite gives SVG; browser can rasterize SVG→PNG later); patient-level Table 1 (spec marks this a later phase).
- **Type consistency:** `render_figure` → `fig_<name>(spec)` → `list(svg=, text=)` uniform across all figures; `runFigure(spec)`/`render()` bridge unchanged across tasks; form registry keys (`forest`/`consort`/`table1`/`km`) match `data-figure` attributes in `index.html`.

# KM Analyze-Form Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild KM's Analyze Your Data form on the shared csv/columnpicker foundation: CSV help, example-CSV download, column mapping, an event-value picker replacing the 0/1 requirement, and progressive disclosure.

**Architecture:** A pure spec builder (`web/guided/km/spec.js`) projects mapped columns to the `{time, status, group}` rows `fig_km` already accepts (status recoded 0/1 from a user-confirmed event value) — no R statistical change. The form (`web/guided/km/analyze-form.js`) clones Group comparison's progressive-disclosure pattern. `.km_script` (R) learns `options.source_roles` so a mapped upload's downloadable script uses the real column names and event coding. The old fixed-column parser (`web/forms/km.js`) is deleted.

**Tech Stack:** Vanilla JS modules (`web/lib/csv.js`, `web/lib/columnpicker.js`), plain-Node unit tests, R/testthat, Playwright.

**Spec:** `docs/superpowers/specs/2026-07-16-km-analyze-form-design.md`

## Global Constraints

- **WARN 0 hard gate** for R: `Rscript -e 'devtools::test()'` must read `[ FAIL 0 | WARN 0 | ... ]`; never `testthat::test_file()`.
- **No R statistical change**: `fig_km`'s inputs, outputs, and demo behavior are untouched; only `.km_script`'s generated prep text changes.
- **No-egress**: only mapped columns cross to the worker; only the file *name* travels (`options.source_filename`); example CSV is a client-side Blob.
- **Event coding is confirmed, never inferred**: the user picks the event value from the status column's distinct values; all other values are censored.
- JS unit: `npm run test:unit` (plain Node asserts, files enumerated in package.json). E2E: `rm -rf web/R && cp -R R web/R && npm run test:e2e`.
- The shell calls `renderAnalyzeForm(container, onSubmit)` — the new form keeps that signature (with the optional trailing `doc` test seam the other forms have).
- Commit after every task.

---

### Task 1: Pure spec builder (`web/guided/km/spec.js`)

**Files:**
- Create: `web/guided/km/spec.js`
- Create: `web/guided/km/spec.test.mjs`
- Modify: `package.json:7` (append the new test file to `test:unit`)

**Interfaces:**
- Consumes: nothing new (plain data in).
- Produces (Task 2 depends on these exact signatures):
  - `buildKmSpec(table, roles, eventValue, options)` → `{ spec, dropped }` where `table` is `parseCsv` output (`{columns, rows, types}`), `roles` is `{time, status, group}` (column names), `eventValue` is a string, `options` is `{time_label, theme, source_filename}`. `spec` is a complete fig_km spec; `dropped` is the count of rows excluded for blank values.
  - `distinctValues(table, col)` → array of distinct non-blank cell strings in first-appearance order.

- [ ] **Step 1: Write the failing tests**

Create `web/guided/km/spec.test.mjs`:

```js
// Pure KM spec assembly: event-value coding, blank-row drops, no-egress projection.
import assert from "node:assert";
import { buildKmSpec, distinctValues } from "./spec.js";

const table = {
  columns: ["id", "followup_months", "vital", "arm"],
  rows: [
    { id: "P1", followup_months: "5.2", vital: "Death", arm: "A" },
    { id: "P2", followup_months: "8.1", vital: "Censored", arm: "A" },
    { id: "P3", followup_months: "", vital: "Death", arm: "B" },      // blank time -> dropped
    { id: "P4", followup_months: "12.4", vital: "Death", arm: "B" },
  ],
  types: { id: "categorical", followup_months: "numeric",
           vital: "categorical", arm: "categorical" },
};
const roles = { time: "followup_months", status: "vital", group: "arm" };

{ // event coding + projection + drop count + passthrough
  const { spec, dropped } = buildKmSpec(table, roles, "Death",
    { time_label: "Months", theme: "generic", source_filename: "trial.csv" });
  assert.equal(dropped, 1);
  assert.equal(spec.figure, "km");
  assert.equal(spec.data.length, 3);
  assert.deepEqual(spec.data[0], { time: 5.2, status: 1, group: "A" });
  assert.deepEqual(spec.data[1], { time: 8.1, status: 0, group: "A" });
  // no-egress: only the three projected keys cross (id never does)
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["group", "status", "time"]);
  assert.equal(spec.options.time_label, "Months");
  assert.equal(spec.options.theme, "generic");
  assert.equal(spec.options.source_filename, "trial.csv");
  assert.deepEqual(spec.options.source_roles,
    { time: "followup_months", status: "vital", group: "arm", event: "Death" });
}

{ // numeric 1/0 coding works through the same picker path
  const t2 = { ...table, rows: [
    { followup_months: "3", vital: "1", arm: "A" },
    { followup_months: "4", vital: "0", arm: "A" },
  ]};
  const { spec, dropped } = buildKmSpec(t2, roles, "1",
    { time_label: "Months", theme: "generic" });
  assert.equal(dropped, 0);
  assert.deepEqual(spec.data.map((r) => r.status), [1, 0]);
  assert.equal(spec.options.source_filename, null);   // absent -> null (embed signal)
}

{ // distinctValues: first-appearance order, blanks skipped
  assert.deepEqual(distinctValues(table, "vital"), ["Death", "Censored"]);
  const t3 = { rows: [{ v: "" }, { v: "x" }, { v: "x" }, { v: " " }] };
  assert.deepEqual(distinctValues(t3, "v"), ["x"]);
}

console.log("spec.test.mjs (km) OK");
```

- [ ] **Step 2: Run to verify it fails**

Run: `node web/guided/km/spec.test.mjs`
Expected: FAIL — `Cannot find module '.../web/guided/km/spec.js'`.

- [ ] **Step 3: Implement `web/guided/km/spec.js`**

```js
// Pure spec assembly for Kaplan–Meier. Rows are projected to the mapped
// time/status/group columns only (no other column crosses to the worker),
// and status is recoded 0/1 from the user-confirmed event value — the spec
// that leaves here is exactly the shape fig_km has always accepted.
export function buildKmSpec(table, roles, eventValue, options) {
  const blank = (v) => v == null || String(v).trim() === "";
  const data = [];
  let dropped = 0;
  for (const r of table.rows) {
    const t = r[roles.time], s = r[roles.status], g = r[roles.group];
    if (blank(t) || blank(s) || blank(g)) { dropped++; continue; }
    data.push({ time: Number(t),
                status: String(s) === String(eventValue) ? 1 : 0,
                group: String(g) });
  }
  return { dropped, spec: {
    figure: "km",
    data,
    options: {
      time_label: options.time_label,
      theme: options.theme,
      source_filename: options.source_filename ?? null,
      // Carried for the downloadable R script: lets .km_script write prep
      // that reads the user's REAL column names and event coding.
      source_roles: { time: roles.time, status: roles.status,
                      group: roles.group, event: String(eventValue) },
    },
  } };
}

// Distinct non-blank values of one column, first-appearance order — feeds
// the event-value picker.
export function distinctValues(table, col) {
  const seen = [];
  for (const r of table.rows) {
    const v = r[col];
    if (v == null || String(v).trim() === "") continue;
    const s = String(v);
    if (!seen.includes(s)) seen.push(s);
  }
  return seen;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `node web/guided/km/spec.test.mjs`
Expected: `spec.test.mjs (km) OK`

- [ ] **Step 5: Register the test file**

In `package.json` line 7, inside the `test:unit` command, insert `node web/guided/km/spec.test.mjs && ` immediately after `node web/guided/km/demo.test.mjs && `. Run `npm run test:unit` — all pass (the old `web/forms/km.test.mjs` still runs; it is removed in Task 2).

- [ ] **Step 6: Commit**

```bash
git add web/guided/km/spec.js web/guided/km/spec.test.mjs package.json
git commit -m "feat(km): pure spec builder — column mapping + event-value 0/1 coding"
```

---

### Task 2: Analyze form + retire the fixed-column parser

**Files:**
- Create: `web/guided/km/analyze-form.js`
- Modify: `web/guided/guided-analysis.js:9` (import) and `:48` (registration)
- Modify: `package.json:7` (remove `node web/forms/km.test.mjs && `)
- Delete: `web/forms/km.js`, `web/forms/km.test.mjs`

**Interfaces:**
- Consumes: `buildKmSpec`, `distinctValues` (Task 1); `parseCsv`, `toCsv` from `web/lib/csv.js`; `renderColumnPicker(container, roles, table, onReady, doc)` from `web/lib/columnpicker.js` (roles: `[{key, label, type}]`, types `"numeric" | "any" | "categorical+"`; onReady fires synchronously — including once immediately with `null` — and on every dropdown change with `{time, status, group}` or `null`; option select ids are `#cp_<key>`).
- Produces: `renderKmAnalyzeForm(container, onSubmit, doc = globalThis.document)` — registered as the shell's `renderAnalyzeForm`. DOM ids Task 4's e2e relies on: `#csv`, `#example-csv` (download `example-survival.csv`), `#km-config`, `#cp_time`, `#cp_status`, `#cp_group`, `#km-event`, `#km-render`, `#km-dropped-note`, `#tlabel`, `#theme`.

- [ ] **Step 1: Implement `web/guided/km/analyze-form.js`**

(No isolated unit test — the logic lives in the Task-1 builder; the form is covered by the Task-4 e2e, matching how the groupcompare form is tested.)

```js
// web/guided/km/analyze-form.js
// Progressive-disclosure upload UI for KM, on the shared csv/columnpicker
// foundation. Pre-upload: heading + privacy line + CSV help + file input ONLY.
// The config (role mapping, event-value picker, options, Render) stays hidden
// until a parse succeeds; a parse failure re-hides it and clears state.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildKmSpec, distinctValues } from "./spec.js";
import { KM_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(KM_DEMO.rows, KM_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderKmAnalyzeForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A numeric follow-up time column, in consistent units (e.g. months).</li>
        <li>A status column where one value marks the event — any coding
          (<code>Death</code>/<code>Censored</code>, <code>1</code>/<code>0</code>, …);
          you confirm which value is the event below.</li>
        <li>A column naming each participant's group or arm.</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-survival.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="km-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#km-config");
  let table = null, roles = null, fileName = null;

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
        fileName = file.name;
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);

        // Event-value picker + Render are created BEFORE renderColumnPicker
        // runs: its onReady callback fires synchronously (including once
        // immediately with null), so everything it touches must exist.
        const eventLabel = doc.createElement("label");
        eventLabel.textContent =
          "Which value of the status column means the event occurred? ";
        const eventSel = doc.createElement("select");
        eventSel.id = "km-event";
        eventLabel.htmlFor = "km-event";
        const eventHint = doc.createElement("p");
        eventHint.className = "hint";
        eventHint.textContent = "All other values count as censored.";

        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "km-render";
        btn.textContent = "Render Kaplan–Meier curve";
        btn.disabled = true;
        const note = doc.createElement("p");
        note.id = "km-dropped-note"; note.className = "hint";

        let statusCol = null;
        const syncReady = () => { btn.disabled = !roles || !eventSel.value; };
        const fillEventOptions = () => {
          eventSel.innerHTML = "";
          const ph = doc.createElement("option");
          ph.value = ""; ph.textContent = "— choose —";
          eventSel.appendChild(ph);
          if (statusCol) for (const v of distinctValues(table, statusCol)) {
            const o = doc.createElement("option");
            o.value = v; o.textContent = v;
            eventSel.appendChild(o);
          }
          eventSel.disabled = !statusCol;
          syncReady();
        };
        renderColumnPicker(pick,
          [{ key: "time", label: "Follow-up time", type: "numeric" },
           { key: "status", label: "Event status", type: "any" },
           { key: "group", label: "Group / arm", type: "categorical+" }],
          table, (v) => {
            roles = v;
            const s = v ? v.status : null;
            if (s !== statusCol) { statusCol = s; fillEventOptions(); }
            else syncReady();
          }, doc);
        eventSel.onchange = syncReady;
        fillEventOptions();

        const mkText = (id, label, value) => {
          const l = doc.createElement("label"); l.textContent = label + " ";
          const inp = doc.createElement("input"); inp.id = id; inp.value = value;
          l.appendChild(inp); config.appendChild(l); return inp;
        };
        const mkSel = (id, label, choices) => {
          const l = doc.createElement("label"); l.textContent = label + " ";
          const s = doc.createElement("select"); s.id = id;
          for (const [val, txt] of choices) {
            const o = doc.createElement("option");
            o.value = val; o.textContent = txt;
            s.appendChild(o);
          }
          l.appendChild(s); config.appendChild(l); return s;
        };
        config.appendChild(eventLabel);
        eventLabel.appendChild(eventSel);
        config.appendChild(eventHint);
        const tlabel = mkText("tlabel", "Time axis label", "Months");
        const themeSel = mkSel("theme", "Journal style",
          [["generic", "Generic"], ["nejm", "NEJM"], ["jama", "JAMA"]]);

        btn.onclick = () => {
          if (!roles || !eventSel.value) return;
          const { spec, dropped } = buildKmSpec(table, roles, eventSel.value,
            { time_label: tlabel.value, theme: themeSel.value,
              source_filename: fileName });
          note.textContent = dropped > 0
            ? `${dropped} row(s) with missing values excluded.` : "";
          onSubmit(spec);
        };
        config.appendChild(btn);
        config.appendChild(note);
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

- [ ] **Step 2: Wire it in and delete the old form**

In `web/guided/guided-analysis.js`, change line 9 from

```js
import { renderKmForm } from "../forms/km.js";
```

to

```js
import { renderKmAnalyzeForm } from "./km/analyze-form.js";
```

and the registration (line ~48) from `renderAnalyzeForm: renderKmForm,` to `renderAnalyzeForm: renderKmAnalyzeForm,`. Then:

```bash
git rm web/forms/km.js web/forms/km.test.mjs
```

In `package.json` line 7, remove the segment `node web/forms/km.test.mjs && `.

- [ ] **Step 3: Run unit tests and grep for stragglers**

Run: `npm run test:unit` — all pass, no reference to the deleted file.
Run: `grep -rn "forms/km" web tests` — expected: no matches (Task 4 owns the e2e updates; if an e2e match appears here, leave it for Task 4).

- [ ] **Step 4: Browser smoke check**

`rm -rf web/R && cp -R R web/R && npm run serve` (port 8321; if "address already in use", a dev server is already up — reuse it). Headless browser at `~/.claude/skills/gstack/browse/dist/browse`:

```bash
B=~/.claude/skills/gstack/browse/dist/browse
$B goto http://localhost:8321
$B click '[data-figure="km"]'
$B js "document.querySelector('[id=tab-analyze]').click()"
$B is visible "#example-csv"        # example download offered
$B is hidden "#km-config"           # progressive reveal: nothing before upload
$B screenshot /tmp/km-analyze.png   # visual sanity
```

Expected: help + file input only; config hidden. (Full upload flow is Task 4's e2e.)

- [ ] **Step 5: Commit**

```bash
git add web/guided/km/analyze-form.js web/guided/guided-analysis.js package.json
git commit -m "feat(km): guided analyze form — csv help, example download, mapping, event picker"
```

---

### Task 3: `.km_script` honors `source_roles`

**Files:**
- Modify: `R/km.R` (`.km_script`, the `prep <- c(...)` block at ~line 204)
- Test: `tests/testthat/test-km.R` (append)

**Interfaces:**
- Consumes: `spec$options$source_roles` — `list(time=, status=, group=, event=)`, present only for mapped uploads (Task 1 sets it; demo specs never do).
- Produces: generated scripts whose prep reads the user's real columns. No change to `fig_km` statistics or to the no-roles prep.

- [ ] **Step 1: Write the failing tests**

Append to `tests/testthat/test-km.R` (reuses the file's existing `km_script_spec(...)` helper, which forwards `...` into `options`):

```r
test_that("km script prep honors source_roles from a mapped upload", {
  out <- fig_km(km_script_spec(
    source_filename = "trial.csv",
    source_roles = list(time = "followup_months", status = "vital",
                        group = "arm", event = "Death")))
  expect_match(out$code, 'as.numeric(df[["followup_months"]])', fixed = TRUE)
  expect_match(out$code, 'as.integer(df[["vital"]] == "Death")', fixed = TRUE)
  expect_match(out$code, 'as.character(df[["arm"]])', fixed = TRUE)
  expect_match(out$code, "every other value counts as censored", fixed = TRUE)
  expect_silent(parse(text = out$code))
})

test_that("km script without source_roles keeps the fixed prep", {
  out <- fig_km(km_script_spec())
  expect_match(out$code, "as.numeric(df$time)", fixed = TRUE)
  expect_false(grepl("source_roles", out$code, fixed = TRUE))
})
```

- [ ] **Step 2: Run to verify the first fails**

Run: `Rscript -e 'devtools::test(filter = "km")'`
Expected: the mapped-upload test FAILS (`df[["followup_months"]]` not found in code); the fixed-prep test passes already.

- [ ] **Step 3: Implement**

In `R/km.R` `.km_script`, replace the current `prep <- c(...)` block:

```r
  prep <- c(
    "dat <- data.frame(time = as.numeric(df$time),",
    "                  status = as.integer(df$status),",
    "                  group  = as.character(df$group),",
    "                  stringsAsFactors = FALSE)",
    if (!is.null(opts$reference))
      sprintf('dat$group <- relevel(factor(dat$group), ref = "%s")',
              qe(opts$reference)),
    "")
```

with:

```r
  # Mapped uploads carry source_roles: the script must read the user's REAL
  # column names and event coding, not the app-internal time/status/group.
  sr <- opts$source_roles
  prep <- c(
    if (!is.null(sr)) c(
      sprintf('# Event coding confirmed in the app: %s == "%s" marks the event;',
              qe(sr$status), qe(sr$event)),
      "# every other value counts as censored.",
      sprintf('dat <- data.frame(time = as.numeric(df[["%s"]]),', qe(sr$time)),
      sprintf('                  status = as.integer(df[["%s"]] == "%s"),',
              qe(sr$status), qe(sr$event)),
      sprintf('                  group  = as.character(df[["%s"]]),', qe(sr$group)),
      "                  stringsAsFactors = FALSE)",
      "# blank cells were excluded in the app; NA rows are excluded here too",
      "dat <- dat[!is.na(dat$time) & !is.na(dat$status) & !is.na(dat$group), ]"
    ) else c(
      "dat <- data.frame(time = as.numeric(df$time),",
      "                  status = as.integer(df$status),",
      "                  group  = as.character(df$group),",
      "                  stringsAsFactors = FALSE)"),
    if (!is.null(opts$reference))
      sprintf('dat$group <- relevel(factor(dat$group), ref = "%s")',
              qe(opts$reference)),
    "")
```

- [ ] **Step 4: Run to verify green, then the full suite**

Run: `Rscript -e 'devtools::test(filter = "km")'` — all pass, WARN 0.
Run: `Rscript -e 'devtools::test()'` — `[ FAIL 0 | WARN 0 | ... ]`.

- [ ] **Step 5: Commit**

```bash
git add R/km.R tests/testthat/test-km.R
git commit -m "feat(km): downloadable script reads mapped column names and event coding"
```

---

### Task 4: E2E migration + docs + full verification

**Files:**
- Modify: `tests/e2e/fixtures/km.csv` (realistic headers/coding)
- Modify: `tests/e2e/km-guided.spec.js` (analyze flow + new help test)
- Modify: `CLAUDE.md` (Input paragraph: KM no longer has its own parser)

**Interfaces:**
- Consumes: form DOM ids from Task 2 (`#csv`, `#example-csv`, `#km-config`, `#cp_time`, `#cp_status`, `#cp_group`, `#km-event`, `#km-render`).
- Produces: the e2e gate for the new workflow.

- [ ] **Step 1: Convert the fixture**

```bash
awk -F, 'NR==1 { print "followup_months,status,group"; next }
         { print $1 "," ($2 == "1" ? "Death" : "Censored") "," $3 }' \
  tests/e2e/fixtures/km.csv > /tmp/km-fixture.csv && mv /tmp/km-fixture.csv tests/e2e/fixtures/km.csv
head -3 tests/e2e/fixtures/km.csv
```

Expected head: `followup_months,status,group` then rows like `5.2,Death,A`.

- [ ] **Step 2: Update the analyze steps in `tests/e2e/km-guided.spec.js`**

In the test `"demo and user results are separate contexts"`, replace:

```js
  await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
  await page.getByRole("button", { name: /render/i }).click();
```

with:

```js
  await page.locator("#csv").setInputFiles(path.join(__dirname, "fixtures", "km.csv"));
  await expect(page.locator("#km-config")).toBeVisible();       // progressive reveal
  await page.locator("#cp_time").selectOption("followup_months");
  await page.locator("#cp_status").selectOption("status");
  await page.locator("#cp_group").selectOption("group");
  await page.locator("#km-event").selectOption("Death");
  await page.getByRole("button", { name: /render/i }).click();
```

Also grep the file for any other `#csv` / old-form assumptions (`grep -n "csv\|tlabel\|render" tests/e2e/km-guided.spec.js`) and apply the same mapping steps wherever the old two-line upload+render idiom appears.

- [ ] **Step 3: Append the help/download test**

```js
test("Analyze tab explains the CSV and offers the example download", async ({ page }) => {
  await page.goto("/#km/analyze");
  await page.getByRole("button", { name: /kaplan-meier/i }).click();
  await expect(page.getByText("What your CSV should look like")).toBeVisible();
  await expect(page.locator("#example-csv")).toHaveAttribute("download", "example-survival.csv");
  const href = await page.locator("#example-csv").getAttribute("href");
  expect(href).toMatch(/^blob:/);                     // client-side Blob — no egress
  await expect(page.locator("#km-config")).toBeHidden();  // nothing before a file
});
```

- [ ] **Step 4: Run the full e2e suite**

Run: `rm -rf web/R && cp -R R web/R && npm run test:e2e`
Expected: all pass (KM's first run downloads survival — slow; existing timeouts cover it).

- [ ] **Step 5: Update CLAUDE.md**

In the Architecture → Input paragraph, replace the parenthetical

```
(KM predates `web/lib` and keeps its own fixed-column parser in `web/forms/km.js`; Summary builds on the shared `csv.js` foundation.)
```

with

```
(All four analyses build on the shared `csv.js` foundation; KM's analyze form maps arbitrary columns to time/status/group roles with a user-confirmed event value in `web/guided/km/{analyze-form,spec}.js`.)
```

- [ ] **Step 6: Full verification and commit**

```bash
Rscript -e 'devtools::test()'    # [ FAIL 0 | WARN 0 | ... ]
npm run test:unit                # all pass
git add tests/e2e/fixtures/km.csv tests/e2e/km-guided.spec.js CLAUDE.md
git commit -m "test(e2e): KM analyze flow via mapping + event picker; docs updated"
```

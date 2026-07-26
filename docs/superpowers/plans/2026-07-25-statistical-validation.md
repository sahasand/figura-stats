# Statistical Validation by Independent Double Programming — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove Figura's numbers are correct by re-deriving every reported statistic in an independently programmed Python implementation and publishing the comparison, so a clinical user can answer "do these numbers match R/SAS?" from evidence rather than assurance.

**Architecture:** Two independent paths compute the same statistics from the same raw CSV. **Path A** is Figura as shipped: the real `web/lib/csv.js` parser and the real `web/guided/*/spec.js` builders turn the CSV into a spec, and `render_figure()` produces the displayed table. **Path B** is a Python implementation written from a prose analysis spec by an implementer who has not read `R/`. A comparator checks Path B against Path A at display precision and, for adjusted model estimates, at full precision via the `.R` script Figura itself exports. Findings are dispositioned the way the HF-1002 QC closure memo dispositions them (real defect / display artifact / accepted difference) and rendered into a self-contained scorecard from precomputed JSON.

**Tech Stack:** Node (ESM, no framework — matches the existing `*.test.mjs` convention), R + testthat, Python 3.11 in a project-local venv (pandas, numpy, scipy, statsmodels, lifelines), Playwright for the optional webR tier.

## Global Constraints

- **Independence is the product.** The Python implementation MUST be written only from the prose spec in `validation/spec/<case>.md`. The implementer MUST NOT read `R/*.R`, `web/guided/**`, or any Path A output before their code passes its own unit tests. Two implementations of one reading is not double programming; it is a port that reproduces the same misreading. When executing this plan with subagents, dispatch each Python task to a fresh subagent and state this prohibition in its prompt.
- **`validation/` never ships to `web/`.** It is a development and evidence directory. The only artifact that reaches users is the generated `web/validation.html` in Task 13. The no-egress invariant is unaffected: nothing here runs in the browser except the existing app.
- **No new runtime dependency.** `DESCRIPTION` Imports stay exactly `ggplot2, survival, cowplot, svglite, jsonlite, grDevices, stats`. Python is a development-time dependency only and never enters `web/` or `worker.js` `EXTRA_PACKAGES`.
- **R suite gate:** `Rscript -e 'devtools::test()'` must report `[ FAIL 0 | WARN 0 | ... ]`. Never `testthat::test_file()`.
- **JS unit gate:** every new `*.test.mjs` must be appended to the `test:unit` chain in `package.json` **in the same commit that creates it** — the chain is hand-maintained, not a glob, and an unlisted test silently never runs.
- **Python gate:** `validation/.venv/bin/python -m pytest validation/python -q` exits 0.
- **Do not modify any file under `R/` or `web/` in Tasks 1 through 12.** If validation finds a defect, write it up under `.scratch/statistical-validation/issues/NN-<slug>.md` per `docs/agents/issue-tracker.md` and keep going. Fixing a defect in the same commit that discovers it destroys the evidence that the harness caught it.
- **Anaconda hijacks builds on this Mac.** Always create and invoke the venv explicitly (`validation/.venv/bin/python`), never a bare `python3`, and never `conda activate`.
- **Numeric tolerance:** relative `1e-6` with an absolute floor of `1e-9`, matching the HF-1002 standard ("continuous stats agreed within 1e-6 on unrounded values").
- **Pinned conventions** (these are declared choices, not bugs; Python must adopt them exactly):
  - Wald CI uses the literal constant `1.96`, not `qnorm(0.975)` (= 1.959964). A 1.96-vs-1.959964 mismatch moves the third decimal of a CI.
  - Sample SD (denominator `n − 1`): R `stats::sd`, Python `numpy.std(ddof=1)`.
  - Quantiles: R `type = 7`, Python `numpy.quantile(method="linear")`. These agree by definition.
  - Skewness: population `g1` (biased). R's `.skewness` divides by `sqrt(mean((x-m)^2))`; Python `scipy.stats.skew(x, bias=True)`.
  - Two-sample t: **Welch** (R `t.test` defaults `var.equal = FALSE`; Python `scipy.stats.ttest_ind` defaults `equal_var = True` and MUST be passed `equal_var=False`). This default flips between the two languages and will produce false findings if left alone.
  - Cox ties: **Efron** (R `survival::coxph` default; lifelines default). SAS `PROC PHREG` defaults to Breslow — do not use SAS output as a reference for Cox without setting `TIES=EFRON`.
  - Chi-square: **no continuity correction** (`correct = FALSE`); Python `scipy.stats.chi2_contingency(correction=False)`. Fisher's exact is substituted when any expected cell count is `< 5`.
  - Categorical covariate coding: treatment contrasts with the declared reference level first and the remaining levels in **alphabetical** order (R's `relevel(factor(x), ref = …)`).
  - Complete cases: a row is dropped if the outcome or **any** selected covariate is `NA` or an empty string. Blank cells are missing, never a category.
  - Display rule for ratio cells: `sprintf("%.2f (%.2f–%.2f, %s)", est, lo, hi, pf)` where `pf` is `"p<0.001"` when `p < 0.001` else `sprintf("p=%.3f", p)`. The separator is an en-dash `–` (U+2013), not a hyphen.
  - Display rule for continuous summaries: `signif(v, 3)` with trailing zeros dropped; `"M ± SD"` or `"Q2 (Q1–Q3)"`.

---

## File Structure

```
validation/
  README.md                          how to run, how to read the scorecard
  requirements.txt                   pinned Python deps
  cases/
    <case-id>/
      data.csv                       raw input, the only shared input between paths
      case.json                      machine-readable roles/options/tolerances
  spec/
    <case-id>.md                     prose analysis spec (the SAP analogue)
  harness/
    build-spec.mjs                   raw CSV -> Figura spec JSON via SHIPPED js
    build-spec.test.mjs              unit test for the above
    run-figura.R                     spec JSON -> render_figure() -> results JSON
    run-script.R                     runs Figura's exported .R -> full-precision JSON
    parse-cells.mjs                  TSV cell parser + Figura display formatter
    parse-cells.test.mjs             unit test for the above
  python/
    validate/
      __init__.py
      io.py                          CSV load, event coding, complete cases
      logistic.py  cox.py  km.py  groupcompare.py  summary.py
      cli.py                         case id -> results JSON
    tests/
      test_io.py  test_logistic.py  test_cox.py  test_km.py
      test_groupcompare.py  test_summary.py
  compare/
    compare.py                       Path A vs Path B, tolerance + disposition
    tests/test_compare.py
  build_scorecard.py                 findings JSON -> self-contained HTML
  results/                           generated, git-tracked (it is the evidence)
    <case-id>.figura.json
    <case-id>.figura-exact.json
    <case-id>.python.json
    findings.json
    scorecard.html
```

Each `validation/python/validate/<analysis>.py` owns one analysis end to end and depends only on `io.py`. Files that change together live together: a new analysis adds one Python module, one prose spec, one case directory, and one comparator entry, and touches nothing else.

---

### Task 1: Case format and the first case (logistic)

**Files:**
- Create: `validation/cases/logistic-confounding/data.csv`
- Create: `validation/cases/logistic-confounding/case.json`
- Create: `validation/spec/logistic-confounding.md`
- Create: `validation/README.md`

**Interfaces:**
- Produces: the `case.json` schema every later task reads — keys `id`, `figure`, `roles`, `options`, `display`, `exact_targets`.

- [ ] **Step 1: Copy the existing demo fixture as the first case's raw data**

```bash
mkdir -p validation/cases/logistic-confounding
cp tests/testthat/fixtures/logistic-demo.csv validation/cases/logistic-confounding/data.csv
head -3 validation/cases/logistic-confounding/data.csv
```

This fixture already encodes a known confounding story (crude arm OR ≈ 1.02 flipping to adjusted ≈ 0.50), so a validation failure has a recognisable clinical meaning rather than being an abstract number mismatch.

- [ ] **Step 2: Write `case.json`**

```json
{
  "id": "logistic-confounding",
  "figure": "logistic",
  "roles": { "outcome": "response", "covariates": ["arm", "age", "stage"] },
  "options": {
    "event_value": "Yes",
    "ref_levels": { "arm": "Control", "stage": "I" },
    "increments": { "age": 10 }
  },
  "display": { "kind": "ratio_table" },
  "exact_targets": ["adjusted_or", "adjusted_ci", "adjusted_p", "n", "n_event", "n_dropped"]
}
```

Verify the column names and the event value against the real file before committing:

```bash
head -1 validation/cases/logistic-confounding/data.csv
cut -d, -f1-6 validation/cases/logistic-confounding/data.csv | sort -u | head
```

If the header names differ from `response/arm/age/stage`, edit `case.json` to the real names. Do not rename columns in the CSV.

- [ ] **Step 3: Write the prose spec — the document the Python implementer works from**

Create `validation/spec/logistic-confounding.md`:

```markdown
# Analysis spec: logistic-confounding

Input: `validation/cases/logistic-confounding/data.csv`.

## Population
Complete cases only. Drop any row where the outcome or any of the three
covariates is missing or an empty string. Report the number dropped.

## Outcome coding
The outcome column is `response`. A row is an event (y = 1) when its value
equals the string `"Yes"`. If both the cell and `"Yes"` parse as numbers,
numeric equality also counts. Everything else is y = 0. A blank cell is
missing, not a non-event.

## Covariates
- `arm` — categorical, reference level `"Control"`.
- `stage` — categorical, reference level `"I"`.
- `age` — continuous, reported per 10 units. Divide the column by 10 before
  fitting, so the coefficient is the log odds ratio per 10 years.

Categorical covariates use treatment contrasts: the reference level first,
remaining levels in alphabetical order.

## Models
1. For each covariate, a univariable logistic regression of y on that
   covariate alone. This gives the unadjusted odds ratio.
2. One multivariable logistic regression of y on all three covariates
   jointly. This gives the adjusted odds ratios.

Both are maximum-likelihood binomial GLMs with a logit link.

## Reported quantities
Per covariate term: odds ratio = exp(coefficient); 95% CI =
exp(coefficient ± 1.96 × standard error) — the literal constant 1.96, not the
exact normal quantile; two-sided Wald p-value.

Also report: n analysed, number of events, number of rows dropped, and the
apparent (in-sample) C-statistic, computed as the normalised Mann-Whitney
statistic of predicted probabilities against observed outcome.

## Reportability
An odds ratio cell is reported only when the estimate and both CI bounds are
finite and the interval lies within [1e-6, 1e6]. Otherwise the cell reads
"not reliably estimated".

## Display
`%.2f (%.2f–%.2f, p=%.3f)` with an en-dash separator; when p < 0.001 the
p-part reads `p<0.001`.
```

- [ ] **Step 4: Write `validation/README.md`**

```markdown
# Statistical validation

Two independent implementations compute the same statistics from the same raw
CSV, and the comparison is published.

- **Path A** is Figura exactly as shipped: the real CSV parser, the real spec
  builders, and `render_figure()`.
- **Path B** is a Python implementation written from the prose spec in
  `spec/`, by an implementer who has not read `R/`.

Run everything:

    make -f validation/Makefile all

Read `results/scorecard.html` in a browser. It is self-contained and opens
from `file://`.

**If you are implementing Path B: do not read `R/*.R`.** Independence is the
only thing this exercise measures. A port that reproduces the same misreading
of the spec proves nothing.
```

- [ ] **Step 5: Commit**

```bash
git add validation/cases validation/spec validation/README.md
git commit -m "validation: case format, prose spec, and the first logistic case"
```

---

### Task 2: Spec-builder harness (raw CSV to Figura spec, through the shipped JS)

This is what makes the exercise cover the glue layer. Every real defect in this app's history lived in CSV parsing, type inference, factor construction, or event coding — not in R. If Path B started from Figura's JSON spec, all of it would be invisible.

**Files:**
- Create: `validation/harness/build-spec.mjs`
- Create: `validation/harness/build-spec.test.mjs`
- Modify: `package.json` (append to the `test:unit` chain)

**Interfaces:**
- Consumes: `parseCsv` from `web/lib/csv.js`; `buildLogisticSpec` from `web/guided/logistic/spec.js`.
- Produces: `buildSpecForCase(caseDir) -> object` and a CLI writing `validation/results/<id>.spec.json`.

- [ ] **Step 1: Write the failing test**

Create `validation/harness/build-spec.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { buildSpecForCase } from "./build-spec.mjs";

const spec = await buildSpecForCase("validation/cases/logistic-confounding");

assert.equal(spec.figure, "logistic");
assert.equal(spec.roles.outcome, "response");
assert.deepEqual(spec.roles.covariates, ["arm", "age", "stage"]);
assert.equal(spec.options.event_value, "Yes");
assert.equal(spec.options.increments.age, 10);
assert.ok(Array.isArray(spec.data), "data must be an array of row objects");
assert.ok(spec.data.length > 0, "data must not be empty");

// Only mapped columns cross into the spec (the no-egress narrowing).
assert.deepEqual(
  Object.keys(spec.data[0]).sort(),
  ["age", "arm", "response", "stage"].sort()
);

console.log("build-spec.test.mjs ok");
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `node validation/harness/build-spec.test.mjs`
Expected: FAIL with `Cannot find module '.../build-spec.mjs'`.

- [ ] **Step 3: Write the implementation**

Create `validation/harness/build-spec.mjs`:

```javascript
// Raw CSV -> Figura spec, using the SHIPPED parser and spec builders. Nothing
// here re-implements app behaviour; if a builder changes, this changes with it.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { parseCsv } from "../../web/lib/csv.js";
import { buildLogisticSpec } from "../../web/guided/logistic/spec.js";

const BUILDERS = {
  logistic: (table, c) =>
    buildLogisticSpec(
      table,
      { outcome: c.roles.outcome, covariates: c.roles.covariates },
      c.options.event_value,
      c.options.ref_levels || {},
      c.options.increments || {},
      { source_filename: "data.csv" }
    ),
};

export async function buildSpecForCase(caseDir) {
  const c = JSON.parse(
    await readFile(path.join(caseDir, "case.json"), "utf8")
  );
  const csv = await readFile(path.join(caseDir, "data.csv"), "utf8");
  const table = parseCsv(csv);
  const build = BUILDERS[c.figure];
  if (!build) throw new Error(`No spec builder registered for: ${c.figure}`);
  return build(table, c);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const caseDir = process.argv[2];
  if (!caseDir) {
    console.error("usage: node build-spec.mjs <case-dir>");
    process.exit(2);
  }
  process.stdout.write(JSON.stringify(await buildSpecForCase(caseDir)));
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node validation/harness/build-spec.test.mjs`
Expected: `build-spec.test.mjs ok`

If `parseCsv` or `buildLogisticSpec` is not exported, or its signature differs, **fix this file to match the app** — never change the app to suit the harness.

- [ ] **Step 5: Append to the test chain**

In `package.json`, append to the end of the `test:unit` value:

```
 && node validation/harness/build-spec.test.mjs
```

Run: `npm run test:unit`
Expected: the full chain passes, ending with `build-spec.test.mjs ok`.

- [ ] **Step 6: Commit**

```bash
git add validation/harness/build-spec.mjs validation/harness/build-spec.test.mjs package.json
git commit -m "validation: build Figura specs from raw CSV via the shipped JS"
```

---

### Task 3: Display-precision runner (Path A)

**Files:**
- Create: `validation/harness/parse-cells.mjs`
- Create: `validation/harness/parse-cells.test.mjs`
- Create: `validation/harness/run-figura.R`
- Modify: `package.json` (`test:unit` chain)

**Interfaces:**
- Produces: `formatRatioCell(est, lo, hi, p) -> string` and `parseRatioTable(text) -> {rows, methods}`; and `validation/results/<id>.figura.json` with shape `{id, cells: {term: {unadj, adj}}, methods, code}`.

- [ ] **Step 1: Write the failing test for the formatter and parser**

Create `validation/harness/parse-cells.test.mjs`:

```javascript
import assert from "node:assert/strict";
import { formatRatioCell, parseRatioTable } from "./parse-cells.mjs";

// Mirrors R: sprintf("%.2f (%.2f–%.2f, %s)", est, lo, hi, pf), en-dash U+2013.
assert.equal(formatRatioCell(1.0234, 0.6301, 1.6551, 0.9321),
  "1.02 (0.63–1.66, p=0.932)");
assert.equal(formatRatioCell(0.5, 0.27, 0.92, 0.00004),
  "0.50 (0.27–0.92, p<0.001)");
// Exactly 0.001 is not below 0.001, so it prints as a number.
assert.equal(formatRatioCell(2, 1, 4, 0.001), "2.00 (1.00–4.00, p=0.001)");

const text =
  "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)\n" +
  "New treatment\t1.02 (0.63–1.66, p=0.932)\t0.50 (0.30–0.83, p=0.023)\n" +
  "age (per 10 units)\t1.60 (1.30–1.97, p<0.001)\t1.69 (1.36–2.10, p<0.001)\n" +
  "\n" +
  "Univariable logistic regression (n = 320, 91 events) ...";
const out = parseRatioTable(text);
assert.equal(out.rows.length, 2);
assert.equal(out.rows[0].term, "New treatment");
assert.equal(out.rows[0].adj, "0.50 (0.30–0.83, p=0.023)");
assert.match(out.methods, /n = 320, 91 events/);

console.log("parse-cells.test.mjs ok");
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node validation/harness/parse-cells.test.mjs`
Expected: FAIL with `Cannot find module`.

- [ ] **Step 3: Write the implementation**

Create `validation/harness/parse-cells.mjs`:

```javascript
// Figura's display rule, restated once so the comparator can format Python's
// full-precision numbers the way the app would and compare strings.
export function formatRatioCell(est, lo, hi, p) {
  const pf = p < 0.001 ? "p<0.001" : `p=${p.toFixed(3)}`;
  return `${est.toFixed(2)} (${lo.toFixed(2)}–${hi.toFixed(2)}, ${pf})`;
}

// `text` from fig_cox / fig_logistic is TSV, then a blank line, then methods.
export function parseRatioTable(text) {
  const [tsv, ...rest] = text.split("\n\n");
  const lines = tsv.split("\n").filter((l) => l.trim() !== "");
  const rows = lines.slice(1).map((l) => {
    const [term, unadj, adj] = l.split("\t");
    return { term: term.trim(), unadj: unadj?.trim(), adj: adj?.trim() };
  });
  return { rows, methods: rest.join("\n\n").trim() };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node validation/harness/parse-cells.test.mjs`
Expected: `parse-cells.test.mjs ok`

- [ ] **Step 5: Write the R runner**

Create `validation/harness/run-figura.R`:

```r
# Path A, display precision. Reads a spec JSON, runs the real render_figure(),
# and writes the displayed cells plus the exported .R script.
#
# usage: Rscript validation/harness/run-figura.R <id> <spec.json> <out.json>
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
id <- args[[1]]; spec_path <- args[[2]]; out_path <- args[[3]]

devtools::load_all(quiet = TRUE)

spec_json <- paste(readLines(spec_path, warn = FALSE), collapse = "\n")
res <- jsonlite::fromJSON(render_figure(spec_json), simplifyVector = FALSE)

if (!isTRUE(res$ok)) {
  stop(sprintf("render_figure failed for %s: %s", id, res$error))
}

jsonlite::write_json(
  list(id = id, text = res$text, code = res$code %||% NA_character_),
  out_path, auto_unbox = TRUE, pretty = TRUE
)
cat(sprintf("wrote %s\n", out_path))
```

- [ ] **Step 6: Run it end to end**

```bash
mkdir -p validation/results
node validation/harness/build-spec.mjs validation/cases/logistic-confounding \
  > validation/results/logistic-confounding.spec.json
Rscript validation/harness/run-figura.R logistic-confounding \
  validation/results/logistic-confounding.spec.json \
  validation/results/logistic-confounding.figura.json
```

Expected: `wrote validation/results/logistic-confounding.figura.json`. Open it and confirm `text` contains a TSV whose first data row names a covariate.

- [ ] **Step 7: Append to the test chain and commit**

In `package.json`, append to `test:unit`:

```
 && node validation/harness/parse-cells.test.mjs
```

```bash
npm run test:unit
git add validation/harness package.json validation/results/.gitignore 2>/dev/null || true
git add validation/harness package.json
git commit -m "validation: display-precision Path A runner and cell parser"
```

---

### Task 4: Full-precision runner via Figura's own exported script

Figura's `.R` export is deparsed from the exact expressions the app evaluated, so running it recovers the unrounded model objects **and** proves the script reproduces what the screen showed. One artifact, two claims.

**Files:**
- Create: `validation/harness/run-script.R`

**Interfaces:**
- Produces: `validation/results/<id>.figura-exact.json`, shape `{id, terms: {term: {est, se, lo, hi, p}}, n, n_event}` on the ratio scale.

- [ ] **Step 1: Write the runner**

Create `validation/harness/run-script.R`:

```r
# Path A, full precision. Runs the .R script Figura exported, in a clean
# environment, from the case directory (so read.csv("data.csv") resolves), then
# harvests the joint model's unrounded estimates.
#
# usage: Rscript validation/harness/run-script.R <id> <figura.json> <case-dir> <out.json>
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 4L)
id <- args[[1]]; figura_path <- args[[2]]; case_dir <- args[[3]]; out_path <- args[[4]]

fj <- jsonlite::fromJSON(figura_path, simplifyVector = TRUE)
code <- fj$code
if (is.null(code) || is.na(code)) stop(sprintf("no exported code for %s", id))

script_file <- file.path(tempdir(), sprintf("%s-export.R", id))
writeLines(code, script_file)

env <- new.env(parent = globalenv())
old <- setwd(case_dir)
on.exit(setwd(old), add = TRUE)
source(script_file, local = env, echo = FALSE)

if (!exists("fit", envir = env)) {
  stop(sprintf("exported script for %s defined no `fit` object", id))
}
fit <- get("fit", envir = env)

sm <- summary(fit)$coefficients
est <- sm[, 1]; se <- sm[, 2]
pcol <- if ("Pr(>|z|)" %in% colnames(sm)) "Pr(>|z|)" else "Pr(>|t|)"
pv <- sm[, pcol]

# Ratio scale, Wald, literal 1.96 — the pinned convention.
terms <- lapply(rownames(sm), function(k) {
  list(est = exp(unname(est[k])),
       lo  = exp(unname(est[k] - 1.96 * se[k])),
       hi  = exp(unname(est[k] + 1.96 * se[k])),
       p   = unname(pv[k]))
})
names(terms) <- rownames(sm)
terms[["(Intercept)"]] <- NULL

dat <- if (exists("dat", envir = env)) get("dat", envir = env) else NULL
jsonlite::write_json(
  list(id = id, terms = terms,
       n = if (is.null(dat)) NA_integer_ else nrow(dat),
       n_event = if (is.null(dat)) NA_integer_ else sum(dat$.y == 1)),
  out_path, auto_unbox = TRUE, digits = NA, pretty = TRUE
)
cat(sprintf("wrote %s\n", out_path))
```

`digits = NA` is load-bearing: `jsonlite` truncates to 4 significant digits by default, which would silently cap this file at far less precision than the 1e-6 gate needs.

- [ ] **Step 2: Run it**

```bash
Rscript validation/harness/run-script.R logistic-confounding \
  validation/results/logistic-confounding.figura.json \
  validation/cases/logistic-confounding \
  validation/results/logistic-confounding.figura-exact.json
```

Expected: `wrote validation/results/logistic-confounding.figura-exact.json`, containing full-precision numbers (many decimal places, not 4 significant digits).

- [ ] **Step 3: Verify the script reproduces the screen**

Confirm by eye that formatting each `terms[k]` through the display rule reproduces the adjusted column of `text` in `logistic-confounding.figura.json`. Task 6 automates this as finding class `SCRIPT_DIVERGENCE`; here you are checking the harness works before wiring it.

If `fit` does not exist in the sourced environment, read the exported script — the object names come from `.logistic_script` in `R/logistic.R`. Adjust the harvest to the real names. **Reading `R/logistic.R` is allowed for anyone working on Path A; only the Path B implementer is barred.**

- [ ] **Step 4: Commit**

```bash
git add validation/harness/run-script.R
git commit -m "validation: full-precision Path A via Figura's exported script"
```

---

### Task 5: Python environment and the independent logistic implementation

**Dispatch this task to a fresh subagent whose prompt forbids reading `R/`, `web/`, and `validation/results/`.**

**Files:**
- Create: `validation/requirements.txt`
- Create: `validation/python/validate/__init__.py`
- Create: `validation/python/validate/io.py`
- Create: `validation/python/validate/logistic.py`
- Create: `validation/python/tests/test_io.py`
- Create: `validation/python/tests/test_logistic.py`

**Interfaces:**
- Produces: `load_case(case_dir) -> (DataFrame, dict)`; `code_event(series, event_value) -> Series[int]`;
  `fit_logistic(df, outcome, event_value, covariates, ref_levels, increments) -> dict` with keys
  `terms` (`{term: {est, lo, hi, p}}`, ratio scale), `n`, `n_event`, `n_dropped`, `c_statistic`.

- [ ] **Step 1: Create the venv and pin dependencies**

Create `validation/requirements.txt`:

```
pandas==2.2.3
numpy==2.1.3
scipy==1.14.1
statsmodels==0.14.4
lifelines==0.30.0
pytest==8.3.4
```

```bash
/opt/homebrew/bin/python3 -m venv validation/.venv
validation/.venv/bin/pip install -r validation/requirements.txt
validation/.venv/bin/python -c "import statsmodels, lifelines; print('ok')"
```

Expected: `ok`. If `python3` resolves into Anaconda, use the explicit Homebrew path as written above.

Add to `.gitignore`:

```
validation/.venv/
```

- [ ] **Step 2: Write the failing tests**

Create `validation/python/tests/test_io.py`:

```python
import pandas as pd
from validate.io import code_event, complete_cases


def test_code_event_matches_string():
    s = pd.Series(["Yes", "No", "Yes", ""])
    assert code_event(s, "Yes").tolist() == [1, 0, 1, 0]


def test_blank_outcome_is_missing_not_a_non_event():
    s = pd.Series(["Yes", "", None])
    coded = code_event(s, "Yes", blank_is_missing=True)
    assert coded.tolist()[0] == 1
    assert pd.isna(coded.tolist()[1])
    assert pd.isna(coded.tolist()[2])


def test_numeric_equality_also_counts():
    s = pd.Series(["1", "0", "1.0"])
    assert code_event(s, "1").tolist() == [1, 0, 1]


def test_complete_cases_drops_blank_strings():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "", "z"]})
    kept, dropped = complete_cases(df, ["a", "b"])
    assert len(kept) == 2
    assert dropped == 1
```

Create `validation/python/tests/test_logistic.py`:

```python
import numpy as np
import pandas as pd
from validate.logistic import fit_logistic


def _frame(seed=7, n=400):
    rng = np.random.default_rng(seed)
    stage = rng.choice(["I", "II"], size=n)
    x = (stage == "II").astype(float)
    logit = -1.0 + 1.2 * x
    y = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    return pd.DataFrame(
        {"resp": np.where(y == 1, "Yes", "No"), "stage": stage}
    )


def test_recovers_a_known_odds_ratio():
    df = _frame()
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    est = out["terms"]["stageII"]["est"]
    assert 2.4 < est < 4.4  # true OR = exp(1.2) = 3.32


def test_ci_uses_the_literal_1_96():
    df = _frame()
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    t = out["terms"]["stageII"]
    # log-CI must be symmetric about the log estimate to machine precision
    lo, hi, est = np.log(t["lo"]), np.log(t["hi"]), np.log(t["est"])
    assert abs((est - lo) - (hi - est)) < 1e-12


def test_increment_rescales_the_odds_ratio():
    rng = np.random.default_rng(3)
    age = rng.normal(60, 10, 500)
    y = rng.binomial(1, 1 / (1 + np.exp(-(-6 + 0.1 * age))))
    df = pd.DataFrame({"resp": np.where(y == 1, "Yes", "No"), "age": age})
    per1 = fit_logistic(df, "resp", "Yes", ["age"], {}, {})
    per10 = fit_logistic(df, "resp", "Yes", ["age"], {}, {"age": 10})
    assert abs(np.log(per10["terms"]["age"]["est"])
               - 10 * np.log(per1["terms"]["age"]["est"])) < 1e-9
    # the p-value is invariant to rescaling
    assert abs(per10["terms"]["age"]["p"] - per1["terms"]["age"]["p"]) < 1e-9


def test_counts_are_reported():
    df = _frame()
    df.loc[0, "stage"] = ""
    out = fit_logistic(df, "resp", "Yes", ["stage"], {"stage": "I"}, {})
    assert out["n_dropped"] == 1
    assert out["n"] == len(df) - 1
    assert out["n_event"] == int((df.drop(index=0)["resp"] == "Yes").sum())
```

- [ ] **Step 3: Run them to verify they fail**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests -q
```

Expected: collection errors — `ModuleNotFoundError: No module named 'validate'`.

- [ ] **Step 4: Write `io.py`**

```python
"""Shared input handling. Written from validation/spec/*.md only."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_case(case_dir: str | Path):
    case_dir = Path(case_dir)
    case = json.loads((case_dir / "case.json").read_text())
    # dtype=str keeps every column as written; each analysis coerces what it
    # needs. Reading numerics eagerly would let pandas guess a type the spec
    # never asked for.
    df = pd.read_csv(case_dir / "data.csv", dtype=str, keep_default_na=False)
    return df, case


def _as_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def code_event(series: pd.Series, event_value, blank_is_missing: bool = False):
    """1 when the cell equals the event value (as text, or numerically)."""
    ev = str(event_value)
    ev_num = _as_number(ev)
    out = []
    for raw in series:
        s = "" if raw is None else str(raw)
        if blank_is_missing and s.strip() == "":
            out.append(np.nan)
            continue
        hit = s == ev
        if not hit and ev_num is not None:
            n = _as_number(s)
            hit = n is not None and n == ev_num
        out.append(1 if hit else 0)
    return pd.Series(out, index=series.index, dtype="float64")


def complete_cases(df: pd.DataFrame, columns: list[str]):
    """Drop rows with a missing or blank cell in any named column."""
    mask = pd.Series(True, index=df.index)
    for c in columns:
        col = df[c]
        blank = col.isna() | col.astype(str).str.strip().eq("")
        mask &= ~blank
    return df[mask].copy(), int((~mask).sum())


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def treatment_dummies(values: pd.Series, reference: str | None):
    """Treatment contrasts: reference first, other levels alphabetical."""
    levels = sorted({str(v) for v in values if str(v).strip() != ""})
    if reference is None:
        reference = values.astype(str).value_counts().idxmax()
    reference = str(reference)
    if reference not in levels:
        raise ValueError(f"reference level {reference!r} not present")
    others = [l for l in levels if l != reference]
    return {lvl: (values.astype(str) == lvl).astype(float) for lvl in others}, reference
```

- [ ] **Step 5: Write `logistic.py`**

```python
"""Independent logistic regression per validation/spec/logistic-*.md."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .io import code_event, complete_cases, to_numeric, treatment_dummies

WALD_Z = 1.96  # literal, per spec — not scipy.stats.norm.ppf(0.975)
RATIO_MIN, RATIO_MAX = 1e-6, 1e6


def _design(df, covariates, ref_levels, increments):
    """Model matrix plus the term name R would give each column."""
    cols, names = {}, []
    for c in covariates:
        raw = df[c]
        numeric = to_numeric(raw)
        is_numeric = not numeric.isna().any()
        if is_numeric:
            k = float(increments.get(c, 1) or 1)
            cols[c] = numeric / k
            names.append(c)
        else:
            dummies, _ref = treatment_dummies(raw, ref_levels.get(c))
            for lvl, series in dummies.items():
                term = f"{c}{lvl}"
                cols[term] = series
                names.append(term)
    return pd.DataFrame(cols, index=df.index), names


def _c_statistic(y, p):
    """Normalised Mann-Whitney U of predicted probability against outcome."""
    order = pd.Series(p).rank().to_numpy()
    n1 = float((y == 1).sum())
    n0 = float((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r1 = order[y == 1].sum()
    return (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)


def _fit(X, y):
    Xc = sm.add_constant(X, has_constant="add")
    model = sm.GLM(y, Xc, family=sm.families.Binomial())
    res = model.fit()
    out = {}
    for term in X.columns:
        b = res.params[term]
        se = res.bse[term]
        out[term] = {
            "est": float(np.exp(b)),
            "lo": float(np.exp(b - WALD_Z * se)),
            "hi": float(np.exp(b + WALD_Z * se)),
            "p": float(res.pvalues[term]),
        }
    return out, res


def reportable(cell) -> bool:
    vals = (cell["est"], cell["lo"], cell["hi"])
    return (all(np.isfinite(v) for v in vals)
            and cell["hi"] <= RATIO_MAX and cell["lo"] >= RATIO_MIN)


def fit_logistic(df, outcome, event_value, covariates, ref_levels, increments):
    used = [outcome] + list(covariates)
    kept, n_dropped = complete_cases(df, used)
    y = code_event(kept[outcome], event_value).to_numpy()

    X, _names = _design(kept, covariates, ref_levels, increments)
    adjusted, res = _fit(X, y)

    unadjusted = {}
    for c in covariates:
        Xc, _ = _design(kept, [c], ref_levels, increments)
        terms, _ = _fit(Xc, y)
        unadjusted.update(terms)

    return {
        "terms": adjusted,
        "unadjusted": unadjusted,
        "n": int(len(kept)),
        "n_event": int(y.sum()),
        "n_dropped": n_dropped,
        "c_statistic": float(_c_statistic(y, res.fittedvalues.to_numpy())),
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests -q
```

Expected: all tests pass. Fix `validate/` only — never adjust a test to match a wrong result.

- [ ] **Step 7: Commit**

```bash
git add validation/requirements.txt validation/python .gitignore
git commit -m "validation: independent Python logistic implementation"
```

---

### Task 6: The comparator

**Files:**
- Create: `validation/python/validate/cli.py`
- Create: `validation/compare/compare.py`
- Create: `validation/compare/tests/test_compare.py`

**Interfaces:**
- Consumes: `<id>.figura.json`, `<id>.figura-exact.json`, `<id>.python.json`.
- Produces: `validation/results/findings.json`, shape
  `{cases: [{id, compared, passed, findings: [{code, disposition, term, quantity, figura, python, note}]}]}`.

Finding codes and their dispositions:

| Code | Meaning | Disposition |
|---|---|---|
| `PASS` | Python's value, formatted through Figura's display rule, is the identical string | pass |
| ~~`EXACT_PASS`~~ | *(planned, never wired &mdash; see the note under this table)* | n/a |
| `DISPLAY_ARTIFACT` | exact values agree but the displayed strings differ | review — a rounding or formatting issue, not a maths error |
| `SCRIPT_DIVERGENCE` | the exported `.R` disagrees with what the screen showed | defect — the user cannot reproduce what they saw |
| `COUNT_MISMATCH` | n, n_event, or n_dropped differ | defect — an input-fidelity failure, the highest-severity class |
| `DEFECT` | exact values disagree beyond tolerance | defect |

`COUNT_MISMATCH` is ranked highest deliberately: a disagreement about which rows were analysed means the two paths did not analyse the same study, and every downstream number is uninterpretable.

**Correction, recorded at the end of Phase 1: `EXACT_PASS` was never emitted.** It was planned here and never wired to any emission site; `compare.py` appends non-pass findings only, so agreement on the exact tier produces no finding at all rather than an `EXACT_PASS` one. `build_scorecard.py` deliberately does not style it either (styling a code the comparator cannot emit would suggest a tier ran that did not). The taxonomy that actually shipped is: `PASS` (synthesised by the scorecard for a case with no findings), `DISPLAY_ARTIFACT`, `DEFECT`, `COUNT_MISMATCH`, `SCRIPT_DIVERGENCE` — the five real ones from this table — plus three added after it was written: `MISSING_QUANTITY` (amendment A3's "every unmatched term / curve point / expected key is a finding"), `DECISION_MISMATCH` (Task 11's Table-1 comparison, where the CHOICE of summary statistic is itself a validated output), and `DIAGNOSTIC_MISMATCH` (amendment A14).

- [ ] **Step 1: Write the failing test**

Create `validation/compare/tests/test_compare.py`:

```python
from compare import classify_cell, close_enough


def test_close_enough_uses_relative_tolerance():
    assert close_enough(1.0000001, 1.0)
    assert not close_enough(1.001, 1.0)
    assert close_enough(0.0, 0.0)


def test_identical_display_is_a_pass():
    f = classify_cell(
        term="stageII", figura_cell="3.32 (2.40–4.59, p<0.001)",
        python={"est": 3.3201, "lo": 2.4012, "hi": 4.5910, "p": 0.0000004},
    )
    assert f["code"] == "PASS"


def test_rounding_only_difference_is_an_artifact_not_a_defect():
    f = classify_cell(
        term="stageII", figura_cell="3.32 (2.40–4.59, p<0.001)",
        python={"est": 3.3249, "lo": 2.4012, "hi": 4.5910, "p": 0.0000004},
    )
    assert f["code"] == "DISPLAY_ARTIFACT"


def test_real_disagreement_is_a_defect():
    f = classify_cell(
        term="stageII", figura_cell="3.32 (2.40–4.59, p<0.001)",
        python={"est": 1.10, "lo": 0.80, "hi": 1.50, "p": 0.6},
    )
    assert f["code"] == "DEFECT"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd validation/compare && ../.venv/bin/python -m pytest tests -q
```

Expected: `ModuleNotFoundError: No module named 'compare'`.

- [ ] **Step 3: Write `compare.py`**

```python
"""Path A vs Path B. Pure functions; the CLI at the bottom wires files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REL_TOL, ABS_TOL = 1e-6, 1e-9
RESULTS = Path(__file__).resolve().parents[1] / "results"


def close_enough(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def format_ratio_cell(est: float, lo: float, hi: float, p: float) -> str:
    pf = "p<0.001" if p < 0.001 else f"p={p:.3f}"
    return f"{est:.2f} ({lo:.2f}–{hi:.2f}, {pf})"


def classify_cell(term: str, figura_cell: str, python: dict) -> dict:
    rendered = format_ratio_cell(
        python["est"], python["lo"], python["hi"], python["p"]
    )
    if rendered == figura_cell:
        return {"code": "PASS", "term": term, "quantity": "displayed cell",
                "figura": figura_cell, "python": rendered, "note": ""}

    # Same to two decimals but a different string means rounding or formatting,
    # not arithmetic. Parse Figura's displayed numbers back out to check.
    try:
        head, tail = figura_cell.split(" (", 1)
        lo_s, rest = tail.split("–", 1)
        hi_s, _p = rest.split(",", 1)
        same = (
            close_enough(round(python["est"], 2), float(head))
            and close_enough(round(python["lo"], 2), float(lo_s))
            and close_enough(round(python["hi"], 2), float(hi_s))
        )
    except (ValueError, IndexError):
        same = False

    code = "DISPLAY_ARTIFACT" if same else "DEFECT"
    return {"code": code, "term": term, "quantity": "displayed cell",
            "figura": figura_cell, "python": rendered,
            "note": "identical to 2 dp; differs only in the rendered string"
                    if same else "values disagree"}


def compare_case(case_id: str) -> dict:
    figura = json.loads((RESULTS / f"{case_id}.figura.json").read_text())
    exact = json.loads((RESULTS / f"{case_id}.figura-exact.json").read_text())
    py = json.loads((RESULTS / f"{case_id}.python.json").read_text())

    findings, compared = [], 0

    for key in ("n", "n_event", "n_dropped"):
        a, b = exact.get(key), py.get(key)
        if a is None or b is None:
            continue
        compared += 1
        if a != b:
            findings.append({"code": "COUNT_MISMATCH", "term": "-",
                             "quantity": key, "figura": a, "python": b,
                             "note": "the two paths analysed different rows"})

    # Displayed adjusted cells.
    tsv = figura["text"].split("\n\n")[0].split("\n")
    for line in tsv[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        term_label, adj_cell = parts[0].strip(), parts[2].strip()
        match = py["display_terms"].get(term_label)
        if match is None:
            findings.append({"code": "DEFECT", "term": term_label,
                             "quantity": "displayed cell", "figura": adj_cell,
                             "python": None,
                             "note": "no Python term maps to this row label"})
            continue
        compared += 1
        f = classify_cell(term_label, adj_cell, match)
        if f["code"] != "PASS":
            findings.append(f)

    # Full-precision adjusted estimates.
    for term, a in exact["terms"].items():
        b = py["terms"].get(term)
        if b is None:
            continue
        for q in ("est", "lo", "hi", "p"):
            compared += 1
            if not close_enough(float(a[q]), float(b[q])):
                findings.append({"code": "DEFECT", "term": term, "quantity": q,
                                 "figura": a[q], "python": b[q],
                                 "note": f"beyond rel {REL_TOL}"})

    return {"id": case_id, "compared": compared,
            "passed": len(findings) == 0, "findings": findings}


def main(case_ids: list[str]) -> int:
    cases = [compare_case(c) for c in case_ids]
    out = {"cases": cases,
           "total_compared": sum(c["compared"] for c in cases),
           "total_findings": sum(len(c["findings"]) for c in cases)}
    (RESULTS / "findings.json").write_text(json.dumps(out, indent=2))
    for c in cases:
        status = "PASS" if c["passed"] else f"{len(c['findings'])} finding(s)"
        print(f"{c['id']}: {c['compared']} compared, {status}")
    return 0 if all(c["passed"] for c in cases) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd validation/compare && ../.venv/bin/python -m pytest tests -q
```

Expected: 4 passed.

- [ ] **Step 5: Write the Python CLI that emits `<id>.python.json`**

Create `validation/python/validate/cli.py`:

```python
"""Run Path B for one case and write its results JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .io import load_case
from .logistic import fit_logistic

RESULTS = Path(__file__).resolve().parents[2] / "results"


def display_label(term: str, covariates, increments) -> str:
    """The row label Figura prints, so the comparator can align rows."""
    for c in covariates:
        if term == c:
            k = float(increments.get(c, 1) or 1)
            return c if k == 1 else f"{c} (per {k:g} units)"
        if term.startswith(c):
            return f"{c}: {term[len(c):]}"
    return term


def run(case_dir: str) -> dict:
    df, case = load_case(case_dir)
    covs = case["roles"]["covariates"]
    incs = case["options"].get("increments", {})
    if case["figure"] != "logistic":
        raise SystemExit(f"no Path B implementation for {case['figure']}")
    out = fit_logistic(
        df, case["roles"]["outcome"], case["options"]["event_value"],
        covs, case["options"].get("ref_levels", {}), incs,
    )
    out["id"] = case["id"]
    out["display_terms"] = {
        display_label(t, covs, incs): v for t, v in out["terms"].items()
    }
    return out


if __name__ == "__main__":
    case_dir = sys.argv[1]
    result = run(case_dir)
    path = RESULTS / f"{result['id']}.python.json"
    path.write_text(json.dumps(result, indent=2))
    print(f"wrote {path}")
```

- [ ] **Step 6: Run the whole chain**

```bash
cd validation/python && ../.venv/bin/python -m validate.cli ../cases/logistic-confounding
cd ../compare && ../.venv/bin/python compare.py logistic-confounding
```

Expected: a line like `logistic-confounding: N compared, PASS` — or a finding count. **A finding here is a result, not a failure of the plan.** Write each one up under `.scratch/statistical-validation/issues/` and continue; do not fix `R/` in this task.

If row labels do not align, fix `display_label` to match what Figura actually prints. The label mapping is Path A metadata, not a statistical claim, so reading `R/logistic.R` to get the label format right is allowed.

- [ ] **Step 7: Commit**

```bash
git add validation/compare validation/python/validate/cli.py
git commit -m "validation: comparator with tolerance rules and finding dispositions"
```

---

### Task 7: Scorecard

**Files:**
- Create: `validation/build_scorecard.py`
- Create: `validation/Makefile`

**Interfaces:**
- Consumes: `results/findings.json`.
- Produces: `results/scorecard.html`, self-contained, `file://`-safe, rendering precomputed JSON only — the same house pattern as `sdtm-bench`'s `results/scorecard.html`.

- [ ] **Step 1: Write the builder**

```python
"""findings.json -> a self-contained scorecard. No live computation."""
from __future__ import annotations

import html
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

CSS = """
:root { --ink:#1a1a1a; --muted:#5b5b5b; --rule:#d8d4cc; --paper:#faf8f5;
        --pass:#0d6b63; --warn:#8a6d1f; --fail:#a02c2c; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#ececec; --muted:#a5a5a5; --rule:#3a3a3a; --paper:#16181a; } }
body { margin:0; padding:2.5rem 1.25rem; background:var(--paper); color:var(--ink);
       font:16px/1.6 "IBM Plex Sans", system-ui, sans-serif; }
main { max-width:60rem; margin:0 auto; }
h1 { font:600 1.6rem/1.2 "Source Serif 4", Georgia, serif; margin:0 0 .25rem; }
.sub { color:var(--muted); margin:0 0 2rem; }
.tiles { display:flex; flex-wrap:wrap; gap:1rem; margin-bottom:2rem; }
.tile { border:1px solid var(--rule); border-radius:8px; padding:.9rem 1.1rem;
        min-width:9rem; }
.tile b { display:block; font:600 1.5rem/1 "IBM Plex Mono", monospace; }
.tile span { color:var(--muted); font-size:.8rem; text-transform:uppercase;
             letter-spacing:.04em; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:.9rem; }
th,td { text-align:left; padding:.45rem .6rem; border-bottom:1px solid var(--rule);
        vertical-align:top; }
th { font-weight:600; }
code { font:.85em "IBM Plex Mono", monospace; }
.PASS { color:var(--pass); }   /* no .EXACT_PASS: never emitted, see above */
.DISPLAY_ARTIFACT { color:var(--warn); }
.DEFECT,.COUNT_MISMATCH,.SCRIPT_DIVERGENCE { color:var(--fail); font-weight:600; }
"""


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def build() -> Path:
    data = json.loads((RESULTS / "findings.json").read_text())
    compared = data["total_compared"]
    findings = data["total_findings"]
    defects = sum(
        1 for c in data["cases"] for f in c["findings"]
        if f["code"] in ("DEFECT", "COUNT_MISMATCH", "SCRIPT_DIVERGENCE")
    )

    rows = []
    for c in data["cases"]:
        if not c["findings"]:
            rows.append(
                f"<tr><td>{esc(c['id'])}</td><td class='PASS'>PASS</td>"
                f"<td colspan='4'>{c['compared']} values compared, "
                f"no differences</td></tr>"
            )
        for f in c["findings"]:
            rows.append(
                f"<tr><td>{esc(c['id'])}</td>"
                f"<td class='{esc(f['code'])}'>{esc(f['code'])}</td>"
                f"<td>{esc(f['term'])}</td><td>{esc(f['quantity'])}</td>"
                f"<td><code>{esc(f['figura'])}</code></td>"
                f"<td><code>{esc(f['python'])}</code></td></tr>"
            )

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Figura statistical validation scorecard</title><style>{CSS}</style></head>
<body><main>
<h1>Statistical validation scorecard</h1>
<p class="sub">Every number Figura reports, re-derived by an independently
programmed Python implementation from the same raw CSV.</p>
<div class="tiles">
  <div class="tile"><b>{compared}</b><span>values compared</span></div>
  <div class="tile"><b>{findings}</b><span>differences</span></div>
  <div class="tile"><b>{defects}</b><span>defects</span></div>
</div>
<div class="scroll"><table>
<thead><tr><th>Case</th><th>Result</th><th>Term</th><th>Quantity</th>
<th>Figura</th><th>Python</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="sub">A <b>display artifact</b> means both paths computed the same
number and only the rendered string differs. A <b>defect</b> means the values
themselves disagree beyond a relative tolerance of 1e-6.</p>
</main></body></html>"""

    out = RESULTS / "scorecard.html"
    out.write_text(doc)
    return out


if __name__ == "__main__":
    print(f"wrote {build()}")
```

- [ ] **Step 2: Write the Makefile that runs the whole pipeline**

Create `validation/Makefile`:

```makefile
PY := $(CURDIR)/.venv/bin/python
CASES := logistic-confounding

.PHONY: all clean
all: $(CASES:%=results/%.done)
	cd compare && $(PY) compare.py $(CASES)
	$(PY) build_scorecard.py

results/%.done: cases/%/data.csv cases/%/case.json
	@mkdir -p results
	node harness/build-spec.mjs cases/$* > results/$*.spec.json
	Rscript harness/run-figura.R $* results/$*.spec.json results/$*.figura.json
	Rscript harness/run-script.R $* results/$*.figura.json cases/$* \
	  results/$*.figura-exact.json
	cd python && $(PY) -m validate.cli ../cases/$*
	@touch $@

clean:
	rm -rf results/*.json results/*.done results/scorecard.html
```

The `harness/build-spec.mjs` path resolution assumes `validation/` as the working directory; run `make -f validation/Makefile` from the repo root with `-C validation` instead:

```bash
make -C validation all
```

- [ ] **Step 3: Run it and open the scorecard**

```bash
make -C validation clean all
open validation/results/scorecard.html
```

Expected: a scorecard showing the compared count and any findings.

- [ ] **Step 4: Commit, including the results**

```bash
git add validation/build_scorecard.py validation/Makefile validation/results
git commit -m "validation: scorecard build and one-command pipeline"
```

Results are committed deliberately: they are the evidence, and a scorecard that only exists on one laptop cannot be cited.

---

### Task 8: Cox regression

**Files:**
- Create: `validation/cases/cox-adjusted/{data.csv,case.json}`
- Create: `validation/spec/cox-adjusted.md`
- Create: `validation/python/validate/cox.py`
- Create: `validation/python/tests/test_cox.py`
- Modify: `validation/harness/build-spec.mjs` (register the cox builder)
- Modify: `validation/python/validate/cli.py` (dispatch on `figure`)
- Modify: `validation/Makefile` (`CASES`)

**Interfaces:**
- Produces: `fit_cox(df, time, status, event_value, covariates, ref_levels) -> dict`, same shape as `fit_logistic` plus `n_event`.

- [ ] **Step 1: Create the case from the existing fixture**

```bash
mkdir -p validation/cases/cox-adjusted
cp tests/testthat/fixtures/cox-demo.csv validation/cases/cox-adjusted/data.csv
head -1 validation/cases/cox-adjusted/data.csv
```

Write `case.json` using the real header names:

```json
{
  "id": "cox-adjusted",
  "figure": "cox",
  "roles": { "time": "time", "status": "status", "covariates": ["arm", "age"] },
  "options": { "event_value": "1", "ref_levels": { "arm": "Control" } },
  "display": { "kind": "ratio_table" },
  "exact_targets": ["adjusted_hr", "adjusted_ci", "adjusted_p", "n", "n_event"]
}
```

- [ ] **Step 2: Write `validation/spec/cox-adjusted.md`**

Same structure as the logistic spec, with these clauses:

```markdown
## Models
Cox proportional-hazards regression, partial likelihood, **Efron** handling of
tied event times. One univariable model per covariate, plus one joint model.

## Reported quantities
Hazard ratio = exp(coefficient); 95% CI = exp(coefficient ± 1.96 × SE);
two-sided Wald p-value. Also n analysed and number of events.

## Status coding
A row is an event when the status column equals the event value (as text, or
numerically if both parse as numbers). Everything else is censored.
```

Copy the Population, Covariates, Reportability, and Display sections from
`logistic-confounding.md` verbatim — the Path B implementer reads only this
file, so it must stand alone. Do not write "same as logistic".

- [ ] **Step 3: Write the failing test**

Create `validation/python/tests/test_cox.py`:

```python
import numpy as np
import pandas as pd
from validate.cox import fit_cox


def _frame(seed=11, n=400, log_hr=0.7):
    rng = np.random.default_rng(seed)
    arm = rng.choice(["Control", "Treated"], size=n)
    x = (arm == "Treated").astype(float)
    scale = np.exp(-log_hr * x)
    t_event = rng.exponential(scale=scale)
    t_cens = rng.exponential(scale=1.5, size=n)
    time = np.minimum(t_event, t_cens)
    status = (t_event <= t_cens).astype(int)
    return pd.DataFrame({"time": time, "status": status.astype(str), "arm": arm})


def test_recovers_a_known_hazard_ratio():
    out = fit_cox(_frame(), "time", "status", "1", ["arm"], {"arm": "Control"})
    hr = out["terms"]["armTreated"]["est"]
    assert 1.6 < hr < 2.4  # true HR = exp(0.7) = 2.01


def test_ci_is_symmetric_on_the_log_scale():
    out = fit_cox(_frame(), "time", "status", "1", ["arm"], {"arm": "Control"})
    t = out["terms"]["armTreated"]
    lo, hi, est = np.log(t["lo"]), np.log(t["hi"]), np.log(t["est"])
    assert abs((est - lo) - (hi - est)) < 1e-12


def test_event_count_matches_the_status_column():
    df = _frame()
    out = fit_cox(df, "time", "status", "1", ["arm"], {"arm": "Control"})
    assert out["n_event"] == int((df["status"] == "1").sum())
```

- [ ] **Step 4: Run it to verify it fails**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests/test_cox.py -q
```

Expected: `ModuleNotFoundError: No module named 'validate.cox'`.

- [ ] **Step 5: Write `cox.py`**

```python
"""Independent Cox regression per validation/spec/cox-*.md."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter

from .io import code_event, complete_cases, to_numeric, treatment_dummies
from .logistic import WALD_Z, _design  # design matrix rule is identical


def _fit(frame, duration_col, event_col):
    # Efron is lifelines' tie-handling default and the spec's requirement.
    cph = CoxPHFitter()
    cph.fit(frame, duration_col=duration_col, event_col=event_col)
    out = {}
    for term in frame.columns.drop([duration_col, event_col]):
        b = cph.params_[term]
        se = cph.standard_errors_[term]
        out[term] = {
            "est": float(np.exp(b)),
            "lo": float(np.exp(b - WALD_Z * se)),
            "hi": float(np.exp(b + WALD_Z * se)),
            "p": float(cph.summary.loc[term, "p"]),
        }
    return out


def fit_cox(df, time, status, event_value, covariates, ref_levels,
            increments=None):
    increments = increments or {}
    used = [time, status] + list(covariates)
    kept, n_dropped = complete_cases(df, used)

    X, _ = _design(kept, covariates, ref_levels, increments)
    base = X.copy()
    base["__t"] = to_numeric(kept[time]).to_numpy()
    base["__e"] = code_event(kept[status], event_value).to_numpy()

    adjusted = _fit(base, "__t", "__e")

    unadjusted = {}
    for c in covariates:
        Xc, _ = _design(kept, [c], ref_levels, increments)
        one = Xc.copy()
        one["__t"] = base["__t"].to_numpy()
        one["__e"] = base["__e"].to_numpy()
        unadjusted.update(_fit(one, "__t", "__e"))

    return {
        "terms": adjusted,
        "unadjusted": unadjusted,
        "n": int(len(kept)),
        "n_event": int(base["__e"].sum()),
        "n_dropped": n_dropped,
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests -q
```

Expected: all tests pass, including the logistic ones.

- [ ] **Step 7: Register cox in the harness and the CLI**

In `validation/harness/build-spec.mjs`, add the import and the builder entry:

```javascript
import { buildCoxSpec } from "../../web/guided/cox/spec.js";
```

```javascript
  cox: (table, c) =>
    buildCoxSpec(
      table,
      { time: c.roles.time, status: c.roles.status,
        covariates: c.roles.covariates },
      c.options.event_value,
      c.options.ref_levels || {},
      { source_filename: "data.csv" }
    ),
```

Check `web/guided/cox/spec.js` for the real export name and argument order and match it exactly. In `validation/python/validate/cli.py`, replace the single-figure guard with a dispatch:

```python
from .cox import fit_cox

def _run_analysis(df, case):
    fig = case["figure"]
    roles, opts = case["roles"], case["options"]
    if fig == "logistic":
        return fit_logistic(df, roles["outcome"], opts["event_value"],
                            roles["covariates"], opts.get("ref_levels", {}),
                            opts.get("increments", {}))
    if fig == "cox":
        return fit_cox(df, roles["time"], roles["status"], opts["event_value"],
                       roles["covariates"], opts.get("ref_levels", {}),
                       opts.get("increments", {}))
    raise SystemExit(f"no Path B implementation for {fig}")
```

and call `_run_analysis(df, case)` in `run()`.

- [ ] **Step 8: Add the case to the Makefile and run**

Change `CASES := logistic-confounding` to:

```makefile
CASES := logistic-confounding cox-adjusted
```

```bash
make -C validation clean all
```

Expected: both cases compared. Write up any findings under `.scratch/statistical-validation/issues/`.

- [ ] **Step 9: Commit**

```bash
git add validation
git commit -m "validation: independent Cox implementation and case"
```

---

### Task 9: Kaplan-Meier and log-rank

**Files:**
- Create: `validation/cases/km-twoarm/{data.csv,case.json}`
- Create: `validation/spec/km-twoarm.md`
- Create: `validation/python/validate/km.py`
- Create: `validation/python/tests/test_km.py`
- Modify: `validation/harness/build-spec.mjs`, `validation/python/validate/cli.py`, `validation/Makefile`

**Interfaces:**
- Produces: `fit_km(df, time, status, event_value, group) -> dict` with keys
  `medians` (`{group: float | None}`), `logrank_p`, `n`, `n_event`, `curve`
  (`{group: [{t, surv, at_risk}]}`).

The curve comparison is the strongest check available for KM: it compares the entire step function, not just a headline number.

- [ ] **Step 1: Create the case**

```bash
mkdir -p validation/cases/km-twoarm
cp tests/testthat/fixtures/km-demo.csv validation/cases/km-twoarm/data.csv
head -1 validation/cases/km-twoarm/data.csv
```

```json
{
  "id": "km-twoarm",
  "figure": "km",
  "roles": { "time": "time", "status": "status", "group": "group" },
  "options": { "event_value": "1" },
  "display": { "kind": "km_summary" },
  "exact_targets": ["median_survival", "logrank_p", "curve", "n", "n_event"]
}
```

- [ ] **Step 2: Write `validation/spec/km-twoarm.md`**

```markdown
# Analysis spec: km-twoarm

Input: `validation/cases/km-twoarm/data.csv`.

## Population
Complete cases only across the time, status, and group columns. A blank cell
is missing.

## Event coding
A row is an event when the status column equals `"1"` (as text, or numerically
if both parse as numbers). Everything else is censored at its recorded time.

## Estimator
The Kaplan-Meier product-limit estimator, computed separately within each
level of the group column. At each distinct event time t, the survival
probability is multiplied by (1 - d/n), where d is the number of events at t
and n is the number at risk just before t. Censored observations leave the
risk set without contributing an event.

## Reported quantities
- Median survival per group: the smallest time at which the estimated survival
  probability is <= 0.5. If the curve never reaches 0.5, the median is not
  reached and must be reported as such, never as the largest observed time.
- The two-sided log-rank test p-value comparing groups (Mantel-Haenszel, equal
  weights across event times — not Peto and not Gehan-Wilcoxon).
- n analysed and total number of events.
- The full step function per group: every distinct event time with its
  survival probability and number at risk.
```

- [ ] **Step 3: Write the failing test**

Create `validation/python/tests/test_km.py`:

```python
import numpy as np
import pandas as pd
from validate.km import fit_km


def test_hand_computed_product_limit():
    # 5 subjects: events at 1 and 4, censored at 2, 3, 5.
    df = pd.DataFrame({
        "time": ["1", "2", "3", "4", "5"],
        "status": ["1", "0", "0", "1", "0"],
        "group": ["A"] * 5,
    })
    out = fit_km(df, "time", "status", "1", "group")
    curve = {p["t"]: p["surv"] for p in out["curve"]["A"]}
    # S(1) = 1 - 1/5 = 0.8; then 2 censored leave, S(4) = 0.8 * (1 - 1/2) = 0.4
    assert abs(curve[1.0] - 0.8) < 1e-12
    assert abs(curve[4.0] - 0.4) < 1e-12


def test_median_not_reached_is_none_not_the_last_time():
    df = pd.DataFrame({
        "time": ["1", "2", "3"],
        "status": ["1", "0", "0"],
        "group": ["A"] * 3,
    })
    out = fit_km(df, "time", "status", "1", "group")
    assert out["medians"]["A"] is None


def test_logrank_detects_a_real_separation():
    rng = np.random.default_rng(5)
    a = rng.exponential(1.0, 150)
    b = rng.exponential(3.0, 150)
    df = pd.DataFrame({
        "time": np.concatenate([a, b]).astype(str),
        "status": ["1"] * 300,
        "group": ["A"] * 150 + ["B"] * 150,
    })
    out = fit_km(df, "time", "status", "1", "group")
    assert out["logrank_p"] < 0.001
```

- [ ] **Step 4: Run it to verify it fails**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests/test_km.py -q
```

Expected: `ModuleNotFoundError: No module named 'validate.km'`.

- [ ] **Step 5: Write `km.py`**

```python
"""Independent Kaplan-Meier and log-rank per validation/spec/km-*.md."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test

from .io import code_event, complete_cases, to_numeric


def _curve(times, events):
    """Product-limit estimate at each distinct event time."""
    order = np.argsort(times, kind="mergesort")
    t, e = np.asarray(times)[order], np.asarray(events)[order]
    n = len(t)
    surv, points, at_risk = 1.0, [], n
    for time in np.unique(t):
        at_time = t == time
        d = int(e[at_time].sum())
        if d > 0:
            surv *= 1.0 - d / at_risk
            points.append({"t": float(time), "surv": float(surv),
                           "at_risk": int(at_risk)})
        at_risk -= int(at_time.sum())
    return points


def _median(points):
    for p in points:
        if p["surv"] <= 0.5:
            return p["t"]
    return None


def fit_km(df, time, status, event_value, group):
    used = [time, status] + ([group] if group else [])
    kept, n_dropped = complete_cases(df, used)
    t = to_numeric(kept[time]).to_numpy()
    e = code_event(kept[status], event_value).to_numpy()
    g = kept[group].astype(str).to_numpy() if group else np.array(["Overall"] * len(kept))

    curve, medians = {}, {}
    for level in sorted(set(g)):
        m = g == level
        pts = _curve(t[m], e[m])
        curve[level] = pts
        medians[level] = _median(pts)

    logrank_p = None
    if len(set(g)) > 1:
        logrank_p = float(multivariate_logrank_test(t, g, e).p_value)

    return {
        "medians": medians,
        "logrank_p": logrank_p,
        "curve": curve,
        "n": int(len(kept)),
        "n_event": int(e.sum()),
        "n_dropped": n_dropped,
    }
```

`KaplanMeierFitter` is imported but the estimate is hand-rolled on purpose: a spec that describes the product-limit formula deserves an implementation of that formula, and hand-rolling gives a second check against lifelines itself. Add a test asserting the two agree:

```python
def test_hand_rolled_agrees_with_lifelines():
    rng = np.random.default_rng(9)
    t = rng.exponential(2.0, 200)
    e = rng.binomial(1, 0.7, 200)
    df = pd.DataFrame({"time": t.astype(str), "status": e.astype(str),
                       "group": ["A"] * 200})
    out = fit_km(df, "time", "status", "1", "group")
    kmf = KaplanMeierFitter().fit(t, e)
    for p in out["curve"]["A"]:
        assert abs(p["surv"] - float(kmf.predict(p["t"]))) < 1e-9
```

Add `from lifelines import KaplanMeierFitter` to the test file's imports.

- [ ] **Step 6: Run the tests**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests -q
```

Expected: all pass.

- [ ] **Step 7: Register km, extend the comparator for KM quantities**

Add the `km` builder to `build-spec.mjs` (import `buildKmSpec` from `web/guided/km/spec.js`, matching its real signature) and the `km` branch to `_run_analysis`. In `compare.py`, add a curve comparison before the ratio-table block:

```python
    if "curve" in py:
        for level, points in py["curve"].items():
            a_points = {p["t"]: p["surv"]
                        for p in exact.get("curve", {}).get(level, [])}
            for p in points:
                if p["t"] not in a_points:
                    continue
                compared += 1
                if not close_enough(a_points[p["t"]], p["surv"]):
                    findings.append(
                        {"code": "DEFECT", "term": level,
                         "quantity": f"S(t={p['t']:g})",
                         "figura": a_points[p["t"]], "python": p["surv"],
                         "note": "survival estimate disagrees"})
```

Extend `harness/run-script.R` to emit `curve` for KM cases by harvesting `survfit` from the exported script:

```r
if (exists("fit", envir = env) && inherits(get("fit", envir = env), "survfit")) {
  sf <- summary(get("fit", envir = env))
  strata <- if (is.null(sf$strata)) rep("Overall", length(sf$time))
            else sub("^[^=]*=", "", as.character(sf$strata))
  curve <- split(
    data.frame(t = sf$time, surv = sf$surv, at_risk = sf$n.risk), strata
  )
  payload$curve <- lapply(curve, function(d) unname(split(d, seq_len(nrow(d)))))
}
```

Restructure `run-script.R` so the JSON body is assembled into a `payload` list and written once at the end, rather than inline as written in Task 4.

- [ ] **Step 8: Add the case and run**

```makefile
CASES := logistic-confounding cox-adjusted km-twoarm
```

```bash
make -C validation clean all
```

- [ ] **Step 9: Commit**

```bash
git add validation
git commit -m "validation: independent Kaplan-Meier and log-rank, with curve comparison"
```

---

### Task 10: Group comparison

**Files:**
- Create: `validation/cases/groupcompare-numeric/{data.csv,case.json}`
- Create: `validation/cases/groupcompare-categorical/{data.csv,case.json}`
- Create: `validation/spec/groupcompare-numeric.md`, `validation/spec/groupcompare-categorical.md`
- Create: `validation/python/validate/groupcompare.py`
- Create: `validation/python/tests/test_groupcompare.py`
- Modify: `validation/harness/build-spec.mjs`, `validation/python/validate/cli.py`, `validation/Makefile`

Two cases because the analysis branches on outcome type, and an untested branch is an unvalidated branch.

**Interfaces:**
- Produces: `compare_groups(df, outcome, group, nonparametric=None) -> dict` with keys
  `test_name`, `p_value`, `effect`, `effect_ci`, `n_per_group`, `posthoc`.

- [ ] **Step 1: Create both cases**

```bash
mkdir -p validation/cases/groupcompare-numeric validation/cases/groupcompare-categorical
cp tests/testthat/fixtures/groupcompare-demo.csv \
   validation/cases/groupcompare-numeric/data.csv
cp tests/testthat/fixtures/groupcompare-demo.csv \
   validation/cases/groupcompare-categorical/data.csv
head -1 validation/cases/groupcompare-numeric/data.csv
```

Pick a numeric outcome column for the first and a categorical one for the second, and write the two `case.json` files with `"figure": "groupcompare"` and roles `{"outcome": …, "group": …}`.

- [ ] **Step 2: Write the two prose specs**

The decisive clauses, which must appear verbatim because they are where the languages disagree by default:

```markdown
## Test selection (numeric outcome)
Assess normality of the outcome and choose accordingly. With two groups:
a **Welch** two-sample t-test (unequal variances assumed — this is not the
pooled t-test) when approximately normal, otherwise a Mann-Whitney U test.
With three or more groups: Welch one-way ANOVA when approximately normal,
otherwise Kruskal-Wallis.

## Test selection (categorical outcome)
A chi-square test of independence **with no continuity correction**. If any
expected cell count is below 5, use Fisher's exact test instead.

## Effect sizes
Two numeric groups: Hedges-corrected standardised mean difference with a 95%
CI. Two groups non-parametric: rank-biserial correlation from the U statistic.
Three or more: eta-squared (parametric) or epsilon-squared (Kruskal-Wallis).
Categorical: Cramer's V from the uncorrected chi-square statistic.

## Post-hoc
Three or more groups, parametric: Tukey HSD, all pairwise. Non-parametric:
Dunn's test with the same pairing.
```

- [ ] **Step 3: Write the failing test**

Create `validation/python/tests/test_groupcompare.py`:

```python
import numpy as np
import pandas as pd
from scipy import stats
from validate.groupcompare import compare_groups


def test_two_numeric_groups_use_welch_not_pooled():
    rng = np.random.default_rng(2)
    a = rng.normal(10, 1, 60)
    b = rng.normal(12, 4, 60)  # deliberately unequal variances
    df = pd.DataFrame({"y": np.concatenate([a, b]).astype(str),
                       "g": ["A"] * 60 + ["B"] * 60})
    out = compare_groups(df, "y", "g", nonparametric=False)
    welch = stats.ttest_ind(a, b, equal_var=False).pvalue
    pooled = stats.ttest_ind(a, b, equal_var=True).pvalue
    assert abs(out["p_value"] - welch) < 1e-12
    assert abs(out["p_value"] - pooled) > 1e-6  # the defaults really do differ


def test_chi_square_has_no_continuity_correction():
    df = pd.DataFrame({
        "y": ["yes"] * 40 + ["no"] * 60 + ["yes"] * 60 + ["no"] * 40,
        "g": ["A"] * 100 + ["B"] * 100,
    })
    out = compare_groups(df, "y", "g")
    table = pd.crosstab(df["g"], df["y"]).to_numpy()
    expected = stats.chi2_contingency(table, correction=False).pvalue
    assert abs(out["p_value"] - expected) < 1e-12


def test_fisher_replaces_chi_square_on_small_expected_counts():
    df = pd.DataFrame({
        "y": ["yes", "no", "no", "no", "yes", "no", "no", "no"],
        "g": ["A", "A", "A", "A", "B", "B", "B", "B"],
    })
    out = compare_groups(df, "y", "g")
    assert "Fisher" in out["test_name"]
```

- [ ] **Step 4: Run it to verify it fails**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests/test_groupcompare.py -q
```

Expected: `ModuleNotFoundError: No module named 'validate.groupcompare'`.

- [ ] **Step 5: Write `groupcompare.py`**

```python
"""Independent group comparison per validation/spec/groupcompare-*.md."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from .io import complete_cases, to_numeric


def _is_numeric(series: pd.Series) -> bool:
    return not to_numeric(series).isna().any()


def _hedges_g(a, b):
    n1, n2 = len(a), len(b)
    s = np.sqrt(((n1 - 1) * np.var(a, ddof=1) + (n2 - 1) * np.var(b, ddof=1))
                / (n1 + n2 - 2))
    d = (np.mean(a) - np.mean(b)) / s
    j = 1 - 3 / (4 * (n1 + n2) - 9)
    g = j * d
    se = np.sqrt((n1 + n2) / (n1 * n2) + g**2 / (2 * (n1 + n2 - 2)))
    return g, (g - 1.96 * se, g + 1.96 * se)


def _numeric(groups, nonparametric):
    values = list(groups.values())
    if len(values) == 2:
        a, b = values
        if nonparametric:
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            r = 1 - 2 * u / (len(a) * len(b))
            return "Mann-Whitney U test", float(p), float(r), None
        t = stats.ttest_ind(a, b, equal_var=False)  # Welch, per spec
        g, ci = _hedges_g(a, b)
        return "Welch t-test", float(t.pvalue), float(g), tuple(map(float, ci))
    if nonparametric:
        h, p = stats.kruskal(*values)
        n = sum(len(v) for v in values)
        eps = (h - len(values) + 1) / (n - len(values))
        return "Kruskal-Wallis test", float(p), float(eps), None
    f = stats.f_oneway(*values)  # replaced below by Welch ANOVA
    w = stats.alexandergovern(*values)
    ss_b = sum(len(v) * (np.mean(v) - np.mean(np.concatenate(values))) ** 2
               for v in values)
    ss_t = float(np.sum((np.concatenate(values)
                         - np.mean(np.concatenate(values))) ** 2))
    return "Welch one-way ANOVA", float(w.pvalue), float(ss_b / ss_t), None


def _categorical(df, outcome, group):
    table = pd.crosstab(df[group].astype(str), df[outcome].astype(str))
    chi = stats.chi2_contingency(table.to_numpy(), correction=False)
    if (chi.expected_freq < 5).any():
        if table.shape == (2, 2):
            p = float(stats.fisher_exact(table.to_numpy()).pvalue)
        else:
            p = float(stats.fisher_exact(table.to_numpy())[1])
        name = "Fisher's exact test"
    else:
        p, name = float(chi.pvalue), "Chi-square test"
    n = int(table.to_numpy().sum())
    k = min(table.shape) - 1
    v = float(np.sqrt(chi.statistic / (n * k))) if k > 0 else float("nan")
    return name, p, v, None


def compare_groups(df, outcome, group, nonparametric=None):
    kept, n_dropped = complete_cases(df, [outcome, group])
    numeric = _is_numeric(kept[outcome])

    if numeric:
        y = to_numeric(kept[outcome])
        groups = {g: y[kept[group].astype(str) == g].to_numpy()
                  for g in sorted(kept[group].astype(str).unique())}
        if nonparametric is None:
            pooled = np.concatenate(list(groups.values()))
            nonparametric = not _approximately_normal(pooled)
        name, p, eff, ci = _numeric(groups, nonparametric)
        posthoc = None
        if len(groups) > 2 and not nonparametric:
            tk = pairwise_tukeyhsd(y.to_numpy(), kept[group].astype(str))
            posthoc = [
                {"pair": f"{r[0]} vs {r[1]}", "p": float(r[3])}
                for r in tk.summary().data[1:]
            ]
        n_per = {g: int(len(v)) for g, v in groups.items()}
    else:
        name, p, eff, ci = _categorical(kept, outcome, group)
        n_per = kept.groupby(kept[group].astype(str)).size().to_dict()
        posthoc = None

    return {"test_name": name, "p_value": p, "effect": eff, "effect_ci": ci,
            "n_per_group": {k: int(v) for k, v in n_per.items()},
            "n_dropped": n_dropped, "posthoc": posthoc}


def _approximately_normal(x) -> bool:
    """Spec rule: Shapiro-Wilk p >= 0.05 and |population skewness| < 1."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 3 or len(np.unique(x)) < 3:
        return False
    skew = float(stats.skew(x, bias=True))
    if len(x) > 300:
        return abs(skew) < 1
    p = float(stats.shapiro(x).pvalue)
    return p >= 0.05 and abs(skew) < 1
```

The `f_oneway` line is dead once Welch ANOVA is used; delete it before committing. Verify `stats.alexandergovern` matches R's `oneway.test(var.equal = FALSE)` on a fixture before relying on it — if it does not, implement Welch's ANOVA directly from the spec formula and record the reason in `.scratch/statistical-validation/issues/`.

- [ ] **Step 6: Run the tests**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests -q
```

Expected: all pass.

- [ ] **Step 7: Register, add cases, run, commit**

```makefile
CASES := logistic-confounding cox-adjusted km-twoarm \
         groupcompare-numeric groupcompare-categorical
```

```bash
make -C validation clean all
git add validation
git commit -m "validation: independent group comparison, numeric and categorical branches"
```

---

### Task 11: Summary (Table 1)

Table 1 is the most-opened analysis in the live traffic read, so it carries the most user-visible risk. Its distinctive feature is that the **decision** (mean ± SD vs median (IQR)) is itself an output that must be validated, not just the numbers.

**Files:**
- Create: `validation/cases/summary-table1/{data.csv,case.json}`
- Create: `validation/spec/summary-table1.md`
- Create: `validation/python/validate/summary.py`
- Create: `validation/python/tests/test_summary.py`
- Modify: `validation/harness/build-spec.mjs`, `validation/python/validate/cli.py`, `validation/Makefile`, `validation/compare/compare.py`

**Interfaces:**
- Produces: `summarize(df, variables, group=None) -> dict` with `rows`
  (`[{variable, kind, cells: {group: str}}]`) where `kind` is `"mean"` or `"median"`.

- [ ] **Step 1: Create the case**

```bash
mkdir -p validation/cases/summary-table1
cp tests/testthat/fixtures/summary-demo.csv validation/cases/summary-table1/data.csv
head -1 validation/cases/summary-table1/data.csv
```

- [ ] **Step 2: Write `validation/spec/summary-table1.md` — the decision rule is the spec**

```markdown
## Choosing mean ± SD vs median (IQR)
For each continuous variable, in this order:

1. If n < 3, or the variable has fewer than 3 distinct values, use
   **median (IQR)**.
2. Otherwise, if n > 300: use **mean ± SD** when |skewness| < 1, else
   **median (IQR)**. Do not run a normality test at this size.
3. Otherwise, run a Shapiro-Wilk test. Use **mean ± SD** when its p-value is
   >= 0.05 **and** |skewness| < 1. Otherwise use **median (IQR)**.

Skewness is the population (biased) third standardised moment: the mean of
cubed deviations divided by the cube of the square root of the mean squared
deviation. It is not the sample-corrected G1.

## Formatting
Every reported number is rounded to **3 significant figures** with trailing
zeros dropped. Mean cells read "M ± SD" where SD is the sample standard
deviation (denominator n - 1). Median cells read "Q2 (Q1–Q3)" where the
quartiles use linear interpolation between order statistics (R's type 7).
Categorical cells read "count (percent%)".

When grouped, the choice of mean vs median is made once per variable across
all groups combined, then applied to every group's cell.
```

- [ ] **Step 3: Write the failing test**

Create `validation/python/tests/test_summary.py`:

```python
import numpy as np
import pandas as pd
from validate.summary import decide, fmt_num, summarize


def test_few_distinct_values_forces_median():
    assert decide(np.array([1.0, 1.0, 2.0]))["kind"] == "median"


def test_large_symmetric_sample_uses_mean_without_shapiro():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 400)
    assert decide(x)["kind"] == "mean"


def test_large_skewed_sample_uses_median():
    rng = np.random.default_rng(1)
    x = rng.exponential(1.0, 400)
    assert decide(x)["kind"] == "median"


def test_three_significant_figures_with_trailing_zeros_dropped():
    assert fmt_num(12.3456) == "12.3"
    assert fmt_num(1234.5) == "1230"
    assert fmt_num(0.00123456) == "0.00123"
    assert fmt_num(2.50) == "2.5"
    assert fmt_num(2.0) == "2"


def test_median_cell_uses_type_7_quartiles():
    df = pd.DataFrame({"x": [str(v) for v in [1, 2, 3, 4, 5, 6, 7, 8, 9]]})
    out = summarize(df, ["x"])
    row = out["rows"][0]
    if row["kind"] == "median":
        # numpy linear == R type 7: Q1 = 3, Q2 = 5, Q3 = 7
        assert row["cells"]["Overall"] == "5 (3–7)"
```

- [ ] **Step 4: Run it to verify it fails**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests/test_summary.py -q
```

Expected: `ModuleNotFoundError: No module named 'validate.summary'`.

- [ ] **Step 5: Write `summary.py`**

```python
"""Independent Table 1 per validation/spec/summary-*.md."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .io import to_numeric


def fmt_num(v: float) -> str:
    """3 significant figures, trailing zeros dropped, never scientific."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    if v == 0:
        return "0"
    exp = int(np.floor(np.log10(abs(v))))
    decimals = max(0, 2 - exp)
    s = f"{round(v, decimals):.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def skewness(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    if len(x) < 3:
        return float("nan")
    m = x.mean()
    s = np.sqrt(np.mean((x - m) ** 2))
    if s == 0:
        return 0.0
    return float(np.mean((x - m) ** 3) / s**3)


def decide(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3 or len(np.unique(x)) < 3:
        return {"kind": "median", "reason": "too few distinct values"}
    sk = skewness(x)
    if n > 300:
        if abs(sk) < 1:
            return {"kind": "mean", "reason": f"symmetric (skewness {sk:.1f})"}
        return {"kind": "median", "reason": f"skewed (skewness {sk:.1f})"}
    p = float(stats.shapiro(x).pvalue)
    if p >= 0.05 and abs(sk) < 1:
        return {"kind": "mean", "reason": f"Shapiro-Wilk p = {p:.3f}"}
    return {"kind": "median", "reason": f"Shapiro-Wilk p = {p:.3f}"}


def _cell(x: np.ndarray, kind: str) -> str:
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return "—"
    if len(x) == 1:
        return fmt_num(float(x[0]))
    if kind == "mean":
        return f"{fmt_num(float(x.mean()))} ± {fmt_num(float(np.std(x, ddof=1)))}"
    q1, q2, q3 = np.quantile(x, [0.25, 0.5, 0.75], method="linear")
    return f"{fmt_num(float(q2))} ({fmt_num(float(q1))}–{fmt_num(float(q3))})"


def summarize(df: pd.DataFrame, variables: list[str], group: str | None = None):
    groups = (df[group].astype(str) if group
              else pd.Series(["Overall"] * len(df), index=df.index))
    levels = sorted(groups.unique())
    rows = []
    for var in variables:
        numeric = to_numeric(df[var])
        if not numeric.isna().any():
            d = decide(numeric.to_numpy())
            rows.append({
                "variable": var, "kind": d["kind"], "reason": d["reason"],
                "cells": {g: _cell(numeric[groups == g].to_numpy(), d["kind"])
                          for g in levels},
            })
        else:
            for lvl in sorted(df[var].astype(str).unique()):
                cells = {}
                for g in levels:
                    sub = df[groups == g][var].astype(str)
                    k = int((sub == lvl).sum())
                    pct = 100 * k / len(sub) if len(sub) else float("nan")
                    cells[g] = f"{k} ({fmt_num(pct)}%)"
                rows.append({"variable": f"{var}: {lvl}", "kind": "count",
                             "reason": "", "cells": cells})
    return {"rows": rows, "n": int(len(df)), "levels": levels}
```

- [ ] **Step 6: Run the tests**

```bash
cd validation/python && ../.venv/bin/python -m pytest tests -q
```

Expected: all pass. If `fmt_num` disagrees with R's `signif(v, 3)` on a boundary value, add the failing value as a test case and fix `fmt_num` — half-to-even vs half-away-from-zero rounding at the third significant figure is a real difference and belongs in the findings if it survives.

- [ ] **Step 7: Extend the comparator for cell tables and the decision**

In `compare.py`, add a branch for `display.kind == "table1"` comparing each `{variable, group}` cell string exactly, and comparing `kind` (mean vs median) as its own quantity with code `DECISION_MISMATCH` mapped to the defect class. A wrong choice of summary statistic is a defect even when both numbers are individually correct.

- [ ] **Step 8: Add the case, run, commit**

```makefile
CASES := logistic-confounding cox-adjusted km-twoarm \
         groupcompare-numeric groupcompare-categorical summary-table1
```

```bash
make -C validation clean all
git add validation
git commit -m "validation: independent Table 1 including the mean-vs-median decision"
```

---

### Task 12: webR tier — proving the browser did not change the numbers

Everything so far ran native R. This task checks the claim that only this product has to make: that R compiled to WebAssembly returns the same numbers as R. wasm has no 80-bit extended precision, so R's `long double` accumulators fall back to double, and webR ships reference BLAS/LAPACK rather than Accelerate. Iterative fits are where drift would appear.

This tier does **not** run in CI (Playwright downloads webR — slow and flaky, per `CLAUDE.md`). It is a release gate, run by hand.

**Files:**
- Create: `tests/e2e/validation-webr.spec.js`
- Modify: `validation/build_scorecard.py` (a webR tier section)

- [ ] **Step 1: Write the e2e test**

```javascript
// tests/e2e/validation-webr.spec.js
// Release gate, not CI. Runs each validation case through the real browser
// runtime and compares against the native-R result the harness already stored.
const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

const RESULTS = path.join(__dirname, "..", "..", "validation", "results");
const CASES = ["logistic-confounding", "cox-adjusted"];

for (const id of CASES) {
  test(`webR reproduces native R for ${id}`, async ({ page }) => {
    test.setTimeout(600000);
    const spec = fs.readFileSync(path.join(RESULTS, `${id}.spec.json`), "utf8");
    const native = JSON.parse(
      fs.readFileSync(path.join(RESULTS, `${id}.figura.json`), "utf8")
    );

    await page.goto("/");
    // Wait for the worker to finish booting webR before injecting a spec.
    await expect(page.locator("#preview")).toBeVisible();

    const out = await page.evaluate(async (specJson) => {
      const { runSpec } = await import("./worker-bridge.js");
      return runSpec(specJson);
    }, spec);

    expect(out.ok).toBe(true);
    // The displayed table is the contract; compare it character for character.
    const tsvOf = (t) => t.split("\n\n")[0];
    expect(tsvOf(out.text)).toBe(tsvOf(native.text));
  });
}
```

- [ ] **Step 2: Run it and see how it fails**

```bash
rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/validation-webr.spec.js
```

Expected: FAIL — there is no `worker-bridge.js` exposing `runSpec` to the page.

- [ ] **Step 3: Drive the app through its real UI instead**

Rather than add a test-only bridge into `web/` (which would violate the "do not modify `web/`" constraint and ship dead code), replace the `page.evaluate` block with the same UI flow the existing `logistic-guided.spec.js` uses: navigate to `#logistic/analyze`, upload `validation/cases/<id>/data.csv` via `setInputFiles`, set the roles through the column picker, run, and read `#stats` textContent. Copy the selector patterns from `tests/e2e/logistic-guided.spec.js` — that file is the reference for how these controls are addressed.

Compare the parsed TSV rows against `native.text` cell by cell, and report any difference as a `WEBR_DRIFT` finding rather than failing the test outright, so a first run produces a measured number instead of a red X.

- [ ] **Step 4: Run and record the result**

```bash
rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/validation-webr.spec.js
```

Write the outcome into `validation/results/webr-tier.json` as `{cases: [{id, identical: bool, differing_cells: [...]}], runtime: "webR <version>", date: "<ISO date>"}` and surface it in the scorecard as its own section.

If every displayed cell is identical, that is the headline: **webR reproduced native R exactly at the reported precision.** If cells differ, that is a finding worth publishing honestly, with the magnitude stated.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/validation-webr.spec.js validation/results/webr-tier.json validation/build_scorecard.py
git commit -m "validation: webR vs native R tier as a release gate"
```

---

### Task 13: CI wiring and the public validation page

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `web/validation.html`
- Modify: `web/index.html` (one link)
- Modify: `web/sw.js` (`CACHE` bump)
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the validation job to CI**

In `.github/workflows/ci.yml`, add a job that runs after the existing R and JS jobs:

```yaml
  validation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: r-lib/actions/setup-r@v2
      - uses: r-lib/actions/setup-r-dependencies@v2
        with: { extra-packages: any::devtools }
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: python -m venv validation/.venv
      - run: validation/.venv/bin/pip install -r validation/requirements.txt
      - run: make -C validation all
      - uses: actions/upload-artifact@v4
        with:
          name: validation-scorecard
          path: validation/results/scorecard.html
```

`make -C validation all` exits non-zero when the comparator finds a defect, so a statistical regression fails the build the same way a unit-test failure does.

- [ ] **Step 2: Verify CI passes**

```bash
git push
gh run watch
```

Expected: the `validation` job green, with `scorecard.html` downloadable from the run's artifacts.

- [ ] **Step 3: Generate the user-facing page**

Extend `validation/build_scorecard.py` with a `--web` flag writing `web/validation.html` using the app's own tokens (link `styles.css` rather than inlining the scorecard CSS, so the page cannot drift from the shipped design), and lead with the plain-language claim:

> Every number Figura reports is re-derived by a separately written Python
> implementation working from a written analysis spec, from the same raw file.
> This page is the comparison. It is regenerated on every change.

Then the tiles, the findings table, and a short "how to check this yourself" section pointing at the `.R` download: run the exported script in your own R and confirm the numbers match.

- [ ] **Step 4: Link it from the app and bump the cache**

Add one link in `web/index.html`'s nav-pane foot, beside the existing `.fb-copy` feedback affordance. Bump `CACHE` in `web/sw.js` (`figura-vN` → `figura-vN+1`) because the precached shell changed; remember the shell needs two reloads to swap.

- [ ] **Step 5: Verify locally**

```bash
rm -rf web/R && cp -R R web/R && npm run serve
```

Open http://localhost:8321, confirm the link reaches the validation page and the page renders in both light and dark.

- [ ] **Step 6: Document it in CLAUDE.md**

Add a section under Commands:

```markdown
## Statistical validation

`make -C validation all` re-derives every reported statistic in an independent
Python implementation and writes `validation/results/scorecard.html`. It runs
in CI and fails the build on a statistical regression. **The Python side is
written from `validation/spec/*.md` only — never port it from `R/`, and never
"fix" a Python difference by copying the R.** The whole point is that the two
readings are independent. See `validation/README.md`.

The webR-vs-native-R tier (`tests/e2e/validation-webr.spec.js`) is a release
gate, not CI, for the same reason the other e2e specs are excluded.
```

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml web/validation.html web/index.html web/sw.js CLAUDE.md validation
git commit -m "validation: CI gate and public validation page"
```

---

## Self-Review

**Spec coverage.** Each of the five analyses that report numbers has a case, a prose spec, an independent Python implementation, and a comparator path: logistic (Tasks 1–7), Cox (8), KM and log-rank (9), group comparison, both branches (10), Table 1 including the mean-vs-median decision (11). Explore is out of scope by design — it is a plot builder whose only numeric output is the summary path already covered by Task 11. The glue layer is covered because Path A starts from the raw CSV through the shipped `parseCsv` and spec builders (Task 2), and Path B starts from the same raw CSV (Task 5). The script-reproducibility claim is covered by Task 4. The wasm-runtime claim is covered by Task 12. Publication is covered by Task 13.

**Known gaps, stated rather than hidden.** Full-precision comparison covers **adjusted** model estimates only, because those are what the exported script leaves in scope as `fit`; unadjusted cells are compared at display precision. The C-statistic, VIF, Cook's distance, and `cox.zph` diagnostics are computed by Path B but not yet compared — they are advisory text, not gating numbers, and comparing them is a natural follow-on. Task 12 measures webR drift for two cases, not all six.

**Interface consistency.** `fit_logistic`, `fit_cox`, `fit_km`, `compare_groups`, and `summarize` all return a dict with `n_dropped`; the model fitters additionally return `terms` on the ratio scale plus `n` and `n_event`, which is what `compare_case` reads. `_design` is defined in `logistic.py` and imported by `cox.py` — one definition of the treatment-contrast rule, so the two analyses cannot drift. `format_ratio_cell` exists in both `parse-cells.mjs` (JS) and `compare.py` (Python) because the two languages need it independently; both are pinned by tests against the same literal strings, which is the point of duplicating rather than sharing it.

**Execution note.** Tasks 5, 8, 9, 10, and 11 are the independence-critical ones. Dispatch each to a fresh subagent whose prompt states the prohibition on reading `R/` and `web/`. Tasks 2, 3, 4, 6, 7, 12, and 13 are Path A and harness work where reading the app is expected and necessary.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 21 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**Findings summary:** Architecture 4 (independence integrity, per-figure exact harvest, comparator per-kind dispatch, CI/evidence freshness) · Code quality 3 (scipy pin vs spec, group-centered normality, NA-string divergence) · Tests 3 (comparator/scorecard spine bundle, Dunn specification, statistical edge bundle) · Performance 1 (CI pip cache) · Outside voice 10 (context-leak sanitization, spec provenance, comparator ground-truthing vs real table shape, CI deps, evidence lifecycle, dead JS module, dirty-CSV cases, page coverage honesty). All 21 resolved; every decision took the complete option, and review decisions D23–D25 expanded scope (diagnostics comparison, shared-webR-boot + full-roster webR tier, sequenced Task 14 NA fix).

**BINDING AMENDMENTS (apply to the task bodies before execution):**
- **A1 (D4+D15):** Strip inline Path B implementations from Tasks 5/8/9/10/11 — keep interfaces, acceptance tests, spec pointers. Each Path B dispatch runs in a sanitized scratch directory outside the repo containing only `validation/spec/<case>.md`, `requirements.txt`, and the python skeleton (no CLAUDE.md, no repo context); completed module copied back and committed.
- **A2 (D5):** Task 4's `run-script.R` becomes a per-figure harvest dispatch, reading `summary()` columns **by name** (glm: `Estimate`/`Std. Error`; coxph: `coef`/`se(coef)`); KM harvests the survfit step function; groupcompare harvests `ht$p.value` + effect; summary skips model harvest; `n_dropped` emitted wherever derivable.
- **A3 (D6+D17):** Task 6's comparator dispatches on `display.kind`. Ratio tables parsed with the real row model: `"(reference:"` header rows expected-empty (asserted), indented level rows keyed `covariate:level` (never bare level). Dispositions for `not reliably estimated` and `1 (reference)` cells (both-paths-agree = PASS). Unadjusted column compared at display precision alongside adjusted. KM compares medians + logrank_p + full curve; groupcompare compares test_name/p/effect + significant-pair set. `SCRIPT_DIVERGENCE` emitted mechanically (exact harvest rendered through the display rule vs the screen). Every unmatched term/curve point/expected key is a finding — no silent `continue`. `exact_targets` in case.json is a wired contract: unmet target = finding; per-case minimum-comparison counts asserted in tests. Exact tier compares `se` explicitly; report notes lo/hi are derived (partly tautological).
- **A4 (D7+D14+D18+D19):** CI runs `make -C validation clean all`; `extra-packages: any::devtools, local::.`; setup-python gains `cache: "pip"` + `cache-dependency-path: validation/requirements.txt`. Git-track only `findings.json`, `scorecard.html`, `webr-tier.json`; gitignore `results/*.done` and raw per-case JSONs (platform-BLAS churn). CI freshness gate: regenerate then `git diff --exit-code` on the tracked three + `web/validation.html`. Makefile gains code prerequisites (`R/`, `harness/`, `python/`, `spec/`).
- **A5 (D8):** Bump the scipy pin to a release with `f_oneway(equal_var=False)` and r×c `fisher_exact`. Spec names "Welch's heteroscedastic F (Welch 1951; R's `oneway.test` default)". Two R-precomputed acceptance tests: 3-group unequal-variance Welch p; r×c small-cell Fisher p.
- **A6 (D9):** Task 10 spec: normality assessed on **group-mean-centered** values, then the full decision rule verbatim (n<3 or <3 distinct; n>300 → |skewness|<1 alone; else Shapiro p≥0.05 AND |skewness|<1). Rule added to Global Constraints pinned conventions. Acceptance test: two well-separated normal groups choose the parametric branch.
- **A7 (D10+D21):** Cases gain `logistic-dirty` (NA strings + CRLF + trailing whitespace + numeric-looking categorical) and `groupcompare-dirty` (numeric-looking categorical outcome). All specs state: blank = missing, literal `"NA"` is an ordinary value; `parseCsv` has no quoting support (app-level limitation, stated not rediscovered). Expected outcome of the NA dirt: a `SCRIPT_DIVERGENCE` finding dispositioned under `.scratch/statistical-validation/issues/`.
- **A8 (D11+D13):** Test bundles: comparator classes (COUNT_MISMATCH, SCRIPT_DIVERGENCE, DECISION_MISMATCH, per-kind dispatch, unmatched findings, malformed-cell fallback), `build_scorecard` smoke + HTML-escaping, `display_label` pinned to real Figura row labels; statistical edges (logistic separation → "not reliably estimated", Cox tied-times vs R-precomputed Efron HR, KM shared-timestamp event+censor convention, Table 1 grouped decide-once + categorical count(%) + 3≤n≤300 Shapiro path, treatment-dummies ordering/missing-reference, build-spec unknown-figure error).
- **A9 (D12):** Spec describes Dunn fully: pairwise z from the shared overall ranking, tie-corrected variance, BH adjustment, run only when omnibus p < 0.05 (Tukey HSD likewise gated). Comparator checks the significant-pair set. Two R-precomputed tests (Tukey pairs; Dunn pairs).
- **A10 (D13):** Task 12 specifies the UI-flow Playwright test directly (selector patterns from `logistic-guided.spec.js`) — no throwaway worker-bridge version.
- **A11 (D16):** Logistic/cox specs add the reference-fallback rule (declared reference absent after filtering → most frequent level, per `R/logistic.R:95-98`). Validation page adds a "what this does and does not prove" provenance paragraph (spec transcribes declared conventions; independence is at implementation level).
- **A12 (D20):** `parse-cells.mjs` keeps `parseRatioTable` (consumed by Task 12's cell comparison); `formatRatioCell` dropped (compare.py's pinned copy is the operative mirror).
- **A13 (D22):** Task 13's page gains a per-analysis "what is compared, at what precision" coverage table; headline tightened ("every displayed statistic, adjusted estimates verified to 1e-6"); webR section shows runtime version + run date from `webr-tier.json` ("not yet run for this release" as the empty state).
- **A14 (D23, scope-in):** Diagnostics comparison built into this plan: C-statistic and VIF compared numerically at 1e-6; Cook's-distance and EPV advisory notes compared as triggered/not-triggered state; `cox.zph` global + per-covariate p with the transform pinned in the spec (R default `transform="km"` differs from lifelines' default).
- **A15 (D24, scope-in):** New task before Task 12: shared-webR-boot e2e refactor (Playwright serial mode/shared fixture; KM + summary suites green before AND after — it touches the regression-sensitive KM spec). Task 12 then runs the **full case roster** in one booted session. Mark the existing TODOS.md shared-boot entry absorbed by this plan.
- **A16 (D25, scope-in):** New Task 14 (after Task 13): app-side fix for the exported-script NA divergence — `R/script.R`'s `read.csv` matches `parseCsv`'s blank-only missing rule — in a **separate commit after** the harness finding is caught and dispositioned (evidence preserved), with a testthat regression test, the full R suite gate, and a pipeline re-run so the scorecard shows the finding as fixed.
- **A17 (D27, isolation — supersedes the sequencing in A15/A16):** The validation directory is **`stats-validation/`** (rename `validation/` throughout: file structure, Makefile invocations `make -C stats-validation`, `.venv` path, RESULTS paths, CI paths). Execution is two-phased:
  - **Phase 1 (Tasks 1–12 + A14 diagnostics + the webR tier):** every created file lives under `stats-validation/`. The webR-tier Playwright spec and its own config live in `stats-validation/e2e/` and run via `npx playwright test --config stats-validation/e2e/playwright.config.js` — no new files in `tests/`. **Boundary invariant (checkable): `git diff` outside `stats-validation/` shows only the additive `ci.yml` validation job and two `.gitignore` lines.** `R/`, `web/`, `package.json`, `CLAUDE.md`, and `tests/` are untouched — harness `*.test.mjs` run from the validation Makefile/CI, a deliberate documented exception to the repo's test:unit-chain convention (chain integration moves to Phase 2). Run Phase 1 sessions under `/freeze stats-validation` for mechanical enforcement.
  - **Phase 2 (starts only on an explicit user go-ahead; separate commits):** Task 13 (`web/validation.html`, nav link, sw CACHE bump, CLAUDE.md docs, test:unit chain integration), the A15 shared-webR-boot refactor of existing e2e specs + full-roster webR run, and the A16 Task 14 `R/script.R` NA fix.
- **Diagrams:** plan gains a pipeline ASCII diagram; inline diagram comments in `compare.py` (dispatch + finding-class decision tree) and `run-script.R` (per-figure harvest).

**OUTSIDE VOICE:** Claude subagent (Codex CLI present but vendored binary missing — repair with `npm install -g @openai/codex`). 10 findings, all adopted after per-item review; cross-model tensions on parse-cells (resolved: wire parser, drop formatter) and dirty-case count (resolved: two targeted cases over per-analysis).

**VERDICT:** ENG CLEARED — ready to implement once the binding amendments above are folded into the task bodies. Eng Review is the only gating review; CEO/Design optional (validation page is a simple static page on existing tokens).

NO UNRESOLVED DECISIONS

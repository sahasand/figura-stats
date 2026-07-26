// stats-validation/e2e/webr-parity.spec.js
//
// THE ONE TIER NO OTHER VALIDATION COVERS: did compiling R to WebAssembly
// change the numbers?
//
// Everything else in stats-validation/ runs native R (`Rscript`) and compares
// it against an independently written Python implementation. That proves the
// statistics are right; it says nothing about the runtime the user actually
// gets. In the browser, R runs under webR: wasm has no 80-bit extended
// precision (R's `long double` accumulators fall back to plain double) and
// webR ships reference BLAS/LAPACK rather than Accelerate. Iteratively fitted
// models — Cox's Newton-Raphson, logistic's IRLS — are where that would show.
//
// HOW TO RUN (release gate, hand-run, NOT in CI, NOT in `make all`/`make test`
// — it needs a browser and the network):
//
//     rm -rf web/R && cp -R R web/R
//     npx playwright test --config stats-validation/e2e/playwright.config.js
//
// or, equivalently, `make -C stats-validation webr`. Both run from the REPO
// ROOT. `npm run serve` serves web/, and web/R/ is a gitignored build copy of
// R/ that must be refreshed first or the worker fetches stale (or missing) R
// sources — the copy step is not optional and `rm -rf` first is not optional
// either (a bare `cp -R R web/R` nests into an existing directory).
//
// WHAT IT DOES NOT DO. It adds no bridge, hook, or export to web/ (A10). It
// drives the shipped UI exactly as tests/e2e/logistic-guided.spec.js and
// tests/e2e/cox-guided.spec.js do — upload, map roles, confirm the event
// value, set reference levels and increments, click render, read #stats — so
// what it measures is the app as shipped, not a test harness wearing the app's
// clothes.
//
// COMPARISON, NOT ASSERTION. A cell that differs from native R is RECORDED as
// a WEBR_DRIFT finding in results/webr-tier.json, not thrown. A first run must
// produce a measured number, not a red X whose size nobody knows. Hard
// PRECONDITIONS are still asserted loudly — the page rendered, the table
// parsed, the row count matched — because a harness that silently measured
// nothing must never be mistaken for a run that found no drift. BUT a
// precondition failure on one case no longer destroys the whole run's
// evidence: it is caught by `runCase` (compare-text.mjs) and published as an
// honest `{id, aborted: true, reason}` case entry, so the scorecard can
// distinguish "ran and hit structural drift" from "never run" — and the test
// still fails loudly afterward (see the end of the test body).
//
// The comparator itself (`compareText`), its cell-kind classification, and
// the abort wrapper live in ./compare-text.mjs — a plain-Node module with no
// Playwright dependency, specifically so it can be pinned by a plain node
// test (compare-text.test.mjs) that `make -C stats-validation test` runs on
// every CI build even though this Playwright spec itself never does.
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { pathToFileURL } = require("url");

const VALIDATION = path.join(__dirname, "..");
const REPO_ROOT = path.join(VALIDATION, "..");
const RESULTS = path.join(VALIDATION, "results");
const OUT = path.join(RESULTS, "webr-tier.json");

// The webR module URL the shipped worker imports. Kept here only to identify
// the runtime in the evidence file; web/worker.js remains the single place it
// is actually loaded from, and the assertion below fails if the two drift
// apart, so this can never quietly describe a runtime the app does not use.
const WEBR_MODULE = "https://webr.r-wasm.org/latest/webr.mjs";

// The two ratio-table cases that have a full native-R display artifact to
// compare against. The rest of the roster is Phase 2: adding it needs the
// shared-boot refactor of the existing suites (A15), not more cases here.
const CASES = [
  { id: "logistic-confounding", nav: /logistic regression/i, kind: "logistic" },
  { id: "cox-adjusted", nav: /cox regression/i, kind: "cox" },
];

// ---------------------------------------------------------------------------

function readCase(id) {
  const dir = path.join(VALIDATION, "cases", id);
  return {
    def: JSON.parse(fs.readFileSync(path.join(dir, "case.json"), "utf8")),
    csv: path.join(dir, "data.csv"),
  };
}

// The native-R side of the comparison: the `text` field of the display
// artifact `make all` already publishes. Nothing is recomputed here.
function nativeText(id) {
  const p = path.join(RESULTS, `${id}.figura.json`);
  if (!fs.existsSync(p)) {
    throw new Error(
      `${p} does not exist. The webR tier compares against the native-R ` +
      `display artifact; run \`make -C stats-validation all\` first.`);
  }
  return JSON.parse(fs.readFileSync(p, "utf8")).text;
}

// ---------------------------------------------------------------------------
// Driving the shipped UI. These mirror tests/e2e/{logistic,cox}-guided.spec.js
// selector for selector; the roles, event value, reference levels and
// increments come from the case.json the native-R run used, so the two paths
// cannot silently diverge into different models.

async function openAnalyze(page, navPattern) {
  await page.getByRole("button", { name: navPattern }).click();
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await expect(page.locator("#csv")).toBeVisible();
}

async function driveLogistic(page, def, csv) {
  await expect(page.locator("#logistic-config")).toBeHidden();
  await page.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#logistic-config")).toBeVisible();

  const analyze = page.locator("#panel-analyze");
  await analyze.locator("#cp_outcome").selectOption(def.roles.outcome);
  // The event dropdown only fills once the outcome role is mapped, and the
  // reference/increment controls are re-rendered on every column-picker
  // change — so covariates must be chosen before either is touched.
  await analyze.locator("#cp_covariates").selectOption(def.roles.covariates);
  await analyze.locator("#logistic-event").selectOption(def.options.event_value);
  for (const [cov, level] of Object.entries(def.options.ref_levels || {})) {
    await analyze.locator(`#logistic-refs select[data-cov="${cov}"]`).selectOption(level);
  }
  for (const [cov, step] of Object.entries(def.options.increments || {})) {
    await analyze.locator(`#logistic-increments input[data-cov="${cov}"]`).fill(String(step));
  }
  await analyze.locator("#logistic-render").click();
}

async function driveCox(page, def, csv) {
  await expect(page.locator("#cox-config")).toBeHidden();
  await page.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#cox-config")).toBeVisible();

  const analyze = page.locator("#panel-analyze");
  await analyze.locator("#cp_time").selectOption(def.roles.time);
  await analyze.locator("#cp_status").selectOption(def.roles.status);
  await analyze.locator("#cp_covariates").selectOption(def.roles.covariates);
  await analyze.locator("#cox-event").selectOption(def.options.event_value);
  for (const [cov, level] of Object.entries(def.options.ref_levels || {})) {
    await analyze.locator(`#cox-refs select[data-cov="${cov}"]`).selectOption(level);
  }
  // Cox's analyze form has no per-covariate increment control (only logistic
  // does); a Cox case that declared one would be silently unhonoured, so say so.
  expect(def.options.increments, "cox has no increment control in the UI").toBeUndefined();
  await analyze.locator("#cox-render").click();
}

const DRIVERS = { logistic: driveLogistic, cox: driveCox };

async function readRenderedText(page) {
  // The table is the visible proof the fit completed; #stats is the artifact
  // being compared. Wait on the TSV header rather than on "not empty", so a
  // leftover render from the previous case can never be read as this one's.
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 600000 });

  const stats = page.locator("#stats");
  // Wait for EITHER a real render or an error state, whichever comes first —
  // via one poll, not two sequential waits. Previously this was
  // `toContainText("Characteristic", {timeout: 600000})` FOLLOWED BY
  // `not.toHaveClass(/error/)`: an error state does not contain
  // "Characteristic", so a genuine app error would burn the entire 10-minute
  // budget on the first wait before the test ever reached the class check —
  // making that guard effectively unreachable in any useful time. Polling for
  // both conditions together means an error surfaces in seconds, not minutes.
  await expect
    .poll(
      async () => {
        const cls = (await stats.getAttribute("class")) || "";
        if (/error/.test(cls)) return "error";
        const text = (await stats.textContent()) || "";
        return text.includes("Characteristic") ? "ready" : "pending";
      },
      {
        timeout: 600000,
        message: "#stats never rendered a table nor an error state within the budget",
      },
    )
    .not.toBe("pending");

  const cls = (await stats.getAttribute("class")) || "";
  if (/error/.test(cls)) {
    throw new Error(
      `#stats rendered an error state (class="${cls}"): ${await stats.textContent()}`,
    );
  }
  return await stats.textContent();
}

// ---------------------------------------------------------------------------
// Runtime identification. web/worker.js imports webR from the CDN's `latest`
// channel and the page never prints a version, so the version is read off the
// runtime's OWN API: `new WebR()` sets `.version`/`.versionR` as its first two
// statements, before it creates any channel. The probe instance is constructed
// against a deliberately nonexistent baseUrl and is never `init()`ed, so it
// spawns no second R and downloads nothing. Falls back to naming what it can
// identify rather than inventing a version.
async function detectRuntime(page, cdnUrls) {
  const probe = await page.evaluate(async (moduleUrl) => {
    try {
      const mod = await import(moduleUrl);
      const w = new mod.WebR({ baseUrl: location.origin + "/__webr_version_probe__/" });
      return { ok: true, version: w.version, versionR: w.versionR };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  }, WEBR_MODULE);

  const loaded = [...new Set(cdnUrls)];
  if (probe.ok && probe.version) {
    return {
      runtime: `webR ${probe.version} (R ${probe.versionR})`,
      runtime_source:
        `read from the WebR instance's own version fields, from the module the ` +
        `app loads (${WEBR_MODULE}); the page itself prints no version string. ` +
        `Runtime binaries served from ${loaded.filter((u) => u.includes("webr.r-wasm.org")).length} ` +
        `webr.r-wasm.org request(s) during this run.`,
    };
  }
  // Honest degradation: name the channel and the R library path actually
  // requested rather than guessing a version number.
  const repo = loaded.find((u) => u.includes("repo.r-wasm.org")) || "";
  const rMinor = (repo.match(/contrib\/(\d+\.\d+)\//) || [])[1];
  return {
    runtime: `webR from ${WEBR_MODULE} (version not exposed by the page` +
      (rMinor ? `; R ${rMinor}.x per the package repo path` : "") + ")",
    runtime_source:
      `the version probe failed (${probe.error || "no version field"}), so this ` +
      `field names only what the run's own network requests identify.`,
  };
}

// ---------------------------------------------------------------------------

// Repo HEAD at run time, so a later `make all` that changes native output
// makes previously-published webR evidence visibly stale (it will name a
// commit whose R/web state no longer matches what is on disk). Read via `git`
// rather than any bundled version, because the thing that must be pinned is
// the actual working tree the browser was driven against.
function repoCommit() {
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { cwd: REPO_ROOT })
      .toString()
      .trim();
  } catch (err) {
    return null; // honest absence beats a fabricated hash
  }
}

// The honest "36 cells" phrasing: not every compared cell is a number that
// could drift. Aggregates the per-case cell-kind breakdown compareText
// produces into one human-readable sentence for the scorecard and the
// evidence file, so a reader cannot come away thinking "N numbers matched"
// when most of N is static labels, headers, and intentionally-blank cells.
function buildCellsNote(completedCases, totalCompared, totalWithNumbers) {
  if (completedCases.length === 0) {
    return "No case completed a comparison this run — see each case's " +
      "\"reason\" for why, in cases[].";
  }
  const agg = completedCases.reduce(
    (a, c) => ({
      header: a.header + c.cell_kinds.header,
      term: a.term + c.cell_kinds.term,
      value: a.value + c.cell_kinds.value,
      empty: a.empty + c.cell_kinds.empty,
      methods: a.methods + c.cell_kinds.methods,
      methods_with_number: a.methods_with_number + c.cell_kinds.methods_with_number,
    }),
    { header: 0, term: 0, value: 0, empty: 0, methods: 0, methods_with_number: 0 },
  );
  return (
    `${totalCompared} = ${agg.value} numeric value cells + ${agg.methods} ` +
    `methods sentences (${agg.methods_with_number} containing a number) + ` +
    `${agg.term} term labels + ${agg.header} header line(s) + ${agg.empty} ` +
    `empty-vs-empty placeholder cells (a categorical covariate's own ` +
    `reference-level row). Only the ${totalWithNumbers} numeric cells (the ` +
    `value cells plus the numeric-bearing methods sentences) can actually ` +
    `show wasm-vs-native drift — the term labels, header line(s), and empty ` +
    `cells are static or intentionally blank.`
  );
}

test("webR renders the same numbers native R does", async ({ page }) => {
  // compare-text.mjs is ESM and this spec is CommonJS (the repo's
  // package.json has no "type": "module"), so it is imported dynamically.
  const { compareText, runCase, nativeDigest } = await import(
    pathToFileURL(path.join(__dirname, "compare-text.mjs")).href);

  // STALE-EVIDENCE DELETE, the same precedent the Makefile's `all` target
  // applies to findings.json: if this run dies before it writes, there must be
  // NOTHING to publish rather than the previous run's numbers sitting under
  // this run's date. The scorecard's honest empty state is the correct output
  // of a run that did not finish.
  fs.rmSync(OUT, { force: true });

  // The evidence file names a runtime; that name is only trustworthy if this
  // spec is looking at the same module the shipped worker imports. Reading
  // web/worker.js (read-only — Phase 1 never edits web/) pins the two together,
  // so a CDN change in the app can never leave this file quietly describing a
  // runtime the user no longer gets.
  const workerSrc = fs.readFileSync(
    path.join(VALIDATION, "..", "web", "worker.js"), "utf8");
  expect(workerSrc, "web/worker.js no longer imports the webR module this " +
    "tier identifies; update WEBR_MODULE").toContain(WEBR_MODULE);

  const cdnUrls = [];
  // Context-level, not page-level: webR is loaded and driven entirely from a
  // Web Worker, and worker requests are reported on the context.
  page.context().on("request", (r) => {
    if (r.url().includes("r-wasm.org")) cdnUrls.push(r.url());
  });

  // ONE page load for both cases: the app is a single-page shell whose nav
  // buttons swap the analysis without a reload, so the webR runtime booted for
  // the first case is the same one that fits the second.
  await page.goto("/");

  const cases = [];
  for (const c of CASES) {
    // Wrapped in runCase: a precondition failure (or any other exception) on
    // THIS case must not erase the evidence for the other case, and must not
    // stop webr-tier.json from being written at all — it becomes an honest
    // `{id, aborted: true, reason}` entry instead. The run still fails loudly
    // below, after the file is written.
    const result = await runCase(c.id, async () => {
      const { def, csv } = readCase(c.id);
      // The nav button and the form driver above are a hand-written mapping;
      // case.json is the authority on what the case actually is. Check them
      // against each other so a case cannot be driven through the wrong
      // analysis's form and have the mismatch read as parity.
      expect(def.figure, `${c.id}: case.json figure vs this file's driver`)
        .toBe(c.kind);
      expect(def.display.kind, `${c.id}: not a ratio-table case`)
        .toBe("ratio_table");
      await openAnalyze(page, c.nav);
      await DRIVERS[c.kind](page, def, csv);
      const webrText = await readRenderedText(page);

      const { compared, differing, cellKinds, cellsWithNumbers } =
        compareText(nativeText(c.id), webrText);
      // Reported, never thrown: the tier's output is a measurement.
      for (const d of differing) {
        console.log(`WEBR_DRIFT ${c.id} [${d.term} / ${d.column}] ` +
          `native=${JSON.stringify(d.native)} webr=${JSON.stringify(d.webr)}`);
      }
      console.log(`${c.id}: ${compared} cells compared, ${differing.length} differing`);
      return {
        id: c.id,
        identical: differing.length === 0,
        cells_compared: compared,
        differing_cells: differing,
        cell_kinds: {
          header: cellKinds.header,
          term: cellKinds.term,
          value: cellKinds.value,
          empty: cellKinds.empty,
          methods: cellKinds.methods,
          methods_with_number: cellKinds.methodsWithNumber,
        },
        cells_with_numbers: cellsWithNumbers,
      };
    });
    if (result.aborted) {
      console.log(`WEBR_ABORT ${c.id}: ${result.reason}`);
    }
    cases.push(result);
  }

  const completed = cases.filter((c) => !c.aborted);
  const totalCellsCompared = completed.reduce((s, c) => s + c.cells_compared, 0);
  const totalCellsWithNumbers = completed.reduce((s, c) => s + c.cells_with_numbers, 0);
  // Digest over the native text actually compared, so a later `make all` that
  // changes results/<id>.figura.json's `text` makes this evidence visibly
  // stale even though the webR run itself is not repeated.
  const digestInput = completed.map((c) => ({ id: c.id, text: nativeText(c.id) }));

  const runtime = await detectRuntime(page, cdnUrls);
  fs.mkdirSync(RESULTS, { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({
    runtime: runtime.runtime,
    runtime_source: runtime.runtime_source,
    date: new Date().toISOString().slice(0, 10),
    commit: repoCommit(),
    native_digest: digestInput.length ? `sha256:${nativeDigest(digestInput)}` : null,
    cases,
    cells_compared: totalCellsCompared,
    cells_with_numbers: totalCellsWithNumbers,
    cells_note: buildCellsNote(completed, totalCellsCompared, totalCellsWithNumbers),
  }, null, 2) + "\n");
  console.log(`runtime: ${runtime.runtime}`);
  console.log(`wrote ${OUT}`);

  // LOUD FAILURE, AFTER THE WRITE: a structural precondition failure on any
  // case must still fail the run (this is a release gate; a partial run must
  // not read as "passed"), but only now — after the honest aborted record for
  // it is safely on disk — so the artifact can distinguish "ran and hit
  // structural drift" from "never run" even though the run itself failed.
  const aborted = cases.filter((c) => c.aborted);
  if (aborted.length) {
    throw new Error(
      `webR tier hit a structural precondition failure on: ` +
      `${aborted.map((c) => c.id).join(", ")}. ${OUT} was still written with ` +
      `an honest aborted record for each — see its "reason" field. This ` +
      `failure is intentional: a precondition failure must be loud.`);
  }
});

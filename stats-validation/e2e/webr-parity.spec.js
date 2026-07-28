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
// drives the shipped UI exactly as tests/e2e/{logistic,cox,km,groupcompare,
// summary}-guided.spec.js do — upload, map roles, confirm the event value, set
// reference levels and increments, tick the variable checklist, click render,
// read #stats — so what it measures is the app as shipped, not a test harness
// wearing the app's clothes.
//
// THE WHOLE ROSTER, ONE BOOT. All eight registered cases run here, in one page
// load, because a page reload throws away the Web Worker and therefore the
// booted webR runtime. Five of the eight are not ratio tables, so the
// comparison shape is chosen per case from its own `display.kind` — see
// compare-text.mjs's header for the three shapes and why they all report the
// same cell vocabulary.
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

// THE FULL ROSTER — every case results/ registers, driven in one booted
// session. `kind` is the analysis (which nav button and which form driver);
// the COMPARISON shape comes from each case.json's own `display.kind`, and the
// test body cross-checks both against case.json so a case can never be driven
// through the wrong form, or compared through a shape it did not declare.
//
// Ordered by analysis so each form is mounted once per group and the lazy
// package installs (`survival` for cox and km, `cowplot` for km) land next to
// each other. Order is a wall-clock convenience only: every case establishes
// its own state through the nav, and the run is a comparison, not a sequence.
const CASES = [
  { id: "logistic-confounding", nav: /logistic regression/i, kind: "logistic" },
  { id: "logistic-dirty", nav: /logistic regression/i, kind: "logistic" },
  { id: "cox-adjusted", nav: /cox regression/i, kind: "cox" },
  { id: "km-twoarm", nav: /kaplan-meier/i, kind: "km" },
  { id: "groupcompare-numeric", nav: /group comparison/i, kind: "groupcompare" },
  { id: "groupcompare-categorical", nav: /group comparison/i, kind: "groupcompare" },
  { id: "groupcompare-dirty", nav: /group comparison/i, kind: "groupcompare" },
  { id: "summary-table1", nav: /summary statistics/i, kind: "summary" },
];

// What "the render finished" looks like per display kind. `fig_summary`,
// `fig_cox` and `fig_logistic` put an HTML <table> in the `svg` field; km and
// group comparison return a real <svg>. Structural, never textual: a readiness
// signal that waited for a specific STRING would time out on exactly the drift
// this tier exists to record, instead of recording it.
const PREVIEW_ELEMENT = {
  ratio_table: "table",
  table1: "table",
  km_summary: "svg",
  gc_summary: "svg",
};

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

// Every case starts here. Clicking the nav button is not decoration: web/app.js
// clears #preview and #stats on a [data-figure] click and re-mounts the guided
// shell (a fresh analyze form, so the file input and the role pickers are the
// pristine ones), which is what lets eight cases share one page without
// inheriting each other's forms.
async function openAnalyze(page, navPattern) {
  await page.getByRole("button", { name: navPattern }).click();
  await page.getByRole("tab", { name: "Analyze Your Data" }).click();
  await expect(page.locator("#panel-analyze #csv")).toBeVisible();
}

// Every driver's LAST action is the render click, and nothing after it — the
// caller relies on that to catch the shell's synchronous blank-out (see
// `runAndRead`). All selectors are scoped to #panel-analyze because
// createGuidedShell mounts BOTH stage panels up front, and group comparison's
// example panel carries the same #cp_group/#cp_outcome ids the analyze form
// does (the same strict-mode fix tests/e2e/groupcompare-guided.spec.js needed).

async function driveLogistic(page, analyze, def, csv) {
  await expect(page.locator("#logistic-config")).toBeHidden();
  await analyze.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#logistic-config")).toBeVisible();

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

async function driveCox(page, analyze, def, csv) {
  await expect(page.locator("#cox-config")).toBeHidden();
  await analyze.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#cox-config")).toBeVisible();

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

async function driveKm(page, analyze, def, csv) {
  await expect(page.locator("#km-config")).toBeHidden();
  await analyze.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#km-config")).toBeVisible();

  await analyze.locator("#cp_time").selectOption(def.roles.time);
  await analyze.locator("#cp_status").selectOption(def.roles.status);
  await analyze.locator("#cp_group").selectOption(def.roles.group);
  await analyze.locator("#km-event").selectOption(def.options.event_value);

  // THE ONE FIELD THIS TIER TYPES THAT case.json DOES NOT LITERALLY DECLARE,
  // and it is a harness correctness fix rather than a nudge toward parity.
  // km-twoarm declares no `time_label`, so the spec the NATIVE run used carries
  // none and R falls back to `opts$time_label %||% "Time"` — which is printed
  // verbatim in the displayed sentence ("Standard care 26.0 Time."). The UI has
  // no way to send "no label": #tlabel always submits its contents, and it is
  // pre-filled "Months". Leaving the default would feed the browser a DIFFERENT
  // SPEC from the one native R ran and then report the inevitable
  // "Time" vs "Months" difference as wasm drift — a harness bug wearing a
  // finding's clothes. So the box is set to whatever the case declares, or to
  // R's own documented default when it declares nothing. Same spec, two
  // runtimes, which is the only comparison this tier is entitled to make.
  await analyze.locator("#tlabel").fill(def.options.time_label ?? "Time");
  // `theme` reaches only the plot (.fig_theme), never `text`; set it when the
  // case pins one so the two runs stay spec-identical anyway.
  if (def.options.theme) await analyze.locator("#theme").selectOption(def.options.theme);
  expect(def.options.ref_levels, "km has no reference-level control in the UI").toBeUndefined();
  expect(def.options.increments, "km has no increment control in the UI").toBeUndefined();
  await analyze.locator("#km-render").click();
}

async function driveGroupCompare(page, analyze, def, csv) {
  await expect(page.locator("#gc-config")).toBeHidden();
  await analyze.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#gc-config")).toBeVisible();

  await analyze.locator("#cp_group").selectOption(def.roles.group);
  await analyze.locator("#cp_outcome").selectOption(def.roles.outcome);
  // "box"/"auto" are simultaneously the form's pre-selected options and R's own
  // `%||%` fallbacks, so a case that declares neither is driven identically to
  // the spec the native run used.
  await analyze.locator("#gc-plot").selectOption(def.options.plot ?? "box");
  await analyze.locator("#gc-test").selectOption(def.options.test ?? "auto");
  expect(def.options.event_value,
    "group comparison has no event-value control in the UI").toBeUndefined();
  expect(def.options.ref_levels,
    "group comparison has no reference-level control in the UI").toBeUndefined();
  expect(def.options.increments,
    "group comparison has no increment control in the UI").toBeUndefined();
  await analyze.locator("#gc-render").click();
}

async function driveSummary(page, analyze, def, csv) {
  await expect(page.locator("#summary-config")).toBeHidden();
  await analyze.locator("#csv").setInputFiles(csv);
  await expect(page.locator("#summary-config")).toBeVisible();

  await analyze.locator("#cp_group").selectOption(def.roles.group);

  // The variable checklist is the summary form's role mapping. The case
  // declares its selection as roles.continuous + roles.categorical; the ticked
  // set is driven to exactly that, and every other column is UNTICKED — the
  // form starts with everything unflagged ticked, so accepting the default
  // would silently include columns the native run's spec never carried. The
  // group column is unticked too, and that makes no difference either way:
  // buildSummarySpec excludes `groupBy` from `vars` regardless.
  const wanted = new Set([
    ...(def.roles.continuous || []), ...(def.roles.categorical || []),
  ]);
  const boxes = analyze.locator("#summary-vars input[type=checkbox]");
  const count = await boxes.count();
  expect(count, `${def.id}: the variable checklist rendered no columns`)
    .toBeGreaterThan(0);
  const offered = [];
  for (let i = 0; i < count; i++) {
    const box = boxes.nth(i);
    const id = await box.getAttribute("id");
    const column =
      (await analyze.locator(`#summary-vars label[for="${id}"]`).textContent()) || "";
    offered.push(column);
    if (wanted.has(column)) await box.check();
    else await box.uncheck();
  }
  // A declared variable that the checklist never offered would silently drop
  // out of the spec and read as a row-count drift. Name it instead.
  for (const column of wanted) {
    expect(offered, `${def.id}: "${column}" is not in the variable checklist`)
      .toContain(column);
  }

  const plots = analyze.locator("#showplots");
  if (def.options.show_plots) await plots.check(); else await plots.uncheck();
  const qq = analyze.locator("#showqq");
  if (def.options.show_qq) await qq.check(); else await qq.uncheck();
  expect(def.options.event_value,
    "summary has no event-value control in the UI").toBeUndefined();
  expect(def.options.ref_levels,
    "summary has no reference-level control in the UI").toBeUndefined();
  expect(def.options.increments,
    "summary has no increment control in the UI").toBeUndefined();
  await analyze.locator("#render").click();
}

const DRIVERS = {
  logistic: driveLogistic,
  cox: driveCox,
  km: driveKm,
  groupcompare: driveGroupCompare,
  summary: driveSummary,
};

// Drive one case's form and read back what the app displayed.
//
// THE STALE-RESULT PROBLEM, and why the wait below is two-stage. Eight cases
// share one page, and five of them share an analysis with another case
// (logistic x2, group comparison x3). The guided shell's `user` result survives
// a nav switch by design, so re-entering an analysis REPAINTS the previous
// case's numbers into #stats — read at the wrong moment, one case's output would
// be compared against another case's native artifact and the mismatch reported
// as wasm drift. The old single-case version dodged this by waiting for the TSV
// header string; that trick cannot generalise (two logistic cases print the
// same header) and, worse, a textual readiness signal times out on precisely the
// drift this tier exists to record.
//
// So the signal is structural and comes in two stages. createGuidedShell's
// runAndShow blanks #stats and paints "Rendering…" into #preview SYNCHRONOUSLY,
// inside the click handler, before the worker is even messaged (none of these
// analyses uses `liveRender`, the one path that keeps the old figure up). So:
//
//   1. wait for #stats to be EMPTY — proof the click was accepted and the
//      previous case's text is gone;
//   2. wait for #preview to hold the expected element AND #stats to be
//      non-empty — the paint, which happens in one synchronous block.
//
// Stage 1 cannot lose a race to stage 2 in any real run: the blank-out is
// synchronous and the fastest webR fit here is seconds. If it ever did, this
// fails loudly as a precondition rather than silently comparing stale text —
// the right direction to fail in.
async function runAndRead(page, driver, analyze, def, csv, previewElement) {
  await driver(page, analyze, def, csv);

  const stats = page.locator("#stats");
  await expect(stats,
    "the render click did not blank #stats — this case may be reading the " +
    "previous case's output").toBeEmpty({ timeout: 60000 });

  // Wait for EITHER a real render or an error state, whichever comes first —
  // via one poll, not two sequential waits. An error state would otherwise burn
  // the entire budget on the first wait before the class check was ever
  // reached, making that guard unreachable in any useful time.
  await expect
    .poll(
      async () => {
        const cls = (await stats.getAttribute("class")) || "";
        if (/error/.test(cls)) return "error";
        const painted = await page.locator(`#preview ${previewElement}`).count();
        const text = (await stats.textContent()) || "";
        return painted > 0 && text.trim() !== "" ? "ready" : "pending";
      },
      {
        timeout: 600000,
        message:
          `#preview never rendered a <${previewElement}> with text in #stats, ` +
          `nor an error state, within the budget`,
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
//
// INVARIANT — do not violate this from an offline edit. `commit` records the
// tree the BROWSER ACTUALLY RAN AGAINST, measured at the moment THIS function
// is called from the test body below. It is not "whatever HEAD happens to be
// right now" and must be written ONLY by a real run of this spec. An offline
// patch script that touches results/webr-tier.json for any OTHER reason (a
// formatting fix, an unrelated field, a bug fix in this very file) must carry
// the existing `commit` value forward VERBATIM — never regenerate it by
// re-invoking `git rev-parse HEAD`, because by patch time HEAD has moved past
// the commit the browser was actually driven against, and that reinvocation
// silently overwrites the true value with a wrong one. This happened for
// real: commit 2997e1b's offline patch (fixing a NUL-byte bug introduced by
// the previous commit, 6c7744d) re-derived `commit` this way and clobbered
// 815fa79d40d5bcb1a9cd5e3115694e51d58bd7b2 (the tree the browser was actually
// driven against) with 6c7744dfd642af01d525d4788e4b644b35938314 (the very
// metadata-only commit that made the patch necessary, where the browser never
// ran) — a silent regression of the exact staleness-honesty guarantee this
// field exists to provide. See build_scorecard.py's `_stale_native_digest` for
// the safety net that now makes a staleness like that visible instead of
// silent — it watches `native_digest` rather than this field precisely BECAUSE
// a clobber of `commit` cannot defeat it — and prefer restoring a clobbered
// value (as that regression's fix did) over ever recomputing it offline. The
// same applies to `web_digest`, which closes the one staleness direction
// `native_digest` cannot see (a web/-only change): both are measurements taken
// during a real run, not metadata to be regenerated by a later patch.
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
// could drift. Aggregates the per-case cell-kind breakdown the comparators
// produce into one human-readable sentence for the scorecard and the evidence
// file, so a reader cannot come away thinking "N numbers matched" when most of
// N is static labels, headers, and intentionally-blank cells.
//
// It stays honest across the whole roster because the three comparison shapes
// share one cell vocabulary (compare-text.mjs): a case that displays no table
// contributes only `methods` cells — one per displayed sentence — so its
// contribution to the total is the number of sentences it really printed, not
// a table's worth of cells it never had.
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
    `${totalCompared} = ${agg.value} table value cells + ${agg.methods} ` +
    `displayed sentences (${agg.methods_with_number} containing a number) + ` +
    `${agg.term} row labels + ${agg.header} table header line(s) + ` +
    `${agg.empty} empty-vs-empty placeholder cells (blank by construction — a ` +
    `categorical variable's own header row carries no value). Only the ` +
    `${totalWithNumbers} numeric cells (the table value cells plus the ` +
    `number-bearing sentences) can actually show wasm-vs-native drift — the ` +
    `row labels, header lines, and empty cells are static or intentionally ` +
    `blank.`
  );
}

test("webR renders the same numbers native R does", async ({ page }) => {
  // compare-text.mjs is ESM and this spec is CommonJS (the repo's
  // package.json has no "type": "module"), so it is imported dynamically.
  const { compareDisplay, COMPARATORS, runCase, nativeDigest, webDigest } =
    await import(pathToFileURL(path.join(__dirname, "compare-text.mjs")).href);

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

  // ONE page load for the whole roster: the app is a single-page shell whose
  // nav buttons swap the analysis without a reload, so the webR runtime booted
  // for the first case is the same one that fits all eight.
  await page.goto("/");

  // Every case this tier claims to cover must actually be registered in
  // results/ — otherwise a typo'd id would quietly shrink the roster while the
  // published coverage ratio kept counting it.
  const registered = new Set(
    fs.readdirSync(RESULTS)
      .filter((f) => f.endsWith(".figura.json"))
      .map((f) => f.slice(0, -".figura.json".length)));
  for (const c of CASES) {
    expect([...registered], `${c.id} has no native display artifact in results/`)
      .toContain(c.id);
  }
  expect(CASES.length,
    "this tier no longer drives every registered case; update the coverage " +
    "prose in build_scorecard.py and README.md in the same change")
    .toBe(registered.size);

  const cases = [];
  for (const c of CASES) {
    // Wrapped in runCase: a precondition failure (or any other exception) on
    // THIS case must not erase the evidence for the other cases, and must not
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
      // Likewise the COMPARISON shape: it is dispatched on the case's declared
      // display kind, and a kind with no registered comparator (or no readiness
      // element) is a loud precondition failure, never a silent skip.
      const displayKind = def.display.kind;
      expect(Object.keys(COMPARATORS),
        `${c.id}: no comparison shape for display kind "${displayKind}"`)
        .toContain(displayKind);
      expect(Object.keys(PREVIEW_ELEMENT),
        `${c.id}: no readiness element for display kind "${displayKind}"`)
        .toContain(displayKind);

      await openAnalyze(page, c.nav);
      const webrText = await runAndRead(
        page, DRIVERS[c.kind], page.locator("#panel-analyze"), def, csv,
        PREVIEW_ELEMENT[displayKind]);

      const { compared, differing, cellKinds, cellsWithNumbers } =
        compareDisplay(displayKind, nativeText(c.id), webrText);
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

  // The other staleness direction: a change to web/ that moves what the BROWSER
  // computes or displays while native R output stays put. `native_digest` cannot
  // see that (the native artifacts are unchanged), and until this field existed
  // the gap was carried by a docstring rather than by evidence. Digested from
  // the shipped app sources by a mechanical glob — see `webDigest`'s comment in
  // compare-text.mjs for exactly what is in and out, and for the deliberate
  // decision to over-trigger rather than risk a false parity claim.
  const web = webDigest(path.join(REPO_ROOT, "web"));

  const runtime = await detectRuntime(page, cdnUrls);
  fs.mkdirSync(RESULTS, { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify({
    runtime: runtime.runtime,
    runtime_source: runtime.runtime_source,
    date: new Date().toISOString().slice(0, 10),
    commit: repoCommit(),
    native_digest: digestInput.length ? `sha256:${nativeDigest(digestInput)}` : null,
    web_digest: `sha256:${web.digest}`,
    // The file COUNT, not the list: it is the one cheap way a reader (or the
    // scorecard) can tell "the glob found the app" from "the glob found
    // nothing and hashed an empty stream", which would otherwise be a stable
    // digest that never flags anything.
    web_files: web.files.length,
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

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildSpecForCase } from "./build-spec.mjs";
import { parseCsv } from "../../web/lib/csv.js";
import { buildLogisticSpec } from "../../web/guided/logistic/spec.js";
import { buildSummarySpec } from "../../web/guided/summary/analyze-form.js";

const spec = await buildSpecForCase("stats-validation/cases/logistic-confounding");

assert.equal(spec.figure, "logistic");
assert.equal(spec.roles.outcome, "complication");
assert.deepEqual(spec.roles.covariates, ["arm", "age", "stage"]);
assert.equal(spec.options.event_value, "Yes");
assert.equal(spec.options.increments.age, 10);
assert.ok(Array.isArray(spec.data), "data must be an array of row objects");
assert.ok(spec.data.length > 0, "data must not be empty");

// This fixture's own data.csv happens to contain only mapped columns, so this
// assertion alone can't distinguish "narrowed" from "passed through raw" — the
// dedicated fixture below (with a deliberately unmapped column) covers that.
assert.deepEqual(
  Object.keys(spec.data[0]).sort(),
  ["age", "arm", "complication", "stage"].sort()
);

// No-egress narrowing, proven for real: a test-local CSV with an unmapped
// column (site_id) run through the same shipped parseCsv + buildLogisticSpec
// path. If the builder ever regressed to returning raw rows unfiltered, this
// would catch it, since site_id would leak into spec.data[0].
const narrowingCsv =
  "arm,age,stage,complication,site_id\n" +
  "Standard care,72,I,No,SITE-01\n" +
  "New treatment,58,II,Yes,SITE-02\n";
const narrowingTable = parseCsv(narrowingCsv);
const narrowingSpec = buildLogisticSpec(
  narrowingTable,
  { outcome: "complication", covariates: ["arm", "age", "stage"] },
  "Yes",
  {},
  {},
  { source_filename: "narrowing-fixture.csv" }
);
assert.ok(narrowingSpec.data.length > 0, "narrowing fixture must produce rows");
assert.deepEqual(
  Object.keys(narrowingSpec.data[0]).sort(),
  ["age", "arm", "complication", "stage"].sort()
);
assert.ok(
  !("site_id" in narrowingSpec.data[0]),
  "unmapped column site_id must not cross into the spec"
);

// --- cox: the real case dir builds via the shipped buildCoxSpec, with the
// correct roles/event/refs and narrowed data (no increments arg — verified
// against web/guided/cox/spec.js's real export signature).
const coxSpec = await buildSpecForCase("stats-validation/cases/cox-adjusted");

assert.equal(coxSpec.figure, "cox");
assert.equal(coxSpec.roles.time, "followup_months");
assert.equal(coxSpec.roles.status, "status");
assert.deepEqual(coxSpec.roles.covariates, ["arm", "age"]);
assert.equal(coxSpec.options.event_value, "Death");
assert.deepEqual(coxSpec.options.ref_levels, { arm: "Standard care" });
assert.ok(Array.isArray(coxSpec.data), "cox spec data must be an array of row objects");
assert.ok(coxSpec.data.length > 0, "cox spec data must not be empty");
assert.deepEqual(
  Object.keys(coxSpec.data[0]).sort(),
  ["age", "arm", "followup_months", "status"].sort()
);

// --- km: the real case dir builds via the shipped buildKmSpec. Its real
// signature returns { dropped, spec } (verified against web/guided/km/spec.js),
// unlike buildLogisticSpec/buildCoxSpec's flat spec — build-spec.mjs's km
// builder must unwrap `.spec` itself, so buildSpecForCase's return here IS
// already the flat spec.
const kmSpec = await buildSpecForCase("stats-validation/cases/km-twoarm");

assert.equal(kmSpec.figure, "km");
assert.ok(Array.isArray(kmSpec.data), "km spec data must be an array of row objects");
assert.ok(kmSpec.data.length > 0, "km spec data must not be empty");
// No-egress narrowing, for real: the real fixture's header is
// participant_id,followup_months,status,group — only time/status/group are
// mapped roles, so participant_id (unmapped) must never cross into the spec.
// fig_km reads spec$data[[i]]$time/$status/$group directly (no `roles` key
// at all, unlike logistic/cox), so the row keys themselves ARE the contract.
assert.deepEqual(
  Object.keys(kmSpec.data[0]).sort(),
  ["group", "status", "time"].sort()
);
assert.ok(!("participant_id" in kmSpec.data[0]),
  "unmapped column participant_id must not cross into the spec");
// status is recoded 0/1 client-side by buildKmSpec, keyed off event_value
// "Death" — never a raw "Death"/"Censored" string reaching R.
assert.ok(
  kmSpec.data.every((r) => r.status === 0 || r.status === 1),
  "km spec status must be recoded to 0/1"
);
assert.equal(kmSpec.options.source_roles.time, "followup_months");
assert.equal(kmSpec.options.source_roles.status, "status");
assert.equal(kmSpec.options.source_roles.group, "group");
assert.equal(kmSpec.options.source_roles.event, "Death");
assert.equal(kmSpec.options.source_filename, "data.csv");

// --- groupcompare: three cases, one per branch the analysis routes on.
// buildGroupCompareSpec's real signature is (table, roles, options) — three
// arguments, no event value and no reference levels (verified against
// web/guided/groupcompare/spec.js), and it returns the FLAT spec like
// buildLogisticSpec/buildCoxSpec, not km's { dropped, spec }.
for (const [id, outcome] of [
  ["groupcompare-numeric", "biomarker_normal"],
  ["groupcompare-categorical", "responder"],
  ["groupcompare-dirty", "site_code"],
]) {
  const gc = await buildSpecForCase(`stats-validation/cases/${id}`);
  assert.equal(gc.figure, "groupcompare", `${id}: figure`);
  assert.equal(gc.roles.group, "arm", `${id}: group role`);
  assert.equal(gc.roles.outcome, outcome, `${id}: outcome role`);
  assert.equal(gc.options.plot, "box", `${id}: plot option`);
  assert.equal(gc.options.test, "auto", `${id}: test option`);
  assert.equal(gc.options.source_filename, "data.csv", `${id}: source filename`);
  assert.ok(Array.isArray(gc.data) && gc.data.length === 150, `${id}: 150 rows`);
  // No-egress narrowing, for real: every one of these fixtures carries
  // columns that are NOT mapped roles (los_skewed/responder/biomarker_normal),
  // so a builder that returned raw rows would leak them here.
  assert.deepEqual(
    Object.keys(gc.data[0]).sort(), ["arm", outcome].sort(),
    `${id}: spec rows must carry only the two mapped role columns`
  );
}

// The dirty case specifically: the shipped parseCsv must have absorbed the
// CRLF line endings and trimmed the padded cells BEFORE the spec was built —
// this is what makes R's numeric type detection see "01" rather than " 01\r",
// and it is the difference between a Kruskal-Wallis and a chi-square.
const dirty = await buildSpecForCase("stats-validation/cases/groupcompare-dirty");
const codes = dirty.data.map((r) => r.site_code);
assert.ok(codes.every((v) => !/[\r\n]/.test(v)),
  "no CR/LF may survive into a dirty-case cell");
assert.ok(codes.every((v) => v === v.trim()),
  "every dirty-case site_code cell must arrive trimmed");
assert.deepEqual([...new Set(codes)].sort(), ["", "01", "02", "03"],
  "trimming must collapse the padded cells to exactly three codes plus blank");
assert.equal(codes.filter((v) => v === "").length, 4,
  "the dirty case must carry exactly four blank site_code cells");
// The unmapped los_skewed column has blanks of its own; they must not be here
// at all, let alone affect anything.
assert.ok(!("los_skewed" in dirty.data[0]),
  "unmapped column los_skewed must not cross into the spec");

// --- logistic-dirty: the SAME builder as logistic-confounding, on a file with
// literal "NA" text in a categorical covariate and trailing spaces on a
// numeric one. The claims here are about the shipped PARSER, because they are
// what makes the case's whole point reproducible:
//   * `NA` is ORDINARY TEXT to parseCsv — it must survive into the spec as the
//     two-character string, becoming a real `stage` level the app models and
//     displays. (R's read.csv, which the exported script uses, turns it into a
//     real NA and drops the row; that divergence is the case.)
//   * a padded numeric cell arrives TRIMMED, so the padding is inert and the
//     only variable under test is the "NA" handling.
const dirtyLogistic = await buildSpecForCase("stats-validation/cases/logistic-dirty");
assert.equal(dirtyLogistic.figure, "logistic");
assert.deepEqual(dirtyLogistic.roles.covariates, ["arm", "age", "stage"]);
assert.equal(dirtyLogistic.data.length, 320, "logistic-dirty: 320 rows");
const dirtyStages = dirtyLogistic.data.map((r) => r.stage);
assert.deepEqual([...new Set(dirtyStages)].sort(), ["I", "II", "III", "NA"],
  'literal "NA" must survive the parser as an ordinary stage level');
assert.equal(dirtyStages.filter((v) => v === "NA").length, 8,
  "logistic-dirty must carry exactly eight literal-NA stage cells");
assert.ok(dirtyLogistic.data.every((r) => r.age === r.age.trim()),
  "every padded age cell must arrive trimmed");
assert.ok(dirtyLogistic.data.every((r) => r.complication === "Yes" || r.complication === "No"),
  "the outcome column must be untouched by the injected dirt");

// --- summary: the ONE analysis whose spec builder does not live in a spec.js.
// `buildSummarySpec` is exported from web/guided/summary/analyze-form.js, and
// its real signature is (table, { groupBy, showPlots, showQq, selected,
// sourceFilename }) — one options object, verified against that file.
const summarySpec = await buildSpecForCase("stats-validation/cases/summary-table1");

assert.equal(summarySpec.figure, "summary");
assert.equal(summarySpec.roles.group, "arm");
assert.equal(summarySpec.options.source_filename, "data.csv");
assert.equal(summarySpec.options.show_plots, false);
assert.equal(summarySpec.options.show_qq, false);
assert.ok(Array.isArray(summarySpec.data) && summarySpec.data.length === 120,
  "summary spec must carry all 120 rows");
// THE registration claim: the case DECLARES a continuous/categorical split,
// and the shipped builder re-derives its own via classifyColumns. The two must
// agree, or the comparator's expectations are keyed to rows the app will never
// print — and the harvester's s1..sN / t1..tM would be mis-keyed too.
//
// THIS IS ALSO THE ONLY CHECK THAT CATCHES A SAME-ARITY SWAP. run-script.R's
// harvest_summary keys s1..sN / t1..tM by the case's declared roles and stops
// loudly when the COUNTS disagree; a swap (one variable moving each way) leaves
// the counts intact and would silently file one variable's numbers under
// another's name. It is caught here, by comparing the two lists element by
// element — so this assertion reads the case's roles from case.json rather than
// restating them, and the literal expectation is asserted against case.json
// separately (a case.json that lost both keys must not pass vacuously).
const summaryCase = JSON.parse(readFileSync(
  "stats-validation/cases/summary-table1/case.json", "utf8"));
assert.deepEqual(summaryCase.roles.continuous, ["age", "length_of_stay", "crp"]);
assert.deepEqual(summaryCase.roles.categorical, ["sex", "diabetes"]);
assert.deepEqual(summarySpec.options.continuous, summaryCase.roles.continuous,
  "the app's own classification must match the case's declared continuous set");
assert.deepEqual(summarySpec.options.categorical, summaryCase.roles.categorical,
  "the app's own classification must match the case's declared categorical set");
// Blank cells travel as empty strings, not as dropped keys: fig_summary counts
// them per variable and never drops the row.
assert.equal(summarySpec.data.filter((r) => r.length_of_stay === "").length, 8,
  "the eight blank length_of_stay cells must reach the spec as blanks");

// No-egress narrowing for summary, proven with a deliberately UNSELECTED
// column (the real case selects every column, so it cannot show this).
const summaryNarrowingCsv =
  "age,crp,arm,notes\n" +
  "72,2.5,Control,private\n" +
  "58,3.1,Treatment,private\n";
const summaryNarrowing = buildSummarySpec(parseCsv(summaryNarrowingCsv), {
  groupBy: "arm", showPlots: false, showQq: false,
  selected: ["age", "crp"], sourceFilename: "narrowing-fixture.csv",
});
assert.deepEqual(Object.keys(summaryNarrowing.data[0]).sort(),
  ["age", "arm", "crp"].sort());
assert.ok(!("notes" in summaryNarrowing.data[0]),
  "an unticked column must not cross into the spec");

console.log("build-spec.test.mjs ok");

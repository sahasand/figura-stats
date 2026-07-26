import assert from "node:assert/strict";
import { buildSpecForCase } from "./build-spec.mjs";
import { parseCsv } from "../../web/lib/csv.js";
import { buildLogisticSpec } from "../../web/guided/logistic/spec.js";

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

console.log("build-spec.test.mjs ok");

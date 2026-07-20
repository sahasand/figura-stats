import assert from "node:assert";
import { buildLogisticSpec, distinctValues, mostFrequent } from "./spec.js";

const table = {
  columns: ["outcome", "arm", "age", "note"],
  rows: [
    { outcome: "Yes", arm: "A", age: "60", note: "x" },
    { outcome: "No", arm: "B", age: "70", note: "y" },
    { outcome: "Yes", arm: "A", age: "65", note: "z" },
  ],
};
const roles = { outcome: "outcome", covariates: ["arm", "age"] };

const spec = buildLogisticSpec(table, roles, "Yes", { arm: "B" }, { age: 10 },
  { source_filename: "f.csv" });
assert.equal(spec.figure, "logistic");
assert.deepEqual(spec.roles, { outcome: "outcome", covariates: ["arm", "age"] });
assert.equal(spec.options.event_value, "Yes");
assert.deepEqual(spec.options.ref_levels, { arm: "B" });
assert.deepEqual(spec.options.increments, { age: 10 });
// no-egress: only mapped columns cross, `note` is dropped
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "outcome"]);
assert.equal(spec.options.source_roles.outcome, "outcome");
assert.equal(spec.options.source_roles.event, "Yes");

assert.deepEqual(distinctValues(table, "arm"), ["A", "B"]);
assert.equal(mostFrequent(table, "arm"), "A");

// no-egress: `note` must never appear in any row, not just the first
for (const row of spec.data) {
  assert.ok(!("note" in row), "note column must not cross to the worker");
}

// roles.covariates and source_roles.covariates must stay identical (drift
// between them would make the generated .R script compute something
// different from what the app rendered)
assert.deepEqual(spec.options.source_roles.covariates, spec.roles.covariates);

// mutating the returned roles.covariates array must not alias the caller's
// input array (defensive copy, matches cox's `.slice()`)
spec.roles.covariates.push("tampered");
assert.deepEqual(roles.covariates, ["arm", "age"]);

// empty covariates: outcome-only model must still work and carry no
// covariate columns
const noCovSpec = buildLogisticSpec(table, { outcome: "outcome", covariates: [] },
  "Yes", {}, {}, {});
assert.deepEqual(noCovSpec.roles.covariates, []);
assert.deepEqual(Object.keys(noCovSpec.data[0]), ["outcome"]);
assert.equal(noCovSpec.options.source_filename, null);

// demo-shape: no source_filename -> null, ref_levels/increments default to {}
const demoSpec = buildLogisticSpec(table, roles, "Yes", null, null, {});
assert.equal(demoSpec.options.source_filename, null);
assert.deepEqual(demoSpec.options.ref_levels, {});
assert.deepEqual(demoSpec.options.increments, {});

// event_value is always carried as an explicit string, even if the caller
// passes a non-string-looking value (R falls back to "" -> all-zero outcome
// if this is ever dropped)
const numericEventSpec = buildLogisticSpec(table, roles, 1, {}, {}, {});
assert.equal(numericEventSpec.options.event_value, "1");
assert.equal(typeof numericEventSpec.options.event_value, "string");

// distinctValues/mostFrequent ignore blank and null cells
const blanky = { columns: ["c"], rows: [{ c: "" }, { c: "A" }, { c: null }, { c: "A" }, { c: "  " }] };
assert.deepEqual(distinctValues(blanky, "c"), ["A"]);
assert.equal(mostFrequent(blanky, "c"), "A");

console.log("ok - logistic spec");

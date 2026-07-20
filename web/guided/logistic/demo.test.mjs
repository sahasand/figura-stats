import assert from "node:assert/strict";
import { buildLogisticDemoSpec, DEFAULT_DEMO_STATE, DEMO_TABLE } from "./demo.js";
import { LOGISTIC_DEMO } from "./demo-data.js";

const spec = buildLogisticDemoSpec(DEFAULT_DEMO_STATE());
assert.equal(spec.figure, "logistic");
assert.equal(spec.roles.outcome, "complication");
assert.deepEqual(spec.roles.covariates, ["arm", "age", "stage"]);
assert.equal(spec.data.length, LOGISTIC_DEMO.rows.length);

// The R side has NO default event value: it falls back to "" and silently
// produces an all-zero outcome. "No" is the majority level here, so a missing
// event_value would not merely flip the story, it would error out.
assert.equal(spec.options.event_value, "Yes");

// A demo spec must NOT carry source_filename — its absence is what makes the
// generated .R script embed the example data instead of emitting a read.csv.
assert.ok(!("source_filename" in spec.options),
  "demo spec must omit options.source_filename");

// age is shown per 10 years, and the reference levels pin the confounding story.
assert.deepEqual(spec.options.increments, { age: 10 });
assert.equal(spec.options.ref_levels.arm, "Standard care");
assert.equal(spec.options.ref_levels.stage, "I");
assert.equal(spec.options.caption, LOGISTIC_DEMO.label);

// no-egress: only the outcome + selected covariates cross to the worker.
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "complication", "stage"]);

// Dropping a covariate drops its column from every row, not just the first.
const noAge = buildLogisticDemoSpec({ covariates: ["arm", "stage"] });
assert.deepEqual(noAge.roles.covariates, ["arm", "stage"]);
for (const row of noAge.data) {
  assert.ok(!("age" in row), "unselected covariate must not cross to the worker");
  assert.ok("complication" in row, "outcome must always cross");
}

// The demo state must be a fresh object each call (the session store resets by
// shallow copy) and the spec must not alias the state's covariates array.
const a = DEFAULT_DEMO_STATE(), b = DEFAULT_DEMO_STATE();
assert.notEqual(a, b);
assert.notEqual(a.covariates, b.covariates);
const s = buildLogisticDemoSpec(a);
s.roles.covariates.push("tampered");
assert.deepEqual(a.covariates, ["arm", "age", "stage"]);

// DEMO_TABLE mirrors the frozen dataset and R's numeric/categorical decision.
assert.deepEqual(DEMO_TABLE.columns, LOGISTIC_DEMO.columns);
assert.equal(DEMO_TABLE.rows.length, LOGISTIC_DEMO.rows.length);
assert.equal(DEMO_TABLE.types.age, "numeric");
assert.equal(DEMO_TABLE.types.complication, "categorical");

console.log("demo.test.mjs OK");

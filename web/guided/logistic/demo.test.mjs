import assert from "node:assert/strict";
import { buildLogisticDemoSpec, DEFAULT_DEMO_STATE, DEMO_TABLE } from "./demo.js";
import { LOGISTIC_DEMO } from "./demo-data.js";
import { EXAMPLE_INTRO_HTML, renderUnderstand } from "./content.js";

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

// F5: the Example intro's sample size is derived from LOGISTIC_DEMO.rows.length
// (drift-proof), but the Understand section's event-rate percentage is a
// hand-typed literal ("28%"). If demo-data.js is ever regenerated, this must
// fail rather than let stale copy silently ship.
assert.ok(EXAMPLE_INTRO_HTML.includes(String(LOGISTIC_DEMO.rows.length)),
  "Example intro must state the actual number of demo rows");

const fakePanel = { innerHTML: "" };
renderUnderstand(fakePanel);
const events = LOGISTIC_DEMO.rows.filter((r) => r.complication === "Yes").length;
const pct = Math.round((100 * events) / LOGISTIC_DEMO.rows.length);
assert.ok(fakePanel.innerHTML.includes(`${pct}%`),
  `Understand copy must quote the actual event rate (${pct}%), not a stale hardcoded value`);

console.log("demo.test.mjs OK");

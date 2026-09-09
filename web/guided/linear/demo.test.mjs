import assert from "node:assert/strict";
import { buildLinearDemoSpec, DEFAULT_DEMO_STATE, DEMO_TABLE } from "./demo.js";
import { LINEAR_DEMO } from "./demo-data.js";
import { EXAMPLE_INTRO_HTML } from "./content.js";
import { renderUnderstand } from "./content.js";

const spec = buildLinearDemoSpec(DEFAULT_DEMO_STATE());
assert.equal(spec.figure, "linear");
assert.equal(spec.roles.outcome, "los");
assert.deepEqual(spec.roles.covariates, ["arm", "age", "stage"]);
assert.equal(spec.data.length, LINEAR_DEMO.rows.length);
assert.equal(LINEAR_DEMO.rows.length, 320);
assert.ok(!("source_filename" in spec.options), "demo spec must omit options.source_filename");
assert.ok(!("event_value" in spec.options));
assert.deepEqual(spec.options.increments, { age: 10 });
assert.equal(spec.options.ref_levels.arm, "Standard care");
assert.equal(spec.options.ref_levels.stage, "I");
assert.equal(spec.options.caption, LINEAR_DEMO.label);
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "los", "stage"]);

const noAge = buildLinearDemoSpec({ covariates: ["arm", "stage"] });
for (const row of noAge.data) {
  assert.ok(!("age" in row), "unselected covariate must not cross");
  assert.ok("los" in row, "outcome must always cross");
}

const a = DEFAULT_DEMO_STATE(), b = DEFAULT_DEMO_STATE();
assert.notEqual(a, b);
assert.notEqual(a.covariates, b.covariates);
const s = buildLinearDemoSpec(a);
s.roles.covariates.push("tampered");
assert.deepEqual(a.covariates, ["arm", "age", "stage"]);

assert.deepEqual(DEMO_TABLE.columns, LINEAR_DEMO.columns);
assert.equal(DEMO_TABLE.types.los, "numeric");
assert.equal(DEMO_TABLE.types.age, "numeric");
assert.equal(DEMO_TABLE.types.stage, "categorical");

// The intro's sample size is derived, never hand-typed.
assert.ok(EXAMPLE_INTRO_HTML.includes(String(LINEAR_DEMO.rows.length)));

const fakePanel = { innerHTML: "" };
renderUnderstand(fakePanel);
assert.ok(fakePanel.innerHTML.includes("<h3>"), "Understand renders sections");
assert.ok(/per 10 years/.test(fakePanel.innerHTML), "Understand copy explains the increment");

console.log("demo.test.mjs OK");

import assert from "node:assert/strict";
import { buildGroupCompareDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";

const spec = buildGroupCompareDemoSpec(DEFAULT_DEMO_STATE());
assert.equal(spec.figure, "groupcompare");
assert.equal(spec.roles.group, "arm");
assert.equal(spec.roles.outcome, "biomarker_normal");
assert.equal(spec.data.length, GROUPCOMPARE_DEMO.rows.length);
// projected to arm + biomarker_normal only
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["arm", "biomarker_normal"]);
const a = DEFAULT_DEMO_STATE(), b = DEFAULT_DEMO_STATE();
assert.notEqual(a.roles, b.roles);
assert.notEqual(a.options, b.options);
console.log("demo.test.mjs OK");

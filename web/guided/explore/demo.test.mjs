// web/guided/explore/demo.test.mjs
import assert from "node:assert/strict";
import { buildExploreDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { EXPLORE_DEMO } from "./demo-data.js";

const spec = buildExploreDemoSpec(DEFAULT_DEMO_STATE());
assert.equal(spec.figure, "explore");
assert.equal(spec.options.geom, "scatter");
assert.equal(spec.roles.x, "age");
assert.equal(spec.roles.y, "biomarker");
assert.equal(spec.roles.color, "arm");
assert.equal(spec.options.caption, EXPLORE_DEMO.label);   // label baked into figure
assert.equal(spec.data.length, EXPLORE_DEMO.rows.length);
// Fresh objects each call — session-state must never share nested references.
const a = DEFAULT_DEMO_STATE(), b = DEFAULT_DEMO_STATE();
assert.notEqual(a.roles, b.roles);
assert.notEqual(a.options, b.options);
console.log("demo.test.mjs OK");

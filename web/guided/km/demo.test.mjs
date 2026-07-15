import assert from "node:assert/strict";
import { buildDemoSpec } from "./demo.js";
import { KM_DEMO } from "./demo-data.js";

const spec = buildDemoSpec({ conf_int: true, landmarks: [], horizon: null });
assert.equal(spec.figure, "km");
assert.equal(spec.data.length, 120);
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["group", "status", "time"]);
const d0 = KM_DEMO.rows[0];
assert.equal(spec.data[0].time, d0.followup_months);
assert.equal(spec.data[0].status, d0.status === "Death" ? 1 : 0);
assert.equal(spec.options.reference, "Standard care");        // HR direction: New vs Standard
assert.equal(spec.options.caption, KM_DEMO.label);            // synthetic label INSIDE the SVG
assert.equal(spec.options.time_label, "Months since randomization");
assert.equal(spec.options.conf_int, true);

const spec2 = buildDemoSpec({ conf_int: false, landmarks: [12, 24], horizon: 24 });
assert.equal(spec2.options.conf_int, false);
assert.deepEqual(spec2.options.landmarks, [12, 24]);
assert.equal(spec2.options.horizon, 24);
console.log("demo.test.mjs OK");

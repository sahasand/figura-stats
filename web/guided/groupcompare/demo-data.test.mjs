import assert from "node:assert/strict";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";

assert.equal(GROUPCOMPARE_DEMO.rows.length, 150);
assert.deepEqual(GROUPCOMPARE_DEMO.columns,
  ["arm", "biomarker_normal", "los_skewed", "responder"]);
assert.equal(GROUPCOMPARE_DEMO.rows.filter((r) => r.los_skewed === null).length, 6);
assert.ok(GROUPCOMPARE_DEMO.label.includes("not for clinical use"));
assert.ok(GROUPCOMPARE_DEMO.rows.every((r) =>
  ["Placebo", "Low dose", "High dose"].includes(r.arm)));
assert.ok(GROUPCOMPARE_DEMO.rows.every((r) => ["Yes", "No"].includes(r.responder)));
console.log("demo-data.test.mjs OK");

// web/guided/explore/demo-data.test.mjs
import assert from "node:assert/strict";
import { EXPLORE_DEMO } from "./demo-data.js";

assert.equal(EXPLORE_DEMO.rows.length, 120);
assert.deepEqual(EXPLORE_DEMO.columns,
  ["patient_id", "visit_month", "age", "bmi", "biomarker", "arm", "sex", "ecog"]);
assert.equal(EXPLORE_DEMO.rows.filter((r) => r.bmi === null).length, 5);
assert.ok(EXPLORE_DEMO.label.includes("not for clinical use"));
assert.ok(EXPLORE_DEMO.rows.every((r) => [0, 3, 6].includes(r.visit_month)));
assert.ok(EXPLORE_DEMO.rows.every((r) => [0, 1, 2].includes(r.ecog)));
console.log("demo-data.test.mjs OK");

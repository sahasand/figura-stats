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

// responder Yes-rate rises with dose (Placebo < High dose) — a teaching target
const yesRate = (arm) => {
  const rows = GROUPCOMPARE_DEMO.rows.filter((r) => r.arm === arm);
  return rows.filter((r) => r.responder === "Yes").length / rows.length;
};
assert.ok(yesRate("High dose") > yesRate("Placebo"));
console.log("demo-data.test.mjs OK");

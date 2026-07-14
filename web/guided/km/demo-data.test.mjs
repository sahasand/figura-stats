import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { KM_DEMO } from "./demo-data.js";

assert.equal(KM_DEMO.version, "1.0.0");
assert.equal(KM_DEMO.label, "Synthetic demonstration data — not for clinical use.");
assert.equal(KM_DEMO.rows.length, 120);
assert.deepEqual(KM_DEMO.columns, ["participant_id", "followup_months", "status", "group"]);
const groups = KM_DEMO.rows.reduce((m, r) => (m[r.group] = (m[r.group] || 0) + 1, m), {});
assert.deepEqual(groups, { "Standard care": 60, "New treatment": 60 });
for (const r of KM_DEMO.rows) {
  assert.match(r.participant_id, /^P\d{3}$/);
  assert.equal(typeof r.followup_months, "number");
  assert.ok(r.followup_months >= 0.1);
  assert.ok(["Death", "Censored"].includes(r.status));
}
// JS module and R fixture must be the same data
const csv = readFileSync("tests/testthat/fixtures/km-demo.csv", "utf8").trim().split("\n");
assert.equal(csv.length - 1, 120);
const first = csv[1].split(",");
assert.equal(first[0], KM_DEMO.rows[0].participant_id);
assert.equal(Number(first[1]), KM_DEMO.rows[0].followup_months);
console.log("demo-data.test.mjs OK");

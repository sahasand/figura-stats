// web/guided/summary/demo-data.test.mjs
import { SUMMARY_DEMO } from "./demo-data.js";
import { parseCsv, toCsv } from "../../lib/csv.js";
import assert from "node:assert";

assert.equal(SUMMARY_DEMO.version, "1.0.0");
assert.equal(SUMMARY_DEMO.label, "Synthetic demonstration data");
assert.deepEqual(SUMMARY_DEMO.columns, ["age", "length_of_stay", "crp", "sex", "diabetes", "arm"]);
assert.equal(SUMMARY_DEMO.rows.length, 120, "demo has 120 rows");
const missing = SUMMARY_DEMO.rows.filter((r) => r.length_of_stay === null).length;
assert.equal(missing, 8, "exactly 8 missing length_of_stay");
assert.deepEqual([...new Set(SUMMARY_DEMO.rows.map((r) => r.arm))].sort(), ["Control", "Treatment"]);
// The downloadable example CSV must reparse cleanly through the app's own parser.
const csvText = toCsv(SUMMARY_DEMO.rows, SUMMARY_DEMO.columns);
const roundTrip = parseCsv(csvText);
assert.deepEqual(roundTrip.columns, SUMMARY_DEMO.columns);
assert.equal(roundTrip.rows.length, 120);
assert.equal(roundTrip.types.age, "numeric");
assert.equal(roundTrip.types.arm, "categorical");
assert.equal(roundTrip.rows[2].length_of_stay, "", "null serializes as an empty (missing) cell");

console.log("ok - summary demo-data");

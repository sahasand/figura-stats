import assert from "node:assert";
import { parseCsv } from "./csv.js";

const csv = "age,arm,resp\r\n61,A,1\n72,B,0\n55,A,1\n";
const out = parseCsv(csv);
assert.deepEqual(out.columns, ["age", "arm", "resp"]);
assert.equal(out.rows.length, 3);
assert.equal(out.rows[0].age, "61");
assert.equal(out.types.age, "numeric");
assert.equal(out.types.arm, "categorical");
assert.equal(out.types.resp, "numeric");

assert.throws(() => parseCsv("a,b\n"), /no data rows/i);
assert.throws(() => parseCsv(""), /empty/i);
assert.throws(() => parseCsv("x,x\n1,2\n"), /duplicate/i);
assert.throws(() => parseCsv("a,b\n1,2,3\n"), /expected 2 columns, found 3/i);

// All-empty/whitespace-only cells -> categorical, not numeric.
const blankCol = parseCsv("age,note\n61, \n72,\n55,   \n");
assert.equal(blankCol.types.note, "categorical");

// Mixed numeric and non-numeric values -> categorical.
const mixedCol = parseCsv("age,val\n61,1\n72,abc\n55,3\n");
assert.equal(mixedCol.types.val, "categorical");

// Padded numeric value is trimmed and parsed as numeric.
const padded = parseCsv("age,arm\n 61 ,A\n72,B\n55,A\n");
assert.equal(padded.types.age, "numeric");
assert.equal(padded.rows[0].age, "61");

console.log("csv.test.mjs OK");

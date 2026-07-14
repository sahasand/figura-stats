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

console.log("csv.test.mjs OK");

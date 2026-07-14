import assert from "node:assert";
import { parseKmCsv } from "./km.js";

// Valid file parses to expected row objects (numeric time/status, trimmed group).
const valid = "time,status,group\n12,1,A\n0.5,0,B\n1e2,1,A\n";
const rows = parseKmCsv(valid);
assert.deepEqual(rows, [
  { time: 12, status: 1, group: "A" },
  { time: 0.5, status: 0, group: "B" },
  { time: 100, status: 1, group: "A" }, // scientific notation accepted
]);

// Leading-dot fraction is a valid decimal.
assert.equal(parseKmCsv("time,status,group\n.5,0,A\n")[0].time, 0.5);

// Non-numeric junk in time is rejected (not silently truncated to 12).
assert.throws(() => parseKmCsv("time,status,group\n12abc,1,A\n"), /'time' is not a number/);
assert.throws(() => parseKmCsv("time,status,group\n1e5x,1,A\n"), /'time' is not a number/);
assert.throws(() => parseKmCsv("time,status,group\n--3,1,A\n"), /'time' is not a number/);

// Empty time cell is rejected.
assert.throws(() => parseKmCsv("time,status,group\n ,1,A\n"), /'time' is not a number/);

// Negative time is rejected with its own message.
assert.throws(() => parseKmCsv("time,status,group\n-3,1,A\n"), /'time' must be non-negative/);

// Status must be exactly "0" or "1".
assert.throws(() => parseKmCsv("time,status,group\n12,1x,A\n"), /'status' must be 0/);
assert.throws(() => parseKmCsv("time,status,group\n12,01,A\n"), /'status' must be 0/);
assert.throws(() => parseKmCsv("time,status,group\n12,1.0,A\n"), /'status' must be 0/);

// Missing required column.
assert.throws(() => parseKmCsv("time,status\n12,1\n"), /needs columns/);

// No data rows.
assert.throws(() => parseKmCsv("time,status,group\n"), /no data rows/);

console.log("km.test.mjs OK");

// Pure KM spec assembly: event-value coding, blank-row drops, no-egress projection.
import assert from "node:assert";
import { buildKmSpec, distinctValues } from "./spec.js";

const table = {
  columns: ["id", "followup_months", "vital", "arm"],
  rows: [
    { id: "P1", followup_months: "5.2", vital: "Death", arm: "A" },
    { id: "P2", followup_months: "8.1", vital: "Censored", arm: "A" },
    { id: "P3", followup_months: "", vital: "Death", arm: "B" },      // blank time -> dropped
    { id: "P4", followup_months: "12.4", vital: "Death", arm: "B" },
  ],
  types: { id: "categorical", followup_months: "numeric",
           vital: "categorical", arm: "categorical" },
};
const roles = { time: "followup_months", status: "vital", group: "arm" };

{ // event coding + projection + drop count + passthrough
  const { spec, dropped } = buildKmSpec(table, roles, "Death",
    { time_label: "Months", theme: "generic", source_filename: "trial.csv" });
  assert.equal(dropped, 1);
  assert.equal(spec.figure, "km");
  assert.equal(spec.data.length, 3);
  assert.deepEqual(spec.data[0], { time: 5.2, status: 1, group: "A" });
  assert.deepEqual(spec.data[1], { time: 8.1, status: 0, group: "A" });
  // no-egress: only the three projected keys cross (id never does)
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["group", "status", "time"]);
  assert.equal(spec.options.time_label, "Months");
  assert.equal(spec.options.theme, "generic");
  assert.equal(spec.options.source_filename, "trial.csv");
  assert.deepEqual(spec.options.source_roles,
    { time: "followup_months", status: "vital", group: "arm", event: "Death" });
}

{ // numeric 1/0 coding works through the same picker path
  const t2 = { ...table, rows: [
    { followup_months: "3", vital: "1", arm: "A" },
    { followup_months: "4", vital: "0", arm: "A" },
  ]};
  const { spec, dropped } = buildKmSpec(t2, roles, "1",
    { time_label: "Months", theme: "generic" });
  assert.equal(dropped, 0);
  assert.deepEqual(spec.data.map((r) => r.status), [1, 0]);
  assert.equal(spec.options.source_filename, null);   // absent -> null (embed signal)
}

{ // distinctValues: first-appearance order, blanks skipped
  assert.deepEqual(distinctValues(table, "vital"), ["Death", "Censored"]);
  const t3 = { rows: [{ v: "" }, { v: "x" }, { v: "x" }, { v: " " }] };
  assert.deepEqual(distinctValues(t3, "v"), ["x"]);
}

console.log("spec.test.mjs (km) OK");

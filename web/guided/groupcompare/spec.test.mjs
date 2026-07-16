import assert from "node:assert/strict";
import { buildGroupCompareSpec } from "./spec.js";

const table = {
  columns: ["arm", "crp", "sex", "note"],
  types: { arm: "categorical", crp: "numeric", sex: "categorical", note: "categorical" },
  rows: [
    { arm: "A", crp: 5.1, sex: "M", note: "x" },
    { arm: "B", crp: 7.4, sex: "F", note: "y" },
  ],
};

{
  const spec = buildGroupCompareSpec(table,
    { group: "arm", outcome: "crp" }, { plot: "violin", test: "auto" });
  assert.equal(spec.figure, "groupcompare");
  assert.deepEqual(spec.roles, { group: "arm", outcome: "crp" });
  assert.deepEqual(spec.options,
    { plot: "violin", test: "auto", source_filename: null });
  // rows projected to group + outcome only — no sex/note egress
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["arm", "crp"]);
}

// source_filename passes through to options (R decides read.csv vs embed on it)
{
  const table = { columns: ["g", "v"], rows: [{ g: "A", v: "1" }] };
  const spec = buildGroupCompareSpec(table, { group: "g", outcome: "v" },
    { plot: "box", test: "auto", source_filename: "trial.csv" });
  assert.equal(spec.options.source_filename, "trial.csv");
}
console.log("spec.test.mjs OK");

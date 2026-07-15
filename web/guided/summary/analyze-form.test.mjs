import { classifyColumns, buildSummarySpec } from "./analyze-form.js";
import assert from "node:assert";

const table = {
  columns: ["age", "crp", "diabetes", "patient_id", "site", "arm"],
  rows: Array.from({ length: 30 }, (_, i) => ({
    age: String(40 + (i % 12)),            // numeric, 12 distinct -> continuous
    crp: (1 + i * 0.37).toFixed(1),        // numeric decimals, all unique -> continuous, NOT id
    diabetes: String(i % 2),               // numeric, 2 distinct -> categorical (0/1)
    patient_id: String(1000 + i),          // integers, all unique -> id flag
    site: "S" + (i % 25),                  // categorical, 25 levels -> many-levels flag
    arm: i % 2 ? "A" : "B",
  })),
  types: { age: "numeric", crp: "numeric", diabetes: "numeric",
           patient_id: "numeric", site: "categorical", arm: "categorical" },
};

{
  const { kinds, flags } = classifyColumns(table);
  assert.equal(kinds.age, "continuous");
  assert.equal(kinds.diabetes, "categorical", "0/1-coded binary is categorical");
  assert.equal(flags.patient_id, "id", "all-unique integers flagged as ID");
  assert.equal(flags.crp, null, "all-unique decimals are NOT flagged as ID");
  assert.equal(flags.site, "many-levels", ">20 levels flagged");
  assert.equal(flags.age, null);
}
{
  const spec = buildSummarySpec(table, {
    groupBy: "arm", showPlots: true, selected: ["age", "crp", "diabetes"] });
  assert.equal(spec.figure, "summary");
  assert.equal(spec.roles.group, "arm");
  assert.deepEqual(spec.options.continuous, ["age", "crp"]);
  assert.deepEqual(spec.options.categorical, ["diabetes"]);
  assert.equal(spec.options.show_plots, true);
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "crp", "diabetes"],
    "rows are projected to selected + group columns only");
}
{
  const spec = buildSummarySpec(table, { groupBy: null, showPlots: false, selected: ["age"] });
  assert.equal(spec.roles.group, null);
  assert.deepEqual(Object.keys(spec.data[0]), ["age"]);
}
console.log("ok - classifyColumns + buildSummarySpec");

import { buildSummaryDemoSpec } from "./demo.js";
import { SUMMARY_DEMO } from "./demo-data.js";
import assert from "node:assert";

{
  const spec = buildSummaryDemoSpec({ groupBy: "arm", showPlots: true, forceMean: false });
  assert.equal(spec.figure, "summary");
  assert.equal(spec.roles.group, "arm");
  assert.equal(spec.data.length, 120);
  assert.deepEqual(spec.options.continuous, ["age", "length_of_stay", "crp"]);
  assert.deepEqual(spec.options.categorical, ["sex", "diabetes"]);
  assert.equal(spec.options.caption, SUMMARY_DEMO.label);
  assert.equal(spec.options.show_plots, true);
  assert.ok(!spec.options.overrides || Object.keys(spec.options.overrides).length === 0);
}
{
  const spec = buildSummaryDemoSpec({ groupBy: null, showPlots: false, forceMean: true });
  assert.equal(spec.roles.group, null);
  assert.equal(spec.options.overrides.length_of_stay, "mean");
  assert.equal(spec.options.overrides.age, "mean");
  assert.equal(spec.options.show_plots, false);
}
console.log("ok - buildSummaryDemoSpec");

import assert from "node:assert";
import { buildLinearSpec, distinctValues, mostFrequent } from "./spec.js";

const table = {
  columns: ["los", "arm", "age", "note"],
  rows: [
    { los: "6.1", arm: "A", age: "60", note: "x" },
    { los: "7.4", arm: "B", age: "70", note: "y" },
    { los: "5.0", arm: "A", age: "65", note: "z" },
  ],
};
const roles = { outcome: "los", covariates: ["arm", "age"] };

const spec = buildLinearSpec(table, roles, { arm: "B" }, { age: 10 }, { source_filename: "f.csv" });
assert.equal(spec.figure, "linear");
assert.deepEqual(spec.roles, { outcome: "los", covariates: ["arm", "age"] });
assert.ok(!("event_value" in spec.options), "a continuous outcome has no event value");
assert.deepEqual(spec.options.ref_levels, { arm: "B" });
assert.deepEqual(spec.options.increments, { age: 10 });
assert.equal(spec.options.source_filename, "f.csv");
assert.deepEqual(spec.options.source_roles, { outcome: "los", covariates: ["arm", "age"] });
// no-egress: only mapped columns cross
for (const row of spec.data) assert.ok(!("note" in row), "note column must not cross");
assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "los"]);
// defensive copies
spec.roles.covariates.push("tampered");
assert.deepEqual(roles.covariates, ["arm", "age"]);
assert.deepEqual(spec.options.source_roles.covariates, ["arm", "age"]);
// demo-shape defaults
const demoSpec = buildLinearSpec(table, roles, null, null, {});
assert.equal(demoSpec.options.source_filename, null);
assert.deepEqual(demoSpec.options.ref_levels, {});
assert.deepEqual(demoSpec.options.increments, {});
// re-exports
assert.deepEqual(distinctValues(table, "arm"), ["A", "B"]);
assert.equal(mostFrequent(table, "arm"), "A");
console.log("ok - linear spec");

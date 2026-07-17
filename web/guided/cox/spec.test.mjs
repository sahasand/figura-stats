import { buildCoxSpec, distinctValues, mostFrequent } from "./spec.js";
import assert from "node:assert";

const table = { columns: ["t", "s", "arm", "age", "extra"],
  rows: [ { t: "5", s: "dead", arm: "A", age: "60", extra: "x" },
          { t: "9", s: "alive", arm: "B", age: "70", extra: "y" },
          { t: "3", s: "dead", arm: "A", age: "65", extra: "z" } ] };
const roles = { time: "t", status: "s", covariates: ["arm", "age"] };

const spec = buildCoxSpec(table, roles, "dead", { arm: "B" },
  { source_filename: "f.csv" });
assert.equal(spec.figure, "cox");
assert.deepEqual(spec.roles.covariates, ["arm", "age"]);
assert.equal(spec.options.event_value, "dead");
assert.deepEqual(spec.options.ref_levels, { arm: "B" });
// only mapped columns cross — never "extra"
assert.ok(!("extra" in spec.data[0]), "extra column must not cross to the worker");
assert.ok("t" in spec.data[0] && "s" in spec.data[0] && "arm" in spec.data[0]);
assert.equal(spec.options.source_roles.time, "t");
assert.deepEqual(spec.options.source_roles.covariates, ["arm", "age"]);
assert.equal(spec.options.source_roles.event, "dead");

// demo-shape: no source_filename -> null, ref_levels defaults to {}
const demoSpec = buildCoxSpec(table, roles, "dead", null, {});
assert.equal(demoSpec.options.source_filename, null);
assert.deepEqual(demoSpec.options.ref_levels, {});

assert.equal(mostFrequent(table, "arm"), "A");
assert.deepEqual(distinctValues(table, "s"), ["dead", "alive"]);

console.log("cox spec.test.mjs ok");

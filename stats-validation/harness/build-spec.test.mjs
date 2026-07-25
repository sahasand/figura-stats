import assert from "node:assert/strict";
import { buildSpecForCase } from "./build-spec.mjs";

const spec = await buildSpecForCase("stats-validation/cases/logistic-confounding");

assert.equal(spec.figure, "logistic");
assert.equal(spec.roles.outcome, "complication");
assert.deepEqual(spec.roles.covariates, ["arm", "age", "stage"]);
assert.equal(spec.options.event_value, "Yes");
assert.equal(spec.options.increments.age, 10);
assert.ok(Array.isArray(spec.data), "data must be an array of row objects");
assert.ok(spec.data.length > 0, "data must not be empty");

// Only mapped columns cross into the spec (the no-egress narrowing).
assert.deepEqual(
  Object.keys(spec.data[0]).sort(),
  ["age", "arm", "complication", "stage"].sort()
);

console.log("build-spec.test.mjs ok");

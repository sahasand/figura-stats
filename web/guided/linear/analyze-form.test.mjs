// web/guided/linear/analyze-form.test.mjs
// The DOM wiring is exercised by the Playwright e2e test; the decisions live
// in pure helpers tested here.
import { linearReadiness, normalizeIncrement, countDroppedRows } from "./analyze-form.js";
import assert from "node:assert";

{
  const ok = linearReadiness({ outcome: "los", covariates: ["arm", "age"] });
  assert.equal(ok.ready, true);
  assert.equal(ok.reason, "");
}
{
  const r = linearReadiness(null);
  assert.equal(r.ready, false);
  assert.match(r.reason, /numeric outcome/i);
  assert.match(r.reason, /covariate/i);
}
{
  const r = linearReadiness({ outcome: "los", covariates: [] });
  assert.equal(r.ready, false);
  assert.match(r.reason, /covariate/i);
}
{
  const r = linearReadiness({ outcome: "los", covariates: ["arm", "los"] });
  assert.equal(r.ready, false, "outcome cannot also be a covariate");
  assert.match(r.reason, /outcome/i);
}
// Re-exports keep the logistic contract.
assert.equal(normalizeIncrement("10"), 10);
assert.equal(normalizeIncrement("abc"), 1);
assert.equal(countDroppedRows({ rows: [{ a: "1" }, { a: "" }] }, ["a"]), 1);
console.log("ok - linear analyze form");

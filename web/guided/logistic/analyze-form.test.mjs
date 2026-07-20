// Unit tests for the non-DOM decision logic of the logistic analyze form.
// The DOM wiring itself is exercised by the Playwright e2e test; everything
// that carries a real decision lives in these pure helpers.
import { normalizeIncrement, renderReadiness, countDroppedRows }
  from "./analyze-form.js";
import assert from "node:assert";

// --- normalizeIncrement: mirrors .logistic_increment in R/logistic.R ---------
{
  assert.equal(normalizeIncrement("10"), 10, "numeric string parses");
  assert.equal(normalizeIncrement(2.5), 2.5, "number passes through");
  assert.equal(normalizeIncrement("0.5"), 0.5, "fractional increment allowed");
  assert.equal(normalizeIncrement(""), 1, "empty falls back to 1");
  assert.equal(normalizeIncrement("   "), 1, "blank falls back to 1");
  assert.equal(normalizeIncrement("abc"), 1, "non-numeric falls back to 1");
  assert.equal(normalizeIncrement("0"), 1, "zero falls back to 1");
  assert.equal(normalizeIncrement("-5"), 1, "negative falls back to 1");
  assert.equal(normalizeIncrement(null), 1, "null falls back to 1");
  assert.equal(normalizeIncrement(undefined), 1, "undefined falls back to 1");
  assert.equal(normalizeIncrement(Infinity), 1, "non-finite falls back to 1");
}

// --- renderReadiness: when is Render enabled, and why not ---------------------
{
  const ok = renderReadiness({
    roles: { outcome: "complication", covariates: ["arm", "age"] },
    eventValue: "Yes",
  });
  assert.equal(ok.ready, true);
  assert.equal(ok.reason, "");
}
{
  const r = renderReadiness({ roles: null, eventValue: "Yes" });
  assert.equal(r.ready, false, "no role mapping yet");
  // The picker nulls the whole map when either role is unset, so the reason
  // must name both halves rather than guess.
  assert.match(r.reason, /outcome/i);
  assert.match(r.reason, /covariate/i);
}
{
  const r = renderReadiness({
    roles: { outcome: "complication", covariates: [] }, eventValue: "Yes" });
  assert.equal(r.ready, false, "no covariate selected");
  assert.match(r.reason, /covariate/i);
}
{
  const r = renderReadiness({
    roles: { outcome: "complication", covariates: ["arm"] }, eventValue: "" });
  assert.equal(r.ready, false, "event value not chosen");
  assert.match(r.reason, /event/i);
}
{
  const r = renderReadiness({
    roles: { outcome: "complication", covariates: ["arm", "complication"] },
    eventValue: "Yes" });
  assert.equal(r.ready, false, "outcome cannot also be a covariate");
  assert.match(r.reason, /outcome/i);
}

// --- countDroppedRows: complete-case preview ---------------------------------
{
  const table = { rows: [
    { a: "1", b: "x" },
    { a: "", b: "y" },        // blank a
    { a: "3", b: null },      // null b
    { a: "4", b: "   " },     // whitespace-only b
    { a: "5", b: "z" },
  ] };
  // R drops a row only for an absent cell or the exact empty string; a
  // whitespace-only cell is a real categorical level there, so it is NOT dropped.
  assert.equal(countDroppedRows(table, ["a", "b"]), 2);
  assert.equal(countDroppedRows(table, ["b"]), 1, "whitespace-only is not missing");
  assert.equal(countDroppedRows(table, ["a"]), 1, "only the mapped columns count");
  assert.equal(countDroppedRows(table, []), 0);
}

console.log("ok - normalizeIncrement + renderReadiness + countDroppedRows");

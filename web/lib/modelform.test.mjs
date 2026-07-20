// Unit tests for web/lib/modelform.js — the decision logic shared by the Cox
// and logistic analyze forms. The DOM wiring of each form is exercised by its
// Playwright e2e test; everything that carries a real decision lives here.
import { retainedSelection, reconcileRefLevels, renderReadiness,
  countDroppedRows, READINESS_MESSAGES } from "./modelform.js";
import assert from "node:assert/strict";

// --- retainedSelection: a remembered dropdown value across an options rebuild -
{
  // Deselecting every covariate nulls the picker's whole role map, which
  // momentarily clears the outcome column and rebuilds the event dropdown. The
  // event the user already chose must come back when the options do.
  assert.equal(retainedSelection("dead", ["dead", "alive"], ""), "dead",
    "a still-offered remembered value survives the rebuild");
  assert.equal(retainedSelection("dead", ["Death", "Censored"], ""), "",
    "a remembered value the new column does not offer falls back");
  assert.equal(retainedSelection("", ["dead", "alive"], ""), "",
    "nothing remembered stays nothing");
  assert.equal(retainedSelection("dead", [], ""), "", "no options at all falls back");
  assert.equal(retainedSelection("B", ["A", "B"], "A"), "B",
    "the fallback is only used when the remembered value is gone");
  assert.equal(retainedSelection(undefined, ["A", "B"], "A"), "A",
    "an unremembered column takes the default");
  // This is the rule the logistic form used to leave implicit in DOM assignment
  // semantics (`select.value = <absent option>` silently leaves ""): both forms
  // now state it here, so it is the same rule and it is tested once.
  assert.equal(retainedSelection("IV", ["I", "II", "III"], "I"), "I",
    "a stale level falls back to the form's default rather than to blank");
}

// --- reconcileRefLevels: per-covariate reference levels across picker changes --
{
  const levels = { arm: ["Control", "Treated"], stage: ["I", "II", "III"], age: null };
  const levelsOf = (c) => levels[c];              // null => numeric, no reference
  const defaultOf = (c) => (levels[c] ? levels[c][0] : null);

  assert.deepEqual(
    reconcileRefLevels({ arm: "Treated" }, ["arm", "age"], levelsOf, defaultOf),
    { arm: "Treated" },
    "a chosen reference survives; a numeric covariate gets no reference at all");

  assert.deepEqual(
    reconcileRefLevels({}, ["arm", "stage"], levelsOf, defaultOf),
    { arm: "Control", stage: "I" },
    "columns with nothing remembered take their default level");

  assert.deepEqual(
    reconcileRefLevels({ stage: "IV" }, ["stage"], levelsOf, defaultOf),
    { stage: "I" },
    "a level that no longer exists falls back to the default");

  assert.deepEqual(
    reconcileRefLevels({ arm: "Treated", stage: "III" }, ["stage"], levelsOf, defaultOf),
    { stage: "III" },
    "only the covariates currently mapped appear in the result");

  assert.deepEqual(reconcileRefLevels({ arm: "Treated" }, [], levelsOf, defaultOf), {},
    "no covariates mapped -> no reference levels");

  // A column whose every cell is blank has no default level at all (mostFrequent
  // returns null); the form's <select> then simply has no options to select.
  assert.deepEqual(
    reconcileRefLevels({}, ["blank"], () => [], () => null), { blank: null },
    "a column with no levels yields the empty default, not a crash");

  const memo = { arm: "Treated" };
  reconcileRefLevels(memo, ["arm", "stage"], levelsOf, defaultOf);
  assert.deepEqual(memo, { arm: "Treated" }, "reconciling does not mutate the memo");
}

// --- renderReadiness: when is Render enabled, and why not ---------------------
// Defaults are the logistic form's rules and wording.
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
  assert.equal(r.reason, READINESS_MESSAGES.roles);
}
{
  const r = renderReadiness({
    roles: { outcome: "", covariates: ["arm"] }, eventValue: "Yes" });
  assert.equal(r.ready, false, "a mapped-but-empty outcome is not ready");
}
{
  const r = renderReadiness({
    roles: { outcome: "complication", covariates: [] }, eventValue: "Yes" });
  assert.equal(r.ready, false, "no covariate selected");
  assert.match(r.reason, /covariate/i);
}
{
  const r = renderReadiness({
    roles: { outcome: "complication" }, eventValue: "Yes" });
  assert.equal(r.ready, false, "an absent covariates key reads as none selected");
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

// The Cox form names its outcome "status" and does not gate on the overlap,
// which is exactly its pre-existing behavior — the options must preserve it.
{
  const COX = { outcomeRole: "status", checkOverlap: false,
    messages: { roles: "Choose a follow-up time column, an event status column, and at least one covariate to continue." } };
  assert.equal(renderReadiness(
    { roles: { time: "t", status: "s", covariates: ["arm"] }, eventValue: "dead" },
    COX).ready, true, "a fully mapped Cox form is ready");
  assert.equal(renderReadiness(
    { roles: { time: "t", status: "s", covariates: ["arm"] }, eventValue: "" },
    COX).ready, false, "no event value chosen");
  assert.equal(renderReadiness(
    { roles: { time: "t", status: "s", covariates: [] }, eventValue: "dead" },
    COX).ready, false, "no covariates chosen");
  assert.equal(renderReadiness({ roles: null, eventValue: "dead" }, COX).reason,
    COX.messages.roles, "the caller's wording overrides the default");
  assert.equal(renderReadiness(
    { roles: { time: "t", status: "s", covariates: ["s", "arm"] }, eventValue: "dead" },
    COX).ready, true, "checkOverlap:false leaves the outcome usable as a covariate");
  // The `outcome` key is irrelevant once outcomeRole is redirected.
  assert.equal(renderReadiness(
    { roles: { outcome: "o", covariates: ["arm"] }, eventValue: "dead" },
    COX).ready, false, "an unmapped status is not ready even if `outcome` is set");
}

// --- countDroppedRows: the preview must match R's complete-case filter --------
{
  const table = { rows: [
    { a: "1", b: "x" },
    { a: "", b: "y" },        // blank a
    { a: "3", b: null },      // null b
    { a: "4", b: "   " },     // whitespace-only b
    { a: "5", b: "z" },
  ] };
  // R/cox.R and R/logistic.R drop a row only for an absent cell or the exact
  // empty string; a whitespace-only cell survives there as a real categorical
  // level, so counting it would tell the user rows are excluded that are not.
  assert.equal(countDroppedRows(table, ["a", "b"]), 2,
    "a row missing either column is counted once");
  assert.equal(countDroppedRows(table, ["b"]), 1, "whitespace-only is not missing");
  assert.equal(countDroppedRows(table, ["a"]), 1, "only the mapped columns count");
  assert.equal(countDroppedRows(table, []), 0, "no columns mapped -> nothing dropped");
  assert.equal(countDroppedRows({ rows: [] }, ["a"]), 0, "no rows -> nothing dropped");
  assert.equal(countDroppedRows(table, ["missing"]), 5,
    "a column absent from every row drops every row");
}

console.log("ok - modelform: retainedSelection + reconcileRefLevels + renderReadiness + countDroppedRows");

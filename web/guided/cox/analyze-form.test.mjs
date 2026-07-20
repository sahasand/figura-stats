// Unit tests for the non-DOM decision logic of the Cox analyze form.
// The DOM wiring itself is exercised by the Playwright e2e test; the real
// decisions live in these pure helpers, which keep the user's event value and
// reference-level choices alive across a column-picker rebuild.
import { retainedSelection, reconcileRefLevels, countDroppedRows }
  from "./analyze-form.js";
import assert from "node:assert";

// --- retainedSelection: a remembered dropdown value across an options rebuild -
{
  // Bug 1: deselecting every covariate nulls the picker's whole role map, which
  // momentarily clears the status column and rebuilds the event dropdown. The
  // event the user already chose must come back when the options do.
  assert.equal(retainedSelection("dead", ["dead", "alive"], ""), "dead",
    "a still-offered remembered value survives the rebuild");
  assert.equal(retainedSelection("dead", ["Death", "Censored"], ""), "",
    "a remembered value the new column does not offer falls back");
  assert.equal(retainedSelection("", ["dead", "alive"], ""), "",
    "nothing remembered stays nothing");
  assert.equal(retainedSelection("dead", [], ""), "",
    "no options at all falls back");
  assert.equal(retainedSelection("B", ["A", "B"], "A"), "B",
    "the fallback is only used when the remembered value is gone");
  assert.equal(retainedSelection(undefined, ["A", "B"], "A"), "A",
    "an unremembered column takes the default");
}

// --- reconcileRefLevels: per-covariate reference levels across picker changes --
{
  const levels = { arm: ["Control", "Treated"], stage: ["I", "II", "III"], age: null };
  const levelsOf = (c) => levels[c];              // null => numeric, no reference
  const defaultOf = (c) => (levels[c] ? levels[c][0] : null);

  // Bug 2: the dropdowns are rebuilt on every picker change, so a deliberately
  // chosen reference must be reconciled in, not reset to the default.
  assert.deepEqual(
    reconcileRefLevels({ arm: "Treated" }, ["arm", "age"], levelsOf, defaultOf),
    { arm: "Treated" },
    "a chosen reference survives; a numeric covariate gets no reference at all");

  assert.deepEqual(
    reconcileRefLevels({}, ["arm", "stage"], levelsOf, defaultOf),
    { arm: "Control", stage: "I" },
    "columns with nothing remembered take their default level");

  // A remembered level that is not among the current column's values (a
  // different file, or the column remapped) must not be restored blindly.
  assert.deepEqual(
    reconcileRefLevels({ stage: "IV" }, ["stage"], levelsOf, defaultOf),
    { stage: "I" },
    "a level that no longer exists falls back to the default");

  // Memory is keyed by column name, so unmapping a covariate must drop it from
  // the result even though the memo still holds it (deselect-all then reselect).
  assert.deepEqual(
    reconcileRefLevels({ arm: "Treated", stage: "III" }, ["stage"], levelsOf, defaultOf),
    { stage: "III" },
    "only the covariates currently mapped appear in the result");

  assert.deepEqual(
    reconcileRefLevels({ arm: "Treated" }, [], levelsOf, defaultOf), {},
    "no covariates mapped -> no reference levels");

  // The memo is not mutated: the form re-harvests it from the live DOM.
  const memo = { arm: "Treated" };
  reconcileRefLevels(memo, ["arm", "stage"], levelsOf, defaultOf);
  assert.deepEqual(memo, { arm: "Treated" }, "reconciling does not mutate the memo");
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
  // R/cox.R drops a row only for an absent cell or the exact empty string; a
  // whitespace-only cell survives there as a real categorical level, so counting
  // it here would tell the user rows are excluded that in fact are not.
  assert.equal(countDroppedRows(table, ["a", "b"]), 2);
  assert.equal(countDroppedRows(table, ["b"]), 1, "whitespace-only is not missing");
  assert.equal(countDroppedRows(table, ["a"]), 1, "only the mapped columns count");
  assert.equal(countDroppedRows(table, []), 0);
}

console.log("ok - retainedSelection + reconcileRefLevels + countDroppedRows");

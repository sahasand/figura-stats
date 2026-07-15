import assert from "node:assert";
import { renderColumnPicker } from "./columnpicker.js";

// Minimal fake DOM: elements track children, value, options, and change handler.
function makeDoc() {
  const mk = (tag) => ({
    tag, children: [], style: {}, options: [], value: "", multiple: false,
    selected: false, id: "", htmlFor: "",
    textContent: "", onchange: null, appendChild(c) { this.children.push(c); },
    querySelectorAll() { return []; },
    add(o) { this.options.push(o); },
  });
  return { createElement: mk };
}

const table = {
  columns: ["age", "arm", "resp"],
  rows: [{ age: "61", arm: "A", resp: "1" }],
  types: { age: "numeric", arm: "categorical", resp: "numeric" },
};
const container = { children: [], innerHTML: "", appendChild(c) { this.children.push(c); } };
const roles = [
  { key: "value", label: "Value", type: "numeric" },
  { key: "group", label: "Group", type: "categorical" },
];
let ready = "unset";
const picker = renderColumnPicker(container, roles, table, (m) => { ready = m; }, makeDoc());

// Numeric role must offer only numeric columns; categorical only categorical.
const selects = container.children.filter((c) => c.tag === "select");
assert.equal(selects.length, 2);
assert.deepEqual(selects[0].options.map((o) => o.value).filter(Boolean), ["age", "resp"]);
assert.deepEqual(selects[1].options.map((o) => o.value).filter(Boolean), ["arm"]);

// Simulate the user choosing both roles.
selects[0].value = "age"; selects[0].onchange();
selects[1].value = "arm"; selects[1].onchange();
assert.deepEqual(picker.value(), { value: "age", group: "arm" });
assert.deepEqual(ready, { value: "age", group: "arm" });

// Label <-> select association (real-browser usability).
const [valueLabel, valueSelect] = [container.children[0], selects[0]];
assert.equal(valueSelect.id, "cp_value");
assert.equal(valueLabel.htmlFor, "cp_value");

// --- multiple: true path (regression table's covariate selection depends on this) ---
const table2 = {
  columns: ["colA", "colB", "colC"],
  rows: [{ colA: "1", colB: "2", colC: "3" }],
  types: { colA: "numeric", colB: "numeric", colC: "categorical" },
};
const container2 = { children: [], innerHTML: "", appendChild(c) { this.children.push(c); } };
const roles2 = [{ key: "covariates", label: "Covariates", type: "any", multiple: true }];
let ready2 = "unset";
const picker2 = renderColumnPicker(container2, roles2, table2, (m) => { ready2 = m; }, makeDoc());
const covSelect = container2.children.filter((c) => c.tag === "select")[0];
assert.equal(covSelect.multiple, true);
assert.deepEqual(covSelect.options.map((o) => o.value), ["colA", "colB", "colC"]);

// 0 selected -> map is null (multiple role with no picks makes the whole map null).
covSelect.options.forEach((o) => { o.selected = false; });
covSelect.onchange();
assert.equal(picker2.value(), null);
assert.equal(ready2, null);

// Exactly 1 selected -> ["colA"].
covSelect.options[0].selected = true;
covSelect.onchange();
assert.deepEqual(picker2.value(), { covariates: ["colA"] });
assert.deepEqual(ready2, { covariates: ["colA"] });

// 2 selected -> ["colA","colB"].
covSelect.options[1].selected = true;
covSelect.onchange();
assert.deepEqual(picker2.value(), { covariates: ["colA", "colB"] });
assert.deepEqual(ready2, { covariates: ["colA", "colB"] });

// Label <-> select association for the multi-select role too.
const covLabel = container2.children.filter((c) => c.tag === "label")[0];
assert.equal(covSelect.id, "cp_covariates");
assert.equal(covLabel.htmlFor, "cp_covariates");

// --- optional: true path (summary form's group picker depends on this) ---
{
  const container3 = { children: [], innerHTML: "", appendChild(c) { this.children.push(c); } };
  const table3 = { columns: ["a", "g"], rows: [{ a: "1", g: "x" }],
                   types: { a: "numeric", g: "categorical" } };
  let last;
  renderColumnPicker(
    container3,
    [{ key: "group", label: "Group by", type: "categorical", optional: true }],
    table3, (v) => { last = v; }, makeDoc());
  assert.deepEqual(last, { group: null }, "blank optional role maps to null, not an incomplete map");
  console.log("ok - columnpicker optional role");
}

// --- "categorical+" role type: numeric-coded groups admitted after true categoricals ---
{
  const table4 = { columns: ["age", "arm", "ecog"], rows: [],
    types: { age: "numeric", arm: "categorical", ecog: "numeric" } };
  const container4 = { children: [], innerHTML: "", appendChild(c) { this.children.push(c); } };
  let got = null;
  renderColumnPicker(container4, [{ key: "x", label: "X", type: "categorical+" }],
    table4, (v) => { got = v; }, makeDoc());
  const opts = container4.children[1].options.map((o) => [o.value, o.textContent]);
  // blank, then categoricals, then numerics with the hint suffix
  assert.deepEqual(opts.slice(1),
    [["arm", "arm"], ["age", "age (as categories)"], ["ecog", "ecog (as categories)"]]);
  console.log("ok - columnpicker categorical+ role");
}

console.log("columnpicker.test.mjs OK");

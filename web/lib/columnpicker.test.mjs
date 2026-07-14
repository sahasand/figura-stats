import assert from "node:assert";
import { renderColumnPicker } from "./columnpicker.js";

// Minimal fake DOM: elements track children, value, options, and change handler.
function makeDoc() {
  const mk = (tag) => ({
    tag, children: [], style: {}, options: [], value: "", multiple: false,
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

console.log("columnpicker.test.mjs OK");

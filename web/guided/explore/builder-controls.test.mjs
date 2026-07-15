// web/guided/explore/builder-controls.test.mjs
import assert from "node:assert/strict";
import { GEOM_ROLES, defaultOptions, buildExploreSpec, renderBuilderControls } from "./builder-controls.js";

const table = {
  columns: ["age", "bmi", "arm", "ecog"],
  types: { age: "numeric", bmi: "numeric", arm: "categorical", ecog: "numeric" },
  rows: [
    { age: 61, bmi: 24.1, arm: "Control", ecog: 0 },
    { age: 55, bmi: 27.9, arm: "Treatment", ecog: 1 },
  ],
};

// Roles per geom: scatter needs numeric x/y; boxplot categorical+ x.
{
  const s = GEOM_ROLES("scatter");
  assert.deepEqual(s.map((r) => [r.key, r.type, !!r.optional]), [
    ["x", "numeric", false], ["y", "numeric", false],
    ["color", "categorical+", true], ["facet", "categorical+", true]]);
  const l = GEOM_ROLES("line").map((r) => r.key);
  assert.deepEqual(l, ["x", "y", "color", "group", "facet"]);
  const b = GEOM_ROLES("bar");
  assert.equal(b.find((r) => r.key === "x").type, "categorical+");
  assert.ok(!b.some((r) => r.key === "y"));
}

// Tagged union: only the active geom's option keys + shared keys are sent.
{
  const spec = buildExploreSpec(table,
    { x: "age", y: "bmi", color: "arm", facet: null },
    { ...defaultOptions("scatter"), title: "T" });
  assert.equal(spec.figure, "explore");
  assert.deepEqual(Object.keys(spec.options).sort(),
    ["alpha", "geom", "point_size", "se", "smoother", "title", "xlab", "ylab"]);
  assert.equal(spec.options.geom, "scatter");
  // Rows are projected to used columns only — unmapped data never crosses.
  assert.deepEqual(Object.keys(spec.data[0]).sort(), ["age", "arm", "bmi"]);
  assert.equal(spec.roles.facet, null);
}

// Caption rides along when provided (demo path).
{
  const spec = buildExploreSpec(table, { x: "ecog" },
    defaultOptions("bar"), "Synthetic demo");
  assert.equal(spec.options.caption, "Synthetic demo");
  assert.deepEqual(Object.keys(spec.data[0]), ["ecog"]);
}
// --- DOM control panel (fake DOM, same idiom as columnpicker.test.mjs) ---
// Selects mirror the HTML spec: assigning a value with no matching <option>
// coerces to "" (selectedIndex = -1) — the exact behavior the geom-switch
// reconcile guards against.
function byId(el, id) {
  if (el.id === id) return el;
  for (const c of el.children || []) { const hit = byId(c, id); if (hit) return hit; }
  return null;
}
function makeDoc() {
  const mk = (tag) => {
    const el = {
      tag, children: [], options: [], id: "", htmlFor: "", className: "",
      textContent: "", type: "", checked: false, multiple: false, selected: false,
      onchange: null, oninput: null,
      appendChild(c) { this.children.push(c); return c; },
      append(...cs) { this.children.push(...cs); },
      add(o) { this.options.push(o); },
      querySelector(q) { return byId(this, q.slice(1)); },
    };
    Object.defineProperty(el, "innerHTML", {
      get() { return ""; },
      set(v) { if (v === "") el.children.length = 0; },
    });
    if (tag === "select") {
      let val = "";
      Object.defineProperty(el, "value", {
        get() { return val; },
        set(v) { v = String(v); val = el.options.some((o) => o.value === v) ? v : ""; },
      });
    } else {
      el.value = "";
    }
    return el;
  };
  return { createElement: mk };
}

// Geom switch reconciles roles to the DOM: a selection with no matching option
// in the new picker (categorical "arm" in scatter's numeric x) must emit as
// null, never leak stale; still-valid selections carry over.
{
  const doc = makeDoc();
  const container = doc.createElement("div");
  let last = null;
  renderBuilderControls(container, table,
    { roles: { x: "arm", y: "bmi", color: null, facet: null },
      options: defaultOptions("boxplot") },
    (s) => { last = s; }, doc);
  const geomSel = byId(container, "explore-geom");
  geomSel.value = "scatter";
  geomSel.onchange();
  assert.equal(last.options.geom, "scatter");
  assert.equal(last.roles.x, null, "stale categorical x must not leak into scatter");
  assert.equal(last.roles.y, "bmi", "still-valid selection carries over");
  console.log("ok - builder-controls geom-switch reconcile");
}

// Clearing a number input must not emit 0 (Number("") === 0); the field is
// restored and nothing is emitted. Real edits still work.
{
  const doc = makeDoc();
  const container = doc.createElement("div");
  let emits = 0, last = null;
  renderBuilderControls(container, table,
    { roles: { x: "age", color: null, facet: null },
      options: defaultOptions("histogram") },
    (s) => { emits++; last = s; }, doc);
  const bins = byId(container, "opt-bins");
  bins.value = "";
  bins.onchange();
  assert.equal(emits, 0, "empty number field must not emit");
  assert.equal(String(bins.value), "30", "field restored to current value");
  bins.value = "40";
  bins.onchange();
  assert.equal(emits, 1);
  assert.equal(last.options.bins, 40);
  console.log("ok - builder-controls empty-number guard");
}

console.log("builder-controls.test.mjs OK");

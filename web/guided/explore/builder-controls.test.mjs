// web/guided/explore/builder-controls.test.mjs
import assert from "node:assert/strict";
import { GEOM_ROLES, defaultOptions, buildExploreSpec } from "./builder-controls.js";

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
console.log("builder-controls.test.mjs OK");

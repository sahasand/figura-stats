// web/guided/explore/demo.js
import { EXPLORE_DEMO } from "./demo-data.js";
import { buildExploreSpec, defaultOptions } from "./builder-controls.js";

// The demo table in csv.js shape, so the builder controls work identically
// on the demo and on uploaded data.
export const DEMO_TABLE = {
  columns: EXPLORE_DEMO.columns,
  rows: EXPLORE_DEMO.rows,
  types: { patient_id: "categorical", visit_month: "numeric", age: "numeric",
           bmi: "numeric", biomarker: "numeric", arm: "categorical",
           sex: "categorical", ecog: "numeric" },
};

// Fresh nested objects on every call — session-state resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return {
    roles: { x: "age", y: "biomarker", color: "arm", facet: null },
    options: defaultOptions("scatter"),
  };
}

// Same request path as user data; the synthetic label is baked INTO the
// rendered figure via options.caption (mirrors the Summary demo).
export function buildExploreDemoSpec(demoState) {
  return buildExploreSpec(DEMO_TABLE, demoState.roles, demoState.options,
    EXPLORE_DEMO.label);
}

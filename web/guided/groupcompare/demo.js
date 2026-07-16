import { GROUPCOMPARE_DEMO } from "./demo-data.js";
import { buildGroupCompareSpec } from "./spec.js";

export const DEMO_TABLE = {
  columns: GROUPCOMPARE_DEMO.columns,
  rows: GROUPCOMPARE_DEMO.rows,
  types: { arm: "categorical", biomarker_normal: "numeric",
           los_skewed: "numeric", responder: "categorical" },
};

// Fresh nested objects each call — the guided session store resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return { roles: { group: "arm", outcome: "biomarker_normal" },
           options: { plot: "box", test: "auto" } };
}

export function buildGroupCompareDemoSpec(demoState) {
  return buildGroupCompareSpec(DEMO_TABLE, demoState.roles, demoState.options);
}

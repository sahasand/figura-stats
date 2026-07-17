import { COX_DEMO } from "./demo-data.js";

export const DEMO_TABLE = {
  columns: COX_DEMO.columns,
  rows: COX_DEMO.rows,
  types: { arm: "categorical", age: "numeric", stage: "categorical",
           followup_months: "numeric", status: "categorical" },
};

// Fresh object each call — the guided session store resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return { covariates: ["arm", "age", "stage"] };
}

// The demo goes through the SAME spec shape + worker + R path as user data.
// Only the mapped columns cross (no-egress). The synthetic label rides along as
// options.caption; ref levels are fixed so the confounding story is stable.
export function buildCoxDemoSpec(demoState) {
  const used = ["followup_months", "status", ...demoState.covariates];
  const data = COX_DEMO.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "cox",
    data,
    roles: { time: "followup_months", status: "status",
             covariates: demoState.covariates.slice() },
    options: { event_value: "Death",
               ref_levels: { arm: "Standard care", stage: "I" },
               caption: COX_DEMO.label },
  };
}

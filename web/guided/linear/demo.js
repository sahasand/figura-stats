import { LINEAR_DEMO } from "./demo-data.js";

export const DEMO_TABLE = {
  columns: LINEAR_DEMO.columns,
  rows: LINEAR_DEMO.rows,
  types: { arm: "categorical", age: "numeric", stage: "categorical", los: "numeric" },
};

// Fresh object each call — the guided session store resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return { covariates: ["arm", "age", "stage"] };
}

// The demo goes through the SAME spec shape + worker + R path as user data.
// ref_levels match the most-frequent default and are stated so the table
// reads the same way every time; age is reported per 10 years. source_filename
// is deliberately ABSENT so the generated .R script embeds the example data.
export function buildLinearDemoSpec(demoState) {
  const used = ["los", ...demoState.covariates];
  const data = LINEAR_DEMO.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "linear",
    data,
    roles: { outcome: "los", covariates: demoState.covariates.slice() },
    options: { ref_levels: { arm: "Standard care", stage: "I" },
               increments: { age: 10 },
               caption: LINEAR_DEMO.label },
  };
}

import { LOGISTIC_DEMO } from "./demo-data.js";

export const DEMO_TABLE = {
  columns: LOGISTIC_DEMO.columns,
  rows: LOGISTIC_DEMO.rows,
  types: { arm: "categorical", age: "numeric", stage: "categorical",
           complication: "categorical" },
};

// Fresh object each call — the guided session store resets by shallow copy.
export function DEFAULT_DEMO_STATE() {
  return { covariates: ["arm", "age", "stage"] };
}

// The demo goes through the SAME spec shape + worker + R path as user data. Only
// the mapped columns cross (no-egress). Three option values are pinned so the
// confounding story is stable and reproducible:
//   - event_value: R has no default (it falls back to "" and yields an all-zero
//     outcome), and "No" is the majority level, so this must be explicit.
//   - ref_levels: they match what the most-frequent default would pick anyway,
//     stated here so the table reads the same way every time.
//   - increments: age is reported per 10 years, which is the clinically
//     meaningful step and showcases the increment feature.
// source_filename is deliberately ABSENT: its absence is what makes the
// generated .R script embed the example data instead of emitting a read.csv.
// caption rides along for parity with the other demos; fig_logistic renders a
// table rather than a captioned ggplot, so the shell's banner is what the user
// sees carrying the synthetic label.
export function buildLogisticDemoSpec(demoState) {
  const used = ["complication", ...demoState.covariates];
  const data = LOGISTIC_DEMO.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "logistic",
    data,
    roles: { outcome: "complication", covariates: demoState.covariates.slice() },
    options: { event_value: "Yes",
               ref_levels: { arm: "Standard care", stage: "I" },
               increments: { age: 10 },
               caption: LOGISTIC_DEMO.label },
  };
}

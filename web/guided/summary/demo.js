import { SUMMARY_DEMO } from "./demo-data.js";

const CONTINUOUS = ["age", "length_of_stay", "crp"];
const CATEGORICAL = ["sex", "diabetes"];
const LABELS = { length_of_stay: "Length of stay", crp: "CRP",
  age: "Age", sex: "Sex", diabetes: "Diabetes" };

// Same request path as user data: the tutorial demonstrates the real workflow.
// The synthetic label rides along as options.caption so it is baked INTO the
// rendered figure, not only shown in the surrounding UI.
export function buildSummaryDemoSpec(demoOptions) {
  const overrides = {};
  if (demoOptions.forceMean) for (const c of CONTINUOUS) overrides[c] = "mean";
  return {
    figure: "summary",
    data: SUMMARY_DEMO.rows,
    roles: { group: demoOptions.groupBy },
    options: {
      continuous: CONTINUOUS,
      categorical: CATEGORICAL,
      labels: LABELS,
      overrides,
      show_plots: demoOptions.showPlots,
      show_qq: !!demoOptions.showQq,
      caption: SUMMARY_DEMO.label,
    },
  };
}

import { KM_DEMO } from "./demo-data.js";

// The demo goes through the SAME request builder + worker + R path as user
// data (PRD: the tutorial demonstrates the real workflow, not a canned output).
// The synthetic label rides along as options.caption so it is baked INTO the
// rendered SVG, not just shown in the surrounding UI.
export function buildDemoSpec(demoOptions) {
  return {
    figure: "km",
    data: KM_DEMO.rows.map((r) => ({
      time: r.followup_months,
      status: r.status === "Death" ? 1 : 0,
      group: r.group,
    })),
    options: {
      time_label: "Months since randomization",
      theme: "generic",
      caption: KM_DEMO.label,
      reference: "Standard care",
      conf_int: demoOptions.conf_int,
      landmarks: demoOptions.landmarks,
      ...(demoOptions.horizon ? { horizon: demoOptions.horizon } : {}),
    },
  };
}

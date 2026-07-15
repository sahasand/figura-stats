// web/guided/summary/guided-summary.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, CALLOUTS } from "./content.js";
import { buildSummaryDemoSpec } from "./demo.js";
import { SUMMARY_DEMO } from "./demo-data.js";
import { renderSummaryForm } from "./analyze-form.js";

function renderSummaryExperiments(panel, ctx, rerun) {
  const o = ctx.getSession().demoOptions;
  panel.querySelector("#demo-experiments").innerHTML = `
    <h4>Optional experiments</h4>
    <label><input type="checkbox" id="exp-group" ${o.groupBy ? "checked" : ""}>
      Group by study arm</label>
    <p class="callout">${CALLOUTS.groupBy}</p>
    <label><input type="checkbox" id="exp-plots" ${o.showPlots ? "checked" : ""}>
      Show distribution plots</label>
    <p class="callout">${CALLOUTS.showPlots}</p>
    <label><input type="checkbox" id="exp-qq" ${o.showQq ? "checked" : ""}>
      Show Q–Q normality panels</label>
    <p class="callout">${CALLOUTS.showQq}</p>
    <label><input type="checkbox" id="exp-forcemean" ${o.forceMean ? "checked" : ""}>
      Force mean ± SD on every variable</label>
    <p class="callout">${CALLOUTS.forceMean}</p>`;
  panel.querySelector("#exp-group").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ groupBy: e.target.checked ? "arm" : null }); rerun();
  });
  panel.querySelector("#exp-plots").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ showPlots: e.target.checked }); rerun();
  });
  panel.querySelector("#exp-qq").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ showQq: e.target.checked }); rerun();
  });
  panel.querySelector("#exp-forcemean").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ forceMean: e.target.checked }); rerun();
  });
}

export const renderGuidedSummary = createGuidedShell({
  title: "Summary statistics",
  hashPrefix: "summary",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: SUMMARY_DEMO.label,
  buildDemoSpec: buildSummaryDemoSpec,
  defaultDemoOptions: () => ({ groupBy: "arm", showPlots: true, forceMean: false, showQq: false }),
  experimentControlsSelector: "#exp-group, #exp-plots, #exp-qq, #exp-forcemean",
  renderExperiments: renderSummaryExperiments,
  renderAnalyzeForm: renderSummaryForm,
});

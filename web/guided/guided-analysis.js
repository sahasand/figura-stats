// web/guided/guided-analysis.js
// KM's guided shell = the shared factory + KM content/demo/form/experiments.
// Behavior must be byte-identical to the pre-factory shell; the KM unit and
// e2e suites are the regression gate.
import { createGuidedShell } from "./shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, CALLOUTS } from "./km/content.js";
import { buildDemoSpec } from "./km/demo.js";
import { KM_DEMO } from "./km/demo-data.js";
import { renderKmForm } from "../forms/km.js";

function renderKmExperiments(panel, ctx, rerun) {
  const o = ctx.getSession().demoOptions;
  panel.querySelector("#demo-experiments").innerHTML = `
    <h4>Optional experiments</h4>
    <label><input type="checkbox" id="exp-ci" ${o.conf_int ? "checked" : ""}>
      Show 95% confidence bands</label>
    <p class="callout">${CALLOUTS.confidenceBands}</p>
    <label><input type="checkbox" id="exp-landmarks" ${o.landmarks.length ? "checked" : ""}>
      Report survival at 12 and 24 months</label>
    <p class="callout">${CALLOUTS.landmarks}</p>
    <label>Displayed horizon
      <select id="exp-horizon">
        <option value="" ${o.horizon === null ? "selected" : ""}>Full follow-up (36 months)</option>
        <option value="24" ${o.horizon === 24 ? "selected" : ""}>24 months</option>
      </select></label>
    <p class="callout">${CALLOUTS.horizon}</p>`;
  panel.querySelector("#exp-ci").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ conf_int: e.target.checked }); rerun();
  });
  panel.querySelector("#exp-landmarks").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ landmarks: e.target.checked ? [12, 24] : [] }); rerun();
  });
  panel.querySelector("#exp-horizon").addEventListener("change", (e) => {
    ctx.patchDemoOptions({ horizon: e.target.value ? Number(e.target.value) : null }); rerun();
  });
}

export const renderGuidedKm = createGuidedShell({
  title: "Kaplan–Meier",
  hashPrefix: "km",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: KM_DEMO.label,
  buildDemoSpec,
  defaultDemoOptions: () => ({ conf_int: true, landmarks: [], horizon: null }),
  experimentControlsSelector: "#exp-ci, #exp-landmarks, #exp-horizon",
  renderExperiments: renderKmExperiments,
  renderAnalyzeForm: renderKmForm,
});

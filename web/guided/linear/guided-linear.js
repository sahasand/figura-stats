import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderLinearExperiments } from "./content.js";
import { buildLinearDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { LINEAR_DEMO } from "./demo-data.js";
import { renderLinearAnalyzeForm } from "./analyze-form.js";

export const renderGuidedLinear = createGuidedShell({
  title: "Linear regression",
  hashPrefix: "linear",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: LINEAR_DEMO.label,
  buildDemoSpec: buildLinearDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments input",
  renderExperiments: renderLinearExperiments,
  renderAnalyzeForm: renderLinearAnalyzeForm,
});

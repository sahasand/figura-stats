// web/guided/cox/guided-cox.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderCoxExperiments } from "./content.js";
import { buildCoxDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { COX_DEMO } from "./demo-data.js";
import { renderCoxAnalyzeForm } from "./analyze-form.js";

export const renderGuidedCox = createGuidedShell({
  title: "Cox regression",
  hashPrefix: "cox",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: COX_DEMO.label,
  buildDemoSpec: buildCoxDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments input",
  renderExperiments: renderCoxExperiments,
  renderAnalyzeForm: renderCoxAnalyzeForm,
});

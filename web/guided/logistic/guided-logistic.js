// web/guided/logistic/guided-logistic.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderLogisticExperiments } from "./content.js";
import { buildLogisticDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { LOGISTIC_DEMO } from "./demo-data.js";
import { renderLogisticAnalyzeForm } from "./analyze-form.js";

export const renderGuidedLogistic = createGuidedShell({
  title: "Logistic regression",
  hashPrefix: "logistic",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: LOGISTIC_DEMO.label,
  buildDemoSpec: buildLogisticDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments input",
  renderExperiments: renderLogisticExperiments,
  renderAnalyzeForm: renderLogisticAnalyzeForm,
});

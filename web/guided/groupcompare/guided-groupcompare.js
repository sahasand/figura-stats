// web/guided/groupcompare/guided-groupcompare.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, renderGroupCompareExperiments }
  from "./content.js";
import { buildGroupCompareDemoSpec, DEFAULT_DEMO_STATE } from "./demo.js";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";
import { renderGroupCompareForm } from "./analyze-form.js";

export const renderGuidedGroupCompare = createGuidedShell({
  title: "Group comparison",
  hashPrefix: "groupcompare",
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: GROUPCOMPARE_DEMO.label,
  buildDemoSpec: buildGroupCompareDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments select",
  renderExperiments: renderGroupCompareExperiments,
  renderAnalyzeForm: renderGroupCompareForm,
});

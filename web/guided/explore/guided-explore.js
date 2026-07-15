// web/guided/explore/guided-explore.js
import { createGuidedShell } from "../shell.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML } from "./content.js";
import { buildExploreDemoSpec, DEFAULT_DEMO_STATE, DEMO_TABLE } from "./demo.js";
import { EXPLORE_DEMO } from "./demo-data.js";
import { renderBuilderControls } from "./builder-controls.js";
import { debounce } from "../live-run.js";
import { renderExploreForm } from "./analyze-form.js";

// The "experiments" for this analysis ARE the builder. Changes patch the demo
// state and rerun (debounced); the shell's liveRender coalescer guarantees at
// most one render in flight with only the newest pending spec queued.
function renderExploreExperiments(panel, ctx, rerun) {
  const host = panel.querySelector("#demo-experiments");
  host.innerHTML = "";
  const rerunDebounced = debounce(rerun, 400);
  renderBuilderControls(host, DEMO_TABLE, ctx.getSession().demoOptions, (state) => {
    ctx.patchDemoOptions(state);
    rerunDebounced();
  });
}

export const renderGuidedExplore = createGuidedShell({
  title: "Explore plot",
  hashPrefix: "explore",
  liveRender: true,
  renderUnderstand,
  exampleIntroHtml: EXAMPLE_INTRO_HTML,
  demoLabel: EXPLORE_DEMO.label,
  buildDemoSpec: buildExploreDemoSpec,
  defaultDemoOptions: DEFAULT_DEMO_STATE,
  experimentControlsSelector: "#demo-experiments select, #demo-experiments input",
  renderExperiments: renderExploreExperiments,
  renderAnalyzeForm: renderExploreForm,
});

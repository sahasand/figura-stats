// web/guided/guided-analysis.js
import { createKmSession, setStage, storeResult, getResult, setDemoOptions, resetDemo, STAGES }
  from "./session-state.js";
import { renderUnderstand } from "./km/content.js";

const STAGE_LABELS = { understand: "Understand", example: "Try an Example", analyze: "Analyze Your Data" };
// Module-level session: survives switching to another analysis and back
// within the tab (PRD story 3/4); page reload starts clean by construction.
let session = null;

export function renderGuidedKm(container, onSubmit, runFigure) {
  session = session || createKmSession();
  // URL hash carries analysis+stage ONLY — never inputs, filenames, results.
  const fromHash = (location.hash.match(/^#km\/(\w+)$/) || [])[1];
  if (fromHash && STAGES.includes(fromHash)) session = setStage(session, fromHash);

  container.innerHTML = `
    <h2>Kaplan–Meier</h2>
    <div class="stage-tabs" role="tablist" aria-label="Guided stages">
      ${STAGES.map((s) => `
        <button type="button" role="tab" data-stage="${s}"
          id="tab-${s}" aria-controls="panel-${s}"
          aria-selected="${s === session.stage}">${STAGE_LABELS[s]}</button>`).join("")}
    </div>
    ${STAGES.map((s) => `
      <section role="tabpanel" id="panel-${s}" aria-labelledby="tab-${s}"
        data-stage-panel="${s}" ${s === session.stage ? "" : "hidden"}></section>`).join("")}`;

  function runAndShow(spec, context) {
    const preview = document.getElementById("preview");
    const stats = document.getElementById("stats");
    preview.innerHTML = "Rendering… (first run downloads R packages)";
    stats.textContent = "";
    stats.classList.remove("error");
    return runFigure(spec).then((out) => {
      if (!out.ok) {
        preview.innerHTML = "";
        stats.textContent = "Error: " + out.error;
        stats.classList.add("error");
        return out;
      }
      session = storeResult(session, context, out);
      showStored(context);
      return out;
    });
  }

  function showStored(context) {
    const out = getResult(session, context);
    const preview = document.getElementById("preview");
    const stats = document.getElementById("stats");
    if (!out) { preview.innerHTML = ""; stats.textContent = ""; return; }
    preview.innerHTML = out.svg;
    stats.textContent = out.text;
    stats.classList.remove("error");
  }

  function selectStage(stage) {
    session = setStage(session, stage);
    history.replaceState(null, "", "#km/" + stage);
    container.querySelectorAll("[role=tab]").forEach((t) =>
      t.setAttribute("aria-selected", String(t.dataset.stage === stage)));
    container.querySelectorAll("[data-stage-panel]").forEach((p) =>
      p.hidden = p.dataset.stagePanel !== stage);
    // Restore the context-appropriate result (demo for example stage,
    // user for analyze; understand keeps whatever is showing).
    if (stage === "example") showStored("demo");
    if (stage === "analyze") showStored("user");
  }

  container.querySelectorAll("[role=tab]").forEach((t) =>
    t.addEventListener("click", () => selectStage(t.dataset.stage)));

  renderPanels(container, { onSubmit, runAndShow,
    getSession: () => session,
    patchDemoOptions: (patch) => { session = setDemoOptions(session, patch); },
    resetDemoState: () => { session = resetDemo(session); showStored("demo"); } });
  selectStage(session.stage);
}

// Panels are filled in by Tasks 5, 6/7, and 8. Placeholders until then.
function renderPanels(container, ctx) {
  renderUnderstand(container.querySelector('[data-stage-panel="understand"]'));
  container.querySelector('[data-stage-panel="example"]').textContent =
    "Try an Example — coming in Task 6.";
  container.querySelector('[data-stage-panel="analyze"]').textContent =
    "Analyze Your Data — coming in Task 8.";
}

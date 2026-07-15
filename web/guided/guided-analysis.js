// web/guided/guided-analysis.js
import { createKmSession, setStage, storeResult, getResult, setDemoOptions, resetDemo,
  getDemoGeneration, isDemoGenerationCurrent, STAGES }
  from "./session-state.js";
import { renderUnderstand, EXAMPLE_INTRO_HTML, CALLOUTS } from "./km/content.js";
import { buildDemoSpec } from "./km/demo.js";
import { KM_DEMO } from "./km/demo-data.js";
import { renderKmForm } from "../forms/km.js";

const STAGE_LABELS = { understand: "Understand", example: "Try an Example", analyze: "Analyze Your Data" };
// The result context each stage is allowed to paint into the shared #preview/#stats.
// A run that resolves may repaint only if its context still matches the selected
// stage; "understand" paints nothing (null never equals a context key).
const CONTEXT_FOR_STAGE = { understand: null, example: "demo", analyze: "user" };
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
    // Snapshot the demo generation so a Reset Example landing mid-run can be
    // detected on resolve and the stale result fully dropped.
    const startGen = getDemoGeneration(session);
    return runFigure(spec).then((out) => {
      // Reset-mid-run: a demo run invalidated by Reset Example neither stores nor paints.
      if (context === "demo" && !isDemoGenerationCurrent(session, startGen)) return out;
      // Tab-switch-mid-run: paint only when this context is still the one the
      // selected stage owns. A stale-but-valid result is still stored below so it
      // reappears when its own tab is reselected.
      const shouldPaint = CONTEXT_FOR_STAGE[session.stage] === context;
      if (!out.ok) {
        if (shouldPaint) {
          preview.innerHTML = "";
          stats.textContent = "Error: " + out.error;
          stats.classList.add("error");
        }
        return out;
      }
      session = storeResult(session, context, out);
      if (shouldPaint) showStored(context);
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

function renderPanels(container, ctx) {
  renderUnderstand(container.querySelector('[data-stage-panel="understand"]'));
  renderExample(container.querySelector('[data-stage-panel="example"]'), ctx);
  // analyze panel: the existing (Stage 0-hardened) CSV form, submitting through
  // the shell so the user result is cached per-context like the demo's.
  const analyzePanel = container.querySelector('[data-stage-panel="analyze"]');
  analyzePanel.innerHTML = "";
  renderKmForm(analyzePanel, (spec) => ctx.runAndShow(spec, "user"));
}

// The synthetic label is mandatory and appears TWICE: as the visible banner here
// and, via options.caption in buildDemoSpec, baked into the rendered SVG. Both use
// KM_DEMO.label directly — never a retyped copy. webR is not warmed up here; the
// worker only boots on the first message, which is the Run Example click.
function renderExample(panel, ctx) {
  panel.innerHTML = `
    ${EXAMPLE_INTRO_HTML}
    <div class="demo-banner" role="note">${KM_DEMO.label}</div>
    <div class="demo-actions">
      <button type="button" id="run-demo">Run Example Analysis</button>
      <button type="button" id="reset-demo">Reset Example</button>
    </div>
    <div id="demo-experiments"></div>`;
  const runBtn = panel.querySelector("#run-demo");

  // Controls that must be frozen for the duration of a run: the Run and Reset
  // buttons plus the three experiment inputs. Worker requests aren't serialized,
  // so toggling an experiment mid-run could let a stale response land last and
  // silently mismatch the visible control state; disabling Reset closes the
  // reset-mid-run path at the UI (the generation counter guards it in state).
  function inFlightControls() {
    return [runBtn, panel.querySelector("#reset-demo"),
      ...panel.querySelectorAll("#exp-ci, #exp-landmarks, #exp-horizon")];
  }

  // Shared run path: the Run button always calls this, and the experiment
  // controls call it too (conditionally) so both go through one place.
  async function runDemo() {
    const controls = inFlightControls();
    controls.forEach((el) => { el.disabled = true; });   // no duplicate/overlapping runs
    try { await ctx.runAndShow(buildDemoSpec(ctx.getSession().demoOptions), "demo"); }
    finally { controls.forEach((el) => { el.disabled = false; }); }
  }

  runBtn.addEventListener("click", runDemo);
  panel.querySelector("#reset-demo").addEventListener("click", () => {
    ctx.resetDemoState();
    renderExample(panel, ctx);                    // clears result + restores default controls
  });

  // An experiment change only reruns if a demo result already exists;
  // before the first Run click it just patches the pending options.
  renderExperiments(panel, ctx, () => {
    if (ctx.getSession().results.demo) runDemo();
  });
}

function renderExperiments(panel, ctx, rerun) {
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

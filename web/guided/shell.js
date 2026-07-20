// web/guided/shell.js
// Shared guided-analysis shell: Understand / Try an Example / Analyze Your Data
// stages with hash sync, per-context result caching, and demo race guards.
// Each createGuidedShell(config) instance owns its OWN session closure — two
// guided analyses never share stage state.
import { createSession, setStage, storeResult, getResult, setDemoOptions, resetDemo,
  getDemoGeneration, isDemoGenerationCurrent, STAGES } from "./session-state.js";
import { createCoalescer } from "./live-run.js";
import { createControlLock } from "./control-lock.js";

const STAGE_LABELS = { understand: "Understand", example: "Try an Example", analyze: "Analyze Your Data" };
// The result context each stage is allowed to paint into the shared #preview/#stats.
// A run that resolves may repaint only if its context still matches the selected
// stage; "understand" paints nothing (null never equals a context key).
const CONTEXT_FOR_STAGE = { understand: null, example: "demo", analyze: "user" };

export function createGuidedShell(cfg) {
  // Per-instance session closure: survives switching to another analysis and
  // back within the tab; page reload starts clean by construction.
  let session = null;
  const hashRe = new RegExp("^#" + cfg.hashPrefix + "/(\\w+)$");

  return function renderGuidedShell(container, onSubmit, runFigure, setStatus) {
    const status = setStatus || (() => {});
    session = session || createSession(cfg.defaultDemoOptions());
    // URL hash carries analysis+stage ONLY — never inputs, filenames, results.
    const fromHash = (location.hash.match(hashRe) || [])[1];
    if (fromHash && STAGES.includes(fromHash)) session = setStage(session, fromHash);

    container.innerHTML = `
      <h2>${cfg.title}</h2>
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
      // liveRender keeps the previous figure visible under a busy overlay;
      // the classic path blanks the panes. First-ever render (empty pane)
      // still shows the boot message either way.
      if (cfg.liveRender && preview.querySelector("svg")) {
        preview.classList.add("busy");
      } else {
        preview.innerHTML = "Rendering… (first run downloads R packages)";
        stats.textContent = "";
        delete stats.dataset.rCode;
        stats.classList.remove("error");
      }
      status("busy", "R: working…");
      // Snapshot the demo generation so a Reset Example landing mid-run can be
      // detected on resolve and the stale result fully dropped.
      const startGen = getDemoGeneration(session);
      return runFigure(spec).then((out) => {
        preview.classList.remove("busy");
        // The chip reports the R session's state, not the visible pane's — set it
        // on every completion, even for results that are dropped or not painted.
        status(out.ok ? "ready" : "error", out.ok ? "R: ready" : "R: error");
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
            delete stats.dataset.rCode;
          }
          return out;
        }
        session = storeResult(session, context, out);
        if (shouldPaint) showStored(context);
        return out;
      }).finally(() => {
        // Belt-and-suspenders: the resolve path already clears "busy" first
        // (idempotent here), but if runFigure ever rejects the then never runs
        // and the overlay would stick — clearing here covers that path too.
        preview.classList.remove("busy");
      });
    }

    function showStored(context) {
      const out = getResult(session, context);
      const preview = document.getElementById("preview");
      const stats = document.getElementById("stats");
      if (!out) { preview.innerHTML = ""; stats.textContent = "";
                  delete stats.dataset.rCode; return; }
      preview.innerHTML = out.svg;
      stats.textContent = out.text;
      stats.classList.remove("error");
      if (out.code) stats.dataset.rCode = out.code;
      else delete stats.dataset.rCode;
    }

    function selectStage(stage) {
      session = setStage(session, stage);
      history.replaceState(null, "", "#" + cfg.hashPrefix + "/" + stage);
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

    const userCoalescer = cfg.liveRender
      ? createCoalescer((spec) => runAndShow(spec, "user")) : null;
    const ctx = { onSubmit, runAndShow,
      runUser: (spec) => userCoalescer ? userCoalescer.submit(spec)
                                       : runAndShow(spec, "user"),
      getSession: () => session,
      patchDemoOptions: (patch) => { session = setDemoOptions(session, patch); },
      resetDemoState: () => { session = resetDemo(session); showStored("demo"); } };

    cfg.renderUnderstand(container.querySelector('[data-stage-panel="understand"]'));
    renderExample(container.querySelector('[data-stage-panel="example"]'), ctx);
    const analyzePanel = container.querySelector('[data-stage-panel="analyze"]');
    analyzePanel.innerHTML = "";
    cfg.renderAnalyzeForm(analyzePanel, (spec) => ctx.runUser(spec));
    selectStage(session.stage);
  };

  // The synthetic label is mandatory and appears TWICE: as the visible banner here
  // and, via options.caption in the demo spec builder, baked into the rendered
  // figure. Both use cfg.demoLabel directly — never a retyped copy. webR is not
  // warmed up here; the worker only boots on the first Run Example click.
  function renderExample(panel, ctx) {
    panel.innerHTML = `
      ${cfg.exampleIntroHtml}
      <div class="demo-banner" role="note">${cfg.demoLabel}</div>
      <div class="demo-actions">
        <button type="button" id="run-demo">Run Example Analysis</button>
        <button type="button" id="reset-demo">Reset Example</button>
      </div>
      <div id="demo-experiments"></div>`;
    const runBtn = panel.querySelector("#run-demo");

    // liveRender: builder controls stay enabled; overlapping requests are
    // coalesced (one in flight, newest pending) instead of control-freezing.
    const coalescer = cfg.liveRender
      ? createCoalescer((spec) => ctx.runAndShow(spec, "demo"))
      : null;

    // Controls that must be frozen for the duration of a run: the Run and Reset
    // buttons plus the analysis's experiment inputs. Worker requests aren't
    // serialized, so toggling an experiment mid-run could let a stale response
    // land last and silently mismatch the visible control state; disabling Reset
    // closes the reset-mid-run path at the UI (the generation counter guards it
    // in state).
    function inFlightControls() {
      return [runBtn, panel.querySelector("#reset-demo"),
        ...panel.querySelectorAll(cfg.experimentControlsSelector)];
    }

    // Reference-counted freeze/restore for the controls above. Restoring the
    // PRE-run disabled state (rather than enabling everything) is what keeps an
    // analysis's own lock — cox/logistic disable the primary-exposure checkbox
    // in content.js — intact across a run.
    const controlLock = createControlLock();

    // Shared run path: the Run button always calls this, and the experiment
    // controls call it too (conditionally) so both go through one place.
    async function runDemo() {
      if (cfg.liveRender) {
        return coalescer.submit(cfg.buildDemoSpec(ctx.getSession().demoOptions));
      }
      controlLock.acquire(inFlightControls());        // no duplicate/overlapping runs
      try { await ctx.runAndShow(cfg.buildDemoSpec(ctx.getSession().demoOptions), "demo"); }
      finally { controlLock.release(); }
    }

    runBtn.addEventListener("click", runDemo);
    panel.querySelector("#reset-demo").addEventListener("click", () => {
      // Drop any spec queued behind an in-flight run BEFORE resetting: a
      // pre-reset pending spec would otherwise pass the generation check and
      // paint a stale plot under the freshly restored default controls.
      if (coalescer) coalescer.clear();
      ctx.resetDemoState();
      renderExample(panel, ctx);                    // clears result + restores default controls
    });

    // An experiment change only reruns if a demo result already exists;
    // before the first Run click it just patches the pending options.
    cfg.renderExperiments(panel, ctx, () => {
      if (ctx.getSession().results.demo) runDemo();
    });
  }
}

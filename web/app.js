// Module worker so it can `import { WebR }` from the CDN at the top level.
const worker = new Worker("worker.js", { type: "module" });
const pending = new Map();
let nextId = 1;

// Session status chip in the toolbar: idle -> busy -> ready/error.
function setStatus(state, label) {
  const chip = document.getElementById("rstatus");
  if (!chip) return;
  chip.className = "chip " + state;
  chip.textContent = label;
}

worker.onmessage = (e) => {
  const { id, result, progress, warmup, ready, stage } = e.data;
  // Warmup messages (page-load engine warm, or its progress/completion pings)
  // only ever touch the status chip — never #preview/#stats, since the user
  // may still be reading the Understand tab when this arrives. Branching on
  // `warmup` first also means `pending.get(undefined)` below is never reached
  // for these messages.
  if (warmup) {
    if (ready === true) setStatus("ready", "R: ready");
    else if (ready === false) setStatus("idle", "R: offline");
    else if (stage === "engine") setStatus("busy", "R: loading engine…");
    else if (stage === "packages") setStatus("busy", "R: loading packages…");
    return;
  }
  // Progress pings (e.g. lazy package downloads) update the UI without
  // resolving the pending request; the final message carries `result`.
  if (progress !== undefined) {
    const preview = document.getElementById("preview");
    if (preview) preview.textContent = progress;
    setStatus("busy", "R: installing packages…");
    return;
  }
  const resolve = pending.get(id);
  if (resolve) { pending.delete(id); resolve(JSON.parse(result)); }
};

worker.onerror = () => {
  const payload = {
    ok: false,
    error: "Failed to load the R runtime (check your network connection and that your browser supports WebAssembly).",
  };
  for (const resolve of pending.values()) resolve(payload);
  pending.clear();
};

// Warm the webR runtime as soon as the page loads, instead of waiting for the
// first Run click. This is a module script, so this fires once at load; the
// worker's single-flight `webRReady = webRReady || boot()` guard means a
// subsequent real Run reuses this same in-flight/settled promise rather than
// booting twice.
setStatus("busy", "R: warming up…");
worker.postMessage({ warmup: true });

export function runFigure(spec) {
  return new Promise((resolve) => {
    const id = nextId++;
    pending.set(id, resolve);
    worker.postMessage({ id, json: JSON.stringify(spec) });
  });
}

async function render(spec) {
  const preview = document.getElementById("preview");
  const stats = document.getElementById("stats");
  preview.innerHTML = "Rendering… (first run downloads R, ~30s)";
  stats.textContent = "";
  stats.classList.remove("error");
  setStatus("busy", "R: working…");
  const out = await runFigure(spec);
  if (!out.ok) {
    preview.innerHTML = "";
    stats.textContent = "Error: " + out.error;
    stats.classList.add("error");
    setStatus("error", "R: error");
    return;
  }
  preview.innerHTML = out.svg;
  stats.textContent = out.text;
  setStatus("ready", "R: ready");
}

import { renderGuidedSummary } from "./guided/summary/guided-summary.js";
import { renderGuidedKm } from "./guided/guided-analysis.js";
import { renderGuidedExplore } from "./guided/explore/guided-explore.js";
import { renderGuidedGroupCompare } from "./guided/groupcompare/guided-groupcompare.js";
import { initExportUI } from "./export-ui.js";
const forms = { summary: renderGuidedSummary, km: renderGuidedKm,
                explore: renderGuidedExplore, groupcompare: renderGuidedGroupCompare };

let currentFigure = "figure";   // export filename stem before any selection

document.querySelectorAll("[data-figure]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = btn.dataset.figure;
    currentFigure = kind;
    document.getElementById("preview").innerHTML = "";
    const stats = document.getElementById("stats");
    stats.textContent = "";
    stats.classList.remove("error");
    document.querySelectorAll("[data-figure]").forEach((b) =>
      { b.classList.toggle("active", b === btn);
        // Expose the selection to assistive tech, matching the guided
        // tabs' aria-selected standard.
        if (b === btn) b.setAttribute("aria-current", "true");
        else b.removeAttribute("aria-current"); });
    const container = document.getElementById("form");
    container.innerHTML = "";
    (forms[kind] || (() => {}))(container, render, runFigure, setStatus);
  });
});

initExportUI(() => currentFigure);

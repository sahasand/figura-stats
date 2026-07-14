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
  const { id, result, progress } = e.data;
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

import { renderForestForm } from "./forms/forest.js";
import { renderConsortForm } from "./forms/consort.js";
import { renderTable1Form } from "./forms/table1.js";
import { renderKmForm } from "./forms/km.js";
import { renderGroupCompareForm } from "./forms/groupcompare.js";
import { renderCorrelationForm } from "./forms/correlation.js";
import { renderRocForm } from "./forms/roc.js";
import { renderRegressionForm } from "./forms/regression.js";
import { renderGuidedKm } from "./guided/guided-analysis.js";
const forms = { forest: renderForestForm, consort: renderConsortForm, table1: renderTable1Form, km: renderGuidedKm, groupcompare: renderGroupCompareForm, correlation: renderCorrelationForm, roc: renderRocForm, regression: renderRegressionForm };

document.querySelectorAll("[data-figure]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = btn.dataset.figure;
    document.querySelectorAll("[data-figure]").forEach((b) =>
      b.classList.toggle("active", b === btn));
    const container = document.getElementById("form");
    container.innerHTML = "";
    (forms[kind] || (() => {}))(container, render, runFigure);
  });
});

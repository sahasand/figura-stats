// Module worker so it can `import { WebR }` from the CDN at the top level.
const worker = new Worker("worker.js", { type: "module" });
const pending = new Map();
let nextId = 1;

worker.onmessage = (e) => {
  const { id, result } = e.data;
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
  const out = await runFigure(spec);
  if (!out.ok) { preview.innerHTML = ""; stats.textContent = "Error: " + out.error; return; }
  preview.innerHTML = out.svg;
  stats.textContent = out.text;
}

import { renderForestForm } from "./forms/forest.js";
const forms = { forest: renderForestForm };

document.querySelectorAll("[data-figure]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = btn.dataset.figure;
    const container = document.getElementById("form");
    container.innerHTML = "";
    (forms[kind] || (() => {}))(container, render);
  });
});

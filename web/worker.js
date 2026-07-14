// Module worker: runs webR (R compiled to WebAssembly) off the main thread.
// Created from app.js with `new Worker("worker.js", { type: "module" })`.
import { WebR } from "https://webr.r-wasm.org/latest/webr.mjs";

let webRReady;

async function boot() {
  const webR = new WebR();
  await webR.init();
  // Install ONLY what the forest plot needs. Later tasks (4-6: KM, Table 1,
  // CONSORT) extend this list with e.g. "survival", "survminer", "gtsummary".
  await webR.installPackages(["ggplot2", "svglite", "jsonlite", "knitr"], { quiet: true });
  // Load the R sources that define render_figure() and the fig_* functions.
  // Only dispatch.R and forest.R exist today; the rest are added by later
  // tasks. Missing files 404, and the `resp.ok` guard skips them.
  for (const f of ["dispatch.R", "forest.R", "consort.R", "table1.R", "km.R", "themes.R"]) {
    const resp = await fetch(`R/${f}`);
    if (resp.ok) await webR.evalRVoid(await resp.text());
  }
  return webR;
}

self.onmessage = async (e) => {
  const { id, json } = e.data;
  try {
    webRReady = webRReady || boot();
    const webR = await webRReady;
    // Bind the JSON spec string into R's global env, then call render_figure.
    // Binding (rather than string-interpolating) avoids any R-escaping issues.
    await webR.objs.globalEnv.bind("figure_input", json);
    const shelter = await new webR.Shelter();
    try {
      // render_figure() returns a length-1 JSON character vector (class "json");
      // as.character() drops the class so toArray() yields a plain string.
      // suppressWarnings + captureConditions:false are REQUIRED: ggplot2 emits a
      // deprecation warning (geom_errorbarh) that otherwise makes webR's
      // condition handling throw "Can't convert atomic vector of length > 1".
      const res = await shelter.evalR(
        "as.character(suppressWarnings(render_figure(figure_input)))",
        { captureConditions: false, captureStreams: false }
      );
      const arr = await res.toArray();
      self.postMessage({ id, result: arr[0] });
    } finally {
      shelter.purge();
    }
  } catch (err) {
    self.postMessage({ id, result: JSON.stringify({ ok: false, error: String(err) }) });
  }
};

// Module worker: runs webR (R compiled to WebAssembly) off the main thread.
// Created from app.js with `new Worker("worker.js", { type: "module" })`.
import { WebR } from "https://webr.r-wasm.org/latest/webr.mjs";

let webRReady;

// Heavy, figure-specific packages are installed LAZILY the first time a figure
// of that type is requested — not at boot — so a Summary-statistics user never
// downloads the KM survival tree. Boot installs only the shared base below.
// See ensureExtraPackages().
const EXTRA_PACKAGES = { km: ["survival", "cowplot"] };
const installedExtras = new Set();
// Single-flight guard: figure type -> in-flight install Promise. Without this,
// two concurrent requests for the same figure type (e.g. a double-click on
// Render, which doesn't disable the button mid-render) would both see
// installedExtras empty and both call webR.installPackages(), double-downloading
// the KM package tree and racing webR's package-install state.
// Mirrors the webRReady = webRReady || boot() single-flight pattern below.
const pendingExtraInstalls = new Map();

async function boot() {
  const webR = new WebR();
  await webR.init();
  // Boot installs ONLY the packages shared by every figure. Heavy per-figure
  // dependencies (e.g. survival + cowplot for KM) are installed lazily on
  // first use via ensureExtraPackages(), keeping first load fast for everyone.
  await webR.installPackages(["ggplot2", "svglite", "jsonlite"], { quiet: true });
  // Load the R sources that define render_figure() and the fig_* functions.
  // Missing files 404, and the `resp.ok` guard skips them.
  for (const f of ["dispatch.R", "summarize.R", "km.R", "themes.R"]) {
    const resp = await fetch(`R/${f}`);
    if (resp.ok) await webR.evalRVoid(await resp.text());
  }
  return webR;
}

// Install any heavy packages a given figure type needs, once. Idempotent:
// tracks what's already installed so the download happens only on first use.
async function ensureExtraPackages(webR, figure, id) {
  const pkgs = EXTRA_PACKAGES[figure];
  if (!pkgs) return;
  const missing = pkgs.filter((p) => !installedExtras.has(p));
  if (missing.length === 0) return;

  // If an install for this figure type is already in flight, await THAT
  // promise instead of starting a second webR.installPackages() call.
  let installPromise = pendingExtraInstalls.get(figure);
  if (!installPromise) {
    self.postMessage({ id, progress: `Loading ${figure} packages (first time, this may take a minute)…` });
    installPromise = webR.installPackages(missing, { quiet: true }).then(() => {
      for (const p of missing) installedExtras.add(p);
    });
    // Clear the in-flight entry once settled (success or failure) so a failed
    // install can be retried by a later request rather than wedging forever.
    installPromise.finally(() => pendingExtraInstalls.delete(figure));
    pendingExtraInstalls.set(figure, installPromise);
  }
  await installPromise;
}

self.onmessage = async (e) => {
  const { id, json } = e.data;
  try {
    webRReady = webRReady || boot();
    const webR = await webRReady;
    // Parse the incoming spec just enough to learn the figure type, so we can
    // lazily install that figure's heavy packages before evaluating it.
    let figure;
    try { figure = JSON.parse(json).figure; } catch (_) { /* dispatch reports bad JSON */ }
    await ensureExtraPackages(webR, figure, id);
    const shelter = await new webR.Shelter();
    try {
      // Pass the JSON spec string via the evalR `env` option so it's bound
      // into an environment local to THIS evaluation, rather than a shared
      // global. onmessage is async and yields at awaits (boot, package
      // install, evalR itself), so two overlapping requests could otherwise
      // interleave bind(A) -> bind(B) -> eval(A) on a single shared global
      // and evaluate the wrong spec. Scoping per-eval makes concurrent
      // requests race-free.
      // render_figure() returns a length-1 JSON character vector (class "json");
      // as.character() drops the class so toArray() yields a plain string.
      // suppressWarnings + captureConditions:false are REQUIRED: ggplot2 emits a
      // deprecation warning (geom_errorbarh) that otherwise makes webR's
      // condition handling throw "Can't convert atomic vector of length > 1".
      const res = await shelter.evalR(
        "as.character(suppressWarnings(render_figure(figure_input)))",
        { env: { figure_input: json }, captureConditions: false, captureStreams: false }
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

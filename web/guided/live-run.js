// web/guided/live-run.js
// Live-render plumbing for builder-style analyses. A running R eval in the
// webR worker cannot be aborted, so "cancellation" is coalescing: at most one
// render in flight, and only the NEWEST waiting spec runs next — intermediate
// specs are dropped, so slow renders can never queue up.
export function createCoalescer(run) {
  let inFlight = false;
  let pending = null;                 // newest spec submitted during flight
  async function submit(spec) {
    if (inFlight) { pending = spec; return; }
    inFlight = true;
    try { await run(spec); }
    catch (_) { /* run() surfaces its own errors; keep the pipeline alive */ }
    finally {
      inFlight = false;
      if (pending !== null) { const next = pending; pending = null; submit(next); }
    }
  }
  return { submit };
}

export function debounce(fn, ms) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// web/guided/control-lock.js
// Freeze a set of controls for the duration of a run and put them back exactly
// as they were — NOT blanket-enabled. Some controls are deliberately disabled by
// an analysis's content.js (cox/logistic lock the primary-exposure checkbox so
// the model can never lose every covariate); a blanket re-enable would silently
// unlock those.
//
// Two properties the guided shell needs:
//   * restore is keyed by ELEMENT, so a re-render mid-run (new nodes, different
//     count, different order) can't map a remembered state onto the wrong node —
//     nodes acquire() never saw are simply left alone.
//   * acquire/release are reference-counted, so overlapping runs (liveRender
//     coalescing, or a rerun fired from an experiment control) unfreeze only
//     once the LAST run settles, and the restored state is the one captured
//     before the FIRST acquire — never the mid-run "everything disabled" state.
export function createControlLock() {
  let depth = 0;
  const priorDisabled = new Map();   // element -> disabled state before the freeze

  function acquire(controls) {
    depth += 1;
    for (const el of controls) {
      if (!el) continue;                              // selector matched nothing
      if (!priorDisabled.has(el)) priorDisabled.set(el, el.disabled);
      el.disabled = true;
    }
  }

  // Safe to call from a `finally`, including after a throw and including more
  // times than acquire() was called.
  function release() {
    if (depth === 0) return;
    depth -= 1;
    if (depth > 0) return;                            // another run still holds it
    for (const [el, wasDisabled] of priorDisabled) el.disabled = wasDisabled;
    priorDisabled.clear();
  }

  return { acquire, release };
}

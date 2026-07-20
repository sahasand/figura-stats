# 03 — Guided shell re-enables demo controls that content.js deliberately locked

Status: resolved
Type: task
Found: 2026-07-20, during the logistic-regression build

## Problem

`web/guided/shell.js:175-177`:

```js
const controls = inFlightControls();
controls.forEach((el) => { el.disabled = true; });
try { await ctx.runAndShow(...); }
finally { controls.forEach((el) => { el.disabled = false; }); }
```

`inFlightControls()` returns everything matching `cfg.experimentControlsSelector` (the `#demo-experiments` inputs). The `finally` block re-enables **all** of them unconditionally, with no memory of which were disabled before the run. That defeats the `cb.disabled = true` lock that cox's and logistic's `content.js` put on the primary-exposure checkbox.

Consequence: after the first demo run the user can uncheck the primary exposure, and unchecking every covariate reaches R's `stop("Select at least one covariate.")` — an error the lock existed to make unreachable. The code is byte-identical on the cox and logistic paths, so it affects both.

## Fix

Snapshot each control's `disabled` state before the run and restore that snapshot in `finally`, rather than blanket-enabling. Add an e2e assertion that the primary-exposure checkbox is still disabled after a completed demo run.

## Answer

Fixed on `fix/cox-shell-issues`. `web/guided/shell.js` now freezes the demo controls through a
reference-counted `createControlLock()` (`web/guided/control-lock.js`): `acquire()` remembers each
element's `disabled` state in a Map keyed by the element, `release()` restores that snapshot only
when the last overlapping run settles. Element-keyed restore survives a re-render mid-run (nodes
acquire never saw are left alone); ref-counting keeps two overlapping runs from unfreezing early;
`release()` stays in the `finally`, so a throw in `runAndShow` still restores.

Covered by `web/guided/control-lock.test.mjs` (registered in the `test:unit` chain) and by an e2e
assertion in `tests/e2e/logistic-guided.spec.js` that `#cov-arm` is still disabled — and
`#cov-age`/`#cov-stage`/`#run-demo` enabled — after a completed demo run.

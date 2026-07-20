// web/guided/control-lock.test.mjs
import assert from "node:assert/strict";
import { createControlLock } from "./control-lock.js";

// The lock only ever touches `.disabled`, so plain objects stand in for inputs.
const ctl = (disabled = false) => ({ disabled });

// Prior state is restored, not blanket-enabled: a control that was ALREADY
// disabled before the run (content.js locks the primary-exposure checkbox)
// must still be disabled afterwards, while the others come back usable.
{
  const locked = ctl(true), free = ctl(false), btn = ctl(false);
  const lock = createControlLock();
  lock.acquire([btn, locked, free]);
  assert.equal(locked.disabled, true);
  assert.equal(free.disabled, true);
  assert.equal(btn.disabled, true);
  lock.release();
  assert.equal(locked.disabled, true, "locked control must stay disabled");
  assert.equal(free.disabled, false);
  assert.equal(btn.disabled, false);
}

// Overlapping runs (liveRender coalescing can start a run while another settles):
// the first release must NOT unfreeze while a second run still holds the lock,
// and the eventual restore must use the state from BEFORE the first acquire.
{
  const locked = ctl(true), free = ctl(false);
  const lock = createControlLock();
  lock.acquire([locked, free]);
  lock.acquire([locked, free]);           // second, overlapping run
  lock.release();                          // first run settles
  assert.equal(free.disabled, true, "still frozen while a run is in flight");
  lock.release();                          // second run settles
  assert.equal(free.disabled, false);
  assert.equal(locked.disabled, true, "prior state, not the mid-run state");
}

// The control set can change between acquire and release (a re-render during the
// run). Restore is keyed by element, not by index, so each element gets its own
// remembered state and elements never seen by acquire are left alone.
{
  const oldLocked = ctl(true), oldFree = ctl(false);
  const newLocked = ctl(true), newFree = ctl(false);
  const lock = createControlLock();
  lock.acquire([oldLocked, oldFree]);
  lock.acquire([newLocked, newFree]);      // re-rendered controls join mid-run
  lock.release();
  lock.release();
  assert.equal(oldLocked.disabled, true);
  assert.equal(oldFree.disabled, false);
  assert.equal(newLocked.disabled, true, "re-rendered lock survives");
  assert.equal(newFree.disabled, false);
}

// An extra release (double-settle, or a release with no acquire) must not
// leave the depth negative and swallow the next run's restore.
{
  const free = ctl(false);
  const lock = createControlLock();
  lock.release();                          // stray
  lock.acquire([free]);
  assert.equal(free.disabled, true);
  lock.release();
  assert.equal(free.disabled, false);
}

// Missing controls (a selector that matched nothing) are skipped, not thrown on.
{
  const free = ctl(false);
  const lock = createControlLock();
  lock.acquire([null, undefined, free]);
  assert.equal(free.disabled, true);
  lock.release();
  assert.equal(free.disabled, false);
}

console.log("control-lock.test.mjs OK");

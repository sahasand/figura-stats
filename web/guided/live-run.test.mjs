// web/guided/live-run.test.mjs
import assert from "node:assert/strict";
import { createCoalescer, debounce } from "./live-run.js";

// Coalescer: rapid submits collapse to first + last.
{
  const ran = [];
  let release;
  const gate = () => new Promise((r) => { release = r; });
  const c = createCoalescer(async (spec) => { ran.push(spec); await gate(); });
  c.submit("a");                    // starts immediately
  c.submit("b");                    // pending
  c.submit("c");                    // overwrites b
  assert.deepEqual(ran, ["a"]);
  const r1 = release; r1();         // settle "a"
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(ran, ["a", "c"]);   // b never ran
  release();
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(ran, ["a", "c"]);
}

// Coalescer: a rejecting run must not wedge the pipeline.
{
  const ran = [];
  const c = createCoalescer(async (spec) => {
    ran.push(spec);
    if (spec === "boom") throw new Error("x");
  });
  c.submit("boom");
  await new Promise((r) => setTimeout(r, 0));
  c.submit("next");
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(ran, ["boom", "next"]);
}

// Coalescer clear(): a queued spec is dropped and never runs after release.
{
  const ran = [];
  let release;
  const gate = () => new Promise((r) => { release = r; });
  const c = createCoalescer(async (spec) => { ran.push(spec); await gate(); });
  c.submit("a");                    // starts immediately (gated in-flight)
  c.submit("b");                    // pending
  c.clear();                        // drop the pending "b"
  assert.deepEqual(ran, ["a"]);
  release();                        // settle "a"
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(ran, ["a"]);     // "b" never ran
}

// Debounce: only the last call within the window fires.
{
  const got = [];
  const d = debounce((v) => got.push(v), 20);
  d(1); d(2); d(3);
  await new Promise((r) => setTimeout(r, 60));
  d(4);
  await new Promise((r) => setTimeout(r, 60));
  assert.deepEqual(got, [3, 4]);
}
console.log("live-run.test.mjs OK");

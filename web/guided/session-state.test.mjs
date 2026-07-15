// web/guided/session-state.test.mjs
import assert from "node:assert/strict";
import { createKmSession, setStage, storeResult, getResult, setDemoOptions, resetDemo,
  getDemoGeneration, isDemoGenerationCurrent, STAGES }
  from "./session-state.js";

assert.deepEqual(STAGES, ["understand", "example", "analyze"]);
let s = createKmSession();
assert.equal(s.stage, "understand");
s = setStage(s, "example");
assert.equal(s.stage, "example");
assert.throws(() => setStage(s, "bogus"), /stage/);

s = storeResult(s, "demo", { svg: "<svg/>", text: "demo text" });
s = storeResult(s, "user", { svg: "<svg2/>", text: "user text" });
assert.equal(getResult(s, "demo").text, "demo text");     // contexts isolated
assert.equal(getResult(s, "user").text, "user text");

assert.deepEqual(s.demoOptions, { conf_int: true, landmarks: [], horizon: null });
s = setDemoOptions(s, { landmarks: [12, 24] });
assert.deepEqual(s.demoOptions.landmarks, [12, 24]);
assert.equal(s.demoOptions.conf_int, true);               // patch, not replace

// A demo run captures the generation at launch; reset bumps it so the snapshot
// goes stale, letting an in-flight demo result be recognized and discarded.
let g = createKmSession();
assert.equal(getDemoGeneration(g), 0);                    // fresh session starts at 0
const launchedGen = getDemoGeneration(g);
assert.equal(isDemoGenerationCurrent(g, launchedGen), true);   // current before any reset
g = resetDemo(g);
assert.equal(getDemoGeneration(g), 1);                    // reset bumps the generation
assert.equal(isDemoGenerationCurrent(g, launchedGen), false);  // pre-reset run now stale
assert.equal(isDemoGenerationCurrent(g, getDemoGeneration(g)), true);  // a fresh launch is current
g = resetDemo(g);
assert.equal(getDemoGeneration(g), 2);                    // each reset bumps again
assert.equal(isDemoGenerationCurrent(g, 1), false);       // still detects the older generation

s = resetDemo(s);
assert.equal(getResult(s, "demo"), null);                 // demo result cleared
assert.deepEqual(s.demoOptions, { conf_int: true, landmarks: [], horizon: null });
assert.equal(getResult(s, "user").text, "user text");     // user context untouched
assert.equal(getDemoGeneration(s), 1);                    // reset also bumps here
console.log("session-state.test.mjs OK");

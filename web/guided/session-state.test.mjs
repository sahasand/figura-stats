// web/guided/session-state.test.mjs
import assert from "node:assert/strict";
import { createKmSession, setStage, storeResult, getResult, setDemoOptions, resetDemo, STAGES }
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

s = resetDemo(s);
assert.equal(getResult(s, "demo"), null);                 // demo result cleared
assert.deepEqual(s.demoOptions, { conf_int: true, landmarks: [], horizon: null });
assert.equal(getResult(s, "user").text, "user text");     // user context untouched
console.log("session-state.test.mjs OK");

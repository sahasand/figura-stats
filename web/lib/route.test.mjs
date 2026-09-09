import assert from "node:assert/strict";
import { analysisFromHash } from "./route.js";

const KNOWN = ["summary", "km", "explore", "groupcompare", "cox", "logistic"];
assert.equal(analysisFromHash("", KNOWN), null);
assert.equal(analysisFromHash(undefined, KNOWN), null);
assert.equal(analysisFromHash("#km", KNOWN), "km");
assert.equal(analysisFromHash("#km/analyze", KNOWN), "km");
assert.equal(analysisFromHash("#km/example", KNOWN), "km");
assert.equal(analysisFromHash("#nope/analyze", KNOWN), null);
assert.equal(analysisFromHash("#km/analyze/extra", KNOWN), null);
assert.equal(analysisFromHash("#km/analyze?csv=x", KNOWN), null);   // never inputs
console.log("route.test.mjs OK");

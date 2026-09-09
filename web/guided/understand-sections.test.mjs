import assert from "node:assert/strict";
import * as km from "./km/content.js";
import * as summary from "./summary/content.js";
import * as cox from "./cox/content.js";
import * as logistic from "./logistic/content.js";
import * as groupcompare from "./groupcompare/content.js";
import * as explore from "./explore/content.js";

const MODULES = { km, summary, cox, logistic, groupcompare, explore };

for (const [name, mod] of Object.entries(MODULES)) {
  assert.ok(Array.isArray(mod.UNDERSTAND_SECTIONS), `${name}: UNDERSTAND_SECTIONS is an array`);
  assert.ok(mod.UNDERSTAND_SECTIONS.length >= 3, `${name}: at least three sections`);
  for (const s of mod.UNDERSTAND_SECTIONS) {
    assert.equal(typeof s.title, "string");
    assert.ok(s.title.trim().length > 0, `${name}: section has a title`);
    assert.equal(typeof s.html, "string");
    assert.ok(/<p|<ul/.test(s.html), `${name}: section "${s.title}" has body HTML`);
  }
  // renderUnderstand paints from the same array — one source of truth.
  const panel = {};
  mod.renderUnderstand(panel);
  for (const s of mod.UNDERSTAND_SECTIONS) {
    assert.ok(panel.innerHTML.includes(`<h3>${s.title}</h3>`),
      `${name}: renderUnderstand renders "${s.title}"`);
  }
}
console.log("understand-sections.test.mjs OK");

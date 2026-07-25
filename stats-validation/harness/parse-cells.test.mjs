import assert from "node:assert/strict";
import { parseRatioTable } from "./parse-cells.mjs";

// `text` from fig_cox / fig_logistic is TSV, then a blank line, then methods.
const text =
  "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)\n" +
  "New treatment\t1.02 (0.63–1.66, p=0.932)\t0.50 (0.30–0.83, p=0.023)\n" +
  "age (per 10 units)\t1.60 (1.30–1.97, p<0.001)\t1.69 (1.36–2.10, p<0.001)\n" +
  "\n" +
  "Univariable logistic regression (n = 320, 91 events) ...";
const out = parseRatioTable(text);
assert.equal(out.rows.length, 2);
assert.equal(out.rows[0].term, "New treatment");
assert.equal(out.rows[0].adj, "0.50 (0.30–0.83, p=0.023)");
assert.match(out.methods, /n = 320, 91 events/);

console.log("parse-cells.test.mjs ok");

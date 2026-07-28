import assert from "node:assert/strict";
import { parseRatioTable } from "./parse-cells.mjs";

// `text` from fig_cox / fig_logistic is TSV, then a blank line, then methods.
//
// Row 2 is a categorical covariate's header row — the real shape captured
// end-to-end from fig_logistic (see task-3-report.md): the covariate name
// plus reference level, with an empty unadj/adj cell pair, immediately
// followed by its first level row ("New treatment"). This is the entire
// subject of addendum point 3 and must stay covered here so a "fix" that
// special-cases header rows (or reintroduces trimming assumptions) fails
// loudly instead of only being caught by manual inspection.
//
// Note the intentional asymmetry: `term` is NOT trimmed (parse-cells.mjs
// leaves it exactly as split from the tab), while `unadj`/`adj` ARE trimmed
// and defaulted to "" when the field is missing. Don't assume fixing one
// side's whitespace handling also fixes the other.
const text =
  "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)\n" +
  "arm (reference: Standard care)\t\t\n" +
  "New treatment\t1.02 (0.63–1.66, p=0.932)\t0.50 (0.30–0.83, p=0.023)\n" +
  "age (per 10 units)\t1.60 (1.30–1.97, p<0.001)\t1.69 (1.36–2.10, p<0.001)\n" +
  "\n" +
  "Univariable logistic regression (n = 320, 91 events) ...";
const out = parseRatioTable(text);
assert.equal(out.rows.length, 3);
assert.deepEqual(out.rows[0], {
  term: "arm (reference: Standard care)",
  unadj: "",
  adj: "",
});
assert.equal(out.rows[1].term, "New treatment");
assert.equal(out.rows[1].adj, "0.50 (0.30–0.83, p=0.023)");
assert.match(out.methods, /n = 320, 91 events/);

console.log("parse-cells.test.mjs ok");

import assert from "node:assert/strict";
import { compareText, classifyColumn, runCase, nativeDigest } from "./compare-text.mjs";

// Regression pin for the review finding this file exists to close:
// `compareText` was previously unexported with no test anywhere, and the
// Playwright spec that was its only caller is excluded from CI (it needs a
// browser + network). An edit that made the comparison always report
// "identical" — e.g. comparing native against itself, or dropping the
// `a !== b` check — would have failed nothing. This module is plain Node, so
// it runs on every `make -C stats-validation test`.

const NATIVE =
  "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)\n" +
  "arm (reference: Standard care)\t\t\n" +
  "New treatment\t1.02 (0.63–1.66, p=0.932)\t0.50 (0.28–0.91, p=0.023)\n" +
  "age (per 10 units)\t1.56 (1.19–2.05, p=0.001)\t1.69 (1.26–2.26, p<0.001)\n" +
  "\n" +
  "Multivariable logistic regression (n = 320, 91 events) adjusted for arm, age. " +
  "Unadjusted odds ratios are from single-covariate models; adjusted odds ratios " +
  "are from the joint model. Overall model discrimination: apparent (in-sample) " +
  "C-statistic = 0.68.";

// ---------------------------------------------------------------------------
// Direction 1: identical text on both sides -> no drift.
{
  const { compared, differing, cellKinds, cellsWithNumbers } = compareText(NATIVE, NATIVE);
  assert.equal(differing.length, 0, "identical text must record zero drift");
  assert.ok(compared > 0, "a real comparison must compare at least one cell");
  // Every compared cell falls into exactly one of five kinds, so the kinds
  // must sum back to the total — this is the same invariant the "36 cells"
  // breakdown published in webr-tier.json depends on.
  const kindTotal =
    cellKinds.header + cellKinds.term + cellKinds.value + cellKinds.empty + cellKinds.methods;
  assert.equal(kindTotal, compared, "cell kinds must partition every compared cell");
  assert.equal(
    cellsWithNumbers,
    cellKinds.value + cellKinds.methodsWithNumber,
    "cellsWithNumbers must be exactly the numeric-bearing kinds",
  );
  // This fixture has the same shape as the real cox-adjusted case: 1 header
  // line + 3 rows (one a bare "reference:" row with two empty cells) x 3
  // columns + 3 methods sentences, 2 of them carrying a number.
  assert.equal(cellKinds.header, 1);
  assert.equal(cellKinds.term, 3);
  assert.equal(cellKinds.value, 4);
  assert.equal(cellKinds.empty, 2);
  assert.equal(cellKinds.methods, 3);
  assert.equal(cellKinds.methodsWithNumber, 2);
  assert.equal(compared, 13);
}

// ---------------------------------------------------------------------------
// Direction 2: a single-cell difference -> exactly one drift record, with the
// right term/column/native/webr.
{
  const webrText = NATIVE.replace(
    "0.50 (0.28–0.91, p=0.023)",
    "0.51 (0.28–0.91, p=0.023)",
  );
  const { differing } = compareText(NATIVE, webrText);
  assert.equal(differing.length, 1, "a single changed cell must record exactly one drift");
  assert.deepEqual(differing[0], {
    term: "New treatment",
    column: "adjusted",
    native: "0.50 (0.28–0.91, p=0.023)",
    webr: "0.51 (0.28–0.91, p=0.023)",
  });
}

// A difference in a methods-paragraph sentence is recorded the same way, by
// sentence index, not folded into the whole-paragraph fallback (that fallback
// is reserved for a SENTENCE-COUNT mismatch, not a same-count edit).
{
  const webrText = NATIVE.replace("C-statistic = 0.68.", "C-statistic = 0.67.");
  const { differing } = compareText(NATIVE, webrText);
  assert.equal(differing.length, 1);
  assert.equal(differing[0].term, "(methods paragraph)");
  assert.equal(differing[0].column, "sentence 3");
  assert.equal(differing[0].native, "Overall model discrimination: apparent (in-sample) C-statistic = 0.68.");
  assert.equal(differing[0].webr, "Overall model discrimination: apparent (in-sample) C-statistic = 0.67.");
}

// ---------------------------------------------------------------------------
// Hard preconditions still throw (comparison-not-assertion applies to VALUE
// differences only; a structural mismatch must be loud).
{
  const oneRowNative =
    "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)\n" +
    "arm\t1.00\t1.00\n" +
    "\nMethods.";
  const twoRowWebr =
    "Characteristic\tUnadjusted OR (95% CI, p)\tAdjusted OR (95% CI, p)\n" +
    "arm\t1.00\t1.00\n" +
    "age\t1.00\t1.00\n" +
    "\nMethods.";
  assert.throws(
    () => compareText(oneRowNative, twoRowWebr),
    /row count/,
    "a row-count mismatch must throw, not be recorded as a drift cell",
  );
}
{
  assert.throws(
    () => compareText("Characteristic\tA\tB\n\nMethods.", "Characteristic\tA\tB\n\nMethods."),
    /parsed no table rows/,
    "a table with zero rows must throw",
  );
}

// ---------------------------------------------------------------------------
// classifyColumn: the partition compareText relies on.
{
  assert.equal(classifyColumn("line", "Characteristic\tA\tB"), "header");
  assert.equal(classifyColumn("characteristic", "II"), "term"); // numeric-looking, still a label
  assert.equal(classifyColumn("unadjusted", "1.02 (0.63–1.66, p=0.932)"), "value");
  assert.equal(classifyColumn("unadjusted", ""), "empty");
  assert.equal(classifyColumn("adjusted", ""), "empty");
  assert.equal(classifyColumn("sentence 1", "n = 320, 91 events."), "methods");
  assert.equal(classifyColumn("whole paragraph", "..."), "methods");
}

// ---------------------------------------------------------------------------
// runCase: the structural-drift fix. A precondition failure must not destroy
// the whole run's evidence — it must come back as an honest aborted record
// the caller can still publish.
{
  const ok = await runCase("case-a", async () => ({ id: "case-a", identical: true }));
  assert.deepEqual(ok, { id: "case-a", identical: true });
}
{
  const bad = await runCase("case-b", async () => {
    throw new Error("webR table row count (1) differs from native R (2)");
  });
  assert.equal(bad.id, "case-b");
  assert.equal(bad.aborted, true);
  assert.match(bad.reason, /row count/);
}
{
  // A thrown non-Error value must still produce a readable reason string.
  const bad = await runCase("case-c", async () => {
    // eslint-disable-next-line no-throw-literal
    throw "plain string failure";
  });
  assert.equal(bad.aborted, true);
  assert.equal(bad.reason, "plain string failure");
}

// ---------------------------------------------------------------------------
// nativeDigest: order-independent, content-sensitive. This is the baseline
// binding fix — a later `make all` that changes native output must change
// this digest, or staleness is invisible.
{
  const a = [
    { id: "logistic-confounding", text: "foo" },
    { id: "cox-adjusted", text: "bar" },
  ];
  const b = [
    { id: "cox-adjusted", text: "bar" },
    { id: "logistic-confounding", text: "foo" },
  ];
  assert.equal(nativeDigest(a), nativeDigest(b), "digest must not depend on array order");

  const changed = [
    { id: "logistic-confounding", text: "foo-CHANGED" },
    { id: "cox-adjusted", text: "bar" },
  ];
  assert.notEqual(
    nativeDigest(a),
    nativeDigest(changed),
    "a changed native text must change the digest (this is the staleness signal)",
  );
}

console.log("compare-text.test.mjs ok");

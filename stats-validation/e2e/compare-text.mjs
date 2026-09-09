// stats-validation/e2e/compare-text.mjs
//
// The webR tier's cell-by-cell comparator, split out of webr-parity.spec.js so
// it can be pinned by a plain node test that `make -C stats-validation test`
// runs — stats-validation/e2e/compare-text.test.mjs — even though the tier
// itself (the Playwright spec) stays excluded from CI. Before this split,
// `compareText` was a private function inside the spec with no test anywhere:
// an edit that made the comparison always report "identical" (e.g. comparing
// a string against itself, or dropping the `a !== b` check) would have failed
// nothing, because the only thing that ever exercised it was a hand-run
// browser gate. This module has no Playwright dependency — it is plain Node
// plus parseRatioTable — specifically so it CAN be required from a plain node
// test that runs on every `make test`.
//
// Importing parseRatioTable (rather than re-rolling a parser here) is the
// point, not an implementation detail: the webR tier is the consumer
// harness/parse-cells.mjs's `parseRatioTable` was kept for (see that file's
// header comment), and a second parser in this module could disagree with the
// real one and call that disagreement drift.
//
// THREE COMPARISON SHAPES, ONE VOCABULARY. The roster is not all ratio tables.
// `parseRatioTable` understands the three-column cox/logistic TSV and nothing
// else, so the other five cases would have to be either skipped or compared by
// a shape that fits what they actually display:
//
//   ratio_table  cox, logistic     -> compareText   (parseRatioTable, unchanged)
//   table1       summary           -> compareTable  (general N-column TSV)
//   km_summary   km                -> compareProse  (no table at all: one
//   gc_summary   group comparison  -> compareProse   displayed sentence block)
//
// `compareDisplay(kind, ...)` dispatches on the case's own `display.kind`, so
// the shape is read off case.json rather than guessed from the text. All three
// produce the SAME result object — `{compared, differing, cellKinds,
// cellsWithNumbers}` over the same five cell kinds — because the honesty
// property the evidence file depends on is that `cells_compared` counts
// comparable UNITS and `cell_kinds` explains what those units are. A prose
// case whose display is one sentence contributes one comparable unit, not
// thirty-six imaginary ones.
//
// The general parser used by compareTable is applied IDENTICALLY to both sides,
// so unlike a second ratio parser it cannot manufacture drift — a quirk in it
// cancels out. It normalises nothing INSIDE THE TABLE (no cell trimming, no
// padding a short row), which is stricter than parseRatioTable's value-cell
// trim; it does trim the methods paragraph, exactly as parseRatioTable does.
// See the note on `parseDisplayTable`.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { parseRatioTable } from "../harness/parse-cells.mjs";

// Column labels the evidence file uses for the two value columns and the
// term/characteristic column. `classifyColumn` below has to agree with this
// exactly, so it lives in one place.
export const COLUMN_LABEL = { term: "characteristic", unadj: "unadjusted", adj: "adjusted" };

function assertPrecondition(condition, message) {
  if (!condition) {
    throw new Error(`webR tier precondition failed: ${message}`);
  }
}

// RESIDUAL BLIND SPOTS — what this comparator provably CANNOT see.
//
// This file's comments are the tier's audit trail, so the honest limits live
// here rather than only in a review thread. None of these is a bug being
// deferred: each is a normalisation applied IDENTICALLY to both sides, so it
// can never manufacture drift. What it can do is hide a difference, and that
// is worth naming precisely, because the published claim is "every displayed
// string was compared".
//
//   1. Trailing whitespace after the FINAL sentence of a prose line.
//      `sentences()` splits on /(?<=\.)\s+/ and drops whitespace-only
//      fragments, so "Alpha. Beta." and "Alpha. Beta.   " both yield
//      ["Alpha.", "Beta."] and compare identical. (A final sentence NOT ending
//      in "." keeps its trailing whitespace and is visible; leading whitespace
//      at the START of a line is also visible, since nothing splits there.)
//   2. Whitespace BETWEEN sentences, for the same reason: the separator is
//      consumed by the split, so "Alpha. Beta." and "Alpha.   Beta." compare
//      identical.
//   3. A whitespace-only line inside a TSV block. Both parsers filter
//      `l.trim() !== ""` before pairing rows, so a blank line one runtime
//      printed and the other did not is removed rather than reported — and
//      because it is removed on the side that has it, it does not even show up
//      as a row-count precondition failure.
//   4. Leading/trailing whitespace on a ratio table's `unadj`/`adj` cell.
//      `parseRatioTable` trims those two columns (documented in
//      parse-cells.mjs and in the classifyColumn note below); the `term`
//      column is left untrimmed, so the asymmetry runs one way only.
//   5. A FOURTH tab-separated field on a ratio-table data row. UNDOCUMENTED
//      until now and pre-existing: `parseRatioTable` destructures
//      `const [term, unadj, adj] = l.split("\t")`, so anything past the third
//      field is discarded on both sides and an extra column webR emitted (or
//      dropped) is invisible. The general `parseDisplayTable` used by
//      `compareTable` does NOT have this hole — it keeps every field and
//      asserts the per-row cell count — so it is specific to the three
//      ratio_table cases.
//
// NEGATIVE CONTROL, AND ITS PROVENANCE. The direction that matters — would a
// real drift actually be CAUGHT end to end — was exercised on 2026-07-28 by
// the reviewer of the 8-case widening, read-only, by running the committed
// comparator against MUTATED COPIES of the native display artifacts (the
// artifacts in results/ were never touched). All three comparison paths
// detected the injected drift: ratio_table (compareText), table1
// (compareTable) and prose (compareProse), and the scorecard's DRIFT and
// ABORTED renderers were confirmed to render the result. Recorded here
// because the review report that established it is gitignored, and evidence
// of a negative control is worth exactly as much as its provenance.

// What KIND of displayed string a compared cell is. Only "value" cells and
// "methods" cells that contain a digit can ever show wasm-vs-native drift —
// "header"/"term" cells are static labels the app prints verbatim (a term
// like "II" or "III" is a row LABEL, not a measured quantity, even though it
// looks numeric), and "empty" cells are the blank unadj/adj slots a
// categorical covariate's own header row carries by construction. This
// classification is what lets webr-tier.json say "compared every displayed
// string, N of them carrying a number" instead of implying every compared
// cell is a number that could have drifted — see the "36 cells" finding this
// module exists to make honest.
//
// NOTE on parseRatioTable's trim asymmetry, because this comparator relies on
// it directly: parseRatioTable trims `unadj`/`adj` but leaves `term`
// UNTRIMMED (see parse-cells.mjs's header comment). That means a stray
// leading/trailing space on a `term` cell would show up here as a genuine
// WEBR_DRIFT finding on a "term" cell, while the equivalent whitespace on an
// `unadj`/`adj` cell would be silently normalized away before this comparator
// ever sees it. Both behaviors are inherited, not decided here — this
// comment exists so a future reader of a `term`-column drift (or the absence
// of one on a value column) does not mistake it for a bug in this file. The
// full list of what this comparator cannot see is in RESIDUAL BLIND SPOTS
// above, of which that trim is item 4.
export function classifyColumn(column, nativeValue) {
  if (column === "line") return "header";
  if (column === "characteristic") return "term";
  if (column === "unadjusted" || column === "adjusted") {
    return nativeValue === "" ? "empty" : "value";
  }
  return "methods"; // "sentence N" or "whole paragraph"
}

// Sentence-split the methods paragraph so a difference is readable instead of
// forcing the reader to diff two paragraphs by eye.
export function sentences(paragraph) {
  return paragraph.split(/(?<=\.)\s+/).filter((s) => s.trim() !== "");
}

// The citation sentence every fig_* appends (R/script.R `.citation_sentence`)
// carries one constant number — the year — that cannot drift between
// runtimes. It stays a compared "methods" cell (the webR gate must still
// prove both sides print it identically) but is never counted as
// number-bearing; the Python comparator strips it for the same reason
// (compare.py `strip_citation`).
export const CITATION_SENTENCE_RE =
  /^Analyses were performed with Figura \([^()\n]*\), which runs R(?: with the [^.\n]+ packages?)? in the browser\.$/;
export function isCitationSentence(s) { return CITATION_SENTENCE_RE.test(String(s).trim()); }

// The one accumulator every comparison shape below writes through, so the five
// cell kinds partition every compared cell no matter which shape produced it —
// the invariant webr-tier.json's published breakdown rests on. The KIND is
// passed in explicitly rather than derived from the column label: only the
// ratio shape has fixed column names, and inferring "value" from a label like
// "Control (N=60)" would be guessing.
function collector() {
  const differing = [];
  const cellKinds = { header: 0, term: 0, value: 0, empty: 0, methods: 0, methodsWithNumber: 0 };
  let compared = 0;
  return {
    cell(term, column, kind, a, b) {
      compared += 1;
      cellKinds[kind] += 1;
      if (kind === "methods" && !isCitationSentence(a) && /\d/.test(a)) cellKinds.methodsWithNumber += 1;
      if (a !== b) differing.push({ term, column, native: a, webr: b });
    },
    result() {
      return {
        compared,
        differing,
        cellKinds,
        cellsWithNumbers: cellKinds.value + cellKinds.methodsWithNumber,
      };
    },
  };
}

// Sentence-by-sentence comparison of one paragraph, shared by all three shapes.
// A SENTENCE-COUNT mismatch means a diagnostic fired on one runtime and not the
// other; aligning by index would misattribute every later sentence, so the whole
// paragraph is recorded as one difference instead.
function compareParagraph(cells, term, nativePara, webrPara) {
  const natS = sentences(nativePara);
  const webS = sentences(webrPara);
  // `sentences` drops whitespace-only fragments, so a line that is blank (or
  // only whitespace) on BOTH sides would otherwise contribute zero comparable
  // units — and a whitespace-only difference between the two would then be
  // invisible rather than reported. Compare the raw line as one unit instead:
  // "both runtimes printed nothing here" is itself a fact worth counting once.
  if (natS.length === 0 && webS.length === 0) {
    cells.cell(term, "line", "methods", nativePara, webrPara);
    return;
  }
  if (natS.length !== webS.length) {
    cells.cell(term, "whole paragraph", "methods", nativePara, webrPara);
    return;
  }
  for (let i = 0; i < natS.length; i++) {
    cells.cell(term, `sentence ${i + 1}`, "methods", natS[i], webS[i]);
  }
}

// The webR tier's comparison, not assertion: differences are RECORDED, not
// thrown. Only the hard preconditions (each side parsed at least one row, the
// row counts agree) throw — a harness failure must be loud and distinguishable
// from drift, per the plan's Step 3 rule.
export function compareText(native, webr) {
  const nat = parseRatioTable(native);
  const web = parseRatioTable(webr);

  assertPrecondition(nat.rows.length > 0, "native artifact parsed no table rows");
  assertPrecondition(web.rows.length > 0, "webR output parsed no table rows");
  assertPrecondition(
    web.rows.length === nat.rows.length,
    `webR table row count (${web.rows.length}) differs from native R (${nat.rows.length})`,
  );

  const cells = collector();
  const cell = (term, column, a, b) =>
    cells.cell(term, column, classifyColumn(column, a), a, b);

  // The TSV's first line is the static column-header row. parseRatioTable
  // deliberately drops it (it holds labels, not values) but it is still one
  // line of output the runtime produced, so it is compared as a single cell
  // rather than left unchecked — a `split("\n")[0]`, not a second parser.
  cell("(header row)", "line", native.split("\n")[0], webr.split("\n")[0]);

  for (let i = 0; i < nat.rows.length; i++) {
    for (const key of ["term", "unadj", "adj"]) {
      cell(nat.rows[i].term, COLUMN_LABEL[key], nat.rows[i][key], web.rows[i][key]);
    }
  }

  compareParagraph(cells, "(methods paragraph)", nat.methods, web.methods);
  return cells.result();
}

// A general "TSV table, blank line, methods paragraph" parse for the display
// kinds parseRatioTable cannot read — today `table1`, whose column count is the
// number of groups plus two and therefore varies per case.
//
// IT NORMALISES NO TABLE CELL. parseRatioTable trims its two value columns (and
// defaults a missing field to ""); this trims nothing and pads nothing inside
// the table, so a whitespace-only difference between the runtimes is reported
// as the difference it is rather than silently absorbed. A short row is
// therefore a structural precondition failure below, not a row quietly padded
// to width.
//
// The one thing it DOES normalise is the methods paragraph, which is `.trim()`ed
// on the way out — exactly as parseRatioTable trims its own, so the two shapes
// agree. Whitespace around the whole paragraph is therefore invisible to both;
// "normalises nothing at all" is the claim this comment used to make, and it
// was wrong by that one call. See RESIDUAL BLIND SPOTS at the top of the file.
export function parseDisplayTable(text) {
  const [tsv, ...rest] = String(text).split("\n\n");
  const lines = tsv.split("\n").filter((l) => l.trim() !== "");
  return {
    header: lines.length ? lines[0] : "",
    columns: lines.length ? lines[0].split("\t") : [],
    rows: lines.slice(1).map((l) => l.split("\t")),
    methods: rest.join("\n\n").trim(),
  };
}

// `table1`: an N-column TSV (Characteristic, one column per group, Missing)
// plus a methods paragraph. Same vocabulary as compareText — column 0 is the
// row label ("term"), every other cell is a "value" unless native prints it
// blank, in which case it is an "empty" placeholder (a categorical variable's
// own header row carries blank group cells, exactly as a ratio table's
// reference row does).
export function compareTable(native, webr) {
  const nat = parseDisplayTable(native);
  const web = parseDisplayTable(webr);

  assertPrecondition(nat.rows.length > 0, "native artifact parsed no table rows");
  assertPrecondition(web.rows.length > 0, "webR output parsed no table rows");
  assertPrecondition(
    web.rows.length === nat.rows.length,
    `webR table row count (${web.rows.length}) differs from native R (${nat.rows.length})`,
  );
  assertPrecondition(
    web.columns.length === nat.columns.length,
    `webR table column count (${web.columns.length}) differs from native R ` +
    `(${nat.columns.length})`,
  );

  const cells = collector();
  cells.cell("(header row)", "line", "header", nat.header, web.header);

  for (let i = 0; i < nat.rows.length; i++) {
    const natRow = nat.rows[i];
    const webRow = web.rows[i];
    assertPrecondition(
      natRow.length === webRow.length,
      `row ${i + 1} ("${natRow[0]}"): webR emitted ${webRow.length} cells, ` +
      `native R emitted ${natRow.length}`,
    );
    for (let j = 0; j < natRow.length; j++) {
      // The column label is the header cell at this index, so a difference
      // reads "Control (N=60)" rather than "column 2".
      const column = j === 0 ? COLUMN_LABEL.term : (nat.columns[j] ?? `column ${j + 1}`);
      const kind = j === 0 ? "term" : (natRow[j] === "" ? "empty" : "value");
      cells.cell(natRow[0], column, kind, natRow[j], webRow[j]);
    }
  }

  compareParagraph(cells, "(methods paragraph)", nat.methods, web.methods);
  return cells.result();
}

// `km_summary` and `gc_summary`: no table at all. The whole display is the
// copy-pasteable methods/results sentence block, so the comparable units are
// its lines and, within a line, its sentences — "compare the displayed text,
// cell-wise where it is tabular and line-wise otherwise". Every unit here is a
// "methods" cell, and the ones carrying a digit are the ones that could drift.
//
// A LINE-COUNT mismatch is structural (one runtime printed a paragraph the
// other did not) and is a precondition failure, exactly like a row-count
// mismatch in the tabular shapes.
export function compareProse(native, webr) {
  const natLines = String(native).split("\n");
  const webLines = String(webr).split("\n");

  assertPrecondition(
    String(native).trim() !== "", "native artifact displayed no text");
  assertPrecondition(
    String(webr).trim() !== "", "webR output displayed no text");
  assertPrecondition(
    webLines.length === natLines.length,
    `webR output line count (${webLines.length}) differs from native R ` +
    `(${natLines.length})`,
  );

  const cells = collector();
  const multiline = natLines.length > 1;
  for (let i = 0; i < natLines.length; i++) {
    compareParagraph(
      cells,
      multiline ? `(displayed text, line ${i + 1})` : "(displayed text)",
      natLines[i],
      webLines[i],
    );
  }
  return cells.result();
}

// The comparison shape for each display kind a case can declare. Read off
// case.json's own `display.kind` rather than sniffed from the text, so a case
// can never be compared through a shape it was not registered for — and an
// unregistered kind is a loud failure, never a silent skip.
export const COMPARATORS = {
  ratio_table: compareText,
  // linear's coefficient table is the SAME three-column TSV shape: the header
  // wording differs ("Adjusted β (95% CI, p)") and the cells read "-1.23
  // (-2.10 to -0.36, p=0.006)", but `parseRatioTable` is column-agnostic and
  // compares each cell as an opaque string, so " to " inside a cell needs no
  // special case.
  coef_table: compareText,
  table1: compareTable,
  km_summary: compareProse,
  gc_summary: compareProse,
};

export function compareDisplay(kind, native, webr) {
  const compare = COMPARATORS[kind];
  assertPrecondition(
    typeof compare === "function",
    `no comparison shape registered for display kind "${kind}" — the webR ` +
    `tier must not fall back to a shape the case did not declare`);
  return compare(native, webr);
}

// Runs one case's driver + comparison, converting a thrown precondition (or
// any other) failure into an honest "aborted" record instead of losing the
// whole run's evidence. Fix for "structural drift publishes nothing": before
// this, a thrown precondition (e.g. a row-count mismatch — the single most
// alarming class of drift, since it means the two runtimes did not even agree
// on the SHAPE of the output) aborted the whole spec before webr-tier.json was
// ever written, so it rendered on the scorecard identically to "never run".
// `fn` must resolve to the published case object (already carrying `id`) on
// success; on failure this returns `{id, aborted: true, reason}` instead, and
// the caller is still expected to fail the run loudly after writing the file
// (see webr-parity.spec.js) — this function only prevents the failure from
// destroying the evidence, it does not swallow it.
export async function runCase(id, fn) {
  try {
    return await fn();
  } catch (err) {
    return { id, aborted: true, reason: err && err.message ? err.message : String(err) };
  }
}

// CODE-POINT ORDER, NOT LOCALE ORDER, and the choice is load-bearing.
// build_scorecard.py recomputes these digests with Python's `sorted()`, which
// orders by code point. `String.prototype.localeCompare` orders by ICU collation
// instead: punctuation is weighted below letters, case is a tertiary weight, and
// the two disagree on real strings — `"summary-table1".localeCompare(
// "summary_table1")` is +1 where the code-point comparison is -1, and the same
// for `"Logistic-dirty"` vs `"logistic-dirty"`. A disagreement means the two
// implementations hash the same inputs in different orders, so the scorecard
// would render a PERMANENT false staleness note for evidence that is perfectly
// current — and the note's only value is that it is believed. `<` on the raw
// string is the same ordering Python's `sorted()` uses (both compare unsigned
// code units; every id here is ASCII, so UTF-16-vs-code-point is moot), and
// compare-text.test.mjs pins the agreement on an adversarial pair.
function byCodePoint(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

// sha256 over the native `text` strings a run compared against, so a later
// `make all` that changes native output (a different display artifact under
// results/<id>.figura.json) makes previously-published webR evidence visibly
// stale instead of silently continuing to claim parity with numbers that no
// longer exist. `cases` is an array of `{id, text}`; sorted by id first so the
// digest does not depend on iteration order.
export function nativeDigest(cases) {
  const hash = createHash("sha256");
  for (const { id, text } of [...cases].sort((a, b) => byCodePoint(a.id, b.id))) {
    hash.update(id, "utf8");
    hash.update(" ", "utf8");
    hash.update(text, "utf8");
    hash.update(" ", "utf8");
  }
  return hash.digest("hex");
}

// THE OTHER HALF OF STALENESS. `nativeDigest` catches the native R numbers
// moving underneath published webR evidence. It cannot catch the opposite and
// equally real case: a change to `web/` that moves what the BROWSER computes or
// displays while native R output stays put. That gap was previously carried only
// by a docstring; this digest closes it.
//
// WHAT IS DIGESTED, and why it is a GLOB rather than a hand-written list. The
// tier drives the shipped single-page app: `web/index.html` loads `web/app.js`,
// whose form registry statically imports every guided analysis, which in turn
// import the shared `web/lib/` and `web/guided/` modules. The static import
// closure from index.html is therefore very nearly "every .js file under web/",
// so enumerating it by hand would buy no precision and would silently go stale
// the first time someone adds a module — a false PARITY claim, the worst
// direction to fail in. So the rule is mechanical and needs no maintenance:
//
//   include  web/index.html, web/styles.css, and every *.js under web/
//   exclude  *.test.mjs        (never shipped; index.html loads no .mjs)
//            web/R/, web/webr/ (gitignored build copies — R sources are already
//                               covered by nativeDigest, which digests the
//                               native output those same sources produce)
//            fonts, preview.png, CNAME (bytes that cannot change the DOM text
//                               this tier reads out of #stats)
//
// styles.css IS included: CSS can alter textContent through generated content,
// so "obviously cosmetic" is not a judgement this digest is entitled to make.
//
// The cost, stated plainly: this over-triggers. A pure styling change flags webR
// staleness even though no number moved. That is the safe direction — the note
// says "re-run the gate", the gate is hand-run before a release anyway, and it
// clears itself on the next run — and it is strictly better than the previous
// live-HEAD note, which fired on EVERY commit including the one that published
// the scorecard, and so could never be cleared at all.
export function webDigest(webDir) {
  const files = [];
  const walk = (rel) => {
    const entries = readdirSync(webDir + (rel ? "/" + rel : ""), {
      withFileTypes: true,
    });
    for (const entry of entries) {
      const path = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        if (path === "R" || path === "webr") continue;
        walk(path);
      } else if (isWebSource(path)) {
        files.push(path);
      }
    }
  };
  walk("");
  files.sort(byCodePoint);
  const hash = createHash("sha256");
  for (const path of files) {
    hash.update(path, "utf8");
    hash.update("\0", "utf8");
    // Bytes, not text: a source file's encoding is not this digest's business,
    // and hashing a decoded string would silently normalise it.
    hash.update(readFileSync(webDir + "/" + path));
    hash.update("\0", "utf8");
  }
  return { digest: hash.digest("hex"), files };
}

// One rule, exported so the Python recomputation in build_scorecard.py can be
// checked against it rather than reimplemented on trust.
export function isWebSource(relPath) {
  if (relPath.startsWith("R/") || relPath.startsWith("webr/")) return false;
  if (relPath.endsWith(".test.mjs")) return false;
  return relPath.endsWith(".js") || relPath === "index.html"
    || relPath === "styles.css";
}

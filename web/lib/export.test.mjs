import assert from "node:assert";
import { svgDimensions, combineSvgs, exportFilename } from "./export.js";

// svgDimensions: svglite emits pt (1pt = 4/3 px)
const svgPt = `<svg xmlns="http://www.w3.org/2000/svg" width="504.00pt" height="252.00pt" viewBox="0 0 504.00 252.00"><rect/></svg>`;
assert.deepEqual(svgDimensions(svgPt), { width: 672, height: 336 });

// bare numbers are px; viewBox is the fallback when width/height absent
assert.deepEqual(svgDimensions(`<svg width="100" height="50"></svg>`), { width: 100, height: 50 });
assert.deepEqual(svgDimensions(`<svg viewBox="0 0 300 150"></svg>`), { width: 300, height: 150 });
assert.throws(() => svgDimensions(`<svg></svg>`), /readable dimensions/i);

// combineSvgs: single panel passes through verbatim
const p1 = { svg: svgPt, width: 672, height: 336 };
assert.equal(combineSvgs([p1]), svgPt);

// multi-panel: max width, summed height, second panel offset by first's height
const p2 = { svg: `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50"></svg>`, width: 100, height: 50 };
const combined = combineSvgs([p1, p2]);
assert.match(combined, /^<svg xmlns="http:\/\/www\.w3\.org\/2000\/svg" width="672" height="386">/);
assert.match(combined, /y="0" width="672" height="336"/);
assert.match(combined, /y="336" width="100" height="50"/);
assert.doesNotMatch(combined, /width="504\.00pt"/, "pt attrs replaced by px layout values");
assert.match(combined, /viewBox="0 0 504\.00 252\.00"/, "inner viewBox preserved so content scales");

// exportFilename — journal-conventional names
assert.equal(exportFilename("summary", "png", { dpi: 600 }), "summary-figure-600dpi.png");
assert.equal(exportFilename("summary", "png", { dpi: 300, panel: 2 }), "summary-panel-2-300dpi.png");
assert.equal(exportFilename("km", "svg", {}), "km-figure.svg");
assert.equal(exportFilename("km", "svg", { panel: 1 }), "km-panel-1.svg");
assert.equal(exportFilename("km", "tsv", {}), "km-output.tsv");

console.log("ok - export core (dimensions, stitching, filenames)");

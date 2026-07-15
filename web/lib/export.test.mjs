import assert from "node:assert";
import { svgDimensions, combineSvgs, exportFilename, crc32, setPngDpi } from "./export.js";

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

// ---- PNG pHYs stamping --------------------------------------------------
// Build a minimal-but-valid PNG in-test: signature + IHDR + IDAT + IEND.
const SIG = Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
function chunk(type, data) {
  const body = Uint8Array.from([...type].map((c) => c.charCodeAt(0)).concat([...data]));
  const out = new Uint8Array(8 + data.length + 4);
  const dv = new DataView(out.buffer);
  dv.setUint32(0, data.length);
  out.set(body, 4);
  dv.setUint32(8 + data.length, crc32(body));
  return out;
}
function concatBytes(arrays) {
  const total = arrays.reduce((n, a) => n + a.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const a of arrays) { out.set(a, off); off += a.length; }
  return out;
}
function chunkTypes(png) {
  const types = [];
  for (let pos = 8; pos < png.length;) {
    const len = new DataView(png.buffer, png.byteOffset + pos).getUint32(0);
    types.push(String.fromCharCode(...png.subarray(pos + 4, pos + 8)));
    pos += 12 + len;
  }
  return types;
}
function physPpm(png) {
  for (let pos = 8; pos < png.length;) {
    const dv = new DataView(png.buffer, png.byteOffset + pos);
    const len = dv.getUint32(0);
    const type = String.fromCharCode(...png.subarray(pos + 4, pos + 8));
    if (type === "pHYs") {
      const body = png.subarray(pos + 4, pos + 8 + len);
      assert.equal(dv.getUint32(8 + len), crc32(body), "pHYs CRC must be valid");
      assert.equal(png[pos + 16], 1, "unit byte must be metre");
      return dv.getUint32(8);
    }
    pos += 12 + len;
  }
  return null;
}

// crc32 reference value (IEND chunk body "IEND" -> 0xAE426082)
assert.equal(crc32(Uint8Array.from([0x49, 0x45, 0x4e, 0x44])), 0xae426082);

const minimalPng = concatBytes([SIG, chunk("IHDR", new Uint8Array(13)), chunk("IDAT", Uint8Array.from([0])), chunk("IEND", new Uint8Array(0))]);

// 600 dpi -> 23622 pixels per metre, pHYs placed before IDAT
const stamped = setPngDpi(minimalPng, 600);
assert.deepEqual(chunkTypes(stamped), ["IHDR", "pHYs", "IDAT", "IEND"]);
assert.equal(physPpm(stamped), 23622);

// restamping replaces, never duplicates; 300 dpi -> 11811 ppm
const restamped = setPngDpi(stamped, 300);
assert.deepEqual(chunkTypes(restamped), ["IHDR", "pHYs", "IDAT", "IEND"]);
assert.equal(physPpm(restamped), 11811);

// non-PNG input and PNG without IDAT both throw readable errors
assert.throws(() => setPngDpi(new Uint8Array([1, 2, 3]), 600), /not a png/i);
assert.throws(() => setPngDpi(concatBytes([SIG, chunk("IHDR", new Uint8Array(13)), chunk("IEND", new Uint8Array(0))]), 600), /idat/i);

console.log("ok - export pHYs stamping (journal dpi metadata)");

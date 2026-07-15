# Journal-Grade Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every analysis a download path **designed for journal submission**: PNG at 300/600/1200 dpi with the DPI genuinely stamped into the file's `pHYs` chunk (so journal submission checkers read the true resolution, not 72 dpi), SVG as the vector master, and copy/`.tsv` for tables and methods text.

**Architecture:** Pure client-side. A new `web/lib/export.js` holds the engine (SVG dimension parsing, multi-panel stitching, canvas rasterization, PNG byte surgery); a new `web/export-ui.js` wires two static pane-header toolbars, reading the DOM at click time so plain-form and guided analyses are covered identically with zero changes to R, `worker.js`, or the guided shell. All output is Blob object URLs — nothing leaves the browser.

**Tech Stack:** Vanilla ES modules, Canvas API, hand-rolled PNG chunk manipulation (no libraries), plain-Node unit tests, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-07-15-export-figures-design.md` — read its "Why (research findings)" section: journals require 300–600+ dpi rasters (line art 600–1200), reject JPEG and SVG submissions, and read unstamped canvas PNGs as 72 dpi. **The entire feature is journal-submission-first; every UX and format decision traces to that.**

## Global Constraints

- **This is a journal-submission feature and the UI must say so**: figure toolbar prefixed `Journal-ready download:`; DPI options labeled exactly `300 dpi`, `600 dpi · journal default`, `1200 dpi · line art`; tooltips state the PNG is stamped with the selected DPI to meet journal figure requirements.
- **No data egress**: Blob object URLs only, revoked after use; no new network calls; no CDN/font links; no vendored libraries.
- Default DPI is **600** (journal line-art guidance); `pHYs` pixels-per-metre = `Math.round(dpi * 39.3701)`, unit byte = 1 (metre), CRC-32 correct, chunk placed before the first `IDAT`, replacing any existing `pHYs`.
- Filenames exactly: `<figure-key>-figure-<dpi>dpi.png`, `<figure-key>-figure.svg`, `<figure-key>-panel-<n>-<dpi>dpi.png`, `<figure-key>-panel-<n>.svg`, `<figure-key>-output.tsv`.
- Multi-panel: default download is ONE vertically stitched file; per-panel row only when the Figure pane holds ≥2 `<svg>`.
- Tables: copy + `.tsv` only — never table-as-image (journals re-typeset tables from text).
- Chrome styling via existing CSS custom properties only (`--line-soft`, `--ink`, `--slate`, `--radius-ctl`, …); do not add new hex colors for chrome.
- svglite emits dimensions in `pt`: 1 pt = 4/3 px.
- Canvas guard: reject with a readable message when a scaled dimension exceeds `maxDim` (default 16000 px) — never a silent blank PNG. Paint a white background first (journals expect white; canvas default is transparent).
- JS unit tests are plain Node scripts (`node:assert`, `console.log("ok - …")`), registered in `package.json`'s `test:unit`. E2E needs `rm -rf web/R && cp -R R web/R` first. R suite (`Rscript -e 'devtools::test()'`, WARN 0 gate) must stay green though no R files change.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## File Structure

| File | Responsibility |
|---|---|
| `web/lib/export.js` (create) | Engine: `svgDimensions`, `combineSvgs`, `exportFilename`, `crc32`, `setPngDpi` (pure); `collectSvgPanels`, `svgToPngBlob`, `downloadBlob` (browser-facing) |
| `web/lib/export.test.mjs` (create) | Node unit tests for all pure functions incl. PNG byte surgery |
| `web/export-ui.js` (create) | Toolbar wiring: MutationObserver enable/disable, per-panel row, click handlers, aria-live feedback |
| `web/index.html` (modify) | Pane-header toolbars (Figure + Console) with journal-framed copy |
| `web/styles.css` (modify) | `.pane-head`, `.export-toolbar`, `.export-feedback`, `#export-panels` rules (tokens only) |
| `web/app.js` (modify) | Track `currentFigure` from nav clicks; call `initExportUI` |
| `package.json` (modify) | Add `export.test.mjs` to `test:unit` |
| `tests/e2e/export.spec.js` (create) | Download-event assertions: filename, PNG magic, 600-dpi pHYs, stitched SVG, `.tsv`, copy, disabled states |

---

### Task 1: Export engine — pure core (`svgDimensions`, `combineSvgs`, `exportFilename`)

**Files:**
- Create: `web/lib/export.js`
- Create: `web/lib/export.test.mjs`
- Modify: `package.json` (test:unit script)

**Interfaces:**
- Consumes: nothing.
- Produces (Tasks 2–4 rely on these exact signatures):
  - `svgDimensions(svg: string) -> {width, height}` in px (pt×4/3; viewBox fallback; throws `Error("SVG has no readable dimensions.")` otherwise)
  - `combineSvgs(panels: [{svg, width, height}]) -> string` (single panel returns its svg verbatim; multi wraps as nested `<svg y=…>`)
  - `exportFilename(figureKey: string, kind: "png"|"svg"|"tsv", {dpi?, panel?}) -> string`

- [ ] **Step 1: Write the failing tests**

Create `web/lib/export.test.mjs`:

```js
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
assert.equal(exportFilename("roc", "tsv", {}), "roc-output.tsv");

console.log("ok - export core (dimensions, stitching, filenames)");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node web/lib/export.test.mjs`
Expected: FAIL — `Cannot find module '…/web/lib/export.js'`

- [ ] **Step 3: Implement the pure core**

Create `web/lib/export.js`:

```js
// web/lib/export.js
// Journal-grade export of rendered output. Journals require raster figures
// at 300-600+ dpi (line art 600-1200), reject JPEG and SVG submissions, and
// read a PNG with no resolution metadata as 72 dpi regardless of its pixel
// count — so the PNG path here stamps the true DPI into the file's pHYs
// chunk (setPngDpi). Everything is client-side Blob work: no data leaves
// the browser.

// Pixel dimensions of an <svg> string. svglite emits pt (1pt = 4/3 px);
// bare numbers are px; viewBox is the fallback.
export function svgDimensions(svg) {
  const attr = (name) => {
    const m = svg.match(new RegExp(`<svg[^>]*\\s${name}="([0-9.]+)(pt|px)?"`));
    if (!m) return null;
    return m[2] === "pt" ? parseFloat(m[1]) * (4 / 3) : parseFloat(m[1]);
  };
  let width = attr("width");
  let height = attr("height");
  if (width == null || height == null) {
    const vb = svg.match(/<svg[^>]*\sviewBox="([^"]+)"/);
    const parts = vb ? vb[1].trim().split(/\s+/).map(Number) : [];
    if (parts.length === 4) {
      width = width ?? parts[2];
      height = height ?? parts[3];
    }
  }
  if (!(width > 0) || !(height > 0)) throw new Error("SVG has no readable dimensions.");
  return { width, height };
}

// Stack panels vertically into one <svg> (journals usually want one file per
// figure; the per-panel buttons cover the exceptions). Each panel becomes a
// nested <svg y=…> whose original width/height attrs (often pt) are replaced
// by the px layout values; its viewBox still scales the content correctly.
export function combineSvgs(panels) {
  if (panels.length === 1) return panels[0].svg;
  const width = Math.max(...panels.map((p) => p.width));
  const height = panels.reduce((sum, p) => sum + p.height, 0);
  let y = 0;
  const children = panels.map((p) => {
    const positioned = p.svg.replace(/<svg([^>]*)>/, (_, attrs) => {
      const cleaned = attrs.replace(/\s(?:x|y|width|height)="[^"]*"/g, "");
      return `<svg${cleaned} y="${y}" width="${p.width}" height="${p.height}">`;
    });
    y += p.height;
    return positioned;
  });
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
    children.join("") + `</svg>`;
}

// Journal-conventional filenames: summary-figure-600dpi.png, km-panel-2.svg,
// roc-output.tsv.
export function exportFilename(figureKey, kind, { dpi, panel } = {}) {
  const base = panel
    ? `${figureKey}-panel-${panel}`
    : `${figureKey}-${kind === "tsv" ? "output" : "figure"}`;
  if (kind === "png") return `${base}-${dpi}dpi.png`;
  if (kind === "svg") return `${base}.svg`;
  return `${base}.tsv`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node web/lib/export.test.mjs`
Expected: `ok - export core (dimensions, stitching, filenames)`

- [ ] **Step 5: Register the test file**

In `package.json`, append to the `test:unit` script (one string, before the closing quote): `&& node web/lib/export.test.mjs`

Run: `npm run test:unit`
Expected: all files pass, ending with the new `ok - export core…` line.

- [ ] **Step 6: Commit**

```bash
git add web/lib/export.js web/lib/export.test.mjs package.json
git commit -m "feat(export): journal-export core — svg dimensions, panel stitching, filenames

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: PNG DPI stamping (`crc32`, `setPngDpi`)

**Files:**
- Modify: `web/lib/export.js`
- Test: `web/lib/export.test.mjs`

**Interfaces:**
- Consumes: nothing from Task 1 (independent byte-level code in the same module).
- Produces: `crc32(bytes: Uint8Array) -> number` (unsigned); `setPngDpi(buffer: ArrayBuffer|Uint8Array, dpi: number) -> Uint8Array` — validates PNG signature, strips any existing `pHYs`, inserts a correct one before the first `IDAT`. **This is the heart of the journal story**: without it every canvas PNG reads as 72 dpi in submission checkers.

- [ ] **Step 1: Write the failing tests**

Append to `web/lib/export.test.mjs` (extend the import line to `import { svgDimensions, combineSvgs, exportFilename, crc32, setPngDpi } from "./export.js";`):

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node web/lib/export.test.mjs`
Expected: FAIL — `does not provide an export named 'crc32'`

- [ ] **Step 3: Implement**

Append to `web/lib/export.js`:

```js
// ---- PNG DPI stamping -------------------------------------------------
// A canvas-produced PNG has no resolution metadata, so journal submission
// checkers read it as 72 dpi no matter how many pixels it has. Inserting a
// pHYs chunk (pixels per metre) before the first IDAT makes the file read
// as the true 300/600/1200 dpi the author selected.

const PNG_SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

export function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) {
    crc ^= bytes[i];
    for (let k = 0; k < 8; k++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

export function setPngDpi(buffer, dpi) {
  const src = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  if (src.length < 8 || !PNG_SIGNATURE.every((b, i) => src[i] === b))
    throw new Error("Not a PNG file.");
  const ppm = Math.round(dpi * 39.3701);
  const phys = new Uint8Array(4 + 4 + 9 + 4);          // len + type + data + crc
  const dv = new DataView(phys.buffer);
  dv.setUint32(0, 9);
  phys.set([0x70, 0x48, 0x59, 0x73], 4);               // "pHYs"
  dv.setUint32(8, ppm);
  dv.setUint32(12, ppm);
  phys[16] = 1;                                        // unit: metre
  dv.setUint32(17, crc32(phys.subarray(4, 17)));
  const parts = [src.subarray(0, 8)];
  let pos = 8, inserted = false;
  while (pos + 12 <= src.length) {
    const len = new DataView(src.buffer, src.byteOffset + pos).getUint32(0);
    const type = String.fromCharCode(...src.subarray(pos + 4, pos + 8));
    const end = pos + 12 + len;
    if (type === "IDAT" && !inserted) { parts.push(phys); inserted = true; }
    if (type !== "pHYs") parts.push(src.subarray(pos, end));
    pos = end;
  }
  if (!inserted) throw new Error("PNG has no IDAT chunk.");
  const total = parts.reduce((n, a) => n + a.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const a of parts) { out.set(a, off); off += a.length; }
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node web/lib/export.test.mjs` then `npm run test:unit`
Expected: `ok - export pHYs stamping (journal dpi metadata)`; all unit files green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/export.js web/lib/export.test.mjs
git commit -m "feat(export): stamp true DPI into PNG pHYs chunk for journal submission checkers

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Toolbars, browser glue, and wiring

**Files:**
- Modify: `web/lib/export.js` (browser-facing helpers)
- Create: `web/export-ui.js`
- Modify: `web/index.html:52-61`
- Modify: `web/styles.css` (append)
- Modify: `web/app.js`

**Interfaces:**
- Consumes: everything Tasks 1–2 exported.
- Produces: DOM ids the e2e (Task 4) asserts: `#export-png`, `#export-svg`, `#export-dpi`, `#export-copy`, `#export-tsv`, `#export-panels`, `#export-feedback-figure`, `#export-feedback-console`; `initExportUI(getFigureKey: () => string)` from `web/export-ui.js`. No unit-test RED/GREEN here (browser APIs — Node can't run them); Task 4's e2e is the failing-first coverage for this task. Run `npm run test:unit` to guard imports.

- [ ] **Step 1: Add browser-facing helpers to `web/lib/export.js`**

Append:

```js
// ---- Browser-facing helpers (covered by e2e, not Node unit tests) ------

export function collectSvgPanels(previewEl) {
  return [...previewEl.querySelectorAll("svg")].map((el) => {
    const svg = el.outerHTML;
    const { width, height } = svgDimensions(svg);
    return { svg, width, height };
  });
}

// Rasterize an SVG string to a DPI-stamped PNG Blob at journal resolution.
// White background first (journals expect white; canvas defaults to
// transparent). Rejects with a readable message when the canvas would
// exceed maxDim — never a silent blank file.
export function svgToPngBlob(svg, { dpi = 600, maxDim = 16000 } = {}) {
  const { width, height } = svgDimensions(svg);
  const scale = dpi / 96;
  const w = Math.round(width * scale);
  const h = Math.round(height * scale);
  if (w > maxDim || h > maxDim)
    return Promise.reject(new Error(
      `Too large at ${dpi} dpi (${w}×${h}px) — choose a lower DPI.`));
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      canvas.toBlob((blob) => {
        if (!blob) { reject(new Error("PNG encoding failed.")); return; }
        blob.arrayBuffer().then((buf) =>
          resolve(new Blob([setPngDpi(buf, dpi)], { type: "image/png" })));
      }, "image/png");
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not rasterize the figure."));
    };
    img.src = url;
  });
}

export function downloadBlob(blob, filename, doc = globalThis.document) {
  const a = doc.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  doc.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
```

- [ ] **Step 2: Add the toolbars to `web/index.html`**

Replace the output pane (lines 52–61) with:

```html
    <section class="pane output-pane" aria-label="Output">
      <div class="output-figure">
        <div class="pane-head">
          <div class="pane-title">Figure</div>
          <div class="export-toolbar" role="group" aria-label="Download figure for journal submission">
            <span class="export-hint">Journal-ready download:</span>
            <select id="export-dpi" aria-label="PNG resolution — journals require 300 dpi or more">
              <option value="300">300 dpi</option>
              <option value="600" selected>600 dpi · journal default</option>
              <option value="1200">1200 dpi · line art</option>
            </select>
            <button id="export-png" disabled
              title="High-resolution PNG stamped with the selected DPI — meets journal figure requirements">PNG</button>
            <button id="export-svg" disabled
              title="Vector master for Illustrator/Inkscape or journals accepting vector">SVG</button>
            <span id="export-feedback-figure" class="export-feedback" role="status" aria-live="polite"></span>
          </div>
        </div>
        <div id="export-panels" hidden></div>
        <div id="preview"><div class="empty"><p>The rendered figure or table appears here.</p></div></div>
      </div>
      <div class="output-console">
        <div class="pane-head">
          <div class="pane-title">Console</div>
          <div class="export-toolbar" role="group" aria-label="Export table and methods text">
            <button id="export-copy" disabled
              title="Copy the table and methods text — journals want tables as editable text, paste into Word or Excel">Copy</button>
            <button id="export-tsv" disabled
              title="Download the table and methods text as .tsv">.tsv</button>
            <span id="export-feedback-console" class="export-feedback" role="status" aria-live="polite"></span>
          </div>
        </div>
        <pre id="stats"></pre>
      </div>
    </section>
```

- [ ] **Step 3: Style with existing tokens — append to `web/styles.css`**

```css
/* Journal-export toolbars: pane titles gain a right-aligned control strip. */
.pane-head { display: flex; align-items: center; justify-content: space-between; gap: .5rem; flex-wrap: wrap; }
.export-toolbar { display: flex; align-items: center; gap: .4rem; }
.export-toolbar .export-hint {
  font-size: .68rem; color: var(--slate); text-transform: uppercase; letter-spacing: .05em;
}
.export-toolbar button, .export-toolbar select {
  font: inherit; font-size: .78rem; color: var(--ink); background: var(--paper, #fff);
  border: 1px solid var(--line-soft); border-radius: var(--radius-ctl);
  padding: .15rem .55rem; cursor: pointer;
}
.export-toolbar button:disabled { opacity: .45; cursor: default; }
.export-feedback { font-size: .74rem; color: var(--slate); }
#export-panels {
  display: flex; align-items: center; gap: .4rem; padding: .3rem 0;
  font-size: .74rem; color: var(--slate);
}
#export-panels button {
  font: inherit; font-size: .7rem; color: var(--ink); background: var(--paper, #fff);
  border: 1px solid var(--line-soft); border-radius: var(--radius-ctl);
  padding: .05rem .45rem; cursor: pointer;
}
```

(`var(--paper, #fff)` uses the token if the file defines one; the fallback keeps chrome white otherwise — check the token block at the top of `styles.css` and drop the fallback if `--paper` exists.)

- [ ] **Step 4: Create `web/export-ui.js`**

```js
// web/export-ui.js
// Wires the journal-export toolbars. Handlers read the DOM at click time, so
// plain-form analyses and both guided shells are covered identically — no
// changes to R, worker.js, or the shell factory. A MutationObserver keeps the
// buttons' disabled state (and the per-panel row) in sync with the panes.
import { collectSvgPanels, combineSvgs, svgToPngBlob, downloadBlob, exportFilename }
  from "./lib/export.js";

export function initExportUI(getFigureKey) {
  const preview = document.getElementById("preview");
  const stats = document.getElementById("stats");
  const pngBtn = document.getElementById("export-png");
  const svgBtn = document.getElementById("export-svg");
  const dpiSel = document.getElementById("export-dpi");
  const copyBtn = document.getElementById("export-copy");
  const tsvBtn = document.getElementById("export-tsv");
  const panelsRow = document.getElementById("export-panels");
  const figNote = document.getElementById("export-feedback-figure");
  const conNote = document.getElementById("export-feedback-console");

  const dpi = () => parseInt(dpiSel.value, 10);
  function note(el, msg) {
    el.textContent = msg;
    setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, 4000);
  }

  function exportPng(svgString, panel) {
    svgToPngBlob(svgString, { dpi: dpi() })
      .then((blob) => downloadBlob(blob,
        exportFilename(getFigureKey(), "png", { dpi: dpi(), panel })))
      .catch((err) => note(figNote, err.message));
  }
  function exportSvg(svgString, panel) {
    downloadBlob(new Blob([svgString], { type: "image/svg+xml" }),
      exportFilename(getFigureKey(), "svg", { panel }));
  }

  pngBtn.addEventListener("click", () => exportPng(combineSvgs(collectSvgPanels(preview))));
  svgBtn.addEventListener("click", () => exportSvg(combineSvgs(collectSvgPanels(preview))));
  tsvBtn.addEventListener("click", () => downloadBlob(
    new Blob([stats.textContent], { type: "text/tab-separated-values" }),
    exportFilename(getFigureKey(), "tsv", {})));
  copyBtn.addEventListener("click", () => navigator.clipboard.writeText(stats.textContent)
    .then(() => note(conNote, "Copied"))
    .catch(() => note(conNote, "Copy failed — select the text manually")));

  // Per-panel row: only when the figure holds >=2 svgs (journals often want
  // one file per figure — these buttons export each panel separately).
  function buildPanelRow(n) {
    panelsRow.hidden = n < 2;
    panelsRow.innerHTML = "";
    if (n < 2) return;
    for (let i = 1; i <= n; i++) {
      const label = document.createElement("span");
      label.textContent = `panel ${i}`;
      const png = document.createElement("button");
      png.textContent = "PNG";
      png.addEventListener("click", () => exportPng(collectSvgPanels(preview)[i - 1].svg, i));
      const svg = document.createElement("button");
      svg.textContent = "SVG";
      svg.addEventListener("click", () => exportSvg(collectSvgPanels(preview)[i - 1].svg, i));
      panelsRow.append(label, png, svg);
    }
  }

  function sync() {
    const n = preview.querySelectorAll("svg").length;
    pngBtn.disabled = svgBtn.disabled = n === 0;
    const hasText = stats.textContent.trim() !== "" && !stats.classList.contains("error");
    copyBtn.disabled = tsvBtn.disabled = !hasText;
    buildPanelRow(n);
  }

  const obs = new MutationObserver(sync);
  obs.observe(preview, { childList: true, subtree: true });
  obs.observe(stats, { childList: true, characterData: true, subtree: true, attributes: true });
  sync();
}
```

- [ ] **Step 5: Wire into `web/app.js`**

Add with the other imports (bottom import block):

```js
import { initExportUI } from "./export-ui.js";
```

Add above the `document.querySelectorAll("[data-figure]")` block:

```js
let currentFigure = "figure";   // export filename stem before any selection
```

Inside the nav click handler, first line of the callback body after `const kind = btn.dataset.figure;`:

```js
    currentFigure = kind;
```

After the whole `document.querySelectorAll("[data-figure]").forEach(...)` block, add:

```js
initExportUI(() => currentFigure);
```

- [ ] **Step 6: Verify imports and serve-smoke**

Run: `npm run test:unit`
Expected: all green (guards the new module graph).

Run: `rm -rf web/R && cp -R R web/R && npm run serve` in the background, open http://localhost:8321 — confirm toolbars render disabled in both pane headers, with the "Journal-ready download:" hint. Stop the server. (Playwright coverage lands in Task 4; this is a visual sanity pass.)

- [ ] **Step 7: Commit**

```bash
git add web/lib/export.js web/export-ui.js web/index.html web/styles.css web/app.js
git commit -m "feat(export): journal-ready download toolbars — DPI-stamped PNG, SVG, copy/tsv

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: E2E coverage + full verification

**Files:**
- Create: `tests/e2e/export.spec.js`

**Interfaces:**
- Consumes: the DOM ids from Task 3 and filenames from Task 1; the guided Summary example flow (`#summary/example`, "Run Example Analysis", two-svg figure).
- Produces: nothing further — closing gate.

- [ ] **Step 1: Write the e2e spec**

Create `tests/e2e/export.spec.js`:

```js
// tests/e2e/export.spec.js — the download feature exists FOR JOURNAL
// SUBMISSION: the PNG must carry a real pHYs DPI stamp (journals read
// unstamped canvas PNGs as 72 dpi), filenames must be submission-friendly,
// and tables must export as editable text.
const { test, expect } = require("@playwright/test");

test.use({ permissions: ["clipboard-read", "clipboard-write"] });

function pngDpi(buf) {
  for (let pos = 8; pos + 12 <= buf.length;) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString("ascii", pos + 4, pos + 8);
    if (type === "pHYs") return Math.round(buf.readUInt32BE(pos + 8) / 39.3701);
    pos += 12 + len;
  }
  return null;
}

async function downloadBuffer(page, trigger) {
  const [download] = await Promise.all([page.waitForEvent("download"), trigger()]);
  const chunks = [];
  for await (const c of await download.createReadStream()) chunks.push(c);
  return { name: download.suggestedFilename(), buf: Buffer.concat(chunks) };
}

test("export toolbars start disabled with journal-ready framing", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Journal-ready download:")).toBeVisible();
  await expect(page.locator("#export-dpi")).toHaveValue("600");   // journal default
  for (const id of ["#export-png", "#export-svg", "#export-copy", "#export-tsv"])
    await expect(page.locator(id)).toBeDisabled();
  await expect(page.locator("#export-panels")).toBeHidden();
});

test("journal-grade exports: 600dpi-stamped PNG, stitched SVG, per-panel row, tsv, copy", async ({ page }) => {
  test.setTimeout(360000);
  await page.goto("/#summary/example");
  await page.getByRole("button", { name: /summary statistics/i }).click();
  await page.getByRole("button", { name: "Run Example Analysis" }).click();
  await expect(page.locator("#preview table")).toBeVisible({ timeout: 330000 });
  await expect(page.locator("#export-png")).toBeEnabled();

  // PNG: journal filename, PNG magic bytes, true 600 dpi in the pHYs chunk.
  const png = await downloadBuffer(page, () => page.locator("#export-png").click());
  expect(png.name).toBe("summary-figure-600dpi.png");
  expect(png.buf.subarray(0, 8)).toEqual(
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  expect(pngDpi(png.buf)).toBe(600);

  // DPI picker changes both the raster and the filename.
  await page.locator("#export-dpi").selectOption("300");
  const png300 = await downloadBuffer(page, () => page.locator("#export-png").click());
  expect(png300.name).toBe("summary-figure-300dpi.png");
  expect(pngDpi(png300.buf)).toBe(300);
  expect(png300.buf.length).toBeLessThan(png.buf.length);

  // SVG: one stitched file wrapping both panels.
  const svg = await downloadBuffer(page, () => page.locator("#export-svg").click());
  expect(svg.name).toBe("summary-figure.svg");
  const svgText = svg.buf.toString("utf8");
  expect(svgText.startsWith("<svg")).toBe(true);
  expect((svgText.match(/<svg/g) || []).length).toBeGreaterThanOrEqual(3); // wrapper + 2 panels

  // Per-panel row: visible with 2 panels, panel-numbered filename.
  await expect(page.locator("#export-panels")).toBeVisible();
  const panel2 = await downloadBuffer(page,
    () => page.locator("#export-panels button", { hasText: "SVG" }).nth(1).click());
  expect(panel2.name).toBe("summary-panel-2.svg");

  // Table + methods text: .tsv download and clipboard copy (editable text —
  // what journals require for tables).
  const tsv = await downloadBuffer(page, () => page.locator("#export-tsv").click());
  expect(tsv.name).toBe("summary-output.tsv");
  expect(tsv.buf.toString("utf8")).toMatch(/^Characteristic\t/);
  await page.locator("#export-copy").click();
  await expect(page.locator("#export-feedback-console")).toHaveText("Copied");
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toMatch(/^Characteristic\t/);
});
```

- [ ] **Step 2: Run the new spec to verify it exercises real behavior**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/export.spec.js`
Expected: 2 passed. (If the pHYs assertion fails, the stamping pipeline — not the test — is wrong: debug `svgToPngBlob`.)

- [ ] **Step 3: Full verification**

```bash
Rscript -e 'devtools::test()'
npm run test:unit
rm -rf web/R && cp -R R web/R && npm run test:e2e
```

Expected: R `[ FAIL 0 | WARN 0 | … ]` (no R changes — confirms nothing regressed); unit all ok; Playwright: all tests passing (18 existing + 2 new).

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/export.spec.js
git commit -m "test(export): e2e — DPI-stamped PNG, stitched SVG, per-panel, tsv, copy

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

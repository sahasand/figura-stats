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
// km-output.tsv.
export function exportFilename(figureKey, kind, { dpi, panel } = {}) {
  const base = panel
    ? `${figureKey}-panel-${panel}`
    : `${figureKey}-${kind === "tsv" ? "output" : "figure"}`;
  if (kind === "png") return `${base}-${dpi}dpi.png`;
  if (kind === "svg") return `${base}.svg`;
  return `${base}.tsv`;
}

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

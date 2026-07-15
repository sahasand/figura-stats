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

// web/export-ui.js
// Wires the journal-export toolbars. Handlers read the DOM at click time, so
// plain-form analyses and both guided shells are covered identically — no
// changes to R, worker.js, or the shell factory. A MutationObserver keeps the
// buttons' disabled state (and the per-panel row) in sync with the panes.
import { collectSvgPanels, combineSvgs, svgToPngBlob, downloadBlob, exportFilename,
  textExportDescriptor, collectTables, richTableHtml } from "./lib/export.js";

export function initExportUI(getFigureKey) {
  const preview = document.getElementById("preview");
  const stats = document.getElementById("stats");
  const pngBtn = document.getElementById("export-png");
  const svgBtn = document.getElementById("export-svg");
  const dpiSel = document.getElementById("export-dpi");
  const copyBtn = document.getElementById("export-copy");
  const tsvBtn = document.getElementById("export-tsv");
  const rBtn = document.getElementById("export-r");
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
  tsvBtn.addEventListener("click", () => {
    const d = textExportDescriptor(getFigureKey());
    downloadBlob(new Blob([stats.textContent], { type: d.mime }),
      exportFilename(getFigureKey(), d.ext, {}));
  });
  // Copy carries two flavours when a table is on screen: the tab-separated
  // text as before, plus an HTML table Word pastes as a real table. Browsers
  // without ClipboardItem, and a refused rich write, fall back to plain text.
  function copyOutput() {
    const text = stats.textContent;
    const plain = () => navigator.clipboard.writeText(text).then(() => "Copied");
    const tables = collectTables(preview);
    if (!tables.length || typeof ClipboardItem === "undefined" || !navigator.clipboard.write)
      return plain();
    const item = new ClipboardItem({
      "text/plain": new Blob([text], { type: "text/plain" }),
      "text/html": new Blob([richTableHtml(tables, text)], { type: "text/html" }),
    });
    return navigator.clipboard.write([item]).then(() => "Copied as a table for Word", plain);
  }
  copyBtn.addEventListener("click", () => copyOutput()
    .then((msg) => note(conNote, msg))
    .catch(() => note(conNote, "Copy failed — select the text manually")));
  rBtn.addEventListener("click", () => {
    const code = stats.dataset.rCode || "";
    if (!code) return;
    downloadBlob(new Blob([code], { type: "text/plain" }),
      exportFilename(getFigureKey(), "Rscript", {}));
  });

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
      png.setAttribute("aria-label", `Download panel ${i} as PNG`);
      png.addEventListener("click", () => {
        const p = collectSvgPanels(preview)[i - 1];
        if (p) exportPng(p.svg, i);
      });
      const svg = document.createElement("button");
      svg.textContent = "SVG";
      svg.setAttribute("aria-label", `Download panel ${i} as SVG`);
      svg.addEventListener("click", () => {
        const p = collectSvgPanels(preview)[i - 1];
        if (p) exportSvg(p.svg, i);
      });
      panelsRow.append(label, png, svg);
    }
  }

  function sync() {
    const d = textExportDescriptor(getFigureKey());
    tsvBtn.textContent = d.buttonLabel;
    tsvBtn.title = d.downloadTitle;
    copyBtn.textContent = d.copyLabel;
    copyBtn.title = d.copyTitle;
    const n = preview.querySelectorAll("svg").length;
    pngBtn.disabled = svgBtn.disabled = n === 0;
    const hasText = stats.textContent.trim() !== "" && !stats.classList.contains("error");
    copyBtn.disabled = tsvBtn.disabled = !hasText;
    // Explore's text pane IS the script (descriptor ext "R") — hide the extra
    // button there; elsewhere enable it only when the painted result carried code.
    rBtn.hidden = d.ext === "R";
    rBtn.disabled = !stats.dataset.rCode;
    buildPanelRow(n);
  }

  const obs = new MutationObserver(sync);
  obs.observe(preview, { childList: true, subtree: true });
  obs.observe(stats, { childList: true, characterData: true, subtree: true, attributes: true });
  sync();

  // app.js registers its nav handlers before initExportUI runs, so by the time
  // this listener fires getFigureKey() already reflects the new selection.
  document.querySelectorAll("[data-figure]").forEach((b) =>
    b.addEventListener("click", sync));
}

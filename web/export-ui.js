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

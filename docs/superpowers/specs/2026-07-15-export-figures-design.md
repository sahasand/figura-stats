# Export / download of analysis output — figures and tables

**Date:** 2026-07-15
**Status:** Approved
**Scope:** Shell-level feature. After the 2026-07-15 trim, the app's two analyses are the guided Kaplan-Meier (`km`) and Summary statistics (`summary`) — the export toolbars serve both, with no per-analysis gating needed. New `web/lib/export.js` + `web/export-ui.js`, toolbar markup in `web/index.html`, wiring in `web/app.js`, styles in `web/styles.css`. No changes to R, `web/worker.js`, or the guided-shell factory.

## Why (research findings)

Today the app has **no way to download any output** — the figure SVG and the TSV/methods
text are display-only. Research into the actual submission workflow shows:

- Medical/science journals require **TIFF at 300–600 dpi** or **vector EPS/PDF** for
  figures; line art (our plots) ideally 600–1200 dpi. JPEG is rejected outright (JCI);
  **SVG is essentially never accepted** as a submission format (PLOS: TIFF/EPS; Wiley:
  PDF→TIFF; JGP: 300 dpi minimum, 600 recommended for line art + text).
- The conversion step is a documented pain point: free standalone tools exist solely to
  convert figures to "300/600/1000 DPI PNG/TIFF, exactly what journals require"
  (sci-draw.com/convert, scholarbits SVG-to-TIFF — the latter advertising "in your
  browser, no upload", i.e. our privacy posture).
- A canvas-produced PNG carries **no resolution metadata**; submission checkers read it
  as 72 dpi regardless of pixel count. Stamping the PNG `pHYs` chunk with the true DPI
  is required for the export to pass journal checks.
- Journals want **tables as editable text** (they re-typeset); table-as-image is
  rejected. Our existing TSV text output is already the right artifact.

## Decisions

1. **Formats (v1):** PNG at a user-picked DPI (300 / **600 default** / 1200), SVG
   (lossless master), and copy/download of the TSV+methods text. No TIFF (revisit if
   users hit TIFF-only journals), no PDF (would require vendoring a library — CDN links
   are forbidden).
2. **Multi-panel figures** (Summary statistics renders up to three stacked sibling
   SVGs): the default download is **one vertically stitched file**; a compact per-panel
   download row appears only when the pane holds more than one `<svg>`.
3. **Table-output analyses** (Summary statistics, Regression): copy + `.tsv` download
   only — no table-as-image. Accompanying plots still export as PNG/SVG.
4. **Architecture:** pure client-side JS (approach A). No R round-trip, no libraries,
   no egress: Blob object URLs only, revoked after the click.

## UX

Two small toolbars, styled exclusively with existing CSS tokens:

- **Figure pane header** (`web/index.html`, next to the "Figure" pane title):
  `Download: [PNG] [dpi ▾] [SVG]`. The DPI `<select>` offers 300 / 600 / 1200,
  default 600. Buttons are `disabled` until `#preview` holds at least one `<svg>`;
  a `MutationObserver` on `#preview` toggles them. When >1 panel is present, a
  per-panel row (`panel 1 [png] [svg] · panel 2 …`) renders beneath the figure
  toolbar; it is absent for single-panel figures.
- **Console pane header**: `[Copy] [.tsv]`. Copy places the **full text output**
  (TSV including header row + methods sentence) on the clipboard and shows brief
  inline feedback ("Copied") — no dialogs. `.tsv` downloads the same text. Both
  disabled while `#stats` is empty or showing an error.

**Filenames:** `<figure-key>-figure-<dpi>dpi.png`, `<figure-key>-figure.svg`,
`<figure-key>-panel-<n>-<dpi>dpi.png`, `<figure-key>-panel-<n>.svg`,
`<figure-key>-output.tsv`, where `<figure-key>` is the active analysis key from the
nav state (`summary` or `km`).

**Journal framing is explicit in the UI copy** — this feature exists for journal
submission and the interface says so: the figure toolbar is prefixed
"Journal-ready download:", the DPI options are labeled `300 dpi`,
`600 dpi · journal default`, `1200 dpi · line art`, and the button tooltips state that
the PNG is stamped with the selected DPI to meet journal figure requirements.

**Accessibility:** every control is a real `<button>`/`<select>` with a visible label
or `aria-label`; the disabled state is the native `disabled` attribute; the "Copied"
feedback is announced via an `aria-live="polite"` region.

## Export engine — `web/lib/export.js`

Pure, unit-testable functions plus thin DOM-facing collectors:

- `collectSvgPanels(previewEl)` → `[{svg: <string>, width: <px>, height: <px>}, …]`
  — serializes each `<svg>` child (via `outerHTML`) and parses dimensions from
  `width`/`height` attributes (handling `pt` units from svglite: 1pt = 4/3 px) with
  `viewBox` as fallback.
- `combineSvgs(panels)` → single `<svg>` string wrapping the panels as nested
  `<svg y="…">` children; width = max panel width, height = sum of heights.
- `svgToPngBlob(svgString, {dpi, maxDim})` → renders the SVG through a Blob-URL
  `Image` onto a canvas scaled by `dpi / 96`, exports via `toBlob("image/png")`,
  then passes through `setPngDpi`. If either scaled dimension would exceed `maxDim`
  (default 16000 px), it **rejects with a readable error** — the caller shows the
  message in the copy-feedback region; never a silent blank PNG. White background
  is painted first (canvas default is transparent; journals expect white).
- `setPngDpi(arrayBuffer, dpi)` → returns a new buffer with a `pHYs` chunk
  (pixels-per-metre = `round(dpi × 39.3701)`, unit = metre, correct CRC-32)
  inserted before the first `IDAT` chunk (replacing an existing `pHYs` if present).
  Pure byte manipulation — this is what makes the PNG read as 300/600/1200 dpi in
  journal checkers instead of 72.
- `download(blob, filename)` — anchor + object URL, revoked after click.
- `copyText(text)` — `navigator.clipboard.writeText` with a `.catch` that surfaces
  a readable failure message (clipboard can be denied); returns a promise the caller
  uses to show "Copied".

## Integration — `web/index.html` + `web/app.js`

- Toolbar markup is **static HTML** in the two pane headers (like the rest of the
  chrome), hidden behind `disabled` states rather than conditional rendering.
- `app.js` wires the buttons once at boot. Handlers read the DOM **at click time**
  (`collectSvgPanels(document.getElementById("preview"))`,
  `document.getElementById("stats").textContent`), so exports work identically for
  plain-form analyses and both guided shells with zero changes to `worker.js`, R
  sources, or `createGuidedShell`. The per-panel row is (re)built by the same
  `MutationObserver` that toggles the buttons.
- The figure key for filenames comes from `app.js`'s existing selected-figure state.
- Error text (canvas too large, clipboard denied) appears in the aria-live feedback
  region next to the toolbar — consistent with the app's no-dialog style.

## Testing

- **Unit (Node, `web/lib/export.test.mjs`):** `setPngDpi` against a tiny hand-built
  valid PNG fixture (assert chunk order, pixels-per-metre bytes, CRC, idempotent
  replace); `combineSvgs` geometry (max-width/summed-height, y offsets, pt→px
  handling); filename builder. Pure functions only — no canvas in Node.
- **E2E (Playwright, extend existing specs):** after a real render — PNG download
  event yields the expected filename, non-empty body, PNG magic bytes, and a `pHYs`
  chunk encoding 600 dpi; SVG download starts with `<svg`; `.tsv` download contains
  the TSV header row; per-panel row appears for Summary with plots on and NOT for a
  single-panel figure; buttons disabled before first render and after an error
  result; copy button (clipboard permission granted) round-trips the console text.

## Risks / notes

- **Fonts:** SVGs rasterized inside an `<img>` cannot load external resources; text
  renders with system fonts resolved by family name. Figure fonts are standard
  sans-serif families, so output is acceptable; verify visually in manual QA.
- **Canvas size limits:** browsers cap canvas dimensions (~16k px). 1200 dpi × wide
  multi-panel figures can exceed it — hence `maxDim` + readable error, never a
  silent blank file.
- **No egress invariant:** all exports are Blob object URLs; nothing leaves the
  browser. No new network calls of any kind.
- TIFF and vector PDF are explicit **non-goals** for v1; the spec's research section
  records why they matter so a future phase can weigh them.

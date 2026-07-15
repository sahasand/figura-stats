# Summary statistics enhancements — rename, richer distribution plots, upload guidance

**Date:** 2026-07-15
**Status:** Approved
**Scope:** The guided Summary analysis (`web/guided/summary/*`, `R/summarize.R`, `web/index.html`). No new figure keys, no new R files, no `EXTRA_PACKAGES` changes.

## Goals

1. Rename the user-facing "Table 1" surfaces to **Summary statistics** — "Table 1" is
   clinical jargon and vague as a navigation label.
2. Enrich the distribution figure with **box plots** and related ggplot2 panels, in both
   the demo and the your-data path (they share one R plot function).
3. Tell users **what to upload** before they pick a file, including a downloadable
   example CSV.

## Non-goals

- No violin plots (redundant with histogram + box combination).
- No p-values, no new statistical methods — presentation only.
- No new webR packages: `fig_summary` stays on the boot set (base stats + ggplot2),
  preserving its no-extra-download property.

## 1. Rename

| Surface | File | Change |
|---|---|---|
| Nav button | `web/index.html` | `Table 1` → `Summary statistics` |
| Guided shell title | `web/guided/summary/guided-summary.js` | `"Table 1 — Summary statistics"` → `"Summary statistics"` |
| Render button | `web/guided/summary/analyze-form.js` | `"Render Table 1"` → `"Render summary table"` |
| Teaching copy | `web/guided/summary/content.js` | Keeps "Table 1" as the clinical term being explained. First section title becomes **"What this table (a clinical 'Table 1') is for"** so the page leads with the plain name. |

Developer-facing text (roxygen comment in `R/summarize.R`, code comments) is out of
scope; only reword it where a touched line already changes.

## 2. R plotting (`R/summarize.R`)

`.summary_plot_svg` becomes a builder of **stacked sibling `<svg>` elements** inside the
existing `<figure class="dist-plot">` HTML block. The summary `svg` field already carries
HTML (it holds the `<table>`), so multiple SVGs need no composition package — each panel
row is its own ggplot rendered through the existing `.svg_string`.

Panel rows, in order:

1. **Histogram + density** — gated by `options.show_plots` (existing). Today's faceted
   histograms (one facet per continuous variable, free scales, dashed mean / solid
   median lines) gain a density curve overlay scaled to counts
   (`geom_density(aes(y = after_stat(count) * binwidth))`-style, implemented so ggplot2
   4.x emits no warnings).
2. **Box + jitter** — gated by `options.show_plots`. `geom_boxplot` drawn first, faint
   `geom_jitter` points layered on top, one facet per continuous variable with free y
   scales. X-axis is the group variable when `roles$group` is set; otherwise a single
   "Overall" category (matching the ungrouped table's column header). Fills use the Tol data palette (distinct from chrome colors).
   Outliers are drawn once (suppress the boxplot's own outlier points where the jitter
   layer already shows them).
3. **Q–Q** — gated by new `options.show_qq` (boolean, default `false` / absent).
   `stat_qq` + `stat_qq_line` faceted **variable × group** (group facet only when a
   group is set), matching how normality is actually assessed (within groups). The
   callout/legend explains: points near the line support mean ± SD; a curved tail
   supports median (IQR).

Shared details:

- The `.plot-legend` div gains one sentence per rendered row; the caption
  (`options.caption`) renders once per figure block, as today.
- `show_plots` continues to gate rows 1–2 as a pair; `show_qq` is independent but only
  meaningful when there is at least one continuous variable (same emptiness guard as
  today: no `<figure>` at all when nothing is plottable).
- Errors keep flowing through `render_figure`'s tryCatch contract.

## 3. UI controls

**Demo** (`web/guided/summary/guided-summary.js`, `content.js`, `demo.js`):

- New experiment checkbox **"Show Q–Q normality panels"**, default off, id `#exp-qq`,
  added to `experimentControlsSelector` and `defaultDemoOptions` (`showQq: false`).
- New `CALLOUTS.showQq` explaining the straight-line vs curved-tail reading and its link
  to the mean-vs-median decision.
- `CALLOUTS.showPlots` updated to mention the box-plot row.
- `demo.js` `buildSummaryDemoSpec` passes `show_qq: demoOptions.showQq`.

**Upload form** (`web/guided/summary/analyze-form.js`):

- New checkbox **"Show Q–Q normality plots"** (default off) beside the existing
  "Show distribution plots" toggle; `buildSummarySpec` gains `showQq` and emits
  `options.show_qq`.

## 4. Upload guidance

Pre-upload block in `renderSummaryForm`, visible before any file is chosen (static
content, so it does not disturb the progressive-disclosure rule that config stays hidden
until a parse succeeds):

- **"What your CSV should look like"** — one row per participant; one column per
  variable; first row is column headers; empty cells mean missing; an optional column
  naming each participant's group/arm; numbers unformatted (no units, no thousands
  separators).
- **"Download example CSV"** link that serializes `SUMMARY_DEMO.rows` client-side via a
  small pure `toCsv(rows, columns)` helper (lives in `web/lib/csv.js` next to
  `parseCsv`). `parseCsv` has no quoting rules, so `toCsv` throws on values containing
  commas/quotes/newlines rather than emitting a file the app's own parser cannot read.
  Download uses a Blob object URL — no network request, preserving the no-egress
  invariant.

## Testing

- **R** (`tests/testthat/test-summarize.R`, run via `devtools::test()`, WARN 0 gate):
  `show_plots` yields two sibling `<svg>`s; box-plot geometry present; grouped spec
  puts groups on the box-plot x-axis, ungrouped uses a single category; `show_qq: true`
  adds the Q–Q svg and `false`/absent omits it; density overlay and jitter leak no
  ggplot2 warnings.
- **JS unit** (`npm run test:unit`): `toCsv` output round-trips through `parseCsv`;
  `buildSummarySpec`/`buildSummaryDemoSpec` carry `show_qq`; form renders the guidance
  block and download link pre-upload; Q–Q checkbox default off.
- **E2E** (Playwright): extend the guided-summary flow — renamed nav button and render
  button; toggling the Q–Q experiment re-renders with an extra svg; example-CSV link
  present.

## Risks / notes

- ggplot2 4.x deprecation traps: use `linewidth`, never `size`, in new geoms; verify the
  density-overlay mapping emits no soft-deprecation warnings (hard WARN 0 gate).
- Tall output: three panel rows across many variables is intentional and scrollable; Q–Q
  defaults off to keep the common case compact.
- `web/R/` is a build copy — e2e verification needs `rm -rf web/R && cp -R R web/R`.

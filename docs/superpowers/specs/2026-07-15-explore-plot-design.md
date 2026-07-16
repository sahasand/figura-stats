# Explore Plot — interactive ggplot2 builder (design)

Date: 2026-07-15
Status: approved (revised after external review)

## Purpose

A third guided analysis, **Explore plot**, that turns the app into an interactive
ggplot2 workbench: the user uploads a CSV, maps columns to aesthetics
(x / y / color / facet), picks a geom, and tweaks options — and the plot
re-renders live via webR. The text pane shows the **exact, reproducible
ggplot2 code** for the current plot, making the module double as a ggplot2
starter/teaching tool. Prior art for the UX is the esquisse package
(Shiny point-and-click ggplot builder); this design reimplements that idea
on the app's existing spec → webR → SVG contract.

## Decisions made during brainstorming and review

| Question | Decision |
|---|---|
| Scope | Full plot builder (esquisse-style), not a fixed-chart param tweaker |
| Update model | Debounced auto re-render; one render in flight + newest-pending coalescing |
| Chart types (v1) | Core six: scatter, line, boxplot, violin, bar, histogram/density |
| UI shell | The guided three-stage shell (`createGuidedShell`), with a new live-render extension point |
| Text pane | Reproducible ggplot2 code (not a caption) |
| R design | Expression-first: build the call programmatically, eval it, `deparse()` it for display |

## Architecture

Follows the five-parallel-keys recipe from CLAUDE.md:

1. **`R/explore.R`** — `fig_explore(spec)` returning `list(svg =, text =)`,
   where `text` is the reproducible ggplot2 code string.
2. **`R/dispatch.R`** — add `explore = fig_explore(spec),` to the switch.
3. **`web/worker.js`** — add `"explore.R"` to the boot-time R-file fetch list.
   **No `EXTRA_PACKAGES` entry**: all six geoms use only ggplot2, which is in
   the boot set — the explorer costs zero extra package download.
4. **`web/guided/explore/`** — shell config + content + demo files mirroring
   `web/guided/summary/`; registered in `web/app.js`; nav button in
   `web/index.html`.
5. **`DESCRIPTION`** — no change (no new packages).

PNG and SVG journal export work with no new code via the existing pane-header
toolbars. **Text export needs a small analysis-aware configuration**: the
current text toolbar copies `#stats` and downloads it as `<figure>-output.tsv`
(`web/export-ui.js`), which is wrong for R code. Explore's text toolbar offers
**Copy R code** and **Download `.R`** instead; the export config gains a
per-analysis text descriptor (label + file extension + MIME type), with the
existing tsv behavior as the default so KM and Summary are untouched.

**Spec shape** — snake_case keys (matching the existing R contract, e.g.
`show_qq`), and a tagged union on `geom`: the form sends only the selected
geom's options plus the shared ones, never a bag of ignored fields.

```json
{
  "figure": "explore",
  "data": [ {"age": 61, "arm": "Treatment", ...}, ... ],
  "roles": { "x": "age", "y": "biomarker", "color": "arm",
             "facet": null, "group": null },
  "options": {
    "geom": "scatter",
    "point_size": 2, "alpha": 0.8, "smoother": "lm", "se": true,
    "title": "", "xlab": "", "ylab": ""
  }
}
```

## R side — expression-first rendering

Column names, titles, and labels are arbitrary user strings (quotes, newlines,
spaces, punctuation, non-syntactic names). `fig_explore` therefore never
interpolates them into code text. Instead:

1. **Validate** into a normalized plot description. Geom must be one of the
   whitelisted six. Role columns are type-checked per geom with readable
   `stop()` messages, reusing the suppress-warning-then-clear-`stop()`
   coercion pattern (`.numeric_col` in `R/summarize.R`).
2. **Construct an R call/expression programmatically** (base R `call()` /
   `bquote()`; no string paste). Aesthetic mappings use the `.data` pronoun —
   `aes(x = .data[["age (years)"]])` — so any column name is safe.
3. **Evaluate that expression** in a minimal environment containing only the
   data frame.
4. **`deparse()` the same expression** for the text pane (width-controlled so
   it stays readable). The displayed code cannot drift from the plot because
   both come from one expression object.

The displayed code is standalone: `library(ggplot2)`, a
`# df <- read.csv("your-data.csv", check.names = FALSE)` header comment
(`check.names = FALSE` so non-syntactic column names like `age (years)` load
unmangled and match the emitted `.data[["age (years)"]]`), then the deparsed plot
code. **The expression must be self-contained in a plain R session**: the
Tol palette values and theme are inlined as literal
`scale_colour_manual(values = c(...))` / `theme_minimal()` + `theme(...)`
calls — it must never reference package internals like `.km_palette()` or
`.fig_theme()`. The palette constants are shared with `R/km.R` at the package
level (hoisted, not duplicated), but the *emitted expression* carries literals.

**Missing values.** Before plotting, rows with `NA` in any used role column
are removed via `complete.cases()`, and the removed count is surfaced as a
comment line in the code text (e.g. `# note: 12 rows with missing values in
the selected columns were excluded`). This is deterministic and prevents
ggplot's own NA-removal warnings, which would otherwise conflict with the
WARN 0 gate for any valid clinical dataset.

### Geoms, roles, and options (v1)

| Geom | Required roles | Options |
|---|---|---|
| scatter | x numeric, y numeric | `point_size`, `alpha`, `smoother` (none/lm/loess), `se` on/off |
| line | x numeric, y numeric; **`group` optional-but-recommended** | `linewidth`, `show_points` |
| boxplot | x categorical, y numeric | `jitter` overlay, `notch` |
| violin | x categorical, y numeric | `inner_box`, `trim` |
| bar | x categorical | `prop` on/off; `position` dodge/stack (only when color set) |
| histogram | x numeric | `bins` slider; `density` toggle |

- **Line charts get a `group` role** (categorical ID column, e.g. patient ID)
  so repeated-measures data draws one line per subject; color alone would
  connect unrelated participants within an arm.
- **Bar proportions have an explicit denominator**: with no color mapping,
  each bar is its share of the total N; with a color mapping, proportions are
  computed **within each x category** (rendered as `position = "fill"`, bars
  sum to 1). The generated code makes this visible, and the UI labels the
  toggle accordingly ("% of total" / "% within group").

Shared across all geoms:

- **color** (optional) → house Tol palette (shared constants with
  `R/km.R .km_palette`, inlined as literals in emitted code).
- **facet** (optional, categorical) → `facet_wrap()`.
- **Numeric-coded categories**: `web/lib/csv.js` classifies `0/1/2` columns
  as numeric, which describes many real clinical grouping variables.
  Categorical roles (x for box/violin/bar, color, facet, group) therefore
  **accept numeric columns too**; when one is chosen, the generated code wraps
  it in `factor()`. The column picker lists numeric columns for these roles
  with a "(treated as categories)" hint, ordered after true categoricals.
- Title / x-label / y-label text inputs → `labs()`.
- House theme, inlined in emitted code.

All generated code is ggplot2 4.x-clean: `linewidth` not `size` for lines,
no deprecated geoms/args. **WARN 0 is a hard gate.**

## JS side — guided shell + live loop

`web/guided/explore/guided-explore.js` is a `createGuidedShell({...})` config,
never a shell copy. Stage content:

- **Understand** (`content.js`): what aesthetic mapping is (columns → x / y /
  color / facet), and when to use which of the six geoms.
- **Try an Example** (`demo.js`, `demo-data.js`): frozen synthetic clinical
  dataset generated by `data-raw/explore-demo-generator.R` (~120 patients:
  age, BMI, biomarker, arm, sex — plus a long-format repeated-measures block
  so the line geom's `group` role has something real to bite on). The
  "experiment controls" for this analysis are the actual builder controls.
- **Analyze Your Data** (`analyze-form.js`): CSV upload via `web/lib/csv.js`,
  role dropdowns via `web/lib/columnpicker.js` (type-filtered per geom with
  the numeric-as-categorical relaxation above), same builder controls as the
  demo stage.

**Live update loop.** The current shell disables all experiment controls and
replaces the preview with "Rendering…" during a run (`web/guided/shell.js`),
which serializes interaction — fine for checkbox experiments, wrong for a
builder. `createGuidedShell` gains an **opt-in `liveRender` extension point**
with these semantics (existing analyses keep the current behavior):

- **Debounce** ~400 ms after the last control change before submitting.
- **At most one render in flight.** New changes during a render overwrite a
  single **newest-pending spec** (not a queue). When the in-flight render
  finishes, its result is discarded if stale, and the pending spec is
  submitted immediately. A running R eval in the webR worker cannot be
  aborted, so this coalescing model is the strongest available guarantee —
  slow renders can never accumulate.
- **Revision tracking is per context** (demo stage vs. analyze stage), so a
  stale demo response can never paint over a user-data plot or vice versa.
- **Controls stay enabled** during renders; the previous SVG stays visible
  with a translucent busy overlay instead of being replaced by text.

**Geom-driven control visibility**: switching geom swaps which role pickers
and option controls are visible (boxplot has no bins slider). Role selections
incompatible with the new geom are cleared; the column pickers' type filtering
guards most invalid specs before R sees them.

## Errors and testing

- **R** (`tests/testthat/test-explore.R`):
  - One golden-path test per geom: SVG renders (`<svg` prefix) and the code
    string contains the expected calls (e.g. `geom_boxplot`, `facet_wrap`).
  - **Adversarial inputs**: column names with spaces, punctuation, and
    unicode; titles/labels containing quotes and newlines; numeric-coded
    grouping columns in categorical roles; datasets with NAs in used columns
    (assert the exclusion comment and no warnings).
  - Error tests: unknown geom, non-numeric column in a numeric role, missing
    required role → readable messages via the never-throws contract.
  - Run with `devtools::test()`; `[ FAIL 0 | WARN 0 ]` required.
- **JS unit** (`npm run test:unit`): spec-building (tagged union — only the
  active geom's options are sent), control-visibility logic, coalescing logic
  (newest-pending replaces, stale results dropped), frozen demo-data test.
- **E2E** (Playwright): load the explorer, demo renders, change geom + one
  option, assert the plot re-renders and the code text updates; rapid-fire two
  changes and assert the final plot matches the last change; text toolbar
  offers Copy R code / Download `.R` (not tsv) and enables correctly.

## Out of scope (v1)

- Heatmaps, error-bar summary plots, strip charts (candidate v2 geoms).
- Numeric color scales / continuous gradients.
- Multiple layered geoms beyond the built-in combos (e.g. violin + inner box).
- Saving/loading plot configurations.

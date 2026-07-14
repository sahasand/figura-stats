# Clinical Manuscript Figures — Design Spec

**Date:** 2026-07-13
**Status:** Approved design, pre-implementation
**Working name:** my-stats (rename candidate at publish time: `manuscript-figures`)

## Purpose

A free, open-source, browser-based tool that produces publication-ready clinical
figures and correctly formatted statistics text for journal manuscripts — powered
by real R packages (ggplot2, survival, gtsummary) running entirely in the user's
browser via webR (WebAssembly). No server, no accounts, no data upload.

## Target user

Non-technical staff at CROs and pharma — medical writers, clinical ops — who
assemble journal manuscripts but do not write code. They typically hold summary
numbers from biostats outputs, not patient-level data.

## Business intent

Open-source credibility play (same pattern as Tracescribe-open): public repo,
free static hosting, adoption and reputation first, no monetization planned.
Success milestone: 10 external viewers/users of the published tool.

## Core value propositions

1. **Zero cost to run** — static site on GitHub Pages, compute happens client-side.
2. **Zero data exposure** — data never leaves the browser; the pharma trust
   objection is answered by architecture, not by a privacy policy.
3. **Real R correctness** — figures and statistics come from the same packages
   (ggplot2, survival, survminer, gtsummary) that biostats departments already
   trust, not a JavaScript reimplementation.

## Scope — v1 outputs

| Output | Input mode | Notes |
|---|---|---|
| Forest plot | Summary numbers (form) | Effect estimates + CIs per subgroup; simplest, build first |
| CONSORT flow diagram | Summary numbers (form) | Pure layout, no stats; required by most journals for RCTs |
| Demographics "Table 1" | Summary numbers (form) | Formatting/layout of stats the writer already has |
| Kaplan-Meier curve | Patient-level CSV (drop-zone) | Risk table, log-rank p, HR; CSV parsed client-side only |

Build order: app shell + forest plot first; the remaining three follow the same
pattern. Patient-level input for the other figures (e.g., computed Table 1 from
ADaM/CSV extracts) is a deliberate later phase, not v1.

Every figure also emits **copyable methods/results text** (e.g., "Median OS was
18.2 months (95% CI 14.1–22.3); log-rank p = 0.003") suitable for pasting into
a manuscript.

## Architecture

A static single-page app. No backend of any kind.

```
┌─────────────────────────── Browser ───────────────────────────┐
│  UI layer (vanilla HTML/CSS/JS — no framework)                 │
│  ├─ Figure picker:  KM │ Forest │ Table 1 │ CONSORT            │
│  ├─ Input panel:    form fields (summary mode) or              │
│  │                  CSV drop-zone (patient-level mode)         │
│  └─ Preview + Export panel                                     │
│                        │  JSON spec in / SVG + text out        │
│                        ▼                                       │
│  webR (WASM) — R session in a Web Worker                       │
│  └─ packages: ggplot2, survival, survminer, gtsummary,         │
│               broom, svglite                                   │
│  NOTHING leaves this box. No backend. No analytics on data.    │
└────────────────────────────────────────────────────────────────┘
```

Key decisions:

1. **webR runs in a Web Worker** so the UI never freezes during R computation.
2. **Contract between UI and R:** the UI sends a plain JSON spec
   (`{figure: "forest", rows: [...], options: {...}}`); one R entry function per
   figure type consumes it and returns SVG plus stats text. Same signature for
   all four.
3. **Lazy loading:** the app shell loads instantly; webR (~30 MB+, one-time,
   browser-cached) downloads in the background with a visible progress state.
   Package binaries come from the webR CDN repository.
4. **Exports:** SVG and PNG (via svglite) for figures; HTML/Word-pasteable
   output from gtsummary for Table 1; copyable methods/results sentences for all.
5. **Reproducibility without data sharing:** users can download the JSON spec
   and re-upload it later to regenerate a figure exactly.

## Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `R/forest.R`, `R/km.R`, `R/table1.R`, `R/consort.R` | One entry function each: JSON spec in → SVG + stats text out | ggplot2, survival, survminer, gtsummary |
| `web/` (UI) | Figure picker, input forms, CSV drop-zone, preview, export. Vanilla JS, no framework — keeps the static site dependency-free | webR worker |
| `web/worker.js` | Boots webR, installs/loads packages, routes JSON specs to R functions, catches errors | webR CDN |
| Journal presets | Theme setting (font, size, DPI) per common target: NEJM/JAMA-ish, generic | pure R theme code |

Unit boundary rationale: each R file is independently testable in plain R on a
laptop, with no browser involved — webR is only the delivery vehicle.

## Data flow

- **Summary mode** (forest, CONSORT, Table 1): form input → JSON spec → R
  function → SVG + results sentence → preview/export.
- **Patient-level mode** (KM): CSV dropped and parsed in-browser → same pipeline.
- No network calls carry user data at any point.

## Error handling

- Form-level validation before R is called (required fields, CI bounds ordered,
  numeric ranges).
- R errors caught in the worker and translated to plain-language messages
  ("Group 2 has no events — the log-rank test needs at least one event per
  arm"); raw R tracebacks are never shown.
- webR load failure (old browser, offline) produces an up-front explanatory
  message, not a dead button.

## Testing

- **Unit:** testthat tests for each R function, run in plain R via CI (GitHub
  Actions), with golden-file snapshots of SVG and stats text.
- **Statistical correctness:** pinned tests reproducing published results — a
  known KM dataset must reproduce its published HR, median, and log-rank p.
- **End-to-end:** one Playwright smoke test verifying the browser wiring
  (load app → enter forest-plot data → SVG appears).

## Constraints and context

- Per the July 2026 working rules: one folder per theme; this project lives in
  `~/Documents/my-stats` (created 2026-07-13). The "no new project dirs until
  one artifact has 10 external viewers" rule (in force until 2026-08-06) was
  flagged and consciously set aside by the owner for this project.
- Initial webR payload (~30–70 MB) is an accepted trade-off; mitigated by lazy
  loading and browser caching.
- Packages must have webR/WASM builds — ggplot2, survival, survminer, and
  gtsummary are all available in the webR repository as of mid-2026; verify at
  implementation start.

## Out of scope (v1)

- Patient-level input for anything other than KM.
- Accounts, saving to cloud, collaboration features.
- Additional figure types (waterfall, spider, funnel) — natural v2 candidates.
- Python/plotnine conversion — the webR approach makes it unnecessary.

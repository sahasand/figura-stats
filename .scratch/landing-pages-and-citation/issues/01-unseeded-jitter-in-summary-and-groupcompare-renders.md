# 01 — Unseeded geom_jitter makes Summary and Group-comparison renders non-reproducible

Status: needs-triage
Type: task
Found: 2026-09-09, during the final whole-branch review of landing-pages-and-citation
(deferred: changes shipped rendering; out of scope for that branch)

## Problem

`R/summarize.R` (~line 174) and `R/groupcompare.R` (~line 111) both call
`ggplot2::geom_jitter()` with no seed. Two renders of the same CSV therefore place
points at different pixel positions each time: the table and reported statistics are
identical, but the scatter figure itself is not byte-reproducible. This bit the landing
pages directly — `scripts/pages/render-examples.R` needed `set.seed(20260909L)` before
rendering the frozen demo datasets, or the committed `web/<slug>/example.json` renders
would not reproduce and `build.test.mjs`'s freshness check would fail on regeneration.

## Impact

A user who re-exports a Summary or Group-comparison figure from the same CSV gets a
slightly different PNG/SVG each time, which is surprising for a tool whose pitch is
reproducible output. The webR release gate compares displayed text only, never SVG
pixels, so this gap is invisible to it and stays invisible after any fix.

## Proposed fix

Pass a fixed `seed` via `ggplot2::position_jitter(seed = <constant>)` inside the plot
builders in `R/summarize.R` and `R/groupcompare.R`, rather than relying on
`render-examples.R`'s external `set.seed`.

## Notes

Changes point placement for every user render, not just the demo — needs a re-run of
`npm run build:examples`, `npm run build:pages`, and `make -C stats-validation all`, even
though no reported number moves. Once fixed, `render-examples.R`'s `set.seed(20260909L)`
can likely be dropped, since the app's own output would already be deterministic.

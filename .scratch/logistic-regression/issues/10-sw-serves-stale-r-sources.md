# 10 — The service worker can serve one page-load of stale statistical code

Status: resolved
Type: task
Found: 2026-07-20, while browser-verifying the forest-plot proportion fix

## Problem

`web/sw.js:61-62` routes **all** same-origin GETs through `staleWhileRevalidate`, and that
includes `R/*.R` — the statistical source of truth, fetched by the webR worker at boot.

On a deploy that changes R without bumping `CACHE`, a returning user's **first** load
serves the previous `R/*.R` from cache and refreshes in the background. The page therefore
computes and renders with the *old* statistics for that whole session, and only picks up
the new code on a subsequent load.

The comment at `web/sw.js:69-75` treats this as a feature ("self-heals within one round
trip, no CACHE bump required"). That reasoning is sound for chrome — CSS, an icon, a nav
label. It is **not** sound for `R/`, because a round trip here means a full extra page load
during which the user sees numbers and figures produced by code the project has already
decided was wrong.

## How it actually bit

Twice, both times reading as "the fix didn't ship":

1. `4695be2` (forest-plot canvas proportions) deployed without a `CACHE` bump. The plot
   looked unchanged on reload. Confirmed the mechanism by unregistering the service worker
   in a headless browser — the same build then rendered the corrected figure immediately.
2. Earlier, during `fix/cox-shell-issues`, the same reasoning surfaced from the other
   direction: a newly-added statically-imported module could miss the cache entirely and
   break the whole `app.js` module graph offline. That one was caught in review and fixed
   with a bump (`a404a07`).

The `CACHE` bump discipline is now documented in CLAUDE.md's "Adding a figure or analysis",
but a convention that must be remembered on every R change is a weak guard for a
correctness-relevant asset.

## Fix

Decide between two routes:

1. **Network-first (or cache-busted) for `R/*.R` specifically.** Give R sources their own
   branch in the fetch handler: try the network, fall back to cache only when offline. R
   files are small (tens of KB) next to the ~6MB webR runtime that legitimately stays
   cache-first, so the bandwidth cost is negligible and the offline story is preserved.
   This removes the stale-statistics window entirely and makes the `CACHE` bump optional
   again rather than load-bearing.
2. **Keep SWR and enforce the bump mechanically.** A CI check that fails when the diff
   touches `R/` without changing `CACHE` in `web/sw.js`. Cheaper to build, but it only
   catches the case where someone *forgets*; it does not shorten the stale window for
   anyone who deploys correctly and has a user mid-session.

Route 1 is the better fix — it addresses the hazard rather than the human step. Route 2 is
a reasonable belt alongside it.

## Test

- Unit or integration: assert the fetch handler does **not** return a cached `R/*.R` when
  the network is reachable. The existing e2e cannot cover this (it runs without a
  registered service worker), so this likely wants a focused test against the handler's
  routing logic rather than a browser test.

## Comments

Fixed with route 1, on `main`. `web/sw.js` gained a pure `routeFor(req)` that returns one
of `r-source` / `same-origin` / `webr-static` / `pass`, and the fetch handler now only
dispatches on its answer; `R/*.R` goes to a new `networkFirst()` whose cached copy is an
offline fallback only.

Route 1 alone was **not sufficient**, which only showed up in a browser. Bypassing the
service-worker cache still left the browser's **HTTP cache** in front of the SW's own
`fetch()`, and a response with no `Cache-Control` (the dev server sends only
`Last-Modified`) gets heuristic freshness of ~10% of its age — so a just-edited R file
kept reading stale through the new network-first path. The fetch is therefore issued as
`new Request(req, { cache: "reload" })`, which bypasses both caches. Verified end to end:
edit an R source, load once, and the first load sees the change.

Route 2 (a CI check tying `R/` diffs to a `CACHE` bump) was **not** added — with R sources
network-first the bump is no longer correctness-relevant for statistics, so the check would
enforce a convention that no longer guards anything.

Tests: `web/sw.test.mjs` runs the real `sw.js` in a `node:vm` sandbox with cache/fetch
doubles (not a copy of its logic) and pins the routing table, the network-wins rule, the
HTTP-cache bypass, the offline fallback, and that a 404 neither answers nor poisons the
cache. Wired into `test:unit`.

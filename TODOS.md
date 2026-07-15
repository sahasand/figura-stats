# TODOS

Deferred work with context. Each entry records what, why, and where to start so it
survives a three-month gap. Added by /plan-eng-review 2026-07-15 (guided summary
statistics plan review).

## Summary-numbers-only Table 1 mode

- **What:** A secondary entry path for users who hold aggregate numbers (means, SDs,
  counts) but no row-level CSV — the capability retired when the typed Table 1 form
  was replaced by the guided upload flow.
- **Why:** Meta-analysts and authors re-reporting a published table cannot produce a
  row-level CSV; today they could type values in, after the replacement they cannot.
- **Context:** `web/forms/table1.js` + `R/table1.R` + `tests/testthat/test-table1.R`
  live in git history at the commit before the guided-summary plan landed. A future
  version should live inside the guided summary shell as an "I only have summary
  numbers" branch rather than a separate nav entry. Deliberate trade-off recorded in
  the plan's NOT-in-scope section (review decision D14).
- **Depends on / blocked by:** A demand signal (user request/issue — the site has no
  analytics by design). Blocked by nothing technically.

## Share one webR boot across e2e example-stage tests

- **What:** Restructure `tests/e2e/km-guided.spec.js` and
  `tests/e2e/summary-guided.spec.js` so the heavy example-stage tests share one booted
  webR page (Playwright serial mode or a shared fixture) instead of each paying a cold
  ~30s+ runtime download.
- **Why:** E2E wall-clock grows linearly with every guided analysis; two suites with
  3–4 heavy tests each is minutes of pure re-downloading and a flake source under
  timeouts.
- **Context:** Deliberately kept out of the guided-summary plan because it touches the
  regression-sensitive KM spec. Best done as a standalone change right after the
  summary feature lands, with both suites green before and after.
- **Depends on / blocked by:** Guided summary statistics feature landing first.

## Write DESIGN.md via /design-consultation

- **What:** Consolidate the de facto design system (styles.css tokens, FINDING-001…011
  control conventions, journal-table and figure treatments, warn register, type scale)
  into a written DESIGN.md.
- **Why:** Two design reviews in two days (KM live audit 2026-07-14, guided-summary
  plan review 2026-07-15) each re-derived the system from styles.css and git history;
  every future review pays that cost again until it's written down.
- **Context:** `/design-consultation` generates it. The tokens and conventions already
  exist — this is documentation, not invention. Approved visual references live in
  `~/.gstack/projects/my-stats/designs/`.
- **Depends on / blocked by:** Nothing; ~10 min with CC. Best done before the next
  analysis goes guided.

## Unify app.js render() with the shared guided shell's runAndShow

- **What:** One paint/error/status path for figure results instead of two
  near-identical implementations (`web/app.js:45-63` and the guided shell's
  `runAndShow`).
- **Why:** DRY — error styling and status-chip behavior must currently be fixed in two
  places and can drift between guided and plain analyses.
- **Context:** The guided-summary plan extracts a shared `createGuidedShell` for the
  guided analyses; this TODO is the follow-on that absorbs the plain-form path too. It
  touches every non-guided form's submit path, so it wants its own change with the
  full e2e suite as the gate. Natural trigger: the next analysis that goes guided.
- **Depends on / blocked by:** The shared shell refactor from the guided-summary plan.

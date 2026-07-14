# Guided Analysis / Kaplan–Meier Final Implementation Plan

**Status:** Ready for implementation  
**Date:** 2026-07-14  
**Canonical requirements:** `.scratch/guided-analysis-km/PRD.md`

## Outcome

Replace the current fixed-column Kaplan–Meier form and Figure/Console output with the complete Guided Analysis pilot described in the PRD, without changing the behavior of the seven other analysis types.

The build is complete when a clinical researcher can learn the method, run the fixed synthetic example, load and validate a private CSV through Analysis Roles, run an authoritative R analysis, understand a structured Analysis Result, and download/copy a responsible Analysis Handoff.

## Architecture and test seam

Keep the static vanilla-JavaScript/webR architecture.

- JavaScript owns Guided Stage navigation, Analysis Session state, CSV parsing, role mapping, progressive preflight, result rendering, and clipboard/download behavior.
- R owns authoritative validation and every statistical value, diagnostic, curve coordinate, and risk-set value.
- The worker remains the only browser-to-R seam.
- Kaplan–Meier returns a versioned structured result plus SVG. The dispatcher preserves the existing `{ok, svg, text}` behavior for other analyses.
- Test the feature primarily at the browser workflow seam and secondarily at the pure R function/dispatcher seam. Use small pure-JS tests only for deterministic logic that does not need a browser.

## Global constraints

- Do not introduce a framework, backend, account, persistent browser storage, or transmission of user data.
- Do not refactor other analysis forms into Guided Analysis in this work.
- Do not silently modify, coerce, delete, impute, or exclude uploaded rows.
- Do not calculate survival statistics in JavaScript.
- Do not build manuscript language from rounded display strings.
- Keep demo and user state/results separate.
- Keep a prior successful result visible on a failed rerun, but label its current/out-of-date state accurately.
- Preserve the existing dirty worktree; each implementation session must inspect overlapping changes before editing.
- Regenerate the ignored `web/R/` copy from `R/` before browser tests; never commit `web/R/`.

## Verification commands

Use these as the stable gates throughout implementation:

```bash
npm run test:unit
Rscript -e 'devtools::test()'
npx playwright test tests/e2e/km-guided.spec.js
npx playwright test
```

The full R suite must finish with WARN 0. `git diff --check` must pass at every commit boundary.

## Dependency graph

```text
WP1 Contract and state foundation
 └─> WP2 Demonstration tracer
      ├─> WP3 User-data and preflight tracer
      └─> WP4 Complete statistical result
             └─> WP5 Result and Analysis Handoff
                    └─> WP6 Teaching, accessibility, resilience, and privacy
                           └─> WP7 Release gate and cleanup
```

WP3 and WP4 may be implemented in either order after WP2, but both must finish before WP5. All other dependencies are strict.

---

## WP1 — Contract and Analysis Session foundation

**Goal:** Establish one reusable Guided Analysis seam and a backward-compatible structured computation contract before building visible detail.

**Primary files**

- Modify: `web/app.js`, `web/index.html`, `web/styles.css`, `web/worker.js`
- Create: `web/guided/guided-analysis.js`
- Create: `web/guided/session-state.js`
- Create: `web/guided/result-schema.js`
- Create: `web/guided/session-state.test.mjs`
- Create: `web/guided/result-schema.test.mjs`
- Modify: `R/dispatch.R`, `tests/testthat/test-dispatch.R`

**Implementation slices**

1. Write a failing state test for separate example/user contexts, active Guided Stage, working/current/out-of-date transitions, and Clear My Data.
2. Implement a small in-memory state reducer/store. Do not use browser persistence.
3. Write a failing schema test for a versioned Kaplan–Meier Analysis Result with explicit missing/not-reached/withheld states.
4. Define the JavaScript schema validator used at the worker boundary. Reject malformed successful responses as an analysis error rather than partially rendering them.
5. Extend R dispatch so a figure function may return an optional structured `analysis` member while existing functions continue returning SVG/text unchanged.
6. Add Guided Analysis shell registration to the existing form registry. Only the Kaplan–Meier route uses it.
7. Add URL query or hash synchronization for `analysis=km` and `stage=understand`; never serialize input values, mappings, filenames, or result data.
8. Implement semantic Guided Stage tabs and empty/working/error/current/out-of-date shell states with placeholder content.
9. Ensure changing analysis and returning to Kaplan–Meier restores the in-memory stage state; page reload starts clean.

**Acceptance gate**

- Unit tests prove state isolation and transitions.
- Dispatcher tests prove legacy responses are unchanged and structured KM responses serialize.
- Keyboard focus can select every stage tab.
- URL changes contain only the analysis and stage.
- Existing unit and e2e tests remain green.

**Commit boundary:** `feat: add guided analysis session and result contract`

---

## WP2 — Full Demonstration Dataset tracer

**Goal:** Deliver the first complete vertical slice: open Kaplan–Meier, run the real synthetic example, and display a minimal structured result.

**Primary files**

- Create: `web/guided/km/module.js`
- Create: `web/guided/km/content.js`
- Create: `web/guided/km/demo.csv`
- Create: `web/guided/km/demo.js`
- Create: `web/guided/km/demo.test.mjs`
- Modify: `R/km.R`, `tests/testthat/test-km.R`
- Create: `tests/e2e/km-guided.spec.js`

**Implementation slices**

1. Add the fixed 120-participant, versioned Demonstration Dataset and a JS fixture test for row count, balanced groups, required columns, fixed checksum/version, and mandatory synthetic label.
2. Add the Kaplan–Meier module descriptor with three stages, role definitions, the approved Demonstration Story, default Analysis Definition, and default options.
3. Render the Try an Example stage with read-only study context and **Run Example Analysis**. Do not initialize webR until this explicit action.
4. Send the example through the same request builder and worker path planned for user data.
5. Upgrade `fig_km()` minimally to return structured source/provenance, group counts, event/censor counts, and a valid SVG while keeping current statistical behavior temporarily.
6. Render a minimal result header, figure, and counts from the structured result—not from hard-coded demo copy.
7. Add Reset Example and separate example state/result storage.
8. Add one Playwright test from Kaplan–Meier selection through real webR computation to a visible synthetic-labeled result.

**Acceptance gate**

- Demo computation is real and uses `fig_km()`.
- No result is shown before Run Example Analysis.
- Demo and user contexts cannot share data or results.
- Every reusable demo surface contains the mandatory synthetic label.
- The demo tracer passes in R and Playwright.

**Commit boundary:** `feat: run guided Kaplan-Meier demonstration end to end`

---

## WP3 — User CSV, Analysis Roles, and Analysis Preflight tracer

**Goal:** Replace the fixed `time,status,group` loader with the approved local data and validation workflow.

**Primary files**

- Modify: `web/lib/csv.js`, `web/lib/csv.test.mjs`
- Create: `web/guided/data-preview.js`
- Create: `web/guided/role-mapping.js`
- Create: `web/guided/preflight.js`
- Create: `web/guided/preflight.test.mjs`
- Create: `web/guided/km/preflight.js`
- Create: `web/guided/km/template.csv`
- Replace Kaplan–Meier use of: `web/forms/km.js`
- Add fixtures under: `tests/e2e/fixtures/`
- Modify: `tests/e2e/km-guided.spec.js`

**Implementation slices**

1. Expand the CSV parser test matrix for quoted commas, escaped quotes, embedded newlines, UTF-8 BOM, CRLF, blank headers, duplicate headers, inconsistent widths, and empty files. Adopt a vetted local parser or implement the standard fully; do not retain comma splitting.
2. Enforce the 5 MB/50,000-row cap before role mapping. Show exact limits and keep the current dataset when a replacement is rejected.
3. Build drag-and-drop/file-picker input, downloadable template, local-processing copy, and read-only first-10-row Data Preview.
4. Implement ranked suggestions for follow-up time, event status, group, and participant identifier while leaving every source column selectable.
5. Build explicit Event/Censored value mapping with counts; group labels; optional participant ID; and two-group reference direction.
6. Build Analysis Definition fields and the Method Suitability Check using the approved domain language.
7. Implement progressive Blocker/Confirmation/Notice findings. Findings link to exact preview rows and never offer delete/fix-in-app actions.
8. Implement duplicate-ID checks or the no-ID independence confirmation.
9. Implement adaptive analysis options for no group, two groups, and more than two groups.
10. Build the final Ready to analyze summary and enable Run only when every Blocker is gone and every Confirmation is accepted.
11. Make dataset replacement transactional and implement confirmed Clear My Data, including object-URL revocation and result removal.
12. Add Playwright coverage for a successful arbitrary-column CSV, a blocker and recovery, transactional replacement, and Clear My Data.

**Acceptance gate**

- No fixed column name is required.
- An event code cannot be inferred silently.
- Invalid rows are reported, not excluded.
- The preflight summary reconciles exactly with the request sent to R.
- User data survives stage navigation only in memory and disappears on reload/Clear My Data.
- Oversized and malformed files fail before webR runs.

**Commit boundary:** `feat: add role-mapped Kaplan-Meier data preflight`

---

## WP4 — Complete authoritative Kaplan–Meier Analysis Result

**Goal:** Make R produce the complete statistically responsible structured result and publication-ready SVG.

**Primary files**

- Modify: `R/km.R`, `R/dispatch.R`, `R/themes.R`
- Modify: `tests/testthat/test-km.R`, `tests/testthat/test-dispatch.R`
- Add fixed R fixtures under: `tests/testthat/fixtures/`
- Keep browser build copy synchronized in: `web/R/` during tests only

**Implementation slices**

1. Replace the random smoke fixture with fixed known datasets for ungrouped, two-group, multi-group, zero-event, median-not-reached, tied-time, sparse-tail, and proportional-hazards concern states.
2. Add authoritative R validation for finite non-negative time, explicit binary status mapping, row counts, group levels, reference direction, and supported model structure.
3. Return normalized provenance and analysis definition plus per-group participant/event/censor counts.
4. Return complete curve coordinates: time, survival, pointwise 95% confidence limits, cumulative events/censors, and risk-table counts at deterministic display times.
5. Return prespecified landmark estimates with confidence intervals and numbers at risk.
6. Return medians and confidence intervals with explicit reached/not-reached/not-estimable states.
7. Return ordinary log-rank chi-square, degrees of freedom, and two-sided p-value for supported grouped analyses; mark multi-group results omnibus.
8. Return an optional directed, unadjusted Cox HR with 95% CI, tie method, and proportional-hazards diagnostic for supported two-group analyses.
9. Return structured findings for sparse tails, crossing curves, PH concerns, unreliable estimates, and withheld comparisons.
10. Generate the SVG with pointwise bands, censor marks, redundant group encoding, endpoint/time labels, group sizes, real aligned risk table, concise caption, accessible title/description, and no external resources.
11. Pin every expected Demonstration Dataset count and estimate used by teaching or handoff copy.
12. Verify precision formatting separately from raw values; retain full precision in the result payload.

**Acceptance gate**

- R tests cover every supported and withheld state with WARN 0.
- Counts reconcile with the input and preflight fixture.
- Known numerical results match independently verified expectations within declared tolerances.
- The SVG contains the risk table and remains distinguishable without color.
- Existing non-KM dispatch behavior remains unchanged.

**Commit boundary:** `feat: produce structured Kaplan-Meier analysis results`

---

## WP5 — Analysis Result, Interpretation Guidance, and Handoff

**Goal:** Replace Figure/Console with the approved result document and manuscript handoff.

**Primary files**

- Create: `web/guided/result-view.js`
- Create: `web/guided/findings-view.js`
- Create: `web/guided/figure-data-view.js`
- Create: `web/guided/handoff.js`
- Create: `web/guided/handoff.test.mjs`
- Create: `web/guided/km/interpretation.js`
- Create: `web/guided/km/interpretation.test.mjs`
- Modify: `web/index.html`, `web/styles.css`, `web/app.js`
- Modify: `tests/e2e/km-guided.spec.js`

**Implementation slices**

1. Write deterministic formatter tests for precision, p-value thresholds, not reached, not estimable, comparison withheld, and directed HR language.
2. Render the single scrollable result in the approved order with a persistent provenance/status header.
3. Render findings at two levels: grouped near the top and repeated beside each affected estimate/comparison.
4. Render group overview, landmark/median estimates, comparisons, diagnostics, and visible limitations from the structured result.
5. Implement deterministic Interpretation Guidance using the approved templates. Never produce free-form statistical claims.
6. Add View figure data semantic tables for plotted values and numbers at risk.
7. Mark the result Out of date on any material input change and disable handoff actions until rerun.
8. Implement Download SVG with the approved sanitized filename. Keep warnings outside the SVG.
9. Implement exact previews and copy behavior for Methods, Results, and Complete Handoff, writing semantic HTML plus equivalent plain text.
10. Add the mandatory figure-use note carrying provenance and applicable warnings with the clean SVG.
11. Add accessible clipboard/download success and failure recovery; fall back to selectable preview text.
12. Add Playwright coverage for copy payload equality, SVG download name/content, demo labeling, and stale-result blocking.

**Acceptance gate**

- Screen, SVG, figure-data tables, Interpretation Guidance, and copy derive from one structured result.
- Description precedes inference and every withheld value has a reason.
- No output says `p = 0.000`, implies causality, or equates threshold crossing with efficacy.
- Clean SVG plus Complete Handoff preserves all required context and warnings.
- Copy/download cannot run on an Out-of-date Result.

**Commit boundary:** `feat: add Kaplan-Meier result and manuscript handoff`

---

## WP6 — Teaching content, accessibility, resilience, and privacy

**Goal:** Finish the approved learning experience and meet the cross-cutting quality bar.

**Primary files**

- Modify: `web/guided/km/content.js`, `web/guided/km/module.js`
- Create: `web/guided/km/teaching-visual.js`
- Modify: `web/guided/guided-analysis.js`, `web/guided/result-view.js`
- Modify: `web/worker.js`, `web/styles.css`, `web/index.html`
- Modify: `tests/e2e/km-guided.spec.js`, `playwright.config.js`

**Implementation slices**

1. Install the approved Understand copy, suitability guidance, required-data explanation, interpretation primer, escalation message, and sources/methodology disclosure.
2. Build the explicitly labeled non-data Teaching Visual with accessible text equivalent.
3. Add contextual Learning Callouts and the three reversible Guided Experiments. Reset Example restores every default.
4. Add ordered progress messages for runtime initialization, package loading, validation, computation, and result preparation.
5. Disable duplicate stage runs and ignore late responses that no longer match the originating request/session version.
6. Add retry after runtime/package/computation failure without clearing inputs or the last successful result.
7. Complete semantic tabs, headings, findings, tables, disclosures, dialog/confirmation behavior, focus management, live status, and error association.
8. Meet visible focus, AA contrast, non-color encoding, reduced-motion, 200% zoom, 320-pixel viewport, and no page-level horizontal-scroll requirements.
9. Keep Guided Stage navigation usable during worker activity and announce result-ready/error status on return.
10. Add a privacy e2e test using a unique sentinel CSV value and network interception; fail if the sentinel enters any request URL, header, or body.
11. Add slow/failing-worker test hooks that are inactive in production and test progress, retry, preserved inputs, and stale-response protection.
12. Perform manual keyboard-only and one screen-reader pass; record results and fixes in the PRD comments or implementation ticket.

**Acceptance gate**

- Every workflow action works with keyboard only and has an accessible name/state.
- Dynamic stage, validation, run, copy, and error changes are announced appropriately.
- The workflow is usable at 200% zoom and 320 CSS pixels.
- Network inspection proves the unique user-data marker never leaves the browser.
- Slow and failed webR states recover without losing input.

**Commit boundary:** `feat: complete guided Kaplan-Meier learning and quality states`

---

## WP7 — Integrated release gate and cleanup

**Goal:** Prove the pilot meets the PRD, remove obsolete KM paths, and leave an agent-maintainable module.

**Primary files**

- Modify: `web/forms/km.js` or remove it after all imports migrate
- Modify: `web/app.js`, `web/index.html`, `web/styles.css`, `web/worker.js`
- Modify: all KM unit/R/e2e tests as required
- Update: project documentation describing the Kaplan–Meier workflow and privacy boundary

**Implementation slices**

1. Remove the old fixed-column KM parser, legacy Figure/Console assumptions for KM, dead selectors, duplicate templates, and unused styles.
2. Verify the other seven analyses still select, render, and report errors as before.
3. Run the 5 MB/50,000-row performance fixture in the supported browser profile. Lower the documented cap if it cannot complete preflight and submit without tab failure; do not raise it in this release.
4. Run every unit, R, focused KM e2e, and full Playwright command.
5. Run `git diff --check` and inspect the final diff against the PRD rather than only against this task list.
6. Complete manual QA for desktop, 320-pixel mobile viewport, 200% zoom, keyboard, screen reader, grayscale print preview, cold package load, retry, Clear My Data, and downloaded/copied artifacts.
7. Run `/code-review` against the implementation base, addressing both Standards and Spec findings before commit.
8. Update the local implementation ticket statuses and add any deliberately deferred items only if they are already out of scope in the PRD.

**Acceptance gate**

- Every PRD user story is implemented or explicitly proven out of scope.
- Full suites pass with R WARN 0 and no unhandled browser errors.
- No user-data network transmission is observed.
- Other analyses have no behavior regression.
- The final code review has no unresolved P1/P2 findings.

**Commit boundary:** `test: verify guided Kaplan-Meier workflow`

## Implementation order and stopping rule

Implement one work package per fresh `/implement` session, using TDD slices and reviewing the diff before committing. WP3 and WP4 are the only packages that may be reordered. Do not reopen product interviews during implementation unless a discovered constraint contradicts the PRD and would materially change user-visible behavior or statistical validity.

After WP7 passes, the Kaplan–Meier pilot is complete. Further Guided Analysis methods are separate projects, not extensions of this plan.

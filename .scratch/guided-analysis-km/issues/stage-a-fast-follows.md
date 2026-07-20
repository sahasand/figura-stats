# Stage A fast-follows (from per-task + final review, 2026-07-14)

Label: ready-for-agent. None are merge blockers; verdict was "Ready to merge" with these tracked.

- [ ] Cross-ANALYSIS paint: switching to a different analysis (e.g. Forest) mid-KM-run can still paint the KM result into the shared #preview (session.stage stays "example" when leaving KM). No mislabel risk; fold into Stage B WP6 stale-response work.
- [x] Status chip: guided-shell runs never call setStatus, chip stays on last busy state after demo runs. — FIXED in ef4a6fb (QA polish) along with figure-pane SVG containment and experiment-label styling.
- [ ] R/km.R: CI-ribbon NA filter checks only $lower — use !is.na(lower) & !is.na(upper).
- [ ] R/km.R: `ref` variable aliased (option value, then Cox reference label) — rename.
- [ ] R/km.R: landmark CI can render "NA%" for unsupported tail landmarks (unreachable in Stage A UI; guard before Stage B exposes landmark input).
- [ ] test-km.R: legend regex ">Group<|>group<|legend" loose; "censor marks" test doesn't assert a censor mark; multi-group landmark strata path untested in R (covered by pinned e2e only).
- [ ] a11y (WP6 batch): arrow-key roving tabindex on stage tabs; tabpanel tabindex="0"; aria-describedby linking experiment callouts to controls.
- [ ] Teaching-visual ALT text "Kaplan-Meier" hyphen → en dash to match copy.
- [ ] data-raw/km-demo-generator.R: add working-directory guard (repo-root-relative paths).
- [ ] session-state.test.mjs: assert input-object purity (no mutation) explicitly.
- [ ] e2e: understand test asserts only 2/5 headings; context-isolation test re-runs full demo path (suite time).

## From /design-review outside voice (2026-07-14, cross-file)
- [ ] Label association: file inputs + textareas across web/forms/*.js use <p> captions, not <label for> (consort 0/2, roc 0/1, table1 1/2). Mechanical a11y batch with the WP6 items.
- [ ] Unified error/render path: CSV parse errors (roc.js:22, correlation.js:24) write to #stats without .error class; two different "Rendering…" strings (app.js vs guided-analysis.js). One shared showError()/showRendering() helper.
- [ ] Privacy promise stated 3 ways ("never uploaded" / "never leaves this browser" / "read locally") — consolidate to one constant.
- [ ] a11y: KM analyze form — aria-describedby linking #km-event to its censored-hint and #km-render to #km-dropped-note.

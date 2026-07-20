# 02 — Cox analyze form loses the event value and reference levels on picker changes

Status: resolved
Type: task
Found: 2026-07-20, during the logistic-regression build (fixed in the logistic form, left unfixed in cox)

## Problem

`web/guided/cox/analyze-form.js` has two state bugs that the logistic analyze form (`web/guided/logistic/analyze-form.js`) fixed:

1. **Deselecting all covariates wipes the chosen event value.** The shared column picker (`web/lib/columnpicker.js`) nulls its *whole* role map when any role is unset, so the form's `roles` goes null and the event-value selection is lost along with it. The user has to re-pick the event after every empty-covariate moment.
2. **Reference-level edits reset on any picker change.** The per-categorical reference dropdowns are rebuilt from scratch whenever the picker fires, so a deliberately chosen reference level silently reverts to the default.

## Fix

Port the logistic form's approach: keep the event value and the reference-level map in form-owned state keyed by column name, and reconcile against the new role set on each picker change instead of rebuilding from zero. Cover with a JS unit test — and remember to append the new `*.test.mjs` to the `test:unit` chain in `package.json` (it is not a glob).

## Comments

- 2026-07-20 — Fixed in `5ac9bfe`. Both the event value and the reference-level map now
  live in per-parse closure state keyed by column name and are reconciled against the
  new role set (`retainedSelection` / `reconcileRefLevels`, both exported and unit-tested
  in `web/guided/cox/analyze-form.test.mjs`, appended to the `test:unit` chain).
  Submit still harvests from the live DOM, so an unmapped column's remembered level
  cannot reach the spec. Separately noted (NOT fixed): the dropped-row preview note in
  the Cox form counts a whitespace-only cell as missing, while `R/cox.R` treats only
  `""`/absent as missing — the note can over-state excluded rows. Worth its own issue.

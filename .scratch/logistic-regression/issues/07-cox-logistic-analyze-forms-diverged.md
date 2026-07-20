# 07 — The cox/logistic "near-clone" analyze forms have diverged in opposite directions

Status: ready-for-agent
Type: task
Found: 2026-07-20, during the whole-branch review of `fix/cox-shell-issues` (deferred: out of scope for that branch)

## Problem

`web/guided/cox/analyze-form.js` and `web/guided/logistic/analyze-form.js` were written as
deliberate near-clones (the same time/status-or-outcome + covariate multi-select +
per-categorical reference-level dropdown shape). Each has since gained a hardening the
other lacks, so the "clone" is now a clone in **neither** direction, and a maintainer who
reads one and assumes the other matches will be wrong twice.

### Cox has, logistic lacks: retained-selection reconciliation

`web/guided/cox/analyze-form.js:17-34` (added on `fix/cox-shell-issues`, issue 02):

```js
export function retainedSelection(remembered, available, fallback = "") {
  return available.includes(remembered) ? remembered : fallback;
}
export function reconcileRefLevels(remembered, covariates, levelsOf, defaultOf) { ... }
```

Logistic still does the weaker inline version, `web/guided/logistic/analyze-form.js:182-183`:

```js
s.value = chosenRefs[c] ?? mostFrequent(table, c);
if (!s.value) s.value = mostFrequent(table, c);   // stale level, no longer present
```

**This is a latent bug, not only an inconsistency.** `chosenRefs[c] ?? mostFrequent(...)`
assigns a remembered level without checking the rebuilt `<option>` list still offers it.
The `if (!s.value)` line is a partial rescue that only fires because assigning an absent
value to a `<select>` leaves `value === ""` — it does not fire when the remembered string
happens to match a **different** column's level after a remap, and it depends on DOM
assignment semantics rather than stating the rule. Cox's `retainedSelection` states the
rule explicitly and is unit-tested.

Failing scenario: map covariate `site` (levels `A`/`B`/`C`), pick reference `C`, then
change the covariate multi-select so `site` is replaced by a column that also has a level
named `C` but for which `C` is a poor/unintended reference. The remembered `"C"` is
silently reused for the new column. The fitted model is valid but is not the model the
user's visible dropdowns describe — a wrong reference level flips the direction of every
OR for that covariate.

### Logistic has, cox lacks: readiness + dropped-row helpers

`web/guided/logistic/analyze-form.js:22-53` exports `renderReadiness()` (Render gating with
a plain-language reason) and `countDroppedRows()` (a missing-cell count that matches R
exactly). Cox has neither: it computes its dropped-row count inline at
`web/guided/cox/analyze-form.js:200-201` — and gets it wrong, see **issue 06** — and has no
equivalent readiness message.

## Fix

Reconcile in both directions, ideally by lifting the shared pure logic into one module
(e.g. `web/guided/lib/` or an existing `web/lib/` home) that both forms import, with a
single unit-test file:

1. Move `retainedSelection`/`reconcileRefLevels` out of `cox/analyze-form.js` and make the
   logistic reference-level dropdown use them, replacing the `?? mostFrequent` +
   `if (!s.value)` pair.
2. Move `renderReadiness`/`countDroppedRows` out of `logistic/analyze-form.js` and make the
   Cox form use them (this closes issue 06 at the same time).

If a shared module is judged wrong for this codebase (the guided analyses are deliberately
duplicated elsewhere — see the header comment in `tests/e2e/logistic-guided.spec.js`), then
at minimum port each helper into the other form verbatim and add a comment in **both**
files naming the sibling, so the next divergence is visible.

## Test

- Unit: the logistic form must fall back to the default reference when the remembered level
  is not among the new column's levels (RED against the current `?? mostFrequent` line).
- Unit: the Cox form's dropped-row count must match R (see issue 06).
- Existing `cox/analyze-form.test.mjs` and `logistic/analyze-form.test.mjs` assertions must
  all still pass unchanged.

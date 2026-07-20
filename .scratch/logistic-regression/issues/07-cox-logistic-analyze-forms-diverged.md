# 07 — The cox/logistic "near-clone" analyze forms have diverged in opposite directions (consistency, not a bug)

Status: resolved
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

**Correction (2026-07-20): this is an inconsistency, not a latent bug.** An earlier
revision of this issue claimed the logistic version could silently reuse one column's
remembered level for a *different* column after a remap. That is not reachable, and the
scenario it described was wrong:

- `chosenRefs` is keyed by **column name** (`chosenRefs[s.dataset.cov] = s.value`,
  `web/guided/logistic/analyze-form.js:166`), not by position, so `chosenRefs[c]` can only
  ever hold a level previously chosen for column `c` itself.
- `chosenRefs` is declared inside the per-parse closure (`:163`), and the option list comes
  from `distinctValues(table, c)` on a `table` that is fixed for the life of that closure —
  so a given column's options are identical on every rebuild. A remembered value for `c` is
  therefore always still among `c`'s options.
- The `if (!s.value)` guard at `:183` is consequently near-dead defensive code rather than
  the load-bearing rescue described above.

Do **not** write a test asserting the cross-column scenario; it cannot be made to fail.

What is genuinely worth fixing here is narrower: logistic encodes the fallback rule
implicitly, in DOM assignment semantics (`select.value = <absent>` leaves `""`), where cox
now states it explicitly in `retainedSelection` and unit-tests it. The behavior is the same;
the robustness and the testability are not.

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

- Unit: if logistic adopts `retainedSelection`, assert it returns the fallback for a
  remembered level absent from the available list. Note this will **not** be RED against
  the current inline version — the behavior already matches; the gain is an explicit,
  tested rule rather than one implied by DOM assignment semantics. See the Correction above.
- Unit: the Cox form's dropped-row count must match R (see issue 06).
- Existing `cox/analyze-form.test.mjs` and `logistic/analyze-form.test.mjs` assertions must
  all still pass unchanged.

## Comments

Resolved on `main` via the shared-module route (option 1), not the copy-into-both fallback.

`web/lib/modelform.js` now holds all four helpers — `retainedSelection`,
`reconcileRefLevels` (from cox) and `renderReadiness`, `countDroppedRows` (from logistic) —
and both analyze forms import them. `renderReadiness` gained an options argument
(`outcomeRole`, `checkOverlap`, `messages`) so cox can express its own shape (a `status`
column rather than an `outcome`, and no outcome/covariate overlap rule) without a second
copy of the logic. Each form keeps a comment naming `web/lib/modelform.js` as the place to
change it.

Logistic also picked up `retainedSelection` for its event-value dropdown, replacing an
inline `Array.from(options).some(...)` scan — same behavior, one fewer hand-rolled rule.

Behavior is unchanged in both forms, deliberately. Two things that looked like changes are
not: cox's readiness check now also tests `roles.status`, which is a no-op because
`renderColumnPicker`'s `current()` returns `null` unless every non-optional role is set
(`web/lib/columnpicker.js:19-37`) and none of cox's roles are optional; and logistic's
reference-level fallback moved from DOM-assignment semantics to an explicit rule that the
issue's own Correction section already established was equivalent.

`web/lib/modelform.test.mjs` covers all four helpers (28 assertions, including that
reconciling does not mutate the caller's memo) and is wired into `test:unit`. The existing
`cox/analyze-form.test.mjs` and `logistic/analyze-form.test.mjs` pass with **every
assertion unchanged**; each form re-exports the helpers its own test imports.

Left undone, deliberately: cox still does not reject a status column that is also selected
as a covariate, where logistic rejects the analogous case. Closing that gap would change
behavior, which was out of scope here. Worth its own issue.

# 04 — `treatment_dummies`'s most-frequent-level tie-break is a code-point sort, not the spec's locale-aware rule

Status: needs-triage
Type: task
Location: **`stats-validation/issues/`, not `.scratch/<slug>/issues/`.** Same
deliberate deviation as issue 02 (see that file's own Location note and
`stats-validation/README.md` §"Where the issue files live"): `.scratch/` is
gitignored and Path B's helper modules are shared, published evidence.
Found: 2026-09-09, during the linear-regression final fix wave, while landing
`stats-validation/python/tests/test_linear.py`'s path-relativity fix.

## Problem

`stats-validation/python/validate/io.py`'s `treatment_dummies` (`io.py:62-76`)
falls back to the **most frequent remaining level** when the declared reference
is absent, and tie-breaks with:

```python
candidates = sorted(level for level in counts.index if counts[level] == max_count)
ref = candidates[0]
```

That `sorted()` is a plain Python code-point sort. Every reference-level spec in
this directory (`spec/linear-confounding.md` "Reference levels and the
fallback", and identically `spec/cox-adjusted.md` and
`spec/logistic-confounding.md`) instead pins **R's locale-aware collation**
for this tie-break, and gives the exact contrasting example:
`c("B","B","a","a")` resolves to `"a"` under R's `sort()`/`factor()` (the
`en_CA.UTF-8` build locale this repo's R runs under), where a code-point sort
would give `"B"` (`0x42 < 0x61`). `treatment_dummies`'s helper would pick `"B"`
for that same input — the wrong level, judged against the spec.

`stats-validation/python/validate/linear.py` does **not** carry this bug: its
own `_resolve_reference` (`linear.py:90-108`) resolves the reference level
itself, using a locale-aware `_collate_key`, and hands `treatment_dummies` an
already-decided reference — so linear regression's Path B output is correct
regardless of the helper's own tie-break. `validate/logistic.py`, by contrast,
calls `treatment_dummies(df[cov], ref_levels[cov])` directly
(`logistic.py:26,46`) with no such pre-resolution, so a logistic case whose
declared reference level is absent from the data (the fallback path) could hit
the helper's code-point tie-break directly.

## Impact

**No shipped case has mixed-case levels**, so this is currently invisible: every
case's categorical levels (`Standard care`/`New treatment`, `I`/`II`/`III`,
`Yes`/`No`, and so on) are same-case ASCII, where a code-point sort and a
locale-aware sort agree. This is a latent divergence, not a measured one — no
finding on record cites it.

## Suggested fix

Either give `treatment_dummies` the same locale-aware tie-break
`_resolve_reference`/`_collate_key` already implement in `linear.py` (and reuse
it from there, rather than a third implementation), or route every caller
through a pre-resolution step the way `linear.py` does. Whichever path is
taken, add a case (or an acceptance-test fixture, since no *shipped* case
should be retuned to mixed case) with mixed-case levels to catch a regression.

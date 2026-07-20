# 06 — Cox's "rows will be excluded" preview over-counts whitespace-only cells

Status: resolved
Type: task
Found: 2026-07-20, during the whole-branch review of `fix/cox-shell-issues` (deferred: out of scope for that branch)

## Problem

The Cox analyze form's dropped-row note and R's complete-case filter disagree about what
counts as missing.

`web/guided/cox/analyze-form.js:200-201`:

```js
const dropped = table.rows.filter((r) =>
  used.some((c) => r[c] == null || String(r[c]).trim() === "")).length;
```

`R/cox.R:61` (categorical covariates) nulls only the **exact** empty string:

```r
v <- .char_col(rows, cl); v[!is.na(v) & v == ""] <- NA
```

So a cell containing `" "` (a space, or a tab — common in hand-edited clinical exports) is:

- **JS**: `.trim() === ""` → counted as an excluded row;
- **R**: a real, non-missing categorical level, kept in the model and printed as its own
  row in the Table-3 output.

## Failing scenario

Upload a CSV whose `arm` column has 12 rows with a single-space value. The form says
"12 row(s) with missing values will be excluded." The rendered table reports n including
those 12 rows, and shows a third arm level rendered as blank-looking text. The user's
sanity check of the preview against the reported n fails, and the honest reading — "the
tool told me it dropped rows it did not drop" — undermines trust in the numbers.

(Note the whitespace level surviving into the model is arguably its own R-side wart, but
the tracked defect here is the JS/R **disagreement**: whatever R does, the preview must
say the same thing.)

## Fix

Use the already-solved version from the logistic form. `countDroppedRows` in
`web/guided/logistic/analyze-form.js:49-53` is an exported pure function that matches R
exactly and documents why:

```js
// "Missing" is exactly what R/logistic.R treats as missing: an absent cell or the
// empty string. A whitespace-only cell is NOT missing there — it stays a real
// categorical level ... so counting it here would over-state the preview.
export function countDroppedRows(table, columns) {
  if (columns.length === 0) return 0;
  return table.rows.filter((r) =>
    columns.some((c) => r[c] == null || String(r[c]) === "")).length;
}
```

Drop the `.trim()` from the Cox count. Prefer factoring this out so both forms call one
function rather than keeping two copies (see issue 07 — the two forms have diverged and
should be reconciled together).

## Test

`web/guided/cox/analyze-form.test.mjs` — a table with a whitespace-only cell in a mapped
column must count 0 dropped rows, while `""` and `null` count 1 each. Mirror the existing
logistic unit test for `countDroppedRows`.

## Comments

Fixed on `fix/cox-forest-and-preview`. The inline count in
`web/guided/cox/analyze-form.js` is now an exported pure `countDroppedRows(table,
columns)` that treats only an absent cell or the exact empty string as missing —
the same rule as `R/cox.R` — with a unit test mirroring the logistic one. The two
forms still hold their own copy of the helper by design; reconciling them is
issue 07.

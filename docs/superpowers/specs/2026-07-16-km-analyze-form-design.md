# KM Analyze-form upgrade — design

**Date:** 2026-07-16
**Status:** Approved
**Motivation:** KM's Analyze Your Data form predates `web/lib` and is the app's worst
upload workflow: it demands literal `time,status,group` headers with 0/1 status, has
no CSV help, no example download, and no progressive disclosure. Summary and Group
comparison already have the better pattern. The clincher: KM's own demo dataset
(`participant_id, followup_months, status("Death"/"Censored"), group`) would be
rejected by the current form — an example-CSV download is only honest if the form
can accept it.

## Decisions (made with the user)

1. **Event coding — event-value picker.** After mapping a status column, a dropdown
   asks "Which value of <column> means the event occurred?" listing the column's
   distinct values; every other value counts as censored. The form converts to 0/1
   client-side. No silent auto-detection (consequential scientific choices are
   confirmed, not inferred); no strict-0/1 requirement (that is the friction being
   removed).

## Components

### 1. Form — `web/guided/km/analyze-form.js` (new)

Mirrors `web/guided/groupcompare/analyze-form.js`:

- Heading + privacy line ("read locally, never uploaded").
- `<details class="csv-help">` "What your CSV should look like": one row per
  participant; a numeric follow-up time column in consistent units; a status column
  where one value marks the event (any coding — words or numbers); a column naming
  each participant's group; leave cells empty when missing.
- Example-CSV download link: `toCsv(KM_DEMO.rows, KM_DEMO.columns)` as a client-side
  Blob, `download="example-survival.csv"` — the synthetic demo dataset, uploadable
  as-is into this form.
- File input; config `<div>` hidden until a parse succeeds; parse failure re-hides
  config, clears state, and shows the styled `#stats` error (same as other forms).
- Config content, in order:
  1. `renderColumnPicker` with roles: Follow-up time (`numeric`), Event status
     (`any`), Group (`categorical+`).
  2. Event-value picker: a labeled `<select>` populated with the mapped status
     column's distinct non-blank values, with the hint "All other values count as
     censored." Repopulates when the status role changes; Render stays disabled
     until both roles and an event value are chosen.
  3. Existing option controls, unchanged semantics: Time axis label (text input,
     default "Months") and Journal style (generic/NEJM/JAMA select).
  4. Render button + a passive note "n row(s) with missing values excluded" when
     the builder dropped any (recomputed per render click).

### 2. Spec builder — `web/guided/km/spec.js` (new, pure, unit-tested)

`buildKmSpec(table, roles, eventValue, options)` returns
`{ spec, dropped }`:

- Rows project to `{time: Number(cell), status: cell === eventValue ? 1 : 0,
  group: String(cell)}` using the mapped columns.
- Rows with a blank/missing value in any mapped column are dropped; `dropped` is
  the count (shown by the form).
- `spec` is the exact shape `fig_km` already accepts — **no R statistical change** —
  with `options`: `time_label`, `theme`, `source_filename`, and new
  `source_roles: { time: <col>, status: <col>, group: <col>, event: <value> }`.
- Only mapped columns cross to the worker (no-egress projection, like the other
  builders).

### 3. R-script compatibility — `R/km.R` `.km_script`

The generated script's prep currently assumes the user's CSV has literal
`time/status/group` columns. With mapping that is false. Fix:

- When `spec$options$source_roles` is present, the prep section becomes
  `dat <- data.frame(time = as.numeric(df[["<time-col>"]]), status =
  as.integer(df[["<status-col>"]] == "<event-value>"), group =
  as.character(df[["<group-col>"]]), stringsAsFactors = FALSE)` with all names and
  the event value quote-escaped, plus a comment naming the event coding.
- Absent `source_roles` (demo runs, embedded data — which is already in
  time/status/group shape): current fixed prep, unchanged.
- `fig_km`'s statistics and outputs are untouched.

### 4. Retirement and migration

- Delete `web/forms/km.js` (`parseKmCsv`, `renderKmForm`) and
  `web/forms/km.test.mjs`.
- `web/guided/guided-analysis.js` imports the new form as `renderAnalyzeForm`.
- `package.json` `test:unit` list: remove `web/forms/km.test.mjs`, add
  `web/guided/km/spec.test.mjs`.
- E2E fixture `tests/e2e/fixtures/km.csv` gains realistic headers
  (`followup_months,status,group` with `Death`/`Censored` coding); the km-guided
  analyze test performs the mapping + event-value steps, proving the new workflow
  end to end.

## Testing

- **JS unit (`web/guided/km/spec.test.mjs`):** event coding (word and numeric
  encodings), missing-row drops + count, no-egress projection, `source_roles` and
  `source_filename` passthrough.
- **R (`tests/testthat/test-km.R`):** `.km_script` with `source_roles` — script
  parses; prep references the original column names and event value. Without —
  current prep asserted unchanged.
- **E2E (`tests/e2e/km-guided.spec.js`):** upload realistic CSV → map roles → pick
  event value → render; example-CSV link has `blob:` href and
  `download="example-survival.csv"`.

## Non-goals

- Single-arm KM (group stays required, as today).
- Exposing landmarks/horizon/reference in the analyze form.
- Any change to `fig_km` statistics, demo behavior, or the Understand stage.

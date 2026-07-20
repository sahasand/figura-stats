// web/lib/modelform.js
// Pure decision logic shared by the regression analyze forms (Cox and logistic,
// web/guided/{cox,logistic}/analyze-form.js). Both forms have the same shape —
// an outcome column plus a user-confirmed event value, a covariate multi-select,
// and one reference-level dropdown per categorical covariate — so the rules that
// carry a real decision live here once instead of drifting apart in two files.
// Unit-tested in modelform.test.mjs; the DOM wiring stays in each form.

// A remembered dropdown value carried across an options rebuild: kept only when
// the rebuilt list still offers it, otherwise the fallback. Deselecting every
// covariate nulls the picker's whole role map (see web/lib/columnpicker.js),
// which momentarily clears the outcome column — the chosen event must survive it.
export function retainedSelection(remembered, available, fallback = "") {
  return available.includes(remembered) ? remembered : fallback;
}

// Reference levels for exactly the categorical covariates currently mapped,
// reconciled against what the user already chose (keyed by column name) rather
// than rebuilt from zero. `levelsOf(col)` returns null for a numeric covariate
// (per-unit effect, no reference). A remembered level the column no longer
// offers falls back to `defaultOf(col)`; a covariate no longer mapped is dropped.
export function reconcileRefLevels(remembered, covariates, levelsOf, defaultOf) {
  const out = {};
  for (const c of covariates) {
    const levels = levelsOf(c);
    if (!levels) continue;
    out[c] = retainedSelection(remembered[c], levels, defaultOf(c));
  }
  return out;
}

// Default (logistic) wording for the readiness reasons. A form that names its
// outcome differently passes its own `messages`.
export const READINESS_MESSAGES = {
  roles: "Choose an outcome column and at least one covariate to continue.",
  covariates: "Choose at least one covariate to adjust for.",
  overlap: "The outcome column cannot also be used as a covariate.",
  eventValue: "Choose which outcome value means the event occurred.",
};

// Whether Render may fire, plus a plain-language reason when it may not.
// `outcomeRole` names the role key holding the outcome column; `checkOverlap`
// rejects an outcome that is also selected as a covariate.
export function renderReadiness({ roles, eventValue },
  { outcomeRole = "outcome", checkOverlap = true, messages = {} } = {}) {
  const m = { ...READINESS_MESSAGES, ...messages };
  // The column picker collapses its whole role map to null when any role is
  // unset, so "no roles yet" can mean either half is missing — say both.
  if (!roles || !roles[outcomeRole]) return { ready: false, reason: m.roles };
  const covs = roles.covariates || [];
  if (covs.length === 0) return { ready: false, reason: m.covariates };
  if (checkOverlap && covs.includes(roles[outcomeRole])) {
    return { ready: false, reason: m.overlap };
  }
  if (!eventValue) return { ready: false, reason: m.eventValue };
  return { ready: true, reason: "" };
}

// Rows the model will drop, because a mapped column is missing (complete cases).
// "Missing" is exactly what R/cox.R and R/logistic.R treat as missing: an absent
// cell or the empty string. A whitespace-only cell is NOT missing there — it
// stays a real categorical level (and makes the column read as categorical), so
// counting it here would over-state the preview.
export function countDroppedRows(table, columns) {
  if (columns.length === 0) return 0;
  return table.rows.filter((r) =>
    columns.some((c) => r[c] == null || String(r[c]) === "")).length;
}

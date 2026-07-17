// Pure spec assembly for Cox regression. Only the mapped columns cross to the
// worker (no-egress); status stays a raw string (R recodes it from event_value,
// as KM does). source_roles lets the .R script read the user's real column names.
export function buildCoxSpec(table, roles, eventValue, refLevels, options) {
  const used = [roles.time, roles.status, ...roles.covariates];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "cox",
    data,
    roles: { time: roles.time, status: roles.status,
             covariates: roles.covariates.slice() },
    options: {
      event_value: String(eventValue),
      ref_levels: refLevels || {},
      source_filename: options.source_filename ?? null,
      source_roles: { time: roles.time, status: roles.status,
                      covariates: roles.covariates.slice(),
                      event: String(eventValue) },
    },
  };
}

// Distinct non-blank values, first-appearance order (feeds the event picker
// and each categorical covariate's reference-level dropdown).
export function distinctValues(table, col) {
  const seen = [];
  for (const r of table.rows) {
    const v = r[col];
    if (v == null || String(v).trim() === "") continue;
    const s = String(v);
    if (!seen.includes(s)) seen.push(s);
  }
  return seen;
}

// Most frequent non-blank value of a column (default reference level).
export function mostFrequent(table, col) {
  const counts = new Map();
  for (const r of table.rows) {
    const v = r[col];
    if (v == null || String(v).trim() === "") continue;
    const s = String(v);
    counts.set(s, (counts.get(s) || 0) + 1);
  }
  let best = null, n = -1;
  for (const [k, c] of counts) if (c > n) { best = k; n = c; }
  return best;
}

// Pure spec assembly for Kaplan–Meier. Rows are projected to the mapped
// time/status/group columns only (no other column crosses to the worker),
// and status is recoded 0/1 from the user-confirmed event value — the spec
// that leaves here is exactly the shape fig_km has always accepted.
export function buildKmSpec(table, roles, eventValue, options) {
  const blank = (v) => v == null || String(v).trim() === "";
  const data = [];
  let dropped = 0;
  for (const r of table.rows) {
    const t = r[roles.time], s = r[roles.status], g = r[roles.group];
    if (blank(t) || blank(s) || blank(g)) { dropped++; continue; }
    data.push({ time: Number(t),
                status: String(s) === String(eventValue) ? 1 : 0,
                group: String(g) });
  }
  return { dropped, spec: {
    figure: "km",
    data,
    options: {
      time_label: options.time_label,
      theme: options.theme,
      source_filename: options.source_filename ?? null,
      // Carried for the downloadable R script: lets .km_script write prep
      // that reads the user's REAL column names and event coding.
      source_roles: { time: roles.time, status: roles.status,
                      group: roles.group, event: String(eventValue) },
    },
  } };
}

// Distinct non-blank values of one column, first-appearance order — feeds
// the event-value picker.
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

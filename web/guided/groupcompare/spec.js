// Pure spec assembly for group comparison. Rows are projected to the group +
// outcome columns only, so no other column crosses to the worker (no-egress).
export function buildGroupCompareSpec(table, roles, options) {
  const used = [roles.group, roles.outcome];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "groupcompare",
    data,
    roles: { group: roles.group, outcome: roles.outcome },
    options: { plot: options.plot, test: options.test },
  };
}

// Pure spec assembly for linear regression. Only mapped columns cross to the
// worker (no-egress); the outcome stays a raw string (R coerces it and errors
// readably if it is not numeric). No event value: the outcome is continuous.
// source_roles lets the .R script read the user's real headers.
import { distinctValues, mostFrequent } from "../logistic/spec.js";
export { distinctValues, mostFrequent };

export function buildLinearSpec(table, roles, refLevels, increments, options) {
  const used = [roles.outcome, ...roles.covariates];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  return {
    figure: "linear",
    data,
    roles: { outcome: roles.outcome, covariates: roles.covariates.slice() },
    options: {
      ref_levels: refLevels || {},
      increments: increments || {},
      source_filename: options.source_filename ?? null,
      source_roles: { outcome: roles.outcome, covariates: roles.covariates.slice() },
    },
  };
}

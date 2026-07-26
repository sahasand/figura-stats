// Raw CSV -> Figura spec, using the SHIPPED parser and spec builders. Nothing
// here re-implements app behaviour; if a builder changes, this changes with it.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { parseCsv } from "../../web/lib/csv.js";
import { buildLogisticSpec } from "../../web/guided/logistic/spec.js";
import { buildCoxSpec } from "../../web/guided/cox/spec.js";

const BUILDERS = {
  logistic: (table, c) =>
    buildLogisticSpec(
      table,
      { outcome: c.roles.outcome, covariates: c.roles.covariates },
      c.options.event_value,
      c.options.ref_levels || {},
      c.options.increments || {},
      { source_filename: "data.csv" }
    ),
  cox: (table, c) =>
    buildCoxSpec(
      table,
      { time: c.roles.time, status: c.roles.status,
        covariates: c.roles.covariates },
      c.options.event_value,
      c.options.ref_levels || {},
      { source_filename: "data.csv" }
    ),
};

export async function buildSpecForCase(caseDir) {
  const c = JSON.parse(
    await readFile(path.join(caseDir, "case.json"), "utf8")
  );
  const csv = await readFile(path.join(caseDir, "data.csv"), "utf8");
  const table = parseCsv(csv);
  const build = BUILDERS[c.figure];
  if (!build) throw new Error(`No spec builder registered for: ${c.figure}`);
  return build(table, c);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const caseDir = process.argv[2];
  if (!caseDir) {
    console.error("usage: node build-spec.mjs <case-dir>");
    process.exit(2);
  }
  // Writes to stdout only; piping this into results/<id>.spec.json is deferred
  // to the Makefile task that wires the harness into the run pipeline.
  process.stdout.write(JSON.stringify(await buildSpecForCase(caseDir)));
}

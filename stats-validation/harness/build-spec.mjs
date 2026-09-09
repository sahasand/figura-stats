// Raw CSV -> Figura spec, using the SHIPPED parser and spec builders. Nothing
// here re-implements app behaviour; if a builder changes, this changes with it.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { parseCsv } from "../../web/lib/csv.js";
import { buildLogisticSpec } from "../../web/guided/logistic/spec.js";
import { buildLinearSpec } from "../../web/guided/linear/spec.js";
import { buildCoxSpec } from "../../web/guided/cox/spec.js";
import { buildKmSpec } from "../../web/guided/km/spec.js";
import { buildGroupCompareSpec } from "../../web/guided/groupcompare/spec.js";
import { buildSummarySpec } from "../../web/guided/summary/analyze-form.js";

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
  // linear has no event value: buildLinearSpec(table, roles, refLevels, increments, options).
  linear: (table, c) =>
    buildLinearSpec(
      table,
      { outcome: c.roles.outcome, covariates: c.roles.covariates },
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
  // buildKmSpec's real shape differs from buildLogisticSpec/buildCoxSpec: it
  // returns { dropped, spec }, not the flat spec itself (KM recodes status to
  // 0/1 and pre-drops blank time/status/group rows client-side, so the
  // builder reports how many it dropped alongside the spec it built). Only
  // `.spec` is what render_figure()/run-figura.R need.
  km: (table, c) =>
    buildKmSpec(
      table,
      { time: c.roles.time, status: c.roles.status, group: c.roles.group },
      c.options.event_value,
      { time_label: c.options.time_label, theme: c.options.theme,
        source_filename: "data.csv" }
    ).spec,
  // buildGroupCompareSpec(table, roles, options) — verified against
  // web/guided/groupcompare/spec.js's real 3-argument export signature (NOT
  // logistic/cox/km's event-value + ref-levels shape: group comparison has no
  // event value, no reference level, and no client-side recoding at all). It
  // returns the FLAT spec, like logistic/cox and unlike km. `plot` and `test`
  // are the two select values the real analyze form submits (defaults "box" /
  // "auto"); they are passed through from case.json so a case can pin the
  // parametric/non-parametric override instead of relying on the R-side
  // `%||% "auto"` fallback.
  groupcompare: (table, c) =>
    buildGroupCompareSpec(
      table,
      { group: c.roles.group, outcome: c.roles.outcome },
      { plot: c.options.plot, test: c.options.test,
        source_filename: "data.csv" }
    ),
  // Summary is the one analysis whose spec builder does NOT live in a
  // `spec.js` beside the guided config: `buildSummarySpec` is exported from
  // web/guided/summary/analyze-form.js (verified — there is no
  // web/guided/summary/spec.js at all; summary's demo path uses a separate
  // `buildSummaryDemoSpec` in demo.js, which embeds the frozen demo rows and
  // is NOT what an upload goes through). Its real signature is
  // `buildSummarySpec(table, { groupBy, showPlots, showQq, selected,
  // sourceFilename })` — ONE options object, no positional event value or
  // reference levels, and it returns the FLAT spec like logistic/cox/gc.
  //
  // `selected` is the user's variable checklist, so the case declares it as
  // roles.continuous + roles.categorical. The builder does NOT trust those
  // labels: it re-derives continuous-vs-categorical itself via
  // `classifyColumns` (numeric with > 5 distinct values -> continuous), which
  // is exactly the shipped behaviour under test. The case's own split is the
  // comparator's EXPECTATION, checked against the displayed rows — so a
  // reclassification in the app surfaces as a finding instead of being
  // absorbed here.
  summary: (table, c) =>
    buildSummarySpec(table, {
      groupBy: c.roles.group,
      showPlots: !!c.options.show_plots,
      showQq: !!c.options.show_qq,
      selected: [...(c.roles.continuous || []), ...(c.roles.categorical || [])],
      sourceFilename: "data.csv",
    }),
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

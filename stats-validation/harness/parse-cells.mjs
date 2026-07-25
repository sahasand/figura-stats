// Parses the `text` field returned by fig_cox / fig_logistic (a TSV table,
// then a blank line, then a methods paragraph) into structured rows plus the
// methods text. This is a parser only — it makes no judgment about display
// formatting; the display formatter (mirroring R's sprintf rule) lives in the
// Python comparator added by a later task. This module's consumer is the webR
// e2e tier.
export function parseRatioTable(text) {
  const [tsv, ...rest] = text.split("\n\n");
  const lines = tsv.split("\n").filter((l) => l.trim() !== "");
  // No special-casing: split each row on tab and hand back the three cells
  // exactly as they came. A categorical covariate's header row (e.g. "arm
  // (reference: Standard care)") carries empty unadj/adj cells; its level
  // rows carry the level name only. Note: R/logistic.R's fig_logistic calls
  // trimws() on the term before writing the TSV, so — despite .logistic_rows
  // building an internal two-space indent for level rows — that indent does
  // NOT survive into `text` (it only ever reaches the HTML table's CSS
  // indent). `term` is still left untrimmed here rather than trimmed
  // defensively, so this parser makes no assumption about that either way and
  // stays faithful to whatever bytes actually arrive. unadj/adj are trimmed
  // only to normalize a missing cell (undefined, when a line has fewer than
  // 3 tab-separated fields) to "".
  const rows = lines.slice(1).map((l) => {
    const [term, unadj, adj] = l.split("\t");
    return { term, unadj: (unadj ?? "").trim(), adj: (adj ?? "").trim() };
  });
  return { rows, methods: rest.join("\n\n").trim() };
}

// Parse a CSV string into columns, row objects, and inferred per-column types.
// Statistics never happen here — this only shapes data for the R layer.
export function parseCsv(text) {
  if (!text || !text.trim()) throw new Error("The CSV file is empty.");
  const [head, ...lines] = text.trim().split(/\r?\n/);
  const columns = head.split(",").map((s) => s.trim());
  const seen = new Set();
  for (const c of columns) {
    if (seen.has(c)) throw new Error(`Duplicate column name: "${c}".`);
    seen.add(c);
  }
  const dataLines = lines.filter((l) => l.trim() !== "");
  if (dataLines.length === 0) throw new Error("The CSV has no data rows.");
  const rows = dataLines.map((l, i) => {
    const cells = l.split(",");
    if (cells.length < columns.length)
      throw new Error(`Row ${i + 1}: expected ${columns.length} columns, found ${cells.length}.`);
    const row = {};
    columns.forEach((c, j) => { row[c] = (cells[j] ?? "").trim(); });
    return row;
  });
  const types = {};
  for (const c of columns) {
    const isNum = rows.every((r) => {
      const v = r[c];
      return v === "" || (v !== "" && Number.isFinite(Number(v)));
    }) && rows.some((r) => r[c] !== "");
    types[c] = isNum ? "numeric" : "categorical";
  }
  return { columns, rows, types };
}

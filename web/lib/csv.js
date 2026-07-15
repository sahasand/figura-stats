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
    if (cells.length > columns.length)
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

// Serialize row objects back to a CSV string for the given columns — the
// inverse of parseCsv for the values it supports. parseCsv has no quoting
// rules, so any column name or value containing a comma, double quote, or
// line break is unrepresentable and throws rather than silently emitting a
// file the app's own parser cannot read. null/undefined become empty cells.
export function toCsv(rows, columns) {
  const cell = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    if (/[",\r\n]/.test(s))
      throw new Error(`Cannot write a CSV value containing a comma, quote, or line break: ${JSON.stringify(s)}.`);
    return s;
  };
  const lines = [columns.map(cell).join(",")];
  for (const r of rows) lines.push(columns.map((c) => cell(r[c])).join(","));
  return lines.join("\n") + "\n";
}

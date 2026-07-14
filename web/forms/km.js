function parseCsv(text) {
  const [head, ...lines] = text.trim().split(/\r?\n/);
  const cols = head.split(",").map((s) => s.trim());
  const idx = (name) => cols.indexOf(name);
  if (idx("time") < 0 || idx("status") < 0 || idx("group") < 0)
    throw new Error("CSV needs columns: time, status, group");
  const need = Math.max(idx("time"), idx("status"), idx("group")) + 1;
  const rows = lines.filter((l) => l.trim() !== "").map((l, i) => {
    const n = i + 1; // 1-based data row number, for user-facing messages
    const c = l.split(",");
    if (c.length < need)
      throw new Error(`Row ${n}: expected at least ${need} columns, found ${c.length}.`);
    const time = parseFloat(c[idx("time")]);
    const status = parseInt((c[idx("status")] || "").trim(), 10);
    const group = (c[idx("group")] || "").trim();
    if (!Number.isFinite(time)) throw new Error(`Row ${n}: 'time' is not a number.`);
    if (status !== 0 && status !== 1)
      throw new Error(`Row ${n}: 'status' must be 0 (censored) or 1 (event).`);
    if (group === "") throw new Error(`Row ${n}: 'group' is empty.`);
    return { time, status, group };
  });
  if (rows.length === 0) throw new Error("CSV has no data rows.");
  return rows;
}

export function renderKmForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Kaplan-Meier</h2>
    <p>Upload a CSV with columns <code>time, status, group</code> (status: 1=event, 0=censored).
       Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <label for="tlabel">Time axis label</label>
    <input id="tlabel" value="Months" />
    <label for="theme">Journal style</label>
    <select id="theme"><option value="generic">Generic</option>
    <option value="nejm">NEJM</option><option value="jama">JAMA</option></select>
    <button type="button" id="render" disabled>Render</button>`;
  let data = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files[0];
    const reader = new FileReader();
    reader.onload = () => {
      try { data = parseCsv(reader.result); btn.disabled = false; }
      catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(file);
  };
  btn.onclick = () => onSubmit({ figure: "km", data,
    options: { time_label: container.querySelector("#tlabel").value,
      theme: container.querySelector("#theme").value } });
}

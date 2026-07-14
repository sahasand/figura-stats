function parseCsv(text) {
  const [head, ...lines] = text.trim().split("\n");
  const cols = head.split(",").map((s) => s.trim());
  const idx = (name) => cols.indexOf(name);
  if (idx("time") < 0 || idx("status") < 0 || idx("group") < 0)
    throw new Error("CSV needs columns: time, status, group");
  return lines.filter(Boolean).map((l) => {
    const c = l.split(",");
    return { time: parseFloat(c[idx("time")]), status: parseInt(c[idx("status")], 10),
             group: c[idx("group")].trim() };
  });
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

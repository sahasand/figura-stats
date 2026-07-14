import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderCorrelationForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Correlation</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <div id="picker"></div>
    <label for="method">Method</label>
    <select id="method"><option value="pearson">Pearson</option><option value="spearman">Spearman</option></select>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        renderColumnPicker(container.querySelector("#picker"),
          [{ key: "x", label: "X (numeric)", type: "numeric" },
           { key: "y", label: "Y (numeric)", type: "numeric" }],
          table, (m) => { roles = m; btn.disabled = !m; });
      } catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "correlation", data: table.rows, roles,
    options: { method: container.querySelector("#method").value } });
}

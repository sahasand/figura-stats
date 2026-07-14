import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderRegressionForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Regression table (Table 2)</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <label for="model">Model</label>
    <select id="model">
      <option value="logistic">Logistic (odds ratios)</option>
      <option value="cox">Cox (hazard ratios)</option>
      <option value="linear">Linear (beta)</option></select>
    <div id="picker"></div>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  const model = container.querySelector("#model");
  const rebuild = () => {
    if (!table) return;
    const isCox = model.value === "cox";
    const rolesDef = isCox
      ? [{ key: "time", label: "Time (numeric)", type: "numeric" },
         { key: "status", label: "Status (0/1)", type: "numeric" },
         { key: "covariates", label: "Covariates", type: "any", multiple: true }]
      : [{ key: "outcome", label: "Outcome", type: "any" },
         { key: "covariates", label: "Covariates", type: "any", multiple: true }];
    renderColumnPicker(container.querySelector("#picker"), rolesDef, table,
      (m) => { roles = m; btn.disabled = !m; });
  };
  model.onchange = rebuild;
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try { table = parseCsv(reader.result); rebuild(); }
      catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "regression", data: table.rows, roles,
    options: { model: model.value } });
}

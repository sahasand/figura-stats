import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderRocForm(container, onSubmit) {
  container.innerHTML = `
    <h2>ROC / AUC</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <div id="picker"></div>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        renderColumnPicker(container.querySelector("#picker"),
          [{ key: "predictor", label: "Predictor (numeric)", type: "numeric" },
           { key: "outcome", label: "Outcome (2 levels)", type: "any" }],
          table, (m) => { roles = m; btn.disabled = !m; });
      } catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "roc", data: table.rows, roles, options: {} });
}

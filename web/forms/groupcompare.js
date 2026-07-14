import { parseCsv } from "../lib/csv.js";
import { renderColumnPicker } from "../lib/columnpicker.js";

export function renderGroupCompareForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Group comparison</h2>
    <p>Upload a CSV. Your file is read locally and never uploaded.</p>
    <input type="file" id="csv" accept=".csv" />
    <div id="picker"></div>
    <label for="plot">Plot</label>
    <select id="plot"><option value="box">Box</option><option value="violin">Violin</option></select>
    <label for="test">Test</label>
    <select id="test"><option value="parametric">Parametric (t-test / ANOVA)</option>
      <option value="nonparametric">Non-parametric (Mann-Whitney / Kruskal-Wallis)</option></select>
    <button type="button" id="render" disabled>Render</button>`;
  let table = null, roles = null;
  const btn = container.querySelector("#render");
  container.querySelector("#csv").onchange = (e) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        renderColumnPicker(container.querySelector("#picker"),
          [{ key: "value", label: "Value (numeric)", type: "numeric" },
           { key: "group", label: "Group", type: "categorical" }],
          table, (m) => { roles = m; btn.disabled = !m; });
      } catch (err) { document.getElementById("stats").textContent = "Error: " + err.message; }
    };
    reader.readAsText(e.target.files[0]);
  };
  btn.onclick = () => onSubmit({ figure: "groupcompare", data: table.rows, roles,
    options: { plot: container.querySelector("#plot").value,
               test: container.querySelector("#test").value } });
}

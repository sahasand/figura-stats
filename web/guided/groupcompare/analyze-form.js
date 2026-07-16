// web/guided/groupcompare/analyze-form.js
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildGroupCompareSpec } from "./spec.js";
import { GROUPCOMPARE_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(GROUPCOMPARE_DEMO.rows, GROUPCOMPARE_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderGroupCompareForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A column naming each participant's group or arm.</li>
        <li>An outcome column — a number (e.g. a measurement) or a category
          (e.g. yes/no).</li>
        <li>Write a yes/no outcome as words (<code>Yes</code>/<code>No</code>),
          not <code>0</code>/<code>1</code> — a 0/1 column is read as a number
          and compared with a t-test rather than a chi-square.</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-groups.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="gc-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#gc-config");
  let table = null, roles = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const fileName = file.name;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);
        // `btn` is created (but not yet appended) before renderColumnPicker
        // runs: renderColumnPicker invokes its onReady callback synchronously
        // — including once immediately, with the pre-selection `null` — so a
        // callback that referenced a later `const btn` would hit the
        // temporal-dead-zone and throw before the button ever existed.
        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "gc-render"; btn.textContent = "Render comparison";
        btn.disabled = true;
        renderColumnPicker(pick,
          [{ key: "group", label: "Groups", type: "categorical+" },
           { key: "outcome", label: "Outcome (number or category)", type: "any" }],
          table, (v) => { roles = v; btn.disabled = !v; }, doc);

        const mkSel = (id, label, choices) => {
          const l = doc.createElement("label"); l.textContent = label + " ";
          const s = doc.createElement("select"); s.id = id;
          for (const [val, txt] of choices) {
            const o = doc.createElement("option"); o.value = val; o.textContent = txt;
            s.appendChild(o);
          }
          l.appendChild(s); config.appendChild(l); return s;
        };
        const plotSel = mkSel("gc-plot", "Plot (numeric outcomes)",
          [["box", "Box"], ["violin", "Violin"]]);
        const testSel = mkSel("gc-test", "Test",
          [["auto", "Auto (by normality)"], ["parametric", "Parametric"],
           ["nonparametric", "Non-parametric"]]);

        btn.onclick = () => {
          if (!roles) return;
          onSubmit(buildGroupCompareSpec(table, roles,
            { plot: plotSel.value, test: testSel.value,
              source_filename: fileName }));
        };
        config.appendChild(btn);
        config.hidden = false;
      } catch (err) {
        table = null; config.hidden = true; config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}

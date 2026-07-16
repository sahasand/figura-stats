// web/guided/km/analyze-form.js
// Progressive-disclosure upload UI for KM, on the shared csv/columnpicker
// foundation. Pre-upload: heading + privacy line + CSV help + file input ONLY.
// The config (role mapping, event-value picker, options, Render) stays hidden
// until a parse succeeds; a parse failure re-hides it and clears state.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildKmSpec, distinctValues } from "./spec.js";
import { KM_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(KM_DEMO.rows, KM_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderKmAnalyzeForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A numeric follow-up time column, in consistent units (e.g. months).</li>
        <li>A status column where one value marks the event — any coding
          (<code>Death</code>/<code>Censored</code>, <code>1</code>/<code>0</code>, …);
          you confirm which value is the event below.</li>
        <li>A column naming each participant's group or arm.</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-survival.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="km-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#km-config");
  let table = null, roles = null, fileName = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        fileName = file.name;
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);

        // Event-value picker + Render are created BEFORE renderColumnPicker
        // runs: its onReady callback fires synchronously (including once
        // immediately with null), so everything it touches must exist.
        const eventLabel = doc.createElement("label");
        eventLabel.textContent =
          "Which value of the status column means the event occurred? ";
        const eventSel = doc.createElement("select");
        eventSel.id = "km-event";
        eventLabel.htmlFor = "km-event";
        const eventHint = doc.createElement("p");
        eventHint.className = "hint";
        eventHint.textContent = "All other values count as censored.";

        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "km-render";
        btn.textContent = "Render Kaplan–Meier curve";
        btn.disabled = true;
        const note = doc.createElement("p");
        note.id = "km-dropped-note"; note.className = "hint";

        let statusCol = null;
        const syncReady = () => { btn.disabled = !roles || !eventSel.value; };
        const fillEventOptions = () => {
          eventSel.innerHTML = "";
          const ph = doc.createElement("option");
          ph.value = ""; ph.textContent = "— choose —";
          eventSel.appendChild(ph);
          if (statusCol) for (const v of distinctValues(table, statusCol)) {
            const o = doc.createElement("option");
            o.value = v; o.textContent = v;
            eventSel.appendChild(o);
          }
          eventSel.disabled = !statusCol;
          syncReady();
        };
        renderColumnPicker(pick,
          [{ key: "time", label: "Follow-up time", type: "numeric" },
           { key: "status", label: "Event status", type: "any" },
           { key: "group", label: "Group / arm", type: "categorical+" }],
          table, (v) => {
            roles = v;
            const s = v ? v.status : null;
            if (s !== statusCol) { statusCol = s; fillEventOptions(); }
            else syncReady();
          }, doc);
        eventSel.onchange = syncReady;
        fillEventOptions();

        const mkText = (id, label, value) => {
          const l = doc.createElement("label"); l.textContent = label + " ";
          const inp = doc.createElement("input"); inp.id = id; inp.value = value;
          l.appendChild(inp); config.appendChild(l); return inp;
        };
        const mkSel = (id, label, choices) => {
          const l = doc.createElement("label"); l.textContent = label + " ";
          const s = doc.createElement("select"); s.id = id;
          for (const [val, txt] of choices) {
            const o = doc.createElement("option");
            o.value = val; o.textContent = txt;
            s.appendChild(o);
          }
          l.appendChild(s); config.appendChild(l); return s;
        };
        config.appendChild(eventLabel);
        eventLabel.appendChild(eventSel);
        config.appendChild(eventHint);
        const tlabel = mkText("tlabel", "Time axis label", "Months");
        const themeSel = mkSel("theme", "Journal style",
          [["generic", "Generic"], ["nejm", "NEJM"], ["jama", "JAMA"]]);

        btn.onclick = () => {
          if (!roles || !eventSel.value) return;
          const { spec, dropped } = buildKmSpec(table, roles, eventSel.value,
            { time_label: tlabel.value, theme: themeSel.value,
              source_filename: fileName });
          note.textContent = dropped > 0
            ? `${dropped} row(s) with missing values excluded.` : "";
          onSubmit(spec);
        };
        config.appendChild(btn);
        config.appendChild(note);
        config.hidden = false;
      } catch (err) {
        table = null; config.hidden = true; config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}

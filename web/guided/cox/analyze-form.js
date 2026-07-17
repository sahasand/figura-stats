// web/guided/cox/analyze-form.js
// Progressive-disclosure upload UI for Cox, on the shared csv/columnpicker
// foundation. The config (roles, event value, covariate reference levels,
// Render) stays hidden until a CSV parse succeeds; a parse failure re-hides it
// and clears state. Mirrors web/guided/km/analyze-form.js.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildCoxSpec, distinctValues, mostFrequent } from "./spec.js";
import { COX_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(COX_DEMO.rows, COX_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderCoxAnalyzeForm(container, onSubmit, doc = globalThis.document) {
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
        <li>One or more covariate columns to adjust for (numeric or categorical).</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-cox.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="cox-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#cox-config");
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

        // Event-value picker + reference area + Render are created BEFORE
        // renderColumnPicker runs: its onReady callback fires synchronously
        // (including once immediately with null), so everything it touches
        // must already exist.
        const eventLabel = doc.createElement("label");
        eventLabel.textContent =
          "Which value of the status column means the event occurred? ";
        const eventSel = doc.createElement("select"); eventSel.id = "cox-event";
        eventLabel.htmlFor = "cox-event";
        const eventHint = doc.createElement("p");
        eventHint.className = "hint";
        eventHint.textContent = "All other values count as censored.";

        // Reference-level area: one dropdown per categorical covariate.
        const refWrap = doc.createElement("div"); refWrap.id = "cox-refs";

        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "cox-render";
        btn.textContent = "Render Cox model"; btn.disabled = true;
        const note = doc.createElement("p");
        note.id = "cox-dropped-note"; note.className = "hint";

        let statusCol = null;
        const isNumericCol = (col) => table.types[col] === "numeric";
        const syncReady = () => {
          btn.disabled = !roles || !roles.covariates
            || roles.covariates.length === 0 || !eventSel.value;
        };
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
        const renderRefs = () => {
          refWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          for (const c of roles.covariates) {
            if (isNumericCol(c)) continue;   // numeric covariate -> per-unit HR, no reference
            const l = doc.createElement("label");
            l.textContent = `Reference level for ${c} `;
            const s = doc.createElement("select");
            s.id = "cox-ref-" + c; s.dataset.cov = c;
            for (const v of distinctValues(table, c)) {
              const o = doc.createElement("option");
              o.value = v; o.textContent = v;
              s.appendChild(o);
            }
            s.value = mostFrequent(table, c);
            l.appendChild(s); refWrap.appendChild(l);
          }
        };

        renderColumnPicker(pick,
          [{ key: "time", label: "Follow-up time", type: "numeric" },
           { key: "status", label: "Event status", type: "any" },
           { key: "covariates", label: "Covariates to adjust for", type: "any",
             multiple: true }],
          table, (v) => {
            roles = v;
            const s = v ? v.status : null;
            if (s !== statusCol) { statusCol = s; fillEventOptions(); }
            renderRefs();
            syncReady();
          }, doc);
        eventSel.onchange = syncReady;
        fillEventOptions();

        config.appendChild(eventLabel);
        eventLabel.appendChild(eventSel);
        config.appendChild(eventHint);
        config.appendChild(refWrap);

        btn.onclick = () => {
          if (!roles || !eventSel.value) return;
          const refLevels = {};
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => {
            refLevels[s.dataset.cov] = s.value;
          });
          const spec = buildCoxSpec(table, roles, eventSel.value, refLevels,
            { source_filename: fileName });
          const used = [roles.time, roles.status, ...roles.covariates];
          const dropped = table.rows.filter((r) =>
            used.some((c) => r[c] == null || String(r[c]).trim() === "")).length;
          note.textContent = dropped > 0
            ? `${dropped} row(s) with missing values will be excluded.` : "";
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

// web/guided/linear/analyze-form.js
// Progressive-disclosure upload UI for linear regression, on the shared
// csv/columnpicker foundation. Mirrors web/guided/logistic/analyze-form.js with
// the event-value picker REMOVED (the outcome is continuous) and the outcome
// dropdown filtered to numeric columns. Reference-level and increment controls
// are the same; the decision logic stays in web/lib/modelform.js.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildLinearSpec, distinctValues, mostFrequent } from "./spec.js";
import { LINEAR_DEMO } from "./demo-data.js";
import { retainedSelection, reconcileRefLevels, renderReadiness, countDroppedRows }
  from "../../lib/modelform.js";
import { normalizeIncrement } from "../logistic/analyze-form.js";
export { normalizeIncrement, countDroppedRows };

// --- pure decision logic (unit-tested in analyze-form.test.mjs) --------------

export function linearReadiness(roles) {
  return renderReadiness({ roles, eventValue: "" }, {
    requireEventValue: false,
    messages: { roles: "Choose a numeric outcome column and at least one covariate to continue." },
  });
}

// --- DOM wiring (exercised by the Playwright e2e test) ----------------------

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(LINEAR_DEMO.rows, LINEAR_DEMO.columns)], { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderLinearAnalyzeForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A numeric outcome column (days, mmHg, a score, …).</li>
        <li>One or more covariate columns to adjust for (numeric or categorical).</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-linear.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="linear-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#linear-config");
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
        roles = null;
        doc.getElementById("stats").classList.remove("error");
        config.innerHTML = "";
        const pick = doc.createElement("div"); config.appendChild(pick);

        const refWrap = doc.createElement("div"); refWrap.id = "linear-refs";
        const incrWrap = doc.createElement("div"); incrWrap.id = "linear-increments";
        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "linear-render";
        btn.textContent = "Render linear model"; btn.disabled = true;
        const readyHint = doc.createElement("p");
        readyHint.id = "linear-ready-hint"; readyHint.className = "hint";
        readyHint.setAttribute("role", "status");
        const note = doc.createElement("p");
        note.id = "linear-dropped-note"; note.className = "hint";

        const isNumericCol = (col) => table.types[col] === "numeric";
        const syncReady = () => {
          const { ready, reason } = linearReadiness(roles);
          btn.disabled = !ready;
          readyHint.textContent = reason;
        };
        const chosenRefs = {}, chosenIncrs = {};
        const renderRefs = () => {
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => { chosenRefs[s.dataset.cov] = s.value; });
          refWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          const levels = {};
          const levelsOf = (c) => {
            if (isNumericCol(c)) return null;
            if (!levels[c]) levels[c] = distinctValues(table, c);
            return levels[c];
          };
          const refs = reconcileRefLevels(chosenRefs, roles.covariates, levelsOf,
            (c) => mostFrequent(table, c));
          for (const c of roles.covariates) {
            if (isNumericCol(c)) continue;
            const l = doc.createElement("label");
            l.textContent = `Reference level for ${c} `;
            const s = doc.createElement("select");
            s.id = "linear-ref-" + c; s.dataset.cov = c;
            l.htmlFor = s.id;
            for (const v of levelsOf(c)) {
              const o = doc.createElement("option");
              o.value = v; o.textContent = v;
              s.appendChild(o);
            }
            s.value = refs[c];
            l.appendChild(s); refWrap.appendChild(l);
          }
        };
        const renderIncrements = () => {
          incrWrap.querySelectorAll("input[data-cov]").forEach((i) => { chosenIncrs[i.dataset.cov] = i.value; });
          incrWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          for (const c of roles.covariates) {
            if (!isNumericCol(c)) continue;
            const l = doc.createElement("label");
            l.textContent = `Report ${c} per (increment) `;
            const inp = doc.createElement("input");
            inp.type = "number"; inp.min = "0"; inp.step = "any";
            inp.value = chosenIncrs[c] ?? "1";
            inp.id = "linear-incr-" + c; inp.dataset.cov = c;
            l.htmlFor = inp.id;
            l.appendChild(inp); incrWrap.appendChild(l);
          }
        };

        renderColumnPicker(pick,
          [{ key: "outcome", label: "Numeric outcome", type: "numeric" },
           { key: "covariates", label: "Covariates to adjust for", type: "any", multiple: true }],
          table, (v) => { roles = v; renderRefs(); renderIncrements(); syncReady(); }, doc);

        config.appendChild(refWrap);
        config.appendChild(incrWrap);
        btn.onclick = () => {
          if (!linearReadiness(roles).ready) return;
          const refLevels = {};
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => { refLevels[s.dataset.cov] = s.value; });
          const increments = {};
          incrWrap.querySelectorAll("input[data-cov]").forEach((inp) => {
            increments[inp.dataset.cov] = normalizeIncrement(inp.value);
          });
          const spec = buildLinearSpec(table, roles, refLevels, increments, { source_filename: fileName });
          const dropped = countDroppedRows(table, [roles.outcome, ...roles.covariates]);
          note.textContent = dropped > 0 ? `${dropped} row(s) with missing values will be excluded.` : "";
          onSubmit(spec);
        };
        config.appendChild(btn);
        config.appendChild(readyHint);
        config.appendChild(note);
        syncReady();
        config.hidden = false;
      } catch (err) {
        table = null; roles = null;
        config.hidden = true; config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}

// web/guided/logistic/analyze-form.js
// Progressive-disclosure upload UI for logistic regression, on the shared
// csv/columnpicker foundation. The config (roles, event value, reference levels,
// per-numeric increments, Render) stays hidden until a CSV parse succeeds; a
// parse failure re-hides it and clears state. Mirrors web/guided/cox/analyze-form.js.
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { buildLogisticSpec, distinctValues, mostFrequent } from "./spec.js";
import { LOGISTIC_DEMO } from "./demo-data.js";

// --- pure decision logic (unit-tested in analyze-form.test.mjs) --------------

// Mirror of .logistic_increment in R/logistic.R: anything that is not a finite
// positive number is 1. Normalizing here means the spec never carries a value
// the R side would silently swallow.
export function normalizeIncrement(value) {
  const k = Number(value);
  return Number.isFinite(k) && k > 0 ? k : 1;
}

// Whether Render may fire, plus a plain-language reason when it may not.
export function renderReadiness({ roles, eventValue }) {
  // The column picker collapses its whole role map to null when any role is
  // unset, so "no roles yet" can mean either half is missing — say both.
  if (!roles || !roles.outcome) {
    return { ready: false,
      reason: "Choose an outcome column and at least one covariate to continue." };
  }
  const covs = roles.covariates || [];
  if (covs.length === 0) {
    return { ready: false, reason: "Choose at least one covariate to adjust for." };
  }
  if (covs.includes(roles.outcome)) {
    return { ready: false,
      reason: "The outcome column cannot also be used as a covariate." };
  }
  if (!eventValue) {
    return { ready: false,
      reason: "Choose which outcome value means the event occurred." };
  }
  return { ready: true, reason: "" };
}

// Rows the model will drop, because a mapped column is missing (complete cases).
// "Missing" is exactly what R/logistic.R treats as missing: an absent cell or the
// empty string. A whitespace-only cell is NOT missing there — it stays a real
// categorical level (and makes .logistic_is_numeric read the column as
// categorical), so counting it here would over-state the preview.
export function countDroppedRows(table, columns) {
  if (columns.length === 0) return 0;
  return table.rows.filter((r) =>
    columns.some((c) => r[c] == null || String(r[c]) === "")).length;
}

// --- DOM wiring (exercised by the Playwright e2e test) ----------------------

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(LOGISTIC_DEMO.rows, LOGISTIC_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

export function renderLogisticAnalyzeForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per participant, one column per variable.</li>
        <li>A binary outcome column — any coding
          (<code>Yes</code>/<code>No</code>, <code>1</code>/<code>0</code>, …);
          you confirm which value is the event below.</li>
        <li>One or more covariate columns to adjust for (numeric or categorical).</li>
        <li>Leave a cell empty when a value is missing.</li>
      </ul>
      <p><a id="example-csv" download="example-logistic.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="logistic-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#logistic-config");
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

        // Built BEFORE renderColumnPicker (its onReady fires synchronously,
        // including once with null), so everything it touches already exists.
        const eventLabel = doc.createElement("label");
        eventLabel.textContent =
          "Which value of the outcome column means the event occurred? ";
        const eventSel = doc.createElement("select"); eventSel.id = "logistic-event";
        eventLabel.htmlFor = "logistic-event";
        const eventHint = doc.createElement("p");
        eventHint.className = "hint";
        eventHint.textContent = "All other values count as non-events.";

        // One reference-level dropdown per categorical covariate; one increment
        // input per numeric covariate.
        const refWrap = doc.createElement("div"); refWrap.id = "logistic-refs";
        const incrWrap = doc.createElement("div"); incrWrap.id = "logistic-increments";

        const btn = doc.createElement("button");
        btn.type = "button"; btn.id = "logistic-render";
        btn.textContent = "Render logistic model"; btn.disabled = true;
        const readyHint = doc.createElement("p");
        readyHint.id = "logistic-ready-hint"; readyHint.className = "hint";
        readyHint.setAttribute("role", "status");
        const note = doc.createElement("p");
        note.id = "logistic-dropped-note"; note.className = "hint";

        let outcomeCol = null;
        // Remembered across option rebuilds: deselecting every covariate makes
        // the picker report a null role map, which momentarily clears the
        // outcome column — the user's event choice must survive that.
        let chosenEvent = "";
        const isNumericCol = (col) => table.types[col] === "numeric";
        const syncReady = () => {
          const { ready, reason } = renderReadiness({ roles, eventValue: eventSel.value });
          btn.disabled = !ready;
          readyHint.textContent = reason;
        };
        const fillEventOptions = () => {
          eventSel.innerHTML = "";
          const ph = doc.createElement("option");
          ph.value = ""; ph.textContent = "— choose —";
          eventSel.appendChild(ph);
          if (outcomeCol) for (const v of distinctValues(table, outcomeCol)) {
            const o = doc.createElement("option");
            o.value = v; o.textContent = v;
            eventSel.appendChild(o);
          }
          eventSel.value = Array.from(eventSel.options)
            .some((o) => o.value === chosenEvent && o.value !== "") ? chosenEvent : "";
          eventSel.disabled = !outcomeCol;
          syncReady();
        };
        // Both areas are rebuilt on every picker change, so a value the user
        // typed or picked is carried over whenever that covariate is still in.
        const chosenRefs = {}, chosenIncrs = {};
        const renderRefs = () => {
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => {
            chosenRefs[s.dataset.cov] = s.value;
          });
          refWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          for (const c of roles.covariates) {
            if (isNumericCol(c)) continue;   // numeric -> increment, not a reference
            const l = doc.createElement("label");
            l.textContent = `Reference level for ${c} `;
            const s = doc.createElement("select");
            s.id = "logistic-ref-" + c; s.dataset.cov = c;
            l.htmlFor = s.id;
            for (const v of distinctValues(table, c)) {
              const o = doc.createElement("option");
              o.value = v; o.textContent = v;
              s.appendChild(o);
            }
            s.value = chosenRefs[c] ?? mostFrequent(table, c);
            if (!s.value) s.value = mostFrequent(table, c);   // stale level, no longer present
            l.appendChild(s); refWrap.appendChild(l);
          }
        };
        const renderIncrements = () => {
          incrWrap.querySelectorAll("input[data-cov]").forEach((i) => {
            chosenIncrs[i.dataset.cov] = i.value;
          });
          incrWrap.innerHTML = "";
          if (!roles || !roles.covariates) return;
          for (const c of roles.covariates) {
            if (!isNumericCol(c)) continue;   // categorical -> reference, not an increment
            const l = doc.createElement("label");
            l.textContent = `Report ${c} per (increment) `;
            const inp = doc.createElement("input");
            inp.type = "number"; inp.min = "0"; inp.step = "any";
            inp.value = chosenIncrs[c] ?? "1";
            inp.id = "logistic-incr-" + c; inp.dataset.cov = c;
            l.htmlFor = inp.id;
            l.appendChild(inp); incrWrap.appendChild(l);
          }
        };

        renderColumnPicker(pick,
          [{ key: "outcome", label: "Binary outcome", type: "any" },
           { key: "covariates", label: "Covariates to adjust for", type: "any",
             multiple: true }],
          table, (v) => {
            roles = v;
            const o = v ? v.outcome : null;
            if (o !== outcomeCol) { outcomeCol = o; fillEventOptions(); }
            renderRefs(); renderIncrements();
            syncReady();
          }, doc);
        eventSel.onchange = () => { chosenEvent = eventSel.value; syncReady(); };
        fillEventOptions();

        config.appendChild(eventLabel);
        eventLabel.appendChild(eventSel);
        config.appendChild(eventHint);
        config.appendChild(refWrap);
        config.appendChild(incrWrap);

        btn.onclick = () => {
          if (!renderReadiness({ roles, eventValue: eventSel.value }).ready) return;
          const refLevels = {};
          refWrap.querySelectorAll("select[data-cov]").forEach((s) => {
            refLevels[s.dataset.cov] = s.value;
          });
          const increments = {};
          incrWrap.querySelectorAll("input[data-cov]").forEach((inp) => {
            increments[inp.dataset.cov] = normalizeIncrement(inp.value);
          });
          const spec = buildLogisticSpec(table, roles, eventSel.value, refLevels,
            increments, { source_filename: fileName });
          const dropped = countDroppedRows(table, [roles.outcome, ...roles.covariates]);
          note.textContent = dropped > 0
            ? `${dropped} row(s) with missing values will be excluded.` : "";
          onSubmit(spec);
        };
        config.appendChild(btn);
        config.appendChild(readyHint);
        config.appendChild(note);
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

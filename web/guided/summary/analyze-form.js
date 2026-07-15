import { parseCsv } from "../../lib/csv.js";
import { renderColumnPicker } from "../../lib/columnpicker.js";

// Pure: classify every column and flag ones that should start unticked.
//   kinds: numeric with <=5 distinct non-missing values -> "categorical"
//          (0/1-coded binaries), otherwise numeric -> "continuous".
//   flags: "id" when every non-missing value is unique AND values are integers
//          or strings (all-unique DECIMALS are legitimate measurements);
//          "many-levels" when a categorical has > 20 levels.
export function classifyColumns(table) {
  const kinds = {}, flags = {};
  for (const c of table.columns) {
    const vals = table.rows.map((r) => r[c]).filter((v) => v !== "" && v != null);
    const distinct = new Set(vals).size;
    const numeric = table.types[c] === "numeric";
    kinds[c] = numeric && distinct > 5 ? "continuous" : "categorical";
    const allInt = numeric && vals.every((v) => Number.isInteger(Number(v)));
    if (vals.length > 1 && distinct === vals.length && (!numeric || allInt)) {
      flags[c] = "id";
    } else if (kinds[c] === "categorical" && distinct > 20) {
      flags[c] = "many-levels";
    } else {
      flags[c] = null;
    }
  }
  return { kinds, flags };
}

// Pure: assemble the spec. Rows are projected to selected + group columns so
// unticked data never crosses to the worker.
export function buildSummarySpec(table, { groupBy, showPlots, showQq, selected }) {
  const { kinds } = classifyColumns(table);
  const vars = table.columns.filter((c) => c !== groupBy && selected.includes(c));
  const keep = groupBy ? [...vars, groupBy] : vars;
  const data = table.rows.map((r) =>
    Object.fromEntries(keep.map((c) => [c, r[c]])));
  return {
    figure: "summary",
    data,
    roles: { group: groupBy },
    options: {
      continuous: vars.filter((c) => kinds[c] === "continuous"),
      categorical: vars.filter((c) => kinds[c] !== "continuous"),
      labels: null, overrides: {},
      show_plots: !!showPlots,
      show_qq: !!showQq,
    },
  };
}

const FLAG_NOTES = { id: "looks like an ID — excluded",
                     "many-levels": "too many categories — excluded" };

// Progressive-disclosure upload UI. Pre-upload: heading + privacy line + file
// input ONLY. The config section (checklist, group picker, plot toggle, Render)
// exists but stays hidden until a parse succeeds; a parse failure re-hides it
// and clears state so a failed re-upload can never render the previous file.
// All dynamic UI is DOM-built — CSV-derived strings never touch innerHTML.
export function renderSummaryForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="summary-config" hidden></div>`;
  const config = container.querySelector("#summary-config");
  let table = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  function idFor(col) { return "var-" + col.replace(/[^A-Za-z0-9_-]/g, "_"); }

  function buildConfig() {
    config.innerHTML = "";
    const { kinds, flags } = classifyColumns(table);

    const varsLabel = doc.createElement("label");
    varsLabel.textContent = `Variables to include (${table.columns.length} columns found)`;
    config.appendChild(varsLabel);

    const list = doc.createElement("div");
    list.className = "var-list"; list.id = "summary-vars";
    const boxes = {};
    for (const c of table.columns) {
      const row = doc.createElement("div"); row.className = "var-row";
      const box = doc.createElement("input");
      box.type = "checkbox"; box.id = idFor(c); box.checked = flags[c] === null;
      const label = doc.createElement("label");
      label.htmlFor = box.id; label.className = "var-name"; label.textContent = c;
      const note = doc.createElement("span");
      note.id = box.id + "-note";
      note.className = flags[c] ? "var-note flag" : "var-note";
      note.textContent = flags[c] ? `${kinds[c]} · ${FLAG_NOTES[flags[c]]}` : kinds[c];
      box.setAttribute("aria-describedby", note.id);
      row.append(box, label, note);
      list.appendChild(row);
      boxes[c] = box;
    }
    config.appendChild(list);

    // Group picker: shared columnpicker with the new optional role. Only
    // categorical columns make sensible grouping variables.
    const groupWrap = doc.createElement("div");
    config.appendChild(groupWrap);
    let groupChoice = { group: null };
    renderColumnPicker(groupWrap,
      [{ key: "group", label: "Group by (optional)", type: "categorical", optional: true }],
      table, (v) => { groupChoice = v || { group: null }; }, doc);

    const plotsLabel = doc.createElement("label");
    const plots = doc.createElement("input");
    plots.type = "checkbox"; plots.id = "showplots"; plots.checked = true;
    plotsLabel.append(plots, doc.createTextNode(" Show distribution plots"));
    config.appendChild(plotsLabel);

    const qqLabel = doc.createElement("label");
    const qq = doc.createElement("input");
    qq.type = "checkbox"; qq.id = "showqq";
    qqLabel.append(qq, doc.createTextNode(" Show Q–Q normality plots"));
    config.appendChild(qqLabel);

    const btn = doc.createElement("button");
    btn.type = "button"; btn.id = "render"; btn.textContent = "Render summary table";
    btn.onclick = () => {
      const selected = table.columns.filter((c) => boxes[c].checked && c !== groupChoice.group);
      onSubmit(buildSummarySpec(table, {
        groupBy: groupChoice.group, showPlots: plots.checked, showQq: qq.checked, selected }));
    };
    config.appendChild(btn);
  }

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;                       // cancelled dialog: no-op
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        buildConfig();
        config.hidden = false;
        doc.getElementById("stats").classList.remove("error");
      } catch (err) {
        table = null;                        // never render a previous file's data
        config.hidden = true;
        config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}

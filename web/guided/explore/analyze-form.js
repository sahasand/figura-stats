// web/guided/explore/analyze-form.js
import { parseCsv, toCsv } from "../../lib/csv.js";
import { renderBuilderControls, buildExploreSpec, defaultOptions }
  from "./builder-controls.js";
import { debounce } from "../live-run.js";
import { EXPLORE_DEMO } from "./demo-data.js";

let exampleCsvUrl = null;
function getExampleCsvUrl() {
  if (!exampleCsvUrl) {
    const blob = new Blob([toCsv(EXPLORE_DEMO.rows, EXPLORE_DEMO.columns)],
      { type: "text/csv" });
    exampleCsvUrl = URL.createObjectURL(blob);
  }
  return exampleCsvUrl;
}

// Progressive disclosure like the Summary form: file input only, then the
// builder appears after a successful parse. Every control change re-renders,
// debounced; coalescing lives in the shell's runUser path (onSubmit).
export function renderExploreForm(container, onSubmit, doc = globalThis.document) {
  container.innerHTML = `
    <h2>Analyze your data</h2>
    <p>Your file is read locally in this browser and never uploaded.</p>
    <details class="csv-help">
      <summary>What your CSV should look like</summary>
      <ul>
        <li>One row per observation, one column per variable.</li>
        <li>The first row holds the column names.</li>
        <li>Leave a cell empty when a value is missing.</li>
        <li>For repeated measures, include an ID column and a time column.</li>
      </ul>
      <p><a id="example-csv" download="example-explore.csv" href="#">Download an example CSV</a>
        — the synthetic teaching dataset from the Example tab.</p>
    </details>
    <label for="csv">CSV file</label>
    <input type="file" id="csv" accept=".csv" />
    <div id="explore-config" hidden></div>`;
  container.querySelector("#example-csv").href = getExampleCsvUrl();
  const config = container.querySelector("#explore-config");
  let table = null;

  function showError(message) {
    const stats = doc.getElementById("stats");
    stats.textContent = "Error: " + message;
    stats.classList.add("error");
  }

  const submitDebounced = debounce((state) => {
    if (!table) return;                              // failed re-upload landed mid-debounce
    if (!state.roles.x) return;                      // incomplete mapping: wait
    const need_y = ["scatter", "line", "boxplot", "violin"]
      .includes(state.options.geom);
    if (need_y && !state.roles.y) return;
    onSubmit(buildExploreSpec(table, state.roles, state.options));
  }, 400);

  container.querySelector("#csv").onchange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        table = parseCsv(reader.result);
        config.hidden = false;
        doc.getElementById("stats").classList.remove("error");
        const state = { roles: {}, options: defaultOptions("scatter") };
        renderBuilderControls(config, table, state, submitDebounced, doc);
      } catch (err) {
        table = null;
        config.hidden = true;
        config.innerHTML = "";
        showError(err.message);
      }
    };
    reader.readAsText(file);
  };
}

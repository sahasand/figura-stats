export function renderTable1Form(container, onSubmit) {
  container.innerHTML = `
    <h2>Table 1</h2>
    <label for="groups">Group names (comma separated)</label>
    <input id="groups" value="Treatment, Placebo" class="input-wide" />
    <p>One row per line as: <code>Variable | val1 | val2</code></p>
    <textarea id="rows" rows="6" cols="50">Age, mean (SD) | 58 (11) | 57 (12)
Male, n (%) | 40 (53%) | 38 (51%)</textarea>
    <button type="button" id="render">Render</button>`;
  container.querySelector("#render").onclick = () => {
    const groups = container.querySelector("#groups").value.split(",").map((s) => s.trim());
    const rows = container.querySelector("#rows").value.split("\n")
      .map((l) => l.trim()).filter(Boolean).map((l) => {
        const parts = l.split("|").map((s) => s.trim());
        return { variable: parts[0], values: parts.slice(1) };
      });
    onSubmit({ figure: "table1", groups, rows });
  };
}

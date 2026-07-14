export function renderForestForm(container, onSubmit) {
  container.innerHTML = `
    <h2>Forest plot</h2>
    <label for="effect">Effect label</label>
    <input id="effect" value="Hazard Ratio" />
    <div id="rows"></div>
    <button type="button" id="addRow">Add row</button>
    <button type="button" id="render">Render</button>`;
  const rows = container.querySelector("#rows");
  function addRow() {
    const i = rows.children.length;
    const div = document.createElement("div");
    div.innerHTML = `
      <label for="lbl${i}">Label</label><input id="lbl${i}" class="lbl" />
      <label for="est${i}">Estimate</label><input id="est${i}" class="est" />
      <label for="lo${i}">Lower</label><input id="lo${i}" class="lo" />
      <label for="hi${i}">Upper</label><input id="hi${i}" class="hi" />`;
    rows.appendChild(div);
  }
  container.querySelector("#addRow").onclick = addRow;
  container.querySelector("#render").onclick = () => {
    const spec = { figure: "forest",
      options: { effect_label: container.querySelector("#effect").value, null_line: 1 },
      rows: [...rows.children]
        .map((d) => ({
          label: d.querySelector(".lbl").value,
          estimate: parseFloat(d.querySelector(".est").value),
          lower: parseFloat(d.querySelector(".lo").value),
          upper: parseFloat(d.querySelector(".hi").value)
        }))
        // Drop rows the user added but left blank, so a stray empty row does not
        // send NaN/null numerics that would fail the R-side length checks.
        .filter((r) => Number.isFinite(r.estimate)) };
    onSubmit(spec);
  };
  // Start with one row so "Add row" is optional; the picker shows a ready form.
  addRow();
}

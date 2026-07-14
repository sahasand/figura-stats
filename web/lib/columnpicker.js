// Render role->column dropdowns filtered by inferred column type.
// No statistics here; this only lets the user map CSV columns to analysis roles.
export function renderColumnPicker(container, roles, table, onReady, doc = globalThis.document) {
  container.innerHTML = "";
  const selects = {};
  const compatible = (role) =>
    table.columns.filter((c) => role.type === "any" || table.types[c] === role.type);

  const current = () => {
    const map = {};
    for (const role of roles) {
      const sel = selects[role.key];
      if (role.multiple) {
        const chosen = Array.from(sel.options).filter((o) => o.selected && o.value).map((o) => o.value);
        if (chosen.length === 0) return null;
        map[role.key] = chosen;
      } else {
        if (!sel.value) return null;
        map[role.key] = sel.value;
      }
    }
    return map;
  };

  for (const role of roles) {
    const label = doc.createElement("label");
    label.textContent = role.label + (role.multiple ? " (pick one or more)" : "");
    container.appendChild(label);
    const sel = doc.createElement("select");
    sel.multiple = !!role.multiple;
    if (!role.multiple) {
      const blank = doc.createElement("option");
      blank.value = ""; blank.textContent = "— choose —";
      sel.add ? sel.add(blank) : sel.appendChild(blank);
    }
    for (const col of compatible(role)) {
      const opt = doc.createElement("option");
      opt.value = col; opt.textContent = col;
      sel.add ? sel.add(opt) : sel.appendChild(opt);
    }
    sel.onchange = () => onReady(current());
    selects[role.key] = sel;
    container.appendChild(sel);
  }
  onReady(current());
  return { value: current };
}

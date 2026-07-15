// Render role->column dropdowns filtered by inferred column type.
// No statistics here; this only lets the user map CSV columns to analysis roles.
export function renderColumnPicker(container, roles, table, onReady, doc = globalThis.document) {
  container.innerHTML = "";
  const selects = {};
  // "categorical+" also admits numeric columns (0/1/2-coded groups are common
  // in clinical data), listed after true categoricals with a visible hint.
  // The option VALUE is always the bare column name.
  const compatible = (role) => {
    if (role.type === "any") return table.columns.map((c) => [c, c]);
    const match = table.columns.filter((c) => table.types[c] === role.type.replace("+", ""))
      .map((c) => [c, c]);
    if (!role.type.endsWith("+")) return match;
    const extra = table.columns.filter((c) => table.types[c] === "numeric")
      .map((c) => [c, c + " (as categories)"]);
    return [...match, ...extra];
  };

  const current = () => {
    const map = {};
    for (const role of roles) {
      const sel = selects[role.key];
      if (role.multiple) {
        const chosen = Array.from(sel.options).filter((o) => o.selected && o.value).map((o) => o.value);
        if (chosen.length === 0) return null;
        map[role.key] = chosen;
      } else {
        if (!sel.value) {
          if (!role.optional) return null;
          map[role.key] = null;
        } else {
          map[role.key] = sel.value;
        }
      }
    }
    return map;
  };

  for (const role of roles) {
    const label = doc.createElement("label");
    label.textContent = role.label + (role.multiple ? " (pick one or more)" : "");
    container.appendChild(label);
    const sel = doc.createElement("select");
    sel.id = "cp_" + role.key;
    label.htmlFor = sel.id;
    sel.multiple = !!role.multiple;
    if (!role.multiple) {
      const blank = doc.createElement("option");
      blank.value = ""; blank.textContent = role.optional ? "— none —" : "— choose —";
      sel.add ? sel.add(blank) : sel.appendChild(blank);
    }
    for (const [col, text] of compatible(role)) {
      const opt = doc.createElement("option");
      opt.value = col; opt.textContent = text;
      sel.add ? sel.add(opt) : sel.appendChild(opt);
    }
    sel.onchange = () => onReady(current());
    selects[role.key] = sel;
    container.appendChild(sel);
  }
  onReady(current());
  return { value: current };
}

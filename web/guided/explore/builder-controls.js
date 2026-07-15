// web/guided/explore/builder-controls.js
// Pure descriptors + spec assembly for the ggplot2 builder, plus the DOM
// control panel shared by the demo and analyze stages. All user strings are
// DOM-built (textContent/value) — never innerHTML.
import { renderColumnPicker } from "../../lib/columnpicker.js";

const COLOR = { key: "color", label: "Color by (optional)", type: "categorical+", optional: true };
const FACET = { key: "facet", label: "Facet by (optional)", type: "categorical+", optional: true };

export function GEOM_ROLES(geom) {
  switch (geom) {
    case "scatter": return [
      { key: "x", label: "X axis", type: "numeric" },
      { key: "y", label: "Y axis", type: "numeric" }, COLOR, FACET];
    case "line": return [
      { key: "x", label: "X axis", type: "numeric" },
      { key: "y", label: "Y axis", type: "numeric" }, COLOR,
      { key: "group", label: "Line per (e.g. patient ID)", type: "categorical+", optional: true },
      FACET];
    case "boxplot": case "violin": return [
      { key: "x", label: "Groups (x axis)", type: "categorical+" },
      { key: "y", label: "Value (y axis)", type: "numeric" }, COLOR, FACET];
    case "bar": return [
      { key: "x", label: "Category (x axis)", type: "categorical+" }, COLOR, FACET];
    case "histogram": return [
      { key: "x", label: "Value (x axis)", type: "numeric" }, COLOR, FACET];
    default: throw new Error("Unknown geom: " + geom);
  }
}

const GEOM_OPTION_KEYS = {
  scatter: ["point_size", "alpha", "smoother", "se"],
  line: ["linewidth", "show_points"],
  boxplot: ["jitter", "notch"],
  violin: ["inner_box", "trim"],
  bar: ["prop", "position"],
  histogram: ["bins", "density"],
};
const SHARED_KEYS = ["title", "xlab", "ylab"];

export function defaultOptions(geom) {
  const d = { geom, title: "", xlab: "", ylab: "" };
  const per = {
    scatter: { point_size: 2, alpha: 0.8, smoother: "none", se: true },
    line: { linewidth: 0.8, show_points: false },
    boxplot: { jitter: false, notch: false },
    violin: { inner_box: true, trim: false },
    bar: { prop: false, position: "dodge" },
    histogram: { bins: 30, density: false },
  }[geom];
  if (!per) throw new Error("Unknown geom: " + geom);
  return { ...d, ...per };
}

// Tagged union: only the active geom's keys plus shared labels (and the demo
// caption) cross to R; rows are projected to used columns only.
export function buildExploreSpec(table, roles, options, caption) {
  const geom = options.geom;
  const roleKeys = GEOM_ROLES(geom).map((r) => r.key);
  const outRoles = {};
  for (const k of roleKeys) outRoles[k] = roles[k] ?? null;
  const used = [...new Set(Object.values(outRoles).filter(Boolean))];
  const data = table.rows.map((r) =>
    Object.fromEntries(used.map((c) => [c, r[c]])));
  const opts = { geom };
  for (const k of [...GEOM_OPTION_KEYS[geom], ...SHARED_KEYS]) opts[k] = options[k];
  if (caption) opts.caption = caption;
  return { figure: "explore", data, roles: outRoles, options: opts };
}

const GEOM_LABELS = { scatter: "Scatter", line: "Line", boxplot: "Boxplot",
  violin: "Violin", bar: "Bar", histogram: "Histogram / density" };

// Per-geom option inputs: [key, label, kind, extra]
const OPTION_CONTROLS = {
  scatter: [["point_size", "Point size", "number", { min: 0.5, max: 6, step: 0.5 }],
            ["alpha", "Opacity", "number", { min: 0.1, max: 1, step: 0.1 }],
            ["smoother", "Trend line", "select", { choices: ["none", "lm", "loess"] }],
            ["se", "Confidence band", "checkbox", {}]],
  line: [["linewidth", "Line width", "number", { min: 0.2, max: 3, step: 0.2 }],
         ["show_points", "Show points", "checkbox", {}]],
  boxplot: [["jitter", "Show raw points", "checkbox", {}],
            ["notch", "Notches", "checkbox", {}]],
  violin: [["inner_box", "Inner boxplot", "checkbox", {}],
           ["trim", "Trim tails", "checkbox", {}]],
  bar: [["prop", "Show proportions", "checkbox", {}],
        ["position", "Grouped bars", "select", { choices: ["dodge", "stack"] }]],
  histogram: [["bins", "Bins", "number", { min: 5, max: 100, step: 1 }],
              ["density", "Density curve instead", "checkbox", {}]],
};

// Renders geom select + role pickers + option inputs into container.
// state = { roles, options }; onChange receives REPLACED objects (session-state
// contract: never mutate nested demoOptions in place).
export function renderBuilderControls(container, table, state, onChange, doc = globalThis.document) {
  container.innerHTML = "";

  const geomLabel = doc.createElement("label");
  geomLabel.textContent = "Chart type";
  const geomSel = doc.createElement("select");
  geomSel.id = "explore-geom";
  geomLabel.htmlFor = geomSel.id;
  for (const g of Object.keys(GEOM_LABELS)) {
    const o = doc.createElement("option");
    o.value = g; o.textContent = GEOM_LABELS[g];
    geomSel.add ? geomSel.add(o) : geomSel.appendChild(o);
  }
  geomSel.value = state.options.geom;
  container.append(geomLabel, geomSel);

  const rolesWrap = doc.createElement("div");
  rolesWrap.className = "explore-roles";
  const optsWrap = doc.createElement("div");
  optsWrap.className = "explore-options";
  const labelsWrap = doc.createElement("div");
  labelsWrap.className = "explore-labels";
  container.append(rolesWrap, optsWrap, labelsWrap);

  let roles = { ...state.roles };
  let options = { ...state.options };
  const emit = () => onChange({ roles: { ...roles }, options: { ...options } });

  geomSel.onchange = () => {
    const geom = geomSel.value;
    const keep = GEOM_ROLES(geom).map((r) => r.key);
    // Keep still-compatible selections; drop the rest. Type compatibility is
    // re-checked by the pickers below (a numeric y stays numeric everywhere).
    roles = Object.fromEntries(keep.map((k) => [k, roles[k] ?? null]));
    options = { ...defaultOptions(geom),
      title: options.title, xlab: options.xlab, ylab: options.ylab };
    buildRoles(); buildOptions();
    emit();
  };

  function readSelects() {
    return Object.fromEntries(GEOM_ROLES(options.geom).map((r) => {
      const sel = rolesWrap.querySelector("#cp_" + r.key);
      return [r.key, sel && sel.value ? sel.value : null];
    }));
  }

  function buildRoles() {
    // renderColumnPicker fires onReady synchronously at build time, BEFORE the
    // saved selections are restored below — that call must not clobber `roles`.
    let ready = false;
    renderColumnPicker(rolesWrap, GEOM_ROLES(options.geom), table, (v) => {
      if (!ready) return;
      // v is null while a required role is unset; individual selections still
      // exist in the DOM, so read them directly to keep partial state.
      roles = v || readSelects();
      emit();
    }, doc);
    // Restore prior selections where the column still exists in the picker.
    for (const r of GEOM_ROLES(options.geom)) {
      const sel = rolesWrap.querySelector("#cp_" + r.key);
      if (sel && roles[r.key]) sel.value = roles[r.key];
    }
    // Reconcile in-memory state to what the pickers actually hold: assigning a
    // value with no matching <option> coerces the select to "" (e.g. a
    // categorical x carried into scatter's numeric picker), and the emitted
    // roles must match the visible state — never a stale selection.
    roles = readSelects();
    ready = true;
  }

  function buildOptions() {
    optsWrap.innerHTML = "";
    for (const [key, label, kind, extra] of OPTION_CONTROLS[options.geom]) {
      const wrap = doc.createElement("label");
      wrap.textContent = label + " ";
      let input;
      if (kind === "select") {
        input = doc.createElement("select");
        for (const c of extra.choices) {
          const o = doc.createElement("option");
          o.value = c; o.textContent = c;
          input.add ? input.add(o) : input.appendChild(o);
        }
        input.value = String(options[key]);
        input.onchange = () => { options = { ...options, [key]: input.value }; emit(); };
      } else if (kind === "checkbox") {
        input = doc.createElement("input");
        input.type = "checkbox"; input.checked = !!options[key];
        input.onchange = () => { options = { ...options, [key]: input.checked }; emit(); };
      } else {
        input = doc.createElement("input");
        input.type = "number";
        input.min = extra.min; input.max = extra.max; input.step = extra.step;
        input.value = options[key];
        input.onchange = () => {
          // A cleared field would coerce to Number("") === 0 — restore the
          // current value instead of shipping 0.
          if (input.value === "") { input.value = options[key]; return; }
          const v = Number(input.value);
          options = { ...options, [key]: Number.isFinite(v) ? v : options[key] };
          emit();
        };
      }
      input.id = "opt-" + key;
      wrap.htmlFor = input.id;
      wrap.appendChild(input);
      optsWrap.appendChild(wrap);
    }
    labelsWrap.innerHTML = "";
    for (const [key, label] of [["title", "Title"], ["xlab", "X label"], ["ylab", "Y label"]]) {
      const wrap = doc.createElement("label");
      wrap.textContent = label + " ";
      const input = doc.createElement("input");
      input.type = "text"; input.value = options[key]; input.id = "lab-" + key;
      wrap.htmlFor = input.id;
      input.oninput = () => { options = { ...options, [key]: input.value }; emit(); };
      wrap.appendChild(input);
      labelsWrap.appendChild(wrap);
    }
  }

  buildRoles(); buildOptions();
}

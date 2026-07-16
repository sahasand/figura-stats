// web/guided/groupcompare/content.js
import { renderColumnPicker } from "../../lib/columnpicker.js";
import { DEMO_TABLE } from "./demo.js";

export function renderUnderstand(panel) {
  panel.innerHTML = `
    <h3>Is the difference between groups real?</h3>
    <p>A group comparison asks whether an outcome differs across two or more
      groups — a biomarker between treatment arms, a complication rate between
      centres. Pick the grouping column and the outcome; the tool chooses the
      right test.</p>
    <h3>The tool picks the test for you</h3>
    <ul>
      <li><strong>A number</strong> (e.g. CRP) compared across groups uses a
        t-test or ANOVA when it looks normal, and their rank-based cousins
        (Mann–Whitney, Kruskal–Wallis) when it is skewed — decided the same way
        the Summary table decides mean vs median.</li>
      <li><strong>A category</strong> (e.g. responder yes/no) uses a chi-square
        test, falling back to Fisher's exact when counts are small.</li>
    </ul>
    <p class="callout">A yes/no outcome written as <code>0</code> and
      <code>1</code> is read as a number, so it is compared with a t-test. To
      get proportions, a chi-square test, and an odds ratio instead, write the
      outcome as words — <code>Yes</code>/<code>No</code>,
      <code>Responder</code>/<code>Non-responder</code>.</p>
    <h3>Report more than a p-value</h3>
    <p>A p-value tells you whether a difference is detectable, not how big it is.
      Every result here also reports an <strong>effect size with a 95% confidence
      interval</strong> — what reviewers increasingly ask for. With three or more
      groups, a significant test is followed by pairwise comparisons so you can
      see <em>which</em> groups differ.</p>`;
}

export const EXAMPLE_INTRO_HTML = `
  <p>This synthetic trial has three arms (Placebo, Low dose, High dose) with a
    roughly normal biomarker, a right-skewed length of stay, and a yes/no
    responder outcome. Change the outcome below to see the test switch.</p>`;

// The demo "experiments" are the analysis controls: outcome column, plot, test.
export function renderGroupCompareExperiments(panel, ctx, rerun) {
  const host = panel.querySelector("#demo-experiments");
  host.innerHTML = "";
  const state = ctx.getSession().demoOptions;

  const outWrap = document.createElement("div");
  host.appendChild(outWrap);
  renderColumnPicker(outWrap,
    [{ key: "group", label: "Groups", type: "categorical+" },
     { key: "outcome", label: "Outcome (number or category)", type: "any" }],
    DEMO_TABLE, (v) => {
      if (!v) return;
      ctx.patchDemoOptions({ roles: { group: v.group, outcome: v.outcome } });
      // A numeric<->categorical outcome switch flips the plot between
      // box/violin and a bar chart, so re-render the Plot control to match.
      renderPlotControl();
      rerun();
    });
  // preselect current roles
  const gsel = outWrap.querySelector("#cp_group"); if (gsel) gsel.value = state.roles.group;
  const osel = outWrap.querySelector("#cp_outcome"); if (osel) osel.value = state.roles.outcome;

  const mk = (parent, id, label, choices, cur, key) => {
    const l = document.createElement("label"); l.textContent = label + " ";
    const s = document.createElement("select"); s.id = id;
    for (const [val, txt] of choices) {
      const o = document.createElement("option"); o.value = val; o.textContent = txt;
      s.appendChild(o);
    }
    s.value = cur;
    // Read the CURRENT session at change time — `state` is a render-time
    // snapshot, so spreading it here would drop an earlier control's change.
    s.onchange = () => {
      const now = ctx.getSession().demoOptions.options;
      ctx.patchDemoOptions({ options: { ...now, [key]: s.value } });
      rerun();
    };
    l.appendChild(s); parent.appendChild(l);
  };

  // A span host so the Plot control can re-render in place (on outcome change)
  // without disturbing the Test control that follows it.
  const plotWrap = document.createElement("span");
  host.appendChild(plotWrap);

  // A numeric outcome is drawn as box/violin; a categorical outcome always
  // renders a stacked proportion bar chart (see R/groupcompare.R .gc_categorical),
  // so show that instead of an inert Box/Violin picker that wouldn't match the
  // figure. DEMO_TABLE.types mirrors R's numeric/categorical decision.
  function renderPlotControl() {
    plotWrap.innerHTML = "";
    const outcome = ctx.getSession().demoOptions.roles.outcome;
    if (DEMO_TABLE.types[outcome] === "numeric") {
      mk(plotWrap, "demo-plot", "Plot", [["box", "Box"], ["violin", "Violin"]],
        ctx.getSession().demoOptions.options.plot, "plot");
    } else {
      const l = document.createElement("label"); l.textContent = "Plot ";
      const s = document.createElement("select"); s.id = "demo-plot"; s.disabled = true;
      const o = document.createElement("option"); o.textContent = "Bar (proportions)";
      s.appendChild(o); l.appendChild(s); plotWrap.appendChild(l);
    }
  }
  renderPlotControl();

  mk(host, "demo-test", "Test", [["auto", "Auto (by normality)"],
    ["parametric", "Parametric"], ["nonparametric", "Non-parametric"]],
    state.options.test, "test");
}

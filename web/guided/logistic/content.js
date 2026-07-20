// web/guided/logistic/content.js
import { LOGISTIC_DEMO } from "./demo-data.js";

const SECTIONS = [
  { title: "Adjust for what else is going on", html: `
    <p>A group comparison tells you whether an outcome happened more often in one
    group. Logistic regression answers the next question: <em>by how much, after
    accounting for the other things that differ between patients?</em> Each covariate
    gets an odds ratio — the relative odds of the outcome per increment (for a number)
    or versus a reference level (for a category).</p>
    <p>Unadjusted odds ratios come from one model per covariate. Adjusted odds ratios
    come from a single joint model, so each one is the effect of that variable with the
    others held fixed. The gap between the two columns is the confounding that the
    adjustment removed — when a treatment is given more often to sicker patients, the
    unadjusted column carries their extra risk and the adjusted column does not.</p>` },
  { title: "What an odds ratio is, and is not", html: `
    <p>Odds are events divided by non-events: 30 complications in 100 patients is a
    risk of 30% but odds of 30/70 = 0.43. An odds ratio compares those odds between
    two groups.</p>
    <p>An odds ratio is <strong>not</strong> a risk ratio, and it is always the further
    of the two from 1. When the outcome is uncommon (under roughly 10%) the two are
    close enough that people read an OR as a relative risk; when the outcome is common
    — as in the example below, where 28% of patients had a complication — an OR of 0.50
    corresponds to about a 42% reduction in <em>risk</em>, not the 50% that "half"
    suggests. Report it as an odds ratio and say so.</p>` },
  { title: "Is logistic regression appropriate?", html: `
    <p>Use it when each row is one independent participant, the outcome is
    <strong>binary</strong> (event / no event), and you have the baseline covariates
    you want to adjust for. The tool needs at least 10 patients in the smaller outcome
    group before it will fit a model, and it drops rows with a missing value in any
    column you use.</p>
    <p>It checks for <strong>separation</strong> (a covariate that predicts the outcome
    almost perfectly, which makes odds ratios meaningless), for
    <strong>multicollinearity</strong> among numeric covariates (two variables carrying
    the same information), and it reports the model's overall discrimination. Each of
    those is advisory — none of them blocks a result or changes a number. The tool does
    not fit penalized (Firth), matched, or mixed models; if separation is flagged, seek
    statistical review rather than reporting the affected odds ratios.</p>` },
  { title: "How to read the result", html: `
    <ul>
      <li><strong>OR &lt; 1</strong>: lower odds of the outcome. <strong>OR &gt; 1</strong>: higher.</li>
      <li>A numeric covariate's OR is <strong>per increment</strong> — set the increment
      (for example per 10 years of age) so that one step is clinically meaningful.</li>
      <li>A category's OR is <strong>versus its reference level</strong>, shown as "1 (reference)".</li>
      <li>A 95% CI that crosses 1 means the effect is not statistically resolved. It does
      not mean there is no effect.</li>
      <li>Adjusted odds ratios are adjusted only for the covariates you put in the model.
      Anything you did not measure could still be confounding the result.</li>
    </ul>
    <p class="callout">With fewer than about 10 events per model term, adjusted
    estimates become unstable — the tool warns you when that happens.</p>` },
];

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("");
}

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic outcome study</h3>
  <p>This teaching dataset has ${LOGISTIC_DEMO.rows.length} fictional patients on
  <strong>Standard care</strong> or a <strong>New treatment</strong>, with baseline age
  and disease stage, and whether a <strong>complication</strong> occurred. The new
  treatment was given preferentially to older, higher-stage patients — the very patients
  most likely to have a complication anyway.</p>
  <p>The example loads with <code>arm</code>, <code>age</code>, and <code>stage</code>
  all checked. Run it as configured and the adjusted odds ratio for the new treatment is
  about 0.5, with a confidence interval that stays under 1. Uncheck <code>age</code> and
  <code>stage</code> and the odds ratio for <code>arm</code> alone jumps to about 1.0,
  with a confidence interval sitting squarely across 1 — in this synthetic dataset,
  adjusting for age and stage accounts for the confounding that made the raw comparison
  look null. Toggle the covariates below to watch that happen.</p>
  <p class="callout">When the results text flags a few observations as "influential"
  (Cook's distance), that is expected here and on most datasets — the rule of thumb it
  uses picks out a small percentage of rows routinely. It is a prompt to check those
  patients for data-entry errors, not a sign that anything is wrong with the model or
  with this example data.</p>`;

// Experiments: check/uncheck which covariates enter the joint model. `arm` is the
// exposure of interest and is always included (its checkbox is disabled).
export function renderLogisticExperiments(panel, ctx, rerun) {
  const host = panel.querySelector("#demo-experiments");
  host.innerHTML = "";
  const ALL = ["arm", "age", "stage"];
  const state = ctx.getSession().demoOptions;
  const fieldset = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = "Covariates in the model";
  fieldset.appendChild(legend);
  for (const c of ALL) {
    const label = document.createElement("label");
    label.className = "inline-check";
    const cb = document.createElement("input");
    cb.type = "checkbox"; cb.id = "cov-" + c; cb.value = c;
    cb.checked = state.covariates.includes(c);
    cb.disabled = c === "arm";
    cb.onchange = () => {
      const now = ctx.getSession().demoOptions.covariates.filter((x) => x !== c);
      if (cb.checked) now.push(c);
      ctx.patchDemoOptions({ covariates: ALL.filter((x) => now.includes(x)) });
      rerun();
    };
    label.appendChild(cb);
    label.appendChild(document.createTextNode(" " + c));
    fieldset.appendChild(label);
  }
  host.appendChild(fieldset);
}

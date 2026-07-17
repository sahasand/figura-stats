// web/guided/cox/content.js
import { COX_DEMO } from "./demo-data.js";

const SECTIONS = [
  { title: "Adjust for what else is going on", html: `
    <p>Kaplan–Meier shows whether survival curves differ. Cox regression answers
    the next question: <em>by how much, after accounting for the other things that
    differ between patients?</em> Each covariate gets a hazard ratio — the relative
    event rate per unit (for a number) or versus a reference level (for a category).</p>
    <p>Unadjusted hazard ratios come from one model per covariate. Adjusted hazard
    ratios come from a single joint model, so each is the effect of that variable
    holding the others fixed — the difference between the two columns is the
    confounding the adjustment removed.</p>` },
  { title: "Is Cox appropriate?", html: `
    <p>Use it when each row is one independent participant with a follow-up time, an
    event or censoring status, and the baseline covariates you want to adjust for.
    The model assumes <strong>proportional hazards</strong>: the hazard ratio for
    each covariate is roughly constant over follow-up.</p>
    <p>This tool checks that assumption with scaled Schoenfeld residuals and warns
    when it looks violated, but it does not fit stratified, time-varying, or
    competing-risks models. If curves cross or the check flags a covariate, seek
    statistical review before interpreting the hazard ratios.</p>` },
  { title: "How to read the result", html: `
    <ul>
      <li><strong>HR &lt; 1</strong>: lower event rate (protective). <strong>HR &gt; 1</strong>: higher.</li>
      <li>A numeric covariate's HR is <strong>per one unit</strong> — scale the variable first if one unit is too small to be meaningful.</li>
      <li>A category's HR is <strong>versus its reference level</strong>, shown as "1 (reference)".</li>
      <li>A 95% CI that crosses 1 means the effect is not statistically resolved.</li>
    </ul>
    <p class="callout">With fewer than about 10 events per model term, adjusted
    estimates become unstable — the tool warns you when that happens.</p>` },
];

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("");
}

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic survival study</h3>
  <p>This teaching dataset has 220 fictional patients on <strong>Standard care</strong>
  or a <strong>New treatment</strong>, with baseline age and disease stage. The treatment
  was given preferentially to older, higher-stage patients — so its unadjusted effect looks
  weak, and only adjusting for age and stage reveals it. Toggle the covariates below to
  watch the treatment's adjusted hazard ratio move.</p>`;

// Experiments: check/uncheck which covariates enter the joint model. `arm` is the
// exposure of interest and is always included (its checkbox is disabled).
export function renderCoxExperiments(panel, ctx, rerun) {
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

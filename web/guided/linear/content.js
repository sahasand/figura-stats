import { LINEAR_DEMO } from "./demo-data.js";

export const UNDERSTAND_SECTIONS = [
  { title: "Adjust for what else is going on", html: `
    <p>A group comparison tells you whether a continuous outcome differs between
    groups. Linear regression answers the next question: <em>by how much, after
    accounting for the other things that differ between patients?</em> Each covariate
    gets a coefficient — the change in the outcome, in its own units, per increment
    (for a number) or versus a reference level (for a category).</p>
    <p>Unadjusted coefficients come from one model per covariate. Adjusted coefficients
    come from a single joint model, so each one is the effect of that variable with the
    others held fixed. When a treatment is given more often to sicker patients, the
    unadjusted column carries their longer stays and the adjusted column does not.</p>` },
  { title: "What a coefficient is, and is not", html: `
    <p>A coefficient is a difference in means. For a category it is the mean outcome in
    that level minus the mean in the reference level, holding the other covariates
    fixed. For a number it is the change in the outcome per increment — set the
    increment (for example age per 10 years) so that one step is clinically
    meaningful; the confidence interval scales with it and the p-value does not.</p>
    <p>It is a difference on the outcome's own scale, not a ratio and not a
    percentage. "New treatment: −1.5 (−2.0 to −1.0)" for length of stay means one and a
    half fewer days on average, not 1.5 times anything. A coefficient of 0 is no
    difference, which is why the forest plot's dashed line sits at 0.</p>` },
  { title: "Is linear regression appropriate?", html: `
    <p>Use it when each row is one independent participant, the outcome is a
    <strong>continuous measurement</strong> (days, mmHg, a score), and you have the
    baseline covariates you want to adjust for. The tool needs at least 10 residual
    degrees of freedom before it will fit a model, and it drops rows with a missing
    value in any column you use.</p>
    <p>It checks the residuals for <strong>normality</strong> (Shapiro–Wilk) and for
    <strong>constant variance</strong> across fitted values (Breusch–Pagan), and it draws
    both checks as a residuals-vs-fitted plot and a normal Q-Q plot. It also flags
    <strong>multicollinearity</strong> among numeric covariates, covariates that are
    exact combinations of others, and influential observations. Every check is
    advisory — none blocks a result or changes a number. The tool does not transform
    the outcome, fit robust standard errors, or add interaction terms; if the residual
    checks warn, that is the moment to seek statistical review.</p>` },
  { title: "How to read the result", html: `
    <ul>
      <li><strong>β &lt; 0</strong>: a lower outcome. <strong>β &gt; 0</strong>: higher.
      The units are the outcome's own.</li>
      <li>A numeric covariate's β is <strong>per increment</strong> (for example per 10 years).</li>
      <li>A category's β is <strong>versus its reference level</strong>, shown as "0 (reference)".</li>
      <li>A 95% CI that crosses 0 means the effect is not statistically resolved. It does
      not mean there is no effect.</li>
      <li>R² is the share of the outcome's variance the joint model explains; adjusted R²
      penalises it for the number of terms. A low R² with a precise coefficient is
      common and not a problem — the question is the coefficient, not the fit.</li>
      <li>Adjusted coefficients are adjusted only for the covariates you put in the model.</li>
    </ul>
    <p class="callout">With fewer than about 10 observations per model term, adjusted
    estimates become unstable — the tool warns you when that happens.</p>` },
];

export function renderUnderstand(panel) {
  panel.innerHTML = UNDERSTAND_SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("");
}

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic length-of-stay study</h3>
  <p>This teaching dataset has ${LINEAR_DEMO.rows.length} fictional patients on
  <strong>Standard care</strong> or a <strong>New treatment</strong>, with baseline age
  and disease stage, and their hospital <strong>length of stay</strong> in days. The new
  treatment was given preferentially to older, higher-stage patients — the very patients
  who stay longest anyway.</p>
  <p>The example loads with <code>arm</code>, <code>age</code>, and <code>stage</code>
  all checked. Run it as configured and the adjusted coefficient for the new treatment
  is about −1.5 days, with a confidence interval that stays below 0. Uncheck
  <code>age</code> and <code>stage</code> and the coefficient for <code>arm</code> alone
  sits near 0 with a confidence interval straddling it — adjusting for age and stage
  accounts for the confounding that made the raw comparison look null. Toggle the
  covariates below to watch that happen.</p>
  <p class="callout">When the results text flags a few observations as "influential"
  (Cook's distance), that is expected here and on most datasets — the rule of thumb it
  uses picks out a small percentage of rows routinely. It is a prompt to check those
  patients for data-entry errors, not a sign that anything is wrong.</p>`;

// Experiments: check/uncheck which covariates enter the joint model. `arm` is the
// exposure of interest and is always included (its checkbox is disabled).
export function renderLinearExperiments(panel, ctx, rerun) {
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

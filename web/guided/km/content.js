// web/guided/km/content.js
// Teaching copy is APPROVED text from
// .scratch/guided-analysis-km/content/km-learning-journey.md — change it there first.
import { TEACHING_VISUAL_SVG, TEACHING_VISUAL_ALT } from "./teaching-visual.js";

const SECTIONS = [
  { title: "Estimate survival over time", html: `
    <p>Kaplan–Meier analysis estimates how the probability of remaining alive—or
    remaining free of a defined event—changes over follow-up. It can include participants
    whose complete event time is unknown because they were still event-free when follow-up
    ended; these observations are censored.</p>
    <p>Each downward step marks an observed event. Censor marks show where follow-up ended
    without the event. Confidence bands show uncertainty, and the risk table shows how many
    participants still support each part of the curve.</p>` },
  { title: "Is Kaplan–Meier appropriate?", html: `
    <p>Use this workflow when each row represents one independent participant, follow-up
    starts from a clearly defined time zero, and each participant has one exact time to
    either the event or ordinary right censoring. A group column is optional.</p>
    <p>This pilot is not designed for competing events, delayed entry, interval censoring,
    repeated or recurrent events, multi-state outcomes, or multiple rows per participant.
    If censoring may be related to prognosis—or you are unsure which structure applies—seek
    statistical review before interpreting the curve.</p>` },
  { title: "What data do you need?", html: `
    <ul>
      <li><strong>Follow-up time:</strong> a non-negative numeric value for each participant.</li>
      <li><strong>Event status:</strong> a value you can explicitly map to Event or Censored.</li>
      <li><strong>Study group (optional):</strong> used to draw and compare separate curves.</li>
      <li><strong>Participant ID (optional):</strong> used to detect duplicate participant rows.</li>
    </ul>
    <p>You will also define the endpoint, time origin and unit, censoring rule, and analysis
    population. Column names alone cannot supply those meanings.</p>` },
  { title: "How should you read the result?", html: `
    <p>Read the curve together with its confidence bands and risk table. Estimates become
    less stable as fewer participants remain under observation, so avoid strong conclusions
    from the sparse tail.</p>
    <p>Median survival is reported only when the estimated curve reaches 50%; otherwise it is
    <strong>not reached</strong>. The log-rank test assesses evidence of an overall difference
    between curves but does not measure its size. An optional hazard ratio compares
    instantaneous event rates under a proportional-hazards assumption—it is not a risk ratio,
    survival-time ratio, or proof of causation.</p>` },
  { title: "When should you seek statistical review?", html: `
    <p>Stop before interpreting this workflow if participants can experience a competing
    event, enter follow-up after time zero, contribute repeated events or records, or have
    censoring that may depend on prognosis. Seek review when curves cross substantially,
    the proportional-hazards check raises concern, estimates are unstable, or an
    observational comparison may be confounded.</p>
    <p>The app can identify patterns and data limitations, but it cannot prove assumptions
    or make a causal conclusion.</p>` },
];

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic survival study</h3>
  <p>This teaching dataset contains 120 fictional participants randomized equally to
  <strong>Standard care</strong> or <strong>New treatment</strong>. Follow-up begins at
  randomization and continues for up to 36 months. The endpoint is all-cause death;
  participants still alive at last contact or the data cutoff are censored.</p>
  <p>The result is intentionally uncertain. Use it to practice reading estimates, confidence
  intervals, censoring, and diminishing risk sets—not to discover whether a real
  treatment works.</p>`;

export const CALLOUTS = {
  confidenceBands: "The shaded 95% pointwise confidence bands show uncertainty around each curve. Wider bands mean less precise estimates; overlap alone does not decide whether groups differ.",
  landmarks: "Prespecified landmark estimates describe survival probability at meaningful times with confidence intervals. Do not search the completed curve for the time point that creates the most favorable comparison.",
  horizon: "The 24-month view focuses on a better-supported region of the same analysis. The underlying data and estimates are unchanged; only the displayed horizon changes.",
  medianStatus: "Median survival is the time when the estimated curve reaches 50%. “Not reached” means the curve did not fall to 50% during supported follow-up; it is not the maximum observed time.",
  logRank: "The ordinary log-rank test evaluates evidence of an overall difference between curves. Its p-value does not measure the size or clinical importance of that difference, and a value above 0.05 does not prove the groups are the same.",
  hazardRatio: "The optional unadjusted hazard ratio compares instantaneous death rates for New treatment versus Standard care among participants still alive. It is not a risk ratio or survival-time ratio and depends on the proportional-hazards assumption.",
};

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("")
    + `<figure class="teaching-visual" aria-label="${TEACHING_VISUAL_ALT}">
         ${TEACHING_VISUAL_SVG}
         <figcaption><strong>Illustration—not computed data.</strong></figcaption>
       </figure>
       <details><summary>Sources and methodology</summary>
         <p>This workflow uses R's <code>survival</code> methods inside your browser. Its
         reporting safeguards draw on established clinical-reporting guidance and
         survival-plot research. Sources support the method and presentation principles;
         they do not make this app a substitute for a study statistician or analysis plan.</p>
         <ul>
           <li><a href="https://www.bmj.com/content/389/bmj-2024-081124">CONSORT 2025 Explanation and Elaboration</a></li>
           <li><a href="https://www.equator-network.org/wp-content/uploads/2013/03/SAMPL-Guidelines-3-13-13.pdf">SAMPL Guidelines</a></li>
           <li><a href="https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survfit.formula.html">R survival documentation</a></li>
           <li><a href="https://bmjopen.bmj.com/content/9/9/e030215">KMunicate</a></li>
           <li><a href="https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf">ASA Statement on p-values</a></li>
         </ul>
       </details>`;
}

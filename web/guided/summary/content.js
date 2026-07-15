// web/guided/summary/content.js
// Teaching copy for the guided Summary (Table 1) analysis. Each section maps to a
// documented descriptive-statistics reporting error.
const SECTIONS = [
  { title: "What this table (a clinical “Table 1”) is for", html: `
    <p>A baseline characteristics table (“Table 1”) describes who was in the study:
    the distribution of each variable, overall and — when relevant — by study group. It is a
    <em>description</em>, not a hypothesis test.</p>` },
  { title: "Mean ± SD or median (IQR)?", html: `
    <p>Report <strong>mean ± SD</strong> only when a continuous variable is approximately
    normally distributed. For skewed variables — length of stay, cost, many biomarkers —
    report the <strong>median with interquartile range</strong>. Reporting a mean for a skewed
    variable is the single most-cited descriptive-statistics error in manuscript review.</p>
    <p>This tool checks each numeric variable for you (Shapiro–Wilk test for small samples,
    skewness for large ones, assessed within your study groups), picks the appropriate
    summary, and shows a one-line reason next to the row so you can defend the choice —
    and shows the distribution so you can see it.</p>` },
  { title: "SD, never SEM", html: `
    <p>The standard deviation (SD) describes how spread out the data are. The standard error of
    the mean (SEM) is smaller and describes the precision of the mean — it is not a measure of
    dispersion. This tool always reports SD, labeled unambiguously, and never SEM.</p>` },
  { title: "Missing data and denominators", html: `
    <p>Reporting guidelines (STROBE) ask for the number of observations per variable and the
    count of missing values, with percentages computed on an unambiguous denominator. This tool
    reports a per-variable missing count and computes each percentage on the non-missing count,
    stated on the variable’s own row — the column header’s N includes rows with missing values,
    so it is never used as the percentage denominator.</p>` },
  { title: "Why there are no p-values here", html: `
    <p>In a randomized trial, any baseline difference between arms is by definition due to chance,
    so a p-value testing baseline balance answers a question no one is asking — the “Table 1
    fallacy.” CONSORT explicitly discourages baseline significance tests. This tool does not
    produce them. Describe the groups; test your outcomes elsewhere.</p>` },
];

export const EXAMPLE_INTRO_HTML = `
  <h3>Explore a synthetic baseline table</h3>
  <p>This teaching dataset contains 120 fictional participants in two arms. It deliberately mixes
  an approximately normal variable (age), two right-skewed variables (length of stay, CRP), two
  categorical variables (sex, diabetes), and some missing length-of-stay values — so you can watch
  the tool pick mean ± SD for the normal variable and median (IQR) for the skewed ones.</p>
  <blockquote><strong>Synthetic teaching data — this is not evidence about a real population.</strong></blockquote>`;

export const CALLOUTS = {
  groupBy: "Grouping splits each row into one column per arm. Percentages use the non-missing count within each arm as the denominator. Note there is still no p-value column — see “Why there are no p-values here.”",
  showPlots: "The distribution panels show each continuous variable with a dashed mean and a solid median line. When the two lines separate, the variable is skewed and median (IQR) is the honest summary.",
  forceMean: "Forcing mean ± SD on every variable reproduces the most common Table 1 error. Watch the skewed variables: the mean is pulled toward the long tail and misrepresents a typical patient.",
};

export function renderUnderstand(panel) {
  panel.innerHTML = SECTIONS.map((s) => `<section><h3>${s.title}</h3>${s.html}</section>`).join("")
    + `<details><summary>Sources and methodology</summary>
         <p>This workflow uses base R statistics (Shapiro–Wilk normality testing, quantiles)
         and ggplot2 inside your browser. Its reporting choices follow established
         clinical-reporting guidance; the sources support the presentation principles and do not
         make this app a substitute for a study statistician.</p>
         <ul>
           <li><a href="https://www.strobe-statement.org/">STROBE Statement</a></li>
           <li><a href="https://www.bmj.com/content/389/bmj-2024-081124">CONSORT 2025 Explanation and Elaboration</a></li>
           <li><a href="https://www.equator-network.org/wp-content/uploads/2013/03/SAMPL-Guidelines-3-13-13.pdf">SAMPL Guidelines</a></li>
         </ul>
       </details>`;
}

# Kaplan–Meier Reporting Baseline

Research asset for **Establish the Kaplan–Meier Reporting Baseline**. Reviewed 2026-07-14.

## Decision

The Guided Analysis should treat a Kaplan–Meier curve as an estimate with a data-provenance and assumptions story—not as a plot generator followed by an automatic p-value. Before calculation it must make the endpoint, time origin, time unit, event coding, censoring rule, analysis population, grouping, and (when applicable) reference group explicit. Its default result must combine the curve with uncertainty, censoring information, numbers at risk, group/event counts, qualified descriptive estimates, and a reproducible methods/results handoff. It must stop or clearly withhold outputs when the data or scientific question fall outside an ordinary right-censored, single-event Kaplan–Meier comparison.

In this document, **require** means the minimum product baseline for a responsible Guided Analysis. It does not mean every item is a legal requirement for every study design or journal. **Recommend** means normally on/default but defeasible for a stated reason. **Avoid** means the product must not perform or phrase the operation without changing the method or adding the stated safeguard.

This baseline combines the current CONSORT guidance to report each group and an effect estimate with uncertainty, the SAMPL survival-analysis checklist, survival-plot guidance, and the primary `survival`/`survminer` documentation. CONSORT 2025 says time-to-event outcomes must be fully defined and results should include group summaries, a between-group effect, and a confidence interval; p-values alone are insufficient ([CONSORT 2025 Explanation and Elaboration](https://www.bmj.com/content/389/bmj-2024-081124)). SAMPL asks authors to identify the time origin, endpoint, censoring circumstances, estimation and comparison methods, assumptions, meaningful-time survival estimates, numbers at risk, medians when useful, and effect estimates with confidence intervals ([SAMPL Guidelines](https://www.equator-network.org/wp-content/uploads/2013/03/SAMPL-Guidelines-3-13-13.pdf)).

## Required baseline

### 1. Define the analysis before accepting the result

The setup and Analysis Handoff must name:

- **Endpoint/event:** a study-specific label such as “all-cause death,” not merely `status`; whether the plotted quantity is survival/event-free probability or cumulative event probability.
- **Time origin and scale:** what time zero means and the unit, for example “Months since randomisation,” not merely “Months.” Survival-plot reporting guidance specifically calls for the time unit and preferably the origin in the x-axis label ([Guidelines for Statistical Reporting in Medical Journals](https://pmc.ncbi.nlm.nih.gov/articles/PMC7642026/)).
- **Censoring rule:** why and when a record is censored, including the analysis/data-cut date where relevant. Standard right-censored methods rely on censoring that is not prognostically informative; loss to follow-up is therefore not just a graphic mark but an assumption that must be disclosed ([Survival Analysis Part I](https://pmc.ncbi.nlm.nih.gov/articles/PMC2394262/), [EMA methodological guidance on time-to-event endpoints](https://www.ema.europa.eu/en/documents/scientific-guideline/appendix-1-guideline-evaluation-anticancer-medicinal-products-man-methodological-consideration-using_en.pdf)).
- **Analysis population and exclusions:** rows provided, rows included, rows not analyzed, and the reason for every exclusion. ICH E9(R1) requires alignment between the clinical question, estimand, estimator, assumptions, and interpretation, and distinguishes intercurrent events from missing-data/censoring problems ([ICH E9(R1)](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-e9-r1-addendum-estimands-and-sensitivity-analysis-clinical-trials-guideline-statistical-principles-clinical-trials-step-5_en.pdf)).
- **Groups and comparison direction:** human-readable group labels and, for a two-group Cox estimate, an explicit numerator/reference such as “Treatment vs control.” Never rely on factor ordering to communicate the HR.
- **Method identity:** Kaplan–Meier estimator, two-sided ordinary log-rank test when requested, Cox proportional-hazards model when requested, CI level/method, tie method, and relevant package/version. The official `survdiff` documentation confirms that `rho = 0` is the ordinary log-rank test and that other weights define different tests ([`survdiff`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survdiff.html)).

The product must explicitly state that the pilot supports **one row per independent analysis unit, one exact follow-up time, one event-or-right-censor indicator, and an optional grouping variable**. The `survival` package supports delayed entry, interval censoring, repeated records, and multi-state data through different `Surv` representations; feeding those designs into the pilot’s simple `Surv(time, status)` shape would silently answer the wrong question ([`Surv`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/Surv.html), [`survfit.formula`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survfit.formula.html)). Unsupported delayed-entry, interval-censored, recurrent-event, multi-state, clustered/repeated-row, or competing-risk data must therefore be blocked with a method-specific explanation rather than coerced into this workflow.

### 2. Validate data without silent repair or deletion

Before R runs, require a preview and explicit Analysis Role mapping for follow-up time, event indicator, and optional group. Event coding must be mapped by meaning (“event” and “censored”), not guessed from a raw code: `Surv` accepts multiple coding conventions, so the official documentation warns through its several valid representations why `0/1` cannot safely be inferred from every dataset ([`Surv`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/Surv.html)).

The preflight must:

- parse standards-compliant CSV including quoted fields; reject empty files, duplicate headers, malformed row widths, and ambiguous encodings;
- reject missing, non-numeric, non-finite, or negative follow-up values; show unusually large values or an event at time zero for confirmation rather than silently changing them;
- require each event value to map unambiguously to event or right censoring;
- reject missing/blank group values when a grouped analysis is requested and preserve the exact user-visible group labels;
- require one record per analysis unit; if an optional participant ID is mapped, flag duplicate IDs rather than assuming they are independent people;
- report total included `n`, events, and censored observations overall and by group before rendering;
- allow a one-curve descriptive analysis, but withhold log-rank and HR outputs unless at least two groups are present;
- withhold a group comparison or Cox HR when it is undefined or numerically unreliable (for example no events overall, a zero-event group, non-convergence, or an infinite coefficient), while keeping any valid descriptive output and explaining what is unavailable.

There is no evidence-based universal minimum sample-size or censoring-percentage cutoff for all KM uses, so the product should not invent a hard “small n” threshold. It must instead expose the counts, uncertainty, and diminishing risk set that determine how much of the curve is supportable. Follow-up should end or be visually de-emphasized once the risk set becomes sparse, with the rule and final displayed time reported; survival-plot guidance emphasizes showing follow-up extent, choosing the horizon responsibly, and avoiding interpretation of unstable tails ([Pocock, Clayton & Altman](https://researchonline.lshtm.ac.uk/id/eprint/16664/), [Guidelines for Statistical Reporting in Medical Journals](https://pmc.ncbi.nlm.nih.gov/articles/PMC7642026/)).

### 3. Render a self-explanatory plot

The default analysis view and default SVG handoff must contain:

- a stepped Kaplan–Meier curve per group with line styles/colors that remain distinguishable without color alone;
- endpoint-specific y-axis text, an x-axis label containing time origin and unit, clear group/legend labels, and an analysis/data-cut caption where supplied;
- visible censoring marks, explained in the legend or caption;
- a number-at-risk table aligned to the x-axis ticks and separated by group;
- 95% **pointwise** confidence bands for each curve by default, plus a control to hide them if a target journal requires it; the analysis view must retain access to them;
- the original group `n` and event/censor counts adjacent to the plot or in the results summary;
- no extrapolation beyond observed curve support and no unqualified reading of the sparse tail.

REMARK explicitly calls for numbers at risk at selected time points and recommends time-point survival estimates with CIs ([REMARK Explanation and Elaboration](https://pmc.ncbi.nlm.nih.gov/articles/PMC3362085/)). KMunicate’s large stakeholder study found the strongest support for visible CIs and an extended table showing at-risk, cumulative-event, and cumulative-censor counts, although its authors deliberately presented this as preference evidence rather than a universal mandate ([KMunicate](https://bmjopen.bmj.com/content/9/9/e030215)). The pilot must therefore require the ordinary risk table and should offer the KMunicate-style extended table as the preferred display when space permits.

The CI method must be deliberate and named. The `survival` documentation notes that plain `p ± 1.96 SE` survival intervals perform poorly and supplies transformed alternatives; the specification should use a bounded transformed method (normally log-log) and label plotted intervals as pointwise rather than simultaneous bands ([`survfit_confint`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survfit_confint.html), [`plot.survfit`](https://stat.ethz.ch/R-manual/R-patched/library/survival/html/plot.survfit.html)).

### 4. Report descriptive estimates before inferential summaries

The result and copied text must report, for every curve:

- `n`, number of events, and number censored;
- median survival/event-free time with a 95% CI **only if estimable**, otherwise “not reached” or “not estimable” (never the maximum observed time);
- survival probability with a 95% CI at user-selected, clinically meaningful time points that were chosen before inspecting the result; and
- enough follow-up context to prevent a time-point estimate from being read past meaningful support.

The official `survfit` documentation defines the median at the point where the curve crosses 0.5 and says it is undefined if the curve does not cross 0.5; it also exposes observations, events, median, and CI per curve ([`print.survfit`](https://stat.ethz.ch/R-manual/R-devel/RHOME/library/survival/html/print.survfit.html)). A fixed-horizon restricted mean can be useful when prespecified, but an unrestricted “mean survival” is not a safe automatic summary because the mean is undefined when the estimated curve does not reach zero and group-specific random truncation points are not comparable ([`print.survfit`](https://stat.ethz.ch/R-manual/R-devel/RHOME/library/survival/html/print.survfit.html)). RMST is therefore a future/advanced option, not something the first Guided Analysis should synthesize opportunistically.

### 5. Qualify comparison statistics

When two or more groups are mapped, the result may report a global ordinary log-rank test as `χ²(df) = …, two-sided p = …`; for more than two groups it must call this an omnibus comparison and must not imply which groups differ. Pairwise comparisons should be absent from the pilot; if added later, they must be user-requested and multiplicity-adjusted rather than generated as unadjusted fishing ([`pairwise_survdiff`](https://search.r-project.org/CRAN/refmans/survminer/html/pairwise_survdiff.html)).

Format p-values without printing an impossible-looking `p = 0.000` (for example, use `p < 0.001` at three-decimal precision). Interpretation Guidance must not call a result “important,” “proven,” or “no difference” based on a threshold. The ASA statement says p-values neither measure effect size nor the probability a hypothesis is true and must not be the sole basis for scientific conclusions ([ASA Statement on p-values](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf)).

For exactly two groups, an **optional unadjusted Cox HR** may be shown only with:

- `HR [comparison] = estimate (95% CI …)` and the model labeled unadjusted;
- explicit reference group and event direction;
- proportional-hazards assessment, including a graphical/diagnostic signal and the limitations of a low-powered test;
- a clear warning or suppression when convergence/separation makes the estimate unreliable; and
- an interpretation as a ratio of instantaneous hazards among those still event-free—not a risk ratio, probability ratio, percent-more-likely statement, survival-time ratio, or automatically causal treatment effect.

`coxph` fits a proportional-hazards model, while `cox.zph` provides term/global diagnostics and a time-varying coefficient plot that should be roughly horizontal under proportional hazards ([`coxph`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/coxph.html), [`cox.zph`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/cox.zph.html)). A hazard ratio conditions on the risk set over time and must not be translated into a relative risk or percent probability statement ([Hernán, “The Hazards of Hazard Ratios”](https://pmc.ncbi.nlm.nih.gov/articles/PMC3653612/)). If curves cross or other evidence makes a constant HR inappropriate, the product must lead with the curves and time-specific absolute estimates, label the single HR as potentially misleading, and recommend statistical review; official FDA draft guidance similarly calls for prespecified PH assessment and supplementary measures such as landmark survival or RMST when non-proportional hazards are anticipated ([FDA draft guidance on overall survival](https://www.fda.gov/media/188274/download)).

### 6. Display assumptions and method boundaries beside the result

Interpretation Guidance must say:

- Kaplan–Meier estimates are descriptive estimates under right censoring; causal conclusions depend on study design and cannot be created by the plot.
- Validity relies on censoring being sufficiently independent/non-informative for the target question. The app can show censoring amount and pattern but cannot prove the assumption from the uploaded columns ([Survival Analysis Part I](https://pmc.ncbi.nlm.nih.gov/articles/PMC2394262/), [ICH E9(R1)](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-e9-r1-addendum-estimands-and-sensitivity-analysis-clinical-trials-guideline-statistical-principles-clinical-trials-step-5_en.pdf)).
- A competing event that prevents the endpoint is not ordinary censoring when estimating real-world cumulative incidence. Using `1 − KM` after censoring competing events overestimates cumulative incidence; use a cumulative-incidence/Aalen–Johansen analysis instead ([Austin et al., review and recommendations](https://pmc.ncbi.nlm.nih.gov/articles/PMC5347914/), [BMJ competing-events guidance](https://www.bmj.com/content/378/bmj-2022-071349), [`survfit.formula`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survfit.formula.html)).
- Apparent curve separation, crossing, or late divergence is exploratory visual evidence, not proof of a time-specific effect; sparse tails and multiple informal time comparisons invite overinterpretation ([Pocock, Clayton & Altman](https://researchonline.lshtm.ac.uk/id/eprint/16664/)).
- An unadjusted curve/HR in observational data may reflect confounding. In a randomized trial, analysis still needs to match the prespecified estimand and analysis plan ([ICH E9(R1)](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-e9-r1-addendum-estimands-and-sensitivity-analysis-clinical-trials-guideline-statistical-principles-clinical-trials-step-5_en.pdf)).

Warnings must travel with the Analysis Handoff. They cannot exist only transiently during validation while the exported SVG or copied sentence appears unconditional.

## Recommended additions

- Default to an extended risk table (`n at risk`, cumulative events, cumulative censored) when the layout remains legible; fall back to `n at risk` plus event/censor totals rather than omitting follow-up context. This follows the favored KMunicate display while respecting that the study did not declare a universal standard ([KMunicate](https://bmjopen.bmj.com/content/9/9/e030215)).
- Offer clinically meaningful landmark estimates, chosen before the result is viewed, with 95% CIs. Do not auto-select the “best-looking” time point ([REMARK Explanation and Elaboration](https://pmc.ncbi.nlm.nih.gov/articles/PMC3362085/), [CONSORT 2025 Explanation and Elaboration](https://www.bmj.com/content/389/bmj-2024-081124)).
- Report median follow-up using a named method such as reverse Kaplan–Meier when follow-up completeness matters; do not call the arithmetic mean/median of observed follow-up times a general completeness measure ([REMARK Explanation and Elaboration](https://pmc.ncbi.nlm.nih.gov/articles/PMC3362748/)).
- Provide a low-risk-set tail control that proposes a defensible cutoff but lets the researcher state the rule. Do not delete late observations from the analysis merely because display is truncated.
- Preserve a machine-readable result object behind the figure: group counts, curve estimates/CIs, risk-table values, median status, test statistic/df/p, HR/CI/model diagnostics, warnings, options, and package versions. The SVG and copyable text should be renderings of this object, not independent calculations.

## Operations the Guided Analysis should avoid

- Do not infer the event code, time origin, endpoint, censoring rule, reference group, or causal interpretation from column names.
- Do not silently drop malformed or missing rows, collapse group labels, transform negative times, or hide model warnings.
- Do not print a risk table request that is not actually present in the exported figure.
- Do not report `p = 0.000`, call a p-value an effect size, equate “not significant” with “same,” or select conclusions by a threshold alone ([ASA Statement on p-values](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf)).
- Do not invent a median when survival never reaches 0.5 or extrapolate beyond observed support ([`print.survfit`](https://stat.ethz.ch/R-manual/R-devel/RHOME/library/survival/html/print.survfit.html), [`summary.survfit`](https://stat.ethz.ch/R-manual/R-patched/library/survival/html/summary.survfit.html)).
- Do not produce a directionless HR, interpret it as “X% more/less likely,” or present it unqualified when PH or convergence is doubtful ([`cox.zph`](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/cox.zph.html), [Hernán](https://pmc.ncbi.nlm.nih.gov/articles/PMC3653612/)).
- Do not generate unadjusted pairwise p-values across multiple groups without a prespecified comparison plan and multiplicity control ([`pairwise_survdiff`](https://search.r-project.org/CRAN/refmans/survminer/html/pairwise_survdiff.html)).
- Do not estimate absolute incidence with `1 − KM` when competing events have been treated as ordinary censoring ([Austin et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5347914/)).
- Do not imply that a grouped, unadjusted analysis accounts for confounders or that a plot alone establishes a treatment effect.

## Gap analysis against the current implementation

| Area | Current behavior | Required change |
|---|---|---|
| Analysis Roles | [`web/forms/km.js`](../../../web/forms/km.js) requires exact headers `time,status,group` and fixes `1=event, 0=censored` (lines 1–20, 28–30). | Map arbitrary columns to roles; explicitly map event/censor values and preview their interpretation. Make grouping optional for a single curve. |
| CSV parsing | The KM parser splits lines and cells on commas and uses permissive `parseFloat`/`parseInt` (lines 2–15), so quoted commas are unsupported and strings such as `12abc` or `1x` can be partially accepted. | Use the shared/robust parser or a standards-compliant parser; reject rather than partially parse. |
| Validation | JS checks finite parsed time, binary status, non-empty group, and at least one row; R checks only two rows and status (lines 4–10 of [`R/km.R`](../../../R/km.R)). Negative time, missing/NA generated in R, group/event counts, duplicate analysis units, zero-event groups, and unsupported censoring designs are not handled. | Implement the full preflight above at UI and R boundaries, with structured errors/warnings and no silent omission. |
| Plot | [`R/km.R`](../../../R/km.R) calls `ggsurvplot(..., risk.table=TRUE)` but returns only `gg$plot` (lines 21–26). The original plan explicitly records that this drops the table ([plan lines 795–811](../../../docs/superpowers/plans/2026-07-13-clinical-figures.md)). Censor marks are present only because `survminer` defaults them on; CIs default off ([`ggsurvplot` arguments](https://rpkgs.datanovia.com/survminer/reference/ggsurvplot_arguments.html)). | Return a composed curve+risk-table SVG; deliberately set censoring, CI method/display, ticks, labels, horizon, and accessible line encodings instead of inheriting defaults. |
| Labels | The x label is user text defaulting to “Months”; y is always “Survival probability”; legend title is “Group” (lines 15, 22–24). Endpoint, origin, censor definition, group meaning, and data-cut are absent. | Require endpoint/origin/unit labels and meaningful group/reference labels; add a concise caption/methods block. |
| Descriptive statistics | No `n`, events, censored, time-point estimates, median, median CI, follow-up summary, or “not reached” state is returned. | Return per-group descriptive and uncertainty results before comparison statistics. |
| Log-rank | `survdiff` is run automatically and output is only `Log-rank p = …`; no statistic, df, sidedness, or omnibus explanation is shown (lines 13–14, 28). `%.3f` can render `p = 0.000`. | Report method, χ², df, two-sided p, group scope, and safe p formatting; withhold when comparison is invalid. |
| Hazard ratio | A Cox HR is automatic for two groups and reported without numerator/reference, event direction, “unadjusted,” tie method, or PH/convergence assessment (lines 29–34). Factor ordering silently determines direction. | Make HR optional/qualified, reference-explicit, diagnostic-aware, and paired with its 95% CI and interpretation guardrails. |
| Warnings | `fig_km` locally suppresses plot warnings, and the worker wraps the entire render in `suppressWarnings(...)` while disabling condition capture ([`web/worker.js`](../../../web/worker.js), lines 83–89). This also suppresses scientifically relevant `coxph` warnings despite the R comment claiming otherwise. | Suppress only identified package-noise warnings; capture model/data warnings as structured output and block unreliable estimates. |
| Result/handoff | [`web/app.js`](../../../web/app.js) inserts one SVG and one plain console sentence (lines 45–62); [`web/index.html`](../../../web/index.html) has no SVG download or copy control. Assumptions and warnings do not travel with an export. | Produce downloadable SVG plus copyable methods/results text, structured summaries, and attached warnings/options. |
| Tests | [`tests/testthat/test-km.R`](../../../tests/testthat/test-km.R) checks only that SVG, “log-rank,” and “HR” exist plus one invalid-status case; [`tests/e2e/km.spec.js`](../../../tests/e2e/km.spec.js) checks only that an SVG appears. The original design called for a known dataset reproducing HR, median, and log-rank p ([design lines 116–123](../../../docs/superpowers/specs/2026-07-13-clinical-figures-design.md)). | Add pinned numerical truth tests and edge cases for mapping, parsing, medians not reached, risk table, CIs, zero events, one/many groups, PH/convergence, competing-risk boundary, exclusions, warnings, handoff text, and export. |

The current architecture is still a sound delivery base: data remains in the browser, webR runs the authoritative R routines in a worker, and the R entry point is independently testable. The gap is not a need to replace `survival`; it is the absence of a structured analysis contract around it. Official `survminer` output already separates the curve and tables into distinct components, which explains the current dropped table and makes composing a complete result feasible ([`ggsurvplot` return value](https://rpkgs.datanovia.com/survminer/reference/ggsurvplot.html)).

## Acceptance implications for the later specification

The written specification should make the following observable rather than aspirational:

1. A user cannot run until endpoint, time origin/unit, event mapping, censor meaning, and Analysis Roles are explicit.
2. The same synthetic and user-data workflows exercise the same validation, calculation, and result contract.
3. Default output visibly contains curves, pointwise CIs, censor marks, and a real risk table; hiding optional layers never removes their underlying numeric summaries.
4. Every displayed statistic has a method, scope, direction, uncertainty measure, estimability state, and plain-language limitation.
5. Invalid rows and model warnings are itemized; no exclusion or warning disappears from copied/exported material.
6. Unsupported censoring/data structures and plausible competing-risk questions are stopped with a route to an appropriate method.
7. Pinned tests verify numerical results against an independently known dataset and verify failure/withholding behavior for scientifically invalid edge cases.

## Source hierarchy and limits

The sources above are primary reporting statements/guidelines, regulator guidance, original peer-reviewed methodological guidance or stakeholder research, and official package documentation. REMARK is specific to prognostic-marker studies, CONSORT to randomized trials, and the cited EMA/FDA documents to regulatory contexts; their study-specific provisions should not be presented as universally binding. Their shared principles—define the endpoint and censoring, expose follow-up and uncertainty, report effect estimates with CIs, and qualify assumptions—form the cross-design baseline. KMunicate supplies strong user-preference evidence, not a mandate. The FDA overall-survival document cited above is explicitly draft guidance and is used only to support the PH/supplementary-analysis safeguard, not to impose an oncology regulatory workflow on this general-purpose tool.

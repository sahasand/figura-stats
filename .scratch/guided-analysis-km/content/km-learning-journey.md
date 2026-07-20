# Kaplan–Meier Learning Journey — First-Draft Copy

Status: approved first draft for specification synthesis  
Language: English  
Scope: **Understand** and **Try an Example** teaching content for the Kaplan–Meier pilot

This asset holds user-facing copy and content behavior. Final component placement belongs to **Design Results, Interpretation, and Analysis Handoff**; implementation structure belongs to **Define the Guided Analysis Module Contract**.

## Learning objectives

After using **Understand** and **Try an Example**, a clinical researcher should be able to:

1. Decide whether ordinary right-censored Kaplan–Meier analysis fits the question and data.
2. Define the endpoint, time origin and unit, censoring rule, population, and comparison context.
3. Distinguish an observed event from a censored observation.
4. Read curve steps, censor marks, pointwise confidence bands, and the risk table together.
5. Interpret median survival, prespecified landmark estimates, an ordinary log-rank result, and an optional unadjusted hazard ratio without overclaiming.
6. Recognize sparse tails, competing events, informative censoring, non-proportional hazards, and situations requiring statistical review.

## Understand

### Opening

#### Estimate survival over time

Kaplan–Meier analysis estimates how the probability of remaining alive—or remaining free of a defined event—changes over follow-up. It can include participants whose complete event time is unknown because they were still event-free when follow-up ended; these observations are censored.

Each downward step marks an observed event. Censor marks show where follow-up ended without the event. Confidence bands show uncertainty, and the risk table shows how many participants still support each part of the curve.

### Suitability

#### Is Kaplan–Meier appropriate?

Use this workflow when each row represents one independent participant, follow-up starts from a clearly defined time zero, and each participant has one exact time to either the event or ordinary right censoring. A group column is optional.

This pilot is not designed for competing events, delayed entry, interval censoring, repeated or recurrent events, multi-state outcomes, or multiple rows per participant. If censoring may be related to prognosis—or you are unsure which structure applies—seek statistical review before interpreting the curve.

### Required data

#### What data do you need?

- **Follow-up time:** a non-negative numeric value for each participant.
- **Event status:** a value you can explicitly map to Event or Censored.
- **Study group (optional):** used to draw and compare separate curves.
- **Participant ID (optional):** used to detect duplicate participant rows.

You will also define the endpoint, time origin and unit, censoring rule, and analysis population. Column names alone cannot supply those meanings.

### Interpretation

#### How should you read the result?

Read the curve together with its confidence bands and risk table. Estimates become less stable as fewer participants remain under observation, so avoid strong conclusions from the sparse tail.

Median survival is reported only when the estimated curve reaches 50%; otherwise it is **not reached**. The log-rank test assesses evidence of an overall difference between curves but does not measure its size. An optional hazard ratio compares instantaneous event rates under a proportional-hazards assumption—it is not a risk ratio, survival-time ratio, or proof of causation.

### Escalation

#### When should you seek statistical review?

Stop before interpreting this workflow if participants can experience a competing event, enter follow-up after time zero, contribute repeated events or records, or have censoring that may depend on prognosis. Seek review when curves cross substantially, the proportional-hazards check raises concern, estimates are unstable, or an observational comparison may be confounded.

The app can identify patterns and data limitations, but it cannot prove assumptions or make a causal conclusion.

### Actions

- Primary learning action: **Try an Example**
- Equal alternative: **Analyze Your Data**
- Optional disclosure: **Sources and methodology**

### Teaching Visual annotations

The Teaching Visual is explicitly labeled **Illustration—not computed data** and annotates:

- a downward step as an observed endpoint event;
- a censor mark as follow-up ending without the event;
- the point estimate and 95% pointwise confidence band;
- the aligned number-at-risk table;
- the shrinking risk set and uncertainty in the late tail; and
- the 50% line used to determine whether median survival is estimable.

## Try an Example

### Demonstration Story introduction

#### Explore a synthetic survival study

This teaching dataset contains 120 fictional participants randomized equally to **Standard care** or **New treatment**. Follow-up begins at randomization and continues for up to 36 months. The endpoint is all-cause death; participants still alive at last contact or the data cutoff are censored.

The result is intentionally uncertain. Use it to practice reading estimates, confidence intervals, censoring, and diminishing risk sets—not to discover whether a real treatment works.

> **Synthetic teaching data—this is not evidence about a real treatment.**

Primary action: **Run Example Analysis**  
Secondary action after changes: **Reset Example**

### Demonstration Dataset contract

- Fixed, versioned CSV; never generated randomly at runtime.
- 120 participants: 60 Standard care and 60 New treatment.
- One row per participant.
- Analysis Roles: participant ID, follow-up months, event status, and study group.
- Endpoint: all-cause death.
- Time origin: randomization.
- Unit: months.
- Censoring: alive at last known follow-up or at the 36-month data cutoff.
- Event/status values are human-readable and arrive explicitly mapped.
- No blockers; useful non-blocking notices about uncertainty and late follow-up are expected.
- Stable teaching targets:
  - realistic censoring and balanced groups;
  - modest hazard-ratio estimate with a 95% CI containing 1;
  - ordinary log-rank p-value above 0.05 but close enough to discourage binary thinking;
  - median reached for Standard care but not reached for New treatment;
  - adequate risk sets at 12 and 24 months and a visibly sparse 36-month tail.
- Pinned tests must verify every expected count and estimate used by teaching copy.

### Learning Callouts

#### Data Preview

> Each row represents one fictional participant. The app shows the source data without editing it. Notice that follow-up time and status are separate: the same time value can end in either an event or censoring.

#### Analysis Roles

> Analysis Roles describe what each column means to Kaplan–Meier analysis. The names are suggested here, but meaning is confirmed rather than inferred. Your own CSV can use different column names.

#### Event mapping

> “Death” is mapped to Event and “Censored” to Censored. Censoring means the participant was still alive when their observed follow-up ended; it does not mean the event happened later or that the participant should be removed.

#### Analysis Definition

> The endpoint, time origin, unit, censoring rule, and population determine what the curve estimates. These definitions remain attached to the result and manuscript text.

#### Method Suitability Check

> The dataset uses one independent row and one exact follow-up time per participant, with all-cause death or ordinary right censoring. The app asks these questions because unsupported structures cannot always be detected from column values alone.

#### Analysis Preflight

> Review the event, censor, and group counts before computing. A passed preflight means the data fit this supported workflow; it does not prove that censoring is non-informative or that a comparison is causal.

#### Curve

> Each step is an estimated change in survival probability after an observed death. The curve is an estimate, not a record of an “average participant.”

#### Confidence bands

> The shaded 95% pointwise confidence bands show uncertainty around each curve. Wider bands mean less precise estimates; overlap alone does not decide whether groups differ.

#### Censor marks

> A censor mark shows where a participant's observed follow-up ended without death. The participant contributes information to the curve up to that time.

#### Risk table

> The risk table shows how many participants remain under observation and event-free at each time. Read the curve cautiously as these counts become small.

#### Median status

> Median survival is the time when the estimated curve reaches 50%. “Not reached” means the curve did not fall to 50% during supported follow-up; it is not the maximum observed time.

#### Log-rank result

> The ordinary log-rank test evaluates evidence of an overall difference between curves. Its p-value does not measure the size or clinical importance of that difference, and a value above 0.05 does not prove the groups are the same.

#### Hazard ratio

> The optional unadjusted hazard ratio compares instantaneous death rates for New treatment versus Standard care among participants still alive. It is not a risk ratio or survival-time ratio and depends on the proportional-hazards assumption.

#### Sparse tail

> Few participants remain at risk near 36 months, so the late estimates are imprecise. Restricting the displayed horizon can improve readability, but it does not remove observations from the analysis.

### Guided Experiments

Each experiment is optional, reversible, and followed by **Reset Example**.

#### What do confidence bands add?

Action: hide, then restore the confidence bands.

> Without the bands, the curves look more certain than the estimates support. Journal formatting may hide them, but the analysis view and numeric summaries should retain uncertainty.

#### Compare prespecified times

Action: add survival estimates at 12 and 24 months before rerunning.

> Prespecified landmark estimates describe survival probability at meaningful times with confidence intervals. Do not search the completed curve for the time point that creates the most favorable comparison.

#### Inspect the supported horizon

Action: shorten the displayed horizon from 36 to 24 months, then restore it.

> The 24-month view focuses on a better-supported region of the same analysis. The underlying data and estimates are unchanged; only the displayed horizon changes.

## Controlled interpretation templates

Templates are deterministic and populated from the structured result. They never invent a conclusion.

### Group summary

> **{group_label}:** {n} participants; {events} events and {censored} censored observations.

### Landmark estimate

> At {time} {unit}, estimated {endpoint_free_label} was {estimate}% (95% CI {lower}%–{upper}%) in {group_label}. {support_notice}

### Median reached

> Median {endpoint_label} time was {median} {unit} (95% CI {lower}–{upper}) in {group_label}.

### Median not reached

> Median {endpoint_label} time was not reached in {group_label} during supported follow-up; the curve did not fall to 50%.

### Two-group log-rank

> The ordinary two-sided log-rank test compared the complete curves: χ²({df}) = {statistic}, p {p_operator} {p_value}. This tests evidence of an overall difference; it does not measure effect size or clinical importance.

### Omnibus log-rank

> The ordinary two-sided omnibus log-rank test compared all {group_count} curves: χ²({df}) = {statistic}, p {p_operator} {p_value}. It does not identify which groups differ.

### Valid unadjusted hazard ratio

> The unadjusted hazard ratio for {comparison} was {estimate} (95% CI {lower}–{upper}). It compares instantaneous {event_label} rates among participants still {endpoint_free_label}; it is not a risk ratio or causal effect. {ph_notice}

### Withheld comparison

> {comparison_name} was not reported because {withholding_reason}. Valid descriptive estimates remain available.

### Tail notice

> Estimates after {time} {unit} are based on a small risk set and should be interpreted cautiously. {display_horizon_notice}

### Synthetic-data footer

> Demonstration Dataset: synthetic teaching data. Values and results do not describe a real treatment or study.

## Sources and methodology

User-facing disclosure text:

> This workflow uses R's `survival` methods inside your browser. Its reporting safeguards draw on established clinical-reporting guidance and survival-plot research. Sources support the method and presentation principles; they do not make this app a substitute for a study statistician or analysis plan.

Topic links:

- [CONSORT 2025 Explanation and Elaboration](https://www.bmj.com/content/389/bmj-2024-081124) — defining time-to-event outcomes and reporting estimates with uncertainty.
- [SAMPL Guidelines](https://www.equator-network.org/wp-content/uploads/2013/03/SAMPL-Guidelines-3-13-13.pdf) — survival-analysis reporting items.
- [R `survival` documentation](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/survfit.formula.html) — estimator behavior and supported data structures.
- [KMunicate](https://bmjopen.bmj.com/content/9/9/e030215) — stakeholder-informed survival-plot presentation.
- [ASA Statement on p-values](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf) — responsible p-value interpretation.
- [ICH E9(R1)](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-e9-r1-addendum-estimands-and-sensitivity-analysis-clinical-trials-guideline-statistical-principles-clinical-trials-step-5_en.pdf) — aligning the question, estimator, assumptions, and interpretation.
- [Competing-events guidance](https://www.bmj.com/content/378/bmj-2022-071349) — why ordinary censoring is not appropriate for a competing event.

The full source synthesis is in [Kaplan–Meier Reporting Baseline](../research/km-reporting-baseline.md).

## Localization boundary

This first draft is English only. Copy is separated by heading, callout, action label, template, and source topic so later localization does not require rewriting statistical logic. Localization itself is outside this map's destination.

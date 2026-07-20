# Kaplan–Meier Result and Analysis Handoff

Status: approved product and content specification  
Scope: result presentation, Interpretation Guidance, and Analysis Handoff for the Kaplan–Meier pilot

This asset specifies what a completed Kaplan–Meier analysis presents and what travels into reuse. The computation and component interfaces are specified later in **Define the Guided Analysis Module Contract**.

## Design goals

The result must let a clinical researcher:

1. verify which data and analysis definition produced the result;
2. read the curve with its uncertainty and risk-set context;
3. understand descriptive estimates before inferential comparisons;
4. see every validation or suitability limitation that affects interpretation;
5. reuse a clean figure and reproducible manuscript wording without losing required warnings; and
6. distinguish demonstration output, current user output, and an Out-of-date Result.

The result must not turn a p-value into the headline, silently omit unsupported statistics, create a causal conclusion, or allow a stale result into an Analysis Handoff.

## Result workspace

Replace the current **Figure** and **Console** split with one scrollable result document. Do not hide major result sections behind tabs. A compact section navigator may jump to sections, but the document order remains:

1. Result header
2. Findings summary
3. Figure
4. Group overview
5. Survival estimates
6. Group comparison
7. Diagnostics and limitations
8. Interpretation Guidance
9. Analysis Handoff

On a wide screen, the result document occupies the output pane and scrolls independently. On a narrow screen it follows the configuration workflow in the page flow. Section order and content do not change between layouts.

### Persistent result header

Keep a compact header visible while the result document scrolls. It contains:

- result title: **Kaplan–Meier analysis**;
- source badge: **Example Data** or **Your Data**;
- status badge: **Current** or **Out of date**;
- endpoint and analysis population;
- group comparison, or **Single curve—no group comparison**;
- data cutoff when defined;
- generation date and time in the user's locale; and
- **View analysis definition**, opening the endpoint, time origin/unit, censoring rule, population, role mappings, group labels/reference, accepted confirmations, and analysis options.

Do not show the uploaded filename in the persistent header. It may remain available inside the in-session analysis definition, but it does not enter copied manuscript text or exported filenames.

### Current and out-of-date behavior

A result is **Current** only while its source data, Analysis Roles, Analysis Definition, accepted confirmations, and analysis settings match the inputs used for computation.

When any of those inputs change:

- retain the prior result for reference;
- change its status immediately to **Out of date**;
- display: **Inputs changed after this result was generated. Run the analysis again before reusing it.**;
- keep inspection and section navigation available; and
- disable Download SVG and all copy actions, with **Run analysis again to enable handoff** as the visible reason.

Never refresh only part of a result. A successful run replaces the structured result atomically.

## Findings presentation

Replace generic console output with structured **Preflight Findings** and analysis diagnostics.

### Two-level presentation

1. A findings summary immediately below the result header groups Blockers, Confirmations, and Notices and links to affected sections.
2. Each finding appears again beside the statistic, comparison, or interpretation it affects.

Critical findings remain expanded. Supporting technical detail may use a disclosure. Each finding contains:

- severity and short title;
- plain-language description;
- consequence for this result;
- recommended next action; and
- relevant source rows or analysis setting when applicable.

Blockers prevent a result from being created. Confirmations accepted during preflight and non-blocking Notices remain attached to the completed result. A withheld comparison is shown explicitly with its reason; it is never represented as a missing or blank value.

## Figure

### On-screen figure

The primary figure contains:

- one Kaplan–Meier step curve per group, or one curve for an ungrouped analysis;
- pointwise 95% confidence intervals;
- censor marks;
- redundant visual encoding so groups do not depend on color alone;
- direct, human-readable group labels and group sample sizes;
- an endpoint-specific y-axis label;
- a follow-up x-axis label with the confirmed time unit;
- a legend when more than one group is present;
- a number-at-risk table aligned to the x-axis; and
- a concise caption identifying the endpoint, population, and data cutoff when defined.

Landmark guides are shown only for user-selected prespecified landmark times. The display horizon may crop the view but must not alter the fitted data or reported analysis.

### Downloaded SVG

The SVG is a clean, self-contained publication figure. It includes the plotted content, risk table, axes, labels, legend, and concise caption. It does **not** print validation warnings, full provenance, Interpretation Guidance, or manuscript prose inside the image.

Warnings and fuller provenance instead travel in the mandatory adjacent **Use with this figure** note and in Complete Handoff text. The interface must make this separation explicit before download:

> The SVG is intentionally clean. Keep the accompanying figure-use note with it so analysis limitations are not lost.

The SVG must contain real text where practical, declare an accessible title and description, and remain legible when printed without color. It must not load external fonts, images, scripts, or network resources.

### View figure data

Place a **View figure data** disclosure directly below the figure. It exposes semantic tables for:

- number at risk at every displayed risk-table time; and
- plotted survival estimates, pointwise confidence limits, and cumulative event/censor counts at reportable times.

The disclosure is available on screen for accessibility and verification. These tables are not included in the SVG or default Complete Handoff and are not downloadable in the pilot.

## Statistical result order

Present statistics in a fixed order so description precedes inference.

### 1. Group overview

For every group, or for the overall population when ungrouped, report:

- participants analyzed;
- observed events;
- censored observations; and
- follow-up context supported by the computation contract.

Counts are never inferred from percentages and never silently exclude invalid rows. The counts must reconcile with the final Analysis Preflight.

### 2. Survival estimates

Report selected prespecified landmark survival estimates first, each with a pointwise 95% confidence interval and number at risk. Then report median survival with a 95% confidence interval.

If the curve does not reach 50%, show **Not reached** rather than a blank, infinity, or extrapolated value. If a confidence bound is not estimable, identify that bound as **Not estimable** and attach an explanation.

### 3. Group comparison

When supported and requested, show:

- ordinary log-rank chi-square statistic, degrees of freedom, and two-sided p-value;
- for more than two groups, label it an omnibus comparison and do not imply which groups differ; and
- an optional unadjusted hazard ratio only for a supported two-group comparison, with explicit numerator/reference direction, 95% confidence interval, and proportional-hazards assessment.

Do not describe the log-rank test as an effect size. Do not describe the hazard ratio as a risk ratio, survival-time ratio, causal effect, or adjusted estimate. If a comparison is unreliable or unsupported, replace it with **Comparison withheld** and the specific reason.

### 4. Diagnostics and limitations

Show applicable proportional-hazards findings, crossing-curve concerns, sparse-tail notices, estimability limits, accepted preflight confirmations, and method-boundary reminders. Diagnostics qualify estimates; they do not claim to prove assumptions.

## Interpretation Guidance

Interpretation Guidance uses deterministic, state-aware templates backed by the structured result. It is not generated free-form prose.

The visible guidance contains:

1. what the curves and descriptive estimates show;
2. what any group comparison assesses;
3. what the result does not establish; and
4. the limitations that materially affect interpretation.

Critical limitations remain visible. Optional teaching detail may expand beneath the relevant sentence. The copy templates approved in `km-learning-journey.md` provide the base phrasing for group summaries, landmark estimates, reached/not-reached medians, two-group and omnibus log-rank results, optional hazard ratios, withheld comparisons, and sparse tails.

Interpretation Guidance must:

- identify groups and reference direction explicitly;
- report uncertainty with estimates;
- avoid binary conclusions based on a p-value threshold;
- avoid causal language;
- distinguish absence of evidence from evidence of no difference;
- state when an estimate is not reached or not estimable;
- tell the user when deeper statistical review is warranted; and
- preserve mandatory synthetic-data language for a Demonstration Dataset.

## Analysis Handoff

Show four unambiguous actions rather than a generic Export menu:

1. **Download SVG**
2. **Copy Methods**
3. **Copy Results**
4. **Copy Complete Handoff**

Each action has a preview of its exact payload. Copy actions write simple semantic HTML and an equivalent plain-text fallback when the browser supports both. The two representations must contain the same claims and numerical values. Success is announced visibly and through an accessible status message; failure preserves the preview and offers manual selection.

No PNG, PDF, Word report, CSV, JSON, or numerical-table download is included in the pilot. The module still produces a structured internal result for rendering, testing, wording, and later export extensions.

### Copy Methods payload

Generate a reproducible Methods paragraph from confirmed analysis semantics and actual methods run. Include every applicable item and omit analyses that were not run:

- analysis population;
- endpoint;
- time origin and confirmed time unit;
- event and censor definitions;
- data cutoff when defined;
- Kaplan–Meier estimator;
- confidence-interval method and confidence level;
- censor-mark and number-at-risk presentation;
- prespecified landmark times;
- ordinary log-rank method when run;
- Cox model, unadjusted status, comparison/reference direction, tie handling, and confidence interval when run;
- proportional-hazards assessment when an HR is reported; and
- analysis module/software and version identifiers required for reproducibility.

Do not include a method merely because the interface supports it.

### Copy Results payload

Generate Results paragraphs in the same fixed order as the screen:

1. population and per-group event/censor counts;
2. prespecified landmark estimates and 95% confidence intervals;
3. median estimates and 95% confidence intervals, including **not reached** or **not estimable** states;
4. ordinary log-rank result when run;
5. optional directed unadjusted hazard ratio and proportional-hazards qualification when supported; and
6. required limitations and reasons for any withheld comparison.

The copy is evidence-limited and uses controlled templates. It must not add claims beyond computed results.

### Copy Complete Handoff payload

Combine, in this order:

1. **Analysis definition**
2. **Methods**
3. **Results**
4. **Required interpretation notes**
5. **Use with this figure**

The **Use with this figure** note repeats the endpoint, population, data cutoff, group/reference direction, applicable validity warnings, and the instruction to retain the text with the clean SVG. This is the mechanism by which warnings travel with the downloaded figure without being printed inside it.

### Precision and formatting

Display and copied prose use:

- counts as integers;
- survival estimates and time values to one decimal;
- hazard ratios to two decimals;
- confidence limits at the precision of their estimate;
- p-values to three decimals; and
- `p < 0.001` for smaller values, never `p = 0.000`.

Trailing zeros are retained where they communicate the declared precision. Computation and the structured internal result retain unrounded values; displayed values must never be parsed back into calculations.

### Filenames

Use:

`kaplan-meier-{demo|user}-{endpoint-slug}-{data-cut}.svg`

Sanitize and length-limit the endpoint slug. If no data cutoff exists, use the analysis generation date. Never include participant identifiers, group names, or the uploaded source filename. Normal browser collision handling may append a sequence number.

## Demonstration result

All four handoff actions remain available for the Demonstration Dataset so the user can learn the complete workflow. Mandatory labeling appears in:

- the result header;
- the SVG caption;
- the SVG filename through the `demo` source token;
- Methods and Results copy; and
- every Complete Handoff preview and payload.

Use this exact sentence:

> Synthetic demonstration data — not for clinical use.

The label cannot be dismissed, renamed, or removed through display controls.

## Required states

The result workspace must specify and test:

- no result yet;
- analysis working;
- current descriptive result without a group comparison;
- current two-group result;
- current multi-group result with omnibus comparison;
- median not reached;
- comparison withheld;
- current result with Confirmations and Notices;
- current result with an optional HR and diagnostics;
- current result where HR is withheld;
- demonstration result;
- Out-of-date Result;
- SVG generation/download failure; and
- clipboard unavailable or copy failure.

An analysis error is not a partial result. Preserve the last successful result, label its status accurately, and show the new error in the analysis controls.

## Acceptance criteria

The result and handoff design is satisfied when:

- a reader can identify the data source, status, endpoint, population, and comparison without opening another stage;
- all displayed counts reconcile with preflight;
- the figure always pairs curves with uncertainty, censor marks, and a real risk table;
- descriptions precede group comparisons;
- every withheld statistic has a visible reason;
- every material finding is visible both in the summary and beside the affected result;
- Interpretation Guidance is deterministic and contains no causal or threshold-based conclusion;
- downloaded SVGs remain clean while Complete Handoff carries required warnings and provenance;
- demo assets cannot be mistaken for clinical output;
- Out-of-date Results cannot be copied or downloaded;
- screen, SVG, Methods, Results, and Complete Handoff derive from one structured result and agree after declared rounding; and
- clipboard and download failures have accessible recovery paths.

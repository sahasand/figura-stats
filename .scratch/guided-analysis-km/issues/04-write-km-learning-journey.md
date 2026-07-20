# Write the Kaplan–Meier Learning Journey and Demonstration Story

Type: grilling
Status: resolved
Label: `wayfinder:grilling`
Blocked by: 01, 02, 03

## Question

What must the Kaplan–Meier pilot teach, what first-draft user-facing copy should it use, and how should its synthetic Demonstration Dataset and annotations let users learn by running the full workflow without turning the product into a statistics course?

## Answer

Teach six outcomes: method suitability, Analysis Definition, event/censor meaning, plot and risk-table reading, qualified statistical interpretation, and recognition of limitations requiring statistical review. Use concise plain clinical English, define statistical terms at first use, keep formulas behind optional technical detail, and use neutral deterministic wording rather than generated narrative or threshold-based conclusions.

Use one fixed, versioned 120-participant synthetic randomized overall-survival dataset with Standard care and New treatment groups. The Demonstration Story is clearly fictional, uses months from randomization, all-cause death, ordinary censoring, and a 36-month cutoff, and produces stable nuanced teaching outcomes: modest separation, overlapping uncertainty, a non-decisive comparison, one median not reached, and a sparse tail. Crossing curves and competing events are taught through non-data Teaching Visuals rather than extra runnable datasets.

Teach through contextual, collapsible Learning Callouts attached to the shared data/validation/result workflow, never a modal tour or mandatory lesson. Add three optional Guided Experiments: hide/restore confidence bands, add prespecified 12/24-month estimates, and change the display horizon without changing the analysis data. Interpretation copy is produced from controlled, state-aware templates backed by structured results. Include an expandable source/methodology section and a fixed escalation message.

The approved first-draft English copy, dataset contract, callouts, experiments, templates, and source links are in [Kaplan–Meier Learning Journey — First-Draft Copy](../content/km-learning-journey.md).

# Define the Guided Analysis Module Contract

Type: grilling
Status: resolved
Label: `wayfinder:grilling`
Blocked by: 02, 03, 05, 06

## Question

What technical interface should each Guided Analysis module implement to supply stages, content, Demonstration Datasets, Analysis Roles, validation, controls, computation requests, structured results, Interpretation Guidance, and Analysis Handoff while preserving the static browser/webR architecture?

## Answer

Use one reusable JavaScript Guided Analysis shell that owns stage navigation, in-memory Analysis Session state, URL synchronization, standard operational states, and result placement. Each method module supplies its labels, teaching content/visual, versioned Demonstration Dataset, Analysis Roles and suggestions, Analysis Definition fields, suitability questions, browser preflight, controls, request construction, Interpretation Guidance templates, and handoff templates.

Keep the JSON worker boundary as the only computation seam. R performs authoritative validation and returns a versioned structured Analysis Result plus SVG. The result carries provenance, counts, curve/risk-table data, estimates, comparisons, diagnostics/findings, display metadata, and semantic handoff values. Existing analyses retain the legacy SVG/text contract through backward-compatible dispatch normalization.

See [Guided Analysis with a Kaplan–Meier Pilot](../PRD.md), especially **Reusable module boundary** and **Computation contract**, and WP1/WP2 in the [Final Implementation Plan](../../../docs/superpowers/plans/2026-07-14-guided-analysis-km.md).

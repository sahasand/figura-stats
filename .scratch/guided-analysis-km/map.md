# Specify a Reusable Guided Analysis with a Kaplan–Meier Pilot

Label: `wayfinder:map`

## Destination

Produce an implementation-ready written product, UX, statistical-content, and technical specification for a reusable Guided Analysis pattern, instantiated completely by a Kaplan–Meier pilot. The specification enables a non-R clinical researcher to optionally learn, try the full workflow with synthetic data, analyze private user data through Analysis Roles, understand the result and its limitations, and complete an Analysis Handoff.

## Notes

- Planning only: the destination is the approved written specification, not a prototype or production implementation.
- Primary user: a clinical researcher who understands study concepts, can prepare a basic CSV, and is not comfortable using R.
- Shared pattern: optional **Understand**, **Try an Example**, and **Analyze Your Data** stages; experienced users may skip directly to their data.
- Kaplan–Meier is the only fully specified method in this effort. Other methods are compatibility checks for the shared pattern, not content deliverables.
- The Demonstration Dataset is synthetic, clearly labeled, and uses the same controls and computation as user data.
- Teaching is concise and contextual. First-draft user-facing copy and Interpretation Guidance are part of the specification; a comprehensive statistics course is not.
- User data remains within an ephemeral Analysis Session in one browser tab. There is no data upload or browser persistence.
- The baseline Analysis Handoff is downloadable SVG plus copyable methods/results text.
- Every session should read `CONTEXT.md`, relevant files under `docs/agents/`, and the current code/docs it is changing or specifying.
- Use `/grilling` and `/domain-modeling` for human-in-the-loop decisions. Research must favor authoritative primary clinical/statistical sources and preserve source links in its asset.
- Record newly resolved domain terms in `CONTEXT.md` immediately.

## Decisions so far

- [Establish the Kaplan–Meier Reporting Baseline](issues/01-establish-km-reporting-baseline.md) — Require explicit analysis semantics, strict preflight validation, uncertainty and risk-set context, qualified comparisons, and warnings that remain attached to the Analysis Handoff.
- [Design the Optional Guided Analysis Journey](issues/02-design-optional-guided-journey.md) — Use directly selectable Guided Stage tabs with optional Back/Next, preserved in-session context, separate example/user results, stage-local operational states, and clean privacy-aware resets.
- [Define the Reusable Data and Validation Experience](issues/03-define-data-validation-experience.md) — Use a read-only, role-mapped CSV pipeline with explicit analysis semantics, method suitability screening, progressive three-severity preflight, no silent data changes, transactional replacement, and legible local-processing privacy.
- [Write the Kaplan–Meier Learning Journey and Demonstration Story](issues/04-write-km-learning-journey.md) — Teach one nuanced synthetic study through concise English copy, contextual Learning Callouts, reversible Guided Experiments, deterministic interpretation templates, and explicit method boundaries.
- [Design Results, Interpretation, and Analysis Handoff](issues/05-design-results-and-handoff.md) — Present one structured, status-bearing Analysis Result from provenance through limitations, keep the SVG clean while mandatory handoff text carries warnings, and provide deterministic manuscript-ready copy actions.
- [Set the Cross-Cutting Quality Bar](issues/06-set-quality-bar.md) — Target WCAG 2.2 AA, verified local-only privacy, resilient slow/failing webR states, an evidence-gated browser cap, pinned statistical correctness, and browser-level workflow coverage.
- [Define the Guided Analysis Module Contract](issues/07-define-module-contract.md) — Use a reusable JavaScript journey/session shell around method modules and a backward-compatible worker boundary returning an authoritative, structured R Analysis Result.
- [Assemble and Approve the Guided Analysis Specification](issues/08-assemble-specification.md) — Consolidate every decision into the ready-for-agent [canonical PRD](PRD.md) and the finite [Final Implementation Plan](../../docs/superpowers/plans/2026-07-14-guided-analysis-km.md).

## Not yet specified

<!-- No remaining fog at this frontier. The content-authoring contract is now a precise part of Define the Guided Analysis Module Contract. -->

## Out of scope

- Production implementation, implementation sequencing, and deployment.
- Interactive prototypes and usability testing; these may follow the written specification as a separate effort.
- Guided teaching content for analyses other than Kaplan–Meier.
- A comprehensive survival-analysis course or individualized statistical advice.
- Server-side processing, analytics involving user data, accounts, saved projects, or cross-session browser persistence.
- PNG export, document/report generation, and other handoff formats beyond SVG plus copyable text.

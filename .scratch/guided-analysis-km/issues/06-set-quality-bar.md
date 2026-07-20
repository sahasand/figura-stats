# Set the Cross-Cutting Quality Bar

Type: grilling
Status: resolved
Label: `wayfinder:grilling`
Blocked by: 02, 03, 05

## Question

Which explicit, testable acceptance criteria must the specification set for keyboard and screen-reader accessibility, responsive behavior, slow webR loading, error recovery, privacy verification, statistical correctness, and end-to-end coverage?

## Answer

The final PRD sets WCAG 2.2 AA as the target, requires complete keyboard operation and semantic/status behavior, defines 200% zoom and 320 CSS-pixel responsive gates, keeps the shell responsive during worker activity, requires phased loading and retry without data loss, and caps the pilot at 5 MB or 50,000 rows subject to a release benchmark that may only lower the cap.

Privacy is verified with a unique sentinel dataset and network interception. Statistical correctness is pinned at the R boundary with fixed expected outputs and WARN 0. Browser coverage exercises both complete demo and user workflows, blocker recovery, stale results, handoff, slow/failing runtime states, accessibility, narrow layout, and Clear My Data.

See [Guided Analysis with a Kaplan–Meier Pilot](../PRD.md), especially **Quality bar** and **Testing Decisions**, and the finite execution gates in the [Final Implementation Plan](../../../docs/superpowers/plans/2026-07-14-guided-analysis-km.md).

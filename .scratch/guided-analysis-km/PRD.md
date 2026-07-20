# Guided Analysis with a Kaplan–Meier Pilot

Status: ready-for-agent  
Date: 2026-07-14  
Product: Clinical Analysis Workbench

## Problem Statement

The current Kaplan–Meier feature assumes that a user already knows the required CSV column names, event coding, statistical method, and interpretation. It accepts a fixed `time,status,group` file, performs minimal validation, and returns only a plot plus a short statistical sentence. A clinical researcher who understands their study but does not use R cannot safely verify whether the method fits, define the endpoint and censoring semantics, understand uncertainty and risk-set support, recover from data problems, or carry the result into a manuscript with its methods and limitations intact.

The current Figure/Console output also separates the picture from the provenance, diagnostics, interpretation, and reusable wording needed for responsible reporting. As a result, a technically valid calculation can still be difficult to understand or easy to misuse.

## Solution

Introduce **Guided Analysis**, a reusable learn-try-analyze pattern for statistical methods, and instantiate it fully for Kaplan–Meier analysis.

The Kaplan–Meier pilot has three freely selectable **Guided Stages**:

- **Understand** teaches what the method answers, when it fits, what data it needs, and how to read its output.
- **Try an Example** runs one fixed synthetic Demonstration Dataset through the real analysis pipeline, with optional learning experiments.
- **Analyze Your Data** accepts a local CSV, lets the user map columns to Analysis Roles, requires an explicit Analysis Definition and Method Suitability Check, performs progressive Analysis Preflight, and runs only when the data and meaning are ready.

The output becomes one structured **Analysis Result** containing provenance, findings, a publication-ready figure, descriptive estimates, qualified comparisons, diagnostics, deterministic Interpretation Guidance, and an **Analysis Handoff**. The handoff provides a clean SVG and reproducible Methods, Results, and combined text while preserving required warnings outside the image.

The entire workflow remains a static browser application. User data is held only in the current browser tab and is never uploaded. JavaScript owns interaction and presentation; R in webR remains the authoritative statistical engine.

## User Stories

1. As a clinical researcher new to survival analysis, I want a concise introduction before I upload data, so that I understand what Kaplan–Meier analysis can answer.
2. As an experienced researcher, I want to skip teaching and go directly to my data, so that guidance does not slow routine work.
3. As a user, I want all Guided Stages to remain freely selectable, so that I can revisit an explanation or example without losing work.
4. As a returning in-tab user, I want the last selected stage and its state restored, so that navigating between analyses does not reset my session.
5. As a user sharing a URL, I want the analysis and Guided Stage represented in the URL without data or settings, so that links are useful but private.
6. As a learner, I want a clearly non-data Teaching Visual, so that I can learn curve steps, censor marks, confidence bands, medians, and risk tables without mistaking an illustration for evidence.
7. As a learner, I want one realistic synthetic study, so that the example has a coherent endpoint, population, censoring rule, and comparison.
8. As a learner, I want the example to use the production computation path, so that the tutorial demonstrates the real workflow rather than a canned output.
9. As a learner, I want optional reversible experiments, so that I can see confidence bands, landmark estimates, and display horizons without damaging the example.
10. As a user, I want demonstration assets labeled as synthetic everywhere they can be reused, so that they cannot be mistaken for clinical evidence.
11. As a researcher, I want to choose a CSV by file picker or drag-and-drop, so that data loading feels familiar.
12. As a researcher, I want a downloadable CSV template, so that I can prepare compatible data without guessing column names or coding.
13. As a researcher, I want standards-compliant CSV parsing, so that quoted values, commas, line endings, and escaped quotes are handled safely.
14. As a researcher, I want a read-only Data Preview, so that I can verify the imported source without the app silently changing it.
15. As a researcher, I want suggested Analysis Roles based on names and types, so that mapping is faster without making inference authoritative.
16. As a researcher, I want every column to remain selectable for a role, so that unconventional but valid datasets are not rejected by superficial type inference.
17. As a researcher, I want to explicitly map event and censored values with counts, so that the analysis cannot silently reverse their meaning.
18. As a researcher, I want group display labels separated from source values, so that manuscript labels can be readable without modifying the uploaded data.
19. As a researcher, I want an optional participant identifier role, so that duplicate participant rows can be detected when identifiers exist.
20. As a researcher without an identifier column, I want to confirm that each row is independent, so that a key modeling assumption is explicit.
21. As a researcher, I want to define the endpoint, time origin and unit, censoring rule, population, and comparison, so that the result has scientific meaning beyond column names.
22. As a researcher, I want a Method Suitability Check, so that competing events, delayed entry, repeated records, and other unsupported structures are caught before interpretation.
23. As a researcher, I want validation findings grouped as Blockers, Confirmations, and Notices, so that I know which problems prevent analysis and which require judgment.
24. As a researcher, I want every invalid source value identified by row and column, so that I can correct my CSV rather than accept a hidden exclusion.
25. As a researcher, I want no automatic row deletion or repair, so that analyzed counts always match a source I can audit.
26. As a researcher, I want a final Ready to analyze summary, so that I can verify roles, counts, event meaning, groups, reference direction, definitions, and accepted findings before computation.
27. As a researcher replacing a dataset, I want the candidate parsed before replacement is committed, so that a bad file does not destroy working state.
28. As a user, I want clear local-processing language near the loader and result, so that I understand the privacy boundary.
29. As a user, I want Clear My Data to remove user-data state without removing teaching or demo content, so that I can deliberately end the sensitive part of the session.
30. As a researcher, I want a single-group descriptive analysis when no group is mapped, so that comparison is optional.
31. As a researcher, I want a two-group log-rank comparison and optional directed unadjusted hazard ratio only when supported, so that inferential output matches the analysis structure.
32. As a researcher with more than two groups, I want an omnibus log-rank result without automatic pairwise claims, so that multiplicity and direction are not hidden.
33. As a researcher, I want unsupported or unreliable comparisons explicitly withheld with reasons, so that a blank value is not mistaken for a software failure.
34. As a reader, I want curves, pointwise confidence intervals, censor marks, and a number-at-risk table together, so that I can judge uncertainty and diminishing support.
35. As a reader, I want accessible group encodings that do not rely on color alone, so that the figure remains distinguishable in grayscale and with color-vision differences.
36. As a reader, I want counts and survival estimates before p-values and hazard ratios, so that inference does not become the headline.
37. As a reader, I want landmark estimates and medians with confidence intervals and explicit not-reached states, so that the app does not extrapolate unavailable values.
38. As a reader, I want validation findings beside the affected statistic as well as in a summary, so that limitations remain connected to their consequence.
39. As a reader, I want deterministic Interpretation Guidance, so that the explanation is consistent with the computed result and avoids invented claims.
40. As a researcher, I want a persistent result provenance header, so that I can identify the data source, status, endpoint, population, comparison, and data cutoff while reading.
41. As a researcher who changes an input, I want the prior result marked Out of date immediately, so that I cannot reuse a result that no longer matches its settings.
42. As a researcher, I want an accessible table of plotted values and numbers at risk, so that I can inspect the figure without relying on vision alone.
43. As a manuscript author, I want to download a clean SVG, so that I can reuse a publication-ready vector figure.
44. As a manuscript author, I want to preview and copy reproducible Methods wording, so that the actual estimator, definitions, comparisons, and diagnostics are recorded.
45. As a manuscript author, I want to preview and copy controlled Results wording, so that counts, estimates, uncertainty, comparisons, and limitations agree with the screen.
46. As a manuscript author, I want a Complete Handoff containing the Analysis Definition, Methods, Results, required interpretation notes, and figure-use note, so that warnings remain attached to a clean SVG.
47. As a Word or Google Docs user, I want semantic formatted copy plus a plain-text fallback, so that handoff content pastes cleanly across applications.
48. As a user, I want clear progress during initial webR and package loading, so that a slow first run does not look frozen.
49. As a user, I want navigation and current inputs to remain usable while computation runs, so that background statistical work does not lock the interface.
50. As a keyboard or screen-reader user, I want the entire journey, validation, results, and handoff operable and understandable without a pointer, so that the feature is independently usable.
51. As a mobile user, I want the same stages and result order in a responsive layout, so that the workflow remains coherent on a narrow screen.
52. As a maintainer, I want every representation to derive from one structured Analysis Result, so that the screen, SVG, tables, and copied text cannot drift.
53. As a maintainer, I want the Guided Analysis shell driven by a method module contract, so that later methods can reuse the journey without duplicating orchestration.
54. As a maintainer, I want browser-level workflow tests and focused R statistical tests, so that user behavior and numerical correctness fail at stable seams.

## Implementation Decisions

### Product and navigation

- Guided Analysis is embedded in the existing workbench rather than created as a separate application.
- Understand, Try an Example, and Analyze Your Data are peer tabs with optional Back/Next actions; there is no locked wizard progression or completion percentage.
- The first Kaplan–Meier visit in a browser tab opens Understand. In-session state is maintained separately for example and user data.
- The URL records only the selected analysis and stage. Reloading creates a clean Analysis Session.
- Moving between stages remains possible during computation. Work and errors stay attached to their originating stage.

### Reusable module boundary

- A Guided Analysis shell owns stage navigation, per-stage operational state, in-memory session state, URL synchronization, standard empty/loading/error/out-of-date states, and Analysis Result placement.
- Each method module supplies identity and labels, teaching content, a Teaching Visual, a versioned Demonstration Dataset, Analysis Role definitions and suggestions, Analysis Definition fields, suitability questions, browser preflight rules, analysis controls, request construction, result interpretation templates, and handoff templates.
- The shell calls a small module interface rather than branching on Kaplan–Meier throughout the application. Kaplan–Meier is the only complete module in this release.
- Session data is held in memory only. No localStorage, IndexedDB, service-worker cache of user data, account, project, or server persistence is introduced.

### Data and validation

- User input is CSV only. Parsing supports the common CSV standard, including quoted delimiters, escaped quotes, embedded line breaks, UTF-8 BOM, and CRLF.
- Data Preview is read-only and shows the filename, dimensions, inferred types, and first 10 source rows.
- Follow-up time and event status are required Analysis Roles. Group and participant identifier are optional.
- Suggestions rank likely columns but never remove columns from selection. Users explicitly confirm the final mapping.
- Event values are explicitly assigned Event or Censored. Missing status blocks. More than two nonblank status values blocks this pilot as a potentially unsupported event structure.
- Analysis Definition and Method Suitability Check are required before computation.
- Browser preflight provides immediate guidance; R repeats authoritative validation before statistics. The R result is authoritative if the two layers disagree.
- Invalid records are not silently excluded, repaired, imputed, coerced, or edited. Blockers identify the source locations that must be fixed and reloaded.
- Replacing user data is transactional. A successful replacement resets user mappings and preflight and makes prior user output Out of date.
- The pilot accepts at most 5 MB or 50,000 data rows, whichever is reached first. Oversized files are refused before computation with a template and reduction guidance. This cap is verified under the supported-browser test profile before release and may be lowered, but not raised, without new performance evidence.

### Computation contract

- R/webR is the only source of statistical estimates, intervals, tests, diagnostics, and figure coordinates.
- The existing JSON request/worker boundary remains. Requests add explicit roles, analysis definitions, mappings, accepted confirmations, and options.
- The dispatcher remains backward compatible for existing analyses while allowing Kaplan–Meier to return a structured Analysis Result in addition to SVG.
- A successful Analysis Result contains a schema version, module version, source kind, normalized analysis definition, provenance, counts, curve/risk-table data, landmark and median estimates, comparison results, diagnostics/findings, display metadata, and handoff-ready semantic values.
- Narrative strings are assembled from controlled templates using structured values. Display strings are never parsed back into calculations.
- Result replacement is atomic. A failed run leaves the previous successful result visible with an accurate status.

### Kaplan–Meier statistical behavior

- Require one independent row per participant, non-negative finite follow-up time, an explicit binary event mapping, and ordinary right censoring.
- Support an ungrouped descriptive curve, a two-group comparison, and a multi-group omnibus comparison.
- Report participant/event/censor counts by group, selected landmark survival estimates with pointwise 95% confidence intervals and numbers at risk, and median survival with a 95% confidence interval or explicit not-reached/not-estimable states.
- Report ordinary log-rank chi-square, degrees of freedom, and two-sided p-value when valid.
- Offer an optional unadjusted Cox hazard ratio only for two groups with explicit numerator/reference direction. Report its 95% confidence interval, tie method, and proportional-hazards assessment.
- Withhold comparisons when events or model conditions do not support them; preserve valid descriptive output.
- Surface sparse-tail, crossing-curve, proportional-hazards, estimability, and accepted-preflight limitations without claiming that diagnostics prove assumptions.
- Use a fixed, versioned 120-participant synthetic Demonstration Dataset with the approved fictional overall-survival story and pinned expected outputs.

### Result and handoff

- Replace Figure/Console with one scrollable Analysis Result in the approved order: persistent header, findings, figure, overview, estimates, comparison, diagnostics, Interpretation Guidance, and Analysis Handoff.
- The figure includes curves, pointwise confidence bands, censor marks, accessible encodings, axes, labels, group sizes, risk table, and concise caption.
- The downloaded SVG remains visually clean. Required warnings and fuller provenance travel in the adjacent figure-use note and Complete Handoff text, not inside the graphic.
- Provide View figure data semantic tables below the SVG.
- Provide Download SVG, Copy Methods, Copy Results, and Copy Complete Handoff with exact previews and accessible success/failure feedback.
- Clipboard output provides equivalent semantic HTML and plain text.
- Out-of-date Results remain inspectable but disable every handoff action until rerun.
- Use the approved precision policy: integer counts; one decimal for survival and time; two decimals for hazard ratios; matched confidence-limit precision; p-values to three decimals with `p < 0.001` below that threshold.
- Use privacy-conscious SVG filenames and mandatory synthetic-data labeling for demonstration artifacts.
- Machine-readable user downloads are not included in this pilot.

### Quality bar

- Target WCAG 2.2 AA for the complete Guided Analysis workflow. Use native elements and semantic tabs, tables, headings, findings, status, and dialogs wherever possible.
- Every action is keyboard reachable; focus order follows visual order; focus is visible; stage changes and dynamic status are announced; errors focus the first actionable problem; no meaning relies on color, hover, position, or SVG alone.
- At 200% browser zoom the desktop workflow remains usable without clipped content. At a 320 CSS-pixel viewport, Guided Stage tabs scroll horizontally, controls remain at least 44 by 44 CSS pixels where practical, and the result preserves its information order without page-level horizontal scrolling.
- The application shell and stage navigation become interactive independently of webR. Starting work produces visible status within 100 ms. Navigation and input editing remain responsive while the worker loads or computes.
- Disable duplicate Run actions for one stage. Expose ordered phases for runtime initialization, package loading, validation, computation, and result preparation; show a retry path after failure without clearing inputs.
- Privacy verification intercepts browser network traffic during a uniquely marked CSV run and proves that marker never appears in a request URL, headers, or body. Expected static/CDN GETs are allowlisted; user data is never transmitted.
- Clear My Data removes all user-data objects and user-result DOM content synchronously, revokes generated object URLs, and returns the user stage to its initial state.
- No unhandled exceptions, R warnings hidden as success, partial result updates, or raw R tracebacks reach users.

## Testing Decisions

- The primary test seam is the browser workflow: select Kaplan–Meier, navigate Guided Stages, run the example or load a CSV, complete preflight, compute, inspect the Analysis Result, and use handoff actions. Tests assert visible behavior rather than private DOM structure or internal state variables.
- The second seam is the pure R Kaplan–Meier function and JSON dispatcher. These tests pin exact counts and numerical estimates before browser formatting and cover every supported/withheld state.
- Pure JavaScript tests cover standards-compliant CSV parsing, role suggestions, preflight classification, session state transitions, deterministic copy templates, precision, and filename sanitization. These modules remain free of browser-only imports where practical.
- Statistical correctness tests use fixed datasets with independently verified expected counts, survival estimates, confidence intervals, medians, log-rank results, hazard ratios, and proportional-hazards diagnostics. The versioned Demonstration Dataset has a complete pinned result fixture.
- Dispatcher contract tests prove that legacy analyses still return their existing SVG/text payload and that structured Kaplan–Meier results serialize without losing missing/not-estimable states.
- Playwright covers at least: first entry and stage navigation; full demonstration run; full user CSV run; blocker recovery; optional ungrouped analysis; out-of-date behavior; handoff copy/download; slow loading/retry; narrow viewport; keyboard-only traversal; and network privacy.
- Accessibility automation checks obvious WCAG violations, but the release gate also includes manual keyboard, screen-reader announcement, 200% zoom, grayscale/contrast, and 320-pixel viewport checks.
- SVG tests verify accessible title/description, no external resource references, expected risk-table text, deterministic labels, and legibility without color. They do not snapshot the entire SVG byte-for-byte.
- All tests run from stable commands documented in the implementation plan. Existing analysis tests remain green. R tests have WARN 0 as a hard gate.

## Out of Scope

- Guided teaching content or complete Guided Analysis modules for methods other than Kaplan–Meier.
- A comprehensive survival-analysis course, individualized statistical advice, or causal interpretation.
- Competing-risk, delayed-entry, interval-censored, recurrent-event, multi-state, clustered, weighted, adjusted, or time-varying survival models.
- Automatic pairwise tests for more than two groups or multiplicity adjustment.
- Excel workbooks, pasted tables, multi-file input, in-app cell editing, automatic cleaning, imputation, or row exclusion.
- Accounts, cloud saving, browser persistence across reloads, collaboration, analytics involving user data, or server-side computation.
- PNG, PDF, Word, report generation, CSV/JSON result export, or raw numerical downloads.
- Production analytics, telemetry on user datasets, localization beyond the approved English copy, and deployment changes.
- Refactoring the other statistical analyses into Guided Analysis during this pilot.

## Further Notes

- The approved first-draft teaching copy is in `content/km-learning-journey.md` within this feature's tracker directory.
- The approved result and handoff contract is in `content/km-results-handoff.md`.
- The reporting baseline and primary-source links are in `research/km-reporting-baseline.md`.
- `CONTEXT.md` is the source of truth for domain terminology.
- Where this PRD conflicts with the older clinical-figures design, this PRD governs Kaplan–Meier only. Existing analyses retain their current behavior.

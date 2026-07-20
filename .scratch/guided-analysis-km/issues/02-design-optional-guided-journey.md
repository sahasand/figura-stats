# Design the Optional Guided Analysis Journey

Type: grilling
Status: resolved
Label: `wayfinder:grilling`

## Question

How should the reusable **Understand**, **Try an Example**, and **Analyze Your Data** stages appear and behave inside the current workbench so first-time users receive orientation while experienced users can skip, move between stages, and remain aware of context?

## Answer

Use three persistent **Guided Stage** tabs at the top of the Configuration pane: **Understand**, **Try an Example**, and **Analyze Your Data**. They are peer destinations, not mandatory wizard steps. Users may select any tab directly; Back/Next actions provide an optional suggested sequence without locking access. The tab strip communicates only operational state—active, working, result ready, error, or out of date—never completion percentages or mandatory progress.

On first entry to Kaplan–Meier in an Analysis Session, open **Understand**. If the user switches analyses and returns within the same browser tab, restore the last active Guided Stage and all in-session inputs, mappings, validation state, and results. Reflect the selected analysis and stage in the URL, but never include user data or settings; a reload or shared URL opens that stage with a clean Analysis Session.

**Understand** is one concise scrollable orientation page with progressive-disclosure sections covering what the method answers, when it is or is not appropriate, required data, and how to interpret the output. It ends with equal paths to the example or user-data stages. The persistent Output pane shows a clearly non-data Teaching Visual rather than an empty state or computed result.

**Try an Example** presents the synthetic scenario and preselected Analysis Roles, then requires an explicit **Run Example Analysis** action before webR downloads or computes. The Demonstration Dataset is read-only, while the same analysis/display controls available for user data may be changed and rerun. **Reset Example** restores teaching defaults. Example output is retained separately and labeled as originating from the Demonstration Dataset.

Moving to **Analyze Your Data** starts clean: endpoint meaning, event mapping, reference group, and Analysis Roles never transfer automatically from the example. The stage is one scrollable working page with a compact checklist: **Choose data → Assign Analysis Roles → Review Analysis Preflight → Run analysis**. Users may revisit completed sections, but computation remains unavailable until required preflight conditions pass. Its output is retained separately and labeled as user-data output.

Users may change Guided Stages while webR is running. The originating stage shows working and result-ready states and restores progress/result on return. Errors stay attached to their stage, preserve inputs, and focus the first actionable problem when the user returns. If source data, roles, definitions, or settings change after computation, keep the prior output visible as an **Out-of-date Result** and disable Analysis Handoff actions until rerun.

Provide a confirmed **Clear My Data** action that removes only uploaded data, mappings, preflight state, and user-data results; it does not reset the Teaching Visual or Demonstration Dataset. On narrow screens, retain the visible stage model as a horizontally scrollable tab strip that brings the active stage into view, with Back/Next below the content.

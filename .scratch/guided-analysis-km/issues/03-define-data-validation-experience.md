# Define the Reusable Data and Validation Experience

Type: grilling
Status: resolved
Label: `wayfinder:grilling`

## Question

How should a Guided Analysis load and switch between synthetic and user data, preview the dataset, map columns to Analysis Roles, validate method-specific requirements, explain and recover from problems, preserve in-tab work, and make the privacy boundary legible?

## Answer

The first Guided Analysis accepts user data only as CSV through one drag-and-drop/file-selection surface, using standards-compliant parsing and offering a downloadable template. Excel workbooks, pasted tables, and multi-file inputs are deferred. After parsing, show a read-only **Data Preview** with filename, row/column counts, inferred types, and the first 10 source rows; the app never edits source cells.

Analysis Role mapping suggests likely columns from header names and inferred types but requires explicit confirmation. Every column remains selectable—ranked likely matches and type hints aid selection, while Analysis Preflight makes the final validity decision. For Kaplan–Meier, follow-up time and event status are required; group and Participant ID are optional. Event values are displayed with counts and explicitly labeled Event or Censored. One observed value is allowed with limitations, two is normal, and more than two nonblank values block the pilot as potentially competing-event or multi-state data. Missing status values are blockers.

When group is mapped, show levels and counts and permit separate human-readable display labels without changing source data. Group remains optional for a single descriptive curve. A two-group hazard ratio requires an explicit comparison/reference direction. Participant ID enables duplicate detection; duplicate IDs block because the pilot supports one independent row per analysis unit. Without an ID, the user explicitly confirms that each row is independent.

Require an **Analysis Definition** naming the endpoint/event, time origin, time unit, censoring rule, and analysis population. Also require a **Method Suitability Check** confirming one independent row per participant, one follow-up time, ordinary right censoring, and the absence of delayed-entry, recurrent-event, multi-state, clustered/repeated-row, or competing-event structure. A No or Unsure response blocks this pilot and explains that a specialist method may be needed.

Validation is progressive: parser findings appear after loading, role-specific findings update as mappings/definitions change, the final summary appears automatically when required inputs exist, and R repeats authoritative checks at computation. **Preflight Findings** have three severities: Blocker (must fix), Confirmation (unusual but potentially valid and explicitly accepted), and Notice (non-blocking context). Invalid rows are never silently repaired, dropped, or excluded in the app; findings identify exact source rows, columns, values, and correction guidance so users fix and reload the CSV. Repeated findings are grouped while every occurrence remains inspectable and linked to its Data Preview row.

The final **Ready to analyze** summary shows included rows, role mappings, event/censor counts, group counts and reference, follow-up range/unit, Analysis Definition, accepted confirmations, and remaining notices. No generic agreement checkbox is used. Analysis options adapt visibly: no group yields descriptive output only; two groups permit optional log-rank and a directed unadjusted HR; more than two permit an omnibus log-rank but no automatic pairwise tests or single HR. Zero-event or unreliable comparisons are visibly withheld while valid descriptive output remains available.

Replacing an existing dataset is transactional: parse and summarize the candidate file before a confirmed **Replace Dataset** action; failures/cancellation preserve current work. Confirmation resets mappings/preflight and makes prior output an Out-of-date Result. Numerical browser limits are set later through performance evidence, while this experience requires early file-size checks, progress feedback, and clear refusal at the tested cap.

Privacy is explicit beside the loader and throughout the stage: files are processed locally and never uploaded; webR may download packages without sending the dataset; closing the tab ends the Analysis Session; and Clear My Data removes the user-data context. The Demonstration Dataset passes visibly through the identical Data Preview, role mapping, Method Suitability Check, progressive validation, and Analysis Preflight pipeline, but arrives prefilled and annotated.

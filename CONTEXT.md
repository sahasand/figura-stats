# Clinical Analysis Workbench

A browser-based environment that helps people understand and perform statistical analyses for clinical manuscripts without uploading their data.

## Language

**Guided Analysis**:
A reusable learning-and-doing journey for one statistical method: understand the method, explore it with demonstration data, then apply the same workflow to the user's own data.
_Avoid_: Tutorial, wizard

**Guided Stage**:
A directly selectable part of a Guided Analysis, connected to the other stages by optional Back/Next actions but never locked behind mandatory completion.
_Avoid_: Wizard step, prerequisite gate

**Demonstration Dataset**:
A built-in, realistic dataset that runs through the same analysis controls and computation as user-provided data.
_Avoid_: Sample output, mock analysis

**Demonstration Story**:
The clearly fictional clinical framing that gives a Demonstration Dataset its endpoint, time origin, censoring rule, population, and comparison meaning.
_Avoid_: Real study, evidence claim

**Teaching Visual**:
A clearly non-data illustration used to explain how to read an analysis output; it is never presented as a computed result.
_Avoid_: Demonstration result, analysis output

**Learning Callout**:
A contextual, non-blocking explanation attached to the part of a Guided Analysis the user is currently viewing; it can be collapsed and reopened.
_Avoid_: Modal tour, mandatory lesson

**Guided Experiment**:
An optional, reversible change to Demonstration Dataset controls that lets a user observe how an analysis choice affects the result without altering the source data.
_Avoid_: Test, required exercise

**Analysis Role**:
The meaning a dataset column has within a particular statistical method, such as follow-up time, event status, or comparison group.
_Avoid_: Required column name, field type

**Data Preview**:
A read-only inspection of a loaded dataset's shape, inferred column types, and representative rows before analysis; it never edits or transforms the source data.
_Avoid_: Spreadsheet, data editor

**Interpretation Guidance**:
Concise, analysis-specific help explaining what a result supports, its important assumptions and limitations, and when the user should seek deeper statistical review.
_Avoid_: Automated conclusion, statistical advice

**Analysis Handoff**:
The explicit transition from an on-screen result to reusable manuscript assets, beginning with a downloadable figure and copyable methods/results text.
_Avoid_: Export screen, report generation

**Out-of-date Result**:
A previously computed result whose data, Analysis Roles, definitions, or settings have since changed; it may remain visible for reference but cannot enter an Analysis Handoff until recomputed.
_Avoid_: Current result, reusable result

**Analysis Session**:
The temporary data, role mappings, choices, and results held within one browser tab while a user performs an analysis; it ends when the tab closes.
_Avoid_: Project, saved analysis

**Analysis Preflight**:
The review before computation that confirms Analysis Roles and event meaning, validates every included row, and makes counts, exclusions, warnings, and unsupported data structures explicit.
_Avoid_: Automatic cleanup, silent repair

**Method Suitability Check**:
A user-confirmed screening of whether the scientific question and data structure fit the supported statistical method, including boundaries the dataset alone cannot reveal.
_Avoid_: Automatic method selection, assumption proof

**Preflight Finding**:
A validation result classified as a blocker that must be fixed, a confirmation that requires explicit acceptance, or a notice that provides non-blocking context.
_Avoid_: Generic warning, silent correction

**Analysis Definition**:
The user-confirmed scientific meaning of an analysis—its endpoint, time origin and unit, censoring rule, population, and comparison context—which remains attached to the result and handoff.
_Avoid_: Column metadata, inferred description

**Analysis Result**:
The structured, status-bearing output of one successful analysis run, including its provenance, figure, statistics, findings, diagnostics, and Interpretation Guidance; all on-screen and handoff forms derive from this same result.
_Avoid_: Plot alone, console output, partially refreshed result

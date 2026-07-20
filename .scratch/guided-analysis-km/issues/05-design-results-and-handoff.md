# Design Results, Interpretation, and Analysis Handoff

Type: grilling
Status: resolved
Label: `wayfinder:grilling`
Blocked by: 01, 02, 03

## Question

How should the Kaplan–Meier figure, required statistics, validation notices, Interpretation Guidance, methods/results wording, SVG download, and copy actions be organized so the result is understandable, responsible, and ready to reuse in a manuscript?

## Answer

Use one scrollable **Analysis Result** rather than separate Figure/Console tabs. Keep a persistent provenance and status header, then present a findings summary, publication-ready figure, group overview, survival estimates, qualified comparisons, diagnostics and limitations, Interpretation Guidance, and Analysis Handoff in that fixed order. Findings appear both in the top summary and beside affected results. Out-of-date Results remain inspectable but cannot be copied or downloaded.

Keep the downloadable SVG clean: curves, pointwise confidence intervals, censor marks, accessible group encodings, axes, legend, a real number-at-risk table, and a concise analysis caption. Do not print validity warnings inside the graphic. Instead, make a mandatory adjacent **Use with this figure** note carry warnings and fuller provenance into copied Complete Handoff text. Provide an accessible on-screen disclosure containing the plotted estimates and risk-table data.

Order statistics from description to inference: group counts and follow-up context; landmark and median estimates with uncertainty; ordinary log-rank and an optional directed unadjusted HR only when supported; then diagnostics and limitations. Use deterministic Interpretation Guidance and manuscript wording, never free-form or causal conclusions. Explicitly represent not-reached, not-estimable, and withheld states.

Provide four actions: **Download SVG**, **Copy Methods**, **Copy Results**, and **Copy Complete Handoff**. Copy simple semantic HTML plus equivalent plain text, preview every payload, and provide accessible success/failure recovery. Methods capture the actual reproducible analysis choices; Results follow the on-screen order; Complete Handoff combines the Analysis Definition, Methods, Results, required interpretation notes, and figure-use note. Use consistent declared precision and privacy-conscious filenames. Keep demo handoff enabled but label every artifact **Synthetic demonstration data — not for clinical use.** Machine-readable downloads remain out of scope, while every representation derives from one structured internal result.

The complete layout, content, state, precision, filename, demonstration, and acceptance contract is in [Kaplan–Meier Result and Analysis Handoff](../content/km-results-handoff.md).

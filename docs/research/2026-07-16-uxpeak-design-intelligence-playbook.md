# UXPeak-inspired UI/UX design intelligence playbook

**Date:** 2026-07-16  
**Product context:** Figura, a browser-based clinical analysis workbench  
**Status:** Working design standard  

## Purpose

This playbook turns the publicly documented UXPeak philosophy into an
operational decision system for Figura. It is intended to help designers,
engineers, reviewers, and AI agents make consistent UI/UX decisions.

This is an original synthesis of UXPeak's public website and public articles.
It does not reproduce the paid UI/UX Playbook or private course material.

## The philosophy in one sentence

**Make the user's next useful decision obvious, inexpensive, trustworthy, and
visually calm.**

UXPeak consistently treats visual polish as the surface of a deeper product
discipline. Spacing, hierarchy, contrast, copy, and interaction details should
make a screen clear and trustworthy; flows should remove friction; retention
and conversion should follow from users understanding value and acting with
confidence. Their teaching method reinforces the same philosophy through real
product breakdowns, before/after comparisons, common mistakes, decision
frameworks, and practical exercises.
([UXPeak platform](https://www.uxpeak.com/),
[About UXPeak](https://www.uxpeak.com/pages/about),
[UI/UX Playbook overview](https://www.uxpeak.com/pages/playbook))

## What “design intelligence” means

Design intelligence is not a preferred visual style. It is the ability to:

1. identify the user's real goal;
2. rank the information and actions that support that goal;
3. remove unnecessary cognitive, physical, and time effort;
4. encode the remaining priority through layout and visual hierarchy;
5. communicate system state in an actionable form;
6. anticipate failure and provide recovery;
7. judge whether the result is clearer and more useful than the previous
   version.

This model reflects UXPeak's focus on practical reasoning, real examples,
before/after redesigns, trade-offs, and design taste rather than abstract theory
or surface cleanliness alone.
([About UXPeak](https://www.uxpeak.com/pages/about),
[UXPeak platform](https://www.uxpeak.com/))

```text
User goal
   ↓
Information priority
   ↓
Lowest-cost useful flow
   ↓
Visual hierarchy
   ↓
State, trust, and recovery
   ↓
Before/after review
```

## 1. Outcome first

Every screen needs one explicit user outcome. A screen may contain many
elements, but they should all support the same immediate job.

Before designing, answer:

- Who is using this screen?
- What are they trying to decide or complete now?
- What must they understand before acting?
- What is the most important result or action?
- What can wait until later?

UXPeak recommends listing the required elements before designing and ranking
them by importance. Size, position, color, weight, and contrast should then
make the highest-priority information fastest to find.
([Prioritize important information](https://www.uxpeak.com/blog-posts/top-ui-ux-design-tips-every-designer-needs-to-know-about))

### Figura rule

The immediate outcome changes by state:

| State | Primary user outcome | Dominant object |
|---|---|---|
| No analysis selected | Choose the right analysis | Analysis navigation |
| Understand | Decide whether the method fits | Suitability explanation |
| Try an Example | Learn how choices affect the result | Demonstration result |
| Analyze Your Data | Configure a valid analysis | Analysis form and preflight |
| Computing | Know what is happening and whether to wait | Measurable progress |
| Result ready | Understand the result and its limits | Figure/table plus interpretation |
| Handoff | Reuse the result correctly | Export and manuscript assets |
| Error | Recover without losing work | Corrective instruction |

If two objects compete to be dominant, the screen hierarchy is unresolved.

## 2. Minimize interaction cost

UXPeak defines interaction cost as the combined cognitive, physical, and time
effort required to reach a goal. The goal is not “fewest clicks” in isolation;
it is the least total effort that still preserves understanding and safety.
([Minimizing interaction cost](https://www.uxpeak.com/blog-posts/make-your-ui-designs-2x-better-by-minimizing-interaction-cost))

### Cognitive cost

Reduce the amount users must:

- interpret;
- remember;
- compare simultaneously;
- translate from technical language;
- infer from hidden choices;
- re-read to find the important part.

### Physical cost

Reduce unnecessary:

- clicks and taps;
- pointer travel;
- scrolling;
- repeated entry;
- context switching;
- precision required to hit a target.

### Time cost

Reduce:

- waiting without progress;
- unnecessary steps;
- repeated computation;
- delayed feedback;
- work that must be redone after an error.

### Decision rules

- Keep actions close to the object they affect.
- Show a short, relevant set of choices before exposing advanced options.
- Prefer recognition over recall: keep labels, meanings, and current selections
  visible.
- Group related information into meaningful chunks.
- Remove or combine steps that do not improve accuracy, comprehension, or
  safety.
- Automate repetition when the automation is visible and reversible.
- Preserve completed work when later input fails.

### Figura application

- Keep each Analysis Role selector close to its explanation and validation.
- Show only controls that apply to the selected analysis and plot type.
- Preserve the last valid result while a reversible visual option recomputes.
- Never ask users to re-upload a valid CSV because an unrelated choice failed.
- Use defaults for safe presentation choices, but require confirmation for
  scientific meanings that cannot be inferred.
- Do not hide a necessary scientific choice merely to make the interface look
  simpler.

## 2A. Familiar patterns reduce learning cost

UXPeak's public explanation of Jakob's Law says users expect a new product to
behave like products they already know. Familiar patterns should therefore be
the default; a novel pattern needs a functional reason strong enough to justify
the new learning cost.
([UX laws](https://www.uxpeak.com/blog-posts/the-9-ux-laws-every-designer-needs-to-know))

### Rules

- Use normal buttons, labels, tabs, checkboxes, radios, selects, disclosures,
  tables, and progress indicators before inventing custom controls.
- Keep common actions in expected places unless the domain requires a safer
  sequence.
- Similar-looking components should behave similarly.
- Different behavior should have a visible difference.
- Do not make novelty the primary expression of brand.
- When breaking a convention, document the user benefit and test whether users
  discover the new behavior.

### Figura application

- A Guided Stage may look like a tab and remain directly selectable; do not
  style it like a locked stepper.
- A disabled export action must look disabled and explain why it is
  unavailable.
- A checkbox changes an independent selection; a radio group chooses one
  mutually exclusive option; an immediate on/off state may use a switch.
- Use conventional table, file-input, and form behavior even when the visual
  styling is custom.

## 3. Expose value; do not hide it behind ceremony

UXPeak argues that hiding useful content behind a promotional banner or extra
navigation step adds a barrier before users experience value. Relevant content
should be exposed as early as practical.
([Expose content and reduce barriers](https://www.uxpeak.com/blog-posts/top-ui-ux-design-tips-every-designer-needs-to-know-about))

### Rules

- Put the useful object on the screen, not a card describing that it exists.
- Let examples demonstrate capability before asking for commitment.
- Use progressive disclosure for complexity, not for the core value.
- Make the recommended path visible without removing alternate valid paths.

### Figura application

The existing **Understand → Try an Example → Analyze Your Data** journey is a
strong expression of this principle:

- Understand establishes suitability and meaning.
- Try an Example exposes a real result using a clearly fictional dataset.
- Analyze Your Data reuses the learned mental model with the user's data.

Do not add a landing page, modal tour, or mandatory tutorial between the user
and these stages.

## 4. Hierarchy is controlled attention

UXPeak repeatedly recommends using size, weight, color, position, contrast,
icons, and spacing to distinguish important information. Presenting every
label and value with equal emphasis makes a screen harder to scan.
([Prioritize important information](https://www.uxpeak.com/blog-posts/top-ui-ux-design-tips-every-designer-needs-to-know-about),
[Differentiate information](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-tricks-every-designer-should-know-part-6-bonus-2f36b80be192))

### Hierarchy order

Use this order when deciding emphasis:

1. the answer or next primary action;
2. the evidence needed to trust it;
3. choices that materially change it;
4. interpretation and limitations;
5. metadata, provenance, and secondary actions.

### Use contrast deliberately

Contrast can come from:

- size;
- weight;
- tone;
- spacing;
- position;
- shape;
- background;
- motion or state change.

Do not use every form of contrast at once. The strongest contrast should be
reserved for the most important element.

### Figura application

- In a result, emphasize the clinical/statistical answer before the test name
  or implementation detail.
- In a metric pair such as `p = 0.031` and `Cohen's d = 0.62`, do not make the
  labels more prominent than the values.
- Keep caveats visually connected to the result they qualify.
- Treat export as the primary action only after a reusable, current result
  exists.
- De-emphasize webR and package metadata unless the system state requires the
  user's attention.

## 5. Typography serves scanning and comprehension

UXPeak advises using whitespace, size, line height, color, weight, and letter
spacing to create clear distinction between headings and body text. It also
warns against very light text and prioritizes legibility over visual flair.
([Readable text](https://www.uxpeak.com/blog-posts/top-10-ux-ui-tips-tricks-to-improve-your-designs),
[Avoid overly light text](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-every-designer-needs-to-know-about-part-4-f002a1f954b1))

### Figura type roles

These are house recommendations derived from the philosophy, not claimed
UXPeak measurements:

| Role | Recommended treatment | Use |
|---|---|---|
| Screen title | 22–28px, 650–700 weight | Analysis or major result |
| Section heading | 17–20px, 600–650 weight | Conceptual grouping |
| Component heading | 14–16px, 600 weight | Card, control group, result block |
| Body | 14–16px, 1.5–1.65 line height | Teaching and explanatory copy |
| Control label | 12–14px, 550–650 weight | Persistent field identification |
| Supporting text | 12–14px, readable neutral | Hints, provenance, secondary detail |
| Tabular/code text | 12–14px monospace | Values whose alignment aids reading |

### Rules

- A user should identify the page, current stage, and next action by scanning
  only headings, selected states, and buttons.
- Body copy should not depend on faint gray to look minimal.
- Uppercase labels are reserved for short navigational or metadata roles.
- Do not use placeholder text as the only label.
- Avoid long centered paragraphs.
- Keep line lengths comfortable and allow text spacing and zoom without
  clipping or overlap.

WCAG 2.2 requires at least 4.5:1 contrast for normal-size text and 3:1 for
large text, with limited exceptions.
([W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum))

## 6. Space communicates relationships

Whitespace is not unused room. It groups related elements, separates different
ideas, and reduces the need for decorative containers.

UXPeak recommends generous whitespace as an alternative to excessive borders
and background colors.
([Use borders sparingly](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-every-designer-needs-to-know-about-part-4-f002a1f954b1))

### Figura spacing scale

Use a small, repeatable scale:

```text
4   micro separation inside a control
8   tightly related elements
12  normal component internals
16  control or paragraph groups
24  sections
32  major regions
48  strong narrative break
```

### Relationship rule

The space inside a group should be smaller than the space between groups.

If a border is required to explain grouping, first ask whether spacing,
alignment, or a restrained background change would communicate it more calmly.

## 7. Borders and shadows should disappear into the structure

UXPeak recommends avoiding border-heavy interfaces. When borders are needed,
they should be thin and light. On colored surfaces, shadows should be tinted
toward the surrounding background instead of using a disconnected pure gray
or black.
([Border guidance](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-every-designer-needs-to-know-about-part-4-f002a1f954b1),
[Shadow guidance](https://medium.com/@uxpeak.com/top-ui-ux-tips-tricks-every-ui-designer-needs-to-know-about-part-5-0856f07e09a6))

### Rules

- Use a border to communicate a boundary, state, or affordance—not to decorate
  every region.
- Prefer one quiet divider to nested boxes.
- Keep neutral borders low contrast while maintaining visible control
  boundaries.
- Use stronger borders for focus, validation, drop targets, or selected states.
- Shadows indicate elevation or separation from the background; they do not
  replace hierarchy.
- Do not combine a strong border, strong shadow, and strong background on the
  same component without a state-based reason.

## 8. Color has jobs

Use color according to a defined role:

- **Neutral:** structure, text, backgrounds, dividers.
- **Accent:** primary action, active selection, focus, link.
- **Semantic:** success, warning, error, information.
- **Data:** distinguish series and categories in figures.

### Rules

- One accent color should dominate product interaction.
- Semantic colors do not compete with the primary accent.
- Color is never the only carrier of state or meaning.
- Data colors must remain distinguishable in context and in exported figures.
- Use saturation in proportion to importance.
- Background washes may group or signal state, but should not create a patchwork
  of competing panels.

WCAG requires meaning not to depend on color alone and requires visible
contrast for text and essential non-text UI information.
([WCAG 2.2](https://www.w3.org/TR/WCAG22/))

## 9. Icons and visual cues must clarify

UXPeak recommends visual cues because they can make information faster to
recognize, but also stresses icon consistency. Mixing unrelated icon families,
stroke weights, levels of detail, or filled and outlined styles makes an
interface feel less coherent. A filled variant may be used intentionally to
show a selected state.
([Visual cues](https://medium.com/@uxpeak.com/top-ui-ux-tips-tricks-every-ui-designer-needs-to-know-about-part-5-0856f07e09a6),
[Icon consistency](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-tricks-every-designer-should-know-part-6-bonus-2f36b80be192))

### Rules

- Add an icon when it improves recognition, status, or spatial orientation.
- Do not add an icon merely to fill empty space.
- Use one icon family and consistent optical size.
- Pair unfamiliar icons with text.
- Use the same icon for the same action everywhere.
- Make selected, destructive, disabled, and loading variants systematic.
- Do not use an icon instead of explaining a statistical concept.

## 10. Controls should fit the information

UXPeak recommends designing an input around the type and amount of information
expected, rather than applying one generic field shape to every input. It also
recommends placing labels above fields to reduce scanning effort.
([Input-specific fields](https://www.uxpeak.com/blog-posts/top-ui-ux-design-tips-every-designer-needs-to-know-about),
[Simple forms](https://www.uxpeak.com/blog-posts/top-10-ux-ui-tips-tricks-to-improve-your-designs))

### Control choice

| Need | Preferred control |
|---|---|
| Choose one of 2–4 visible options | Radio group or segmented control |
| Choose one from a long list | Select or searchable combobox |
| Choose any number of independent options | Checkboxes |
| Turn an immediate binary state on/off | Switch |
| Enter a bounded number | Number input with unit and valid range |
| Make a small incremental adjustment | Stepper or slider with visible value |
| Choose a file | File drop/input with accepted format and parsed summary |
| Map data meaning | Labeled role selector plus example/validation |
| Reveal advanced settings | Disclosure with a meaningful summary |

### Form rules

- Use persistent, explicit labels.
- Place instructions before the field when users need them to answer.
- Put errors adjacent to the field and explain how to fix them.
- Mark required inputs in text and semantics.
- Group related controls with a visible heading and programmatic relationship.
- Ask only for information required at the current stage.
- Match field width to expected content where practical.
- Preserve valid values after a different field fails.
- Do not disable the primary action without explaining what is missing.

W3C guidance recommends explicit labels, short forms, logical grouping,
instructions, validation, clear notifications, and progress for multi-stage
forms.
([W3C forms tutorial](https://www.w3.org/WAI/tutorials/forms/),
[W3C labeling controls](https://www.w3.org/WAI/tutorials/forms/labels/),
[W3C validation guidance](https://www.w3.org/WAI/tutorials/forms/validation/))

## 11. Place actions in the user's reading and decision sequence

UXPeak's public button-order example places the safe/regressive action before
the destructive/progressive action in a left-to-right interface so the gaze
moves through the decision once rather than bouncing between controls.
([Button order](https://www.uxpeak.com/blog-posts/top-10-ux-ui-tips-tricks-to-improve-your-designs))

### Rules

- Give each region one visually primary action.
- Write buttons as explicit verbs: `Run analysis`, `Download SVG`, `Retry`.
- Put the action beside the object or inputs it affects.
- In left-to-right layouts, order secondary/back/cancel before
  commit/continue/destructive actions when they form one decision pair.
- Separate destructive actions from routine actions and require confirmation
  when recovery is difficult.
- A disabled button must still be understandable.
- Do not style a navigation link, toggle, and submit action identically.

### Figura action hierarchy

1. Run or recompute the current analysis.
2. Resolve a blocker or confirmation.
3. Export a current result.
4. Change a presentation option.
5. Reset or abandon work.

## 12. Cards are for peers, not every piece of content

UXPeak recommends maintaining consistent heights across sets of three or more
peer cards. When copy length varies, align calls to action at the bottom so the
set remains scannable.
([Card consistency](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-tricks-every-designer-should-know-part-6-bonus-2f36b80be192))

### Rules

- Use cards only for comparable, selectable, or independently actionable
  objects.
- Give peer cards the same information order.
- Align titles, key values, and actions across the set.
- Keep equal height when it materially improves comparison.
- Do not wrap every paragraph, field, or metric in its own card.
- A card needs a clear boundary and purpose; otherwise use normal document
  flow.

## 13. Show system state; do not merely name it

UXPeak's public waiting-state framework argues that static labels such as
“Uploading” or “Processing” leave users to infer whether the system is alive,
how much remains, and what to do if it stalls. Good waiting states expose a
definite answer, visible change, a unit of progress, and a recovery path.
([Show, don't tell, status](https://medium.com/@uxpeak.com/ui-design-tip-dont-tell-users-the-status-show-it-95116b2ac24c))

### The four-question wait audit

For every operation that makes the user wait:

1. Is there a definite current answer: percentage, count, step, or time?
2. Can the user see real progress change?
3. Is the unit of progress visible?
4. Is there a retry, cancel, refresh, or other recovery path?

### Figura state model

| State | Required communication |
|---|---|
| Engine warm-up | Current stage: engine, packages, or ready |
| File parsing | File name, rows/columns found, errors if any |
| Analysis preflight | Included rows, exclusions, blockers, confirmations |
| Computing | Analysis name and meaningful progress when available |
| Recomputing display | Preserve prior valid result; mark it as updating |
| Success | What completed and which result is current |
| Out-of-date Result | What changed and why recomputation is required |
| Failure | What failed, what remained safe, and the next recovery action |

Avoid an indefinite spinner when the system can expose a real stage or count.

## 14. Errors are recovery interfaces

An error is not complete until the user knows:

- what happened;
- where it happened;
- what was preserved;
- what they can do next;
- whether retrying is safe.

### Rules

- Use plain, specific language.
- Name the affected field, file, role, or analysis.
- Put field errors near the field and summarize multi-field failures.
- Preserve valid inputs and valid prior results.
- Never silently repair scientific data or meaning.
- Distinguish blockers, confirmations, and non-blocking notices.
- Confirm successful completion as clearly as failure.

W3C recommends concise notifications and error messages with simple corrective
instructions.
([W3C user notifications](https://www.w3.org/WAI/tutorials/forms/notifications/))

## 15. Empty states should orient and begin

An empty state should answer:

1. What belongs here?
2. Why is it empty?
3. What should I do next?
4. Is there an example?

### Figura examples

- Configuration: “Choose an analysis to see the required data and controls.”
- Figure: “Run the example or your own analysis to create a journal-ready
  figure.”
- Console/result text: “Methods, estimates, limitations, and reusable text
  appear here after a successful analysis.”

Keep privacy reassurance near the first data-upload decision, not only in the
footer.

## 15A. UX writing should remove inference

Copy is part of the interaction, not explanatory material added after the
interface is designed.

### Rules

- Write for comprehension and action, not cleverness.
- Use the user's domain language and define unavoidable technical terms.
- Name actions by their outcome: `Run Kaplan–Meier analysis`, not `Submit`.
- Prefer one concrete status, quantity, or next step over vague reassurance.
- Keep navigation labels concise and stable.
- Put the explanation at the point where the question arises.
- State success and failure explicitly.
- Explain why a consequential automatic choice was made.
- Avoid blame, false certainty, urgency, and celebratory language around
  scientific results.

### Figura examples

| Weak | Better |
|---|---|
| `Invalid input` | `Follow-up time contains 3 negative values. Correct those rows before running the analysis.` |
| `Processing…` | `Computing Kaplan–Meier estimates: building risk table` |
| `Done` | `Analysis complete — 118 of 120 rows included` |
| `Select columns` | `Map the columns that represent follow-up time, event status, and study group` |
| `Warning` | `Confirmation required: “Death” is mapped to Event` |

## 16. Trust is a visible product feature

For Figura, trust outranks conversion. The interface must make the following
facts easy to see and verify:

- user data remains in the browser;
- demonstration data is fictional;
- an Analysis Result has explicit provenance;
- assumptions and unsupported structures are named;
- uncertainty is visible;
- the app does not claim causal or clinical conclusions it cannot support;
- an Out-of-date Result cannot enter an Analysis Handoff.

### Trust design rules

- Explain a consequential automatic choice and make its reason inspectable.
- Distinguish computed results from Teaching Visuals.
- Attach limitations to the result, not a distant legal page.
- Show missingness, exclusions, denominators, and warnings before computation.
- Use confidence intervals and effect sizes where the method supports them.
- Do not use reassuring color or celebratory animation to imply scientific
  validity.
- Make data handling explicit at upload and computation points.

## 17. Retention and conversion should come from confidence

UXPeak connects UI design with retention and conversion through onboarding,
habit loops, empty states, reactivation, product pages, pricing, forms, and
checkouts. The unifying principle is that users understand value faster and
act with more confidence.
([UXPeak platform](https://www.uxpeak.com/))

For Figura, the ethical equivalents are:

- **Activation:** the user successfully runs a Demonstration Dataset and
  understands the result.
- **Retention:** the user trusts the workflow enough to return for another
  analysis.
- **Conversion:** the user moves from learning to a correct Analysis Handoff,
  not to a purchase.

Do not introduce gamification, urgency, or completion pressure into scientific
decisions.

## 17A. Results and data visuals must answer, not decorate

This is a Figura-specific extension of UXPeak's hierarchy, visual-cue, and
“show, don't tell” principles.

### Rules

- Start with the question the figure or table must answer.
- Emphasize the estimate or pattern before implementation details.
- Show uncertainty whenever it is part of the analysis.
- Keep denominators, missingness, exclusions, and units visible.
- Use direct labels where they reduce legend lookup.
- Show raw observations when they materially improve interpretation and do not
  create unreadable overplotting.
- Use position and length before color for important quantitative comparisons.
- Make reference lines, censor marks, confidence bands, and annotations
  visually subordinate to the main data while remaining legible.
- Do not use decorative gradients, perspective, excessive smoothing, or
  animation that changes the perceived evidence.
- Ensure the exported figure retains meaning without the surrounding app.
- Pair every computed visual with text that states what it supports and what it
  does not support.

### Result hierarchy

1. analysis question and population;
2. main estimate or pattern;
3. uncertainty and supporting counts;
4. comparison statistic or test;
5. diagnostics and limitations;
6. provenance and export details.

## 18. Accessibility is part of clarity

The UXPeak philosophy of readable text, visible hierarchy, simple forms, and
reduced interaction cost aligns with accessibility, but accessibility requires
explicit implementation and testing.

### Minimum release rules

- Meet WCAG 2.2 AA contrast requirements.
- Do not rely on color alone.
- Maintain visible keyboard focus.
- Make every action keyboard-operable.
- Use semantic headings, labels, groups, tabs, tables, and status messages.
- Make pointer targets at least 24 by 24 CSS pixels or provide the spacing
  allowed by WCAG 2.2; aim larger for important actions.
- Support reflow at 320 CSS pixels without losing information or functionality,
  except where a two-dimensional presentation is essential.
- Allow text spacing and zoom without clipping or overlap.
- Provide text alternatives for meaningful visual information.
- Ensure charts have readable labels, descriptions, and non-color distinctions.

Sources:
[WCAG 2.2](https://www.w3.org/TR/WCAG22/),
[target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html),
[text spacing](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing),
[ARIA patterns](https://www.w3.org/WAI/ARIA/apg/patterns/)

## 18A. Validate behavior, not taste

UXPeak's public material recommends end-user testing, comparison of meaningful
alternatives, and iteration based on feedback. Its before/after method is a
way to form a design hypothesis, not proof that the redesign works.
([Top design tips](https://www.uxpeak.com/blog-posts/top-10-ux-ui-tips-tricks-to-improve-your-designs),
[UX laws](https://www.uxpeak.com/blog-posts/the-9-ux-laws-every-designer-needs-to-know))

### Validation ladder

1. **Expert review:** use this playbook to find obvious hierarchy, friction,
   consistency, trust, and accessibility issues.
2. **Task walkthrough:** can a new user predict the next action and its result?
3. **Keyboard and screen-reader check:** verify semantics and operability.
4. **Representative usability test:** observe users completing the real task
   without coaching.
5. **Before/after comparison:** measure time, errors, backtracking, help
   requests, confidence, and completion.
6. **Production evidence:** inspect abandonment, retries, invalid submissions,
   support questions, and successful handoffs.

For clinical workflows, do not optimize only for speed. Also measure:

- correct interpretation;
- correct role mapping;
- recognition of limitations;
- ability to recover from invalid data;
- ability to distinguish a Teaching Visual from an Analysis Result.

## 19. Figura screen architecture

Figura's calm three-pane workbench is a good foundation. Preserve its stable
spatial model while changing emphasis according to the current task.

### Global layer

- Brand and local-processing promise.
- R/webR status only when operationally relevant.
- Analysis navigation.

### Configuration layer

- Analysis title.
- Guided Stage navigation.
- Teaching, Demonstration Dataset controls, or user-data configuration.
- One primary action.

### Result layer

- Currentness and provenance.
- Figure or table.
- Main estimates and Interpretation Guidance.
- Warnings and limitations.
- Analysis Handoff actions.

### Spatial rules

- The left pane answers “Which analysis?”
- The center pane answers “What does this analysis need?”
- The right pane answers “What did it produce?”
- Do not move the same responsibility between panes in different analyses.
- On narrow screens, preserve this responsibility order in the vertical flow.
- Keep the current result visible during reversible presentation changes.

## 20. Component intelligence matrix

| Component | User question | Must show | Avoid |
|---|---|---|---|
| Analysis navigation | What can I do? | Plain names, active state | Marketing descriptions in every item |
| Guided Stage tabs | Where am I? | Current stage and direct access | Locked linear wizard behavior |
| File input | What did I load? | Name, shape, parse status | A bare filename with no validation |
| Analysis Role selector | What does this column mean here? | Role, selected column, constraints | Assuming meaning from a column name |
| Preflight finding | Can I continue safely? | Severity, evidence, action | Generic yellow warning boxes |
| Primary action | What happens next? | Explicit verb and scope | “Submit”, “OK”, or multiple primaries |
| Progress state | Is it working? | Stage/count/unit and recovery | Indefinite spinner plus vague copy |
| Result header | What result is this? | Analysis Definition and currentness | Figure without provenance |
| Figure | What pattern should I see? | Labels, uncertainty, denominator/context | Decoration that competes with data |
| Interpretation Guidance | What does this support? | Meaning, limits, escalation point | Automated conclusion |
| Export controls | What can I reuse? | Format, purpose, currentness | Exporting an Out-of-date Result |
| Error | How do I recover? | Cause, preserved state, next action | Stack traces or blame |

## 21. Before/after redesign method

UXPeak uses before/after comparisons because they make design judgment visible.
Use this sequence for every redesign:

### Step 1: State the user's question

Write one sentence: “On this screen, the user needs to…”

### Step 2: Inventory

List every visible:

- fact;
- action;
- choice;
- status;
- warning;
- decoration.

### Step 3: Rank

Assign each item:

- **P0:** required for the immediate outcome;
- **P1:** required for confidence or a safe decision;
- **P2:** useful secondary detail;
- **P3:** removable or deferrable.

### Step 4: Remove interaction cost

For each item, ask:

- Can it be eliminated?
- Can it be inferred safely?
- Can it be exposed earlier?
- Can it be grouped?
- Can it be prefilled?
- Can it be placed closer to what it affects?
- Can the system remember it?

### Step 5: Encode hierarchy

Make P0 visually dominant, P1 adjacent and readable, P2 available without
competition, and P3 removed or disclosed.

### Step 6: Add state and recovery

Specify idle, hover, focus, active, disabled, loading, success, warning, error,
empty, and out-of-date behavior where applicable.

### Step 7: Compare

The “after” version should answer:

- Is the user's next useful action found faster?
- Is important information easier to scan?
- Are there fewer decisions and less pointer travel?
- Is the system's state more concrete?
- Are consequences and recovery clearer?
- Is anything important less accessible or less honest?

If the redesign is merely prettier, it is incomplete.

## 21A. Standard format for a playbook entry

Each design-intelligence entry should contain:

1. **User problem:** the observable difficulty or risk.
2. **Decision rule:** one concise instruction.
3. **Why it works:** the cognitive, behavioral, or product reasoning.
4. **Before:** a realistic weak/default example.
5. **After:** an improved example with the changed decisions identified.
6. **Outcome:** what should become faster, clearer, safer, or more trustworthy.
7. **Common misuse:** how the rule is applied mechanically or decoratively.
8. **Exceptions and trade-offs:** when another pattern may be better.
9. **Decision tree:** the minimum questions needed to choose the pattern.
10. **Implementation checklist:** visual, interaction, content, state, and
    accessibility requirements.
11. **Exercise:** a small realistic redesign task.
12. **Validation:** how the team will know the change helped.

This structure follows UXPeak's public emphasis on visual lessons, real product
breakdowns, before/after redesigns, reasoning, common mistakes, decision
frameworks, and hands-on exercises.
([UXPeak platform](https://www.uxpeak.com/),
[UI/UX Playbook overview](https://www.uxpeak.com/pages/playbook))

## 22. Design review score

Score each dimension from 0 to 2:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Outcome clarity | Goal or next action is unclear | Understandable after reading | Obvious on first scan |
| Information hierarchy | Elements compete | Mostly ordered | Priority is unmistakable |
| Interaction cost | Avoidable effort or repetition | Some friction remains | No unnecessary effort |
| System state | Silent or vague | Named state | Measurable state plus recovery |
| Trust | Meaning/consequences hidden | Main caveats present | Provenance, limits, and currentness are clear |
| Consistency | Patterns drift | Minor variation | Components and language are predictable |
| Accessibility | Known blockers | Meets basics with gaps | WCAG AA behavior is verified |
| Visual calm | Noisy or over-contained | Mostly restrained | Space and contrast do the work |

### Release gate

- No dimension may score `0`.
- Accessibility and trust must score `2` for a clinical workflow.
- Total target: at least `14/16`.
- A score does not replace usability testing; it makes review criteria explicit.

## 23. AI design-review protocol

Use this prompt structure when asking an AI agent to critique or design a
screen:

```text
Act as a product-design reviewer for Figura.

Screen:
[name and current state]

User:
[role, context, and likely level of statistical confidence]

Immediate outcome:
[one sentence]

Consequential constraints:
[privacy, clinical meaning, accessibility, latency, unsupported cases]

Current elements or screenshot:
[content]

Review in this order:
1. user goal and information priority;
2. cognitive, physical, and time interaction cost;
3. visual hierarchy and scanning;
4. control choice, labels, and action order;
5. system state, waiting, and recovery;
6. trust, provenance, limitations, and currentness;
7. consistency and WCAG 2.2 AA accessibility.

For every issue provide:
- severity: blocker, important, or polish;
- the user consequence;
- the principle being violated;
- a specific before → after change;
- the evidence or assumption behind the recommendation.

Do not propose decoration unless it improves hierarchy, comprehension,
feedback, trust, or accessibility. Preserve Figura's domain language.
```

## 24. Definition of done for a new screen or flow

### Goal and content

- [ ] The immediate user outcome is written in one sentence.
- [ ] Required information is ranked before layout work begins.
- [ ] The dominant object matches the current state.
- [ ] Optional detail does not compete with the main task.

### Flow

- [ ] The shortest path is also understandable and safe.
- [ ] Core value is exposed without unnecessary ceremony.
- [ ] Related controls and actions are close together.
- [ ] Repeated entry and avoidable context switching are removed.
- [ ] Advanced options use progressive disclosure.

### Visual hierarchy

- [ ] Important values are more prominent than their labels.
- [ ] Space groups related elements before borders are added.
- [ ] There is one interaction accent and one primary action per region.
- [ ] Borders, shadows, cards, icons, and color each have a clear job.
- [ ] Text remains readable without relying on faint tones.

### State and recovery

- [ ] Empty, loading, success, warning, error, disabled, and out-of-date states
      are specified.
- [ ] Waiting states expose real progress where possible.
- [ ] Errors preserve safe work and give a corrective action.
- [ ] Consequential actions have an appropriate recovery or confirmation.

### Trust and clinical safety

- [ ] Analysis Definition and provenance remain attached to the result.
- [ ] Demonstration data and Teaching Visuals cannot be mistaken for evidence.
- [ ] Missingness, exclusions, assumptions, and limitations are visible.
- [ ] An Out-of-date Result cannot be exported as current.
- [ ] Copy does not overstate statistical or causal meaning.

### Accessibility

- [ ] Keyboard flow and visible focus are verified.
- [ ] Labels, headings, groups, tabs, tables, and statuses are semantic.
- [ ] Text and non-text contrast meet WCAG 2.2 AA.
- [ ] Meaning does not depend on color alone.
- [ ] Targets and spacing meet WCAG 2.2.
- [ ] Reflow, zoom, and text spacing do not hide functionality.

## 25. Source map

### UXPeak first-party sources

- [UXPeak platform and stated outcomes](https://www.uxpeak.com/)
- [About UXPeak and its practical-over-theoretical philosophy](https://www.uxpeak.com/pages/about)
- [UI/UX Playbook public overview](https://www.uxpeak.com/pages/playbook)
- [Course curriculum](https://www.uxpeak.com/pages/course)
- [Minimizing interaction cost](https://www.uxpeak.com/blog-posts/make-your-ui-designs-2x-better-by-minimizing-interaction-cost)
- [Priority, exposed content, and input-specific fields](https://www.uxpeak.com/blog-posts/top-ui-ux-design-tips-every-designer-needs-to-know-about)
- [UX laws and familiar patterns](https://www.uxpeak.com/blog-posts/the-9-ux-laws-every-designer-needs-to-know)
- [Testing, forms, empty states, and visual guidance](https://www.uxpeak.com/blog-posts/top-10-ux-ui-tips-tricks-to-improve-your-designs)
- [Borders and readable text](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-every-designer-needs-to-know-about-part-4-f002a1f954b1)
- [Visual cues and background-aware shadows](https://medium.com/@uxpeak.com/top-ui-ux-tips-tricks-every-ui-designer-needs-to-know-about-part-5-0856f07e09a6)
- [Hierarchy, icon consistency, and card consistency](https://medium.com/@uxpeak.com/top-ui-ux-design-tips-tricks-every-designer-should-know-part-6-bonus-2f36b80be192)
- [Cards, button order, forms, icons, and readable typography](https://medium.com/@uxpeak.com/top-5-ux-ui-tips-tricks-to-improve-your-designs-424fe02e9988)
- [Actionable waiting-state framework](https://medium.com/@uxpeak.com/ui-design-tip-dont-tell-users-the-status-show-it-95116b2ac24c)

### Implementation standards

- [Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/)
- [W3C Forms Tutorial](https://www.w3.org/WAI/tutorials/forms/)
- [W3C ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)

## Final decision principle

When two designs are both attractive, choose the one that lets the user:

1. understand the situation with fewer inferences;
2. reach the useful outcome with less total effort;
3. see what the system is doing;
4. recover without losing safe work;
5. trust the result for the right reasons.

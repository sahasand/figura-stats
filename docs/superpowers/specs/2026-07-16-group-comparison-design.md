# Group comparison — guided analysis (design)

Date: 2026-07-16
Status: approved

## Purpose

A fourth guided analysis, **Group comparison**, that compares an outcome across
two or more groups and reports it the way modern clinical journals expect:
the right test (auto-selected, normality-aware), an **effect size with a 95%
confidence interval**, and the p-value — not the p-value alone. Research on
published clinical papers shows effect-size and CI reporting is the single most
common gap; this analysis closes it by construction.

One guided experience covers the three largest inferential method clusters in
the clinical-journal frequency data: ANOVA/means (#1), chi-square (#2), and
non-parametric tests (#5). It revives and substantially upgrades the trimmed
`fig_groupcompare` that survives at git tag `pre-trim-8-analyses` (the trimmed
version had a manual parametric toggle, numeric-only outcomes, no effect sizes,
no CIs, no post-hoc, and no guided shell).

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Test selection | Auto-select, normality-aware (reuse Summary's decision), user override allowed |
| Chi-square | Folded in — auto-detect by outcome type (numeric → t/ANOVA family; categorical → chi-square/Fisher) |
| What to report | Effect size + 95% CI + p-value, per test |
| Paired data | Independent groups only in v1; paired/repeated-measures is a named v2 |
| Post-hoc | Yes for 3+ groups when omnibus significant, with multiplicity correction |
| Packages | Base R, hand-computed effect sizes/CIs/Dunn — no new packages, zero cold-start weight |

## Architecture

Follows the five-parallel-keys recipe from CLAUDE.md:

1. **`R/groupcompare.R`** — `fig_groupcompare(spec)` returning `list(svg=, text=)`.
2. **`R/dispatch.R`** — add `groupcompare = fig_groupcompare(spec),` to the switch.
3. **`web/worker.js`** — add `"groupcompare.R"` to the boot-time R-file fetch
   loop. **No `EXTRA_PACKAGES` entry** — base `stats` + `ggplot2` only, so the
   analysis stays in the free cold-start tier (no per-figure download).
4. **`web/guided/groupcompare/`** — shell config + content + demo + analyze
   files mirroring `web/guided/summary/`; registered in `web/app.js`; nav
   button in `web/index.html`.
5. **`DESCRIPTION`** — no change (no new packages).

Submit-driven like Summary/KM (a Render click), **not** a live builder — uses
the classic shell path, `liveRender` is **not** set. Journal export (DPI PNG /
SVG / copy / `.tsv`) works unchanged via the pane toolbars; text is tabular
results so it stays `.tsv` — no `textExportDescriptor` change.

**Spec shape** — snake_case options, roles carry a grouping column and an
outcome column:

```json
{
  "figure": "groupcompare",
  "data": [ {"arm": "Treatment", "crp": 5.2, ...}, ... ],
  "roles": { "group": "arm", "outcome": "crp" },
  "options": { "plot": "box", "test": "auto" }
}
```

`options.test` is `"auto"` (default), `"parametric"`, or `"nonparametric"`
(override, numeric outcomes only). `options.plot` is `"box"` or `"violin"`
(numeric outcomes only; categorical outcomes always render a bar chart). Rows
are projected to the group + outcome columns only before crossing to the
worker (no-egress).

## R side — statistics engine (base R, hand-computed)

`fig_groupcompare(spec)`:

1. **Extract & validate.** Group column read as character; a group with fewer
   than 2 non-missing outcome values is dropped with a note; after dropping,
   fewer than 2 groups is a readable `stop()`. NA/blank rows removed.
2. **Route on outcome type.** The outcome column is coerced numeric with the
   suppress-warning-then-clear-`stop()` pattern (`.numeric_col` in
   `R/summarize.R`): if every non-blank cell is numeric → **numeric branch**;
   otherwise → **categorical branch**. (The JS form also tags the intended
   route from the inferred column type; R re-derives it so a direct caller is
   safe.)

### Numeric branch

Reuse Summary's `.summary_decide` (Shapiro–Wilk + skewness, group-mean-centered
so pooled group shifts don't falsely fail normality) to pick parametric vs
non-parametric **once** across the pooled centered values, unless
`options.test` overrides. State the reason in the text
("used Mann–Whitney: CRP is right-skewed (skewness 1.8)").

| Groups | Parametric | Non-parametric |
|---|---|---|
| 2 | Welch t-test | Mann–Whitney U (`wilcox.test`) |
| 3+ | one-way ANOVA, Welch (`oneway.test`) | Kruskal–Wallis (`kruskal.test`) |

Effect size + 95% CI + p per test, hand-computed:

- **Welch t-test**: mean difference with CI (from `t.test`), and Cohen's d
  (pooled SD) with CI via the noncentral-t / Hedges approximation
  `d ± 1.96·SE(d)` where `SE(d) = sqrt((n1+n2)/(n1·n2) + d²/(2(n1+n2)))`.
- **Mann–Whitney**: rank-biserial correlation `r = 1 − 2U/(n1·n2)` with CI via
  Fisher z-transform of `r`.
- **one-way ANOVA**: eta-squared `η² = SS_between / SS_total` with CI via the
  noncentral-F method (F, df1, df2 → CI on η²).
- **Kruskal–Wallis**: epsilon-squared `ε² = H / (n − 1)` (CI omitted — no
  standard closed form; report point estimate only, noted as such).

**Post-hoc** (3+ groups, only when omnibus p < 0.05):
- Parametric → Tukey HSD via `TukeyHSD(aov(value ~ group))`, adjusted p per pair.
- Non-parametric → Dunn's test hand-computed: pairwise rank-sum z-statistics
  from the shared Kruskal ranking, two-sided p, Benjamini–Hochberg adjusted.
  No `dunn.test`/`PMCMRplus` dependency.

### Categorical branch

Contingency table of outcome × group. **Pearson chi-square** (`chisq.test`);
if any expected cell count < 5, fall back to **Fisher's exact** (`fisher.test`)
and say so. Effect size:
- **Cramér's V** `= sqrt(χ² / (n · min(r−1, c−1)))` for any table.
- **Odds ratio + 95% CI** additionally when the table is 2×2 (from the
  cross-product, CI via the log-OR standard error).

### Errors, WARN 0

Every guard is a readable `stop()` surfaced through the never-throws
`render_figure` contract as `{ok:false}`. WARN 0 is a hard gate; ggplot 4.x
clean (`linewidth`, no deprecated args). If a base test emits an unavoidable
warning for valid data (e.g. `chisq.test` approximation warning), wrap **only
that library call** in `suppressWarnings()` and switch to Fisher on the
expected-count rule — never suppress our own computation.

## Outputs

`list(svg=, text=)`, injected into `#preview`/`#stats` unchanged.

- **Numeric outcome** → `svg` is a box (default) or violin plot with jittered
  raw points, one column per group, house Tol palette (`.km_palette` values)
  and `.fig_theme`, significance annotation. Upgrades the trimmed grey-box
  plot.
- **Categorical outcome** → `svg` is a grouped/proportion bar chart of the
  contingency table (Explore bar-geom styling), so chi-square still yields a
  figure.
- **`text`** is a copy-pasteable methods+results sentence in house style:
  per-group summaries (mean ± SD or median [IQR], chosen by the same normality
  logic), the named test with its selection reason, effect size with CI,
  p-value, and post-hoc lines when present.

## JS side — guided shell

`web/guided/groupcompare/guided-groupcompare.js` is a `createGuidedShell({...})`
config, never a shell copy. Stages:

- **Understand** (`content.js`): what a group comparison answers; parametric vs
  non-parametric and why the tool auto-picks; why effect size + CI matter
  beyond the p-value (the teaching hook the research surfaced); the
  multiple-comparisons caveat for 3+ groups.
- **Try an Example** (`demo.js`, `demo-data.js`, frozen
  `data-raw/groupcompare-demo-generator.R`): a synthetic dataset engineered so
  one numeric outcome reads approximately normal (→ t-test/ANOVA), one is
  right-skewed (→ non-parametric), and a categorical outcome exercises the
  chi-square path — all three routes reachable from the demo. Experiment
  controls: swap outcome column, box↔violin, force parametric/non-parametric.
- **Analyze Your Data** (`analyze-form.js`): CSV upload via `web/lib/csv.js`,
  `web/lib/columnpicker.js` with a `categorical+` **group** role and an
  **any-type outcome** role (numeric or categorical; type drives routing),
  progressive disclosure like the Summary form (config hidden until a parse
  succeeds; parse failure re-hides and clears state). All CSV-derived strings
  DOM-built, never `innerHTML`.

## Testing

- **R** (`tests/testthat/test-groupcompare.R`), `devtools::test()`,
  **[ FAIL 0 | WARN 0 ]**:
  - Golden path per branch: 2-group parametric + non-parametric; 3+ group
    ANOVA + Kruskal with post-hoc firing only when omnibus significant;
    chi-square; Fisher fallback on small expected cells.
  - Each asserts the SVG renders (`expect_match(out$svg, "<svg", fixed=TRUE)`),
    and the text carries the named test, the effect size, a CI, and the
    p-value.
  - Effect-size values pinned against hand-verified constants (Cohen's d,
    rank-biserial, eta-squared, Cramér's V, odds ratio).
  - Edge/adversarial: non-numeric cell in a would-be-numeric outcome that
    should still route numeric vs one that routes categorical; a group with <2
    values (dropped + note); one remaining group (readable error); NA/blank
    rows; 2×2 vs larger contingency table (odds ratio only when 2×2); override
    forcing a test.
  - Summary's normality decision is reused, not re-tested here.
- **JS unit** (`web/guided/groupcompare/*.test.mjs`): spec-building (roles +
  options, rows projected to used columns only), outcome-type routing logic,
  frozen demo-data snapshot.
- **E2E** (`tests/e2e/groupcompare-guided.spec.js`): three tabs + hash sync;
  demo renders each route (switch outcome column → plot + test change);
  analyze upload → box plot + a real p-value and effect size in the text; the
  existing KM/Summary/Explore/export specs stay green (regression gate).

## Out of scope (v1)

- Paired / repeated-measures comparisons (paired t-test, Wilcoxon signed-rank,
  repeated-measures ANOVA) — a named v2 needing a pairing/subject-ID column.
- More than one outcome per run / small-multiple group comparisons.
- Trend tests across ordered groups (Jonckheere, Cochran–Armitage).
- Kruskal–Wallis epsilon-squared confidence interval (no standard closed form).
- Covariate adjustment (ANCOVA) — belongs with the regression analysis.

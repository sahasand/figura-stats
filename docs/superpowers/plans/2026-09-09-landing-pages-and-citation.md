# Landing Pages, Sitemap and Citation Line Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seven crawlable HTML pages (six analyses + About) generated from the app's own modules, a sitemap, a hash deep-link into the app, and one deterministic citation sentence appended to every analysis's methods text and exported script.

**Architecture:** A Node generator in `scripts/pages/` (outside `web/`, so outside the validation digest) reads each analysis's exported `UNDERSTAND_SECTIONS`, its demo data, and a committed native-R render, and writes tracked pages under `web/<slug>/`. R gains one `.citation_sentence(pkgs)` helper that every `fig_*` appends; the validation comparator learns to strip that paragraph. `app.js` reads the URL hash once on load and clicks the matching rail button.

**Tech Stack:** R (`devtools::test()`), Node 20+ (`node:test`-free plain assert scripts chained in `package.json`), Python 3.11 comparator (`pytest`), Playwright for one e2e case. No new dependencies of any kind.

**Spec:** `docs/superpowers/specs/2026-09-09-landing-pages-and-citation-design.md`

**Reviewed 2026-09-09 by the owner; five corrections applied:** the page test's off-origin check is restricted to fetched resources and compares origins (Task 8); the validation instructions reflect the current zero-findings baseline and add the `make webr` release gate before rebuilding published evidence (Task 12); the citation strip matches only the citation grammar and a test proves extra content survives (Task 3); Explore's code output is labelled as code, never as methods text (Tasks 6 and 8); the analytics disclosure says "no uploaded research data or analysis results" and README.md is in the correction (Task 9).

## Global Constraints

- **WARN 0 is a hard gate** in R: run `Rscript -e 'devtools::test()'`, never `testthat::test_file()`.
- **Every new `*.test.mjs` is appended to the `test:unit` chain in `package.json` in the same commit that creates it.** Every entry runs from the repo root.
- **No CDN, no off-origin `<link>`/`<script>` in any page.** Fonts are self-hosted; pages link `../styles.css` and `../pages.css` only.
- **Generated files are tracked and never hand-edited:** `web/<slug>/index.html`, `web/<slug>/sample.csv`, `web/<slug>/example.json`, `web/sitemap.xml`, `web/robots.txt`.
- **The citation sentence contains no R version and no date.** Wording: `Analyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R with the survival, ggplot2, and cowplot packages in the browser.` (package clause varies by analysis; see Task 1).
- **`web/` sources in the validation digest** are every `*.js` (not `*.test.mjs`), `index.html` and `styles.css`. Task 5 touches three of them, so Task 12 must run the validation pipeline.
- **Never run `make -C stats-validation gate-update` automatically.** Read every changed finding first (Task 12).
- **Path B independence:** `stats-validation/python/validate/` is never edited here. The comparator `stats-validation/compare/compare.py` and the specs `stats-validation/spec/*.md` are.
- **Deviation from spec, recorded:** `fig_explore`'s `text` field *is* its ggplot2 script (there is no methods sentence), so appending a prose sentence would corrupt the `.R` download. Explore gets a `# Cite:` comment line in that script instead (Task 2). The sitemap carries no `<lastmod>`: a git-derived date changes on the very commit that records it and would fail the freshness test forever; omitting it is the deterministic choice.
- **Commit messages** end with the attribution lines the session provides.

---

## File Structure

**Created**

| Path | Responsibility |
|---|---|
| `scripts/pages/registry.mjs` | The one table: slug ↔ analysis key ↔ title/description/lede ↔ imported `UNDERSTAND_SECTIONS` ↔ demo dataset. Also `SITE`, `CITATION`, `BIBTEX`. |
| `scripts/pages/html.mjs` | Pure string templates: `renderAnalysisPage`, `renderAboutPage`, `renderSitemap`, `renderRobots`, `escapeHtml`. |
| `scripts/pages/build.mjs` | `buildAll()` → `Map<relpath, string>`; `main()` writes into `web/`. |
| `scripts/pages/build.test.mjs` | Freshness (built == committed) + structural assertions. |
| `scripts/pages/example-specs.mjs` | Writes each demo spec JSON to `scripts/pages/.build/<slug>.spec.json`. |
| `scripts/pages/render-examples.R` | Reads those specs, calls `render_figure`, writes `web/<slug>/example.json`. |
| `web/lib/route.js`, `web/lib/route.test.mjs` | `analysisFromHash(hash, known)`. |
| `web/guided/understand-sections.test.mjs` | Every content module exports a well-formed `UNDERSTAND_SECTIONS` that `renderUnderstand` uses. |
| `web/pages.css` | Document layout for the seven pages, tokens only. |
| `web/<slug>/index.html`, `sample.csv`, `example.json` × 6; `web/about/index.html`; `web/sitemap.xml`; `web/robots.txt` | Generated outputs. |
| `tests/e2e/pages.spec.js` | Landing page → app deep link. |

**Modified**

| Path | Change |
|---|---|
| `R/script.R` | Citation constants, `.citation_sentence`, `.with_citation`, `# Cite:` header line. |
| `R/km.R`, `R/cox.R`, `R/logistic.R`, `R/summarize.R`, `R/groupcompare.R`, `R/explore.R` | Append the sentence (or the comment line, for explore). |
| `tests/testthat/test-script.R` + one test per analysis file | Assertions. |
| `stats-validation/compare/compare.py`, `compare/tests/test_compare.py`, `spec/*.md` | Strip the citation paragraph; document it. |
| `web/guided/{km,summary,cox,logistic,groupcompare,explore}/content.js` | Export `UNDERSTAND_SECTIONS`. |
| `web/app.js`, `web/index.html`, `web/sw.js`, `web/styles.css` (comment only) | Hash on load, About link, cache bump, honest comment. |
| `stats-validation/build_scorecard.py`, `CLAUDE.md` | Analytics disclosure; docs. |
| `package.json`, `.gitignore` | Scripts, test chain, `.build/` ignore. |

---

### Task 1: The citation sentence in R

**Files:**
- Modify: `R/script.R` (top of file, and `.script_header`)
- Test: `tests/testthat/test-script.R`

**Interfaces:**
- Produces: `.citation_sentence(pkgs = character(0)) -> character(1)`; `.with_citation(text, pkgs) -> character(1)` (appends `"\n\n"` + sentence); constants `FIGURA_CITE_AUTHOR`, `FIGURA_CITE_YEAR`, `FIGURA_CITE_URL`. `.script_header` output gains a line beginning `# Cite: `.

- [ ] **Step 1: Write the failing tests**

Append to `tests/testthat/test-script.R`:

```r
test_that(".citation_sentence names the tool, the URL, and the packages", {
  expect_equal(.citation_sentence(),
    "Analyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R in the browser.")
  expect_equal(.citation_sentence("survival"),
    "Analyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R with the survival package in the browser.")
  expect_equal(.citation_sentence(c("survival", "ggplot2")),
    "Analyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R with the survival and ggplot2 packages in the browser.")
  expect_equal(.citation_sentence(c("survival", "ggplot2", "cowplot")),
    "Analyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R with the survival, ggplot2, and cowplot packages in the browser.")
})

test_that(".citation_sentence carries no R version and no date", {
  s <- .citation_sentence(c("survival", "ggplot2"))
  expect_no_match(s, "R version")
  expect_no_match(s, format(Sys.Date(), "%Y-%m-%d"), fixed = TRUE)
  expect_no_match(s, "\n", fixed = TRUE)
})

test_that(".with_citation appends the sentence as a final paragraph", {
  out <- .with_citation("HR 1.2.", "survival")
  expect_equal(out, paste0("HR 1.2.\n\n", .citation_sentence("survival")))
})

test_that("the script header carries a # Cite: line", {
  code <- .script_assemble("Test analysis", script_spec(), c("a", "b"),
                           c("ggplot2"), c("m <- mean(df$a)"))
  expect_match(code, paste0("# Cite: ", .citation_sentence("ggplot2")), fixed = TRUE)
  env <- new.env(parent = globalenv())
  eval(parse(text = code), env)       # the header line is a comment: still runs
  expect_equal(env$m, 2.5)
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test(filter = "script")'`
Expected: 4 failures, `could not find function ".citation_sentence"`.

- [ ] **Step 3: Implement**

At the top of `R/script.R`, after the file comment block and before `.script_dep`:

```r
# ---- Citation ----------------------------------------------------------------
# ONE place to change when a DOI is minted: swap FIGURA_CITE_URL for the DOI URL.
# The sentence deliberately carries NO R version and NO date. The webR release
# gate (stats-validation, `make webr`) compares displayed sentences between
# native R and webR line by line; a version would differ between them and a
# date would change daily. R.version.string already lives in .script_header.
FIGURA_CITE_AUTHOR <- "Saha"
FIGURA_CITE_YEAR   <- "2026"
FIGURA_CITE_URL    <- "https://figurastats.org"

# The attribution sentence a manuscript's methods section needs. `pkgs` is the
# same vector the analysis hands .script_assemble, so the sentence and the
# script header name the same packages.
.citation_sentence <- function(pkgs = character(0)) {
  pkgs <- as.character(pkgs)
  n <- length(pkgs)
  runs <- if (n == 0) {
    "which runs R in the browser"
  } else if (n == 1) {
    sprintf("which runs R with the %s package in the browser", pkgs)
  } else if (n == 2) {
    sprintf("which runs R with the %s and %s packages in the browser", pkgs[1], pkgs[2])
  } else {
    sprintf("which runs R with the %s, and %s packages in the browser",
            paste(pkgs[-n], collapse = ", "), pkgs[n])
  }
  sprintf("Analyses were performed with Figura (%s, %s; %s), %s.",
          FIGURA_CITE_AUTHOR, FIGURA_CITE_YEAR, FIGURA_CITE_URL, runs)
}

# Append the sentence as the FINAL paragraph of a methods text. The blank line
# is load-bearing: the validation comparator strips exactly one trailing
# paragraph that matches the sentence (stats-validation/compare/compare.py,
# strip_citation), and the spec/*.md files document that rule.
.with_citation <- function(text, pkgs = character(0))
  paste0(text, "\n\n", .citation_sentence(pkgs))
```

In `.script_header`, change the returned vector so the cite line follows the data line:

```r
  c(sprintf("# %s — R script generated by Figura", analysis),
    sprintf("# Data: %s", source_label),
    sprintf("# Cite: %s", .citation_sentence(pkgs)),
    honesty,
    paste0("# ", R.version.string),
    if (length(pkg_lines) > 0) c("# Package versions:", pkg_lines),
    "")
```

- [ ] **Step 4: Run to verify they pass**

Run: `Rscript -e 'devtools::test(filter = "script")'`
Expected: `[ FAIL 0 | WARN 0 | SKIP 0 | PASS n ]`.

- [ ] **Step 5: Commit**

```bash
git add R/script.R tests/testthat/test-script.R
git commit -m "feat(script): citation sentence helper and # Cite: header line"
```

---

### Task 2: Every analysis appends the citation

**Files:**
- Modify: `R/km.R:160`, `R/cox.R:209`, `R/logistic.R:487`, `R/summarize.R:352`, `R/groupcompare.R:173-176` and `:240-242`, `R/explore.R:128-138`
- Test: `tests/testthat/test-km.R`, `test-cox.R`, `test-logistic.R`, `test-summarize.R`, `test-groupcompare.R`, `test-explore.R`

**Interfaces:**
- Consumes: `.with_citation(text, pkgs)`, `.citation_sentence(pkgs)` from Task 1.
- Produces: every `fig_*` text ends with the sentence (explore: its code contains a `# Cite:` line). Package vectors per analysis, identical to the ones each `.script_assemble` call already passes: km `c("survival", "ggplot2", "cowplot")`; cox `c("survival", "ggplot2")`; logistic `"ggplot2"`; summary `character(0)`; groupcompare `"ggplot2"`; explore `"ggplot2"`.

- [ ] **Step 1: Write the failing tests**

Append to each test file. Every helper named below already exists in that file (verified): `make_spec()` in `test-km.R`; `sc_cox(mk_cox_rows())` in `test-cox.R`; `sc_logit(mk_logit_rows())` in `test-logistic.R`; `mk_summary_spec()` in `test-summarize.R`; `sc(two_norm)` and `sc2(mkrows2(out, g))` in `test-groupcompare.R`; the module-level `rows_xy` in `test-explore.R`.

`tests/testthat/test-km.R`:
```r
test_that("fig_km ends with the citation paragraph", {
  out <- fig_km(make_spec())
  tail <- paste0("\n\n", .citation_sentence(c("survival", "ggplot2", "cowplot")))
  expect_true(endsWith(out$text, tail))
})
```

`tests/testthat/test-cox.R`:
```r
test_that("fig_cox ends with the citation paragraph after the methods sentence", {
  out <- fig_cox(sc_cox(mk_cox_rows()))
  tail <- paste0("\n\n", .citation_sentence(c("survival", "ggplot2")))
  expect_true(endsWith(out$text, tail))
  # TSV, blank line, methods, blank line, citation: exactly three paragraphs.
  expect_equal(length(strsplit(out$text, "\n\n", fixed = TRUE)[[1]]), 3L)
})
```
`tests/testthat/test-logistic.R`:
```r
test_that("fig_logistic ends with the citation paragraph", {
  out <- fig_logistic(sc_logit(mk_logit_rows()))
  expect_true(endsWith(out$text, paste0("\n\n", .citation_sentence("ggplot2"))))
  expect_equal(length(strsplit(out$text, "\n\n", fixed = TRUE)[[1]]), 3L)
})
```

`tests/testthat/test-summarize.R`:
```r
test_that("fig_summary ends with the citation paragraph", {
  out <- fig_summary(mk_summary_spec())
  expect_true(endsWith(out$text, paste0("\n\n", .citation_sentence())))
  expect_equal(length(strsplit(out$text, "\n\n", fixed = TRUE)[[1]]), 3L)
})
```

`tests/testthat/test-groupcompare.R` (both branches):
```r
test_that("fig_groupcompare ends with the citation paragraph for numeric and categorical outcomes", {
  num <- fig_groupcompare(sc(two_norm))
  set.seed(21)
  g <- rep(c("A", "B"), each = 60)
  yn <- c(sample(c("Yes", "No"), 60, TRUE, c(0.3, 0.7)),
          sample(c("Yes", "No"), 60, TRUE, c(0.6, 0.4)))
  cat <- fig_groupcompare(sc2(mkrows2(yn, g)))
  tail <- paste0("\n\n", .citation_sentence("ggplot2"))
  expect_true(endsWith(num$text, tail))
  expect_true(endsWith(cat$text, tail))
})
```

`tests/testthat/test-explore.R`:
```r
test_that("fig_explore's script carries a # Cite: comment and still parses", {
  out <- fig_explore(list(
    data = rows_xy,
    roles = list(x = "age", y = "bmi", color = "arm"),
    options = list(geom = "scatter", point_size = 2, alpha = 0.8,
                   smoother = "lm", se = TRUE)))
  expect_match(out$text, paste0("# Cite: ", .citation_sentence("ggplot2")), fixed = TRUE)
  expect_no_match(out$text, "Analyses were performed with Figura \\(Saha.*\\)\\.$")  # never bare prose
  expect_silent(parse(text = out$text))
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `Rscript -e 'devtools::test()'`
Expected: the six new tests fail; everything else passes.

- [ ] **Step 3: Implement**

`R/km.R` line 160:
```r
  list(svg = .svg_string(plot_obj, width = 7, height = 6),
       text = .with_citation(txt, c("survival", "ggplot2", "cowplot")),
       code = .km_script(spec, opts, n_groups, fit_expr, lr_expr, cox_expr))
```

`R/cox.R` line 209:
```r
  text <- .with_citation(paste0(tsv, "\n\n", methods), c("survival", "ggplot2"))
```

`R/logistic.R` line 487:
```r
  text <- .with_citation(paste0(tsv, "\n\n", methods), "ggplot2")
```

`R/summarize.R` line 352:
```r
  text <- .with_citation(
    paste0(paste(c(tsv_header, tsv_lines), collapse = "\n"), "\n\n", methods))
```

`R/groupcompare.R` line 176 (numeric branch):
```r
  list(svg = .svg_string(gg, width = 6, height = 4.5),
       text = .with_citation(txt, "ggplot2"),
       code = .gc_script_numeric(spec, test_expr, tname, reason, nonpar, ng))
```
and line 242 (categorical branch):
```r
  list(svg = .svg_string(gg, width = 6, height = 4.5),
       text = .with_citation(txt, "ggplot2"),
       code = .gc_script_categorical(spec, test_expr, tname,
                                     is_2x2 = all(dim(tab) == 2)))
```

`R/explore.R` line 128, the code header:
```r
  code <- c("library(ggplot2)",
    sprintf("# Cite: %s", .citation_sentence("ggplot2")), "",
    "# Load your data (edit the path):",
    '# df <- read.csv("your-data.csv", check.names = FALSE)', "")
```

- [ ] **Step 4: Run the full suite**

Run: `Rscript -e 'devtools::test()'`
Expected: `[ FAIL 0 | WARN 0 | ... ]`. If any pre-existing test asserted an exact full `text` string, update it to append the citation tail rather than loosening it.

- [ ] **Step 5: Commit**

```bash
git add R/ tests/testthat/
git commit -m "feat: every analysis appends the citation sentence to its methods text"
```

---

### Task 3: The comparator strips the citation paragraph; the specs document it

**Files:**
- Modify: `stats-validation/compare/compare.py` (near `methods_text`, ~line 783, and the four `text = figura.get("text")` sites at ~1237, ~1630, ~2188, ~2636)
- Modify: `stats-validation/spec/{km-twoarm,cox-adjusted,logistic-confounding,logistic-dirty,summary-table1,groupcompare-numeric,groupcompare-categorical,groupcompare-dirty}.md`
- Test: `stats-validation/compare/tests/test_compare.py`

**Interfaces:**
- Produces: `strip_citation(text: str | None) -> str | None` in `compare.py`, exported at module level; `methods_text` returns citation-free text.

- [ ] **Step 1: Write the failing tests**

Append to `stats-validation/compare/tests/test_compare.py` (the file already imports from `compare`; add `strip_citation, methods_text` to that import list):

```python
CITE = ("Analyses were performed with Figura (Saha, 2026; https://figurastats.org), "
        "which runs R with the survival and ggplot2 packages in the browser.")


def test_strip_citation_removes_exactly_the_trailing_paragraph():
    text = "a\tb\n\nMethods sentence. Another.\n\n" + CITE
    assert strip_citation(text) == "a\tb\n\nMethods sentence. Another."


def test_strip_citation_leaves_text_without_a_citation_alone():
    assert strip_citation("HR 1.2; log-rank p = 0.3.") == "HR 1.2; log-rank p = 0.3."
    assert strip_citation(None) is None


def test_strip_citation_does_not_touch_a_citation_like_sentence_mid_text():
    text = CITE + "\n\nReal methods."
    assert strip_citation(text) == text


def test_methods_text_is_citation_free():
    assert methods_text("tsv\n\nMethods.\n\n" + CITE) == "Methods."


def test_strip_citation_keeps_a_paragraph_that_carries_more_than_the_citation():
    # A statistical sentence sharing the citation's line is NOT swallowed: the
    # paragraph no longer matches the grammar, so it survives whole and the
    # comparator sees the extra sentence (which is the point).
    extra = "tsv\n\nMethods.\n\n" + CITE + " Median survival 12.0 months."
    assert strip_citation(extra) == extra
    # Nor is a citation whose parenthetical hides a nested paren or a second line.
    odd = "tsv\n\nMethods.\n\nAnalyses were performed with Figura (Saha (2026); x), which runs R in the browser."
    assert strip_citation(odd) == odd
    # The no-package and single-package forms are stripped like the multi-package one.
    for pk in ("", " with the survival package", " with the survival, ggplot2, and cowplot packages"):
        t = "a\n\nb.\n\nAnalyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R" + pk + " in the browser."
        assert strip_citation(t) == "a\n\nb."
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd stats-validation/compare && ../.venv/bin/python -m pytest tests/test_compare.py -q -k citation`
Expected: `ImportError: cannot import name 'strip_citation'`.

- [ ] **Step 3: Implement**

In `compare.py`, immediately above `def methods_text`:

```python
# ---------------------------------------------------------------------------
# THE CITATION PARAGRAPH. Every fig_* appends one attribution sentence as the
# FINAL paragraph of its text (R/script.R `.with_citation`; documented in each
# spec/*.md under "Display"). It carries no statistical content, but it does
# contain a number (the year), so it is stripped BEFORE any parser sees the
# text. Anchored to the end: a citation-shaped sentence anywhere else would be
# a display defect and must stay visible to the comparison.
# The grammar is exactly R/script.R `.citation_sentence`: a parenthetical with
# no nested parens, then "which runs R", an optional package clause with no
# period inside it, then "in the browser." and END OF TEXT. Anything after the
# final period — a second sentence on the same line, say — means this is not
# the bare citation paragraph, and nothing is stripped.
CITATION_RE = re.compile(
    r"\n\nAnalyses were performed with Figura \([^()\n]*\), which runs R"
    r"(?: with the [^.\n]+ packages?)? in the browser\.\Z")


def strip_citation(text):
    """`text` without its trailing citation paragraph; non-strings pass through."""
    if not isinstance(text, str):
        return text
    return CITATION_RE.sub("", text)
```

Change `methods_text` to:
```python
def methods_text(text: str) -> str:
    """The methods paragraph of a ratio_table `text` field, citation removed.
    ...(keep the existing docstring body)...
    """
    if not isinstance(text, str):
        return ""
    parts = strip_citation(text).split("\n\n", 1)
    return parts[1] if len(parts) == 2 else parts[0]
```

At each of the four sites that read `text = figura.get("text")` (km_summary, gc_summary, table1, and the ratio-table site), change to `text = strip_citation(figura.get("text"))`. Also apply it inside `parse_ratio_tsv` and `parse_table1_tsv` before their `split("\n\n")[0]` — harmless for the TSV, but it means no caller can forget.

- [ ] **Step 4: Document in every spec**

Append this block to the "Display" section of each of the eight files (for `summary-table1.md`, under "How the DECISION is surfaced in the displayed output"; for the three `groupcompare-*.md`, under whichever section describes the displayed sentence):

```markdown
### Citation paragraph (not compared)

The `text` field ends with one extra paragraph, separated from everything
above it by a blank line: a fixed attribution sentence beginning
`Analyses were performed with Figura (` and ending `in the browser.`. It
names the tool, a URL, a year, and the R packages the analysis used. It
carries no statistical content and is excluded from every comparison: the
comparator removes exactly one such trailing paragraph before parsing. An
implementer of this spec must not emit it and must not parse it.
```

- [ ] **Step 5: Run the comparator suite**

Run: `make -C stats-validation test`
Expected: green.

- [ ] **Step 6: Commit**

```bash
git add stats-validation/compare stats-validation/spec
git commit -m "validation: strip the citation paragraph before comparing; document it in every spec"
```

---

### Task 4: Content modules export `UNDERSTAND_SECTIONS`

**Files:**
- Modify: `web/guided/km/content.js`, `web/guided/summary/content.js`, `web/guided/cox/content.js`, `web/guided/logistic/content.js`, `web/guided/groupcompare/content.js`, `web/guided/explore/content.js`
- Create: `web/guided/understand-sections.test.mjs`
- Modify: `package.json` (`test:unit` chain)

**Interfaces:**
- Produces: each module exports `UNDERSTAND_SECTIONS: Array<{title: string, html: string}>` and `renderUnderstand(panel)` renders from it. The generator (Task 8) imports these.

- [ ] **Step 1: Write the failing test**

`web/guided/understand-sections.test.mjs`:
```js
import assert from "node:assert/strict";
import * as km from "./km/content.js";
import * as summary from "./summary/content.js";
import * as cox from "./cox/content.js";
import * as logistic from "./logistic/content.js";
import * as groupcompare from "./groupcompare/content.js";
import * as explore from "./explore/content.js";

const MODULES = { km, summary, cox, logistic, groupcompare, explore };

for (const [name, mod] of Object.entries(MODULES)) {
  assert.ok(Array.isArray(mod.UNDERSTAND_SECTIONS), `${name}: UNDERSTAND_SECTIONS is an array`);
  assert.ok(mod.UNDERSTAND_SECTIONS.length >= 3, `${name}: at least three sections`);
  for (const s of mod.UNDERSTAND_SECTIONS) {
    assert.equal(typeof s.title, "string");
    assert.ok(s.title.trim().length > 0, `${name}: section has a title`);
    assert.equal(typeof s.html, "string");
    assert.ok(/<p|<ul/.test(s.html), `${name}: section "${s.title}" has body HTML`);
  }
  // renderUnderstand paints from the same array — one source of truth.
  const panel = {};
  mod.renderUnderstand(panel);
  for (const s of mod.UNDERSTAND_SECTIONS) {
    assert.ok(panel.innerHTML.includes(`<h3>${s.title}</h3>`),
      `${name}: renderUnderstand renders "${s.title}"`);
  }
}
console.log("understand-sections.test.mjs OK");
```

- [ ] **Step 2: Run to verify it fails**

Run: `node web/guided/understand-sections.test.mjs`
Expected: `AssertionError: km: UNDERSTAND_SECTIONS is an array`.

- [ ] **Step 3: Implement the four array-based modules**

In `km/content.js`, `summary/content.js`, `cox/content.js`, `logistic/content.js`: rename `const SECTIONS = [` to `export const UNDERSTAND_SECTIONS = [` and change every `SECTIONS.map(` to `UNDERSTAND_SECTIONS.map(`. Nothing else changes.

- [ ] **Step 4: Convert the two inline modules**

`web/guided/groupcompare/content.js` — replace `renderUnderstand` with:
```js
export const UNDERSTAND_SECTIONS = [
  { title: "Is the difference between groups real?", html: `
    <p>A group comparison asks whether an outcome differs across two or more
      groups — a biomarker between treatment arms, a complication rate between
      centres. Pick the grouping column and the outcome; the tool chooses the
      right test.</p>` },
  { title: "The tool picks the test for you", html: `
    <ul>
      <li><strong>A number</strong> (e.g. CRP) compared across groups uses a
        t-test or ANOVA when it looks normal, and their rank-based cousins
        (Mann–Whitney, Kruskal–Wallis) when it is skewed — decided the same way
        the Summary table decides mean vs median.</li>
      <li><strong>A category</strong> (e.g. responder yes/no) uses a chi-square
        test, falling back to Fisher's exact when counts are small.</li>
    </ul>
    <p class="callout">A yes/no outcome written as <code>0</code> and
      <code>1</code> is read as a number, so it is compared with a t-test. To
      get proportions, a chi-square test, and an odds ratio instead, write the
      outcome as words — <code>Yes</code>/<code>No</code>,
      <code>Responder</code>/<code>Non-responder</code>.</p>` },
  { title: "Report more than a p-value", html: `
    <p>A p-value tells you whether a difference is detectable, not how big it is.
      Every result here also reports an <strong>effect size with a 95% confidence
      interval</strong> — what reviewers increasingly ask for. With three or more
      groups, a significant test is followed by pairwise comparisons so you can
      see <em>which</em> groups differ.</p>` },
];

export function renderUnderstand(panel) {
  panel.innerHTML = UNDERSTAND_SECTIONS.map((s) =>
    `<section><h3>${s.title}</h3>${s.html}</section>`).join("");
}
```

`web/guided/explore/content.js` — same shape with its three sections ("Map columns to a picture", "Six chart types cover most manuscripts", "The code pane is yours to keep"), prose copied verbatim from the current template, split at each `<h3>`.

The only DOM difference is a `<section>` wrapper around each heading+body, which the four other analyses already have; the e2e tests locate headings by text and are unaffected.

- [ ] **Step 5: Register the test and run the chain**

In `package.json`, append `&& node web/guided/understand-sections.test.mjs` to `test:unit` (before the `stats-validation` entries).

Run: `npm run test:unit`
Expected: every suite prints OK.

- [ ] **Step 6: Commit**

```bash
git add web/guided package.json
git commit -m "refactor(guided): export UNDERSTAND_SECTIONS from every content module"
```

---

### Task 5: Hash on load, About link, cache bump, honest comments

**Files:**
- Create: `web/lib/route.js`, `web/lib/route.test.mjs`
- Modify: `web/app.js` (after the `[data-figure]` click handlers, before `initExportUI`), `web/index.html` (rail foot), `web/sw.js:14`, `web/styles.css:6-7` (comment)
- Modify: `package.json`

**Interfaces:**
- Produces: `analysisFromHash(hash: string, known: string[]) -> string | null`.

- [ ] **Step 1: Write the failing test**

`web/lib/route.test.mjs`:
```js
import assert from "node:assert/strict";
import { analysisFromHash } from "./route.js";

const KNOWN = ["summary", "km", "explore", "groupcompare", "cox", "logistic"];
assert.equal(analysisFromHash("", KNOWN), null);
assert.equal(analysisFromHash(undefined, KNOWN), null);
assert.equal(analysisFromHash("#km", KNOWN), "km");
assert.equal(analysisFromHash("#km/analyze", KNOWN), "km");
assert.equal(analysisFromHash("#km/example", KNOWN), "km");
assert.equal(analysisFromHash("#nope/analyze", KNOWN), null);
assert.equal(analysisFromHash("#km/analyze/extra", KNOWN), null);
assert.equal(analysisFromHash("#km/analyze?csv=x", KNOWN), null);   // never inputs
console.log("route.test.mjs OK");
```

- [ ] **Step 2: Run to verify it fails**

Run: `node web/lib/route.test.mjs`
Expected: `Cannot find module .../web/lib/route.js`.

- [ ] **Step 3: Implement**

`web/lib/route.js`:
```js
// web/lib/route.js
// The URL hash carries analysis and stage ONLY — `#<analysis>/<stage>` — never
// inputs, filenames or results (web/guided/shell.js owns the stage half). This
// reads the analysis half once at load so a landing page can deep-link into
// the app; `known` is the rail's registry, so an unknown prefix is ignored.
export function analysisFromHash(hash, known) {
  const m = /^#(\w+)(?:\/\w+)?$/.exec(hash || "");
  return m && known.includes(m[1]) ? m[1] : null;
}
```

`web/app.js`, after the `document.querySelectorAll("[data-figure]").forEach(...)` block and before `initExportUI`:
```js
import { analysisFromHash } from "./lib/route.js";
// Deep link from a landing page (web/<slug>/index.html → "/#km/example"):
// select the analysis the hash names; the guided shell then reads the stage
// from the same hash exactly as it does for an in-app tab click.
{
  const fromHash = analysisFromHash(location.hash, Object.keys(forms));
  if (fromHash) document.querySelector(`[data-figure="${fromHash}"]`)?.click();
}
```

`web/index.html` rail foot, after the "Statistical validation" block:
```html
        <div class="rail-feedback">
          <p class="fb-prompt">What is this, and how do I cite it?</p>
          <a class="fb-copy" href="about/">
            <span class="fb-addr">About Figura</span>
          </a>
        </div>
```

`web/sw.js` line 14: `const CACHE = "figura-v12";` and update the trailing comment to `// v11 -> v12: landing pages, About link, hash deep-link.`

`web/styles.css` lines 6–7, replace the comment sentence with:
```
   Fonts are SELF-HOSTED (web/fonts/): the app's own code makes no network
   call beyond webR and its own files — never link a font CDN here. (Cloudflare
   injects its Web Analytics beacon at the edge; that is disclosed in /about/.)
```

- [ ] **Step 4: Register the test and run**

Append `&& node web/lib/route.test.mjs` to `test:unit`. Run: `npm run test:unit`. Expected: all OK, including `web/sw.test.mjs`.

- [ ] **Step 5: Commit**

```bash
git add web/lib/route.js web/lib/route.test.mjs web/app.js web/index.html web/sw.js web/styles.css package.json
git commit -m "feat(app): open the analysis named in the URL hash; About link; cache bump"
```

---

### Task 6: Render the six example outputs with native R

**Files:**
- Create: `scripts/pages/registry.mjs` (the part Task 8 extends), `scripts/pages/example-specs.mjs`, `scripts/pages/render-examples.R`
- Modify: `package.json` (`build:examples`), `.gitignore`
- Output: `web/<slug>/example.json` × 6

**Interfaces:**
- Produces: `registry.mjs` exports `SITE`, `PAGES` (array of `{slug, key, title, description, lede, sections, demo}` where `sections` is the module's `UNDERSTAND_SECTIONS` and `demo` is `{label, columns, rows}`), `pageFor(key)`. `example.json` shape: `{"svg": "<...>", "text": "..."}` exactly as `render_figure` returned.

- [ ] **Step 1: Write the registry (data only for now)**

`scripts/pages/registry.mjs`:
```js
// scripts/pages/registry.mjs
// THE ONE TABLE: slug ↔ analysis key ↔ page copy ↔ the modules a page is
// generated from. A new analysis is one entry here plus `npm run
// build:examples && npm run build:pages`; build.test.mjs fails if this table
// and web/index.html's [data-figure] buttons disagree.
import { UNDERSTAND_SECTIONS as SUMMARY_SECTIONS } from "../../web/guided/summary/content.js";
import { UNDERSTAND_SECTIONS as KM_SECTIONS } from "../../web/guided/km/content.js";
import { UNDERSTAND_SECTIONS as GC_SECTIONS } from "../../web/guided/groupcompare/content.js";
import { UNDERSTAND_SECTIONS as COX_SECTIONS } from "../../web/guided/cox/content.js";
import { UNDERSTAND_SECTIONS as LOGISTIC_SECTIONS } from "../../web/guided/logistic/content.js";
import { UNDERSTAND_SECTIONS as EXPLORE_SECTIONS } from "../../web/guided/explore/content.js";
import { TEACHING_VISUAL_SVG, TEACHING_VISUAL_ALT } from "../../web/guided/km/teaching-visual.js";
import { SUMMARY_DEMO } from "../../web/guided/summary/demo-data.js";
import { KM_DEMO } from "../../web/guided/km/demo-data.js";
import { GROUPCOMPARE_DEMO } from "../../web/guided/groupcompare/demo-data.js";
import { COX_DEMO } from "../../web/guided/cox/demo-data.js";
import { LOGISTIC_DEMO } from "../../web/guided/logistic/demo-data.js";
import { EXPLORE_DEMO } from "../../web/guided/explore/demo-data.js";
import { buildSummaryDemoSpec } from "../../web/guided/summary/demo.js";
import { buildDemoSpec as buildKmDemoSpec } from "../../web/guided/km/demo.js";
import { buildGroupCompareDemoSpec, DEFAULT_DEMO_STATE as GC_STATE } from "../../web/guided/groupcompare/demo.js";
import { buildCoxDemoSpec, DEFAULT_DEMO_STATE as COX_STATE } from "../../web/guided/cox/demo.js";
import { buildLogisticDemoSpec, DEFAULT_DEMO_STATE as LOGISTIC_STATE } from "../../web/guided/logistic/demo.js";
import { buildExploreDemoSpec, DEFAULT_DEMO_STATE as EXPLORE_STATE } from "../../web/guided/explore/demo.js";

export const SITE = "https://figurastats.org";

// Same wording as R/script.R `.citation_sentence` with no package clause; the
// R side is the source of truth and test-script.R pins its exact text.
export const CITATION =
  "Saha S. Figura: clinical manuscript figures and statistics in the browser. 2026. https://figurastats.org";
export const BIBTEX = `@misc{figura2026,
  author = {Saha, Sandeep},
  title  = {Figura: clinical manuscript figures and statistics in the browser},
  year   = {2026},
  url    = {https://figurastats.org},
  note   = {Accessed <date>}
}`;

// Demo specs use each shell's default demo options (web/guided/*/guided-*.js),
// so the example on the page is the example the user first sees in the app.
// `textKind` defaults to "methods" (a paste-ready methods sentence, or a TSV
// table followed by one). Explore's `text` is its ggplot2 SCRIPT, so it is
// labelled as code and never as methods text.
export const PAGES = [
  { slug: "table-1", key: "summary", title: "Table 1 baseline characteristics",
    description: "A journal-ready baseline characteristics table from a CSV: mean ± SD or median (IQR) chosen per variable by a normality check, n (%) for categories, missing counts per row, no p-values.",
    lede: "Upload a CSV, tick the variables, and get a Table 1 that a reviewer will not send back. Figura tests each continuous variable for normality within your groups and reports mean ± SD or median (IQR) accordingly, with the reason on the row.",
    sections: SUMMARY_SECTIONS, demo: SUMMARY_DEMO,
    demoSpec: () => buildSummaryDemoSpec({ groupBy: "arm", showPlots: true, forceMean: false, showQq: false }) },
  { slug: "kaplan-meier", key: "km", title: "Kaplan–Meier survival curves",
    description: "Kaplan–Meier curves with confidence bands, censor marks, a number-at-risk table, median survival, a log-rank test and an optional hazard ratio, computed by R's survival package in your browser.",
    lede: "Time-to-event data in, a publication-ready survival figure out: curves per group with pointwise confidence bands, a number-at-risk table beneath, median survival, and a log-rank test. R's survival and ggplot2 packages do the work, inside your browser tab.",
    sections: KM_SECTIONS, demo: KM_DEMO,
    teachingVisual: { svg: TEACHING_VISUAL_SVG, alt: TEACHING_VISUAL_ALT },
    demoSpec: () => buildKmDemoSpec({ conf_int: true, landmarks: [], horizon: null }) },
  { slug: "group-comparison", key: "groupcompare", title: "Group comparison",
    description: "Compare an outcome across two or more groups: t-test, ANOVA, Mann–Whitney, Kruskal–Wallis, chi-square or Fisher's exact, chosen for you, with an effect size, 95% CI, p-value and post-hoc pairs.",
    lede: "Pick a grouping column and an outcome. Figura chooses the right test from the data's shape, reports an effect size with a 95% confidence interval rather than a bare p-value, and runs pairwise comparisons when there are three or more groups.",
    sections: GC_SECTIONS, demo: GROUPCOMPARE_DEMO,
    demoSpec: () => buildGroupCompareDemoSpec(GC_STATE()) },
  { slug: "cox-regression", key: "cox", title: "Cox proportional-hazards regression",
    description: "Univariable and multivariable Cox regression from a CSV: a Table 3 of unadjusted and adjusted hazard ratios with 95% CIs, a forest plot, and a proportional-hazards check.",
    lede: "Map time, status and covariates, and get the Table 3 a manuscript needs: unadjusted hazard ratios beside adjusted ones from the joint model, a forest plot of the adjusted estimates, and a proportional-hazards check reported without blocking the fit.",
    sections: COX_SECTIONS, demo: COX_DEMO,
    demoSpec: () => buildCoxDemoSpec(COX_STATE()) },
  { slug: "logistic-regression", key: "logistic", title: "Logistic regression odds ratios",
    description: "Univariable and multivariable logistic regression from a CSV: unadjusted and adjusted odds ratios with 95% CIs, a forest plot, per-increment scaling for continuous covariates, and separation, EPV, C-statistic and VIF checks.",
    lede: "A binary outcome, a set of covariates, and a Table 3 of odds ratios: unadjusted and adjusted side by side, a forest plot on a log axis, and continuous covariates reported per a clinically meaningful step such as age per 10 years.",
    sections: LOGISTIC_SECTIONS, demo: LOGISTIC_DEMO,
    demoSpec: () => buildLogisticDemoSpec(LOGISTIC_STATE()) },
  { slug: "explore-plot", key: "explore", title: "Explore plot with ggplot2",
    description: "An interactive ggplot2 builder: scatter, line, box, violin, bar and histogram from your CSV, with the exact R code that drew the figure ready to paste.",
    lede: "Map columns to x, y, colour and facets and watch the figure redraw. Every plot comes with the ggplot2 code that produced it, so the explorer doubles as a way to learn the grammar of graphics on your own data.",
    sections: EXPLORE_SECTIONS, demo: EXPLORE_DEMO, textKind: "code",
    demoSpec: () => buildExploreDemoSpec(EXPLORE_STATE()) },
];

export function pageFor(key) {
  const p = PAGES.find((x) => x.key === key);
  if (!p) throw new Error(`no page registered for analysis "${key}"`);
  return p;
}
```

- [ ] **Step 2: The spec writer**

`scripts/pages/example-specs.mjs`:
```js
// Writes each registered page's demo spec to scripts/pages/.build/<slug>.spec.json
// for render-examples.R. Run from the repo root.
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { PAGES } from "./registry.mjs";

const out = path.resolve("scripts/pages/.build");
await mkdir(out, { recursive: true });
for (const p of PAGES) {
  const spec = p.demoSpec();
  await writeFile(path.join(out, `${p.slug}.spec.json`), JSON.stringify(spec));
  console.log(`wrote .build/${p.slug}.spec.json (${p.key})`);
}
```

- [ ] **Step 3: The R renderer**

`scripts/pages/render-examples.R`:
```r
# Renders each demo spec in scripts/pages/.build/*.spec.json through the real
# render_figure() and writes web/<slug>/example.json = {svg, text}. Run from
# the repo root:  npm run build:examples
# The output is COMMITTED so the page generator (build.mjs) needs no R.
devtools::load_all(quiet = TRUE)
specs <- Sys.glob("scripts/pages/.build/*.spec.json")
stopifnot(length(specs) > 0)
for (sp in specs) {
  slug <- sub("\\.spec\\.json$", "", basename(sp))
  res <- jsonlite::fromJSON(render_figure(paste(readLines(sp, warn = FALSE), collapse = "\n")),
                            simplifyVector = FALSE)
  if (!isTRUE(res$ok)) stop(sprintf("render_figure failed for %s: %s", slug, res$error))
  dir.create(file.path("web", slug), showWarnings = FALSE)
  jsonlite::write_json(list(svg = res$svg, text = res$text),
                       file.path("web", slug, "example.json"),
                       auto_unbox = TRUE, pretty = TRUE)
  cat(sprintf("wrote web/%s/example.json\n", slug))
}
```

- [ ] **Step 4: Wire the scripts and ignore the scratch dir**

`package.json` scripts: add
```json
"build:examples": "node scripts/pages/example-specs.mjs && Rscript scripts/pages/render-examples.R",
```
`.gitignore`: append `scripts/pages/.build/`.

- [ ] **Step 5: Run it and inspect**

Run: `npm run build:examples`
Expected: six `wrote web/<slug>/example.json` lines. Then:
```bash
for s in table-1 kaplan-meier group-comparison cox-regression logistic-regression explore-plot; do
  node -e "const j=require('./web/$s/example.json'); console.log('$s', j.svg.length, JSON.stringify(j.text.slice(-60)))"
done
```
Expected: each `text` ends with `in the browser."` (explore's ends with its ggplot2 code; check its `# Cite:` line with `grep -c "Cite:" web/explore-plot/example.json` → 1). Each `svg` is non-empty; `table-1`, `cox-regression`, `logistic-regression` start with `<div class="summary-output"` or `<table`.

Run twice and diff: `npm run build:examples && git status --short web/` must show the six files; run again and `git diff --stat web/*/example.json` must be empty (determinism).

- [ ] **Step 6: Commit**

```bash
git add scripts/pages/registry.mjs scripts/pages/example-specs.mjs scripts/pages/render-examples.R package.json .gitignore web/*/example.json
git commit -m "build(pages): registry and committed native-R example renders for the six analyses"
```

---

### Task 7: `web/pages.css`

**Files:**
- Create: `web/pages.css`

**Interfaces:**
- Produces: classes used by Task 8's templates: `.doc`, `.card`, `.eyebrow`, `.lede`, `.page-nav`, `.cta`, `.cta-row`, `.example`, `.example-text`, `.cite`, `.doc-foot`, `.wordmark`, `.teaching-visual`.

- [ ] **Step 1: Write the stylesheet**

Copy the document-layout rules from `web/validation.html`'s inline `<style>` (the `html, body`, dark-scheme `:root` remap, `.doc`, `.card`, `.eyebrow`, `.doc h1/h2/h3/h4/ul/li/code/a`, `.lede`, `.wordmark` rules) verbatim into `web/pages.css` under a header comment:

```css
/* web/pages.css — the seven crawlable pages (web/<slug>/index.html), in the
   app's own tokens. styles.css is LINKED beside this file, never copied, so a
   page cannot drift from the shipped design system. This file holds only what
   a workbench stylesheet cannot: a scrolling document and a dark remap. Every
   colour is a token from styles.css, never a literal. validation.html carries
   the same rules inline because a different builder generates it. */
```

Then append the page-specific rules:
```css
/* ---- Landing-page pieces ------------------------------------------------ */
.page-nav { display: flex; flex-wrap: wrap; gap: .25rem 1rem; margin: .75rem 0 1.5rem;
  font: .8125rem/1.5 var(--sans); color: var(--ink-muted); }
.page-nav a { color: var(--ink-muted); text-decoration: none; }
.page-nav a:hover, .page-nav a[aria-current] { color: var(--accent); text-decoration: underline; }

.cta-row { display: flex; flex-wrap: wrap; gap: .625rem; margin: 1.25rem 0 2rem; }
.cta { display: inline-block; padding: .625rem 1rem; border-radius: var(--radius-ctl);
  font: 600 .875rem/1.2 var(--sans); text-decoration: none;
  background: var(--accent); color: var(--paper); border: 1px solid var(--accent); }
.cta:hover { background: var(--accent-dark); border-color: var(--accent-dark); }
.cta.secondary { background: transparent; color: var(--accent); }
.cta.secondary:hover { background: var(--accent-wash); }
@media (pointer: coarse) { .cta { font-size: 16px; } }

.example { margin: 1rem 0 0; }
.example figure { margin: 0; }
.example svg { display: block; max-width: 100%; height: auto; }
.example .summary-output { overflow-x: auto; }
.example figcaption { font: italic .8125rem/1.5 var(--serif); color: var(--ink-muted); margin-top: .5rem; }
.example-text { margin: 1rem 0 0; padding: .75rem 1rem; border-left: 3px solid var(--line);
  font: .8125rem/1.6 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere;
  background: var(--panel-raised); color: var(--ink-2); }

.cite pre { margin: .5rem 0 0; padding: .75rem 1rem; font: .8125rem/1.5 var(--mono);
  background: var(--panel-raised); border: 1px solid var(--line-soft);
  border-radius: 3px; white-space: pre-wrap; overflow-wrap: anywhere; }

.doc-foot { margin-top: 3rem; padding-top: 1.25rem; border-top: 1px solid var(--line);
  font-size: .8125rem; color: var(--ink-muted); }
.doc-foot p { margin: .375rem 0; }
.teaching-visual svg { max-width: 100%; height: auto; }
```

Every variable above exists in `styles.css` (`--paper`, `--radius-ctl`, `--accent-wash`, `--panel-raised`, `--line-soft`, `--sans`, `--serif`, `--mono` are all defined there).

- [ ] **Step 2: Verify no literal colours**

Run: `grep -nE "#[0-9a-fA-F]{3,6}\b" web/pages.css | grep -v "prefers-color-scheme" | grep -v "^\s*--"`
Expected: only lines inside the dark-scheme `:root { --token: #... }` block (those define tokens; that is the one place literals belong).

- [ ] **Step 3: Commit**

```bash
git add web/pages.css
git commit -m "style(pages): document layout for the landing pages, tokens only"
```

---

### Task 8: The generator, the pages, the sitemap

**Files:**
- Create: `scripts/pages/html.mjs`, `scripts/pages/build.mjs`, `scripts/pages/build.test.mjs`
- Modify: `scripts/pages/registry.mjs` (nothing new; consumed), `package.json`
- Output: `web/<slug>/index.html`, `web/<slug>/sample.csv` × 6, `web/about/index.html`, `web/sitemap.xml`, `web/robots.txt`

**Interfaces:**
- Consumes: `PAGES`, `SITE`, `CITATION`, `BIBTEX` from `registry.mjs`; `toCsv(rows, columns)` from `web/lib/csv.js`; `web/<slug>/example.json` from Task 6.
- Produces: `buildAll({ webDir }) -> Promise<Map<string, string>>` keyed by path relative to `web/` (e.g. `"kaplan-meier/index.html"`); `main()` writes them. Templates: `renderAnalysisPage(page, example, nav) -> string`, `renderAboutPage(nav) -> string`, `renderSitemap(urls) -> string`, `renderRobots() -> string`, `escapeHtml(s) -> string`.

- [ ] **Step 1: Write the failing test**

`scripts/pages/build.test.mjs` (runs from the repo root):
```js
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { buildAll } from "./build.mjs";
import { PAGES, SITE } from "./registry.mjs";
import { parseCsv } from "../../web/lib/csv.js";

const webDir = path.resolve("web");
const built = await buildAll({ webDir });

// 1. Registry ↔ rail parity: every analysis the app offers has a page, and
//    no page names an analysis the app does not offer.
const indexHtml = await readFile(path.join(webDir, "index.html"), "utf8");
const railKeys = [...indexHtml.matchAll(/data-figure="(\w+)"/g)].map((m) => m[1]).sort();
assert.deepEqual(PAGES.map((p) => p.key).sort(), railKeys, "registry keys == rail buttons");

// 2. Freshness: what this commit builds is what is committed.
for (const [rel, content] of built) {
  const committed = await readFile(path.join(webDir, rel), "utf8");
  assert.equal(committed, content,
    `${rel} is stale — run \`npm run build:pages\` and commit the result`);
}

// 3. Structure of every analysis page.
const expectedUrls = new Set([`${SITE}/`, `${SITE}/validation.html`, `${SITE}/about/`,
  ...PAGES.map((p) => `${SITE}/${p.slug}/`)]);
for (const p of PAGES) {
  const html = built.get(`${p.slug}/index.html`);
  assert.ok(html, `${p.slug}/index.html built`);
  assert.equal((html.match(/<h1[\s>]/g) || []).length, 1, `${p.slug}: exactly one <h1>`);
  assert.ok(html.includes(`<title>${p.title} — Figura</title>`), `${p.slug}: title`);
  assert.ok(html.includes(`<meta name="description" content="`), `${p.slug}: description`);
  assert.ok(html.includes(`<link rel="canonical" href="${SITE}/${p.slug}/">`), `${p.slug}: canonical`);
  assert.ok(html.includes(`href="../#${p.key}/example"`), `${p.slug}: example button`);
  assert.ok(html.includes(`href="../#${p.key}/analyze"`), `${p.slug}: analyze button`);
  assert.ok(html.includes("Analyses were performed with Figura"), `${p.slug}: citation`);
  for (const s of p.sections)
    assert.ok(html.includes(`<h2>${s.title}</h2>`), `${p.slug}: section "${s.title}"`);
  // Code output is never labelled as methods text.
  const labelledAsMethods = html.includes("ready to paste into a methods section");
  assert.equal(labelledAsMethods, p.textKind !== "code", `${p.slug}: example text label matches its kind`);
  // No off-origin FETCHED resource: stylesheets, scripts, images. Plain links
  // (canonical, og:url, nav) are allowed to be absolute — they are not fetched.
  const fetched = [
    ...html.matchAll(/<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"/g),
    ...html.matchAll(/<script[^>]*src="([^"]+)"/g),
    ...html.matchAll(/<img[^>]*src="([^"]+)"/g),
  ].map((m) => m[1]);
  for (const url of fetched) {
    const origin = /^(https?:)?\/\//.test(url) ? new URL(url, SITE).origin : SITE;
    assert.equal(origin, SITE, `${p.slug}: off-origin resource ${url}`);
  }
  assert.ok(html.includes(`<link rel="canonical" href="${SITE}/${p.slug}/">`));
  // Sample CSV round-trips through the app's own parser.
  const csv = built.get(`${p.slug}/sample.csv`);
  const table = parseCsv(csv);
  assert.deepEqual(table.columns, p.demo.columns, `${p.slug}: sample.csv columns`);
  assert.equal(table.rows.length, p.demo.rows.length, `${p.slug}: sample.csv rows`);
}

// 4. About, sitemap, robots.
const about = built.get("about/index.html");
assert.ok(about.includes("Web Analytics"), "About discloses the Cloudflare beacon");
assert.ok(about.includes("/cdn-cgi/rum"), "About names the beacon path");
assert.ok(about.includes("@misc{figura2026"), "About carries BibTeX");
const sitemap = built.get("sitemap.xml");
const locs = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
assert.deepEqual(new Set(locs), expectedUrls, "sitemap lists exactly the nine URLs");
assert.equal(locs.length, 9);
assert.ok(built.get("robots.txt").includes(`Sitemap: ${SITE}/sitemap.xml`));
console.log("build.test.mjs OK");
```

- [ ] **Step 2: Run to verify it fails**

Run: `node scripts/pages/build.test.mjs`
Expected: `Cannot find module .../scripts/pages/build.mjs`.

- [ ] **Step 3: Write the templates**

`scripts/pages/html.mjs`:
```js
// scripts/pages/html.mjs — pure string templates for the generated pages.
import { SITE, CITATION, BIBTEX } from "./registry.mjs";

export function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// One <head> for every page. Relative asset paths (../) keep the pages
// subpath-safe, the same reason sw.js resolves against its scope.
function head({ title, description, canonical }) {
  const t = escapeHtml(`${title} — Figura`);
  const d = escapeHtml(description);
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${t}</title>
<meta name="description" content="${d}">
<link rel="canonical" href="${canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Figura">
<meta property="og:url" content="${canonical}">
<meta property="og:title" content="${t}">
<meta property="og:description" content="${d}">
<meta property="og:image" content="${SITE}/preview.png">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Figura: real R, running in your browser — beside a journal-style Table 1 of baseline characteristics.">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="../styles.css">
<link rel="stylesheet" href="../pages.css">
</head>`;
}

// nav = [{href, label, current}] — rendered on every page.
function pageNav(nav) {
  return `<nav class="page-nav" aria-label="Site">` + nav.map((n) =>
    `<a href="${n.href}"${n.current ? ' aria-current="page"' : ""}>${escapeHtml(n.label)}</a>`
  ).join("") + `</nav>`;
}

function masthead() {
  return `<header class="toolbar"><a class="wordmark" href="../">Figura</a></header>`;
}

function citeBlock() {
  return `<section class="cite" id="cite">
<h2>How to cite</h2>
<p>Journals ask for a software statement. The methods text Figura generates already ends with one; this is the same attribution in reference form.</p>
<pre>${escapeHtml(CITATION)}</pre>
<pre>${escapeHtml(BIBTEX)}</pre>
</section>`;
}

function foot() {
  return `<footer class="doc-foot">
<p>Figura runs R in your browser via webR. There is no backend: your CSV and your results never leave the tab. <a href="../about/">What the page does connect to, and why</a>.</p>
<p><a href="../validation.html">How the numbers are checked</a> · Feedback: feedback@figurastats.org</p>
</footer>`;
}

export function renderAnalysisPage(page, example, nav) {
  const canonical = `${SITE}/${page.slug}/`;
  const sections = page.sections.map((s) =>
    `<section><h2>${escapeHtml(s.title)}</h2>${s.html}</section>`).join("\n");
  const teaching = page.teachingVisual
    ? `<figure class="teaching-visual" aria-label="${escapeHtml(page.teachingVisual.alt)}">${page.teachingVisual.svg}<figcaption><strong>Illustration—not computed data.</strong></figcaption></figure>`
    : "";
  const exampleBlock = example.svg.trimStart().startsWith("<svg")
    ? `<figure>${example.svg}<figcaption>${escapeHtml(page.demo.label)}: the figure Figura renders for the example dataset.</figcaption></figure>`
    : `<figure>${example.svg}<figcaption>${escapeHtml(page.demo.label)}: the table Figura renders for the example dataset.</figcaption></figure>`;
  return `${head({ title: page.title, description: page.description, canonical })}
<body>
<div class="doc">
${masthead()}
${pageNav(nav)}
<article class="card">
<p class="eyebrow">Guided analysis</p>
<h1>${escapeHtml(page.title)}</h1>
<p class="lede">${escapeHtml(page.lede)}</p>
<div class="cta-row">
<a class="cta" href="../#${page.key}/example">See the worked example</a>
<a class="cta secondary" href="../#${page.key}/analyze">Analyze your data</a>
</div>
${sections}
${teaching}
<section class="example">
<h2>Example output</h2>
${exampleBlock}
${page.textKind === "code"
  ? `<p>The ggplot2 code Figura produced for this example — the exact call that drew the figure, ready to run in your own R session:</p>`
  : `<p>The text Figura produced for this example, ready to paste into a methods section:</p>`}
<pre class="example-text">${escapeHtml(example.text)}</pre>
</section>
<section>
<h2>Sample data</h2>
<p><a href="sample.csv" download>Download sample.csv</a> — ${page.demo.rows.length} rows, columns <code>${page.demo.columns.map(escapeHtml).join("</code>, <code>")}</code>. A frozen synthetic dataset generated by a script in the repository's <code>data-raw/</code> folder; nothing in it is a real patient.</p>
</section>
${citeBlock()}
</article>
${foot()}
</div>
</body>
</html>
`;
}

export function renderAboutPage(nav) {
  const canonical = `${SITE}/about/`;
  return `${head({ title: "About Figura", description: "What Figura is, whether you can use it with patient data, what the page connects to, how the numbers are checked, and how to cite it.", canonical })}
<body>
<div class="doc">
${masthead()}
${pageNav(nav)}
<article class="card">
<p class="eyebrow">About</p>
<h1>About Figura</h1>
<p class="lede">Figura makes journal-ready tables and figures for clinical manuscripts: a Table 1, Kaplan–Meier curves, group comparisons, Cox and logistic regression tables, and ggplot2 figures. Real R packages do the statistics, running inside your browser through webR. It is free, and it has no server.</p>

<h2>Can I use this with patient data?</h2>
<p><strong>Your data stays in the tab.</strong> There is no backend, no upload, and no request that carries any part of your CSV or any result. R runs in a Web Worker in your browser; the figures you download are produced there.</p>
<p><strong>What the page does connect to.</strong> Three things, and nothing else:</p>
<ul>
<li>the webR runtime and R packages, downloaded from the webR content delivery network the first time you run an analysis;</li>
<li>Figura's own files from this domain: the app, the R sources, self-hosted fonts;</li>
<li>Cloudflare Web Analytics, a small beacon Cloudflare injects at the network edge. It reports that a page loaded, the referring site, country, device type and browser to Cloudflare. It carries no uploaded research data and no analysis results; nothing from your files is in it. You can see it in your browser's network panel as a request to <code>/cdn-cgi/rum</code>.</li>
</ul>
<p>You can verify all of this yourself: open the browser's developer tools, watch the network panel while you run an analysis, and confirm that no request leaves with your data.</p>

<h2>How the numbers are checked</h2>
<p>Every statistic Figura reports on eight fixed test datasets is re-derived by an independent Python implementation written from a specification rather than from Figura's R, and every difference is published. <a href="../validation.html">Read the validation page</a>.</p>

${citeBlock()}

<h2>Feedback</h2>
<p>Write to feedback@figurastats.org. Bugs, ideas, and analyses you wish it had are all welcome.</p>

<h2>The analyses</h2>
<ul>
${nav.filter((n) => n.slug).map((n) => `<li><a href="${n.href}">${escapeHtml(n.label)}</a></li>`).join("\n")}
</ul>
</article>
${foot()}
</div>
</body>
</html>
`;
}

export function renderSitemap(urls) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u}</loc></url>`).join("\n")}
</urlset>
`;
}

export function renderRobots() {
  return `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`;
}
```

- [ ] **Step 4: Write the builder**

`scripts/pages/build.mjs`:
```js
// scripts/pages/build.mjs — generates the crawlable pages into web/.
//   npm run build:pages
// Deterministic: same inputs, byte-identical output (build.test.mjs pins it).
// Inputs: registry.mjs (copy + imported UNDERSTAND_SECTIONS + demo data) and
// the committed web/<slug>/example.json renders (npm run build:examples).
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { PAGES, SITE } from "./registry.mjs";
import { toCsv } from "../../web/lib/csv.js";
import { renderAnalysisPage, renderAboutPage, renderSitemap, renderRobots } from "./html.mjs";

export async function buildAll({ webDir }) {
  const out = new Map();
  const navFor = (currentSlug) => [
    { href: "../", label: "App" },
    ...PAGES.map((p) => ({ href: `../${p.slug}/`, label: p.title, slug: p.slug,
                           current: p.slug === currentSlug })),
    { href: "../about/", label: "About", current: currentSlug === "about" },
    { href: "../validation.html", label: "Validation" },
  ];
  for (const p of PAGES) {
    const example = JSON.parse(
      await readFile(path.join(webDir, p.slug, "example.json"), "utf8"));
    out.set(`${p.slug}/index.html`, renderAnalysisPage(p, example, navFor(p.slug)));
    out.set(`${p.slug}/sample.csv`, toCsv(p.demo.rows, p.demo.columns));
  }
  out.set("about/index.html", renderAboutPage(navFor("about")));
  out.set("sitemap.xml", renderSitemap([
    `${SITE}/`, `${SITE}/validation.html`, `${SITE}/about/`,
    ...PAGES.map((p) => `${SITE}/${p.slug}/`)]));
  out.set("robots.txt", renderRobots());
  return out;
}

export async function main() {
  const webDir = path.resolve("web");
  const built = await buildAll({ webDir });
  for (const [rel, content] of built) {
    const target = path.join(webDir, rel);
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content);
    console.log(`wrote web/${rel}`);
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === new URL(import.meta.url).pathname) {
  await main();
}
```

- [ ] **Step 5: Generate, register, and run the test**

`package.json` scripts: add `"build:pages": "node scripts/pages/build.mjs"` and append `&& node scripts/pages/build.test.mjs` to `test:unit`.

Run: `npm run build:pages && node scripts/pages/build.test.mjs`
Expected: 15 `wrote web/...` lines, then `build.test.mjs OK`. If `toCsv` throws on a demo value containing a comma, that is a real finding: report it, do not patch the CSV writer.

Run: `npm run test:unit` — all OK.

- [ ] **Step 6: Look at one page**

Run: `rm -rf web/R && cp -R R web/R && npm run serve` and open `http://localhost:8321/kaplan-meier/`. Check: fonts load (Plex/Source Serif), the KM SVG renders at width, both buttons open the app at the right analysis and stage, the nav links resolve, dark mode remaps. Then open `/table-1/` and confirm the table renders inside its galley sheet. Stop the server.

- [ ] **Step 7: Commit**

```bash
git add scripts/pages/html.mjs scripts/pages/build.mjs scripts/pages/build.test.mjs package.json web/*/index.html web/*/sample.csv web/sitemap.xml web/robots.txt
git commit -m "feat(pages): generate six analysis pages, About, sitemap and robots from the app's own modules"
```

---

### Task 9: Correct the "no analytics" claims that are live today

**Files:**
- Modify: `stats-validation/build_scorecard.py` (~line 2172–2176, the `doc-foot` template, and the comment at ~line 806 that says "No analytics"), `CLAUDE.md` (the "No data egress" paragraph), `README.md` (lines 11–16)

**Interfaces:** none.

- [ ] **Step 1: The validation page footer**

In `build_scorecard.py`, replace the footer paragraph text with:
```
<p>Figura runs entirely in your browser: there is no backend that could receive
your data, and this page adds none. It loads the app's own stylesheet and
self-hosted fonts. Cloudflare, which serves the site, injects its Web
Analytics beacon at the edge (a page-load count with referrer, country and
device type; no uploaded research data or analysis results) &mdash; see <a href="about/">About</a>.</p>
```

- [ ] **Step 2: `CLAUDE.md`**

Replace the "No data egress" paragraph's first two sentences with:

> **No data egress.** The app's own code makes only two kinds of network call: the webR runtime/packages from the CDN and `fetch("R/*.R")`. Nothing carries user data or results, and there is no upload — this is an invariant, not a preference. **Cloudflare Web Analytics is enabled** (edge-injected beacon to `/cdn-cgi/rum`: page load, referrer, country, device, browser; no uploaded research data or analysis results) and must be disclosed wherever the app describes what it connects to — `web/about/`, the validation page footer, this paragraph. Never write "no analytics".

Keep the rest of the paragraph (statistics in R, fonts self-hosted) unchanged.

- [ ] **Step 3: `README.md`**

Replace the sentence `There is no analytics.` in the "Your data never leaves your browser" paragraph with:

> The only network requests the app itself makes are for the webR runtime and R packages from the r-wasm CDN. Cloudflare, which serves the site, injects a Web Analytics beacon at the edge: it reports that a page loaded, the referrer, country, device type and browser, and carries no uploaded research data or analysis results. See [About](https://figurastats.org/about/).

Also change the `build_scorecard.py` comment at ~line 806 from "No analytics, no CDN font, no external link" to "No CDN font, no external link; the Cloudflare analytics beacon is edge-injected and disclosed in the footer".

- [ ] **Step 4: Regenerate and check**

Run: `cd stats-validation && .venv/bin/python build_scorecard.py --web && cd .. && grep -c "Web Analytics" web/validation.html`
Expected: `1`. (The full `make all` in Task 12 regenerates it again; this step only confirms the template change renders.)

- [ ] **Step 5: Commit**

```bash
git add stats-validation/build_scorecard.py CLAUDE.md README.md web/validation.html
git commit -m "docs: disclose the Cloudflare analytics beacon wherever the app describes its network calls"
```

---

### Task 10: Playwright: landing page deep-links into the app

**Files:**
- Create: `tests/e2e/pages.spec.js`

- [ ] **Step 1: Write the test**

```js
const { test, expect } = require("@playwright/test");

// The landing pages are static HTML; this checks the one thing that crosses
// into the app — the hash deep link — and that the page itself is served with
// its stylesheet and example. No webR render is awaited here; the guided
// specs own that.
test("Kaplan–Meier landing page opens the app on the example stage", async ({ page }) => {
  await page.goto("/kaplan-meier/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Kaplan–Meier survival curves");
  await expect(page.locator(".example svg")).toBeVisible();
  await expect(page.locator("link[rel=canonical]")).toHaveAttribute("href", "https://figurastats.org/kaplan-meier/");
  await page.getByRole("link", { name: "See the worked example" }).click();
  await expect(page).toHaveURL(/#km\/example$/);
  await expect(page.getByRole("button", { name: /kaplan-meier/i })).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("tab", { name: "Try an Example" })).toHaveAttribute("aria-selected", "true");
});

test("an unknown hash opens the app in its empty state", async ({ page }) => {
  await page.goto("/#nope/analyze");
  await expect(page.getByText("Select an analysis to begin.")).toBeVisible();
});
```

- [ ] **Step 2: Run it**

Run: `rm -rf web/R && cp -R R web/R && npx playwright test tests/e2e/pages.spec.js`
Expected: 2 passed. If the KM example stage has not rendered yet when the tab assertion runs, that is fine — the assertion is on the tab, not the render.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/pages.spec.js
git commit -m "e2e: landing page deep-links into the guided KM example stage"
```

---

### Task 11: Documentation for the next person

**Files:**
- Modify: `CLAUDE.md` ("Commands" and "Adding a figure or analysis")

- [ ] **Step 1: Commands**

Under "JS unit tests", add:

> - Landing pages: `npm run build:pages` regenerates `web/<slug>/index.html`, `sample.csv`, `web/about/index.html`, `web/sitemap.xml`, `web/robots.txt` from `scripts/pages/registry.mjs` and each analysis's exported `UNDERSTAND_SECTIONS`; `scripts/pages/build.test.mjs` fails CI if the committed pages differ from a fresh build. **`npm run build:examples` (needs R)** re-renders `web/<slug>/example.json` through `render_figure()`; run it whenever a demo generator, a `fig_*`, or the citation sentence changes, then `build:pages`, and commit both. The generator lives outside `web/` on purpose (validation digest).

- [ ] **Step 2: Adding a figure**

Append a sixth key:

> 6. `scripts/pages/registry.mjs` — one `PAGES` entry (slug, title, description, lede, the module's `UNDERSTAND_SECTIONS`, its demo data and demo spec builder), then `npm run build:examples && npm run build:pages`. `build.test.mjs` asserts the registry's keys equal the rail's `data-figure` set, so a missing entry fails CI. The analysis's `fig_*` must append `.with_citation(text, pkgs)` with the same `pkgs` it passes `.script_assemble`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: landing-page build, example renders, and the sixth key for a new analysis"
```

---

### Task 12: Validation pipeline, gate review, freshness

**Files:**
- Regenerated: `stats-validation/results/findings.json`, `stats-validation/results/scorecard.html`, `stats-validation/results/webr-tier.json`, `web/validation.html`
- Possibly modified after review: `stats-validation/expected-findings.json`

**Current baseline (verified 2026-09-09): all eight cases carry zero findings** in `expected-findings.json`. The "exits non-zero by design" note in older comments dates from when `logistic-dirty` published 30 findings; that was resolved on 2026-07-28. Today a non-zero `make all` means a finding appeared and must be investigated.

- [ ] **Step 1: Unit suites**

Run: `make -C stats-validation test`
Expected: green.

- [ ] **Step 2: Rebuild the evidence**

Run: `make -C stats-validation clean all; echo "exit $?"`
Expected: **`exit 0`** and zero findings on all eight cases. A non-zero exit means a case published a finding; open `stats-validation/results/findings.json`, read it, and treat it as Step 3 describes. Do not proceed on a red `all` by calling it "by design".

- [ ] **Step 3: The gate — read before touching the baseline**

Run: `make -C stats-validation gate`
Expected: **passes with no change**, because the only new text is the citation paragraph and Task 3 strips it before any parser runs.

If it fails: run `make -C stats-validation gate 2>&1 | tee /tmp/gate.txt` and read every added, removed or changed finding. For each one, name the case, the term, the quantity, and why this change could have produced it. Unless the explanation is "the comparator saw the citation paragraph" — which would mean Task 3 missed a site, fix Task 3 — the finding is a regression to investigate, not a baseline to accept. Only after every changed finding is explained in the commit message may `make -C stats-validation gate-update` be run, by hand.

- [ ] **Step 4: The webR release gate (browser + network, hand-run)**

This work changes what the browser displays (the citation paragraph is in every `text`) and three digested shell files, so the release gate must be re-measured, not left stale:

```bash
make -C stats-validation webr
```
Expected: all eight cases compared in one booted webR session, every cell and sentence identical to native R (the citation sentence is byte-identical on both sides by construction — no version, no date). It rewrites `stats-validation/results/webr-tier.json`. If any case reports a difference, stop and investigate; a citation-related difference would mean the two sides built the sentence differently, which Task 1's tests make impossible, so anything reported is a real display divergence.

- [ ] **Step 5: Rebuild the published evidence with the fresh webR tier, then freshness**

```bash
make -C stats-validation all
make -C stats-validation freshness
git diff --stat -- stats-validation/results/scorecard.html stats-validation/results/webr-tier.json web/validation.html
```
Expected: `all` exits 0; freshness passes; the pages show a diff (new web digest, the webR tier's new timestamp, the footer from Task 9) and the staleness box on `web/validation.html` is **gone**, because the webR evidence now matches the shipped sources.

- [ ] **Step 6: Whole-repo check**

```bash
Rscript -e 'devtools::test()'      # FAIL 0 | WARN 0
npm run test:unit                  # every suite OK
```

- [ ] **Step 7: Commit**

```bash
git add stats-validation/results/findings.json stats-validation/results/scorecard.html stats-validation/results/webr-tier.json web/validation.html
git commit -m "validation: re-run the webR release gate and regenerate evidence after the citation sentence and shell changes"
```

---

### Task 13: Post-deploy, by hand (not code)

- [ ] After the deploy workflow publishes `main`, open `https://figurastats.org/sitemap.xml` and `https://figurastats.org/about/` and confirm both are served.
- [ ] In Search Console (property already verified), submit `https://figurastats.org/sitemap.xml`.
- [ ] Open one landing page on a phone and tap both buttons.

---

## Self-review

**Spec coverage.** §2.1 URL set → Task 6 registry + Task 8. §2.2 skeleton (head, header, lede, buttons, prose, example, sample, limits, footer) → Task 8 templates; "limits" is a section of `UNDERSTAND_SECTIONS` where the module has one, so it renders with the rest. §2.3 About → Task 8 + Task 9 disclosures. §2.4 sitemap/robots → Task 8. §2.5 styling → Task 7. §3.1 generator outside `web/` → Task 8. §3.2 `UNDERSTAND_SECTIONS` → Task 4. §3.3 committed renders → Task 6. §4.1 hash → Task 5. §4.2 rail link → Task 5. §4.3 cache bump → Task 5. §4.4 pipeline and gate review → Task 12. §5.1–5.2 citation → Tasks 1–2. §5.3 comparator and specs → Task 3. §6 testing → each task; e2e → Task 10. §7 sitemap submission → Task 13. Two recorded deviations (explore's text is code; no `<lastmod>`) are in Global Constraints.

**Placeholders.** None: every code step carries the code, and Task 2's test helpers are the names the test files actually define.

**Type consistency.** `analysisFromHash(hash, known)` (Task 5 test and app). `buildAll({ webDir })` returns a `Map` keyed by `web/`-relative path (Task 8 builder and test). `PAGES[i]` fields `slug, key, title, description, lede, sections, demo, demoSpec, teachingVisual?, textKind?` (Task 6 registry; Task 8 templates and test read exactly those). `.with_citation(text, pkgs)` and `.citation_sentence(pkgs)` (Tasks 1–3). `strip_citation` / `methods_text` (Task 3).

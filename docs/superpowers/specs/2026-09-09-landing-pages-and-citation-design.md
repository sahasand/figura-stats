# Landing pages, sitemap and citation line — design

**Date:** 2026-09-09
**Status:** approved 2026-09-09 (owner review applied); implementation plan at `docs/superpowers/plans/2026-09-09-landing-pages-and-citation.md`
**Scope:** seven crawlable HTML pages generated from the app's own modules, a sitemap, a deep link from each page into the app, and one attribution sentence appended to every analysis's methods text and exported script.

## 1. Why

Seven weeks after launch, Cloudflare records roughly 45 to 55 page views a day from browser user agents after crawlers and headless clients are filtered out. That is a user-agent heuristic, not a confirmed human count, but the level has held since launch week and the referrer data (two thirds of real-browser loads carry no referrer; the named ones are Instagram, Facebook and ChatGPT, none of which the owner posted to) says the link is being passed along person to person.

Google already indexes the site and Search Console is verified. What the index holds is thin: the app is one page whose content is rendered by JavaScript after webR boots, so a crawler or an AI assistant sees a title, a meta description and a rail of buttons, with no per-analysis text to match a query like "free Table 1 generator" or to summarise when recommending a tool.

Two changes address this together.

1. **Crawlable pages, one per analysis plus About.** Each explains in plain HTML what the analysis makes, for whom, what data it needs, what it cannot do, shows a real rendered example, offers a sample CSV, and opens the matching analysis in the app. This gives the index and assistants substantive text per analysis.
2. **A citation sentence in the methods text.** Every user is writing a paper, and journals require a software statement. If the generated methods paragraph ends with a scholarly attribution, authors paste it as-is and each published paper links the next reader to the tool. This was planned for late July (see the traction-strategy notes) and never built.

What the traffic data cannot say: which analyses people run. The app imports every guided module statically, so a fetch of any `guided/*.js` file is a page load, not a choice. The only per-analysis signal is a fetch of an analysis's `analyze-form.js` reaching the "Analyze your data" stage, and even that is lost to the service worker cache on repeat visits.

The statistical code does not change. The R text output gains one deterministic paragraph.

## 2. Pages and URLs

### 2.1 URL set

| Slug | Analysis key | Source modules |
|---|---|---|
| `/table-1/` | `summary` | `web/guided/summary/` |
| `/kaplan-meier/` | `km` | `web/guided/km/` |
| `/group-comparison/` | `groupcompare` | `web/guided/groupcompare/` |
| `/cox-regression/` | `cox` | `web/guided/cox/` |
| `/logistic-regression/` | `logistic` | `web/guided/logistic/` |
| `/explore-plot/` | `explore` | `web/guided/explore/` |
| `/about/` | none | generator template only |

Each slug is a folder under `web/` holding a generated `index.html`, so GitHub Pages serves the clean URL. The mapping from slug to analysis key is one table in the generator and is the single place a page is registered. A test asserts the set of analysis keys in that table equals the set of `data-figure` buttons in `web/index.html`, so a new analysis without a page fails CI rather than silently missing one.

### 2.2 Analysis page skeleton

Every analysis page has the same sections in this order.

1. **Head.** `<title>` of the form "Kaplan–Meier survival curves — Figura", a `<meta name="description">` of one sentence, a `<link rel="canonical">` to the absolute URL, the same Open Graph tags as `index.html` with the page's own title and description, and the viewport meta.
2. **Header.** Wordmark linking to `/`, and a one-line nav: About · Validation · the other five analyses.
3. **Lede.** One paragraph in plain English answering "what does this make and for whom" (e.g. "A journal-ready baseline characteristics table from a CSV, with mean ± SD or median (IQR) chosen per variable by a normality check."). This is new copy, written once per page in the generator's registry, kept to two or three sentences.
4. **Buttons.** "See the worked example" → `/#<key>/example` and "Analyze your data" → `/#<key>/analyze`. Both are ordinary links; the app's hash routing does the rest (section 4.1).
5. **Understand prose.** The analysis's Understand-stage HTML, verbatim, from the content module (section 3.2). Sub-headings become `<h2>`.
6. **Example output.** The demo figure as an inline `<svg>` with a `<title>` and a caption, followed by the demo's methods text (the `text` field) in a `<blockquote>`, labelled as the sentence the tool produced for the example dataset. For the table analyses (Table 1, Cox, logistic) the `svg` field holds an HTML table plus sibling SVGs; the page embeds that fragment as-is inside the same `.summary-output` wrapper the app uses, so the galley-proof styling applies.
7. **Sample data.** A link to `sample.csv` in the same folder, with the row count and the column list, and one sentence on where the data came from (a frozen synthetic dataset, generated by the script in `data-raw/`).
8. **Limits.** The content module's "when to seek statistical review" section, where one exists, under its own `<h2>`. Analyses whose content has no such section (Explore) omit it.
9. **Footer.** The citation block (section 5.3), a link to `/about/`, a link to `/validation.html`, and the feedback address as plain text.

### 2.3 About page

Sections: what Figura is (three sentences); **"Can I use this with patient data?"**, which makes two separate claims and keeps them separate: first, that the data stays in the browser tab (there is no backend, no upload, and no request that carries any part of the CSV or a result), and second, an honest list of what the page does talk to: the webR runtime and packages from the webR CDN, the app's own files from this domain, and Cloudflare's Web Analytics beacon, which Cloudflare injects at the edge and which reports page loads, referrer, country, device type and browser to Cloudflare and carries no uploaded research data or analysis results. The text must not say "the only network calls are the runtime and the app files"; that is false while Cloudflare Web Analytics is enabled. It should say the data claim is verifiable in the browser's network panel and name the beacon path so a reader can check it. The same claim already appears, and is already false, in four places that this work corrects: the validation page's footer, whose source is the template string in `stats-validation/build_scorecard.py` (it reads "no analytics, no external resource of any kind"); the "No data egress" paragraph in `CLAUDE.md` ("There is no analytics"); `README.md`'s "Your data never leaves your browser" paragraph ("There is no analytics"); and the comment in `web/styles.css` that says the site makes no network calls beyond webR. The `index.html` meta and Open Graph descriptions say only that data never leaves the tab, which remains true and needs no change. Then **how the numbers are checked** (two sentences and a link to the validation page), **how to cite** (section 5.3, plain text and BibTeX in copyable blocks), **feedback** (the address as plain text), and a list of the six analysis pages.

### 2.4 Sitemap and robots

`web/sitemap.xml` lists nine absolute URLs: `/`, `/validation.html`, and the seven pages, with no `<lastmod>`: any date derived from git changes on the very commit that records it and would fail the freshness test forever, and search engines largely ignore the field. `web/robots.txt` allows everything and names the sitemap. Both are generated. Both live under `web/`, never the repo root, for the same reason as `CNAME`: the deploy uploads `web/` as the artifact.

### 2.5 Styling

Each page links `../styles.css` (relative URLs inside it resolve against the stylesheet, so the self-hosted font paths keep working) and a new `web/pages.css` holding only what a workbench stylesheet cannot provide: a scrolling document layout, a content column, and the dark-scheme remap. `validation.html` already carries an inline block of exactly this kind; it stays as it is, because it is generated by a different builder and touching that builder is out of scope. Every colour in `pages.css` is a token from `styles.css`, never a literal. Fonts stay self-hosted; no CDN link of any kind.

## 3. Generator

### 3.1 Location and invocation

`scripts/pages/build.mjs`, run from the repo root with `npm run build:pages`. It lives outside `web/` deliberately: the validation digest covers every `.js` under `web/`, and a generator inside `web/` would be shipped and digested for no reason.

Inputs, all read from the repo:

- the slug registry (in the generator), giving slug, analysis key, title, description, lede, and the demo spec builder to call;
- each analysis's Understand HTML (section 3.2);
- each analysis's demo data module, for the sample CSV via `toCsv` from `web/lib/csv.js`;
- the committed demo render (section 3.3);
- `web/index.html`, to read the `data-figure` set for the parity test and the Open Graph tags to mirror.

Outputs, all tracked in git: `web/<slug>/index.html`, `web/<slug>/sample.csv`, `web/sitemap.xml`, `web/robots.txt`. `web/pages.css` is hand-written, not generated.

The generator is deterministic: same inputs, byte-identical output. Nothing in it reads the clock or git.

### 3.2 Exposing the Understand prose

The six content modules are not uniform. Four (`km`, `summary`, `cox`, `logistic`) keep their prose in a module-private `SECTIONS` array of `{title, html}`; two (`groupcompare`, `explore`) assign a template string to `panel.innerHTML` inside `renderUnderstand`. The KM module also injects a teaching SVG.

The refactor: every content module exports `UNDERSTAND_SECTIONS`, an array of `{title, html}`, and its `renderUnderstand(panel)` renders from that array. For the two inline modules this means splitting the existing template at its `<h3>` boundaries into the array; the rendered DOM is unchanged and the existing tests for those modules still pass. The KM teaching visual stays a render-time addition in `renderUnderstand` and is also placed on the landing page by the generator, using the same exported `TEACHING_VISUAL_SVG` and alt text.

This is the whole reason the pages are generated rather than written: the landing page and the in-app teaching text come from one array and cannot drift.

### 3.3 Demo renders

Each analysis's example output is rendered once by native R and committed as `web/<slug>/example.json`, holding the `svg` and `text` fields exactly as `render_figure()` returned them for the demo spec. A small R script, `scripts/pages/render-examples.R`, builds each demo spec through the same spec builders the app uses (via Node, mirroring how the validation harness's Path A does it) and calls `render_figure`. The generator reads the JSON and never needs R at run time.

Committing the render keeps R out of the page build and keeps the pages reviewable locally. The committed JSON is regenerated only when a demo generator or an R figure function changes; the freshness test in section 6 does not cover it, because rendering needs the full R toolchain, so the rule is documented in `CLAUDE.md` alongside the existing "regenerate the OG card" rule.

Neither `.json`, `.svg`, `.csv`, `.xml`, `.txt` nor the new `index.html` files under slug folders enter the validation digest, which matches only `.js`, the root `index.html` and `styles.css`. `pages.css` is likewise outside it.

## 4. App changes

### 4.1 Hash on load

The guided shell already writes `#<key>/<stage>` into the URL and reads the stage back on render, but `web/app.js` never reads the hash to choose the analysis. Add: on `DOMContentLoaded`, parse `location.hash` with a pure function `analysisFromHash(hash)` in `web/lib/route.js` that returns the analysis key when the hash matches `^#(\w+)(?:/\w+)?$` and that key is a registered form, else `null`. When it returns a key, `app.js` dispatches a click on the rail button with that `data-figure`. The shell then reads the stage from the same hash as it does today. No `hashchange` listener; the rail is still the in-app navigation.

An unknown prefix is ignored and the app opens as it does now. The hash carries analysis and stage only, never inputs or filenames, which the shell already enforces.

### 4.2 Rail foot

`web/index.html` gains an "About" link beside the existing "Validation" link in the rail foot. Nothing else in the app shell changes. The rail's analysis buttons stay buttons.

### 4.3 Service worker

`CACHE` is bumped because the shell changed. The seven pages, the sample CSVs and the sitemap are **not** added to `PRECACHE`: they are entry points, not the app shell, and same-origin requests already take the stale-while-revalidate route. A page cached from before a regeneration is served once and refreshed behind it, which is the accepted behaviour for every non-R file.

### 4.4 Validation digest consequence

`app.js`, `index.html` and `sw.js` are digested, and the citation sentence changes every analysis's displayed `text`, so this work must re-run the hand-run webR release gate (`make -C stats-validation webr`, browser + network) and then `make -C stats-validation all`, and commit the regenerated `webr-tier.json`, scorecard and `web/validation.html`. All eight cases currently carry zero findings, so `make all` is expected to exit 0; a non-zero exit is a finding to investigate, not a by-design status. If `make -C stats-validation gate` then reports a changed findings set, every changed finding is read and explained before the baseline moves: the only change this work should cause is the comparator learning to skip the citation paragraph, and any other added, removed or altered finding is a defect to investigate, not a baseline to accept. `gate-update` is run by hand, after that review, never as a routine step. With the webR gate re-run in the same work, the staleness box on the validation page clears.

## 5. Citation

### 5.1 The sentence

One helper in `R/script.R`:

```r
.citation_sentence <- function(pkgs = character(0))
```

returns a single sentence of the form

> Analyses were performed with Figura (Saha, 2026; https://figurastats.org), which runs R with the survival and ggplot2 packages in the browser.

with the package clause built from `pkgs`: none → "which runs R in the browser"; one → "with the survival package"; several → an Oxford-comma list. The URL, the author and the year live in one constant block at the top of `R/script.R` so a DOI can replace the URL later in one place.

The sentence deliberately contains **no R version and no access date.** The webR release gate compares the displayed sentences between native R and webR, and an R version would differ between them; a date would change daily and defeat every freshness check. The exported script header already prints `R.version.string`, which is where the version belongs.

### 5.2 Where it goes

- **Methods text.** Every `fig_<name>` with a methods text appends the sentence as a final paragraph, separated from the existing text by a blank line, using the same `pkgs` vector it passes to `.script_assemble`. Analyses that emit a TSV table followed by a methods paragraph (Table 1, Cox, logistic) append it after that paragraph. **Explore is the exception:** its `text` field *is* the ggplot2 script the user downloads, so a prose sentence would corrupt it; Explore carries the sentence as a `# Cite:` comment line in that script instead, and the landing page labels its example output as code, never as methods text.
- **Exported script.** `.script_header` gains a `# Cite:` line carrying the same sentence.
- **About page and every landing-page footer.** The same wording, plus a BibTeX `@misc` entry with `author`, `title`, `year`, `url` and `note = {Accessed <date>}` left for the author to fill.

### 5.3 Validation interaction

The independent Python implementation (Path B) compares values it extracts from the methods text, and "2026" is a number. The rule of the validation suite is that Path B implementers read only `stats-validation/spec/`, never `R/`. So the change is made at the spec level: each affected spec gains a clause that the methods text ends with a citation paragraph that carries no statistical content and is excluded from comparison, and the comparator drops the final paragraph when it matches the documented pattern. The expected result is that the findings set does not change at all; if the gate reports otherwise, section 4.4 applies. The webR gate needs no change: the sentence is identical on both sides.

## 6. Testing

**Node unit tests**, each appended to the `test:unit` chain in `package.json` in the same commit that creates it:

- `scripts/pages/build.test.mjs`: building into a temp dir produces files byte-identical to the committed `web/<slug>/` files, `sitemap.xml` and `robots.txt` (the freshness test); the registry's analysis keys equal the `data-figure` set in `web/index.html`; every page has exactly one `<h1>`, a `<title>`, a description, a canonical link equal to its sitemap entry, both buttons with the correct hash, the citation sentence, and no `<link>` or `<script>` pointing off-origin; the sitemap lists exactly nine URLs; each `sample.csv` parsed by `parseCsv` yields the demo table's columns and row count.
- `web/lib/route.test.mjs`: `analysisFromHash` on `""`, `"#km"`, `"#km/analyze"`, `"#nope/analyze"`, `"#km/analyze/extra"`.
- Existing content-module tests keep passing after the `UNDERSTAND_SECTIONS` refactor; one new assertion per module that `renderUnderstand` output contains every section title.

**R tests** (`devtools::test()`, WARN 0 is the gate): every `fig_<name>` text ends with the citation paragraph; `.citation_sentence` formats zero, one and three packages correctly; every generated script's header contains the `# Cite:` line.

**Playwright e2e** (not in CI): loading `/kaplan-meier/`, clicking "See the worked example" lands on the Kaplan–Meier example stage with the demo rendered.

**Validation**: `make -C stats-validation test`, then `all`, `gate`, `freshness`, each green or at its documented non-zero-by-design status. A changed findings set is reviewed finding by finding before any baseline update (section 4.4).

The generated pages' "no off-origin `<link>` or `<script>`" test holds despite the analytics beacon: Cloudflare injects it at the edge, so it is absent from the source the test reads. The About page's disclosure is what tells the reader it exists.

## 7. Out of scope

- Sitemap submission in Search Console: a manual step after the first deploy. The property is already verified.
- A Zenodo DOI: deferred by decision; the URL constant is the swap point.
- Precaching the pages, a `hashchange` listener, or moving the rail to links.
- Changing `validation.html`'s builder to share `pages.css`.
- An export counter or any other instrumentation.

## 8. Decisions recorded

- Pages are generated and committed, not hand-written and not built in CI (approach 1 of three considered). Rationale: one source of truth with the in-app prose, and the repo's standing rule that generated pages are tracked and never hand-edited.
- Six analysis pages plus About, not the three first proposed. The traffic data cannot rank the analyses by use (section 1), so no analysis is left out on that basis; the regression pages also have the clearest search intent.
- Citation identifies the tool by URL now, DOI later.
- The demo render is committed JSON rendered by native R, so the page build needs Node only.

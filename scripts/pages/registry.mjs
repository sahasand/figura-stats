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

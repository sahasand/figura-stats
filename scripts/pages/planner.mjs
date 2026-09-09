import { METHODS, PRESETS } from "../../web/sample-size/catalog.js";
import { escapeHtml } from "./html.mjs";

export function renderPlannerPage() {
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample size &amp; power planner — Figura</title>
<meta name="description" content="Plan sample size, statistical power and precision across 15 study designs. Compare scenarios, inspect assumptions and export reproducible R. Free, in your browser.">
<link rel="canonical" href="https://figurastats.org/sample-size/">
<meta property="og:title" content="Sample size &amp; power planner — Figura">
<meta property="og:description" content="How much evidence will your study need? Explore sample size, power and precision with real R in your browser.">
<meta property="og:type" content="website"><meta property="og:url" content="https://figurastats.org/sample-size/">
<meta property="og:image" content="https://figurastats.org/preview.png"><meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="../styles.css"><link rel="stylesheet" href="planner.css">
</head><body>
<a href="#planning" class="skip-link">Skip to planning controls</a>
<header class="planner-header"><a href="../" class="planner-brand">Figura <span>Study planning</span></a>
<nav aria-label="Site"><a href="../">Analysis workbench</a><a href="../about/">About</a><a href="#methodology">Methods &amp; limits</a></nav>
<span id="engine-status" role="status">Starting the local R engine…</span></header>
<main class="planner-main">
<section class="planner-intro"><p class="planner-kicker">Sample size · power · precision</p>
<h1>How much evidence<br>will your study need?</h1>
<p>Make the assumptions explicit. Explore the trade-offs. Build a study you can explain.</p>
<div class="preset-row" aria-label="Example study plans">${PRESETS.map((p,i)=>`<button type="button" data-preset="${i}"><strong>${escapeHtml(p.title)}</strong><span>${escapeHtml(p.subtitle)}</span></button>`).join("")}</div>
</section>
<div class="planning-layout">
<aside class="design-library"><p class="planner-kicker">01 / Choose your design</p>
<label for="design-search" class="sr-only">Find a study design</label><input id="design-search" type="search" placeholder="Find a study design…" autocomplete="off">
<nav id="design-list" aria-label="Study designs">${[...new Set(METHODS.map(m=>m.category))].map(category=>`<div class="design-category"><h2>${escapeHtml(category)}</h2>${METHODS.filter(m=>m.category===category).map(m=>`<button type="button" data-method="${m.id}"${m.id==="two_mean"?' aria-current="true"':""}><span>${escapeHtml(m.title)}</span><small>${escapeHtml(m.tag)}</small></button>`).join("")}</div>`).join("")}</nav>
<p class="library-note">15 explicit models. Each has its own assumptions and limits.</p>
</aside>
<section class="assumptions-panel" id="planning" aria-labelledby="design-title"><p class="planner-kicker">02 / Set your assumptions</p>
<h2 id="design-title">Two independent means</h2><p id="design-description"></p>
<div id="solve-controls" class="solve-controls" role="group" aria-label="Quantity to calculate"></div>
<form id="planning-form" novalidate><div id="design-fields" class="field-grid"></div>
<fieldset class="planning-settings"><legend id="settings-legend">Statistical settings</legend><div id="settings-fields" class="field-grid"></div></fieldset>
<button class="calculate-button" type="submit">Calculate plan <span aria-hidden="true">↗</span></button>
<p class="quiet">Changes recalculate automatically after a short pause.</p></form>
<details class="helper"><summary>Effect-size helpers</summary>
<p>These transformations help express assumptions; they do not choose a scientifically meaningful effect for you.</p>
<div class="helper-grid"><label>Anticipated R²<input id="helper-r2" type="number" min="0" max="0.99" step="any" value="0.13"></label><p id="helper-r2-result"></p></div>
<div class="helper-grid"><label>SD at each occasion<input id="helper-sd" type="number" min="0.00001" step="any" value="10"></label><label>Within-pair correlation<input id="helper-r" type="number" min="-0.99" max="0.99" step="any" value="0.5"></label><p id="helper-pair-result"></p></div>
<p class="quiet">The paired helper assumes equal SD at both occasions: SD(diff) = SD × √(2(1 − correlation)).</p>
</details></section>
<section class="results-panel" aria-labelledby="result-title"><p class="planner-kicker">03 / Explore your design</p>
<div id="result-status" role="status" class="result-status">Preparing your first calculation…</div>
<div id="result-content" aria-busy="true"><h2 id="result-title">Your planning result</h2><p>Your result and sensitivity curve appear here once the local engine is ready.</p></div>
<div class="scenario-save"><label for="scenario-name">Scenario name</label><div><input id="scenario-name" maxlength="100" placeholder="e.g. Primary assumptions"><button id="save-scenario" type="button" disabled>Keep scenario</button></div></div>
<div class="export-actions" aria-label="Export current calculation"><button id="export-r" type="button" disabled>R script</button><button id="export-report" type="button" disabled>Print / PDF</button></div>
</section></div>
<section class="comparison-panel" aria-labelledby="comparison-title"><div class="comparison-heading"><div><p class="planner-kicker">04 / Keep the alternatives visible</p><h2 id="comparison-title">Compare scenarios</h2></div><div class="export-actions"><button id="download-plan" type="button" disabled>Save plan</button><button id="download-csv" type="button" disabled>Export CSV</button><button id="open-plan" type="button">Open plan</button><input id="plan-file" type="file" accept=".json,application/json" hidden></div></div>
<p>Keep up to eight scenarios. Download a plan to reopen its assumptions later; imported scenarios are recalculated in your current R environment.</p>
<div id="comparison"><p class="empty-scenarios">Start with one plausible design, then keep alternatives for the assumptions you are least certain about.</p></div><p id="plan-status" role="status"></p>
</section>
<section class="methodology" id="methodology"><div><p class="planner-kicker">An inspectable calculation</p><h2>Know what your number means.</h2><p>Power is conditional on the design and anticipated effect. A precise calculation cannot resolve an uncertain assumption. These tools plan a future study; they do not turn an observed effect into retrospective evidence.</p></div>
<div><h3>Methods and numerical checks</h3><p>Calculations run in R with <a href="https://cran.r-project.org/web/packages/pwr/pwr.pdf">pwr</a> and stats. The method shown with each result identifies its approximation. The downloadable script contains the actual engine used for that result.</p><p>The test suite checks standard t-test references, solver round trips, integer-size minimality, unequal allocation, attrition, margin boundaries and precision formulae. This is numerical checking of the supported models, not certification of a study design.</p>
<h3>Scope matters</h3><p>General repeated-measures interactions, mixed models, adaptive trials, Bayesian assurance and prediction-model development need their own planning models. They are not covered by selecting a superficially similar method here.</p></div></section>
</main><footer class="planner-footer"><span>Figura · Real R, in your browser.</span><p>No research dataset is needed. Plans stay in this tab until you download them. <a href="../about/">Network and analytics disclosure</a>.</p><a href="../">Continue to the analysis workbench →</a></footer>
<script type="module" src="planner.js"></script></body></html>`;
}

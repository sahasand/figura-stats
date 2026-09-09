import { METHODS, PRESETS } from "../../web/sample-size/catalog.js";
import { escapeHtml } from "./html.mjs";

// Derive the shared chrome from the workbench so its navigation stays in sync.
export function renderPlannerPage(workbenchHtml) {
  const header = workbenchHtml.match(/<header class="toolbar">[\s\S]*?<\/header>/)?.[0]
    .replace('id="rstatus" class="chip idle"', 'id="engine-status" class="chip busy"')
    .replace('R: idle', 'R: starting…');
  const rail = workbenchHtml.match(/<aside class="pane nav-pane"[\s\S]*?<\/aside>/)?.[0]
    .replace(/<button data-figure="(\w+)">([\s\S]*?)<\/button>/g,
      '<a class="planning-link" href="#$1">$2</a>')
    .replace(/href="([^"]+)"/g, 'href="../$1"')
    .replace('class="planning-link" href="../sample-size/"',
      'class="planning-link active" aria-current="page" href="../sample-size/"');
  if (!header || !rail) throw new Error('The planner requires the shared workbench header and navigation.');
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample size &amp; power planner — Figura</title>
<meta name="description" content="Plan sample size, statistical power and precision across 15 study designs. Compare scenarios, inspect assumptions and export reproducible R. Free, in your browser.">
<link rel="canonical" href="https://figurastats.org/sample-size/">
<meta property="og:title" content="Sample size &amp; power planner — Figura">
<meta property="og:description" content="How much evidence will your study need? Explore sample size, power and precision with real R in your browser.">
<meta property="og:type" content="website"><meta property="og:url" content="https://figurastats.org/sample-size/">
<meta property="og:image" content="https://figurastats.org/preview.png"><meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="../styles.css"><link rel="stylesheet" href="planner.css?v=workbench-1">
</head><body>
<a href="#planning" class="skip-link">Skip to planning controls</a>
${header}
<main class="workbench planner-workbench">
${rail}
<section class="pane config-pane" id="planning" aria-label="Configuration">
<div class="pane-title">Configuration</div>
<div id="form">
<h2>Sample size &amp; power</h2><p>Plan a study and compare its assumptions.</p>
<label for="design-select">Study design</label>
<select id="design-select">${[...new Set(METHODS.map(m=>m.category))].map(category=>`<optgroup label="${escapeHtml(category)}">${METHODS.filter(m=>m.category===category).map(m=>`<option value="${m.id}">${escapeHtml(m.title)}</option>`).join("")}</optgroup>`).join("")}</select>
<details class="example-plans"><summary>Start from an example</summary><div class="preset-row" aria-label="Example study plans">${PRESETS.map((p,i)=>`<button type="button" data-preset="${i}">${escapeHtml(p.title)}</button>`).join("")}</div></details>
<h3 id="design-title">Two independent means</h3><p id="design-description"></p>
<div id="solve-controls" class="solve-controls" role="group" aria-label="Quantity to calculate"></div>
<form id="planning-form" novalidate><div id="design-fields" class="field-grid"></div>
<fieldset class="planning-settings"><legend id="settings-legend">Statistical settings</legend><div id="settings-fields" class="field-grid"></div></fieldset>
<button id="render" class="calculate-button" type="submit">Calculate plan</button>
<p class="quiet">Changes recalculate automatically after a short pause.</p></form>
<details class="helper"><summary>Effect-size helpers</summary>
<p>These transformations help express assumptions; they do not choose a scientifically meaningful effect for you.</p>
<div class="helper-grid"><label>Anticipated R²<input id="helper-r2" type="number" min="0" max="0.99" step="any" value="0.13"></label><p id="helper-r2-result"></p></div>
<div class="helper-grid"><label>SD at each occasion<input id="helper-sd" type="number" min="0.00001" step="any" value="10"></label><label>Within-pair correlation<input id="helper-r" type="number" min="-0.99" max="0.99" step="any" value="0.5"></label><p id="helper-pair-result"></p></div>
<p class="quiet">The paired helper assumes equal SD at both occasions: SD(diff) = SD × √(2(1 − correlation)).</p>
</details>
<details class="methodology" id="methodology"><summary>Methods, scope &amp; privacy</summary><p>Calculations run locally in R using pwr and stats. Each result records the method, approximation and assumptions. No dataset is required; plans stay in this tab until you download them.</p><p>General repeated-measures interactions, mixed models, adaptive trials and Bayesian assurance require different planning models and are outside this catalogue.</p><p>Numerical checks cover reference calculations, integer rounding, allocation, attrition and solver round trips. They do not establish that a study’s assumptions are appropriate.</p><p><a href="../validation.html">Validation coverage</a> · <a href="../about/">Network and analytics disclosure</a></p></details>
</div></section>
<section class="pane planner-output" aria-label="Output">
<div class="pane-head"><div class="pane-title">Planning result</div><div class="export-toolbar" role="group" aria-label="Export current calculation"><button id="export-r" type="button" disabled>R script</button><button id="export-report" type="button" disabled>Print / PDF</button></div></div>
<div class="planner-output-scroll"><div class="results-panel">
<div id="result-status" role="status" class="result-status">Preparing your first calculation…</div>
<div id="result-content" aria-busy="true"><h2 id="result-title">Your planning result</h2><p>Your result and sensitivity curve appear here once the local engine is ready.</p></div>
<div class="scenario-save"><label for="scenario-name">Scenario name</label><div><input id="scenario-name" maxlength="100" placeholder="e.g. Primary assumptions"><button id="save-scenario" type="button" disabled>Keep scenario</button></div></div>
</div>
<section class="comparison-panel" aria-labelledby="comparison-title"><div class="pane-head"><h2 class="pane-title" id="comparison-title">Scenarios</h2><div class="export-toolbar" role="group" aria-label="Scenario files"><button id="download-plan" type="button" disabled>Save plan</button><button id="download-csv" type="button" disabled>Export CSV</button><button id="open-plan" type="button">Open plan</button><input id="plan-file" type="file" accept=".json,application/json" hidden></div></div>
<div class="comparison-body"><p class="quiet">Keep up to eight scenarios. Save a plan to reopen its assumptions later.</p>
<div id="comparison"><p class="empty-scenarios">Keep a scenario to compare alternative assumptions.</p></div><p id="plan-status" role="status"></p></div>
</section>
</div></section></main>
<script type="module" src="planner.js?v=workbench-1"></script></body></html>`;
}

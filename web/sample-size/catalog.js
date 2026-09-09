// Display metadata only. R owns every statistical calculation.
export const FIELD = {
  delta: { label: "Anticipated difference", value: .5, step: "any", help: "In the outcome's original units. Choose a scientifically meaningful difference." },
  sd: { label: "Population standard deviation", value: 1, min: .000001, step: "any", help: "Use prior evidence for variability, not the standard error of a mean." },
  ratio: { label: "Allocation ratio · group 2 / group 1", value: 1, min: .1, max: 10, step: "any", help: "1 means equal allocation. Group 2 is rounded up at each candidate size." },
  margin: { label: "Margin in outcome units", value: .3, min: .000001, step: "any", help: "A prespecified, scientifically justified bound—not a value selected to reduce sample size." },
  groups: { label: "Number of independent groups", value: 3, min: 2, max: 100, step: 1 },
  f: { label: "Cohen’s f", value: .25, min: 0, max: 10, step: "any", help: "SD of population group means divided by the common within-group SD, with equal group weights." },
  r: { label: "Anticipated Pearson correlation", value: .3, min: -.999, max: .999, step: "any", help: "Correlation under the alternative; the null is zero." },
  predictors: { label: "Number of slope parameters tested", value: 3, min: 1, max: 100, step: 1, help: "All slopes are tested together. Count dummy variables separately; exclude the intercept." },
  f2: { label: "Cohen’s f²", value: .15, min: 0, max: 100, step: "any", help: "For the omnibus model, f² = anticipated R² / (1 − anticipated R²)." },
  df: { label: "Test degrees of freedom", value: 2, min: 1, max: 1000, step: 1, help: "For association: (rows − 1) × (columns − 1). For goodness of fit, account for estimated parameters." },
  w: { label: "Cohen’s w", value: .3, min: 0, max: 10, step: "any", help: "w = sqrt(sum((alternative probability − null probability)² / null probability))." },
  p1: { label: "Group 1 proportion", value: .5, min: .0001, max: .9999, step: "any", help: "Enter a proportion: 0.20 means 20%." },
  p2: { label: "Group 2 proportion", value: .65, min: .0001, max: .9999, step: "any", help: "For detectable-effect planning, its position above/below group 1 sets the search direction." },
  hr: { label: "Anticipated hazard ratio · group 2 / group 1", value: .7, min: .01, max: 100, step: "any", help: "Assumes proportional hazards. 1 means no difference." },
  event_fraction: { label: "Expected observed-event fraction", value: .6, min: .001, max: 1, step: "any", help: "Among analyzable participants by the analysis date. Account for follow-up and censoring here." },
  cluster_size: { label: "Participants per retained cluster", value: 20, min: 2, max: 100000, step: 1, help: "Fixed, equal cluster sizes; this calculation does not allow varying sizes." },
  icc: { label: "Intracluster correlation · ICC", value: .05, min: 0, max: .99, step: "any", help: "Correlation of outcomes within the same cluster." },
  width: { label: "Target confidence-interval half-width", value: .05, min: .000001, step: "any", help: "Half of the total interval width. For a proportion, 0.05 means five percentage points." },
};

export const METHODS = [
  { id:"two_mean", category:"Compare means", title:"Two independent means", tag:"Two-sample t-test", fields:["delta","sd","ratio"], unit:"Participants in group 1", effect:"delta", sided:true, description:"Plan the difference between two independent groups in the outcome’s original units.", formula:"d = difference / SD; power from the noncentral t distribution." },
  { id:"paired_mean", category:"Compare means", title:"Paired measurements", tag:"Paired t-test", fields:["delta","sd"], unit:"Complete pairs", effect:"delta", sided:true, overrides:{sd:{label:"SD of within-pair differences",help:"Use the variability of differences—not the SD at either occasion. See the effect-size helpers."}}, description:"Plan a before–after or matched-pair comparison with exactly two measurements per pair.", formula:"dz = mean paired difference / SD of paired differences." },
  { id:"one_mean", category:"Compare means", title:"One mean against a reference", tag:"One-sample t-test", fields:["delta","sd"], unit:"Participants", effect:"delta", sided:true, description:"Compare a population mean with a prespecified reference value.", formula:"d = (anticipated mean − reference mean) / SD." },
  { id:"anova", category:"Compare means", title:"One-way ANOVA", tag:"Balanced independent groups", fields:["groups","f"], unit:"Participants per group", effect:"f", description:"Power an omnibus difference among independent groups with equal sample sizes.", formula:"Noncentral F: df₁ = groups − 1; df₂ = groups × (n − 1)." },
  { id:"correlation", category:"Associations", title:"Pearson correlation", tag:"Correlation against zero", fields:["r"], unit:"Complete observation pairs", effect:"r", sided:true, description:"Plan a test of association between two continuous measurements.", formula:"Fisher-z approximation with the small-sample adjustment used by pwr." },
  { id:"regression", category:"Associations", title:"Multiple linear regression", tag:"Omnibus model F-test", fields:["predictors","f2"], unit:"Participants", effect:"f2", description:"Plan a joint test of all slope parameters in a linear regression model.", formula:"f² = R² / (1 − R²); residual df = N − slopes − 1." },
  { id:"chi_square", category:"Associations", title:"Chi-square test", tag:"Association / goodness of fit", fields:["df","w"], unit:"Observations", effect:"w", description:"Plan a categorical association or goodness-of-fit test using anticipated cell probabilities.", formula:"Noncentral χ²: noncentrality = N × w²." },
  { id:"two_proportion", category:"Proportions", title:"Two independent proportions", tag:"Arcsine normal approximation", fields:["p1","p2","ratio"], unit:"Participants in group 1", effect:"p2", sided:true, description:"Compare an anticipated binary-outcome rate between two independent groups.", formula:"h = 2 asin(√p₂) − 2 asin(√p₁); normal-approximation power." },
  { id:"one_proportion", category:"Proportions", title:"One proportion against a reference", tag:"Arcsine normal approximation", fields:["p1","p2"], unit:"Participants", effect:"p2", sided:true, overrides:{p1:{label:"Reference proportion"},p2:{label:"Anticipated alternative proportion"}}, description:"Plan a binary-outcome comparison with a prespecified reference proportion.", formula:"h = 2 asin(√p_alternative) − 2 asin(√p_reference)." },
  { id:"ni_mean", category:"Clinical designs", title:"Noninferiority · means", tag:"One-sided normal approximation", fields:["delta","sd","margin","ratio"], defaults:{delta:0,alpha:.025}, unit:"Participants in group 1", overrides:{delta:{label:"Anticipated difference · new − control",help:"Higher is better. The noninferiority boundary is −margin."}}, description:"Plan to rule out a clinically unacceptable reduction in a continuous outcome.", formula:"Power = Φ((difference + margin) / SE − z₁₋α)." },
  { id:"equivalence_mean", category:"Clinical designs", title:"Equivalence · means", tag:"Two one-sided z tests", fields:["delta","sd","margin","ratio"], defaults:{delta:0}, unit:"Participants in group 1", description:"Plan to demonstrate that a continuous-outcome difference lies within symmetric bounds.", formula:"Joint TOST rejection probability; equivalence bounds = ±margin." },
  { id:"survival", category:"Clinical designs", title:"Survival · two groups", tag:"Schoenfeld approximation", fields:["hr","event_fraction","ratio"], unit:"Participants in group 1", effect:"hr", sided:true, description:"Plan an event-driven, two-group survival comparison under proportional hazards.", formula:"Information = expected events × allocation₁ × allocation₂; effect = log(HR)." },
  { id:"cluster_mean", category:"Clinical designs", title:"Cluster-randomized means", tag:"Equal-size cluster-mean t-test", fields:["delta","sd","cluster_size","icc","ratio"], defaults:{n:10}, unit:"Clusters in group 1", effect:"delta", sided:true, description:"Plan a continuous-outcome comparison where whole schools, clinics or other clusters are randomized.", formula:"SD of a cluster mean = individual SD × √(ICC + (1 − ICC) / cluster size)." },
  { id:"precision_mean", category:"Estimate precisely", title:"Precision of a mean", tag:"Two-sided t interval", fields:["sd","width"], defaults:{width:.2}, unit:"Participants", precision:true, overrides:{width:{help:"Desired half-width in the outcome’s original units."}}, description:"Choose a sample size for a target interval width rather than a significance test.", formula:"Planning half-width = t₁₋α/₂,ₙ₋₁ × SD / √n." },
  { id:"precision_proportion", category:"Estimate precisely", title:"Precision of a proportion", tag:"Wilson score interval", fields:["p1","width"], unit:"Participants", precision:true, overrides:{p1:{label:"Anticipated population proportion",help:"Use 0.50 for the widest Wilson interval at a fixed sample size."}}, description:"Plan the precision of a prevalence, response rate or other population proportion.", formula:"Wilson half-width evaluated at the anticipated proportion; no guarantee of realized width." },
];
export const methodById = (id) => METHODS.find(m => m.id === id);
export function defaultsFor(id) {
  const m = methodById(id);
  if (!m) throw new Error("Unknown study design.");
  return {method:id,solve:"n",params:{alpha:.05,target:.8,dropout:0,n:64,sides:2,ratio:1,
    ...Object.fromEntries(m.fields.map(k=>[k,FIELD[k].value])),...m.defaults}};
}
export const PRESETS = [
  {title:"Two-group experiment", subtitle:"A moderate standardized difference", spec:defaultsFor("two_mean")},
  {title:"Within-person change", subtitle:"Two measurements, one paired analysis",spec:{...defaultsFor("paired_mean"),params:{...defaultsFor("paired_mean").params,delta:3,sd:8}}},
  {title:"Survey precision",subtitle:"Estimate a proportion within ±5 points",spec:defaultsFor("precision_proportion")},
  {title:"Survival comparison",subtitle:"Events, follow-up and recruitment",spec:defaultsFor("survival")},
];

export function parsePlan(text) {
  const data = JSON.parse(text);
  if (!data || data.format !== "figura-sample-size" || data.version !== 1 || !Array.isArray(data.scenarios) || (data.scenarios.length < 1 || data.scenarios.length > 8))
    throw new Error("Choose a Figura sample-size plan (version 1, up to eight scenarios).");
  return data.scenarios.map((s,i)=>{
    const m=methodById(s?.spec?.method);
    if(!m || !s.spec.params || typeof s.spec.params !== "object") throw new Error(`Scenario ${i+1} has an unsupported design.`);
    const allowed=m.precision?["n","precision"]:["n","power",...(m.effect?["effect"]:[])];
    if(!allowed.includes(s.spec.solve)) throw new Error(`Scenario ${i+1} has an unsupported solver.`);
    const keys=new Set([...m.fields,"alpha","target","dropout","n","sides","ratio"]);
    const params={};
    for(const [k,v] of Object.entries(s.spec.params)) {
      if(!keys.has(k)) continue;
      if(typeof v!=="number" || !Number.isFinite(v)) throw new Error(`Invalid parameter ${k}.`);
      params[k]=v;
    }
    return {name:String(s.name||`Scenario ${i+1}`).slice(0,100),spec:{method:m.id,solve:s.spec.solve,params}};
  });
}

export function csvCell(value) {
  const s = String(value ?? '');
  // Imported scenario names must stay literal when opened in a spreadsheet.
  const literal = typeof value === 'string' && /^[=+\-@\t\r\n]/.test(s) ? "'" + s : s;
  return '"' + literal.replaceAll('"', '""') + '"';
}

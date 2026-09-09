import { FIELD, METHODS, PRESETS, defaultsFor, methodById, parsePlan } from './catalog.js';
import { escape, array, number, percent, metric, resultMarkup, scenariosCsv, reportHtml } from './presentation.js';
const $ = id => document.getElementById(id);
let spec = defaultsFor('two_mean'), current = null, scenarios = [], revision = 0, timer;
let worker, serial = 0;
const pending = new Map();
const copy = x => JSON.parse(JSON.stringify(x));

function getWorker() {
  if(worker) return worker;
  worker = new Worker(new URL('./worker.js', import.meta.url), {type:'module'});
  worker.onmessage = ({data}) => {
    if(data.status) { $('engine-status').textContent=data.status; return; }
    const request=pending.get(data.id);
    if(!request) return;
    pending.delete(data.id);
    if(data.ok) { $('engine-status').textContent=`Local R ${data.result.engine.R} · Ready`; request.resolve(data.result); }
    else request.reject(new Error(data.error || 'The calculation could not be completed.'));
  };
  worker.onerror = event => {
    event.preventDefault();
    $('engine-status').textContent='R engine unavailable';
    for(const request of pending.values()) request.reject(new Error('The local R engine could not load. Check your connection, then choose Calculate plan to retry.'));
    pending.clear(); worker.terminate(); worker=null;
  };
  return worker;
}
function calculate(input) {
  return new Promise((resolve,reject)=>{
    const id=++serial;
    try { const w=getWorker(); pending.set(id,{resolve,reject}); w.postMessage({id,spec:copy(input)}); }
    catch(error) { pending.delete(id); reject(error); }
  });
}
function setStatus(message, error=false) {
  $('result-status').textContent=message;
  $('result-status').classList.toggle('error',error);
}
function showError(error) {
  setStatus(error.message,true);
  $('result-content').innerHTML='<h2 id="result-title">Calculation unavailable</h2><p>Correct the assumptions above and calculate again. The previous result is no longer current.</p>';
  $('result-content').classList.remove('is-stale');
  $('result-content').setAttribute('aria-busy','false');
}
function exportsState() {
  for(const id of ['export-r','export-report','save-scenario']) $(id).disabled=!current || (id==='save-scenario' && scenarios.length>=8);
  for(const id of ['download-plan','download-csv']) $(id).disabled=!current && !scenarios.length;
}
function invalidate() {
  revision++; current=null; clearTimeout(timer); exportsState();
  $('result-content').setAttribute('aria-busy','true');
  $('result-content').classList.add('is-stale');
  setStatus('Assumptions changed. Updating the calculation…');
}
function readForm() {
  const params={...spec.params};
  for(const input of $('planning-form').querySelectorAll('[name]')) {
    if(!input.checkValidity() || input.value==='') throw new Error(`Check “${input.dataset.label}”: enter a valid value${input.min ? ` (minimum ${input.min})`:''}${input.max?` (maximum ${input.max})`:''}.`);
    params[input.name]=Number(input.value);
  }
  spec={...spec,params};
  return copy(spec);
}
async function run() {
  clearTimeout(timer);
  const version=revision;
  let input;
  try { input=readForm(); }
  catch(error) { showError(error); return; }
  setStatus('Calculating in your browser…');
  try {
    const result=await calculate(input);
    if(version!==revision) return;
    // Changing the solver should start from the design just calculated.
    if(input.solve==='n') spec.params.n=result.counts.n;
    if(input.solve==='effect') {
      spec.params[result.effect.key]=result.effect.value;
      const effectInput=$(`param-${result.effect.key}`);
      if(effectInput) effectInput.value=result.effect.value;
    }
    current={spec:copy(spec),result};
    $('result-content').innerHTML=resultMarkup(result);
    $('result-content').classList.remove('is-stale');
    setStatus('Calculated from the assumptions shown.');
    exportsState();
  } catch(error) { if(version===revision) showError(error); }
  finally { if(version===revision) $('result-content').setAttribute('aria-busy','false'); }
}
function field(key, descriptor, value) {
  const d=descriptor, id=`param-${key}`;
  return `<label class="planning-field" for="${id}"><span>${escape(d.label)}</span><input id="${id}" name="${key}" data-label="${escape(d.label)}" aria-label="${escape(d.label)}" type="number" required value="${escape(value)}" step="${d.step??'any'}"${d.min!=null?` min="${d.min}"`:''}${d.max!=null?` max="${d.max}"`:''}${d.help?` aria-describedby="${id}-help"`:''}>${d.help?`<small id="${id}-help">${escape(d.help)}</small>`:''}</label>`;
}
function renderForm() {
  const m=methodById(spec.method);
  $('design-title').textContent=m.title; $('design-description').textContent=m.description;
  for(const b of document.querySelectorAll('[data-method]')) b.toggleAttribute('aria-current', b.dataset.method===m.id);
  const solvers=m.precision ? [['n','Sample size'],['precision','Interval width']] : [['n','Sample size'],['power','Power'],...(m.effect?[['effect','Detectable effect']]:[])];
  $('solve-controls').innerHTML=solvers.map(([key,label])=>`<button type="button" data-solve="${key}" aria-pressed="${spec.solve===key}">${label}</button>`).join('');
  $('design-fields').innerHTML=m.fields.map(k=>{
    const d={...FIELD[k],...m.overrides?.[k]};
    if(k==='width' && spec.solve==='precision') d.label='Reference half-width for the chart';
    if(k===m.effect && spec.solve==='effect') {
      // Signed inputs also determine the direction of the detectable-effect root.
      if(['delta','r','p2','hr'].includes(k)) d.help='This value sets the anticipated direction; R solves the detectable magnitude. '+(d.help||'');
      else return '';
    }
    return field(k,d,spec.params[k]);
  }).join('');
  let settings='';
  if(spec.solve!=='n') settings+=field('n',{label:m.unit,min:m.id==='correlation'?4:m.id==='regression'?spec.params.predictors+3:2,max:1e7,step:1,help:'Enter the analyzable size, before any allowance for attrition.'},spec.params.n);
  settings+=field('alpha',{label:m.precision?'Alpha · 0.05 gives 95% confidence':m.id==='equivalence_mean'?'Alpha for each one-sided test':'Significance level · alpha',min:.00001,max:.25,help:'Enter a proportion: 0.05 means 5%.'},spec.params.alpha);
  if(!m.precision) settings+=field('target',{label:spec.solve==='power'?'Power reference for the chart':'Target power',min:.5,max:.9999,help:'0.80 means 80% power under the anticipated effect.'},spec.params.target);
  if(m.sided) settings+=`<label class="planning-field" for="param-sides"><span>Alternative hypothesis</span><select id="param-sides" name="sides" data-label="Alternative hypothesis"><option value="2"${spec.params.sides===2?' selected':''}>Two-sided</option><option value="1"${spec.params.sides===1?' selected':''}>One-sided · anticipated direction</option></select></label>`;
  settings+=field('dropout',{label:m.id==='cluster_mean'?'Whole-cluster attrition':m.id==='paired_mean'?'Expected loss of complete pairs':'Expected attrition',min:0,max:.8,help:m.id==='survival'?'Additional losses beyond censoring already included in the event fraction.':'0.10 means 10% loss. Recruitment is rounded up separately in each group.'},spec.params.dropout);
  $('settings-fields').innerHTML=settings;
}
function choose(next) {
  spec=copy(next); invalidate(); renderForm(); run();
}
$('planning-form').addEventListener('input',()=>{
  invalidate();
  // Keep partial edits so switching solvers does not silently restore old values.
  for(const el of $('planning-form').querySelectorAll('[name]')) if(el.value!=='' && Number.isFinite(Number(el.value))) spec.params[el.name]=Number(el.value);
  timer=setTimeout(run,400);
});
$('planning-form').addEventListener('submit',e=>{e.preventDefault(); invalidate(); run();});
$('solve-controls').addEventListener('click',e=>{
  const b=e.target.closest('[data-solve]'); if(b) choose({...spec,solve:b.dataset.solve});
});
$('design-list').addEventListener('click',e=>{
  const b=e.target.closest('[data-method]'); if(b) choose(defaultsFor(b.dataset.method));
});
for(const b of document.querySelectorAll('[data-preset]')) b.addEventListener('click',()=>choose(PRESETS[Number(b.dataset.preset)].spec));
$('design-search').addEventListener('input',e=>{
  const q=e.target.value.trim().toLowerCase();
  for(const b of document.querySelectorAll('[data-method]')) b.hidden=!b.textContent.toLowerCase().includes(q);
  for(const category of document.querySelectorAll('.design-category')) category.hidden=![...category.querySelectorAll('button')].some(b=>!b.hidden);
});
function helpers() {
  const r2=Number($('helper-r2').value), sd=Number($('helper-sd').value), r=Number($('helper-r').value);
  $('helper-r2-result').textContent=$('helper-r2').value!=='' && r2>=0 && r2<1 ? `Cohen’s f² = ${number(r2/(1-r2))}` : 'Enter R² between 0 and 1 (exclusive).';
  $('helper-pair-result').textContent=$('helper-sd').value!=='' && $('helper-r').value!=='' && sd>0 && Math.abs(r)<1 ? `SD of differences = ${number(sd*Math.sqrt(2*(1-r)))}` : 'Enter a positive SD and a correlation strictly between −1 and 1.';
}
for(const id of ['helper-r2','helper-sd','helper-r']) $(id).addEventListener('input',helpers);
helpers();

function renderScenarios() {
  $('comparison').innerHTML=scenarios.length ? `<div class="table-scroll"><table><thead><tr><th scope="col">Scenario / design</th><th scope="col">Analyzable</th><th scope="col">Recruit</th><th scope="col">Power / half-width</th><th scope="col">Actions</th></tr></thead><tbody>${scenarios.map((s,i)=>`<tr><th scope="row">${escape(s.name)}<small>${escape(methodById(s.spec.method).title)}</small></th><td>${number(s.result.counts.analyzable)} ${escape(s.result.counts.unit)}<small>${array(s.result.counts.per_group).map(number).join(' / ')}</small></td><td>${number(s.result.counts.recruit)}</td><td>${metric(s.result)}<small>${s.result.metric_kind==='precision'?'Interval half-width':'Power'}</small></td><td><button type="button" data-load="${i}" aria-label="Load ${escape(s.name)}">Load</button><button type="button" data-remove="${i}" aria-label="Remove ${escape(s.name)}">Remove</button></td></tr>`).join('')}</tbody></table></div>` : '<p class="empty-scenarios">Start with one plausible design, then keep alternatives for the assumptions you are least certain about.</p>';
  exportsState();
}
$('save-scenario').addEventListener('click',()=>{
  if(!current || scenarios.length>=8) return;
  scenarios.push({...copy(current),name:$('scenario-name').value.trim() || `Scenario ${scenarios.length+1}`});
  $('scenario-name').value=''; renderScenarios();
  $('plan-status').textContent=`Kept ${scenarios.length} of 8 scenarios in this tab. Save the plan to keep it after closing.`;
});
$('comparison').addEventListener('click',e=>{
  const load=e.target.closest('[data-load]'), remove=e.target.closest('[data-remove]');
  if(load) { const s=scenarios[Number(load.dataset.load)]; $('scenario-name').value=s.name; choose(s.spec); $('design-title').scrollIntoView({block:'start',behavior:'smooth'}); }
  if(remove) { scenarios.splice(Number(remove.dataset.remove),1); renderScenarios(); $('plan-status').textContent='Scenario removed from this tab.'; }
});
function download(content,name,type) {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const a=document.createElement('a'); a.href=url; a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
}
const exportScenarios = () => scenarios.length ? scenarios : current ? [{...current,name:$('scenario-name').value.trim()||'Current plan'}] : [];
$('export-r').addEventListener('click',()=>{if(current) download(current.result.script,`figura-${current.spec.method}.R`,'text/plain;charset=utf-8');});
$('export-report').addEventListener('click',()=>{
  if(!current) return;
  const report=window.open('','_blank');
  if(!report) { $('plan-status').textContent='Allow this site to open the printable report, then try again.'; return; }
  report.document.open(); report.document.write(reportHtml([{...current,name:$('scenario-name').value.trim()||'Current plan'}])); report.document.close();
});
$('download-plan').addEventListener('click',()=>download(JSON.stringify({format:'figura-sample-size',version:1,scenarios:exportScenarios().map(({name,spec})=>({name,spec}))},null,2),'figura-study-plan.json','application/json'));
$('download-csv').addEventListener('click',()=>download(scenariosCsv(exportScenarios()),'figura-study-scenarios.csv','text/csv;charset=utf-8'));
$('open-plan').addEventListener('click',()=>$('plan-file').click());
$('plan-file').addEventListener('change',async e=>{
  const file=e.target.files[0]; if(!file) return;
  $('open-plan').disabled=true;
  try {
    if(file.size>100000) throw new Error('Choose a plan file smaller than 100 KB.');
    const imported=parsePlan(await file.text());
    if(scenarios.length+imported.length>8) throw new Error('Opening this plan would exceed eight scenarios. Remove some current scenarios first.');
    const recalculated=[];
    for(const [i,s] of imported.entries()) {
      $('plan-status').textContent=`Recalculating imported scenario ${i+1} of ${imported.length}…`;
      recalculated.push({...s,result:await calculate(s.spec)});
    }
    if(scenarios.length+recalculated.length>8) throw new Error("The scenario list changed during import and would now exceed eight. Remove some scenarios and reopen the plan.");
    scenarios.push(...recalculated); renderScenarios();
    $('plan-status').textContent=`Opened and recalculated ${recalculated.length} scenarios. Saved results were not used.`;
    if(recalculated.length) choose(recalculated[0].spec);
  } catch(error) { $('plan-status').textContent=`Plan not opened: ${error.message}`; }
  finally { $('open-plan').disabled=false; e.target.value=''; }
});
renderForm(); run();

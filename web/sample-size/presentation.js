import { FIELD, methodById, csvCell } from './catalog.js';
export const escape = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const array = v => Array.isArray(v) ? v : v == null ? [] : [v];
export const number = v => Number(v).toLocaleString('en', Number.isInteger(Number(v)) ? {maximumFractionDigits:0} : {maximumSignificantDigits:5});
export const percent = v => v>0 && v<.0001 ? '≤0.01%' : v<1 && v>.9999 ? '≥99.99%' : `${(v*100).toLocaleString('en',{maximumFractionDigits:2})}%`;
export const metric = r => r.metric_kind === 'precision' ? number(r.metric) : percent(r.metric);

export function assumptionRows(r) {
  const m = methodById(r.method);
  const rows = m.fields.map(k => [m.overrides?.[k]?.label || FIELD[k].label, number(r.params[k])]);
  rows.push([m.precision ? 'Confidence level' : m.id === 'equivalence_mean' ? 'Alpha for each one-sided test' : 'Alpha', m.precision ? percent(1-r.params.alpha) : number(r.params.alpha)]);
  if(m.sided) rows.push(['Test direction', r.params.sides === 2 ? 'Two-sided' : 'One-sided, in the anticipated direction']);
  if(!m.precision) rows.push(['Target power', percent(r.params.target)]);
  rows.push([m.id === 'cluster_mean' ? 'Whole-cluster attrition' : m.id === 'paired_mean' ? 'Loss of complete pairs' : 'Attrition', percent(r.params.dropout)]);
  rows.push(['Analyzable allocation', array(r.counts.per_group).map(number).join(' / ')]);
  return rows;
}

export function curveMarkup(r) {
  const points = array(r.curve);
  if(points.length < 2) return '';
  const W=540, H=270, L=58, R=20, T=23, B=45;
  const minX=points[0].total, maxX=points.at(-1).total;
  const maxY=r.metric_kind==='power' ? 1 : Math.max(r.target,r.metric,...points.map(p=>p.value))*1.08;
  const x = n => L+(n-minX)/(maxX-minX || 1)*(W-L-R);
  const y = v => H-B-v/maxY*(H-T-B);
  const fmt = v => r.metric_kind==='power' ? percent(v) : number(v);
  const path=points.map((p,i)=>`${i?'L':'M'}${x(p.total).toFixed(2)},${y(p.value).toFixed(2)}`).join(' ');
  const ticks = Array.from({length:5},(_,i)=>maxY*i/4);
  const yTitle=r.metric_kind==='power'?'Power':'Interval half-width';
  const title=`${yTitle} as analyzable ${r.counts.unit} increase`;
  return `<div class="chart-heading"><h3>Sensitivity to sample size</h3><span>Other assumptions held fixed</span></div>
    <svg class="sensitivity-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${escape(title)}">
    <title>${escape(title)}</title><desc>Solid curve: ${yTitle.toLowerCase()}. Dashed line: target ${fmt(r.target)}. Dot: current plan, ${r.counts.analyzable} ${escape(r.counts.unit)}, ${fmt(r.metric)}. All values are available in the curve data table.</desc>
    ${ticks.map(v=>`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end">${fmt(v)}</text>`).join('')}
    <line x1="${L}" x2="${W-R}" y1="${y(r.target)}" y2="${y(r.target)}" stroke="var(--ink-muted)" stroke-dasharray="5 5"/>
    <path d="${path}" fill="none" stroke="var(--accent)" stroke-width="3"/>
    <circle cx="${x(r.counts.analyzable)}" cy="${y(r.metric)}" r="5" fill="var(--accent)" stroke="var(--panel)" stroke-width="2"/>
    ${[minX,Math.round((minX+maxX)/2),maxX].map(n=>`<text x="${x(n)}" y="${H-B+20}" text-anchor="middle">${number(n)}</text>`).join('')}
    <text x="${(L+W-R)/2}" y="${H-3}" text-anchor="middle">Total analyzable ${escape(r.counts.unit)}</text>
    </svg><details class="curve-table"><summary>View curve data</summary><div class="table-scroll"><table><thead><tr><th scope="col">Total analyzable ${escape(r.counts.unit)}</th><th scope="col">${yTitle}</th></tr></thead><tbody>${points.map(p=>`<tr><td>${number(p.total)}</td><td>${fmt(p.value)}</td></tr>`).join('')}</tbody></table></div></details>`;
}

export function resultMarkup(r) {
  const m=methodById(r.method), c=r.counts;
  const main=r.solve==='effect' ? number(r.effect.value) : r.solve==='power' || r.solve==='precision' ? metric(r) : number(c.analyzable);
  const unit=r.solve==='effect' ? r.effect.label : r.solve==='power' ? 'power at the specified analyzable size' : r.solve==='precision' ? 'planned interval half-width' : `analyzable ${c.unit}`;
  return `<h2 id="result-title">${escape(m.title)}</h2><p class="result-number" data-result-value="${r.solve==='effect'?r.effect.value:r.solve==='n'?c.analyzable:r.metric}">${main}</p><p class="result-unit">${escape(unit)}</p>
    <p class="result-detail">${c.groups>1 ? array(c.per_group).map((v,i)=>`${number(v)} in group ${i+1}`).join(' · ') : `${number(c.analyzable)} analyzable ${escape(c.unit)}`}${m.id==='cluster_mean'?` · ${number(c.analyzable*r.params.cluster_size)} participants in retained clusters`:''}</p>
    <div class="result-metrics"><div><span>${m.precision?'Planned half-width':'Achieved power'}</span><strong data-metric="${r.metric}">${metric(r)}</strong></div><div><span>${c.unit==='complete pairs'?'Plan for, before pair loss':'Recruit, allowing for attrition'}</span><strong>${number(c.recruit)} ${escape(c.unit)}</strong></div>${c.events!=null?`<div><span>Expected events, rounded up</span><strong>${number(c.events)}</strong></div>`:''}${m.id==='cluster_mean'?`<div><span>Participants to recruit</span><strong>${number(c.participants)}</strong></div>`:''}</div>
    ${r.params.dropout>0?`<p class="quiet">Recruitment by group: ${array(c.recruit_per_group).map(number).join(' / ')}. Attrition is an expected allowance; it does not guarantee the analyzable count.</p>`:''}
    ${curveMarkup(r)}<details class="assumptions-readout"><summary>Method, assumptions &amp; planning statement</summary>
    <p class="formula">${escape(m.formula)}</p><table><tbody>${assumptionRows(r).map(([k,v])=>`<tr><th scope="row">${escape(k)}</th><td>${escape(v)}</td></tr>`).join('')}</tbody></table>
    <ul>${array(r.notes).map(n=>`<li>${escape(n)}</li>`).join('')}</ul><p class="statement">${escape(r.statement)}</p>
    <p><a href="${escape(r.reference.url)}" target="_blank" rel="noopener">${escape(r.reference.label)}</a></p><p class="quiet">Computed locally with R ${escape(r.engine.R)} · pwr ${escape(r.engine.pwr)}</p></details>`;
}

export function scenariosCsv(scenarios) {
  const header=['Scenario','Design','Solver','Analyzable units','Unit','Recruitment units','Allocation (analyzable)','Power','Planned half-width','Assumptions (JSON)','R version','pwr version'];
  const rows=scenarios.map(s=>[s.name,methodById(s.spec.method).title,s.spec.solve,s.result.counts.analyzable,s.result.counts.unit,s.result.counts.recruit,array(s.result.counts.per_group).join(' / '),s.result.metric_kind==='power'?s.result.metric:'',s.result.metric_kind==='precision'?s.result.metric:'',JSON.stringify(s.result.params),s.result.engine.R,s.result.engine.pwr]);
  return [header,...rows].map(row=>row.map(csvCell).join(',')).join('\r\n');
}

export function reportHtml(scenarios) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Figura — study planning report</title><style>
    :root{--accent:#0d6b63;--ink-muted:#465554;--line:#d9dfdc;--panel:white}body{max-width:850px;margin:32px auto;padding:0 24px;color:#202826;font:15px/1.6 system-ui,sans-serif}h1,h2{font-family:Georgia,serif}section{break-before:page}section:first-of-type{break-before:auto}.result-number{font-size:44px;margin:8px 0;line-height:1.1}.result-unit{font-size:20px}.result-metrics{display:flex;gap:24px;flex-wrap:wrap}.result-metrics span{display:block;font-size:12px}.sensitivity-chart{width:100%;max-width:600px}.sensitivity-chart text{font:12px system-ui;fill:#465554}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:7px;border-bottom:1px solid #ddd}th{font-weight:500}.curve-table{display:none}.quiet{color:#465554;font-size:13px}button{padding:12px 20px;font:inherit}summary{font-weight:bold}.statement{padding:14px;background:#f1f5f2}@media print{button{display:none}body{margin:0;padding:0;font-size:11pt}a{color:inherit}svg{max-height:220px}tr{break-inside:avoid}}
    </style></head><body><button onclick="window.print()">Print / save as PDF</button><h1>Figura · Study planning</h1><p>Sample size, power and precision under explicit assumptions. Generated ${escape(new Date().toLocaleDateString('en-CA'))}.</p>
    ${scenarios.map(s=>`<section><h2>${escape(s.name)}</h2>${resultMarkup(s.result).replace('<details class="assumptions-readout">','<details open class="assumptions-readout">')}</section>`).join('')}
    <p class="quiet">Each calculation is conditional on its listed assumptions. Reproduce it with the accompanying R script. <a href="https://figurastats.org/sample-size/">figurastats.org/sample-size/</a></p></body></html>`;
}

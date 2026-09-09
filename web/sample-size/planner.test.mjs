import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {METHODS,defaultsFor,parsePlan,csvCell} from './catalog.js';
import {escape,reportHtml,scenariosCsv,assumptionRows} from './presentation.js';
// Plans contain assumptions, never executable R or trusted saved calculations.
const saved = (scenarios) => JSON.stringify({format:'figura-sample-size',version:1,scenarios});
for(const m of METHODS) {
  const spec=defaultsFor(m.id);
  const [reopened]=parsePlan(saved([{name:m.title,spec,result:{metric:1e99},script:'arbitrary code'}]));
  assert.deepEqual(reopened,{name:m.title,spec});
}
for(const bad of [null,{}, {format:'figura-sample-size',version:2,scenarios:[]},
  {format:'figura-sample-size',version:1,scenarios:[null]}]) assert.throws(()=>parsePlan(JSON.stringify(bad)));
assert.throws(()=>parsePlan(saved(Array.from({length:9},()=>({spec:defaultsFor('two_mean')})))));
assert.throws(()=>parsePlan(saved([{spec:{method:'two_mean',solve:'n',params:{sd:'1'}}}])));
assert.throws(()=>parsePlan(saved([{spec:{method:'precision_mean',solve:'effect',params:{}}}])));
const [safe]=parsePlan(saved([{name:'x'.repeat(200),spec:{...defaultsFor('two_mean'),params:{sd:1,unexpected:'not R'}}}]));
assert.equal(safe.name.length,100);
assert.deepEqual(safe.spec.params,{sd:1});
assert.equal(csvCell('=HYPERLINK("evil")'),'"\'=HYPERLINK(""evil"")"');
assert.equal(csvCell(-.3),'"-0.3"');
assert.equal(escape('<script>"&'), '&lt;script&gt;&quot;&amp;');
// A real native-R result fixture exercises complete reporting and scalar/array
// allocation shapes, without inventing a browser statistical implementation.
const fixture=JSON.parse(await readFile(new URL('../../tests/fixtures/sample-size-reference.json',import.meta.url)));
assert.deepEqual(fixture.map(x=>x.spec.method).sort(),METHODS.map(x=>x.id).sort());
for(const s of fixture) {
  assert.deepEqual(s.spec,defaultsFor(s.spec.method),"reference inputs must match displayed defaults");
  assert.ok(assumptionRows(s.result).length>4);
  const malicious={...s,name:'<img src=x onerror=alert(1)>'};
  const report=reportHtml([malicious]);
  assert.ok(!report.includes('<img src=x'));
  assert.ok(report.includes('&lt;img src=x'));
  assert.ok(report.includes('<details open class="assumptions-readout">'));
  assert.ok(report.includes(s.result.engine.R));
  assert.ok(scenariosCsv([s]).includes('Assumptions (JSON)'));
}
console.log('planner.test.mjs OK');

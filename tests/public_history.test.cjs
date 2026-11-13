const test=require('node:test'),assert=require('node:assert/strict');
const H=require('../public-site/history.js');
const history=JSON.parse(require('node:fs').readFileSync('data/history/public_history.json','utf8'));
// Keep the regression anchor stable as the durable ledger gains later editions.
const frozenIds=new Set(['6edfbde7bc12618f42f5ff501fc644b6050ed60e5bd9d68b6a04d950dd6cbc4f','b5c1908c389701e4b2c43ee4ad789b31eb829a4713db9a4cd4c70c144510851a']);
const baseline=history.editions.filter(e=>frozenIds.has(e.id)).sort((a,b)=>a.reference_date.localeCompare(b.reference_date));
const state={from:'',to:''};
test('frozen pilot has one observed 36-day interval, not a cadence estimate',()=>{
 const events=H.events(history,baseline);assert.equal(events[1].delta,7);assert.equal(events[1].gap,36);assert.equal(events[1].type,'data_changed');
 const f=H.frequency(history,baseline,state)[0];assert.equal(f.changes,1);assert.equal(f.median,null);assert.deepEqual(f.gaps,[36]);
});
test('status-filter denominators and transition subset are explicit',()=>{
 assert.equal(H.count(baseline[0],'listed'),452);assert.equal(H.count(baseline[1],'listed'),461);
 assert.equal(H.count(baseline[0],'rejected_or_denied'),0);assert.equal(H.count(baseline[0]),1327);
});
test('as-of returns one actual edition per source, never future data',()=>{
 const one=H.asOf(baseline,'2026-07-01');assert.equal(one.selected[0].total,1327);
 const none=H.asOf(baseline,'2026-01-01');assert.equal(none.selected.length,0);assert.equal(none.missing.length,1);
});
test('same-date parser revisions are unresolved, not arbitrarily sorted',()=>{
 const variant={...baseline[1],id:'fixture-revision',parser_signature:'fixture@3'};
 const series=[...baseline,variant];const asof=H.asOf(series,'2026-08-03');assert.equal(asof.selected.length,0);assert.equal(asof.ambiguous.length,1);
 assert.equal(H.events(history,series).filter(e=>e.type==='unordered').length,2);
});
test('same bytes and data do not become an update',()=>{
 const same={...baseline[0],id:'fixture-same',reference_date:'2026-07-01'};
 assert.equal(H.events(history,[baseline[0],same])[1].type,'same_document');
 assert.equal(H.frequency(history,[baseline[0],same],state)[0].changes,0);
});
test('file-only and parser revisions are kept distinct',()=>{
 const a={...baseline[0],data_fingerprint:'same'};
 const b={...baseline[1],data_fingerprint:'same'};
 assert.equal(H.events({...history,comparisons:[]},[a,b])[1].type,'file_only');
 assert.equal(H.events(history,[a,{...b,parser_signature:'fixture@3'}])[1].type,'parser_revision');
 assert.equal(H.comparison(history,a,{...b,register_key:'another'}),null);
});
test('a date filter retains the preceding comparison baseline outside the period',()=>{
 const f=H.frequency(history,baseline,{from:'2026-08-01',to:'2026-08-31'})[0];assert.equal(f.editions,1);assert.deepEqual(f.gaps,[36]);
});

test('Biella repeated captures remain auditable but count as two content editions',()=>{
 const fingerprints=new Set([
  'e03e96f373a1ce5a69c71cd2a9a9f86d25bdd0b014f6d1f5a84b6f3428005d6d',
  'c0be361913280ef7eaa0d5ab6052b4ebeb0875447005189620cabb8f51d09272'
 ]);
 const raw=history.editions.filter(e=>e.authority_key==='biella'&&e.reference_date_raw==='2026-08-26'&&fingerprints.has(e.data_fingerprint));
 const display=H.logicalEditions(raw,history.checks);
 assert.ok(raw.length>=46);
 assert.equal(display.length,2);
 assert.deepEqual(display.map(e=>e.source_key).sort(),['biella-applicants','biella-listed']);
 for(const e of display){
   assert.ok(e.document_versions>=23);
   assert.equal(e.archived_ids.length,raw.filter(r=>r.source_key===e.source_key).length);
   assert.equal(e.check_count,history.checks.filter(c=>e.archived_ids.includes(c.edition_id)).length);
   assert.equal(H.latestComparablePair([e]).before,null);
   assert.equal(H.latestComparablePair([e]).after.id,e.id);
 }
});
test('content change under the same declared date stays a separate, unordered version',()=>{
 const a={...baseline[0],id:'test-one',data_fingerprint:'a'.repeat(64)};
 const same={...a,id:'test-two',document_sha256:'f'.repeat(64),parser_signature:'fixture@2'};
 const altered={...a,id:'test-three',document_sha256:'e'.repeat(64),data_fingerprint:'d'.repeat(64)};
 const logical=H.logicalEditions([a,same,altered]);
 assert.equal(logical.length,2);
 assert.equal(logical.find(e=>e.data_fingerprint===a.data_fingerprint).document_versions,2);
 assert.equal(H.latestComparablePair(logical).after,null);
});
test('missing fingerprints never deduplicate distinct source files by equal totals',()=>{
 const a={...baseline[0],id:'undetermined-one',data_fingerprint:null};
 const b={...a,id:'undetermined-two',document_sha256:'f'.repeat(64)};
 assert.equal(H.logicalEditions([a,b]).length,2);
});
test('approved observational comparisons remain reachable through grouped capture IDs',()=>{
 const before={...baseline[0],data_fingerprint:'a'.repeat(64)};
 const after={...baseline[1],data_fingerprint:'b'.repeat(64)};
 const a={...before,id:'replayed-before',document_sha256:'c'.repeat(64)};
 const b={...after,id:'replayed-after',document_sha256:'d'.repeat(64)};
 const first=H.logicalEditions([a,before])[0];
 const second=H.logicalEditions([b,after])[0];
 const evidence=H.comparison(history,first,second);
 assert.ok(evidence);
 assert.equal(evidence.added,21);
});
test('CSV retains missing values and neutralises formula injection',()=>{
 const text=H.csv([{label:'=BAD()',value:null},{label:'ordinary',value:-7}]);assert.match(text,/"'=BAD\(\)"/);assert.match(text,/"-7"/);assert.match(text,/""/);
});

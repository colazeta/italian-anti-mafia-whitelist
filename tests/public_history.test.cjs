const test=require('node:test'),assert=require('node:assert/strict');
const H=require('../public-site/history.js');
const history=JSON.parse(require('node:fs').readFileSync('data/history/public_history.json','utf8'));
const baseline=history.editions.filter(e=>e.authority_key==='cosenza').sort((a,b)=>a.reference_date.localeCompare(b.reference_date));
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
test('CSV retains missing values and neutralises formula injection',()=>{
 const text=H.csv([{label:'=BAD()',value:null},{label:'ordinary',value:-7}]);assert.match(text,/"'=BAD\(\)"/);assert.match(text,/"-7"/);assert.match(text,/""/);
});

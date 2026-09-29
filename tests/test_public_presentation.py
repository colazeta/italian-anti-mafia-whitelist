import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_calendar_dates_are_strict_and_independent_of_timezone():
    script = r"""
const assert=require('node:assert/strict');
const {displayDate,displayCheckTime}=require('./public-site/summary.js');
for(const value of ['2026-08-03','03/08/2026','3/8/2026'])assert.equal(displayDate(value),'03/08/2026');
assert.equal(displayDate('2024-02-29'),'29/02/2024');
assert.equal(displayDate('2000-02-29'),'29/02/2000');
for(const value of ['2026-02-29','1900-02-29','31/04/2026','2026-00-12','2026-13-01'])assert.equal(displayDate(value),value+' (data non valida)');
for(const value of ['08/2026','2026','3 Aug 2026','03/08/26'])assert.equal(displayDate(value),value+' (valore della fonte)');
assert.equal(displayDate(null),'—');
assert.equal(displayDate(''),'—');
assert.equal(displayCheckTime('2026-09-08T00:15:00+02:00'),'07/09/2026 22:15:00 UTC');
assert.equal(displayCheckTime('2026-09-08T22:15:00Z'),'08/09/2026 22:15:00 UTC');
assert.equal(displayCheckTime('2026-02-30T12:00:00Z'),'2026-02-30T12:00:00Z (valore della fonte)');
"""
    for timezone in ['UTC', 'Europe/Rome', 'America/Los_Angeles']:
        subprocess.run(['node', '-e', script], cwd=ROOT, env={**os.environ, 'TZ': timezone}, check=True)


def test_register_labels_identify_territorial_registers_without_merging_them():
    script = r"""
const assert=require('node:assert/strict');
const {registerOptions}=require('./public-site/summary.js');
const rows=['cosenza','parma','pistoia'].map(name=>({register_key:name+'-ordinary',register_name:'White List ordinaria',authority_name:'Prefettura di '+name}));
const before=JSON.stringify(rows);
const opts=registerOptions([...rows,rows[0]]);
assert.equal(opts.length,3);
assert.equal(new Set(opts.map(x=>x[1])).size,3);
assert.deepEqual(new Set(opts.map(x=>x[0])),new Set(rows.map(x=>x.register_key)));
assert.equal(JSON.stringify(rows),before);
assert.throws(()=>registerOptions([...rows,{...rows[0],authority_name:'Altra Prefettura'}]));
"""
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True)


def test_statistics_count_latest_source_presences_with_explicit_denominators():
    script = r"""
const assert=require('node:assert/strict');
const {publicStatistics,latestPublishedRows}=require('./public-site/summary.js');
const row=(source,date,status,extra={})=>({authority_key:'a',authority_name:'A',register_key:'ordinary',source_key:source,reference_date:date,capture_sha256:source+date,source_status:status,name:'Same company',...extra});
const rows=[row('listed','2025-01-01','listed'),row('listed','2026-01-01','listed'),row('listed','2026-01-01','expired_observed'),row('applicants','2025-12-01','pending'),row('listed','2026-01-01','listed',{authority_key:'b',authority_name:'B'})];
const before=JSON.stringify(rows),s=publicStatistics(rows);
assert.equal(s.total,4); // Same name does not mean one presence.
assert.deepEqual(Object.fromEntries(s.statuses.map(x=>[x.status,[x.count,x.percentage]])),{listed:[2,50],expired_observed:[1,25],pending:[1,25]});
assert.deepEqual(s.prefectures,[{key:'a',name:'A',listed:1,pending:1},{key:'b',name:'B',listed:1,pending:0}]);
const filtered=publicStatistics(rows,'a');
assert.equal(filtered.total,3);
assert.ok(filtered.statuses.every(x=>x.count===1&&Math.abs(x.percentage-100/3)<1e-9));
assert.deepEqual(filtered.prefectures,s.prefectures); // First filter does not alter national comparison.
assert.equal(publicStatistics(rows,'missing').total,0);
assert.deepEqual(publicStatistics([]).statuses,[]);
assert.deepEqual(latestPublishedRows(rows.slice().reverse()).reverse(),s.latest);
assert.equal(JSON.stringify(rows),before);
assert.throws(()=>latestPublishedRows([row('x','2026-02-30','listed')]));
assert.throws(()=>latestPublishedRows([row('x','01/02/2026','listed')]));
assert.throws(()=>latestPublishedRows([row('x','2026-01-01','listed'),row('x','2026-01-01','listed',{capture_sha256:'different'})]));
const superseded=[row('x','2025-01-01','listed'),row('x','2025-01-01','listed',{capture_sha256:'different'}),row('x','2026-01-01','pending')];
assert.deepEqual(latestPublishedRows(superseded),[superseded[2]]);
assert.deepEqual(latestPublishedRows(superseded.slice().reverse()),[superseded[2]]);
"""
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True)


def test_temporal_distributions_preserve_dates_statuses_and_reconcile_every_presence():
    script = r"""
const assert=require('node:assert/strict');
const {calendarDate,publicStatistics,defaultStatisticsPeriod,publicDateDistributions}=require('./public-site/summary.js');
const row=(status,application,expiry,extra={})=>({authority_key:'a',authority_name:'A',register_key:'ordinary',source_key:'mixed',reference_date:'2026-09-01',capture_sha256:'same',source_status:status,application_date:application,observed_expiry_date:expiry,...extra});
const rows=[
 row('pending','2025-01-01','2026-02-01'),row('pending','1/1/2025'),
 row('pending','2025-03-31'),row('pending','2024-12-31'),row('pending','2026-01-01'),
 row('pending',null,'2025-01-01'),row('pending',''),row('pending','02/2025'),
 row('pending','2025-02-29'),row('pending','2024-02-29'),row('pending','5201-05-28'),
 row('pending','1202-04-15'),row('pending','2025-01-01',null,{authority_key:'b',authority_name:'B'}),
 row('renewal_update_in_progress','2024-01-01','2025-12-31'),
 row('renewal_update_in_progress','2025-01-01',null),
 row('renewal_update_in_progress',null,'2026-09-30'), // Future expiry is not a rejection.
 row('renewal_requested',null,'2025-12-31'),row('listed','2025-01-01','2025-12-31'),
 row('pending','2025-01-01',null,{reference_date:'2025-08-01',capture_sha256:'old'})
];
const before=JSON.stringify(rows),s=publicStatistics(rows,'a');
assert.deepEqual(defaultStatisticsPeriod(s.latest),{fromYear:2017,toYear:2027,interval:'year'});
const period={fromYear:2025,toYear:2025,interval:'month'};
const [p,u]=publicDateDistributions(s.selected,period);
assert.equal(p.total,12);
assert.deepEqual([p.inPeriod,p.missing,p.uninterpretable,p.before,p.after],[3,2,2,3,2]);
assert.deepEqual(p.bins.map(b=>b.count),[2,0,1,0,0,0,0,0,0,0,0,0]);
assert.equal(p.bins[0].period,'2025-01');assert.equal(p.bins[11].period,'2025-12');
assert.deepEqual(p.outsideYears,[{year:1202,count:1},{year:2024,count:2},{year:2026,count:1},{year:5201,count:1}]);
assert.equal(p.min,'1202-04-15');assert.equal(p.max,'5201-05-28');assert.equal(p.afterReference,1);
assert.equal(u.total,3);assert.equal(u.inPeriod,1);assert.equal(u.bins[11].count,1);
assert.equal(u.missing,1);assert.equal(u.after,1);assert.equal(u.afterReference,0);
for(const d of [p,u]){
 assert.equal(d.total,d.inPeriod+d.missing+d.uninterpretable+d.before+d.after);
 assert.equal(d.inPeriod,d.bins.reduce((sum,b)=>sum+b.count,0));
 assert.equal(d.before+d.after,d.outsideYears.reduce((sum,b)=>sum+b.count,0));
}
const annual=publicDateDistributions(s.selected,{...period,fromYear:2024,toYear:2026,interval:'year'});
assert.deepEqual(annual[0].bins,[{period:'2024',count:2},{period:'2025',count:3},{period:'2026',count:1}]);
assert.equal(publicDateDistributions(publicStatistics(rows).selected,period)[0].inPeriod,4);
assert.deepEqual(publicDateDistributions(s.selected.slice().reverse(),period),[p,u]);
assert.equal(JSON.stringify(rows),before);
assert.equal(calendarDate('0000-01-01').kind,'invalid');
assert.equal(calendarDate('1900-02-29').kind,'invalid');
assert.equal(calendarDate('2000-02-29').iso,'2000-02-29');
assert.equal(calendarDate('01/02/26').kind,'unrecognized');
assert.equal(calendarDate('2026-01-01T00:00:00Z').kind,'unrecognized');
assert.equal(calendarDate('   ').kind,'unrecognized');
for(const d of publicDateDistributions([],period)){
 assert.equal(d.total,0);assert.equal(d.min,null);assert.equal(d.max,null);assert.equal(d.bins.length,12);
 assert.ok(d.bins.every(b=>b.count===0));
}
for(const bad of [{fromYear:2026,toYear:2025},{fromYear:NaN},{fromYear:0},{toYear:10000},{fromYear:1.5},{interval:'day'},{fromYear:1202,toYear:5201}])
 assert.throws(()=>publicDateDistributions(s.selected,{...period,...bad}));
"""
    for timezone in ['UTC', 'Europe/Rome', 'America/Los_Angeles']:
        subprocess.run(['node', '-e', script], cwd=ROOT, env={**os.environ, 'TZ': timezone}, check=True)

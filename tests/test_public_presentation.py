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

/* Every displayed aggregate is computed from the published observations. */
function archiveSummary(registry, prefectures) {
  const records=registry.records;
  const dates=records.map(r=>r.reference_date).filter(Boolean).sort();
  const checks=registry.meta.sources.map(s=>s.document_checked_at).filter(Boolean).sort();
  return {
    observations:records.length,
    authorities:new Set(records.map(r=>r.authority_key)).size,
    registers:new Set(records.map(r=>r.register_key)).size,
    documents:new Set(records.map(r=>JSON.stringify([r.source_key,r.reference_date,r.capture_sha256]))).size,
    earliest:dates[0]||'',latest:dates.at(-1)||'',
    documentsCheckedAt:checks.length===registry.meta.sources.length?checks.at(-1)||'':'',
    directoryAuthorities:prefectures.prefectures.length
  };
}
if(typeof module!=='undefined')module.exports={archiveSummary};

// Presentation only: never rewrite a source value or parse ambiguous date strings.
function displayDate(value,missing='—') {
  if(value===null||value===undefined||value==='')return missing;
  const raw=String(value);
  let parts=/^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  let year,month,day;
  if(parts)[,year,month,day]=parts;
  else {
    parts=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(raw);
    if(!parts)return `${raw} (valore della fonte)`;
    [,day,month,year]=parts;
  }
  const y=Number(year),m=Number(month),d=Number(day);
  const leap=y%4===0&&(y%100!==0||y%400===0);
  const days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
  if(y<1||m<1||m>12||d<1||d>days[m-1])return `${raw} (data non valida)`;
  return `${String(d).padStart(2,'0')}/${String(m).padStart(2,'0')}/${year}`;
}
function displayCheckTime(value,missing='Non registrata') {
  if(!value)return missing;
  // Only timezone-qualified instants; calendar dates above never enter Date().
  const match=/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if(!match||displayDate(match[1]).includes('non valida')||Number(match[2])>23||Number(match[3])>59||Number(match[4])>59)return `${value} (valore della fonte)`;
  const instant=new Date(value);
  if(!Number.isFinite(instant.getTime()))return `${value} (valore della fonte)`;
  const iso=instant.toISOString();
  return `${displayDate(iso.slice(0,10))} ${iso.slice(11,19)} UTC`;
}
function registerOptions(rows) {
  const registers=new Map();
  for(const row of rows) {
    const label=`${row.register_name} · ${row.authority_name}`;
    if(registers.has(row.register_key)&&registers.get(row.register_key)!==label)throw Error('Registro con denominazioni o Prefetture discordanti');
    registers.set(row.register_key,label);
  }
  return [...registers].sort((a,b)=>a[1].localeCompare(b[1],'it'));
}
if(typeof module!=='undefined')Object.assign(module.exports,{displayDate,displayCheckTime,registerOptions});

// Latest available edition per published source series, never latest per company.
function latestPublishedRows(records) {
  const key=r=>JSON.stringify([r.authority_key,r.register_key,r.source_key]);
  const latest=new Map();
  for(const r of records) {
    if(!/^\d{4}-\d{2}-\d{2}$/.test(r.reference_date)||displayDate(r.reference_date).includes('('))throw Error('Data dell’elenco non interpretabile');
    const k=key(r);
    if(!latest.has(k)||r.reference_date>latest.get(k))latest.set(k,r.reference_date);
  }
  const selected=records.filter(r=>r.reference_date===latest.get(key(r)));
  const hashes=new Map();
  for(const r of selected) {
    const k=key(r);
    if(hashes.has(k)&&hashes.get(k)!==r.capture_sha256)throw Error('Più versioni della stessa edizione: selezione da verificare');
    hashes.set(k,r.capture_sha256);
  }
  return selected;
}
function publicStatistics(records,authority='all') {
  const latest=latestPublishedRows(records);
  const selected=latest.filter(r=>authority==='all'||r.authority_key===authority);
  const counts=new Map(),prefectures=new Map();
  for(const r of selected)counts.set(r.source_status,(counts.get(r.source_status)||0)+1);
  for(const r of latest) {
    if(!prefectures.has(r.authority_key))prefectures.set(r.authority_key,{key:r.authority_key,name:r.authority_name,listed:0,pending:0});
    const p=prefectures.get(r.authority_key);
    if(r.source_status==='listed'||r.source_status==='pending')p[r.source_status]++;
  }
  return {latest,selected,total:selected.length,
    statuses:[...counts].map(([status,count])=>({status,count,percentage:selected.length?100*count/selected.length:0})),
    prefectures:[...prefectures.values()].sort((a,b)=>a.name.localeCompare(b.name,'it'))};
}
if(typeof module!=='undefined')Object.assign(module.exports,{latestPublishedRows,publicStatistics});

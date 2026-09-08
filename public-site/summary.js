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

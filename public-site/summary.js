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

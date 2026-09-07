from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    psycopg = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


TAB_MARKER = '<button class="tab" data-view="method">Metodo</button>'
VIEW_MARKER = '<section class="view" id="view-method"></section>'
STYLE_MARKER = '</style>'
BODY_MARKER = '</body>'
ROW_LOCATOR_RE = re.compile(r"^row:(\d+)$")

REVIEW_FIELDS = (
    "review_verdict",
    "review_municipality",
    "review_street",
    "review_civic",
    "review_coordinate",
    "review_precision",
    "review_notes",
    "reviewed_at",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _fingerprint(sample_path: Path, summary_path: Path) -> str:
    digest = hashlib.sha256()
    for path in (sample_path, summary_path):
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _source_occurrences(
    dsn: str,
    address_ids: list[str],
    source_evidence: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if psycopg is None:
        raise RuntimeError(
            "psycopg is required; install the project with the database extra"
        ) from _IMPORT_ERROR
    if not address_ids:
        return {}

    ids = [uuid.UUID(value) for value in address_ids]
    sql = """
        WITH requested(address_id) AS (
            SELECT unnest(%s::uuid[])
        )
        SELECT DISTINCT
            r.address_id::text,
            e.legal_entity_id::text,
            COALESCE(en.name, '') AS entity_name,
            eo.observation_date::text,
            pr.record_locator
        FROM requested r
        JOIN core.establishment_address ea
          ON ea.address_id = r.address_id
         AND upper_inf(ea.system_period)
        JOIN core.establishment e
          ON e.establishment_id = ea.establishment_id
         AND upper_inf(e.system_period)
        LEFT JOIN LATERAL (
            SELECT n.name
            FROM core.entity_name n
            WHERE n.legal_entity_id = e.legal_entity_id
              AND n.name_type_code = 'legal_name'
              AND upper_inf(n.system_period)
            ORDER BY lower(n.system_period) DESC, n.entity_name_id
            LIMIT 1
        ) en ON true
        JOIN semantic.entity_projection_resolution er
          ON er.legal_entity_id = e.legal_entity_id
         AND er.decision_status_code = 'accepted'
        JOIN semantic.entity_observation eo
          ON eo.entity_observation_id = er.entity_observation_id
        JOIN semantic.establishment_observation eso
          ON eso.entity_observation_id = eo.entity_observation_id
         AND btrim(eso.full_address_raw) = (
             SELECT btrim(a.full_address)
             FROM core.address a
             WHERE a.address_id = r.address_id
         )
        JOIN source.parsed_record pr
          ON pr.parsed_record_id = eo.parsed_record_id
        ORDER BY r.address_id, eo.observation_date, pr.record_locator, e.legal_entity_id
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, (ids,))
        for (
            address_id,
            entity_id,
            entity_name,
            observation_date,
            record_locator,
        ) in cur.fetchall():
            item: dict[str, Any] = {
                "legal_entity_id": entity_id,
                "entity_name": entity_name,
                "observation_date": observation_date,
                "record_locator": record_locator,
            }
            match = ROW_LOCATOR_RE.fullmatch(record_locator or "")
            edition = source_evidence.get("editions", {}).get(observation_date, {})
            if match and isinstance(edition, dict):
                ordinal = str(int(match.group(1)))
                page = (edition.get("rows") or {}).get(ordinal, {}).get("page_start")
                pdf_path = edition.get("pdf_path")
                if page and pdf_path:
                    item["row_ordinal"] = int(ordinal)
                    item["page_start"] = int(page)
                    item["source_pdf_href"] = f"{pdf_path}#page={int(page)}"
            grouped[address_id].append(item)
    return dict(grouped)


def build_review_payload(
    *,
    dsn: str,
    sample_path: Path,
    summary_path: Path,
    source_evidence_path: Path,
) -> dict[str, Any]:
    rows = _read_csv(sample_path)
    summary = _load_json(summary_path)
    evidence = _load_json(source_evidence_path)
    sample_ids = [row["address_id"] for row in rows]
    occurrences = _source_occurrences(dsn, sample_ids, evidence)

    output_rows: list[dict[str, Any]] = []
    for position, row in enumerate(rows, start=1):
        item: dict[str, Any] = dict(row)
        item["sample_position"] = position
        item["source_occurrences"] = occurrences.get(row["address_id"], [])
        for field in REVIEW_FIELDS:
            item[field] = ""
        output_rows.append(item)

    return {
        "schema_version": 1,
        "sample_fingerprint": _fingerprint(sample_path, summary_path),
        "sample_size": len(output_rows),
        "summary": summary,
        "review_fields": list(REVIEW_FIELDS),
        "rows": output_rows,
        "source_evidence_archive_policy": evidence.get("archive_policy"),
    }


CSS = r'''
.review-progress{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:4px;margin-bottom:5px}
.review-progress .statuscell{background:var(--chrome)}
.review-layout{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:7px}
.review-panel{border:1px solid #777;background:#fff}
.review-panel-title{background:var(--head);border-bottom:1px solid #888;padding:3px 5px;font-weight:700}
.review-panel-body{padding:5px}
.review-compare{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.review-box{border:1px solid #999;padding:5px;background:#fff}
.review-box h4{margin:0 0 4px;background:#eee;border-bottom:1px solid #bbb;padding:2px 3px}
.review-form{display:grid;grid-template-columns:180px 1fr;gap:0;border:1px solid #999}
.review-form label,.review-form>div{padding:3px 5px;border-bottom:1px solid #ccc}
.review-form label{background:#eee;font-weight:700;border-right:1px solid #bbb}
.review-form select,.review-form textarea{width:100%;border:1px solid #777;background:#fff;font:inherit}
.review-form textarea{min-height:70px;resize:vertical}
.review-queue{max-height:520px;overflow:auto}
.review-queue table{min-width:900px}
.review-queue tr.current{background:#c9d8f0}
.review-queue tr.done td:first-child{color:#075c0a;font-weight:700}
.review-actions{display:flex;gap:4px;flex-wrap:wrap;margin:5px 0}
.review-small{font-size:11px}
@media(max-width:1050px){.review-layout,.review-compare{grid-template-columns:1fr}.review-progress{grid-template-columns:1fr 1fr}}
'''


JS = r'''
(function(){
const AV=window.__ADDRESS_VALIDATION__;
if(!AV)return;
const avEsc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const avKey='white-list-address-review:'+AV.sample_fingerprint;
let avState={};
try{avState=JSON.parse(localStorage.getItem(avKey)||'{}')||{}}catch(_){avState={}}
let avCurrent=0, avFilter='all', avSearch='';

function avRowState(row){return avState[row.address_id]||{}}
function avSave(row,patch){
  avState[row.address_id]={...avRowState(row),...patch,reviewed_at:new Date().toISOString()};
  localStorage.setItem(avKey,JSON.stringify(avState)); avRender();
}
function avReviewed(row){let v=avRowState(row).review_verdict;return v==='correct'||v==='incorrect'||v==='uncertain'}
function avVisible(){
  return AV.rows.filter(r=>(avFilter==='all'||r.review_stratum===avFilter)&&(!avSearch||JSON.stringify(r).toLowerCase().includes(avSearch.toLowerCase())));
}
function avWeightedPrecision(rows){
  let good=0,total=0;
  rows.forEach(r=>{let s=avRowState(r),w=Number(r.sampling_weight||1);if(s.review_verdict==='correct'){good+=w;total+=w}else if(s.review_verdict==='incorrect'){total+=w}});
  return total?100*good/total:null;
}
function avChoice(value,labels){
  return `<option value=""></option>`+Object.entries(labels).map(([v,l])=>`<option value="${avEsc(v)}"${value===v?' selected':''}>${avEsc(l)}</option>`).join('');
}
function avOccurrences(row){
  let xs=row.source_occurrences||[];
  if(!xs.length)return '<div class="muted">Nessun collegamento deterministico aggiuntivo alla riga sorgente.</div>';
  return xs.map(x=>`<div class="review-small"><b>${avEsc(x.entity_name||x.legal_entity_id)}</b> · ${avEsc(x.observation_date||'')} · <span class="mono">${avEsc(x.record_locator||'')}</span>${x.source_pdf_href?` · <a href="${avEsc(x.source_pdf_href)}" target="_blank" rel="noopener">Apri PDF p.${avEsc(x.page_start)}</a>`:''}</div>`).join('');
}
function avMap(row){
  if(!row.latitude||!row.longitude)return '<span class="muted">nessuna coordinata</span>';
  let lat=Number(row.latitude),lon=Number(row.longitude);
  let href=`https://www.openstreetmap.org/?mlat=${encodeURIComponent(lat)}&mlon=${encodeURIComponent(lon)}#map=18/${encodeURIComponent(lat)}/${encodeURIComponent(lon)}`;
  return `<a href="${href}" target="_blank" rel="noopener">Apri su OpenStreetMap</a> <span class="mono">${avEsc(row.latitude)}, ${avEsc(row.longitude)}</span>`;
}
function avMetrics(){
  let reviewed=AV.rows.filter(avReviewed), determinate=reviewed.filter(r=>['correct','incorrect'].includes(avRowState(r).review_verdict));
  let wp=avWeightedPrecision(AV.rows);
  return {reviewed:reviewed.length,determinate:determinate.length,weighted:wp};
}
function avStratumTable(){
  let groups={};AV.rows.forEach(r=>(groups[r.review_stratum]??=[]).push(r));
  return `<table class="summary"><tr><th>Strato</th><th>Campione</th><th>Rivisti</th><th>Precisione pesata*</th></tr>`+
    Object.entries(groups).sort().map(([k,rows])=>{let rev=rows.filter(avReviewed).length,wp=avWeightedPrecision(rows);return `<tr><td class="mono">${avEsc(k)}</td><td>${rows.length}</td><td>${rev}</td><td>${wp===null?'—':wp.toFixed(1)+'%'}</td></tr>`}).join('')+
    `</table><div class="muted review-small">* Tra giudizi determinati correct/incorrect; usa i pesi del campione stratificato.</div>`;
}
function avExport(kind){
  let payload=AV.rows.map(r=>({...r,...avRowState(r)}));
  if(kind==='json'){
    let blob=new Blob([JSON.stringify({sample_fingerprint:AV.sample_fingerprint,exported_at:new Date().toISOString(),rows:payload},null,2)],{type:'application/json'});
    avDownload(blob,`cosenza-address-review-${AV.sample_fingerprint.slice(0,10)}.json`);return;
  }
  let fields=[...new Set(payload.flatMap(Object.keys))].filter(k=>k!=='source_occurrences');
  let q=v=>`"${String(v??'').replaceAll('"','""')}"`;
  let csv=fields.map(q).join(',')+'\n'+payload.map(r=>fields.map(f=>q(r[f])).join(',')).join('\n');
  avDownload(new Blob([csv],{type:'text/csv;charset=utf-8'}),`cosenza-address-review-${AV.sample_fingerprint.slice(0,10)}.csv`);
}
function avDownload(blob,name){let a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function avImport(file){
  let reader=new FileReader();reader.onload=()=>{try{let x=JSON.parse(reader.result);if(x.sample_fingerprint!==AV.sample_fingerprint)throw new Error('fingerprint del campione diverso');let next={};(x.rows||[]).forEach(r=>{let s={};AV.review_fields.forEach(f=>{if(r[f]!=null)s[f]=r[f]});next[r.address_id]=s});avState=next;localStorage.setItem(avKey,JSON.stringify(avState));avRender()}catch(e){alert('Import non valido: '+e.message)}};reader.readAsText(file);
}
function avReviewCard(row){
  let s=avRowState(row);
  return `<div class="review-panel"><div class="review-panel-title">CASO ${row.sample_position}/${AV.sample_size} · ${avEsc(row.review_stratum)}</div><div class="review-panel-body">
    <div class="review-compare">
      <div class="review-box"><h4>FONTE PREFETTURA</h4><div><b>${avEsc(row.source_address)}</b></div><div class="muted">country source: ${avEsc(row.source_country_code||'—')}</div><hr>${avOccurrences(row)}</div>
      <div class="review-box"><h4>RISULTATO ANNCSU</h4><div><b>${avEsc(row.normalised_address||'Nessun candidato')}</b></div><div>Strada: ${avEsc(row.street_name||'—')}</div><div>Civico: ${avEsc(row.house_number||'—')}</div><div>Comune: ${avEsc(row.locality||'—')}</div><div>Precisione: <span class="mono">${avEsc(row.precision_code||'—')}</span></div><div>Coordinate: ${avMap(row)}</div><div class="muted mono">provider=${avEsc(row.provider_name||'—')} · version=${avEsc(row.provider_version||'—')}</div></div>
    </div>
    <div class="note">Valuta il <b>linkage</b> separatamente dalla precisione spaziale. Un risultato <code>street</code> non pretende di identificare il portone.</div>
    <div class="review-form">
      <label>Giudizio complessivo</label><div><select data-av="review_verdict">${avChoice(s.review_verdict,{'correct':'Corretto','incorrect':'Errato','uncertain':'Incerto / non verificabile'})}</select></div>
      <label>Comune</label><div><select data-av="review_municipality">${avChoice(s.review_municipality,{'yes':'Sì','no':'No','uncertain':'Incerto'})}</select></div>
      <label>Strada / odonimo</label><div><select data-av="review_street">${avChoice(s.review_street,{'yes':'Sì','no':'No','uncertain':'Incerto'})}</select></div>
      <label>Civico</label><div><select data-av="review_civic">${avChoice(s.review_civic,{'yes':'Sì','no':'No','na':'N/A','uncertain':'Incerto'})}</select></div>
      <label>Coordinata plausibile</label><div><select data-av="review_coordinate">${avChoice(s.review_coordinate,{'yes':'Sì','no':'No','na':'N/A','uncertain':'Incerto'})}</select></div>
      <label>Precisione dichiarata</label><div><select data-av="review_precision">${avChoice(s.review_precision,{'yes':'Adeguata','no':'Sovra/sottostimata','uncertain':'Incerto'})}</select></div>
      <label>Note</label><div><textarea data-av="review_notes">${avEsc(s.review_notes||'')}</textarea></div>
    </div>
    <div class="review-actions"><button class="btn" id="av-prev">← precedente</button><button class="btn" id="av-next">successivo →</button><button class="btn" id="av-next-unreviewed">prossimo non rivisto</button></div>
  </div></div>`;
}
function avQueue(rows){
  return `<div class="review-panel"><div class="review-panel-title">CODA CAMPIONE</div><div class="review-panel-body review-queue"><table class="tree"><thead><tr><th>#</th><th>Stato</th><th>Strato</th><th>Indirizzo fonte</th><th>Precisione</th></tr></thead><tbody>`+
    rows.map(r=>{let idx=AV.rows.indexOf(r),s=avRowState(r);return `<tr data-av-index="${idx}" class="${idx===avCurrent?'current ':''}${avReviewed(r)?'done':''}"><td>${r.sample_position}</td><td>${avEsc(s.review_verdict||'—')}</td><td class="mono">${avEsc(r.review_stratum)}</td><td>${avEsc(r.source_address)}</td><td class="mono">${avEsc(r.precision_code||'—')}</td></tr>`}).join('')+
    `</tbody></table></div></div>`;
}
function avRender(){
  let root=document.querySelector('#view-address-validation');if(!root)return;
  let visible=avVisible();if(!visible.length){root.innerHTML='<div class="note">Nessun caso corrisponde ai filtri.</div>';return}
  if(!visible.includes(AV.rows[avCurrent]))avCurrent=AV.rows.indexOf(visible[0]);
  let row=AV.rows[avCurrent],m=avMetrics(),strata=[...new Set(AV.rows.map(r=>r.review_stratum))].sort();
  root.innerHTML=
   section('VALIDAZIONE SOSTANZIALE INDIRIZZI — COSENZA',`<div class="note"><b>Campione congelato:</b> ${AV.sample_size} casi · fingerprint <span class="mono">${avEsc(AV.sample_fingerprint.slice(0,16))}…</span>. I giudizi restano nel browser finché non li esporti; esporta JSON/CSV per conservarli come gold standard.</div>
   <div class="review-progress"><div class="statuscell">Rivisti: <b>${m.reviewed}/${AV.sample_size}</b></div><div class="statuscell">Determinati: <b>${m.determinate}</b></div><div class="statuscell">Precisione pesata: <b>${m.weighted===null?'—':m.weighted.toFixed(1)+'%'}</b></div><div class="statuscell">Strato corrente: <b>${avEsc(row.review_stratum)}</b></div></div>
   <div class="toolbar"><label>Strato</label><select id="av-filter"><option value="all">Tutti</option>${strata.map(x=>`<option value="${avEsc(x)}"${avFilter===x?' selected':''}>${avEsc(x)}</option>`).join('')}</select><label>Cerca</label><input id="av-search" value="${avEsc(avSearch)}"><button class="btn" id="av-export-json">Esporta JSON</button><button class="btn" id="av-export-csv">Esporta CSV</button><label class="btn" style="display:inline-flex;align-items:center">Importa JSON<input id="av-import" type="file" accept="application/json" style="display:none"></label><button class="btn" id="av-reset">Azzera giudizi</button></div>`)+
   section('STIMA PER STRATO',avStratumTable())+
   `<div class="review-layout">${avReviewCard(row)}${avQueue(visible)}</div>`;
  root.querySelectorAll('[data-av]').forEach(el=>el.onchange=()=>avSave(row,{[el.dataset.av]:el.value}));
  let notes=root.querySelector('[data-av="review_notes"]');if(notes)notes.oninput=()=>{avState[row.address_id]={...avRowState(row),review_notes:notes.value};localStorage.setItem(avKey,JSON.stringify(avState))};
  root.querySelector('#av-prev').onclick=()=>{avCurrent=Math.max(0,avCurrent-1);avRender()};
  root.querySelector('#av-next').onclick=()=>{avCurrent=Math.min(AV.rows.length-1,avCurrent+1);avRender()};
  root.querySelector('#av-next-unreviewed').onclick=()=>{let start=avCurrent;for(let i=1;i<=AV.rows.length;i++){let j=(start+i)%AV.rows.length;if(!avReviewed(AV.rows[j])){avCurrent=j;break}}avRender()};
  root.querySelectorAll('[data-av-index]').forEach(tr=>tr.onclick=()=>{avCurrent=Number(tr.dataset.avIndex);avRender()});
  root.querySelector('#av-filter').onchange=e=>{avFilter=e.target.value;avRender()};
  root.querySelector('#av-search').oninput=e=>{avSearch=e.target.value;avRender()};
  root.querySelector('#av-export-json').onclick=()=>avExport('json');
  root.querySelector('#av-export-csv').onclick=()=>avExport('csv');
  root.querySelector('#av-import').onchange=e=>{if(e.target.files[0])avImport(e.target.files[0])};
  root.querySelector('#av-reset').onclick=()=>{if(confirm('Cancellare tutti i giudizi locali per questo campione?')){avState={};localStorage.removeItem(avKey);avRender()}};
}
const avTab=document.querySelector('[data-view="address-validation"]');
if(avTab)avTab.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===avTab));document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id==='view-address-validation'));avRender()});
avRender();
})();
'''


def patch_explorer(index_path: Path, payload: dict[str, Any]) -> None:
    html = index_path.read_text(encoding="utf-8")
    if 'data-view="address-validation"' in html:
        raise ValueError("Explorer already contains the address-validation tab")
    for marker in (TAB_MARKER, VIEW_MARKER, STYLE_MARKER, BODY_MARKER):
        if marker not in html:
            raise ValueError(f"Explorer template marker not found: {marker}")
    html = html.replace(
        TAB_MARKER,
        TAB_MARKER
        + '\n<button class="tab" data-view="address-validation">Validazione indirizzi</button>',
        1,
    )
    html = html.replace(
        VIEW_MARKER,
        VIEW_MARKER
        + '<section class="view" id="view-address-validation"></section>',
        1,
    )
    html = html.replace(STYLE_MARKER, CSS + "\n" + STYLE_MARKER, 1)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    injection = (
        f'<script>window.__ADDRESS_VALIDATION__={data};</script>\n'
        f'<script>{JS}</script>\n'
    )
    html = html.replace(BODY_MARKER, injection + BODY_MARKER, 1)
    index_path.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Add a persistent manual address-validation tab to the retro Dataset Explorer."
        )
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    args = parser.parse_args()
    payload = build_review_payload(
        dsn=args.dsn,
        sample_path=args.sample,
        summary_path=args.summary,
        source_evidence_path=args.source_evidence,
    )
    patch_explorer(args.index, payload)
    print(
        json.dumps(
            {
                "index": str(args.index),
                "sample_size": payload["sample_size"],
                "sample_fingerprint": payload["sample_fingerprint"],
                "rows_with_source_occurrences": sum(
                    bool(row["source_occurrences"]) for row in payload["rows"]
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

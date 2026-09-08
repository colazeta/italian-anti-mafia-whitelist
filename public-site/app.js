const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const fmt=n=>new Intl.NumberFormat('it-IT').format(Number(n||0));
const pct=n=>`${Number(n).toFixed(2).replace('.',',')}%`;
const section=(title,body)=>`<div class="section"><div class="section-title">${esc(title)}</div><div class="section-body">${body}</div></div>`;
const metric=(label,value)=>`<div class="metricline"><span>${esc(label)}</span><span class="value">${esc(value)}</span></div>`;
const STATUS={listed:'Iscritta',pending:'In istruttoria',renewal_update_in_progress:'Aggiornamento in corso',renewal_requested:'Rinnovo richiesto',other_or_unknown:'Altro / non classificato',rejected_or_denied:'Diniego / rigetto',cancellation_related:'Cancellazione'};
const registryState={query:'',status:'listed',page:1,size:50};
let SITE=null;
let REGISTRY=null;

function activate(name){
  $$('.tab').forEach(x=>x.classList.toggle('active',x.dataset.view===name));
  $$('.view').forEach(x=>x.classList.toggle('active',x.id===`view-${name}`));
}
function listText(values){
  if(!Array.isArray(values))return '';
  return values.map(v=>{
    if(typeof v==='string')return v;
    if(!v||typeof v!=='object')return String(v??'');
    return v.raw_value||v.value||v.label||v.date||v.code||'';
  }).filter(Boolean).join(' · ');
}
function badge(status){
  const cls=status==='listed'?'ok':status==='pending'?'warn':'';
  return `<span class="badge ${cls}">${esc(STATUS[status]||status)}</span>`;
}
function registryRows(){
  if(!REGISTRY)return [];
  const q=registryState.query.trim().toLocaleLowerCase('it');
  return REGISTRY.records.filter(r=>{
    if(registryState.status!=='all'&&r.source_status!==registryState.status)return false;
    if(!q)return true;
    const hay=[r.name,r.registered_office,r.secondary_office,r.identifier_field_raw,r.requested_activities_raw,r.application_date_field_raw,r.outcome_raw,r.record_locator].join(' ').toLocaleLowerCase('it');
    return hay.includes(q);
  });
}
function drawRegistry(){
  if(!REGISTRY){
    $('#view-registry').innerHTML='<div class="note bad"><b>Registro non disponibile.</b> L’export source-backed non è stato prodotto dal deploy.</div>';
    return;
  }
  const all=registryRows();
  const pages=Math.max(1,Math.ceil(all.length/registryState.size));
  registryState.page=Math.min(registryState.page,pages);
  const start=(registryState.page-1)*registryState.size;
  const shown=all.slice(start,start+registryState.size);
  $('#rowstatus').textContent=`${fmt(all.length)} righe filtrate`;
  const rows=shown.map(r=>`<tr class="clickrow" data-record="${esc(r.record_locator)}" tabindex="0">
    <td><b>${esc(r.name)}</b></td>
    <td>${esc(r.registered_office)}</td>
    <td class="mono">${esc(listText(r.identifiers)||r.identifier_field_raw)}</td>
    <td>${esc(listText(r.requested_activities)||r.requested_activities_raw)}</td>
    <td class="nowrap">${esc(listText(r.application_dates)||r.application_date_field_raw)}</td>
    <td class="nowrap">${esc(r.observed_listing_date)}</td>
    <td class="nowrap">${esc(r.observed_expiry_date)}</td>
    <td>${badge(r.source_status)}</td>
    <td>${esc(r.authority_name)}</td>
  </tr>`).join('');
  const counts=REGISTRY.meta.status_counts||{};
  $('#view-registry').innerHTML=
    `<div class="public-banner">REGISTRO PUBBLICO · edizione ${esc(REGISTRY.meta.reference_date)} · ${fmt(REGISTRY.meta.record_count)} osservazioni source-backed</div>`+
    section('RICERCA NEL REGISTRO',`<div class="toolbar">
      <label for="reg-q">Cerca</label><input id="reg-q" type="search" value="${esc(registryState.query)}" placeholder="Ragione sociale, CF/P.IVA, sede, attività…">
      <label for="reg-status">Stato</label><select id="reg-status">
        <option value="listed" ${registryState.status==='listed'?'selected':''}>Iscritte / listed (${fmt(counts.listed)})</option>
        <option value="pending" ${registryState.status==='pending'?'selected':''}>In istruttoria (${fmt(counts.pending)})</option>
        <option value="renewal_update_in_progress" ${registryState.status==='renewal_update_in_progress'?'selected':''}>Aggiornamento in corso (${fmt(counts.renewal_update_in_progress)})</option>
        <option value="renewal_requested" ${registryState.status==='renewal_requested'?'selected':''}>Rinnovo richiesto (${fmt(counts.renewal_requested)})</option>
        <option value="all" ${registryState.status==='all'?'selected':''}>Tutti gli stati (${fmt(REGISTRY.meta.record_count)})</option>
      </select>
      <label for="reg-size">Righe</label><select id="reg-size"><option ${registryState.size===25?'selected':''}>25</option><option ${registryState.size===50?'selected':''}>50</option><option ${registryState.size===100?'selected':''}>100</option></select>
      <a class="btn linkbtn" href="data/registry.csv" download>CSV</a><a class="btn linkbtn" href="data/registry.json" download>JSON</a>
    </div><div class="note"><b>Vista predefinita:</b> imprese indicate dalla fonte come <span class="mono">listed</span>. Clicca una riga per vedere tutti gli attributi, l’esito testuale e la provenance. L’unità corrente è la riga/osservazione dell’ultima edizione approvata, non ancora una deduplicazione canonica nazionale.</div>`)+
    section(`REGISTRO — ${fmt(all.length)} RISULTATI`,`<div class="gridwrap registry-grid"><table class="grid"><thead><tr><th>Ragione sociale</th><th>Sede legale</th><th>CF / P.IVA</th><th>Attività richieste</th><th>Istanza</th><th>Inserimento osservato</th><th>Scadenza osservata</th><th>Stato</th><th>Prefettura</th></tr></thead><tbody>${rows||'<tr><td colspan="9">Nessun risultato.</td></tr>'}</tbody></table></div><div class="pager"><button class="btn" id="prev" ${registryState.page<=1?'disabled':''}>◀ Precedente</button><span>Pagina ${registryState.page} / ${pages}</span><button class="btn" id="next" ${registryState.page>=pages?'disabled':''}>Successiva ▶</button></div>`);
  $('#reg-q').addEventListener('input',e=>{registryState.query=e.target.value;registryState.page=1;drawRegistry()});
  $('#reg-status').addEventListener('change',e=>{registryState.status=e.target.value;registryState.page=1;drawRegistry()});
  $('#reg-size').addEventListener('change',e=>{registryState.size=Number(e.target.value);registryState.page=1;drawRegistry()});
  $('#prev')?.addEventListener('click',()=>{registryState.page--;drawRegistry()});
  $('#next')?.addEventListener('click',()=>{registryState.page++;drawRegistry()});
  $$('.clickrow').forEach(row=>{
    const open=()=>openDetail(row.dataset.record);
    row.addEventListener('click',open);
    row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}});
  });
}
function openDetail(locator){
  const r=REGISTRY?.records.find(x=>x.record_locator===locator);
  if(!r)return;
  $('#detail-title').textContent=r.name||'Dettaglio osservazione';
  const id=listText(r.identifiers)||r.identifier_field_raw||'—';
  const acts=listText(r.requested_activities)||r.requested_activities_raw||'—';
  const apps=listText(r.application_dates)||r.application_date_field_raw||'—';
  $('#detail-body').innerHTML=`<div class="note"><b>Osservazione della fonte ufficiale.</b> Il locator pubblico permette di risalire alla specifica riga dell’edizione approvata.</div>
    <div class="kv"><div>Ragione sociale</div><div><b>${esc(r.name)}</b></div><div>Stato</div><div>${badge(r.source_status)}</div><div>Prefettura</div><div>${esc(r.authority_name)}</div><div>Edizione</div><div>${esc(r.reference_date)}</div><div>Locator pubblico</div><div class="mono">${esc(r.record_locator)}</div><div>Riga sorgente</div><div class="mono">${esc(r.source_row_ordinal)}</div><div>Sede legale</div><div>${esc(r.registered_office||'—')}</div><div>Sede secondaria</div><div>${esc(r.secondary_office||'—')}</div><div>CF / P.IVA</div><div class="mono">${esc(id)}</div><div>Attività richieste</div><div>${esc(acts)}</div><div>Data/e istanza</div><div>${esc(apps)}</div><div>Inserimento osservato</div><div>${esc(r.observed_listing_date||'—')}</div><div>Scadenza osservata</div><div>${esc(r.observed_expiry_date||'—')}</div></div>
    ${section('ESITO COME PUBBLICATO',`<div class="raw">${esc(r.outcome_raw||'—')}</div>`)}
    ${section('PROVENANCE',`<table class="summary"><tr><th>Pagina ufficiale</th><td><a href="${esc(r.source_page_url)}" target="_blank" rel="noopener">Apri pagina Prefettura</a></td></tr><tr><th>Documento ufficiale</th><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Apri PDF</a></td></tr><tr><th>Capture SHA-256</th><td class="mono">${esc(REGISTRY.meta.capture_sha256)}</td></tr><tr><th>Parser</th><td class="mono">${esc(REGISTRY.meta.parser_name)} ${esc(REGISTRY.meta.parser_version)}</td></tr><tr><th>Audit tecnico</th><td><a href="${esc(SITE.audit.repository_url)}" target="_blank" rel="noopener">Repository pubblico</a> · <a href="${esc(SITE.audit.parser_url)}" target="_blank" rel="noopener">Parser</a></td></tr></table>`)}`;
  $('#detail').classList.add('open');
  $('#detail').setAttribute('aria-hidden','false');
}
function closeDetail(){
  $('#detail').classList.remove('open');
  $('#detail').setAttribute('aria-hidden','true');
}
function renderOverview(D){
  $('#view-overview').innerHTML=`<div class="public-banner">${esc(D.meta.classification)} · dati al ${esc(D.meta.data_as_of)}</div>`+
  section('ARCHIVIO PUBBLICO',`<p><b>${esc(D.meta.title)}</b> rende interrogabili le White List antimafia con attributi di fonte, storico e provenance.</p><div class="note">${esc(D.meta.disclaimer)}</div>`)+
  `<div class="split">${section('REGISTRO PUBBLICATO',metric('Prefetture con righe pubblicate',fmt(D.national.published_entity_registers.length))+metric('Cosenza — righe ultima edizione',fmt(D.cosenza.source_rows))+metric('Cosenza — iscritte/listed',fmt(D.cosenza.status_counts.listed))+metric('Edizioni Cosenza censite',fmt(D.history.length)))}${section('COPERTURA DELLE FONTI',metric('Autorità con pagina verificata',fmt(D.national.verified_authorities))+metric('Serie di fonte censite',fmt(D.national.source_series))+metric('Ambiti di registro censiti',fmt(D.national.register_scopes))+metric('Ambiti completi',fmt(D.national.complete_scopes)))}</div>`+
  section('PRINCIPIO DI PUBBLICAZIONE',`<div class="flow">${esc(D.publication.principle.toUpperCase())}\n\n${esc(D.publication.interpretation)}</div>`);
}
function renderHistory(D){
  const rows=[...D.history].reverse().map((r,i)=>`<tr><td class="mono">${String(D.history.length-i).padStart(2,'0')}</td><td>${esc(r.date)}</td><td><span class="badge ${r.origin==='official_historical'?'warn':'ok'}">${esc(r.origin)}</span></td><td><a href="${esc(r.page_url)}" target="_blank" rel="noopener">Fonte ufficiale</a></td></tr>`).join('');
  $('#view-history').innerHTML=section('SERIE STORICA COSENZA',`<div class="note">Le edizioni restano distinte e non vengono sovrascritte. Il registro principale mostra l’ultima edizione approvata; questa sezione conserva il percorso storico delle fonti.</div><div class="gridwrap"><table class="grid"><thead><tr><th>#</th><th>Data di riferimento</th><th>Origine</th><th>Pagina</th></tr></thead><tbody>${rows}</tbody></table></div>`);
}
function renderCoverage(D){
  const missing=D.national.incomplete_scope_names.map(x=>`<tr><td>${esc(x)}</td><td><span class="badge warn">incompleto</span></td></tr>`).join('');
  $('#view-coverage').innerHTML=section('COPERTURA NAZIONALE DELLE FONTI',`<div class="split"><div>${metric('Autorità con pagina primaria verificata',fmt(D.national.verified_authorities))+metric('Serie di fonte censite',fmt(D.national.source_series))+metric('Ambiti di registro censiti',fmt(D.national.register_scopes))}</div><div>${metric('Ambiti con popolazione completa',fmt(D.national.complete_scopes))+metric('Ambiti ancora incompleti',fmt(D.national.incomplete_scopes))+metric('Registri entity-level pubblicati',fmt(D.national.published_entity_registers.length))}</div></div>`)+section('AMBITI ANCORA INCOMPLETI',`<table class="summary"><thead><tr><th>Prefettura</th><th>Stato</th></tr></thead><tbody>${missing}</tbody></table><div class="footer-note">La copertura source-discovery è distinta dalla disponibilità di record entity-level nel registro pubblico.</div>`);
}
function renderQuality(D){
  const q=D.quality;
  const classes=q.classes.map(r=>`<tr><td class="mono">${esc(r.class)}</td><td class="num">${fmt(r.sample)}</td><td class="num">${fmt(r.correct)}</td><td class="num">${pct(r.precision_pct)}</td><td>${esc(r.public_interpretation)}</td></tr>`).join('');
  $('#view-quality').innerHTML=section('VALIDAZIONE INDIRIZZI — COSENZA',`<div class="note"><b>Metriche locali, non performance nazionali.</b> I <code>not_found</code> incidono su copertura/yield, non sulla precisione dei match restituiti.</div><div class="split"><div>${metric('Indirizzi canonici',fmt(q.address_population))+metric('Candidati ANNCSU',fmt(q.anncsu_candidates))+metric('Not found',fmt(q.not_found))+metric('Candidate coverage',pct(q.candidate_coverage_pct))}</div><div>${metric('Precisione pesata candidati',pct(q.candidate_weighted_precision_pct))+metric('Validated end-to-end yield',pct(q.estimated_validated_yield_pct))+metric('Auto-accepted',fmt(q.auto_accepted))}</div></div>`)+section('PRECISIONE PER CLASSE',`<div class="gridwrap"><table class="grid"><thead><tr><th>Classe</th><th>Campione</th><th>Corretti</th><th>Precisione osservata</th><th>Interpretazione</th></tr></thead><tbody>${classes}</tbody></table></div>`);
}
function renderMethod(D){
  const flow=D.method.flow.map((x,i)=>`${String(i+1).padStart(2,'0')}  ${x}`).join('\n   ↓\n');
  $('#view-method').innerHTML=section('PIPELINE',`<div class="flow">${esc(flow)}</div>`)+section('PRINCIPI',`<table class="summary"><tr><th>Fonte</th><td>Il dato osservato viene preservato e versionato prima dell’interpretazione.</td></tr><tr><th>Registro</th><td>La vista pubblica espone gli attributi source-supported utili alla consultazione.</td></tr><tr><th>Canonicalizzazione</th><td>La futura identità canonica nazionale resta distinta dalle righe di fonte.</td></tr><tr><th>Geografia</th><td>I risultati ANNCSU sono candidate-by-default finché non esiste una policy validata.</td></tr><tr><th>Audit</th><td>Codice, validation e decisioni architetturali rimangono pubblicamente ispezionabili.</td></tr></table>`);
}
function renderAudit(D){
  const r=REGISTRY?.meta;
  $('#view-audit').innerHTML=section('AUDIT PUBBLICO',`<div class="note">Il livello di audit non è nascosto: è un secondo livello di lettura del registro. Serve a verificare come una pubblicazione ufficiale diventa una riga interrogabile.</div><table class="summary"><tr><th>Repository</th><td><a href="${esc(D.audit.repository_url)}" target="_blank" rel="noopener">Codice e storia Git</a></td></tr><tr><th>Explorer tecnico</th><td><a href="${esc(D.audit.explorer_source_url)}" target="_blank" rel="noopener">Sorgenti Explorer</a></td></tr><tr><th>Parser Cosenza</th><td><a href="${esc(D.audit.parser_url)}" target="_blank" rel="noopener">Codice parser</a></td></tr><tr><th>Validazione geocoding</th><td><a href="${esc(D.audit.validation_url)}" target="_blank" rel="noopener">Gold standard e risultati</a></td></tr><tr><th>Architettura</th><td><a href="${esc(D.audit.architecture_url)}" target="_blank" rel="noopener">Documentazione</a></td></tr><tr><th>Issue tracker</th><td><a href="${esc(D.audit.issues_url)}" target="_blank" rel="noopener">Lavoro aperto</a></td></tr>${r?`<tr><th>Parser build corrente</th><td class="mono">${esc(r.parser_name)} ${esc(r.parser_version)}</td></tr><tr><th>Capture corrente</th><td class="mono">${esc(r.capture_sha256)}</td></tr>`:''}</table>`)+section('CATENA DI EVIDENZA',`<div class="flow">SOURCE PAGE\n  ↓\nPDF / CONTENT SHA-256\n  ↓\nVERSIONED PARSER\n  ↓\nSOURCE RECORD LOCATOR\n  ↓\nPUBLIC REGISTER ROW\n  ↓\nCANONICAL / GEO / VALIDATION LAYERS (quando applicabili)</div>`);
}
function renderSources(D){
  const rows=D.sources.map(s=>`<tr><td><b>${esc(s.name)}</b></td><td>${esc(s.role)}</td><td><a href="${esc(s.url)}" target="_blank" rel="noopener">Apri</a></td></tr>`).join('');
  $('#view-sources').innerHTML=section('FONTI PRIMARIE E DI SUPPORTO',`<div class="gridwrap"><table class="grid"><thead><tr><th>Fonte</th><th>Ruolo</th><th>Link</th></tr></thead><tbody>${rows}</tbody></table></div>`)+section('NOTA',`<div class="note">Il portale non sostituisce le pubblicazioni ufficiali. Link, hash e metadati rendono verificabile la provenienza delle osservazioni.</div>`);
}
async function getJson(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok)throw new Error(`${path}: HTTP ${r.status}`);return r.json()}
async function main(){
  try{
    SITE=await getJson('./data/site.json');
    try{REGISTRY=await getJson('./data/registry.json')}catch(err){console.error(err);REGISTRY=null}
    drawRegistry();renderOverview(SITE);renderHistory(SITE);renderCoverage(SITE);renderQuality(SITE);renderMethod(SITE);renderAudit(SITE);renderSources(SITE);
    $('#status').textContent=REGISTRY?'Pronto · registro pubblico v2':'Configurazione caricata · registro non disponibile';
    $('#asof').textContent='Dati al '+SITE.meta.data_as_of;
    $$('.tab').forEach(t=>t.addEventListener('click',()=>activate(t.dataset.view)));
    $('#detail-close').addEventListener('click',closeDetail);
    document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail()});
  }catch(err){
    $('#status').textContent='Errore caricamento dati';
    $('#view-registry').innerHTML=`<div class="note bad"><b>Impossibile caricare il portale.</b><br>${esc(err.message)}</div>`;
  }
}
main();

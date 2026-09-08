const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const fmt=n=>new Intl.NumberFormat('it-IT').format(Number(n||0));
const pct=n=>`${Number(n).toFixed(2).replace('.',',')}%`;
const section=(title,body)=>`<div class="section"><div class="section-title">${esc(title)}</div><div class="section-body">${body}</div></div>`;
const metric=(label,value)=>`<div class="metricline"><span>${esc(label)}</span><span class="value">${esc(value)}</span></div>`;
const STATUS={
  listed:'Iscritta',
  pending:'In istruttoria',
  renewal_update_in_progress:'Aggiornamento in corso',
  renewal_requested:'Rinnovo richiesto',
  expired_observed:'Scadenza osservata',
  rejected_or_denied:'Diniego / rigetto',
  cancellation_related:'Cancellazione / cessazione',
  other_or_unknown:'Altro / non classificato'
};
const MAP_STATUS={published:'Dati pubblicati',source_mapped:'Fonte mappata',discovered:'Da mappare'};
const registryState={query:'',status:'listed',authority:'all',register:'all',page:1,size:50};
const prefectureState={query:'',status:'all',page:1,size:50};
let SITE=null;
let REGISTRY=null;
let PREFECTURES=null;

function activate(name){
  $$('.tab').forEach(x=>x.classList.toggle('active',x.dataset.view===name));
  $$('.view').forEach(x=>x.classList.toggle('active',x.id===`view-${name}`));
  $('#rowstatus').textContent='';
  if(name==='registry')drawRegistry();
  if(name==='prefectures')drawPrefectures();
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
  const cls=status==='listed'?'ok':status==='pending'?'warn':status==='rejected_or_denied'?'bad':'';
  return `<span class="badge ${cls}">${esc(STATUS[status]||status)}</span>`;
}
function mapBadge(status){
  const cls=status==='published'?'ok':status==='source_mapped'?'warn':'';
  return `<span class="badge ${cls}">${esc(MAP_STATUS[status]||status)}</span>`;
}
function uniqueOptions(rows,key,labelKey){
  const m=new Map();
  rows.forEach(r=>{if(r[key])m.set(r[key],r[labelKey]||r[key])});
  return [...m.entries()].sort((a,b)=>String(a[1]).localeCompare(String(b[1]),'it'));
}
function option(value,label,current){return `<option value="${esc(value)}" ${current===value?'selected':''}>${esc(label)}</option>`}

function registryBaseRows(){
  if(!REGISTRY)return [];
  return REGISTRY.records.filter(r=>{
    if(registryState.authority!=='all'&&r.authority_key!==registryState.authority)return false;
    if(registryState.register!=='all'&&r.register_key!==registryState.register)return false;
    return true;
  });
}
function registryRows(){
  const q=registryState.query.trim().toLocaleLowerCase('it');
  return registryBaseRows().filter(r=>{
    if(registryState.status!=='all'&&r.source_status!==registryState.status)return false;
    if(!q)return true;
    const hay=[
      r.name,r.registered_office,r.secondary_office,r.identifier_field_raw,
      listText(r.identifiers),listText(r.requested_activities),r.requested_activities_raw,
      r.outcome_raw,r.authority_name,r.register_name,r.record_locator,
      r.primary_date,r.application_date,r.observed_listing_date,r.decision_date,
      r.registration_date,r.observed_expiry_date
    ].join(' ').toLocaleLowerCase('it');
    return hay.includes(q);
  }).sort((a,b)=>String(a.name).localeCompare(String(b.name),'it')||String(a.authority_name).localeCompare(String(b.authority_name),'it'));
}
function sourceDate(r){
  const value=r.primary_date||r.observed_listing_date||r.application_date||r.decision_date||r.registration_date||'';
  const label=r.primary_date_label||'';
  return value?`<span class="nowrap">${esc(value)}</span>${label?`<div class="muted small">${esc(label)}</div>`:''}`:'—';
}
function drawRegistry(){
  if(!REGISTRY){
    $('#view-registry').innerHTML='<div class="note bad"><b>Registro non disponibile.</b> L’export source-backed non è stato prodotto dal deploy.</div>';
    return;
  }
  const authorities=uniqueOptions(REGISTRY.records,'authority_key','authority_name');
  const availableRegisters=uniqueOptions(
    REGISTRY.records.filter(r=>registryState.authority==='all'||r.authority_key===registryState.authority),
    'register_key','register_name'
  );
  if(registryState.register!=='all'&&!availableRegisters.some(([key])=>key===registryState.register))registryState.register='all';
  const base=registryBaseRows();
  const counts=base.reduce((acc,r)=>(acc[r.source_status]=(acc[r.source_status]||0)+1,acc),{});
  const all=registryRows();
  const pages=Math.max(1,Math.ceil(all.length/registryState.size));
  registryState.page=Math.min(registryState.page,pages);
  const start=(registryState.page-1)*registryState.size;
  const shown=all.slice(start,start+registryState.size);
  $('#rowstatus').textContent=`${fmt(all.length)} righe filtrate`;
  const rows=shown.map(r=>`<tr class="clickrow" data-record="${esc(r.record_locator)}" tabindex="0">
    <td><b>${esc(r.name)}</b></td>
    <td class="mono">${esc(listText(r.identifiers)||r.identifier_field_raw)}</td>
    <td>${badge(r.source_status)}</td>
    <td>${esc(r.authority_name)}</td>
    <td>${esc(r.register_name)}</td>
    <td>${esc(listText(r.requested_activities)||r.requested_activities_raw)}</td>
    <td>${esc(r.registered_office)}</td>
    <td>${sourceDate(r)}</td>
    <td class="nowrap">${esc(r.observed_expiry_date||'—')}</td>
  </tr>`).join('');
  const statusOptions=[
    ['listed','Iscritte / listed'],['pending','In istruttoria'],
    ['renewal_update_in_progress','Aggiornamento in corso'],['renewal_requested','Rinnovo richiesto'],
    ['expired_observed','Scadenza osservata'],['rejected_or_denied','Diniego / rigetto'],
    ['cancellation_related','Cancellazione / cessazione'],['other_or_unknown','Altro / non classificato']
  ].filter(([key])=>counts[key]).map(([key,label])=>option(key,`${label} (${fmt(counts[key])})`,registryState.status)).join('');
  $('#view-registry').innerHTML=
    `<div class="public-banner">REGISTRO NAZIONALE PILOTA · ${fmt(REGISTRY.meta.authority_count)} Prefetture · ${fmt(REGISTRY.meta.register_count)} registri · ${fmt(REGISTRY.meta.record_count)} osservazioni pubblicate</div>`+
    section('RICERCA NEL REGISTRO',`<div class="toolbar">
      <label for="reg-q">Cerca</label><input id="reg-q" type="search" value="${esc(registryState.query)}" placeholder="Ragione sociale, CF/P.IVA, sede, attività…">
      <label for="reg-authority">Prefettura</label><select id="reg-authority">${option('all','Tutte',registryState.authority)}${authorities.map(([k,v])=>option(k,v,registryState.authority)).join('')}</select>
      <label for="reg-register">Registro</label><select id="reg-register">${option('all','Tutti',registryState.register)}${availableRegisters.map(([k,v])=>option(k,v,registryState.register)).join('')}</select>
      <label for="reg-status">Stato</label><select id="reg-status">${statusOptions}${option('all',`Tutti gli stati (${fmt(base.length)})`,registryState.status)}</select>
      <label for="reg-size">Righe</label><select id="reg-size">${[25,50,100].map(n=>option(String(n),String(n),String(registryState.size))).join('')}</select>
      <a class="btn linkbtn" href="data/registry.csv" download>CSV</a><a class="btn linkbtn" href="data/registry.json" download>JSON</a>
    </div><div class="note"><b>Vista predefinita:</b> osservazioni che le fonti classificano come iscritte/listed. La stessa Prefettura può gestire più registri: Bologna, per esempio, espone il registro provinciale e quello post-sisma. La pubblicazione non attende la geolocalizzazione.</div>`)+
    section(`REGISTRO — ${fmt(all.length)} RISULTATI`,`<div class="gridwrap registry-grid"><table class="grid"><thead><tr><th>Ragione sociale</th><th>CF / P.IVA</th><th>Stato</th><th>Prefettura</th><th>Registro</th><th>Attività / settori</th><th>Sede pubblicata</th><th>Data fonte</th><th>Scadenza osservata</th></tr></thead><tbody>${rows||'<tr><td colspan="9">Nessun risultato.</td></tr>'}</tbody></table></div><div class="pager"><button class="btn" id="prev" ${registryState.page<=1?'disabled':''}>◀ Precedente</button><span>Pagina ${registryState.page} / ${pages}</span><button class="btn" id="next" ${registryState.page>=pages?'disabled':''}>Successiva ▶</button></div>`);
  $('#reg-q').addEventListener('input',e=>{registryState.query=e.target.value;registryState.page=1;drawRegistry()});
  $('#reg-authority').addEventListener('change',e=>{registryState.authority=e.target.value;registryState.register='all';registryState.page=1;drawRegistry()});
  $('#reg-register').addEventListener('change',e=>{registryState.register=e.target.value;registryState.page=1;drawRegistry()});
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
function dateDetail(label,value){return value?`<div>${esc(label)}</div><div>${esc(value)}</div>`:''}
function openDetail(locator){
  const r=REGISTRY?.records.find(x=>x.record_locator===locator);
  if(!r)return;
  $('#detail-title').textContent=r.name||'Dettaglio osservazione';
  const id=listText(r.identifiers)||r.identifier_field_raw||'—';
  const acts=listText(r.requested_activities)||r.requested_activities_raw||'—';
  $('#detail-body').innerHTML=`<div class="note"><b>Record source-backed.</b> Il locator identifica la specifica osservazione pubblicata; non implica da solo una identità canonica nazionale.</div>
    <div class="kv"><div>Ragione sociale</div><div><b>${esc(r.name)}</b></div><div>Stato</div><div>${badge(r.source_status)}</div><div>Prefettura</div><div>${esc(r.authority_name)}</div><div>Registro</div><div>${esc(r.register_name)}</div><div>Edizione / riferimento</div><div>${esc(r.reference_date)}</div><div>Locator pubblico</div><div class="mono">${esc(r.record_locator)}</div><div>Riga sorgente</div><div class="mono">${esc(r.source_row_ordinal)}</div><div>Sede pubblicata</div><div>${esc(r.registered_office||'—')}</div><div>Sede secondaria</div><div>${esc(r.secondary_office||'—')}</div><div>CF / P.IVA</div><div class="mono">${esc(id)}</div><div>Attività / settori</div><div>${esc(acts)}</div>${dateDetail('Data presentazione istanza',r.application_date)}${dateDetail('Data inserimento osservata',r.observed_listing_date)}${dateDetail('Data provvedimento',r.decision_date)}${dateDetail('Data registrazione',r.registration_date)}${dateDetail('Scadenza osservata',r.observed_expiry_date)}</div>
    ${section('ESITO / ANNOTAZIONE COME PUBBLICATA',`<div class="raw">${esc(r.outcome_raw||'—')}</div>`)}
    ${r.source_fields&&Object.keys(r.source_fields).length?section('CAMPI SPECIFICI DELLA FONTE',`<div class="raw">${esc(JSON.stringify(r.source_fields,null,2))}</div>`):''}
    ${section('PROVENANCE',`<table class="summary"><tr><th>Pagina ufficiale</th><td><a href="${esc(r.source_page_url)}" target="_blank" rel="noopener">Apri pagina</a></td></tr><tr><th>Risorsa ufficiale</th><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Apri documento</a></td></tr><tr><th>Capture SHA-256</th><td class="mono">${esc(r.capture_sha256)}</td></tr><tr><th>Parser</th><td class="mono">${esc(r.parser_name)} ${esc(r.parser_version||'')}</td></tr><tr><th>Audit tecnico</th><td><a href="${esc(SITE.audit.repository_url)}" target="_blank" rel="noopener">Repository</a> · <a href="${esc(SITE.audit.parser_url)}" target="_blank" rel="noopener">Parser</a></td></tr></table>`)}`;
  $('#detail').classList.add('open');
  $('#detail').setAttribute('aria-hidden','false');
}
function closeDetail(){
  $('#detail').classList.remove('open');
  $('#detail').setAttribute('aria-hidden','true');
}

function prefectureRows(){
  if(!PREFECTURES)return [];
  const q=prefectureState.query.trim().toLocaleLowerCase('it');
  return PREFECTURES.prefectures.filter(r=>{
    if(prefectureState.status!=='all'&&r.mapping_status!==prefectureState.status)return false;
    if(!q)return true;
    return [r.jurisdiction_name,r.authority_key,(r.publication_models||[]).join(' '),(r.published_registers||[]).join(' ')].join(' ').toLocaleLowerCase('it').includes(q);
  });
}
function drawPrefectures(){
  if(!PREFECTURES){$('#view-prefectures').innerHTML='<div class="note bad">Indice Prefetture non disponibile.</div>';return}
  const all=prefectureRows();
  const pages=Math.max(1,Math.ceil(all.length/prefectureState.size));
  prefectureState.page=Math.min(prefectureState.page,pages);
  const shown=all.slice((prefectureState.page-1)*prefectureState.size,prefectureState.page*prefectureState.size);
  $('#rowstatus').textContent=`${fmt(all.length)} Prefetture / autorità`;
  const rows=shown.map(r=>{
    const url=r.verified_primary_page||(r.official_white_list_urls||[])[0]||'';
    const mapped=r.mapped?'Sì':'No';
    return `<tr><td><b>${esc(r.jurisdiction_name)}</b></td><td>${mapBadge(r.mapping_status)}</td><td>${mapped}</td><td class="num">${fmt(r.series_count)}</td><td>${esc((r.publication_models||[]).join(' · ')||'—')}</td><td>${esc((r.published_registers||[]).join(' · ')||'—')}</td><td class="nowrap">${esc(r.last_project_check||'—')}</td><td class="nowrap">${esc(r.last_source_update||'—')}</td><td>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">Fonte ufficiale</a>`:'—'}</td></tr>`;
  }).join('');
  const c=PREFECTURES.meta.status_counts||{};
  $('#view-prefectures').innerHTML=`<div class="public-banner">INDICE NAZIONALE PREFETTURE · ${fmt(PREFECTURES.meta.authority_count)} autorità/jurisdizioni · ${fmt(PREFECTURES.meta.mapped_count)} fonti mappate · ${fmt(PREFECTURES.meta.published_count)} con dati pubblicati</div>`+
    section('STATO DI MAPPATURA',`<div class="toolbar"><label for="pref-q">Cerca</label><input id="pref-q" type="search" value="${esc(prefectureState.query)}" placeholder="Prefettura / provincia…"><label for="pref-status">Stato</label><select id="pref-status">${option('all',`Tutte (${fmt(PREFECTURES.meta.authority_count)})`,prefectureState.status)}${option('published',`Dati pubblicati (${fmt(c.published)})`,prefectureState.status)}${option('source_mapped',`Fonte mappata (${fmt(c.source_mapped)})`,prefectureState.status)}${option('discovered',`Da mappare (${fmt(c.discovered)})`,prefectureState.status)}</select><a class="btn linkbtn" href="data/prefectures.csv" download>CSV</a><a class="btn linkbtn" href="data/prefectures.json" download>JSON</a></div><div class="note"><b>Ultimo controllo del progetto</b> indica quando abbiamo verificato/mappato la fonte. <b>Ultimo aggiornamento della fonte</b> indica la data dichiarata o dedotta con evidenza dalla pubblicazione ufficiale; se non è ancora stata registrata viene mostrato “—”.</div>`)+
    section(`PREFETTURE — ${fmt(all.length)} RISULTATI`,`<div class="gridwrap"><table class="grid prefecture-grid"><thead><tr><th>Prefettura / giurisdizione</th><th>Stato</th><th>Mappata</th><th>Serie</th><th>Modello pubblicazione</th><th>Registri pubblicati</th><th>Ultimo controllo progetto</th><th>Ultimo aggiornamento fonte</th><th>Fonte</th></tr></thead><tbody>${rows}</tbody></table></div><div class="pager"><button class="btn" id="pref-prev" ${prefectureState.page<=1?'disabled':''}>◀ Precedente</button><span>Pagina ${prefectureState.page} / ${pages}</span><button class="btn" id="pref-next" ${prefectureState.page>=pages?'disabled':''}>Successiva ▶</button></div>`);
  $('#pref-q').addEventListener('input',e=>{prefectureState.query=e.target.value;prefectureState.page=1;drawPrefectures()});
  $('#pref-status').addEventListener('change',e=>{prefectureState.status=e.target.value;prefectureState.page=1;drawPrefectures()});
  $('#pref-prev')?.addEventListener('click',()=>{prefectureState.page--;drawPrefectures()});
  $('#pref-next')?.addEventListener('click',()=>{prefectureState.page++;drawPrefectures()});
}

function renderOverview(D){
  $('#view-overview').innerHTML=`<div class="public-banner">${esc(D.meta.classification)} · build ${esc(D.meta.portal_build_date)}</div>`+
  section('ARCHIVIO PUBBLICO',`<p><b>${esc(D.meta.title)}</b> rende interrogabili White List antimafia eterogenee attraverso un contratto pubblico comune, preservando sempre la fonte originale.</p><div class="note">${esc(D.meta.disclaimer)}</div>`)+
  `<div class="split">${section('REGISTRO PUBBLICATO',metric('Prefetture pubblicate',fmt(REGISTRY?.meta.authority_count))+metric('Registri pubblicati',fmt(REGISTRY?.meta.register_count))+metric('Osservazioni pubbliche',fmt(REGISTRY?.meta.record_count))+metric('Fonti/versioni correnti',fmt(REGISTRY?.meta.source_count)))}${section('COPERTURA NAZIONALE',metric('Autorità nell’indice nazionale',fmt(PREFECTURES?.meta.authority_count))+metric('Fonti mappate',fmt(PREFECTURES?.meta.mapped_count))+metric('Con dati pubblicati',fmt(PREFECTURES?.meta.published_count))+metric('Serie di fonte censite',fmt(D.national.source_series)))}</div>`+
  section('PRINCIPIO DI PUBBLICAZIONE',`<div class="flow">${esc(D.publication.principle.toUpperCase())}\n\n${esc(D.publication.interpretation)}\n\nGEO: ${esc(D.publication.geography_policy)}</div>`);
}
function renderHistory(D){
  const rows=[...D.history].reverse().map((r,i)=>`<tr><td class="mono">${String(D.history.length-i).padStart(2,'0')}</td><td>${esc(r.date)}</td><td><span class="badge ${r.origin==='official_historical'?'warn':'ok'}">${esc(r.origin)}</span></td><td><a href="${esc(r.page_url)}" target="_blank" rel="noopener">Fonte ufficiale</a></td></tr>`).join('');
  $('#view-history').innerHTML=section('SERIE STORICA — PILOTA COSENZA',`<div class="note">Cosenza è il primo registro con recupero storico profondo. Parma, Pistoia e Bologna entrano inizialmente con la loro edizione corrente approvata; lo storico verrà esteso senza sovrascrivere le edizioni esistenti.</div><div class="gridwrap"><table class="grid"><thead><tr><th>#</th><th>Data di riferimento</th><th>Origine</th><th>Pagina</th></tr></thead><tbody>${rows}</tbody></table></div>`);
}
function renderCoverage(D){
  const missing=D.national.incomplete_scope_names.map(x=>`<tr><td>${esc(x)}</td><td><span class="badge warn">scope ancora incompleto</span></td></tr>`).join('');
  $('#view-coverage').innerHTML=section('COPERTURA NAZIONALE',`<div class="split"><div>${metric('Autorità indice nazionale',fmt(PREFECTURES?.meta.authority_count))+metric('Fonti primarie mappate',fmt(PREFECTURES?.meta.mapped_count))+metric('Prefetture pubblicate',fmt(PREFECTURES?.meta.published_count))}</div><div>${metric('Serie di fonte censite',fmt(D.national.source_series))+metric('Ambiti di registro censiti',fmt(D.national.register_scopes))+metric('Ambiti completi',fmt(D.national.complete_scopes))}</div></div>`)+section('AMBITI DELLA DUE DILIGENCE ANCORA INCOMPLETI',`<table class="summary"><thead><tr><th>Prefettura</th><th>Stato</th></tr></thead><tbody>${missing}</tbody></table><div class="footer-note">“Fonte mappata” nella pagina Prefetture e “scope completo” nella due diligence del registro sono misure diverse.</div>`);
}
function renderQuality(D){
  const q=D.quality;
  const classes=q.classes.map(r=>`<tr><td class="mono">${esc(r.class)}</td><td class="num">${fmt(r.sample)}</td><td class="num">${fmt(r.correct)}</td><td class="num">${pct(r.precision_pct)}</td><td>${esc(r.public_interpretation)}</td></tr>`).join('');
  $('#view-quality').innerHTML=section('VALIDAZIONE GEOGRAFICA — COSENZA',`<div class="note"><b>Arricchimento opzionale.</b> Queste metriche descrivono il benchmark geografico di Cosenza e non bloccano la pubblicazione del registro. I <code>not_found</code> incidono su copertura/yield, non sulla precisione dei match restituiti.</div><div class="split"><div>${metric('Indirizzi canonici',fmt(q.address_population))+metric('Candidati ANNCSU',fmt(q.anncsu_candidates))+metric('Not found',fmt(q.not_found))+metric('Candidate coverage',pct(q.candidate_coverage_pct))}</div><div>${metric('Precisione pesata candidati',pct(q.candidate_weighted_precision_pct))+metric('Validated end-to-end yield',pct(q.estimated_validated_yield_pct))+metric('Auto-accepted',fmt(q.auto_accepted))}</div></div>`)+section('PRECISIONE PER CLASSE',`<div class="gridwrap"><table class="grid"><thead><tr><th>Classe</th><th>Campione</th><th>Corretti</th><th>Precisione</th><th>Interpretazione</th></tr></thead><tbody>${classes}</tbody></table></div>`);
}
function renderMethod(D){
  const core=D.method.core_flow.map((x,i)=>`${String(i+1).padStart(2,'0')}  ${x}`).join('\n   ↓\n');
  const geo=D.method.geo_flow.map((x,i)=>`${String(i+1).padStart(2,'0')}  ${x}`).join('\n   ↓\n');
  $('#view-method').innerHTML=section('PIPELINE CORE — BLOCCA / ABILITA LA PUBBLICAZIONE',`<div class="flow">${esc(core)}</div>`)+section('RAMO GEO — OPZIONALE E INCREMENTALE',`<div class="flow">${esc(geo)}</div><div class="note">${esc(D.method.publication_rule)}</div>`)+section('UNITÀ E MODELLAZIONE',`<table class="summary"><tr><th>Authority</th><td>Prefettura/autorità che gestisce uno o più registri.</td></tr><tr><th>Register</th><td>Registro amministrativo specifico; Bologna dimostra che una Prefettura può averne più di uno.</td></tr><tr><th>Public observation</th><td>Osservazione source-backed dell'edizione corrente; le ripetizioni puramente per settore possono essere aggregate per leggibilità.</td></tr><tr><th>LegalEntity</th><td>Livello canonico nazionale distinto, che non viene affermato quando la sola fonte non basta.</td></tr></table>`);
}
function renderAudit(D){
  $('#view-audit').innerHTML=section('AUDIT PUBBLICO',`<div class="note">Il registro è public-first, ma il percorso tecnico resta ispezionabile. Dai record si può risalire a fonte, SHA, parser e codice.</div><table class="summary"><tr><th>Repository e Git history</th><td><a href="${esc(D.audit.repository_url)}" target="_blank" rel="noopener">Apri repository</a></td></tr><tr><th>Dataset Explorer</th><td><a href="${esc(D.audit.explorer_source_url)}" target="_blank" rel="noopener">Codice Explorer</a></td></tr><tr><th>Parser source-specific</th><td><a href="${esc(D.audit.parser_url)}" target="_blank" rel="noopener">Apri parser</a></td></tr><tr><th>Architettura</th><td><a href="${esc(D.audit.architecture_url)}" target="_blank" rel="noopener">Documentazione</a></td></tr><tr><th>Gold standard geografia</th><td><a href="${esc(D.audit.validation_url)}" target="_blank" rel="noopener">Validazione Cosenza</a></td></tr><tr><th>Issue tracker</th><td><a href="${esc(D.audit.issues_url)}" target="_blank" rel="noopener">Issue aperte</a></td></tr></table>`);
}
function renderSources(D){
  const rows=D.sources.map(s=>`<tr><td><b>${esc(s.name)}</b></td><td>${esc(s.role)}</td><td><a href="${esc(s.url)}" target="_blank" rel="noopener">Apri</a></td></tr>`).join('');
  $('#view-sources').innerHTML=section('FONTI PRIMARIE E DI SUPPORTO',`<div class="gridwrap"><table class="grid"><thead><tr><th>Fonte</th><th>Ruolo</th><th>Link</th></tr></thead><tbody>${rows}</tbody></table></div>`)+section('NOTA',`<div class="note">Il portale non sostituisce le pubblicazioni ufficiali. URL, hash, date e parser servono a rendere verificabile la trasformazione della fonte in registro interrogabile.</div>`);
}

async function fetchJson(path){
  const response=await fetch(path,{cache:'no-store'});
  if(!response.ok)throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}
async function main(){
  try{
    [SITE,REGISTRY,PREFECTURES]=await Promise.all([
      fetchJson('./data/site.json'),fetchJson('./data/registry.json'),fetchJson('./data/prefectures.json')
    ]);
    drawRegistry();drawPrefectures();renderOverview(SITE);renderHistory(SITE);renderCoverage(SITE);renderQuality(SITE);renderMethod(SITE);renderAudit(SITE);renderSources(SITE);
    $('#status').textContent=`Pronto · contratto pubblico v${REGISTRY.meta.contract_version}`;
    $('#asof').textContent=`${fmt(REGISTRY.meta.authority_count)} Prefetture · ${fmt(REGISTRY.meta.register_count)} registri`;
    $$('.tab').forEach(t=>t.addEventListener('click',()=>activate(t.dataset.view)));
    $('#detail-close').addEventListener('click',closeDetail);
    document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail()});
  }catch(err){
    $('#status').textContent='Errore caricamento dati';
    $('#view-registry').innerHTML=`<div class="note bad"><b>Impossibile caricare il registro pubblico.</b><br>${esc(err.message)}</div>`;
  }
}
main();

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
const MAP_STATUS={published:'Dati pubblicati',source_mapped:'Fonte individuata',discovered:'Dati non ancora disponibili'};
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
    $('#view-registry').innerHTML='<div class="note bad"><b>Registro non disponibile.</b> I dati non sono disponibili. Riprova più tardi.</div>';
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
    ['listed','Iscritte'],['pending','In istruttoria'],
    ['renewal_update_in_progress','Aggiornamento in corso'],['renewal_requested','Rinnovo richiesto'],
    ['expired_observed','Scadenza osservata'],['rejected_or_denied','Diniego / rigetto'],
    ['cancellation_related','Cancellazione / cessazione'],['other_or_unknown','Altro / non classificato']
  ].filter(([key])=>counts[key]).map(([key,label])=>option(key,`${label} (${fmt(counts[key])})`,registryState.status)).join('');
  $('#view-registry').innerHTML=
    `<div class="public-banner">${fmt(archiveSummary(REGISTRY,PREFECTURES).authorities)} Prefetture con dati pubblicati · ${fmt(REGISTRY.records.length)} presenze negli elenchi · Edizione più recente disponibile: ${esc(archiveSummary(REGISTRY,PREFECTURES).latest)}</div>`+
    `<p>Questo archivio raccoglie gli elenchi White List pubblicati dalle Prefetture. Cerca un’impresa e apri la sua scheda per consultare l’elenco ufficiale.</p><p><b>Territorio coperto:</b> ${authorities.map(([,name])=>esc(name)).join(' · ')}.</p>`+
    section('RICERCA NEL REGISTRO',`<div class="toolbar">
      <label for="reg-q">Cerca</label><input id="reg-q" type="search" value="${esc(registryState.query)}" placeholder="Ragione sociale, CF/P.IVA, sede, attività…">
      <label for="reg-authority">Prefettura</label><select id="reg-authority">${option('all','Tutte',registryState.authority)}${authorities.map(([k,v])=>option(k,v,registryState.authority)).join('')}</select>
      <label for="reg-register">Registro</label><select id="reg-register">${option('all','Tutti',registryState.register)}${availableRegisters.map(([k,v])=>option(k,v,registryState.register)).join('')}</select>
      <label for="reg-status">Stato</label><select id="reg-status">${statusOptions}${option('all',`Tutti gli stati (${fmt(base.length)})`,registryState.status)}</select>
      <label for="reg-size">Righe</label><select id="reg-size">${[25,50,100].map(n=>option(String(n),String(n),String(registryState.size))).join('')}</select>
      <a class="btn linkbtn" href="data/registry.csv" download>CSV</a><a class="btn linkbtn" href="data/registry.json" download>JSON</a>
    </div><div class="note"><b>Vista predefinita:</b> presenze classificate come iscritte negli elenchi consultati. Usa il filtro Stato per vedere anche le domande e gli altri esiti. La stessa impresa può comparire in più registri: il totale non indica imprese distinte in Italia. Le date di riferimento sono nella scheda; il portale non certifica lo stato attuale dell’impresa.</div>`)+
    section(`REGISTRO — ${fmt(all.length)} RISULTATI`,`<div class="gridwrap registry-grid"><table class="grid"><thead><tr><th>Ragione sociale</th><th>CF / P.IVA</th><th>Stato</th><th>Prefettura</th><th>Registro</th><th>Attività / settori</th><th>Sede pubblicata</th><th>Data riportata per l’impresa</th><th>Scadenza osservata</th></tr></thead><tbody>${rows||'<tr><td colspan="9">Nessun risultato.</td></tr>'}</tbody></table></div><div class="pager"><button class="btn" id="prev" ${registryState.page<=1?'disabled':''}>◀ Precedente</button><span>Pagina ${registryState.page} / ${pages}</span><button class="btn" id="next" ${registryState.page>=pages?'disabled':''}>Successiva ▶</button></div>`);
  $('#reg-q').addEventListener('input',e=>{registryState.query=e.target.value;registryState.page=1;drawRegistry();$('#reg-q').focus()});
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
  $('#detail-body').innerHTML=`<div class="note">Questa scheda descrive la presenza dell’impresa in uno specifico elenco. La stessa impresa può avere altre presenze in registri o edizioni diversi.</div>
    <div class="kv"><div>Ragione sociale</div><div><b>${esc(r.name)}</b></div><div>Stato</div><div>${badge(r.source_status)}</div><div>Prefettura</div><div>${esc(r.authority_name)}</div><div>Registro</div><div>${esc(r.register_name)}</div><div>Edizione / riferimento</div><div>${esc(r.reference_date)}</div><div>Riferimento della scheda</div><div class="mono">${esc(r.record_locator)}</div><div>Riga nell’elenco</div><div class="mono">${esc(r.source_row_ordinal)}</div><div>Sede pubblicata</div><div>${esc(r.registered_office||'—')}</div><div>Sede secondaria</div><div>${esc(r.secondary_office||'—')}</div><div>CF / P.IVA</div><div class="mono">${esc(id)}</div><div>Attività / settori</div><div>${esc(acts)}</div>${dateDetail('Data presentazione istanza',r.application_date)}${dateDetail('Data inserimento osservata',r.observed_listing_date)}${dateDetail('Data provvedimento',r.decision_date)}${dateDetail('Data registrazione',r.registration_date)}${dateDetail('Scadenza osservata',r.observed_expiry_date)}</div>
    ${section('ESITO / ANNOTAZIONE COME PUBBLICATA',`<div class="raw">${esc(r.outcome_raw||'—')}</div>`)}
    ${r.source_fields&&Object.keys(r.source_fields).length?section('CAMPI SPECIFICI DELLA FONTE',`<div class="raw">${esc(JSON.stringify(r.source_fields,null,2))}</div>`):''}
    ${section('FONTE E RIFERIMENTI',`<table class="summary"><tr><th>Pagina ufficiale</th><td><a href="${esc(r.source_page_url)}" target="_blank" rel="noopener">Consulta la pagina ufficiale</a></td></tr><tr><th>Risorsa ufficiale</th><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Consulta l’elenco ufficiale</a></td></tr><tr><th>Impronta del documento (SHA-256)</th><td class="mono">${esc(r.capture_sha256)}</td></tr><tr><th>Parser</th><td class="mono">${esc(r.parser_name)} ${esc(r.parser_version||'')}</td></tr><tr><th>Audit tecnico</th><td><a href="${esc(SITE.audit.repository_url)}" target="_blank" rel="noopener">Repository</a> · <a href="${esc(SITE.audit.parser_url)}" target="_blank" rel="noopener">Parser</a></td></tr></table>`)}`;
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
  $('#rowstatus').textContent=`${fmt(all.length)} autorità nell’indice`;
  const rows=shown.map(r=>{
    const url=r.verified_primary_page||(r.official_white_list_urls||[])[0]||'';
    return `<tr><td><b>${esc(r.jurisdiction_name)}</b></td><td>${mapBadge(r.mapping_status)}</td><td>${esc((r.published_registers||[]).join(' · ')||'—')}</td><td class="nowrap">${esc(r.last_source_update||'Non disponibile')}</td><td class="nowrap">${esc(r.last_project_check||'Non registrata')}</td><td>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">Consulta la fonte ufficiale</a>`:'—'}</td></tr>`;
  }).join('');
  const counts=PREFECTURES.prefectures.reduce((a,r)=>(a[r.mapping_status]=(a[r.mapping_status]||0)+1,a),{});
  $('#view-prefectures').innerHTML=`<div class="public-banner">${fmt(counts.published)} Prefetture con dati pubblicati · ${fmt(PREFECTURES.prefectures.length)} autorità nell’indice del Ministero</div>`+
    section('CERCA UNA PREFETTURA',`<div class="toolbar"><label for="pref-q">Cerca</label><input id="pref-q" type="search" value="${esc(prefectureState.query)}" placeholder="Prefettura / provincia…"><label for="pref-status">Disponibilità</label><select id="pref-status">${option('all',`Tutte (${fmt(PREFECTURES.prefectures.length)})`,prefectureState.status)}${Object.entries(MAP_STATUS).map(([k,v])=>option(k,`${v} (${fmt(counts[k])})`,prefectureState.status)).join('')}</select><a class="btn linkbtn" href="data/prefectures.csv" download>CSV</a><a class="btn linkbtn" href="data/prefectures.json" download>JSON</a></div><div class="note">Una fonte individuata non significa che i dati siano già consultabili nell’archivio. L’edizione disponibile è datata dalla pubblicazione dell’elenco; la verifica della pagina indica quando il progetto ne ha controllato il percorso ufficiale. Nessuna delle due date certifica lo stato attuale di un’impresa.</div>`)+
    section(`PREFETTURE — ${fmt(all.length)} RISULTATI`,`<div class="gridwrap"><table class="grid prefecture-grid"><thead><tr><th>Prefettura / territorio</th><th>Disponibilità</th><th>Registri consultabili</th><th>Ultima edizione disponibile</th><th>Pagina verificata il</th><th>Fonte</th></tr></thead><tbody>${rows}</tbody></table></div><div class="pager"><button class="btn" id="pref-prev" ${prefectureState.page<=1?'disabled':''}>◀ Precedente</button><span>Pagina ${prefectureState.page} / ${pages}</span><button class="btn" id="pref-next" ${prefectureState.page>=pages?'disabled':''}>Successiva ▶</button></div>`);
  $('#pref-q').addEventListener('input',e=>{prefectureState.query=e.target.value;prefectureState.page=1;drawPrefectures();$('#pref-q').focus()});
  $('#pref-status').addEventListener('change',e=>{prefectureState.status=e.target.value;prefectureState.page=1;drawPrefectures()});
  $('#pref-prev')?.addEventListener('click',()=>{prefectureState.page--;drawPrefectures()});
  $('#pref-next')?.addEventListener('click',()=>{prefectureState.page++;drawPrefectures()});
}
function publishedEditions(){
  const editions=new Map();
  REGISTRY.records.forEach(r=>{const key=JSON.stringify([r.source_key,r.reference_date,r.capture_sha256]);if(!editions.has(key))editions.set(key,r)});
  return [...editions.values()].sort((a,b)=>b.reference_date.localeCompare(a.reference_date)||a.authority_name.localeCompare(b.authority_name,'it'));
}
function editionTable(){
  return `<div class="gridwrap"><table class="grid"><thead><tr><th>Prefettura</th><th>Registro</th><th>Data dell’elenco</th><th>Contenuto</th><th>Fonte</th></tr></thead><tbody>${publishedEditions().map(r=>`<tr><td>${esc(r.authority_name)}</td><td>${esc(r.register_name)}</td><td>${esc(r.reference_date)}</td><td>${esc(({listed:'Imprese iscritte',applicant:'Domande di iscrizione',listed_and_applicant:'Iscrizioni e domande',operational_mixed:'Iscrizioni, domande e altri esiti'})[r.population_scope]||'Elenco')}</td><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Consulta l’elenco ufficiale</a></td></tr>`).join('')}</tbody></table></div>`;
}
function renderHistory(D){
  const rows=[...D.history].sort((a,b)=>b.date.localeCompare(a.date)).map(r=>`<tr><td>${esc(r.date)}</td><td>Edizione individuata sul sito ufficiale</td><td><a href="${esc(r.page_url)}" target="_blank" rel="noopener">Consulta la pagina ufficiale</a></td></tr>`).join('');
  $('#view-history').innerHTML=section('EDIZIONI CONSULTABILI NEL REGISTRO',editionTable())+
    section('PAGINE STORICHE INDIVIDUATE — COSENZA',`<p>Le pagine qui indicate documentano la disponibilità di edizioni dal 2024. Questo elenco di collegamenti non garantisce una copia permanentemente conservata né la ricerca delle imprese in tutte le edizioni. La data non indica da quando un’impresa è iscritta.</p><div class="gridwrap"><table class="grid"><thead><tr><th>Data dell’elenco</th><th>Disponibilità</th><th>Fonte</th></tr></thead><tbody>${rows}</tbody></table></div>`);
}
function renderUpdates(){
  const s=archiveSummary(REGISTRY,PREFECTURES);
  $('#view-updates').innerHTML=section('AGGIORNAMENTI DISPONIBILI',metric('Edizione più recente nel registro',s.latest||'Non disponibile')+metric('Ultima verifica completata dei documenti pubblicati',s.documentsCheckedAt||'Non registrata')+`<p>La verifica confronta i documenti pubblicati con le copie approvate. Non dimostra che siano le ultime edizioni presenti oggi sui siti delle Prefetture. Le date delle edizioni possono essere diverse da Prefettura a Prefettura.</p>`)+section('ELENCHI PUBBLICATI, DAL PIÙ RECENTE',editionTable());
}
function renderQuality(D){
  $('#view-quality').innerHTML=section('CONTROLLI E LIMITI',`<p>I controlli verificano che i documenti corrispondano alle copie approvate, che le righe siano lette senza omissioni note e che i dati pubblici rispettino i campi autorizzati.</p><p>La stessa impresa può essere presente in più elenchi. Il numero delle presenze non misura il numero di imprese distinte. Una scadenza riportata o l’assenza da una successiva edizione non dimostrano da sole la perdita dell’iscrizione.</p><p>Le verifiche sulla posizione geografica degli indirizzi sono separate. I risultati del caso Cosenza non dimostrano la qualità dell’intero archivio.</p>`)+section('DOCUMENTAZIONE TECNICA',`<ul><li><a href="${esc(D.audit.validation_url)}" target="_blank" rel="noopener">Verifiche sugli indirizzi di Cosenza: campioni, risultati e limiti</a></li><li><a href="${esc(D.audit.architecture_url)}" target="_blank" rel="noopener">Modello dei dati e conservazione delle fonti</a></li><li><a href="${esc(D.audit.repository_url)}" target="_blank" rel="noopener">Codice e cronologia delle modifiche</a></li></ul>`);
}
function renderMethod(D){
  const sources=new Map();
  REGISTRY.records.forEach(r=>sources.set(r.source_page_url,r.authority_name));
  $('#view-method').innerHTML=section('COME LEGGERE IL REGISTRO',`<p>${esc(D.meta.disclaimer)}</p><p>Ogni riga descrive la presenza di un’impresa in uno specifico elenco. Aprendo la scheda puoi vedere i dati riportati dalla Prefettura, la data dell’edizione e i collegamenti ufficiali. Alcune fonti ripetono l’impresa per ciascuna attività: queste ripetizioni sono riunite solo quando gli altri dati coincidono secondo le regole di lettura della fonte.</p><p>“Iscritta” e “in istruttoria” sono stati diversi. Gli stati visualizzati descrivono gli elenchi alle rispettive date, non certificano la situazione attuale. Un campo vuoto significa che l’informazione non è disponibile nella scheda.</p>`)+
    section('COME RACCOGLIAMO I DATI',`<ol><li>Individuiamo la pagina e gli elenchi pubblicati dall’autorità competente.</li><li>Identifichiamo il documento e la sua data di riferimento, conservando i riferimenti alla fonte.</li><li>Leggiamo le tabelle e controlliamo i risultati prima della pubblicazione.</li><li>Pubblichiamo i campi autorizzati. Le correzioni e le edizioni successive conservano la traccia delle fonti precedenti.</li></ol>`)+
    section('FONTI UFFICIALI DEGLI ELENCHI PUBBLICATI',`<ul><li><a href="${esc(PREFECTURES.meta.national_index_url)}" target="_blank" rel="noopener">Ministero dell’Interno — indice nazionale White List</a></li>${[...sources].map(([url,name])=>`<li><a href="${esc(url)}" target="_blank" rel="noopener">${esc(name)} — pagina degli elenchi</a></li>`).join('')}</ul><p>Per le altre autorità, consulta la sezione Prefetture.</p>`);
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
    drawPrefectures();drawRegistry();renderHistory(SITE);renderUpdates();renderQuality(SITE);renderMethod(SITE);
    $('#status').textContent='Registro caricato';
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

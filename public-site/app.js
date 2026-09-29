const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const fmt=n=>new Intl.NumberFormat('it-IT').format(Number(n||0));
const pct=n=>`${Number(n).toFixed(2).replace('.',',')}%`;
const section=(title,body,id='')=>`<div class="section"><div class="section-title"${id?` id="${esc(id)}" tabindex="-1"`:''}>${esc(title)}</div><div class="section-body">${body}</div></div>`;
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
let statisticsAuthority='all';
const registryState={query:'',status:'listed',authority:'all',register:'all',page:1,size:50,latestOnly:false};
const prefectureState={query:'',status:'all',page:1,size:50};
let SITE=null;
let REGISTRY=null;
let PREFECTURES=null;
let HISTORY=null;
let HISTORY_UI=null;
const loadingData=new Map();
let navigationVersion=0;

function loadData(key){
  if(!loadingData.has(key))loadingData.set(key,fetchJson(`./data/${key}.json`).then(data=>{
    if(key==='site')SITE=data;
    if(key==='registry')REGISTRY=data;
    if(key==='prefectures')PREFECTURES=data;
    if(key==='history')HISTORY=data;
    return data;
  }).catch(error=>{loadingData.delete(key);throw error}));
  return loadingData.get(key);
}

async function activate(name,{replace=false}={}){
  if(!$$('.tab').some(tab=>tab.dataset.view===name)){name='registry';replace=true}
  const version=++navigationVersion;
  if(location.hash!==`#${name}`)history[replace||!location.hash?'replaceState':'pushState'](null,'',`#${name}`);
  closeDetail();
  $$('.tab').forEach(x=>x.classList.toggle('active',x.dataset.view===name));
  $$('.tab').forEach(x=>x.setAttribute('aria-current',x.dataset.view===name?'page':'false'));
  $$('.view').forEach(x=>x.classList.toggle('active',x.id===`view-${name}`));
  $('#rowstatus').textContent='';
  $('#status').textContent='Caricamento della sezione…';
  const view=$(`#view-${name}`);
  view.innerHTML='<div class="note" role="status">Caricamento dei dati della sezione… Puoi già usare il menu.</div>';
  try{
    if(name==='electoral')await renderElectoral();
    else if(name==='robots')await renderRobots();
    else{
      const dependencies={prefectures:['prefectures'],quality:['site'],registry:['site','registry','prefectures'],statistics:['registry'],history:['site','registry','history'],method:['site','registry','prefectures']}[name];
      await Promise.all(dependencies.map(loadData));
      if(version!==navigationVersion)return;
      ({registry:drawRegistry,prefectures:drawPrefectures,statistics:renderStatistics,history:()=>renderHistory(SITE),quality:()=>renderQuality(SITE),method:()=>renderMethod(SITE)})[name]();
    }
    if(version!==navigationVersion)return;
    $('#status').textContent=name==='registry'?'Registro caricato':'Sezione caricata';
    $('#asof').textContent=REGISTRY?`${fmt(REGISTRY.meta.authority_count)} Prefetture · ${fmt(REGISTRY.meta.register_count)} registri`:'';
  }catch(error){
    if(version!==navigationVersion)return;
    $('#status').textContent='Sezione non disponibile';
    view.innerHTML=`<div class="note bad" role="alert">Sezione non disponibile: ${esc(error.message)}. Le altre sezioni restano accessibili. <button class="btn" data-retry>Riprova</button></div>`;
    view.querySelector('[data-retry]').addEventListener('click',()=>activate(name));
  }
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
function redrawFilter(draw,input){
  const id=input.id;
  draw();
  const replacement=document.getElementById(id);
  replacement?.focus({preventScroll:true});
  return replacement;
}
function redrawSearch(selector,draw,input){
  const start=input.selectionStart,end=input.selectionEnd;
  const replacement=redrawFilter(draw,input);
  replacement.setSelectionRange(start,end);
}
function pagination(prefix,state,pages,position){
  const suffix=position==='top'?'-top':'';
  return `<nav class="pager" aria-label="${prefix?'Prefetture':'Registro'}: paginazione ${position==='top'?'iniziale':'finale'}"><button class="btn" id="${prefix}prev${suffix}" data-page-step="-1" ${state.page<=1?'disabled':''}>◀ Precedente</button><span>Pagina ${state.page} / ${pages}</span><button class="btn" id="${prefix}next${suffix}" data-page-step="1" ${state.page>=pages?'disabled':''}>Successiva ▶</button></nav>`;
}
function bindPagination(view,state,draw,title){
  view.querySelectorAll('[data-page-step]').forEach(button=>button.addEventListener('click',()=>{
    state.page+=Number(button.dataset.pageStep);
    draw();
    const heading=document.getElementById(title);
    heading.focus({preventScroll:true});
    heading.scrollIntoView({block:'start'});
  }));
}

function registryBaseRows(){
  if(!REGISTRY)return [];
  return (registryState.latestOnly?latestPublishedRows(REGISTRY.records):REGISTRY.records).filter(r=>{
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
      r.registration_date,r.observed_expiry_date,
      ...[r.primary_date,r.application_date,r.observed_listing_date,r.decision_date,r.registration_date,r.observed_expiry_date].filter(Boolean).map(v=>displayDate(v))
    ].join(' ').toLocaleLowerCase('it');
    return hay.includes(q);
  }).sort((a,b)=>Number(!a.name)-Number(!b.name)||String(a.name).localeCompare(String(b.name),'it')||String(a.authority_name).localeCompare(String(b.authority_name),'it'));
}
function sourceDate(r){
  const value=r.primary_date||r.observed_listing_date||r.application_date||r.decision_date||r.registration_date||'';
  const label=r.primary_date_label||'';
  return value?`<span class="nowrap">${esc(displayDate(value))}</span>${label?`<div class="muted small">${esc(label)}</div>`:''}`:'—';
}
function drawRegistry(){
  if(!REGISTRY){
    $('#view-registry').innerHTML='<div class="note bad"><b>Registro non disponibile.</b> I dati non sono disponibili. Riprova più tardi.</div>';
    return;
  }
  const authorities=uniqueOptions(REGISTRY.records,'authority_key','authority_name');
  const availableRegisters=registerOptions(
    REGISTRY.records.filter(r=>registryState.authority==='all'||r.authority_key===registryState.authority)
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
    <td><b>${esc(r.name||'Denominazione non disponibile')}</b></td>
    <td class="mono">${esc(listText(r.identifiers)||r.identifier_field_raw)}</td>
    <td>${badge(r.source_status)}</td>
    <td>${esc(r.authority_name)}</td>
    <td>${esc(r.register_name)}</td>
    <td>${esc(listText(r.requested_activities)||r.requested_activities_raw)}</td>
    <td>${esc(r.registered_office)}</td>
    <td>${sourceDate(r)}</td>
    <td class="nowrap">${esc(displayDate(r.observed_expiry_date))}</td>
  </tr>`).join('');
  const statusOptions=[
    ['listed','Iscritte'],['pending','In istruttoria'],
    ['renewal_update_in_progress','Aggiornamento in corso'],['renewal_requested','Rinnovo richiesto'],
    ['expired_observed','Scadenza osservata'],['rejected_or_denied','Diniego / rigetto'],
    ['cancellation_related','Cancellazione / cessazione'],['other_or_unknown','Altro / non classificato']
  ].map(([key,label])=>option(key,`${label} (${fmt(counts[key])})`,registryState.status)).join('');
  $('#view-registry').innerHTML=
    `<div class="public-banner">${fmt(archiveSummary(REGISTRY,PREFECTURES).authorities)} Prefetture con dati pubblicati · ${fmt(REGISTRY.records.length)} presenze negli elenchi · Edizione più recente disponibile: ${esc(displayDate(archiveSummary(REGISTRY,PREFECTURES).latest))}</div>`+
    `<details class="coverage"><summary>Territori coperti (${authorities.length} Prefetture)</summary><p>${authorities.map(([,name])=>esc(name)).join(' · ')}.</p></details>`+
    section('RICERCA NEL REGISTRO',`<div class="toolbar registry-filters">
      <div class="filter-field filter-query"><label for="reg-q">Cerca</label><input id="reg-q" type="search" value="${esc(registryState.query)}" placeholder="Ragione sociale, CF/P.IVA, sede, attività…"></div>
      <div class="filter-field"><label for="reg-authority">Prefettura</label><select id="reg-authority">${option('all','Tutte',registryState.authority)}${authorities.map(([k,v])=>option(k,v,registryState.authority)).join('')}</select></div>
      <div class="filter-field"><label for="reg-status">Stato</label><select id="reg-status">${statusOptions}${option('all',`Tutti gli stati (${fmt(base.length)})`,registryState.status)}</select></div>
      <div class="filter-field"><label for="reg-register">Registro</label><select id="reg-register">${option('all','Tutti',registryState.register)}${availableRegisters.map(([k,v])=>option(k,v,registryState.register)).join('')}</select></div>
      <div class="filter-field"><label for="reg-size">Righe per pagina</label><select id="reg-size">${[25,50,100].map(n=>option(String(n),String(n),String(registryState.size))).join('')}</select></div>
      <label class="filter-latest" for="reg-latest"><input id="reg-latest" type="checkbox" ${registryState.latestOnly?'checked':''}> Solo ultime edizioni disponibili</label>
      <div class="filter-actions"><button class="btn" id="reg-reset">Azzera filtri</button><span>Scarica l’intero registro: <a class="btn linkbtn" href="data/registry.csv" download>CSV</a> <a class="btn linkbtn" href="data/registry.json" download>JSON</a></span></div>
    </div><details class="note"><summary>Come leggere i risultati</summary><p><b>Vista predefinita:</b> presenze classificate come iscritte negli elenchi consultati. Usa il filtro Stato per vedere anche le domande e gli altri esiti. La stessa impresa può comparire in più registri: il totale non indica imprese distinte in Italia. Le date di riferimento sono nella scheda; il portale non certifica lo stato attuale dell’impresa.</p></details>`)+
    section(`REGISTRO — ${fmt(all.length)} RISULTATI`,`${pagination('',registryState,pages,'top')}<div class="gridwrap registry-grid"><table class="grid"><thead><tr><th>Ragione sociale</th><th>CF / P.IVA</th><th>Stato</th><th>Prefettura</th><th>Registro</th><th>Attività / settori</th><th>Sede pubblicata</th><th>Data riportata per l’impresa</th><th>Scadenza osservata</th></tr></thead><tbody>${rows||'<tr><td colspan="9">Nessun risultato.</td></tr>'}</tbody></table></div>${!all.length?'<p class="note">Nessuna presenza corrisponde ai filtri selezionati. Prova un altro stato o usa “Azzera filtri”. Questo risultato non dimostra l’assenza dell’impresa dagli elenchi ufficiali.</p>':''}${pagination('',registryState,pages,'bottom')}`,'registry-results');
  $('#reg-q').addEventListener('input',e=>{registryState.query=e.target.value;registryState.page=1;redrawSearch('#reg-q',drawRegistry,e.target)});
  $('#reg-authority').addEventListener('change',e=>{registryState.authority=e.target.value;registryState.register='all';registryState.page=1;redrawFilter(drawRegistry,e.target)});
  $('#reg-register').addEventListener('change',e=>{registryState.register=e.target.value;registryState.page=1;redrawFilter(drawRegistry,e.target)});
  $('#reg-status').addEventListener('change',e=>{registryState.status=e.target.value;registryState.page=1;redrawFilter(drawRegistry,e.target)});
  $('#reg-latest').addEventListener('change',e=>{registryState.latestOnly=e.target.checked;registryState.page=1;redrawFilter(drawRegistry,e.target)});
  $('#reg-size').addEventListener('change',e=>{registryState.size=Number(e.target.value);registryState.page=1;redrawFilter(drawRegistry,e.target)});
  $('#reg-reset').addEventListener('click',()=>{
    Object.assign(registryState,{query:'',authority:'all',register:'all',status:'listed',page:1,latestOnly:false});
    drawRegistry();$('#reg-q').focus();
  });
  bindPagination($('#view-registry'),registryState,drawRegistry,'registry-results');
  $$('.clickrow').forEach(row=>{
    const open=()=>openDetail(row.dataset.record);
    row.addEventListener('click',open);
    row.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open()}});
  });
}
function dateDetail(label,value){return value?`<div>${esc(label)}</div><div>${esc(displayDate(value))}<div class="muted small">Valore originale: ${esc(value)}</div></div>`:''}
function openDetail(locator){
  const r=REGISTRY?.records.find(x=>x.record_locator===locator);
  if(!r)return;
  $('#detail-title').textContent=r.name||'Dettaglio osservazione';
  const id=listText(r.identifiers)||r.identifier_field_raw||'—';
  const acts=listText(r.requested_activities)||r.requested_activities_raw||'—';
  $('#detail-body').innerHTML=`<div class="note">Questa scheda descrive la presenza dell’impresa in uno specifico elenco. La stessa impresa può avere altre presenze in registri o edizioni diversi.</div>
    <div class="kv"><div>Ragione sociale</div><div><b>${esc(r.name)}</b></div><div>Stato</div><div>${badge(r.source_status)}</div><div>Prefettura</div><div>${esc(r.authority_name)}</div><div>Registro</div><div>${esc(r.register_name)}</div><div>Edizione / riferimento</div><div>${esc(displayDate(r.reference_date))}</div><div>Riferimento della scheda</div><div class="mono">${esc(r.record_locator)}</div><div>Riga nell’elenco</div><div class="mono">${esc(r.source_row_ordinal)}</div><div>Sede pubblicata</div><div>${esc(r.registered_office||'—')}</div><div>Sede secondaria</div><div>${esc(r.secondary_office||'—')}</div><div>CF / P.IVA</div><div class="mono">${esc(id)}</div><div>Attività / settori</div><div>${esc(acts)}</div>${dateDetail('Data presentazione istanza',r.application_date)}${dateDetail('Data inserimento osservata',r.observed_listing_date)}${dateDetail('Data provvedimento',r.decision_date)}${dateDetail('Data registrazione',r.registration_date)}${dateDetail('Scadenza osservata',r.observed_expiry_date)}</div>
    ${section('ESITO / ANNOTAZIONE COME PUBBLICATA',`<div class="raw">${esc(r.outcome_raw||'—')}</div>`)}
    ${r.source_fields&&Object.keys(r.source_fields).length?section('CAMPI SPECIFICI DELLA FONTE',`<div class="raw">${esc(JSON.stringify(r.source_fields,null,2))}</div>`):''}
    ${section('FONTE E RIFERIMENTI',`<table class="summary"><tr><th>Pagina ufficiale</th><td><a href="${esc(r.source_page_url)}" target="_blank" rel="noopener">Consulta la pagina ufficiale</a></td></tr><tr><th>Risorsa ufficiale</th><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Consulta l’elenco ufficiale</a></td></tr><tr><th>Impronta del documento (SHA-256)</th><td class="mono">${esc(r.capture_sha256)}</td></tr><tr><th>Parser</th><td class="mono">${esc(r.parser_name)} ${esc(r.parser_version||'')}</td></tr><tr><th>Audit tecnico</th><td><a href="${esc(SITE.audit.repository_url)}" target="_blank" rel="noopener">Repository</a> · <a href="${esc(SITE.audit.parser_url)}" target="_blank" rel="noopener">Parser</a></td></tr></table>`)}`;
  $('#detail').classList.add('open');
  $('#detail').setAttribute('aria-hidden','false');
  detailPreviousFocus=document.activeElement;
  $('.window').inert=true;
  $('#detail-close').focus();
}
let detailPreviousFocus=null;
function closeDetail(){
  if(!$('#detail').classList.contains('open'))return;
  $('#detail').classList.remove('open');
  $('#detail').setAttribute('aria-hidden','true');
  $('.window').inert=false;
  detailPreviousFocus?.focus();
  detailPreviousFocus=null;
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
    return `<tr><td><b>${esc(r.jurisdiction_name)}</b></td><td>${mapBadge(r.mapping_status)}</td><td>${esc((r.published_registers||[]).join(' · ')||'—')}</td><td class="nowrap">${esc(displayDate(r.last_source_update,'Non disponibile'))}</td><td class="nowrap">${esc(displayDate(r.last_project_check,'Non registrata'))}</td><td>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">Consulta la fonte ufficiale</a>`:'—'}</td></tr>`;
  }).join('');
  const counts=PREFECTURES.prefectures.reduce((a,r)=>(a[r.mapping_status]=(a[r.mapping_status]||0)+1,a),{});
  $('#view-prefectures').innerHTML=`<div class="public-banner">${fmt(counts.published)} Prefetture con dati pubblicati · ${fmt(PREFECTURES.prefectures.length)} autorità nell’indice del Ministero</div>`+
    section('CERCA UNA PREFETTURA',`<div class="toolbar"><label for="pref-q">Cerca</label><input id="pref-q" type="search" value="${esc(prefectureState.query)}" placeholder="Prefettura / provincia…"><label for="pref-status">Disponibilità</label><select id="pref-status">${option('all',`Tutte (${fmt(PREFECTURES.prefectures.length)})`,prefectureState.status)}${Object.entries(MAP_STATUS).map(([k,v])=>option(k,`${v} (${fmt(counts[k])})`,prefectureState.status)).join('')}</select><a class="btn linkbtn" href="data/prefectures.csv" download>CSV</a><a class="btn linkbtn" href="data/prefectures.json" download>JSON</a></div><div class="note">Una fonte individuata non significa che i dati siano già consultabili nell’archivio. L’edizione disponibile è datata dalla pubblicazione dell’elenco; la verifica della pagina indica quando il progetto ne ha controllato il percorso ufficiale. Nessuna delle due date certifica lo stato attuale di un’impresa.</div>`)+
    section(`PREFETTURE — ${fmt(all.length)} RISULTATI`,`${pagination('pref-',prefectureState,pages,'top')}<div class="gridwrap"><table class="grid prefecture-grid"><thead><tr><th>Prefettura / territorio</th><th>Disponibilità</th><th>Registri consultabili</th><th>Ultima edizione disponibile</th><th>Pagina verificata il</th><th>Fonte</th></tr></thead><tbody>${rows||'<tr><td colspan="6">Nessuna Prefettura corrisponde ai filtri selezionati.</td></tr>'}</tbody></table></div>${pagination('pref-',prefectureState,pages,'bottom')}`,'prefecture-results');
  $('#pref-q').addEventListener('input',e=>{prefectureState.query=e.target.value;prefectureState.page=1;redrawSearch('#pref-q',drawPrefectures,e.target)});
  $('#pref-status').addEventListener('change',e=>{prefectureState.status=e.target.value;prefectureState.page=1;redrawFilter(drawPrefectures,e.target)});
  bindPagination($('#view-prefectures'),prefectureState,drawPrefectures,'prefecture-results');
}
function publishedEditions(){
  const editions=new Map();
  REGISTRY.records.forEach(r=>{const key=JSON.stringify([r.source_key,r.reference_date,r.capture_sha256]);if(!editions.has(key))editions.set(key,r)});
  return [...editions.values()].sort((a,b)=>b.reference_date.localeCompare(a.reference_date)||a.authority_name.localeCompare(b.authority_name,'it'));
}
function editionTable(){
  return `<div class="gridwrap"><table class="grid"><thead><tr><th>Prefettura</th><th>Registro</th><th>Data dell’elenco</th><th>Contenuto</th><th>Fonte</th></tr></thead><tbody>${publishedEditions().map(r=>`<tr><td>${esc(r.authority_name)}</td><td>${esc(r.register_name)}</td><td>${esc(displayDate(r.reference_date))}</td><td>${esc(({listed:'Imprese iscritte',applicant:'Domande di iscrizione',listed_and_applicant:'Iscrizioni e domande',operational_mixed:'Iscrizioni, domande e altri esiti'})[r.population_scope]||'Elenco')}</td><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Consulta l’elenco ufficiale</a></td></tr>`).join('')}</tbody></table></div>`;
}
function historyController(){
  if(!HISTORY_UI&&HISTORY)HISTORY_UI=WhiteListHistory.createController({
    history:HISTORY,registry:REGISTRY,site:SITE,
    historyRoot:'#view-history',updatesRoot:'#view-updates',onRecord:openDetail,onHistory:()=>activate('history')
  });
  return HISTORY_UI;
}
function renderHistory(D){
  const controller=historyController();
  if(controller)controller.renderHistory();
  else $('#view-history').innerHTML='<div class="note bad">Storico non disponibile. Il registro e le statistiche correnti restano consultabili.</div>';
}
function renderUpdates(){
  const controller=historyController();
  if(controller)controller.renderUpdates();
  else $('#view-updates').innerHTML='<div class="note bad">Registro storico dei controlli non disponibile. Nessuna frequenza viene stimata.</div>';
}
function renderQuality(D){
  $('#view-quality').innerHTML=section('CONTROLLI E LIMITI',`<p>I controlli verificano che i documenti corrispondano alle copie approvate, che le righe siano lette senza omissioni note e che i dati pubblici rispettino i campi autorizzati.</p><p>La stessa impresa può essere presente in più elenchi. Il numero delle presenze non misura il numero di imprese distinte. Una scadenza riportata o l’assenza da una successiva edizione non dimostrano da sole la perdita dell’iscrizione.</p><p>Le verifiche sulla posizione geografica degli indirizzi sono separate. I risultati del caso Cosenza non dimostrano la qualità dell’intero archivio.</p>`)+section('DOCUMENTAZIONE TECNICA',`<ul><li><a href="${esc(D.audit.validation_url)}" target="_blank" rel="noopener">Verifiche sugli indirizzi di Cosenza: campioni, risultati e limiti</a></li><li><a href="${esc(D.audit.architecture_url)}" target="_blank" rel="noopener">Modello dei dati e conservazione delle fonti</a></li><li><a href="${esc(D.audit.repository_url)}" target="_blank" rel="noopener">Codice e cronologia delle modifiche</a></li></ul>`);
}
function renderMethod(D){
  const sources=new Map();
  REGISTRY.records.forEach(r=>sources.set(r.source_page_url,r.authority_name));
  $('#view-method').innerHTML=section('COME LEGGERE IL REGISTRO',`<p>${esc(D.meta.disclaimer)}</p><p>Ogni riga descrive la presenza di un’impresa in uno specifico elenco. Aprendo la scheda puoi vedere i dati riportati dalla Prefettura, la data dell’edizione e i collegamenti ufficiali. Alcune fonti ripetono l’impresa per ciascuna attività: queste ripetizioni sono riunite solo quando gli altri dati coincidono secondo le regole di lettura della fonte.</p><p>“Iscritta” e “in istruttoria” sono stati diversi. Gli stati visualizzati descrivono gli elenchi alle rispettive date, non certificano la situazione attuale. Un campo vuoto significa che l’informazione non è disponibile nella scheda.</p><p>I registri ordinari appartengono a Prefetture diverse: il filtro indica sia il registro sia la Prefettura. Le date complete sono mostrate come giorno/mese/anno (GG/MM/AAAA); gli orari delle verifiche sono in UTC. Date incomplete o non interpretabili restano riconoscibili come valori della fonte. Le trascrizioni originali e i file scaricabili mantengono i valori pubblicati, senza conversioni di presentazione.</p>`)+
    section('COME RACCOGLIAMO I DATI',`<ol><li>Individuiamo la pagina e gli elenchi pubblicati dall’autorità competente.</li><li>Identifichiamo il documento e la sua data di riferimento, conservando i riferimenti alla fonte.</li><li>Leggiamo le tabelle e controlliamo i risultati prima della pubblicazione.</li><li>Pubblichiamo i campi autorizzati. Le correzioni e le edizioni successive conservano la traccia delle fonti precedenti.</li></ol>`)+
    section('FONTI UFFICIALI DEGLI ELENCHI PUBBLICATI',`<ul><li><a href="${esc(PREFECTURES.meta.national_index_url)}" target="_blank" rel="noopener">Ministero dell’Interno — indice nazionale White List</a></li>${[...sources].map(([url,name])=>`<li><a href="${esc(url)}" target="_blank" rel="noopener">${esc(name)} — pagina degli elenchi</a></li>`).join('')}</ul><p>Per le altre autorità, consulta la sezione Prefetture.</p>`);
}

async function fetchJson(path){
  const response=await fetch(path,{cache:'no-store'});
  if(!response.ok)throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}
async function main(){
  new MutationObserver(()=>enhanceTables()).observe($('.content'),{childList:true,subtree:true});
  $$('.tab').forEach(t=>t.addEventListener('click',()=>activate(t.dataset.view)));
  $('#detail-close').addEventListener('click',closeDetail);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDetail()});
  window.addEventListener('hashchange',()=>{if(location.hash==='#main-content'){$('#main-content').focus();return}activate(location.hash.slice(1),{replace:true})});
  await activate(location.hash.slice(1)||'registry',{replace:true});
}
function enhanceTables(){
  $$('.gridwrap').forEach(wrap=>{wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Tabella consultabile: scorri per vedere tutte le colonne')});
  $$('.registry-grid table').forEach(table=>{
    const labels=[...table.querySelectorAll('thead th')].map(th=>th.textContent);
    table.querySelectorAll('tbody tr').forEach(row=>[...row.cells].forEach((cell,i)=>{cell.dataset.label=labels[i]||''}));
  });
}
main();

function renderStatistics(){
  if(!REGISTRY)return;
  const view=$('#view-statistics');
  try {
    const s=publicStatistics(REGISTRY.records,statisticsAuthority);
    const authorityOptions=uniqueOptions(s.latest,'authority_key','authority_name');
    const statuses=[...s.statuses].sort((a,b)=>Object.keys(STATUS).indexOf(a.status)-Object.keys(STATUS).indexOf(b.status));
    const bar=(count,max,status,authority,label)=>`<button class="stat-bar" data-stat-status="${esc(status)}" data-stat-authority="${esc(authority)}" aria-label="${esc(label)}: ${fmt(count)} presenze. Consulta il registro"><span class="stat-fill ${status==='pending'?'stat-pending':''}" style="width:${max?100*count/max:0}%" aria-hidden="true"></span><span class="stat-number">${fmt(count)}</span></button>`;
    const maximum=Math.max(0,...s.prefectures.flatMap(p=>[p.listed,p.pending]));
    const editions=new Map();
    for(const r of s.latest)editions.set(JSON.stringify([r.source_key,r.reference_date,r.capture_sha256]),r);
    const scopes={listed:'Imprese iscritte',applicant:'Domande di iscrizione',listed_and_applicant:'Iscrizioni e domande',operational_mixed:'Iscrizioni, domande e altri esiti'};
    view.innerHTML=`<div class="note">Le statistiche contano le presenze nell’ultima edizione disponibile di ciascun elenco pubblicato nell’archivio. La stessa impresa può comparire più volte. Gli stati descrivono le fonti alle rispettive date: non sono nuove iscrizioni o domande presentate in un periodo, né certificano la situazione attuale.</div>`+
      section('PRESENZE PER STATO RIPORTATO',`<div class="toolbar"><label for="stats-authority">Prefettura</label><select id="stats-authority">${option('all','Tutte',statisticsAuthority)}${authorityOptions.map(([k,n])=>option(k,n,statisticsAuthority)).join('')}</select></div><p>Percentuali su ${fmt(s.total)} presenze nella selezione. Seleziona una barra per consultare le righe corrispondenti.</p><table class="grid stat-table"><thead><tr><th>Stato riportato</th><th>Presenze</th><th>Percentuale</th></tr></thead><tbody>${statuses.map(x=>`<tr><th scope="row">${esc(STATUS[x.status]||x.status)}</th><td>${bar(x.count,Math.max(0,...statuses.map(x=>x.count)),x.status,statisticsAuthority,STATUS[x.status]||x.status)}</td><td>${pct(x.percentage)}</td></tr>`).join('')||'<tr><td colspan="3">Nessuna presenza disponibile.</td></tr>'}</tbody></table>`)+
      section('PRESENZE PER PREFETTURA E STATO',`<p>Tutte le Prefetture con dati consultabili. La Prefettura è quella che pubblica l’elenco, non necessariamente quella della sede dell’impresa. Le due serie usano la stessa scala; gli altri stati sono rappresentati nel primo grafico.</p><table class="grid stat-table"><thead><tr><th>Prefettura</th><th>Iscritte</th><th>In istruttoria</th></tr></thead><tbody>${s.prefectures.map(p=>`<tr><th scope="row">${esc(p.name)}</th><td>${bar(p.listed,maximum,'listed',p.key,p.name+' — Iscritte')}</td><td>${bar(p.pending,maximum,'pending',p.key,p.name+' — In istruttoria')}</td></tr>`).join('')}</tbody></table>`)+
      section('EDIZIONI UTILIZZATE',`<p>Le date possono differire tra elenchi e Prefetture. Questa tabella indica le fonti considerate nei grafici; il filtro del primo grafico seleziona soltanto la Prefettura indicata.</p><div class="gridwrap"><table class="grid"><thead><tr><th>Prefettura</th><th>Registro</th><th>Contenuto</th><th>Data dell’elenco</th><th>Fonte</th></tr></thead><tbody>${[...editions.values()].sort((a,b)=>a.authority_name.localeCompare(b.authority_name,'it')||a.source_key.localeCompare(b.source_key)).map(r=>`<tr><td>${esc(r.authority_name)}</td><td>${esc(r.register_name)}</td><td>${esc(scopes[r.population_scope]||r.population_scope)}</td><td>${esc(displayDate(r.reference_date))}</td><td><a href="${esc(r.resource_url)}" target="_blank" rel="noopener">Consulta l’elenco ufficiale</a></td></tr>`).join('')}</tbody></table></div>`);
    $('#stats-authority').addEventListener('change',e=>{statisticsAuthority=e.target.value;renderStatistics()});
    view.querySelectorAll('[data-stat-status]').forEach(button=>button.addEventListener('click',()=>{
      Object.assign(registryState,{authority:button.dataset.statAuthority,status:button.dataset.statStatus,register:'all',query:'',page:1,latestOnly:true});
      activate('registry').then(()=>$('#reg-q')?.focus());
    }));
  } catch(error) {view.innerHTML=`<div class="note bad">Statistiche non disponibili: ${esc(error.message)}. Il registro resta consultabile.</div>`;}
}

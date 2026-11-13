const robotState={data:null,reports:{},query:'',filter:'all',selected:null,loaded:false,notice:''};
const ROBOT_RUN='https://github.com/colazeta/italian-anti-mafia-whitelist/actions/workflows/prefecture-robots.yml';
const ROBOT_REPORT='https://raw.githubusercontent.com/colazeta/italian-anti-mafia-whitelist/robot-state/state.json';
const robotLabels={baseline:'Prima rilevazione',unchanged:'Nessuna variazione rilevata',changed:'Variazione tecnica rilevata',partial:'Controllo parziale',unseen:'Non ancora controllato'};
const robotDate=value=>value?new Date(value).toLocaleString('it-IT',{timeZone:'Europe/Rome',dateStyle:'short',timeStyle:'short'}):'—';

/* A source URL change, a page change, and an unreviewed document are different facts.
   The robot-state file contains discovery evidence, not private parser or release state. */
function robotCandidateDocuments(report){
  const entries=Object.entries(report?.resources||{});
  const newUrls=new Set(report?.new_urls||[]);
  return entries.filter(([url,resource])=>{
    if(typeof url!=='string'||resource?.role!=='candidate')return false;
    if(!/^https:\/\/prefettura\.interno\.gov\.it\/sites\/default\/files\//i.test(url))return false;
    if(!/\.(pdf|xlsx?|docx?)(?:\?.*)?$/i.test(url))return false;
    let name;
    try{name=decodeURIComponent(url.split('?')[0].split('/').pop()||'').replace(/[-_]/g,' ').toLowerCase();}
    catch{return false;}
    return /(white\s*list|iscritt|richiedent|elenco.{0,25}(imprese|ditte)|ditte.{0,20}iscritte)/i.test(name)&&
      !/(sequestrat|modul|dichiaraz|domand|istanza|comunicaz|fac.?simil|autocertificaz)/i.test(name);
  }).map(([url,resource])=>{
    let name=url.split('?')[0].split('/').pop()||'Documento ufficiale';
    try{name=decodeURIComponent(name).replace(/[_-]/g,' ');}catch{}
    return {url,name,newInLastCheck:newUrls.has(url),archived:Boolean(resource.archived_sha256),
      lastModified:resource.last_modified||''};
  }).sort((a,b)=>(Date.parse(b.lastModified)||0)-(Date.parse(a.lastModified)||0)||a.url.localeCompare(b.url));
}
function robotObservedChangeCounts(report){
  const resources=report?.resources||{};
  const changed=report?.changed_urls||[];
  const docs=robotCandidateDocuments(report);
  return {
    landingPages:changed.filter(url=>resources[url]?.role==='landing').length,
    associatedSources:changed.filter(url=>resources[url]?.role==='source').length,
    newCandidateDocuments:docs.filter(doc=>doc.newInLastCheck).length,
  };
}

async function renderRobots(){
  if(!robotState.data)robotState.data=await fetchJson('./data/robots.json');
  // The published edition date comes from the selected public release, never the robot.
  try{if(typeof loadData==='function'&&!PREFECTURES)await loadData('prefectures');}
  catch{robotState.notice='La data delle edizioni pubblicate non è al momento consultabile.';}
  if(!robotState.loaded){
    try{
      const response=await fetch(ROBOT_REPORT,{cache:'no-store',signal:AbortSignal.timeout(8000)});
      if(!response.ok)throw new Error(String(response.status));
      const report=await response.json();
      if(report.schema_version!==1||!report.robots||typeof report.robots!=='object')throw new Error('format');
      robotState.reports=report.robots;robotState.notice='';
    }catch(error){robotState.notice=error.message==='404'?'Il primo rapporto di esecuzione non è ancora disponibile.':'Rapporti di esecuzione non raggiungibili. Le configurazioni restano consultabili; riprova il caricamento.'}
    robotState.loaded=true;
  }
  drawRobots();
}
function drawRobots(){
  const view=document.querySelector('#view-robots'),robots=robotState.data.robots;
  const checked=robots.filter(r=>robotState.reports[r.authority_key]);
  const partial=checked.filter(r=>robotState.reports[r.authority_key].status==='partial');
  const changed=checked.filter(r=>robotState.reports[r.authority_key].status==='changed');
  const query=robotState.query.trim().toLocaleLowerCase('it');
  const shown=robots.filter(r=>(r.name+' '+r.region+' '+r.authority_key).toLocaleLowerCase('it').includes(query)&&(robotState.filter==='all'||(robotState.reports[r.authority_key]?.status||'unseen')===robotState.filter));
  const selected=robots.find(r=>r.authority_key===robotState.selected),report=selected?robotState.reports[selected.authority_key]:null;
  const detail=selected?section(`ROBOT · ${selected.name}`,`<p><b>Controlla o acquisisci una nuova versione:</b> apri <a href="${ROBOT_RUN}" target="_blank" rel="noopener">l’esecuzione su GitHub</a>, premi “Run workflow” e indica <code>${esc(selected.authority_key)}</code> nel campo <code>authority</code>. Usa <code>capture</code> per controllare le fonti e conservare le versioni acquisite. La conservazione non implica la validazione del contenuto.</p><div class="kv"><div>Ultimo tentativo</div><div>${esc(robotDate(report?.checked_at))} · ora italiana</div><div>Esito</div><div>${esc(robotLabels[report?.status||'unseen']||'Da verificare')}</div><div>Ultimo ciclo di controllo completato</div><div>${esc(robotDate(report?.last_successful_check_at))}</div><div>Risorse acquisite nell’ultimo tentativo</div><div>${report?.captured_urls?.length||0}</div><div>Estrazione dei record</div><div>${selected.population_mapping_reviewed?'Fonti e parser già validati per le versioni approvate. Ogni nuova versione richiede verifica.':'Acquisizione e scoperta disponibili; mappatura delle popolazioni e parser da validare.'}</div></div><details class="robot-detail"><summary>Pagine ufficiali e dettagli del controllo</summary><ul>${selected.landing_pages.map(url=>`<li><a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a></li>`).join('')}</ul>${report?`<p>${report.requests} risorse controllate · ${report.errors?.length||0} errori · ${report.pending_urls?.length||0} risorse in coda. Il controllo successivo riprende dai documenti rimasti.</p>${report.run_url&&/^https:\/\/github\.com\/colazeta\/italian-anti-mafia-whitelist\/actions\/runs\/\d+$/.test(report.run_url)?`<a href="${esc(report.run_url)}" target="_blank" rel="noopener">Apri il rapporto di esecuzione</a>`:''}`:''}</details>`):'';

  const changedSources=checked.filter(r=>robotObservedChangeCounts(robotState.reports[r.authority_key]).associatedSources>0);
  const newDocumentCount=checked.reduce((n,r)=>n+robotObservedChangeCounts(robotState.reports[r.authority_key]).newCandidateDocuments,0);
  let stage='';
  if(selected){
    const changes=robotObservedChangeCounts(report);
    const candidates=robotCandidateDocuments(report);
    const published=typeof PREFECTURES!=='undefined'?PREFECTURES?.prefectures?.find(p=>p.authority_key===selected.authority_key):null;
    const edition=published?.last_source_update?displayDate(published.last_source_update):
      (published?'Nessuna edizione di questa Prefettura nella release selezionata':'Dato pubblico non disponibile');
    const docList=candidates.length?'<ul>'+candidates.slice(0,6).map(doc=>
      '<li><a href="'+esc(doc.url)+'" target="_blank" rel="noopener noreferrer">'+esc(doc.name)+'</a>'+
      (doc.newInLastCheck?' · <b>Nuovo collegamento</b>':'')+
      (doc.archived?' · Copia conservata':' · Conservazione non attestata')+'</li>'
    ).join('')+'</ul>':'<p>Nessun documento candidato riconoscibile tra le risorse registrate.</p>';
    stage=section('STATO DELL’AGGIORNAMENTO',
      '<div class="kv">'+
      '<div>Ultima edizione nella release pubblica</div><div><b>'+esc(edition)+'</b></div>'+
      '<div>Serie e parser mappati</div><div>'+(selected.population_mapping_reviewed?'Mappatura revisionata; nuove strutture da ricontrollare':'Mappatura ancora da validare')+'</div>'+
      '<div>Modifiche alle pagine monitorate</div><div>'+changes.landingPages+'</div>'+
      '<div>Modifiche a URL di fonti associate</div><div>'+changes.associatedSources+'</div>'+
      '<div>Nuovi documenti candidati</div><div>'+changes.newCandidateDocuments+'</div>'+
      '<div>Interpretazione privata</div><div>Non verificabile dal rapporto pubblico dei robot</div>'+
      '</div>'+
      '<p><b>Documenti potenzialmente rilevanti non ancora associati a una serie approvata: '+
      candidates.length+'.</b> Sono collegamenti da qualificare, non nuove edizioni certificate. '+
      'La data HTTP di modifica non equivale alla data amministrativa dell’elenco.</p>'+docList+
      (candidates.length>6?'<p>Mostrati i 6 documenti più recenti tra quelli riconoscibili.</p>':'')
    );
  }
  view.innerHTML=`<div class="public-banner">Robot delle Prefetture · controllo delle fonti e acquisizione delle versioni</div><div class="robot-summary"><span><b>${robots.length}</b> robot dedicati</span><span><b>${checked.length}</b> con un tentativo registrato</span><span><b>${changed.length}</b> variazioni tecniche</span><span><b>${changedSources.length}</b> fonti associate con variazioni</span><span><b>${newDocumentCount}</b> nuovi documenti candidati</span><span><b>${partial.length}</b> controlli parziali</span></div><p>Ogni Prefettura ha un robot eseguibile singolarmente. Il controllo nazionale è programmato ogni giorno. I cambiamenti delle pagine web non provano un aggiornamento degli elenchi. Gli orari si riferiscono all’ultimo tentativo registrato, anche quando la fonte non è raggiungibile.</p>${robotState.notice?`<div class="note" role="status">${esc(robotState.notice)}</div>`:''}<div class="toolbar"><label for="robot-q">Prefettura</label><input id="robot-q" type="search" placeholder="Nome, regione o codice…" value="${esc(robotState.query)}"><label for="robot-filter">Esito</label><select id="robot-filter">${option('all','Tutti',robotState.filter)}${Object.entries(robotLabels).map(([key,label])=>option(key,label,robotState.filter)).join('')}</select><button id="robot-refresh" class="btn">Ricarica rapporti</button><a class="btn linkbtn" href="${ROBOT_RUN}" target="_blank" rel="noopener">Esegui su GitHub</a></div>${detail}${stage}${section(`ROBOT — ${shown.length} PREFETTURE`,`<div class="gridwrap"><table class="grid robot-grid"><thead><tr><th>Prefettura</th><th>Ultimo tentativo · ora italiana</th><th>Esito</th><th>Risorse già associate</th><th>Comandi</th></tr></thead><tbody>${shown.map(r=>{const s=robotState.reports[r.authority_key];return `<tr><td><b>${esc(r.name)}</b><div class="small muted">${esc(r.region)}</div></td><td>${esc(robotDate(s?.checked_at))}</td><td><span class="badge ${s?.status==='partial'?'warn':''}">${esc(robotLabels[s?.status||'unseen']||'Da verificare')}</span></td><td class="num">${r.reviewed_resources}</td><td><button class="btn" data-robot="${esc(r.authority_key)}">Apri robot</button></td></tr>`}).join('')||'<tr><td colspan="5">Nessuna Prefettura trovata.</td></tr>'}</tbody></table></div>`)}<div class="note">Una variazione nei file o nei collegamenti richiede verifica: può dipendere anche dal formato della pagina. Gli originali acquisiti sono conservati nell’archivio di evidenze; l’estrazione e la pubblicazione dei dati delle imprese seguono i controlli della fonte. Per ${robots.filter(r=>!r.population_mapping_reviewed).length} autorità la mappatura delle popolazioni e i parser restano da validare.</div>`;
  view.querySelector('#robot-q').addEventListener('input',e=>{robotState.query=e.target.value;redrawSearch('#robot-q',drawRobots,e.target)});
  view.querySelector('#robot-filter').addEventListener('change',e=>{robotState.filter=e.target.value;drawRobots()});
  view.querySelector('#robot-refresh').addEventListener('click',async e=>{e.target.disabled=true;robotState.loaded=false;await renderRobots()});
  view.querySelectorAll('[data-robot]').forEach(button=>button.addEventListener('click',()=>{robotState.selected=button.dataset.robot;drawRobots();view.querySelector('.kv')?.scrollIntoView({block:'center'})}));
}

if(typeof module!=='undefined'&&module.exports){module.exports={robotCandidateDocuments,robotObservedChangeCounts};}

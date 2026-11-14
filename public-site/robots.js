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

// Dates in filenames are discovery clues, never certified administrative dates.
const robotMonths={gennaio:1,febbraio:2,marzo:3,aprile:4,maggio:5,giugno:6,luglio:7,agosto:8,settembre:9,ottobre:10,novembre:11,dicembre:12};
function robotDateInText(text){
  if(typeof text!=='string'||text.length>500)return '';
  const dates=new Set();
  function add(y,m,d){
    const value=[String(y),String(m).padStart(2,'0'),String(d).padStart(2,'0')].join('-');
    const date=new Date(value+'T00:00:00Z');
    if(Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value)dates.add(value);
  }
  // Numeric formats: YYYY-MM-DD, DD-MM-YYYY, with spaces/dots/underscores.
  const numeric=/(?:^|[^0-9])(?:(20\d{2})[-_.\s]+(\d{1,2})[-_.\s]+(\d{1,2})|(\d{1,2})[-_.\s]+(\d{1,2})[-_.\s]+(20\d{2}))(?!\d)/g;
  for(const m of text.matchAll(numeric))add(m[1]||m[6],m[2]||m[5],m[3]||m[4]);
  // Common official Italian attachment names: "4-settembre-2026".
  const written=/(?:^|[^0-9])(\d{1,2})[-_.\s]+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)[-_.\s]+(20\d{2})(?!\d)/gi;
  for(const m of text.matchAll(written))add(m[3],robotMonths[m[2].toLowerCase()],m[1]);
  // Conflicting date strings in one filename must not be resolved by guessing.
  return dates.size===1?[...dates][0]:'';
}
function robotDocumentDate(url){
  if(typeof url!=='string')return '';
  let name;try{name=decodeURIComponent(url.split(/[?#]/)[0].split('/').pop()||'');}catch{return '';}
  return robotDateInText(name);
}
function robotDocumentHistory(report){
  const observations=report?.document_observations||{};
  const urls=new Set([...Object.keys(observations),...Object.keys(report?.resources||{}),...(report?.discovered_documents||[])]);
  return [...urls].filter(url=>typeof url==='string'&&/^https:\/\//i.test(url)&&/\.(pdf|xlsx?|docx?)(?:[?#].*)?$/i.test(url)).filter(url=>{
    let name;try{name=decodeURIComponent(url.split(/[?#]/)[0].split('/').pop()||'');}catch{return false;}
    return report?.resources?.[url]?.role==='source'||(
      /white[ _-]*list|iscritt|richiedent|elenco/i.test(name)&&
      !/sequestrat|modul|dichiaraz|domand|istanza|comunicaz|fac.?simil|autocertificaz/i.test(name));
  }).map(url=>{
    const resource=report?.resources?.[url]||{};
    const captures=Array.isArray(resource.capture_history)?resource.capture_history:[];
    const seen=observations[url]?.first_seen_at||captures.map(c=>c.captured_at).filter(Boolean).sort()[0]||'';
    let name;try{name=decodeURIComponent(url.split(/[?#]/)[0].split('/').pop()||'');}catch{name='Documento ufficiale';}
    return {url,name,date:robotDocumentDate(url),seen,modified:resource.last_modified||'',
      versions:new Set(captures.map(c=>c.sha256).filter(Boolean)).size};
  }).sort((a,b)=>b.date.localeCompare(a.date)||b.seen.localeCompare(a.seen)||
    (Date.parse(b.modified)||0)-(Date.parse(a.modified)||0)||a.url.localeCompare(b.url));
}
function robotLatestDocument(report){return robotDocumentHistory(report).find(d=>d.date)?.date||'';}
function robotLatestFile(report){return robotDocumentHistory(report)[0]||null;}
// Compare newly detected document clues against the exact selected public source editions.
// A candidate URL/date is not a parser-approved or legally confirmed new list.
function robotDocumentPopulation(name){
  const lower=String(name||'').toLocaleLowerCase('it');
  const applicant=/richiedent|richiest|aspirant/i.test(lower);
  const listed=/iscritt|permanenz|imprese.iscritte/i.test(lower);
  return applicant&&listed?'listed_and_applicant':applicant?'applicant':listed?'listed':'';
}
function robotPublicationGap(report,selectedSources){
  if(!Array.isArray(selectedSources)||!selectedSources.length)
    return {status:'no_release',count:null,later:[],unclassified:[],incomplete:false};
  if(!report)
    return {status:'no_report',count:null,later:[],unclassified:[],incomplete:false};
  const dates=selectedSources.map(s=>s.reference_date).filter(Boolean).sort();
  if(!dates.length)
    return {status:'no_release',count:null,later:[],unclassified:[],incomplete:false};
  const byKey=new Map(selectedSources.map(s=>[s.source_key,s]));
  const publishedHashes=new Set(selectedSources.map(s=>s.sha256).filter(Boolean));
  const latest=dates.at(-1);
  const earliest=dates[0];
  const later=new Map(),unclassified=[];
  for(const doc of robotDocumentHistory(report)){
    const resource=report.resources?.[doc.url]||{};
    const digest=resource.sha256||resource.archived_sha256||'';
    const acquired=Boolean(resource.archived_sha256&&resource.archived_sha256===digest);
    // A source already selected for publication cannot also be outstanding.
    if(digest&&publishedHashes.has(digest))continue;
    const population=robotDocumentPopulation(doc.name);
    const sourceKeys=(Array.isArray(resource.source_keys)?resource.source_keys:[]).filter(k=>byKey.has(k));
    const scoped=sourceKeys.length?sourceKeys.map(k=>byKey.get(k)):
      selectedSources.filter(s=>s.population_scope===population||
        (population&&['listed_and_applicant','operational_mixed'].includes(s.population_scope)));
    // Only an exact source binding or a unique compatible source scope identifies
    // a narrower baseline. Otherwise require a date later than EVERY published
    // source, not just one unrelated list.
    const exact=sourceKeys.length===1||(!sourceKeys.length&&scoped.length===1);
    const cutoff=exact?scoped[0].reference_date:latest;
    if(doc.date&&doc.date>cutoff&&acquired){
      const key=exact?scoped[0].source_key+'|'+doc.date:
        (digest?'sha256:'+digest:'scope:'+population+'|'+doc.date);
      if(!later.has(key))later.set(key,{...doc,population,publicationBaseline:cutoff,
        captured:acquired,binding:exact?scoped[0].source_key:null});
    }else if(!acquired||!doc.date||doc.date===cutoff||(!exact&&doc.date>earliest&&doc.date<=latest)){
      // Same-date variants and documents without an interpretable date require
      // manual examination; neither is silently counted as a newer edition.
      if(resource.role==='candidate'||(resource.role==='source'&&digest)||report.document_observations?.[doc.url])
        unclassified.push({...doc,population,captured:acquired});
    }
  }
  const rows=[...later.values()].sort((a,b)=>b.date.localeCompare(a.date)||a.url.localeCompare(b.url));
  return {status:'ok',count:rows.length,later:rows,unclassified,
    incomplete:report.status==='partial'||Boolean(report.pending_urls?.length)||Boolean(report.errors?.length)};
}
function robotLastPublishedDate(selectedSources){
  if(!Array.isArray(selectedSources)||!selectedSources.length)return '';
  return selectedSources.map(s=>s.reference_date).filter(Boolean).sort().at(-1)||'';
}
function robotBacklogCell(gap){
  if(gap.status==='no_release')return '<span class="muted">Non confrontabile</span><div class="small muted">Nessuna edizione pubblicata</div>';
  if(gap.status==='no_report')return '<span class="muted">Non disponibile</span><div class="small muted">Rapporto robot assente</div>';
  const count=gap.count;
  const display=gap.incomplete?(count?'Almeno '+count:'Non determinabile'):String(count);
  return '<b>'+esc(display)+'</b><div class="small muted">'+
    (count===1?'Documento successivo candidato':'Documenti successivi candidati')+' · da verificare'+
    (gap.unclassified.length?' · '+esc(gap.unclassified.length)+' senza confronto certo':'')+'</div>';
}
function robotBacklogDetail(gap){
  if(gap.status!=='ok')return '<p>Non è possibile confrontare le pubblicazioni senza un rapporto del robot e una release selezionata.</p>';
  const rows=gap.later.slice(0,20);
  return '<p><b>'+esc(gap.count)+' documenti successivi rilevati.</b> Il conteggio riguarda i file acquisiti e conservati, con una data nel nome successiva alla rispettiva data di riferimento della release, non edizioni pronte per essere pubblicate. I documenti con date assenti o ambigue non sono inclusi.</p>'+
    (rows.length?'<ul>'+rows.map(doc=>'<li><b>'+esc(doc.date)+'</b> · <a href="'+esc(doc.url)+'" target="_blank" rel="noopener noreferrer">'+esc(doc.name)+'</a> · '+(doc.captured?'Copia conservata':'Acquisizione non attestata')+'</li>').join('')+'</ul>':'')+
    (gap.count>rows.length?'<p>Altri '+esc(gap.count-rows.length)+' documenti candidati non mostrati; consulta lo storico.</p>':'')+
    (gap.unclassified.length?'<p><b>'+esc(gap.unclassified.length)+' documenti da verificare separatamente</b> (data assente, non successiva in modo certo o differenza documentale con la stessa data).</p>':'')+
    (gap.incomplete?'<p>Il controllo del robot è parziale: il numero mostrato è soltanto quello già rilevato.</p>':'');
}
function robotDocumentCell(report){
  const doc=robotLatestFile(report);
  if(!doc)return '<span class="muted">Nessun documento rilevato</span>';
  return '<div>'+(doc.date?'<b>'+esc(doc.date)+'</b>':'<span class="muted">Data non identificata</span>')+'</div>'+
    '<div class="small robot-file-name"><a href="'+esc(doc.url)+'" target="_blank" rel="noopener noreferrer">'+esc(doc.name)+'</a></div>'+
    '<div class="small muted">'+(doc.date?'Data nel nome · da verificare':doc.seen?'Prima rilevazione: '+esc(robotDate(doc.seen)):'Data di pubblicazione non disponibile')+'</div>';
}
function robotHistoryPanel(report){
  const rows=robotDocumentHistory(report);
  return section('STORICO DEI DOCUMENTI WHITE LIST',
    '<p>File individuati sui siti ufficiali, anche prima della loro estrazione. La data nel nome è un indizio e non certifica la pubblicazione. In assenza di data, i file sono ordinati per prima rilevazione conservata quando disponibile. Le rilevazioni ripetute dello stesso collegamento non creano nuove righe.</p>'+
    '<div class="gridwrap"><table class="grid"><thead><tr><th>Data nel nome del file</th><th>Prima rilevazione</th><th>Modifica HTTP (tecnica)</th><th>Versioni acquisite distinte</th><th>File individuato</th></tr></thead><tbody>'+
    rows.map(d=>'<tr><td>'+esc(d.date||'Non identificata')+'</td><td>'+esc(robotDate(d.seen))+'</td><td>'+esc(robotDate(d.modified))+'</td><td>'+d.versions+'</td><td class="robot-file-name"><a target="_blank" rel="noopener noreferrer" href="'+esc(d.url)+'">'+esc(d.name)+'</a></td></tr>').join('')+
    (rows.length?'':'<tr><td colspan="5">Nessun documento identificato nelle evidenze disponibili.</td></tr>')+'</tbody></table></div>');
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
  const publishedByKey=new Map((typeof PREFECTURES!=='undefined'?PREFECTURES?.prefectures:[])?.map(p=>[p.authority_key,p])||[]);
  const checked=robots.filter(r=>robotState.reports[r.authority_key]);
  const partial=checked.filter(r=>robotState.reports[r.authority_key].status==='partial');
  const changed=checked.filter(r=>robotState.reports[r.authority_key].status==='changed');
  const query=robotState.query.trim().toLocaleLowerCase('it');
  const shown=robots.filter(r=>(r.name+' '+r.region+' '+r.authority_key).toLocaleLowerCase('it').includes(query)&&(robotState.filter==='all'||(robotState.reports[r.authority_key]?.status||'unseen')===robotState.filter));
  const selected=robots.find(r=>r.authority_key===robotState.selected),report=selected?robotState.reports[selected.authority_key]:null;
  const selectedSources=selected?.selected_public_sources||[];
  const selectedGap=robotPublicationGap(report,selectedSources);
  const detail=selected?section(`ROBOT · ${selected.name}`,`<p><b>Controlla o acquisisci una nuova versione:</b> apri <a href="${ROBOT_RUN}" target="_blank" rel="noopener">l’esecuzione su GitHub</a>, premi “Run workflow” e indica <code>${esc(selected.authority_key)}</code> nel campo <code>authority</code>. Usa <code>capture</code> per controllare le fonti e conservare le versioni acquisite. La conservazione non implica la validazione del contenuto.</p><div class="kv"><div>Ultimo tentativo</div><div>${esc(robotDate(report?.checked_at))} · ora italiana</div><div>Esito</div><div>${esc(robotLabels[report?.status||'unseen']||'Da verificare')}</div><div>Ultimo ciclo di controllo completato</div><div>${esc(robotDate(report?.last_successful_check_at))}</div><div>Risorse acquisite nell’ultimo tentativo</div><div>${report?.captured_urls?.length||0}</div><div>Estrazione dei record</div><div>${selected.population_mapping_reviewed?'Fonti e parser già validati per le versioni approvate. Ogni nuova versione richiede verifica.':'Acquisizione e scoperta disponibili; mappatura delle popolazioni e parser da validare.'}</div></div><details class="robot-detail"><summary>Pagine ufficiali e dettagli del controllo</summary><ul>${selected.landing_pages.map(url=>`<li><a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a></li>`).join('')}</ul>${report?`<p>${report.requests} risorse controllate · ${report.errors?.length||0} errori · ${report.pending_urls?.length||0} risorse in coda. Il controllo successivo riprende dai documenti rimasti.</p>${report.run_url&&/^https:\/\/github\.com\/colazeta\/italian-anti-mafia-whitelist\/actions\/runs\/\d+$/.test(report.run_url)?`<a href="${esc(report.run_url)}" target="_blank" rel="noopener">Apri il rapporto di esecuzione</a>`:''}`:''}</details>`):'';

  const changedSources=checked.filter(r=>robotObservedChangeCounts(robotState.reports[r.authority_key]).associatedSources>0);
  const newDocumentCount=checked.reduce((n,r)=>n+robotObservedChangeCounts(robotState.reports[r.authority_key]).newCandidateDocuments,0);
  const latestDocument=checked.map(r=>robotLatestDocument(robotState.reports[r.authority_key])).filter(Boolean).sort().pop();
  let stage='';
  if(selected){
    const changes=robotObservedChangeCounts(report);
    const candidates=robotCandidateDocuments(report);
    const published=publishedByKey.get(selected.authority_key);
    const edition=published?.last_source_update?displayDate(published.last_source_update):
      (published?'Nessuna edizione di questa Prefettura nella release selezionata':'Dato pubblico non disponibile');
    const released=robotLastPublishedDate(selectedSources);
    const publicationAligned=Boolean(published)&&((published.last_source_update||'')===released);
    const docList=candidates.length?'<ul>'+candidates.slice(0,6).map(doc=>
      '<li><a href="'+esc(doc.url)+'" target="_blank" rel="noopener noreferrer">'+esc(doc.name)+'</a>'+
      (doc.newInLastCheck?' · <b>Nuovo collegamento</b>':'')+
      (doc.archived?' · Copia conservata':' · Conservazione non attestata')+'</li>'
    ).join('')+'</ul>':'<p>Nessun documento candidato riconoscibile tra le risorse registrate.</p>';
    stage=section('STATO DELL’AGGIORNAMENTO',
      '<div class="kv">'+
      '<div>Ultima edizione nella release pubblica</div><div><b>'+esc(edition)+'</b></div>'+
      '<div>Documenti successivi rilevati</div><div>'+(publicationAligned?robotBacklogCell(selectedGap):'Dati delle release non allineati')+'</div>'+
      '<div>File individuato dal robot</div><div>'+robotDocumentCell(report)+'</div>'+
      '<div>Serie e parser mappati</div><div>'+(selected.population_mapping_reviewed?'Mappatura revisionata; nuove strutture da ricontrollare':'Mappatura ancora da validare')+'</div>'+
      '<div>Modifiche alle pagine monitorate</div><div>'+changes.landingPages+'</div>'+
      '<div>Modifiche a URL di fonti associate</div><div>'+changes.associatedSources+'</div>'+
      '<div>Nuovi documenti candidati</div><div>'+changes.newCandidateDocuments+'</div>'+
      '<div>Interpretazione privata</div><div>Non verificabile dal rapporto pubblico dei robot</div>'+
      '</div>'+
      '<p><b>Documenti potenzialmente rilevanti non ancora associati a una serie approvata: '+
      candidates.length+'.</b> Sono collegamenti da qualificare, non nuove edizioni certificate. '+
      'La data HTTP di modifica non equivale alla data amministrativa dell’elenco.</p>'+docList+
      (publicationAligned?robotBacklogDetail(selectedGap):'<p>Confronto fra release e robot non disponibile: dati delle release non allineati.</p>')+
      (candidates.length>6?'<p>Mostrati i 6 documenti più recenti tra quelli riconoscibili.</p>':'')
    );
  }
  view.innerHTML=`<div class="public-banner">Robot delle Prefetture · controllo delle fonti e acquisizione delle versioni</div><div class="robot-summary"><span><b>${robots.length}</b> robot dedicati</span><span>Data più recente nel nome di un documento: <b>${esc(latestDocument||'Non disponibile')}</b> · indizio, non pubblicazione certificata</span><span><b>${checked.length}</b> con un tentativo registrato</span><span><b>${changed.length}</b> variazioni tecniche</span><span><b>${changedSources.length}</b> fonti associate con variazioni</span><span><b>${newDocumentCount}</b> nuovi documenti candidati</span><span><b>${partial.length}</b> controlli parziali</span></div><p>Ogni Prefettura ha un robot eseguibile singolarmente. Il controllo nazionale è programmato ogni giorno. «Documenti successivi rilevati» indica candidati datati più recenti della rispettiva fonte nella release pubblica, non edizioni già validate o pronte alla pubblicazione. I file senza data confrontabile o non ancora acquisiti non entrano nel conteggio. I cambiamenti delle pagine web non provano un aggiornamento degli elenchi. Gli orari si riferiscono all’ultimo tentativo registrato, anche quando la fonte non è raggiungibile.</p>${robotState.notice?`<div class="note" role="status">${esc(robotState.notice)}</div>`:''}<div class="toolbar"><label for="robot-q">Prefettura</label><input id="robot-q" type="search" placeholder="Nome, regione o codice…" value="${esc(robotState.query)}"><label for="robot-filter">Esito</label><select id="robot-filter">${option('all','Tutti',robotState.filter)}${Object.entries(robotLabels).map(([key,label])=>option(key,label,robotState.filter)).join('')}</select><button id="robot-refresh" class="btn">Ricarica rapporti</button><a class="btn linkbtn" href="${ROBOT_RUN}" target="_blank" rel="noopener">Esegui su GitHub</a></div>${detail}${stage}${selected?robotHistoryPanel(report):''}${section(`ROBOT — ${shown.length} PREFETTURE`,`<div class="gridwrap"><table class="grid robot-grid"><thead><tr><th>Prefettura</th><th>Ultimo tentativo · ora italiana</th><th>Documento individuato · data nel nome</th><th>Ultima edizione pubblicata</th><th>Documenti successivi rilevati</th><th>Esito</th><th>Risorse già associate</th><th>Comandi</th></tr></thead><tbody>${shown.map(r=>{const s=robotState.reports[r.authority_key];const publishedDate=robotLastPublishedDate(r.selected_public_sources);
    const published=publishedByKey.get(r.authority_key);
    const aligned=Boolean(published)&&(published.last_source_update||'')===publishedDate;
    return `<tr><td><b>${esc(r.name)}</b><div class="small muted">${esc(r.region)}</div></td><td>${esc(robotDate(s?.checked_at))}</td><td>${robotDocumentCell(s)}</td><td>${aligned?(publishedDate?esc(displayDate(publishedDate)):'<span class="muted">Nessuna edizione</span>'):'<span class="muted">Dati non allineati</span>'}</td><td>${aligned?robotBacklogCell(robotPublicationGap(s,r.selected_public_sources)):'<span class="muted">Non disponibile</span>'}</td><td><span class="badge ${s?.status==='partial'?'warn':''}">${esc(robotLabels[s?.status||'unseen']||'Da verificare')}</span></td><td class="num">${r.reviewed_resources}</td><td><button class="btn" data-robot="${esc(r.authority_key)}">Apri robot</button></td></tr>`}).join('')||'<tr><td colspan="8">Nessuna Prefettura trovata.</td></tr>'}</tbody></table></div>`)}<div class="note">Una variazione nei file o nei collegamenti richiede verifica: può dipendere anche dal formato della pagina. Gli originali acquisiti sono conservati nell’archivio di evidenze; l’estrazione e la pubblicazione dei dati delle imprese seguono i controlli della fonte. Per ${robots.filter(r=>!r.population_mapping_reviewed).length} autorità la mappatura delle popolazioni e i parser restano da validare.</div>`;
  view.querySelector('#robot-q').addEventListener('input',e=>{robotState.query=e.target.value;redrawSearch('#robot-q',drawRobots,e.target)});
  view.querySelector('#robot-filter').addEventListener('change',e=>{robotState.filter=e.target.value;drawRobots()});
  view.querySelector('#robot-refresh').addEventListener('click',async e=>{e.target.disabled=true;robotState.loaded=false;await renderRobots()});
  view.querySelectorAll('[data-robot]').forEach(button=>button.addEventListener('click',()=>{robotState.selected=button.dataset.robot;drawRobots();view.querySelector('.kv')?.scrollIntoView({block:'center'})}));
}

if(typeof module!=='undefined'&&module.exports){module.exports={robotCandidateDocuments,robotObservedChangeCounts,robotDateInText,robotDocumentDate,robotDocumentHistory,robotLatestDocument,robotLatestFile,robotDocumentPopulation,robotPublicationGap,robotLastPublishedDate};}

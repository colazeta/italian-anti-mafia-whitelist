const $=s=>document.querySelector(s);
const $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const fmt=n=>new Intl.NumberFormat('it-IT').format(Number(n||0));
const pct=n=>`${Number(n).toFixed(2).replace('.',',')}%`;
const section=(title,body)=>`<div class="section"><div class="section-title">${esc(title)}</div><div class="section-body">${body}</div></div>`;
const metric=(label,value)=>`<div class="metricline"><span>${esc(label)}</span><span class="value">${esc(value)}</span></div>`;

function activate(name){
  $$('.tab').forEach(x=>x.classList.toggle('active',x.dataset.view===name));
  $$('.view').forEach(x=>x.classList.toggle('active',x.id===`view-${name}`));
}

function renderHome(D){
  $('#view-home').innerHTML=`<div class="public-banner">${esc(D.meta.classification)} · aggiornamento dati ${esc(D.meta.data_as_of)}</div>`+
  section('ARCHIVIO PUBBLICO',`<p><b>${esc(D.meta.title)}</b> raccoglie, versiona e rende confrontabili fonti pubbliche sulle White List antimafia italiane.</p><div class="note">${esc(D.meta.disclaimer)}</div>`)+
  `<div class="split">${section('COPERTURA DELLE FONTI',metric('Autorità con pagina primaria verificata',fmt(D.national.verified_authorities))+metric('Serie di fonte censite',fmt(D.national.source_series))+metric('Ambiti di registro censiti',fmt(D.national.register_scopes))+metric('Ambiti con popolazione completa',fmt(D.national.complete_scopes))+metric('Ambiti ancora incompleti',fmt(D.national.incomplete_scopes)))}${section('PILOTA COSENZA',metric('Ultima edizione pubblica',D.cosenza.latest_reference_date)+metric('Righe sorgente osservate',fmt(D.cosenza.source_rows))+metric('Edizioni storiche censite',fmt(D.history.length))+metric('Copertura candidati ANNCSU',pct(D.quality.candidate_coverage_pct))+metric('Auto-accepted geography',fmt(D.quality.auto_accepted)))}</div>`+
  section('CONTRATTO DI PUBBLICAZIONE',`<div class="flow">${esc(D.method.publication_rule)}</div><div class="footer-note">La vista pubblica è un prodotto derivato esplicito. Il database interno e gli strumenti di curation non sono direttamente esposti.</div>`);
}

function renderCosenza(D){
  const s=D.cosenza.status_counts;
  const rows=[
    ['Inserita / listed',s.listed],['In istruttoria / pending',s.pending],['Aggiornamento in corso',s.renewal_update_in_progress],['Rinnovo richiesto',s.renewal_requested],['Altro / ignoto',s.other_or_unknown]
  ].map(([k,v])=>`<tr><td>${esc(k)}</td><td class="num">${fmt(v)}</td></tr>`).join('');
  $('#view-cosenza').innerHTML=section(`COSENZA — EDIZIONE ${D.cosenza.latest_reference_date}`,`<div class="note"><b>Unità:</b> righe/osservazioni della fonte parser v2. Questi conteggi non vanno interpretati automaticamente come numero di imprese uniche.</div><div class="gridwrap"><table class="summary"><tr><th>Esito osservato</th><th>N.</th></tr>${rows}<tr><th>Totale</th><th class="num">${fmt(D.cosenza.source_rows)}</th></tr></table></div>`)+
  section('EVIDENZA SORGENTE',`<table class="summary"><tr><th>Pagina ufficiale</th><td><a href="${esc(D.cosenza.latest_source_page)}" target="_blank" rel="noopener">Apri pagina Prefettura</a></td></tr><tr><th>PDF ufficiale</th><td><a href="${esc(D.cosenza.latest_resource_url)}" target="_blank" rel="noopener">Apri documento</a></td></tr><tr><th>SHA-256 capture</th><td class="mono">${esc(D.cosenza.capture_sha256)}</td></tr><tr><th>Pagine</th><td>${fmt(D.cosenza.page_count)}</td></tr><tr><th>Schema fingerprint</th><td class="mono">${esc(D.cosenza.schema_fingerprint)}</td></tr></table>`);
}

function renderHistory(D){
  const rows=[...D.history].reverse().map((r,i)=>`<tr><td class="mono">${String(D.history.length-i).padStart(2,'0')}</td><td>${esc(r.date)}</td><td><span class="badge ${r.origin==='official_historical'?'warn':'ok'}">${esc(r.origin)}</span></td><td><a href="${esc(r.page_url)}" target="_blank" rel="noopener">Fonte ufficiale</a></td></tr>`).join('');
  $('#view-history').innerHTML=section('SERIE STORICA COSENZA',`<div class="note">Ogni edizione è trattata come osservazione storica distinta. Una futura automazione settimanale aggiungerà nuove edizioni senza sovrascrivere quelle precedenti.</div><div class="gridwrap"><table class="grid"><thead><tr><th>#</th><th>Data di riferimento</th><th>Origine</th><th>Pagina</th></tr></thead><tbody>${rows}</tbody></table></div>`);
}

function renderQuality(D){
  const q=D.quality;
  const classes=q.classes.map(r=>`<tr><td class="mono">${esc(r.class)}</td><td class="num">${fmt(r.sample)}</td><td class="num">${fmt(r.correct)}</td><td class="num">${pct(r.precision_pct)}</td><td>${esc(r.public_interpretation)}</td></tr>`).join('');
  $('#view-quality').innerHTML=section('VALIDAZIONE INDIRIZZI — COSENZA',`<div class="note"><b>Queste metriche sono stime sul caso Cosenza, non performance nazionali.</b> I <code>not_found</code> incidono sulla copertura/yield, non sulla precisione dei match restituiti.</div><div class="split"><div>${metric('Indirizzi canonici',fmt(q.address_population))+metric('Candidati ANNCSU',fmt(q.anncsu_candidates))+metric('Not found',fmt(q.not_found))+metric('Candidate coverage',pct(q.candidate_coverage_pct))}</div><div>${metric('Precisione pesata candidati',pct(q.candidate_weighted_precision_pct))+metric('Validated end-to-end yield',pct(q.estimated_validated_yield_pct))+metric('Auto-accepted',fmt(q.auto_accepted))}</div></div>`)+
  section('PRECISIONE PER CLASSE',`<div class="gridwrap"><table class="grid"><thead><tr><th>Classe</th><th>Campione</th><th>Corretti</th><th>Precisione osservata</th><th>Interpretazione</th></tr></thead><tbody>${classes}</tbody></table></div>`)+
  section('POLICY ATTUALE',`<p>Nessuna classe viene promossa automaticamente a geografia accettata sulla sola evidenza di Cosenza. <span class="mono">civic_access</span> è l’unica classe candidata a futura auto-accept dopo replica multi-regione.</p>`);
}

function renderMethod(D){
  const flow=D.method.flow.map((x,i)=>`${String(i+1).padStart(2,'0')}  ${x}`).join('\n   ↓\n');
  $('#view-method').innerHTML=section('PIPELINE',`<div class="flow">${esc(flow)}</div>`)+
  section('PRINCIPI',`<table class="summary"><tr><th>Fonte</th><td>Il dato osservato viene preservato e versionato prima di ogni interpretazione.</td></tr><tr><th>Canonicalizzazione</th><td>Solo trasformazioni deterministiche e tracciabili possono alimentare il livello canonico.</td></tr><tr><th>Geografia</th><td>I risultati di linkage sono candidate-by-default; la geografia accettata resta separata.</td></tr><tr><th>Validazione</th><td>Le stime di qualità derivano da campioni congelati e review manuale versionata.</td></tr><tr><th>Pubblicazione</th><td>${esc(D.method.publication_rule)}</td></tr></table>`);
}

function renderSources(D){
  const rows=D.sources.map(s=>`<tr><td><b>${esc(s.name)}</b></td><td>${esc(s.role)}</td><td><a href="${esc(s.url)}" target="_blank" rel="noopener">Apri</a></td></tr>`).join('');
  $('#view-sources').innerHTML=section('FONTI PRIMARIE E DI SUPPORTO',`<div class="gridwrap"><table class="grid"><thead><tr><th>Fonte</th><th>Ruolo</th><th>Link</th></tr></thead><tbody>${rows}</tbody></table></div>`)+section('NOTA',`<div class="note">Il portale non sostituisce le pubblicazioni ufficiali. Link, hash e metadati servono a rendere verificabile la provenienza delle osservazioni.</div>`);
}

async function main(){
  try{
    const response=await fetch('./data/site.json',{cache:'no-store'});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const D=await response.json();
    renderHome(D);renderCosenza(D);renderHistory(D);renderQuality(D);renderMethod(D);renderSources(D);
    $('#status').textContent='Pronto · export pubblico v'+D.meta.public_contract_version;
    $('#asof').textContent='Dati al '+D.meta.data_as_of;
    $$('.tab').forEach(t=>t.addEventListener('click',()=>activate(t.dataset.view)));
  }catch(err){
    $('#status').textContent='Errore caricamento dati';
    $('#view-home').innerHTML=`<div class="note bad"><b>Impossibile caricare il dataset pubblico.</b><br>${esc(err.message)}</div>`;
  }
}
main();

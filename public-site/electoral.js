// The ranking concerns source update timestamps. It never ranks prefectural resources.
const electoralState={data:null,pending:null,event:'overall',metric:'weighted_mean_hours',query:''};
const electoralMetrics={weighted_mean_hours:'Media ponderata per sezioni',weighted_p90_hours:'90° percentile ponderato',last_hours:'Ultimo aggiornamento'};
const electoralHours=n=>n===null||n===undefined?'—':Number(n).toFixed(2).replace('.',',');
function electoralRank(rows,value){
  const sorted=[...rows].sort((a,b)=>value(a)-value(b)||a.province.localeCompare(b.province,'it'));
  let rank=0;
  return sorted.map((row,i)=>{if(i===0||value(row)!==value(sorted[i-1]))rank=i+1;return {...row,rank}});
}

function renderOverallElectoral(view){
  const data=electoralState.data, field=electoralState.metric, events=data.events;
  const complete=electoralRank(data.overall.provinces.filter(p=>p.status==='complete_in_all'),p=>p.scores[field]);
  const missing=data.overall.provinces.filter(p=>p.status!=='complete_in_all');
  const q=electoralState.query.toLocaleLowerCase('it').trim();
  const shown=[...complete,...missing].filter(p=>p.province.toLocaleLowerCase('it').includes(q));
  const chart=complete.slice(0,20).map(p=>`<tr><td>${esc(p.province)}</td><td class="electoral-bar-cell"><span class="electoral-bar" style="width:${p.scores[field].toFixed(1)}%"></span></td><td class="num">${electoralHours(p.scores[field])}</td></tr>`).join('');
  const rows=shown.map(p=>`<tr><td class="num">${p.rank||'—'}</td><td>${esc(p.province)}</td><td class="num">${p.scores?electoralHours(p.scores[field]):'—'}</td><td class="num">${p.events_complete}/4</td>${events.map(e=>`<td class="num">${p.event_hours?electoralHours(p.event_hours[e.id][field]):'—'}</td>`).join('')}</tr>`).join('');
  view.innerHTML=`<div class="public-banner">Tempi elettorali · Classifica complessiva</div>
    <div class="note"><b>Metodo:</b> ogni tornata pesa il 25%. Per ciascuna provincia calcoliamo la posizione percentuale rispetto alle province complete in quella tornata (0 = aggiornamento più rapido; 100 = più lento) e ne facciamo la media sulle quattro tornate. A parità di tempo si usa la posizione media. Il punteggio è descrittivo dei timestamp degli estratti, non delle risorse o dell'efficienza delle Prefetture. Le province incomplete anche in una sola tornata restano fuori classifica.</div>
    <div class="toolbar"><label for="electoral-event">Consultazione</label><select id="electoral-event"><option value="overall" selected>Tutte le tornate · classifica complessiva</option>${events.map(e=>`<option value="${esc(e.id)}">${esc(e.label)}</option>`).join('')}</select>
    <label for="electoral-metric">Indicatore</label><select id="electoral-metric">${Object.entries(electoralMetrics).map(([key,label])=>`<option value="${key}" ${key===field?'selected':''}>${esc(label)}</option>`).join('')}</select>
    <label for="electoral-query">Provincia</label><input id="electoral-query" type="search" value="${esc(electoralState.query)}" placeholder="Cerca provincia"></div>
    <div class="note">${complete.length} province complete in tutte e quattro le tornate · ${missing.length} fuori dalla classifica complessiva. I tempi nelle ultime quattro colonne sono ore dalla chiusura delle urne; il punteggio composito è una media di posizioni percentuali, non ore.</div>
    <div class="split"><div class="section"><div class="section-title">PRIME 20 · PUNTEGGIO PIÙ BASSO</div><div class="section-body"><table class="summary electoral-chart"><thead><tr><th>Provincia</th><th>Posizione percentuale media</th><th>Punti</th></tr></thead><tbody>${chart}</tbody></table></div></div>
    <div class="section"><div class="section-title">RANK COMPLESSIVO · ${shown.length} RIGHE</div><div class="section-body"><div class="gridwrap"><table class="grid electoral-grid"><thead><tr><th>Rank</th><th>Provincia</th><th>Punti</th><th>Tornate</th>${events.map(e=>`<th>${esc(e.label)} · ore</th>`).join('')}</tr></thead><tbody>${rows||'<tr><td colspan="8">Nessuna provincia trovata.</td></tr>'}</tbody></table></div></div></div></div>
    <p class="footer-note">Il confronto fra tornate risente dell'ordine degli scrutini, delle schede e dei perimetri. Metodo, fonti e impronte SHA-256 sono nella <a href="https://github.com/colazeta/italian-anti-mafia-whitelist/tree/main/scripts/elections" target="_blank" rel="noopener">repository del progetto</a>.</p>`;
  bindElectoralControls(view);
}

function bindElectoralControls(view){
  view.querySelector('#electoral-event').addEventListener('change',e=>{electoralState.event=e.target.value;electoralState.query='';renderElectoral()});
  view.querySelector('#electoral-metric').addEventListener('change',e=>{electoralState.metric=e.target.value;renderElectoral()});
  view.querySelector('#electoral-query').addEventListener('input',e=>{const position=e.target.selectionStart;electoralState.query=e.target.value;renderElectoral();const input=view.querySelector('#electoral-query');input.focus();input.setSelectionRange(position,position)});
}

async function renderElectoral(){
  const view=document.querySelector('#view-electoral');
  if(!electoralState.data){
    view.innerHTML='<div class="note">Caricamento degli estratti elettorali…</div>';
    if(!electoralState.pending)electoralState.pending=fetch('./data/electoral.json',{cache:'no-store'}).then(response=>{
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      return response.json();
    }).then(data=>{electoralState.data=data}).finally(()=>{electoralState.pending=null});
    await electoralState.pending;
  }
  if(electoralState.event==='overall'){renderOverallElectoral(view);return}
  const events=electoralState.data.events;
  const event=events.find(e=>e.id===electoralState.event)||events[0];
  const field=electoralState.metric;
  const complete=electoralRank(event.provinces.filter(p=>p.status==='complete_in_extract'),p=>p[field]);
  const missing=event.provinces.filter(p=>p.status!=='complete_in_extract');
  const q=electoralState.query.toLocaleLowerCase('it').trim();
  const shown=[...complete,...missing].filter(p=>p.province.toLocaleLowerCase('it').includes(q));
  const hours=electoralHours;
  const median=complete.length?(complete[Math.floor((complete.length-1)/2)][field]+complete[Math.floor(complete.length/2)][field])/2:null;
  const width=Math.max(...complete.slice(0,20).map(p=>p[field]),1);
  const chart=complete.slice(0,20).map(p=>`<tr><td>${esc(p.province)}</td><td class="electoral-bar-cell"><span class="electoral-bar" style="width:${(p[field]/width*100).toFixed(1)}%"></span></td><td class="num">${hours(p[field])}</td></tr>`).join('');
  const rows=shown.map(p=>`<tr><td class="num">${p.status==='complete_in_extract'?p.rank:'—'}</td><td>${esc(p.province)}</td><td class="num">${p.status==='complete_in_extract'?hours(p[field]):'—'}</td><td class="num">${p.sections_reported===null?'Non determinabile':p.sections_reported}/${p.sections_expected}</td><td>${p.status==='complete_in_extract'?esc(p.last_update_local.replace('T',' ')):'Incompleta nell’estratto'}</td></tr>`).join('');
  view.innerHTML=`<div class="public-banner">Aggiornamenti degli scrutini · ${esc(event.label)}</div>
    <div class="note"><b>Che cosa misura:</b> la media e il percentile attribuiscono a ciascuna sezione l’orario <code>dt_agg</code> della sua riga comunale. Non disponiamo del timestamp della singola sezione. Il rank ordina le province complete nell’estratto, non le risorse o la qualità delle Prefetture. L’orario può includere rettifiche successive: non identifica il primo completamento.</div>
    <div class="toolbar"><label for="electoral-event">Consultazione</label><select id="electoral-event"><option value="overall">Tutte le tornate · classifica complessiva</option>${events.map(e=>`<option value="${esc(e.id)}" ${e.id===event.id?'selected':''}>${esc(e.label)}</option>`).join('')}</select>
    <label for="electoral-metric">Indicatore</label><select id="electoral-metric">${Object.entries(electoralMetrics).map(([key,label])=>`<option value="${key}" ${key===field?'selected':''}>${esc(label)}</option>`).join('')}</select>
    <label for="electoral-query">Provincia</label><input id="electoral-query" type="search" value="${esc(electoralState.query)}" placeholder="Cerca provincia"></div>
    <div class="note">${complete.length} province complete su ${event.provinces.length} nell’estratto · Mediana provinciale: ${hours(median)} ore dalla chiusura delle urne · ${missing.length} fuori classifica. ${esc(event.note)}</div>
    <div class="split"><div class="section"><div class="section-title">PRIME 20 · ${esc(electoralMetrics[field])}</div><div class="section-body"><table class="summary electoral-chart"><thead><tr><th>Provincia</th><th>Ore dalla chiusura</th><th>Ore</th></tr></thead><tbody>${chart}</tbody></table></div></div>
    <div class="section"><div class="section-title">RANK PROVINCIALE · ${shown.length} RIGHE</div><div class="section-body"><div class="gridwrap"><table class="grid electoral-grid"><thead><tr><th>Rank</th><th>Provincia</th><th>Ore</th><th>Sezioni</th><th>Ultimo aggiornamento locale</th></tr></thead><tbody>${rows||'<tr><td colspan="5">Nessuna provincia trovata.</td></tr>'}</tbody></table></div></div></div></div>
    <p class="footer-note">Fonte dei dati: <a href="${esc(event.provenance.repository)}" target="_blank" rel="noopener">onData, estratto da Eligendo</a>. Attribuzione e condizioni di riuso sono indicate nei repository di origine. Impronte SHA-256 e script di elaborazione nella <a href="https://github.com/colazeta/italian-anti-mafia-whitelist/tree/main/scripts/elections" target="_blank" rel="noopener">repository del progetto</a>. Il confronto fra consultazioni richiede di considerare l’ordine degli scrutini, le schede, il perimetro e l’orario di chiusura.</p>`;
  bindElectoralControls(view);
}

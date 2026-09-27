// The ranking concerns source update timestamps. It never ranks prefectural resources.
const electoralState={data:null,event:'eu-2024',metric:'weighted_mean_hours',query:'',error:null};
const electoralMetrics={weighted_mean_hours:'Media ponderata per sezioni',weighted_p90_hours:'90° percentile ponderato',last_hours:'Ultimo aggiornamento'};

async function renderElectoral(){
  const view=document.querySelector('#view-electoral');
  if(!electoralState.data&&!electoralState.error){
    view.innerHTML='<div class="note">Caricamento degli estratti elettorali…</div>';
    try{
      const response=await fetch('./data/electoral.json',{cache:'no-store'});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      electoralState.data=await response.json();
    }catch(error){electoralState.error=error.message}
  }
  if(electoralState.error){view.innerHTML=`<div class="note bad">Tempi elettorali non disponibili: ${esc(electoralState.error)}</div>`;return}
  const events=electoralState.data.events;
  const event=events.find(e=>e.id===electoralState.event)||events[0];
  const field=electoralState.metric;
  const complete=event.provinces.filter(p=>p.status==='complete_in_extract').sort((a,b)=>a[field]-b[field]||a.province.localeCompare(b.province,'it'));
  complete.forEach((p,i)=>p.rank=i+1);
  const missing=event.provinces.filter(p=>p.status!=='complete_in_extract');
  const q=electoralState.query.toLocaleLowerCase('it').trim();
  const shown=[...complete,...missing].filter(p=>p.province.toLocaleLowerCase('it').includes(q));
  const hours=n=>Number(n).toFixed(2).replace('.',',');
  const median=complete.length?(complete[Math.floor((complete.length-1)/2)][field]+complete[Math.floor(complete.length/2)][field])/2:null;
  const width=Math.max(...complete.slice(0,20).map(p=>p[field]),1);
  const chart=complete.slice(0,20).map(p=>`<tr><td>${esc(p.province)}</td><td class="electoral-bar-cell"><span class="electoral-bar" style="width:${(p[field]/width*100).toFixed(1)}%"></span></td><td class="num">${hours(p[field])}</td></tr>`).join('');
  const rows=shown.map(p=>`<tr><td class="num">${p.status==='complete_in_extract'?p.rank:'—'}</td><td>${esc(p.province)}</td><td class="num">${p.status==='complete_in_extract'?hours(p[field]):'—'}</td><td class="num">${p.sections_reported}/${p.sections_expected}</td><td>${p.status==='complete_in_extract'?esc(p.last_update_local.replace('T',' ')):'Incompleta nell’estratto'}</td></tr>`).join('');
  view.innerHTML=`<div class="public-banner">Aggiornamenti degli scrutini · ${esc(event.label)}</div>
    <div class="note"><b>Che cosa misura:</b> la media e il percentile attribuiscono a ciascuna sezione l’orario <code>dt_agg</code> della sua riga comunale. Non disponiamo del timestamp della singola sezione. Il rank ordina le province complete nell’estratto, non le risorse o la qualità delle Prefetture. L’orario può includere rettifiche successive: non identifica il primo completamento.</div>
    <div class="toolbar"><label for="electoral-event">Consultazione</label><select id="electoral-event">${events.map(e=>`<option value="${esc(e.id)}" ${e.id===event.id?'selected':''}>${esc(e.label)}</option>`).join('')}</select>
    <label for="electoral-metric">Indicatore</label><select id="electoral-metric">${Object.entries(electoralMetrics).map(([key,label])=>`<option value="${key}" ${key===field?'selected':''}>${esc(label)}</option>`).join('')}</select>
    <label for="electoral-query">Provincia</label><input id="electoral-query" type="search" value="${esc(electoralState.query)}" placeholder="Cerca provincia"></div>
    <div class="note">${complete.length} province complete su ${event.provinces.length} nell’estratto · Mediana provinciale: ${hours(median)} ore dalla chiusura delle urne · ${missing.length} fuori classifica. ${esc(event.note)}</div>
    <div class="split"><div class="section"><div class="section-title">PRIME 20 · ${esc(electoralMetrics[field])}</div><div class="section-body"><table class="summary electoral-chart"><thead><tr><th>Provincia</th><th>Ore dalla chiusura</th><th>Ore</th></tr></thead><tbody>${chart}</tbody></table></div></div>
    <div class="section"><div class="section-title">RANK PROVINCIALE · ${shown.length} RIGHE</div><div class="section-body"><div class="gridwrap"><table class="grid electoral-grid"><thead><tr><th>Rank</th><th>Provincia</th><th>Ore</th><th>Sezioni</th><th>Ultimo aggiornamento locale</th></tr></thead><tbody>${rows||'<tr><td colspan="5">Nessuna provincia trovata.</td></tr>'}</tbody></table></div></div></div></div>
    <p class="footer-note">Fonte dei dati: <a href="${esc(event.provenance.repository)}" target="_blank" rel="noopener">onData, estratto da Eligendo</a>. Attribuzione e condizioni di riuso sono indicate nei repository di origine. Impronte SHA-256 e script di elaborazione nella <a href="https://github.com/colazeta/italian-anti-mafia-whitelist/tree/main/scripts/elections" target="_blank" rel="noopener">repository del progetto</a>. Il confronto fra consultazioni richiede di considerare l’ordine degli scrutini, le schede, il perimetro e l’orario di chiusura.</p>`;
  view.querySelector('#electoral-event').addEventListener('change',e=>{electoralState.event=e.target.value;electoralState.query='';renderElectoral()});
  view.querySelector('#electoral-metric').addEventListener('change',e=>{electoralState.metric=e.target.value;renderElectoral()});
  view.querySelector('#electoral-query').addEventListener('input',e=>{const position=e.target.selectionStart;electoralState.query=e.target.value;renderElectoral();const input=view.querySelector('#electoral-query');input.focus();input.setSelectionRange(position,position)});
}

/* Historical read model: approved observations, not administrative events. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WhiteListHistory = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const STATUS = {
    listed:'Iscritte',
    pending:'In istruttoria',
    renewal_update_in_progress:'Aggiornamento in corso',
    renewal_requested:'Rinnovo richiesto',
    expired_observed:'Scadenza osservata',
    rejected_or_denied:'Diniego / rigetto',
    cancellation_related:'Cancellazione / cessazione',
    other_or_unknown:'Altro / non classificato'
  };
  const TYPES = {
    baseline:'Prima edizione disponibile',
    data_changed:'Dati modificati',
    file_only:'File diverso, dati invariati',
    document_changed:'Documento diverso; dettaglio non disponibile',
    parser_revision:'Revisione dell’elaborazione',
    same_document:'Stesso documento',
    unordered:'Versioni non ordinabili',
    undated:'Data dell’elenco non disponibile'
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const fmt = value => value === null || value === undefined ? '—' : new Intl.NumberFormat('it-IT').format(value);
  const signed = value => value === null || value === undefined ? '—' : `${value > 0 ? '+' : ''}${fmt(value)}`;
  const dateLabel = value => value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('/') : 'Data non disponibile';
  const scope = e => JSON.stringify([e.authority_key,e.register_key,e.population_scope,e.source_key]);
  const count = (edition, status='all') => status === 'all' ? edition.total : edition.status_counts[status] || 0;
  const days = (a,b) => a && b ? Math.round((Date.parse(`${b}T00:00:00Z`)-Date.parse(`${a}T00:00:00Z`))/86400000) : null;
  const median = values => {
    if (!values.length) return null;
    const a=[...values].sort((x,y)=>x-y), i=Math.floor(a.length/2);
    return a.length%2 ? a[i] : (a[i-1]+a[i])/2;
  };

  function group(editions) {
    const result = new Map();
    for (const e of editions) {
      const key=scope(e);
      if(!result.has(key)) result.set(key,[]);
      result.get(key).push(e);
    }
    return result;
  }
  function inPeriod(date, state) {
    return (!state.from && !state.to) || (!!date && (!state.from || date>=state.from) && (!state.to || date<=state.to));
  }
  function scoped(editions, state) {
    return editions.filter(e =>
      (state.authority==='all'||e.authority_key===state.authority) &&
      (state.register==='all'||e.register_key===state.register) &&
      (state.source==='all'||scope(e)===state.source)
    );
  }
  function comparison(history, a, b) {
    if(!a || !b || scope(a)!==scope(b) || !a.reference_date || !b.reference_date || a.reference_date>=b.reference_date) return null;
    if(a.parser_signature!==b.parser_signature) return null;
    const found=history.comparisons.filter(c=>c.before_id===a.id && c.after_id===b.id);
    return found.find(c=>c.basis==='frozen_observational_diff') || found[0] || null;
  }
  function eventType(a,b) {
    if(!b.reference_date) return 'undated';
    if(!a) return 'baseline';
    if(a.document_sha256===b.document_sha256) return a.parser_signature===b.parser_signature?'same_document':'parser_revision';
    if(a.parser_signature!==b.parser_signature) return 'parser_revision';
    if(a.data_fingerprint && b.data_fingerprint) return a.data_fingerprint===b.data_fingerprint?'file_only':'data_changed';
    return 'document_changed';
  }
  function events(history, editions=history.editions) {
    const output=[];
    for(const series of group(editions).values()) {
      const byDate=new Map();
      for(const e of series) {
        const date=e.reference_date||'';
        if(!byDate.has(date)) byDate.set(date,[]);
        byDate.get(date).push(e);
      }
      let previous=null;
      for(const [date,versions] of [...byDate].sort(([a],[b])=>a.localeCompare(b))) {
        if(!date || versions.length!==1) {
          versions.forEach(e=>output.push({before:null,after:e,type:date?'unordered':'undated',gap:null,delta:null,comparison:null}));
          previous=null;
          continue;
        }
        const after=versions[0], diff=comparison(history,previous,after);
        let type=eventType(previous,after);
        if(type==='document_changed' && diff && (diff.added||diff.disappeared||diff.content_changed)) type='data_changed';
        output.push({before:previous,after,type,gap:previous?days(previous.reference_date,after.reference_date):null,delta:previous?after.total-previous.total:null,comparison:diff});
        previous=after;
      }
    }
    return output.sort((a,b)=>(a.after.reference_date||'').localeCompare(b.after.reference_date||'') || a.after.authority_name.localeCompare(b.after.authority_name,'it') || a.after.id.localeCompare(b.after.id));
  }
  function asOf(editions, cutoff) {
    const selected=[],missing=[],ambiguous=[];
    for(const [key,series] of group(editions)) {
      const candidates=series.filter(e=>e.reference_date && (!cutoff||e.reference_date<=cutoff));
      if(!candidates.length){missing.push(key);continue;}
      const latest=candidates.reduce((m,e)=>e.reference_date>m?e.reference_date:m,'');
      const versions=candidates.filter(e=>e.reference_date===latest);
      if(versions.length!==1) ambiguous.push(key); else selected.push(versions[0]);
    }
    return {selected,missing,ambiguous};
  }
  function frequency(history, editions, state) {
    const all=events(history,editions), result=[];
    for(const [key,series] of group(editions)) {
      const changes=[],gaps=[];
      let lastDocument=null;
      for(const event of all.filter(e=>scope(e.after)===key)) {
        if(['unordered','undated'].includes(event.type)){lastDocument=null;continue;}
        if(!lastDocument){lastDocument=event.after;continue;}
        if(event.after.document_sha256===lastDocument.document_sha256) continue;
        const gap=days(lastDocument.reference_date,event.after.reference_date);
        if(gap>0 && inPeriod(event.after.reference_date,state)){changes.push(event);gaps.push(gap);}
        lastDocument=event.after;
      }
      const visible=series.filter(e=>inPeriod(e.reference_date,state));
      const checks=history.checks.filter(c=>series.some(e=>e.id===c.edition_id));
      result.push({
        key,edition:series[0],editions:visible.length,changes:changes.length,gaps,
        median:gaps.length>=2?median(gaps):null,
        first:visible.map(e=>e.reference_date).filter(Boolean).sort()[0]||null,
        last:visible.map(e=>e.reference_date).filter(Boolean).sort().at(-1)||null,
        latestCheck:checks.map(c=>c.checked_at).sort().at(-1)||null
      });
    }
    return result.filter(x=>x.editions).sort((a,b)=>a.edition.authority_name.localeCompare(b.edition.authority_name,'it')||a.edition.source_key.localeCompare(b.edition.source_key));
  }
  function csv(rows) {
    if(!rows.length) return '';
    const keys=Object.keys(rows[0]);
    const cell=v=>{
      let text=String(v??'');
      if(typeof v==='string' && /^[=+@\-\t\r]/.test(text)) text="'"+text;
      return '"'+text.replace(/"/g,'""')+'"';
    };
    return [keys,...rows.map(r=>keys.map(k=>r[k]))].map(row=>row.map(cell).join(',')).join('\r\n');
  }

  function uniqueDated(series) {
    const byDate=new Map();
    for(const e of series) {
      if(!e.reference_date) continue;
      if(!byDate.has(e.reference_date)) byDate.set(e.reference_date,[]);
      byDate.get(e.reference_date).push(e);
    }
    return [...byDate.entries()]
      .filter(([,versions])=>versions.length===1)
      .sort(([a],[b])=>a.localeCompare(b))
      .map(([,versions])=>versions[0]);
  }
  function latestComparablePair(series) {
    const editions=uniqueDated(series);
    if(!editions.length) return {before:null,after:null};
    const after=editions.at(-1);
    let before=null;
    for(let i=editions.length-2;i>=0;i--) {
      const candidate=editions[i];
      if(candidate.parser_signature!==after.parser_signature) continue;
      if(candidate.document_sha256===after.document_sha256) continue;
      before=candidate;
      break;
    }
    return {before,after};
  }

  function createController({history,historyRoot}) {
    const root=document.querySelector(historyRoot);
    const authorityMap=new Map();
    for(const e of history.editions) {
      if(!authorityMap.has(e.authority_key)) authorityMap.set(e.authority_key,e.authority_name);
    }
    const authorityScores=[...authorityMap].map(([key,name])=>{
      const editions=history.editions.filter(e=>e.authority_key===key);
      const comparable=[...group(editions).values()].filter(series=>latestComparablePair(series).before).length;
      return {key,name,comparable,editions:editions.length};
    }).sort((a,b)=>b.comparable-a.comparable||b.editions-a.editions||a.name.localeCompare(b.name,'it'));
    const state={authority:authorityScores[0]?.key||'all',series:''};

    const section=(title,body)=>`<div class="section"><div class="section-title">${esc(title)}</div><div class="section-body">${body}</div></div>`;
    const option=(v,n,current)=>`<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(n)}</option>`;
    const link=(url,text)=>url?.startsWith('https://')?`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}</a>`:'—';
    const seriesName=e=>`${e.register_name} · ${e.source_key}`;

    function selectedEditions(){
      return history.editions.filter(e=>e.authority_key===state.authority);
    }
    function selectedSeries(){
      return [...group(selectedEditions())].map(([key,series])=>({key,series:[...series].sort((a,b)=>(a.reference_date||'').localeCompare(b.reference_date||''))}))
        .sort((a,b)=>seriesName(a.series[0]).localeCompare(seriesName(b.series[0]),'it'));
    }
    function ensureSeries(groups){
      if(groups.some(g=>g.key===state.series)) return;
      const preferred=groups.find(g=>latestComparablePair(g.series).before) || groups[0];
      state.series=preferred?.key||'';
    }
    function deltaRows(before,after) {
      const statuses=Object.keys(STATUS).filter(k=>(before.status_counts[k]||0)||(after.status_counts[k]||0));
      return [
        `<tr><th scope="row">Tutte le presenze</th><td class="num">${fmt(before.total)}</td><td class="num">${fmt(after.total)}</td><td class="num"><b>${signed(after.total-before.total)}</b></td></tr>`,
        ...statuses.map(k=>`<tr><th scope="row">${esc(STATUS[k])}</th><td class="num">${fmt(before.status_counts[k]||0)}</td><td class="num">${fmt(after.status_counts[k]||0)}</td><td class="num">${signed((after.status_counts[k]||0)-(before.status_counts[k]||0))}</td></tr>`)
      ].join('');
    }
    function seriesTable(groups) {
      const rows=groups.map(({key,series})=>{
        const pair=latestComparablePair(series), selected=key===state.series;
        if(!pair.after) return '';
        const interval=pair.before?days(pair.before.reference_date,pair.after.reference_date):null;
        const delta=pair.before?pair.after.total-pair.before.total:null;
        return `<tr class="${selected?'history-selected':''}">
          <th scope="row">${esc(seriesName(pair.after))}</th>
          <td>${pair.before?esc(dateLabel(pair.before.reference_date)):'—'}</td>
          <td>${esc(dateLabel(pair.after.reference_date))}</td>
          <td class="num">${fmt(interval)}</td>
          <td class="num">${pair.before?fmt(pair.before.total):'—'}</td>
          <td class="num">${fmt(pair.after.total)}</td>
          <td class="num">${pair.before?signed(delta):'—'}</td>
          <td><button class="btn" type="button" data-h-series="${esc(key)}">${selected?'Selezionato':'Apri'}</button></td>
        </tr>`;
      }).join('');
      return `<div class="gridwrap"><table class="grid history-series-table"><thead><tr><th>Registro / elenco</th><th>Edizione precedente</th><th>Ultima edizione</th><th>Giorni</th><th>Presenze A</th><th>Presenze B</th><th>Delta</th><th></th></tr></thead><tbody>${rows||'<tr><td colspan="8">Nessuna edizione disponibile.</td></tr>'}</tbody></table></div>`;
    }
    function detail(groups) {
      const selected=groups.find(g=>g.key===state.series);
      if(!selected) return section('DELTA', '<p>Nessun elenco disponibile per la Prefettura selezionata.</p>');
      const pair=latestComparablePair(selected.series), after=pair.after;
      if(!after) return section(`DELTA — ${seriesName(selected.series[0])}`, '<p>Non sono disponibili edizioni datate confrontabili.</p>');
      if(!pair.before) {
        return section(`DELTA — ${seriesName(after)}`, `<div class="note">Per questo elenco è disponibile una sola edizione comparabile. Il delta non viene stimato né sostituito con zero.</div><p class="history-source-line">Ultima fonte: ${link(after.resource_url,'consulta l’elenco ufficiale')}.</p>`);
      }
      const before=pair.before;
      const evidence=comparison(history,before,after);
      const type=eventType(before,after);
      const statusTable=`<div class="gridwrap"><table class="summary history-delta"><thead><tr><th>Indicatore</th><th>Edizione A<br>${esc(dateLabel(before.reference_date))}</th><th>Edizione B<br>${esc(dateLabel(after.reference_date))}</th><th>Delta</th></tr></thead><tbody>${deltaRows(before,after)}</tbody></table></div>`;
      let observed;
      if(evidence) {
        observed=`<table class="summary history-delta"><tbody>
          <tr><th>Nuove presenze osservate nell’elenco</th><td class="num">${fmt(evidence.added)}</td></tr>
          <tr><th>Presenze non più osservate</th><td class="num">${fmt(evidence.disappeared)}</td></tr>
          <tr><th>Righe comuni modificate</th><td class="num">${fmt(evidence.content_changed)}</td></tr>
          <tr><th>di cui: cambi di stato</th><td class="num">${fmt(evidence.status_changed)}</td></tr>
        </tbody></table>`;
      } else {
        observed='<div class="note">Per questa coppia è disponibile il delta delle consistenze, ma non un confronto riga-per-riga approvato. Le entrate e le uscite osservate restano quindi non disponibili.</div>';
      }
      return section(`DELTA — ${seriesName(after)}`,
        `<p><b>${esc(TYPES[type])}.</b> Confronto tra le ultime due edizioni comparabili della stessa serie (${fmt(days(before.reference_date,after.reference_date))} giorni).</p>`+
        statusTable+
        `<p><b>Dettaglio osservazionale</b></p>${observed}`+
        `<div class="note"><b>Come leggere il delta:</b> descrive differenze tra due elenchi pubblicati. “Nuova presenza” e “non più osservata” non equivalgono automaticamente a nuova iscrizione o cancellazione amministrativa. I cambi di stato sono inclusi nelle righe modificate.</div>`+
        `<p class="history-source-line">Fonte A: ${link(before.resource_url,'elenco precedente')} · Fonte B: ${link(after.resource_url,'elenco più recente')}.</p>`
      );
    }
    function editionsTable(editions) {
      const rows=[...editions].sort((a,b)=>(b.reference_date||'').localeCompare(a.reference_date||'')||seriesName(a).localeCompare(seriesName(b),'it')).map(e=>
        `<tr><td>${esc(seriesName(e))}</td><td>${esc(dateLabel(e.reference_date))}</td><td class="num">${fmt(e.total)}</td><td>${link(e.resource_url,'Elenco ufficiale')}</td></tr>`
      ).join('');
      return `<div class="gridwrap"><table class="grid history-editions-table"><thead><tr><th>Registro / elenco</th><th>Data dell’edizione</th><th>Presenze</th><th>Fonte</th></tr></thead><tbody>${rows||'<tr><td colspan="4">Nessuna edizione archiviata.</td></tr>'}</tbody></table></div>`;
    }
    function bind() {
      root.querySelector('#h-authority')?.addEventListener('change',e=>{
        state.authority=e.target.value;
        state.series='';
        renderHistory();
      });
      root.querySelectorAll('[data-h-series]').forEach(button=>button.addEventListener('click',()=>{
        state.series=button.dataset.hSeries;
        renderHistory();
        root.querySelector('.history-delta')?.scrollIntoView({block:'nearest'});
      }));
    }
    function renderHistory() {
      if(!root) return;
      const editions=selectedEditions(), groups=selectedSeries();
      ensureSeries(groups);
      const authorityName=authorityMap.get(state.authority)||'Prefettura';
      root.innerHTML=
        `<div class="note"><b>Storico per Prefettura.</b> Questa pagina confronta le edizioni archiviate degli elenchi pubblicati. Il delta riguarda le presenze osservate nelle fonti, non provvedimenti amministrativi.</div>`+
        section('PREFETTURA',`<div class="toolbar history-prefecture-select"><label for="h-authority">Seleziona</label><select id="h-authority">${authorityScores.map(a=>option(a.key,a.name,state.authority)).join('')}</select></div><p>${esc(authorityName)} · ${fmt(editions.length)} edizioni archiviate · ${fmt(groups.length)} serie di elenchi.</p>`)+
        section('ULTIME EDIZIONI E DELTA',`<p>Per ogni elenco viene confrontata l’ultima edizione con la precedente edizione compatibile. Serie diverse non vengono sommate tra loro.</p>${seriesTable(groups)}`)+
        detail(groups)+
        section('EDIZIONI ARCHIVIATE',`<p>Elenco cronologico delle edizioni conservate per la Prefettura selezionata.</p>${editionsTable(editions)}`);
      bind();
    }
    function renderUpdates() { /* Kept as a no-op for backwards compatibility with app initialisation. */ }
    return {renderHistory,renderUpdates,state};
  }

  return {scope,count,days,median,events,asOf,frequency,comparison,csv,createController,latestComparablePair};
});

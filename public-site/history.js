/* Historical read model: approved observations, not administrative events. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WhiteListHistory = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const STATUS = {listed:'Iscritte',pending:'In istruttoria',renewal_update_in_progress:'Aggiornamento in corso',renewal_requested:'Rinnovo richiesto',expired_observed:'Scadenza osservata',rejected_or_denied:'Diniego / rigetto',cancellation_related:'Cancellazione / cessazione',other_or_unknown:'Altro / non classificato'};
  const TYPES = {baseline:'Prima edizione disponibile',data_changed:'Dati modificati',file_only:'File diverso, dati invariati',document_changed:'Documento diverso; dettaglio non disponibile',parser_revision:'Revisione dell’elaborazione',same_document:'Stesso documento',unordered:'Versioni non ordinabili',undated:'Data dell’elenco non disponibile'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
  const fmt = value => value === null || value === undefined ? '—' : new Intl.NumberFormat('it-IT').format(value);
  const signed = value => value === null || value === undefined ? '—' : `${value > 0 ? '+' : ''}${fmt(value)}`;
  const dateLabel = value => value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('/') : 'Data non disponibile';
  const timeLabel = value => value ? `${dateLabel(value.slice(0,10))} ${value.slice(11,19)} UTC` : 'Non disponibile';
  const scope = e => JSON.stringify([e.authority_key,e.register_key,e.population_scope,e.source_key]);
  const count = (edition, status='all') => status === 'all' ? edition.total : edition.status_counts[status] || 0;
  const days = (a,b) => a && b ? Math.round((Date.parse(`${b}T00:00:00Z`)-Date.parse(`${a}T00:00:00Z`))/86400000) : null;
  const median = values => { if (!values.length) return null; const a=[...values].sort((x,y)=>x-y), i=Math.floor(a.length/2); return a.length%2 ? a[i] : (a[i-1]+a[i])/2; };
  function group(editions) {
    const result = new Map();
    for (const e of editions) { const key=scope(e); if(!result.has(key))result.set(key,[]); result.get(key).push(e); }
    return result;
  }
  function inPeriod(date, state) {
    return (!state.from && !state.to) || (!!date && (!state.from || date>=state.from) && (!state.to || date<=state.to));
  }
  function scoped(editions, state) {
    return editions.filter(e => (state.authority==='all'||e.authority_key===state.authority) && (state.register==='all'||e.register_key===state.register) && (state.source==='all'||scope(e)===state.source));
  }
  function comparison(history, a, b) {
    if(!a || !b || scope(a)!==scope(b) || !a.reference_date || !b.reference_date || a.reference_date>=b.reference_date)return null;
    if(a.parser_signature!==b.parser_signature)return null;
    const found=history.comparisons.filter(c=>c.before_id===a.id && c.after_id===b.id);
    return found.find(c=>c.basis==='frozen_observational_diff') || found[0] || null;
  }
  function eventType(a,b) {
    if(!b.reference_date)return 'undated';
    if(!a)return 'baseline';
    if(a.document_sha256===b.document_sha256)return a.parser_signature===b.parser_signature?'same_document':'parser_revision';
    if(a.parser_signature!==b.parser_signature)return 'parser_revision';
    if(a.data_fingerprint && b.data_fingerprint)return a.data_fingerprint===b.data_fingerprint?'file_only':'data_changed';
    return 'document_changed';
  }
  function events(history, editions=history.editions) {
    const output=[];
    for(const series of group(editions).values()) {
      const byDate=new Map();
      for(const e of series) {const date=e.reference_date||''; if(!byDate.has(date))byDate.set(date,[]);byDate.get(date).push(e);}
      let previous=null;
      for(const [date,versions] of [...byDate].sort(([a],[b])=>a.localeCompare(b))) {
        if(!date || versions.length!==1) {
          versions.forEach(e=>output.push({before:null,after:e,type:date?'unordered':'undated',gap:null,delta:null,comparison:null}));
          previous=null;
          continue;
        }
        const after=versions[0], diff=comparison(history,previous,after);
        let type=eventType(previous,after);
        if(type==='document_changed' && diff && (diff.added||diff.disappeared||diff.content_changed))type='data_changed';
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
      if(versions.length!==1)ambiguous.push(key);else selected.push(versions[0]);
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
        if(event.after.document_sha256===lastDocument.document_sha256)continue;
        const gap=days(lastDocument.reference_date,event.after.reference_date);
        if(gap>0 && inPeriod(event.after.reference_date,state)){changes.push(event);gaps.push(gap);}
        lastDocument=event.after;
      }
      const visible=series.filter(e=>inPeriod(e.reference_date,state));
      const checks=history.checks.filter(c=>series.some(e=>e.id===c.edition_id));
      result.push({key,edition:series[0],editions:visible.length,changes:changes.length,gaps,median:gaps.length>=2?median(gaps):null,first:visible.map(e=>e.reference_date).filter(Boolean).sort()[0]||null,last:visible.map(e=>e.reference_date).filter(Boolean).sort().at(-1)||null,latestCheck:checks.map(c=>c.checked_at).sort().at(-1)||null});
    }
    return result.filter(x=>x.editions).sort((a,b)=>a.edition.authority_name.localeCompare(b.edition.authority_name,'it')||a.edition.source_key.localeCompare(b.edition.source_key));
  }
  function csv(rows) {
    if(!rows.length)return '';
    const keys=Object.keys(rows[0]);
    const cell=v=>{let text=String(v??'');if(typeof v==='string' && /^[=+@\-\t\r]/.test(text))text="'"+text;return '"'+text.replace(/"/g,'""')+'"';};
    return [keys,...rows.map(r=>keys.map(k=>r[k]))].map(row=>row.map(cell).join(',')).join('\r\n');
  }
  function createController({history,registry,site,historyRoot,updatesRoot,onRecord,onHistory}) {
    const allGroups=group(history.editions);
    const preferred=[...allGroups.values()].sort((a,b)=>b.length-a.length || a[0].authority_name.localeCompare(b[0].authority_name,'it'))[0];
    const state={authority:preferred?.[0].authority_key||'all',register:'all',source:'all',from:'',to:'',status:'all',asof:'',mode:'series',percent:false,type:'all',minDelta:'',minGap:'',before:'',after:'',query:'',page:1,recordsOpen:false};
    let roots={history:document.querySelector(historyRoot),updates:document.querySelector(updatesRoot)};
    const label=e=>`${e.authority_name} · ${e.register_name} · ${e.source_key}`;
    const section=(title,body)=>`<div class="section"><h2 class="section-title">${esc(title)}</h2><div class="section-body">${body}</div></div>`;
    const option=(v,n,current)=>`<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(n)}</option>`;
    const link=(url,text)=>url?.startsWith('https://')?`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(text)}</a>`:'—';
    const table=(heads,rows,cls='')=>`<div class="gridwrap ${cls}"><table class="grid"><thead><tr>${heads.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')||`<tr><td colspan="${heads.length}">Nessun dato nella selezione.</td></tr>`}</tbody></table></div>`;
    function options(editions,key,name) {return [...new Map(editions.map(e=>[e[key],e[name]])).entries()].sort((a,b)=>a[1].localeCompare(b[1],'it'));}
    function normaliseScope() {
      const a=history.editions.filter(e=>state.authority==='all'||e.authority_key===state.authority);
      if(state.register!=='all'&&!a.some(e=>e.register_key===state.register))state.register='all';
      const r=a.filter(e=>state.register==='all'||e.register_key===state.register);
      if(state.source!=='all'&&!r.some(e=>scope(e)===state.source))state.source='all';
    }
    function filters(prefix,updates=false) {
      const a=history.editions.filter(e=>state.authority==='all'||e.authority_key===state.authority);
      const r=a.filter(e=>state.register==='all'||e.register_key===state.register);
      return `<div class="toolbar history-filters">
        <label for="${prefix}-authority">Prefettura</label><select id="${prefix}-authority" data-h-field="authority">${option('all','Tutte',state.authority)}${options(history.editions,'authority_key','authority_name').map(([k,n])=>option(k,n,state.authority)).join('')}</select>
        <label for="${prefix}-register">Registro</label><select id="${prefix}-register" data-h-field="register">${option('all','Tutti',state.register)}${options(a,'register_key','register_name').map(([k,n])=>option(k,n+' · '+k,state.register)).join('')}</select>
        <label for="${prefix}-source">Elenco</label><select id="${prefix}-source" data-h-field="source">${option('all','Tutti gli elenchi',state.source)}${[...group(r)].map(([k,v])=>option(k,v[0].source_key,state.source)).join('')}</select>
        <label for="${prefix}-from">Dal</label><input id="${prefix}-from" type="date" data-h-field="from" value="${esc(state.from)}">
        <label for="${prefix}-to">Al</label><input id="${prefix}-to" type="date" data-h-field="to" value="${esc(state.to)}">
        <label for="${prefix}-status">Stato</label><select id="${prefix}-status" data-h-field="status">${option('all','Tutti gli stati',state.status)}${Object.entries(STATUS).map(([k,n])=>option(k,n,state.status)).join('')}</select>
        <button class="btn" data-h-reset>Reimposta</button><button class="btn" data-h-export="csv">CSV filtrato</button><button class="btn" data-h-export="json">JSON filtrato</button>
      </div>${updates?`<div class="toolbar"><label for="${prefix}-type">Tipo di variazione</label><select id="${prefix}-type" data-h-field="type">${option('all','Tutti',state.type)}${Object.entries(TYPES).map(([k,n])=>option(k,n,state.type)).join('')}</select><label for="${prefix}-delta">Saldo assoluto minimo</label><input id="${prefix}-delta" data-h-field="minDelta" type="number" min="0" step="1" value="${esc(state.minDelta)}"><label for="${prefix}-gap">Intervallo minimo (giorni)</label><input id="${prefix}-gap" data-h-field="minGap" type="number" min="0" step="1" value="${esc(state.minGap)}"></div>`:''}`;
    }
    function viewData() {
      normaliseScope();
      const base=scoped(history.editions,state);
      const visible=base.filter(e=>inPeriod(e.reference_date,state));
      const eventRows=events(history,base).filter(e=>inPeriod(e.after.reference_date,state))
        .filter(e=>state.type==='all'||e.type===state.type)
        .filter(e=>state.minDelta===''||(e.before && Math.abs(count(e.after,state.status)-count(e.before,state.status))>=Number(state.minDelta)))
        .filter(e=>state.minGap===''||(e.gap!==null&&e.gap>=Number(state.minGap)));
      return {base,visible,eventRows};
    }
    function download(kind,view) {
      const {base,visible,eventRows}=viewData();
      const snapshot=state.mode==='asof'?asOf(base,state.asof||state.to):null;
      const selected=view==='updates'?eventRows.map(e=>e.after):(snapshot?snapshot.selected:visible);
      const ids=new Set(selected.map(e=>e.id));
      const changes=eventRows.map(e=>({prefettura:e.after.authority_name,registro:e.after.register_name,elenco:e.after.source_key,data_precedente:e.before?.reference_date||null,data_successiva:e.after.reference_date,tipo:e.type,intervallo_giorni:e.gap,stato:state.status,prima:e.before?count(e.before,state.status):null,dopo:count(e.after,state.status),saldo:e.before?count(e.after,state.status)-count(e.before,state.status):null,nuove_presenze_intero_elenco:e.comparison?.added??null,non_piu_rilevate_intero_elenco:e.comparison?.disappeared??null,cambi_stato_intero_elenco:e.comparison?.status_changed??null}));
      const rows=view==='updates'?changes:selected.map(e=>({prefettura:e.authority_name,registro:e.register_name,elenco:e.source_key,data_elenco:e.reference_date,stato:state.status,presenze:count(e,state.status),presenze_totali:e.total,sha256:e.document_sha256,parser:e.parser_signature,fonte:e.resource_url}));
      const payload=kind==='csv'?csv(rows):JSON.stringify({unit:'source observations, not distinct companies or administrative events',view,filters:{...state,query:undefined},rows,editions:selected,checks:history.checks.filter(c=>ids.has(c.edition_id)),comparisons:history.comparisons.filter(c=>ids.has(c.after_id)),missing_scopes:snapshot?.missing||[],ambiguous_scopes:snapshot?.ambiguous||[]},null,2);
      const url=URL.createObjectURL(new Blob([kind==='csv'?'\ufeff'+payload:payload],{type:kind==='csv'?'text/csv;charset=utf-8':'application/json'}));
      const a=document.createElement('a');a.href=url;a.download=`whitelist-${view}-filtrato.${kind}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    function bind(root) {
      root.querySelectorAll('[data-h-field]').forEach(el=>el.addEventListener('change',()=>{
        state[el.dataset.hField]=el.type==='checkbox'?el.checked:el.value;
        if(el.dataset.hField==='authority'){state.register='all';state.source='all';}
        if(['authority','register','source','from','to'].includes(el.dataset.hField)){state.before='';state.after='';}
        state.page=1;drawBoth();
      }));
      root.querySelectorAll('[data-h-reset]').forEach(el=>el.addEventListener('click',()=>{Object.assign(state,{authority:'all',register:'all',source:'all',from:'',to:'',status:'all',type:'all',minDelta:'',minGap:'',before:'',after:'',asof:'',mode:'series',query:'',page:1});drawBoth();}));
      root.querySelectorAll('[data-h-export]').forEach(el=>el.addEventListener('click',()=>download(el.dataset.hExport,root===roots.updates?'updates':'history')));
      root.querySelectorAll('[data-h-edition]').forEach(el=>{
        const open=()=>{const edition=history.editions.find(e=>e.id===el.dataset.hEdition);if(!edition)return;state.source=scope(edition);state.authority=edition.authority_key;state.register=edition.register_key;state.after=edition.id;state.before='';state.page=1;drawBoth();onHistory?.();roots.history.querySelector('#h-comparison')?.scrollIntoView({block:'nearest'});};
        el.addEventListener('click',open);
        if(el.tagName.toLowerCase()!=='button')el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
      });
      root.querySelectorAll('[data-h-record]').forEach(el=>el.addEventListener('click',()=>onRecord?.(el.dataset.hRecord)));
      root.querySelectorAll('[data-h-page]').forEach(el=>el.addEventListener('click',()=>{state.page+=Number(el.dataset.hPage);state.recordsOpen=true;drawBoth();}));
      const search=root.querySelector('[data-h-query]');
      search?.addEventListener('input',()=>{const pos=search.selectionStart;state.query=search.value;state.recordsOpen=true;state.page=1;renderHistory();const next=roots.history.querySelector('[data-h-query]');next.focus();next.setSelectionRange(pos,pos);});
    }
    function invalid(root,prefix,updates=false) {
      if(state.from && state.to && state.from>state.to){root.innerHTML=section('Filtri',filters(prefix,updates))+'<div class="note bad" role="alert">La data iniziale deve precedere quella finale.</div>';bind(root);return true;}return false;
    }
    function calendar(editions) {
      const dated=editions.filter(e=>e.reference_date), dates=dated.map(e=>Date.parse(e.reference_date+'T00:00:00Z'));
      const min=Math.min(...dates), max=Math.max(...dates), span=Math.max(1,max-min);
      const rows=[...group(editions).values()].map(series=>{
        const marks=series.filter(e=>e.reference_date).map(e=>{
          const x=18+564*(Date.parse(e.reference_date+'T00:00:00Z')-min)/span;
          return `<g role="button" tabindex="0" data-h-edition="${esc(e.id)}" aria-label="${esc(dateLabel(e.reference_date))}: ${fmt(count(e,state.status))} presenze, apri confronto"><circle cx="${x}" cy="17" r="6"/><title>${esc(dateLabel(e.reference_date))} · ${fmt(count(e,state.status))} presenze</title></g>`;
        }).join('');
        return `<tr><th scope="row">${esc(label(series[0]))}</th><td><svg class="history-timeline" viewBox="0 0 600 34" aria-label="Edizioni archiviate di ${esc(series[0].source_key)}"><path d="M18 17 H582" class="history-axis"/>${marks}</svg></td><td>${fmt(series.filter(e=>!e.reference_date).length)} senza data</td></tr>`;
      });
      return `<p>Ogni punto è un’edizione conservata nell’archivio; non prova che siano state osservate tutte le pubblicazioni. Seleziona un punto per il confronto. ${dated.length?`${dateLabel(new Date(min).toISOString().slice(0,10))} — ${dateLabel(new Date(max).toISOString().slice(0,10))}.`:''}</p>`+table(['Elenco','Data dell’edizione (scala comune)','Date mancanti'],rows,'history-scroll');
    }
    function distribution(editions) {
      const max=Math.max(1,...editions.map(e=>e.total));
      const ordered=[...editions].sort((a,b)=>label(a).localeCompare(label(b),'it')||(a.reference_date||'').localeCompare(b.reference_date||''));
      const selectedStatuses=state.status==='all'?Object.keys(STATUS):[state.status];
      const rows=ordered.map(e=>{
        const bars=selectedStatuses.filter(k=>e.status_counts[k]).map(k=>{
          const n=e.status_counts[k],width=100*n/(state.percent?(e.total||1):max);
          return `<span class="history-segment history-state-${esc(k)}" style="width:${width}%" title="${esc(STATUS[k])}: ${fmt(n)} (${e.total?(100*n/e.total).toFixed(2):'0'}%)"><span class="sr-only">${esc(STATUS[k])}: ${fmt(n)}. </span></span>`;
        }).join('');
        return `<tr><th scope="row"><button class="btn history-plain" data-h-edition="${esc(e.id)}">${esc(dateLabel(e.reference_date))}</button><div class="muted small">${esc(label(e))}</div></th><td><div class="history-stack" role="img" aria-label="${esc(selectedStatuses.map(k=>`${STATUS[k]}: ${e.status_counts[k]||0}`).join('; '))}">${bars}</div></td><td class="numeric">${fmt(count(e,state.status))}</td><td class="numeric">${e.total?(100*count(e,state.status)/e.total).toFixed(2).replace('.',',')+'%':'—'}</td></tr>`;
      });
      return `<div class="toolbar"><label for="h-percent"><input id="h-percent" data-h-field="percent" type="checkbox" ${state.percent?'checked':''}> Scala percentuale</label></div><p>Una barra per edizione, senza sommare date diverse. Le percentuali hanno come denominatore tutte le presenze della rispettiva edizione, anche con un filtro di stato.</p><div class="history-legend">${selectedStatuses.map(k=>`<span><i class="history-state-${esc(k)}"></i>${esc(STATUS[k])}</span>`).join('')}</div>`+table(['Edizione / elenco','Distribuzione per stato','Presenze selezionate','Quota dell’edizione'],rows,'history-scroll');
    }
    function sourceTable(editions) {
      return table(['Prefettura / registro','Elenco','Data dell’elenco','Presenze selezionate','Fonte'],editions.map(e=>`<tr><td>${esc(e.authority_name)}<div class="small">${esc(e.register_name)}</div></td><td>${esc(e.source_key)}</td><td>${esc(dateLabel(e.reference_date))}</td><td>${fmt(count(e,state.status))}</td><td>${link(e.resource_url,'Elenco ufficiale')}<div class="small mono">SHA-256: ${esc(e.document_sha256.slice(0,16))}…</div></td></tr>`));
    }
    function comparisonPanel(base,visible) {
      const groups=group(base);
      if(groups.size!==1)return '<p>Seleziona un elenco o un punto nel calendario per confrontare due sue edizioni. Elenchi distinti non vengono uniti artificialmente.</p>';
      const series=[...groups.values()][0].filter(e=>e.reference_date).sort((a,b)=>a.reference_date.localeCompare(b.reference_date)||a.id.localeCompare(b.id));
      if(!series.length)return '<p>Non ci sono edizioni con una data completa. Nessuna cronologia viene inventata.</p>';
      const choices=series.filter(e=>visible.some(v=>v.id===e.id));
      if(!choices.length)return '<p>Nessuna edizione nell’intervallo selezionato.</p>';
      let after=choices.find(e=>e.id===state.after)||choices.at(-1);
      state.after=after.id;
      const earlier=series.filter(e=>e.reference_date<after.reference_date);
      const latest=earlier.at(-1)?.reference_date;
      const lastVersions=earlier.filter(e=>e.reference_date===latest);
      const before=earlier.find(e=>e.id===state.before)||(lastVersions.length===1?lastVersions[0]:null);
      state.before=before?.id||'';
      const name=e=>`${dateLabel(e.reference_date)} · ${e.document_sha256.slice(0,8)} · ${e.parser_signature}`;
      const selectors=`<div class="toolbar"><label for="h-before">Edizione precedente (A)</label><select id="h-before" data-h-field="before">${option('','Seleziona',state.before)}${earlier.map(e=>option(e.id,name(e),state.before)).join('')}</select><label for="h-after">Edizione successiva (B)</label><select id="h-after" data-h-field="after">${choices.map(e=>option(e.id,name(e),state.after)).join('')}</select></div>`;
      const sources=`<p>${before?`A: ${link(before.resource_url,'documento ufficiale')} · `:''}B: ${link(after.resource_url,'documento ufficiale')}. Gli URL ufficiali possono cambiare: le impronte identificano i documenti confrontati.</p>`;
      if(!before)return selectors+'<div class="note">Una sola edizione confrontabile, oppure più versioni precedenti non ordinabili. Seleziona A quando disponibile; il delta resta non disponibile, non zero.</div>'+sources+recordsPanel(after);
      const evidence=comparison(history,before,after), interval=days(before.reference_date,after.reference_date), totalDelta=count(after,state.status)-count(before,state.status);
      const percentage=count(before,state.status)?100*totalDelta/count(before,state.status):null;
      const fullMeasure=(n)=>fmt(n);
      const metrics=`<div class="history-metrics"><div><span>Intervallo tra le due date</span><strong>${fmt(interval)} giorni</strong></div><div><span>Saldo presenze · ${esc(state.status==='all'?'tutti gli stati':STATUS[state.status])}</span><strong>${signed(totalDelta)}</strong><small>${percentage===null?'Percentuale non definita su base zero':signed(Number(percentage.toFixed(2)))+'% rispetto ad A'}</small></div><div><span>Nuove presenze · intero elenco</span><strong>${fullMeasure(evidence?.added)}</strong></div><div><span>Non più rilevate · intero elenco</span><strong>${fullMeasure(evidence?.disappeared)}</strong></div><div><span>Righe comuni modificate</span><strong>${fullMeasure(evidence?.content_changed)}</strong></div><div><span>Di cui: cambi di stato</span><strong>${fullMeasure(evidence?.status_changed)}</strong></div></div>`;
      const accounting=evidence?.basis==='frozen_observational_diff'?`<p>Confronto osservazionale delle menzioni nelle fonti, non risoluzione delle identità societarie. I ${fmt(evidence.status_changed)} cambi di stato sono inclusi nelle ${fmt(evidence.content_changed)} righe modificate, non si sommano ad esse.</p>`:evidence?`<p>${fmt(evidence.common)} corrispondenze osservazionali; ${fmt(evidence.unresolved_before)} righe non risolte in A e ${fmt(evidence.unresolved_after)} in B. I cambi di stato sono un sottoinsieme delle righe modificate, non vanno sommati ad esse.</p>`:'<p>Le sole consistenze non consentono di ricostruire entrate, uscite o transizioni individuali. Questi indicatori restano «—». Una diversa versione del parser non è un aggiornamento della Prefettura.</p>';
      const statuses=Object.keys(STATUS).filter(k=>(before.status_counts[k]||after.status_counts[k]) && (state.status==='all'||state.status===k));
      const balances=table(['Stato riportato','Edizione A','Edizione B','Saldo'],statuses.map(k=>`<tr><th scope="row">${esc(STATUS[k])}</th><td>${fmt(before.status_counts[k]||0)}</td><td>${fmt(after.status_counts[k]||0)}</td><td>${signed((after.status_counts[k]||0)-(before.status_counts[k]||0))}</td></tr>`));
      const transitions=evidence?Object.entries(evidence.transition_counts).filter(([k])=>state.status==='all'||k.split('->').includes(state.status)):[];
      const transitionTable=transitions.length?'<h3>Transizioni osservate tra gli stati</h3>'+table(['Da','A','Presenze'],transitions.map(([k,n])=>{const [a,b]=k.split('->');return `<tr><td>${esc(STATUS[a])}</td><td>${esc(STATUS[b])}</td><td>${fmt(n)}</td></tr>`;})):'';
      return selectors+`<p><b>${esc(TYPES[events(history,[before,after]).find(e=>e.after.id===after.id)?.type||eventType(before,after)])}.</b> Il confronto descrive le fonti, non nuove iscrizioni o cancellazioni amministrative.${!inPeriod(before.reference_date,state)?' La base A precede il periodo selezionato.':''}</p>`+metrics+accounting+balances+transitionTable+sources+recordsPanel(after);
    }
    function recordsPanel(edition) {
      const available=registry.records.filter(r=>r.source_key===edition.source_key && r.reference_date===edition.reference_date_raw && r.capture_sha256===edition.document_sha256 && `${r.parser_name}@${r.parser_version||''}`===edition.parser_signature);
      if(!available.length)return '<div class="note">Per questa edizione è disponibile lo storico aggregato, non il dettaglio nominativo pubblico. Consulta il documento ufficiale.</div>';
      const q=state.query.trim().toLocaleLowerCase('it');
      const rows=available.filter(r=>(state.status==='all'||r.source_status===state.status)&&(!q||`${r.name} ${r.identifier_field_raw}`.toLocaleLowerCase('it').includes(q))).sort((a,b)=>a.name.localeCompare(b.name,'it'));
      const pages=Math.max(1,Math.ceil(rows.length/25));state.page=Math.min(state.page,pages);
      const displayed=rows.slice((state.page-1)*25,state.page*25);
      return `<details class="history-records" ${state.query||state.recordsOpen?'open':''}><summary>Righe pubbliche dell’edizione B · ${fmt(rows.length)} nella selezione</summary><p>Questa è la consistenza dell’edizione B, non una lista delle sole righe cambiate.</p><label for="h-row-query">Cerca nell’edizione</label> <input id="h-row-query" type="search" data-h-query value="${esc(state.query)}">`+table(['Impresa','Stato riportato','Dettaglio'],displayed.map(r=>`<tr><td>${esc(r.name)}</td><td>${esc(STATUS[r.source_status]||r.source_status)}</td><td><button class="btn" data-h-record="${esc(r.record_locator)}">Apri scheda</button></td></tr>`))+`<div class="pager"><button class="btn" data-h-page="-1" ${state.page<=1?'disabled':''}>Precedente</button><span>Pagina ${state.page} / ${pages}</span><button class="btn" data-h-page="1" ${state.page>=pages?'disabled':''}>Successiva</button></div></details>`;
    }
    function renderHistory() {
      const root=roots.history;if(!root)return;if(invalid(root,'h'))return;
      const {base,visible}=viewData();
      const cut=state.asof||state.to||visible.map(e=>e.reference_date).filter(Boolean).sort().at(-1)||'';
      const observed=asOf(base,cut);
      const mode=`<div class="toolbar"><label for="h-mode">Modalità</label><select id="h-mode" data-h-field="mode">${option('series','Edizioni e confronti',state.mode)}${option('asof','Situazione osservabile alla data',state.mode)}</select>${state.mode==='asof'?`<label for="h-asof">Data limite</label><input id="h-asof" type="date" data-h-field="asof" value="${esc(cut)}">`:''}</div>`;
      let body;
      if(state.mode==='asof') {
        body=section('Ultime edizioni con riferimento non successivo alla data scelta',`<div class="note">Ricostruzione per data degli elenchi, non di ciò che il progetto conosceva allora e non dello stato giuridico esatto a quella data. Il filtro «Dal» non esclude le basi più vecchie necessarie a questa ricostruzione. Nessuna impresa è interpolata tra edizioni.</div><p><b>${fmt(observed.selected.reduce((s,e)=>s+count(e,state.status),0))} presenze</b> negli ultimi elenchi utilizzabili alla data ${esc(dateLabel(cut))}. ${fmt(observed.missing.length)} elenchi senza una base anteriore; ${fmt(observed.ambiguous.length)} con più versioni non ordinabili, esclusi dal totale. La stessa impresa può comparire in più elenchi.</p>`+sourceTable(observed.selected)+distribution(observed.selected));
      } else {
        body=section('Calendario delle edizioni',`<p>${fmt(visible.length)} edizioni · ${fmt(group(visible).size)} elenchi. Con un intervallo di date, le edizioni prive di una data completa non entrano nei grafici.</p>`+calendar(visible))+
          section('Consistenza e distribuzione per stato',distribution(visible))+
          `<div id="h-comparison">${section('Confronto tra due edizioni',comparisonPanel(base,visible))}</div>`;
      }
      const discovered=(state.authority==='all'||state.authority==='cosenza')?`<details><summary>Altre pagine storiche individuate — Cosenza</summary><p>Collegamenti di scoperta, non edizioni già estratte: non entrano nei conteggi o nella frequenza.</p>${table(['Data dichiarata','Pagina ufficiale'],(site.history||[]).filter(e=>inPeriod(e.date,state)).map(e=>`<tr><td>${esc(dateLabel(e.date))}</td><td>${link(e.page_url,'Consulta la pagina')}</td></tr>`))}</details>`:'';
      root.innerHTML=`<div class="note"><b>Storico delle fonti osservate.</b> I numeri sono presenze negli elenchi, non un conteggio nazionale di imprese distinte. L’assenza da un’edizione non equivale a cancellazione. I filtri territoriali, temporali e di stato sono condivisi con «Aggiornamenti».</div>`+section('Filtri dello storico',filters('h')+mode)+body+discovered;
      bind(root);
    }
    function renderUpdates() {
      const root=roots.updates;if(!root)return;if(invalid(root,'u',true))return;
      const {base,visible,eventRows}=viewData();
      const stats=frequency(history,base,state);
      const frequencyTable=table(['Prefettura / elenco','Edizioni nel periodo','Cambi documentali tra edizioni','Intervallo mediano','Ultima verifica documentale'],stats.map(s=>`<tr><th scope="row">${esc(label(s.edition))}</th><td>${fmt(s.editions)}</td><td>${fmt(s.changes)}</td><td>${s.median===null?(s.gaps.length===1?`${fmt(s.gaps[0])} giorni · unico intervallo`:'Non stimabile'):`${fmt(s.median)} giorni · ${fmt(s.gaps.length)} intervalli`}</td><td>${esc(timeLabel(s.latestCheck))}</td></tr>`),'history-scroll');
      const eventTable=table(['Elenco','Da → a','Tipo','Giorni','Saldo presenze filtrate','Nuove / non più rilevate¹','Cambi di stato¹','Confronto'],[...eventRows].reverse().map(e=>`<tr><th scope="row">${esc(label(e.after))}</th><td>${esc(e.before?dateLabel(e.before.reference_date):'Nessuna base')} → ${esc(dateLabel(e.after.reference_date))}</td><td>${esc(TYPES[e.type])}</td><td>${fmt(e.gap)}</td><td>${e.before?signed(count(e.after,state.status)-count(e.before,state.status)):'—'}</td><td>${fmt(e.comparison?.added)} / ${fmt(e.comparison?.disappeared)}</td><td>${fmt(e.comparison?.status_changed)}</td><td><button class="btn" data-h-edition="${esc(e.after.id)}">Apri</button></td></tr>`),'history-scroll');
      const ids=new Set(base.map(e=>e.id));
      // Check dates use their own clock, never the source-reference date filter.
      const checks=history.checks.filter(c=>ids.has(c.edition_id)&&inPeriod(c.checked_at.slice(0,10),state));
      const byId=new Map(history.editions.map(e=>[e.id,e]));
      const checkRows=[...checks].reverse().map(c=>{const e=byId.get(c.edition_id);return `<tr><td>${esc(timeLabel(c.checked_at))}</td><td>${esc(label(e))}</td><td>${esc(dateLabel(e.reference_date))}</td><td>${c.kind==='historical_capture'?'Acquisizione storica':'Verifica del documento approvato'}</td><td class="mono">${esc(e.document_sha256.slice(0,16))}…</td></tr>`;});
      root.innerHTML=`<div class="note"><b>Frequenza osservabile, non graduatoria delle Prefetture.</b> Gli intervalli collegano le date di riferimento delle edizioni archiviate. Non dimostrano che siano state rilevate tutte le pubblicazioni. Le verifiche qui registrate controllano documenti approvati, non tutte le nuove pubblicazioni del sito istituzionale.</div>`+
        section('Filtri degli aggiornamenti',filters('u',true))+
        section('Intervalli tra edizioni',`<p>Una sola edizione non dà una frequenza; con due edizioni si mostra soltanto l’unico intervallo. Una mediana è mostrata da almeno due intervalli, con il numero di osservazioni. Il filtro Stato cambia le consistenze, non la frequenza documentale; tipo e soglie selezionano soltanto la tabella delle variazioni.</p>`+frequencyTable)+
        section('Variazioni per aggiornamento',`<p>${fmt(eventRows.length)} righe nella selezione. La base precedente può essere esterna al periodo. ¹ Entrate, assenze e transizioni riguardano l’intero elenco e non vengono ricostruite dal saldo. «—» significa non disponibile.</p>`+eventTable)+
        section('Controlli documentali riusciti',`<p>${fmt(checks.length)} controlli conservati nelle date selezionate (UTC). Ripetere il controllo della stessa impronta non crea una nuova edizione. Il registro non contiene tutti i tentativi falliti: non consente di calcolare disponibilità del sito o assenza di aggiornamenti nei periodi non osservati.</p><details><summary>Apri il registro dei controlli</summary>`+table(['Controllo (UTC)','Elenco','Data dell’elenco','Tipo','Impronta'],checkRows,'history-scroll')+'</details>');
      bind(root);
    }
    function drawBoth(){renderHistory();renderUpdates();}
    return {renderHistory,renderUpdates,state,drawBoth};
  }
  return {scope,count,days,median,events,asOf,frequency,comparison,csv,createController};
});

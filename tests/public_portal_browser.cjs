// CI acceptance test of the actual Pages artifact, served over HTTP.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const registry=JSON.parse(fs.readFileSync('public-site/data/registry.json'));
const {displayDate,publicStatistics}=require('../public-site/summary.js');
const numeric=text=>Number(text.replace(/\D/g,''));
const statusCounts=records=>Object.fromEntries([...records.reduce((m,r)=>m.set(r.source_status,(m.get(r.source_status)||0)+1),new Map())].sort());

(async()=>{
  fs.mkdirSync('test-results',{recursive:true});
  const browser=await chromium.launch();
  try {
    for(const width of [1440,390]){
      const page=await browser.newPage({viewport:{width,height:900}});
      const errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.goto('http://127.0.0.1:8765/');
      await page.locator('#status').filter({hasText:'Registro caricato'}).waitFor();
      assert.equal(await page.locator('#reg-status').inputValue(),'listed');
      const labels=await page.locator('#reg-register option').allTextContents();
      assert.equal(labels.length,new Set(labels).size);
      assert.ok(labels.includes('White List ordinaria · Prefettura di Cosenza'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Parma'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Pistoia'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Alessandria'));
      assert.ok(labels.includes("White List ordinaria · Regione autonoma Valle d'Aosta · funzioni prefettizie"));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Arezzo'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Avellino'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Pesaro e Urbino'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Biella'));
      assert.ok(labels.includes('White List ordinaria · Prefettura di Benevento'));
      assert.ok(!(await page.locator('#view-registry tbody').innerText()).match(/\b\d{4}-\d{2}-\d{2}\b/));
      assert.equal(numeric(await page.locator('#view-registry .section-title').last().innerText()),registry.records.filter(r=>r.source_status==='listed').length);
      assert.equal(numeric((await page.locator('.public-banner').first().innerText()).match(/([\d.,]+) presenze/)[1]),registry.records.length);
      await page.screenshot({path:`test-results/registry-${width}.png`});
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
      assert.equal(overflow,false,`Unexpected outer horizontal overflow at ${width}px`);
      // Keep explicit table scrolling; do not drop company columns on mobile.
      assert.equal(await page.locator('#view-registry th').count(),9);
      await page.locator('#reg-authority').selectOption('cosenza');
      await page.locator('#reg-status').selectOption('pending');
      const pending=registry.records.filter(r=>r.authority_key==='cosenza'&&r.source_status==='pending');
      assert.equal(numeric(await page.locator('#view-registry .section-title').last().innerText()),pending.length);
      await page.locator('#reg-q').pressSequentially('zzzz_no_company');
      assert.equal(await page.locator('#reg-q').inputValue(),'zzzz_no_company');
      assert.equal(await page.locator('#view-registry tbody').innerText(),'Nessun risultato.');
      await page.locator('#reg-q').fill('');
      await page.locator('#reg-status').selectOption('listed');
      const row=page.locator('#view-registry .clickrow').first();
      const locator=await row.getAttribute('data-record');
      const expected=registry.records.find(r=>r.record_locator===locator);
      await row.press('Enter');
      await page.locator('#detail.open').waitFor();
      assert.equal(await page.locator('#detail-title').innerText(),expected.name);
      assert.ok((await page.locator('#detail-body').innerText()).includes(displayDate(expected.reference_date)));
      assert.equal(await page.getByRole('link',{name:'Consulta l’elenco ufficiale',exact:true}).first().getAttribute('href'),expected.resource_url);
      await page.screenshot({path:`test-results/detail-${width}.png`});
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#detail').getAttribute('aria-hidden'),'true');
      for(const [name,id] of [['Statistiche','statistics'],['Prefetture','prefectures'],['Storico','history'],['Aggiornamenti','updates'],['Metodo e fonti','method'],['Qualità dei dati','quality']]){
        await page.getByRole('button',{name,exact:true}).click();
        await page.locator(`#view-${id}.active`).waitFor();
        const body=await page.locator(`#view-${id}`).innerText();
        for(const forbidden of ['canonical population','candidate precision','schema_fingerprint','scope ancora incompleto','review_notes','table_catalog'])assert.ok(!body.includes(forbidden));
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        await page.screenshot({path:`test-results/${id}-${width}.png`,fullPage:id==='statistics'});
      }
      await page.getByRole('button',{name:'Statistiche',exact:true}).click();
      const stats=publicStatistics(registry.records);
      // Freeze the pre-expansion four-Prefecture baseline independently of later
      // authorities, then assert each added authority and the current total.
      assert.equal(stats.total,8522);
      const previous=registry.records.filter(r=>!['alessandria','aosta','arezzo','avellino','pesaro-e-urbino','biella','benevento'].includes(r.authority_key));
      assert.equal(previous.length,5052);
      assert.deepEqual(statusCounts(previous),{
        cancellation_related:2,expired_observed:171,listed:2229,other_or_unknown:5,
        pending:1416,rejected_or_denied:12,renewal_requested:14,renewal_update_in_progress:1203
      });
      const alessandria=registry.records.filter(r=>r.authority_key==='alessandria');
      assert.equal(alessandria.length,434);
      assert.equal(alessandria.filter(r=>r.source_key==='alessandria-listed').length,363);
      assert.equal(alessandria.filter(r=>r.source_key==='alessandria-applicants').length,71);
      const aosta=registry.records.filter(r=>r.authority_key==='aosta');
      assert.equal(aosta.length,384);
      assert.equal(aosta.filter(r=>r.source_key==='aosta-listed').length,245);
      assert.equal(aosta.filter(r=>r.source_key==='aosta-applicants').length,139);
      assert.deepEqual(statusCounts(aosta),{listed:345,pending:22,renewal_update_in_progress:17});
      const arezzo=registry.records.filter(r=>r.authority_key==='arezzo');
      assert.equal(arezzo.length,364);
      assert.equal(arezzo.filter(r=>r.source_key==='arezzo-listed').length,332);
      assert.equal(arezzo.filter(r=>r.source_key==='arezzo-applicants').length,32);
      assert.deepEqual(statusCounts(arezzo),{listed:288,pending:32,renewal_update_in_progress:44});
      const avellino=registry.records.filter(r=>r.authority_key==='avellino');
      assert.equal(avellino.length,627);
      assert.equal(avellino.filter(r=>r.source_key==='avellino-listed').length,383);
      assert.equal(avellino.filter(r=>r.source_key==='avellino-applicants').length,244);
      assert.deepEqual(statusCounts(avellino),{listed:383,pending:244});
      const pesaro=registry.records.filter(r=>r.authority_key==='pesaro-e-urbino');
      assert.equal(pesaro.length,484);
      assert.equal(pesaro.filter(r=>r.source_key==='pesaro-urbino-combined').length,484);
      assert.deepEqual(statusCounts(pesaro),{listed:406,renewal_update_in_progress:78});
      const biella=registry.records.filter(r=>r.authority_key==='biella');
      assert.equal(biella.length,239);
      assert.equal(biella.filter(r=>r.source_key==='biella-listed').length,130);
      assert.equal(biella.filter(r=>r.source_key==='biella-applicants').length,109);
      assert.deepEqual(statusCounts(biella),{listed:213,pending:12,renewal_update_in_progress:14});
      const benevento=registry.records.filter(r=>r.authority_key==='benevento');
      assert.equal(benevento.length,938);
      assert.equal(benevento.filter(r=>r.source_key==='benevento-listed').length,734);
      assert.equal(benevento.filter(r=>r.source_key==='benevento-applicants').length,204);
      assert.deepEqual(statusCounts(benevento),{listed:734,pending:204});
      const bars=page.locator('#view-statistics .stat-table').first().locator('.stat-number');
      assert.equal((await bars.allTextContents()).reduce((n,t)=>n+numeric(t),0),stats.total);
      assert.equal(await page.locator('#view-statistics a').count(),new Set(stats.latest.map(r=>JSON.stringify([r.source_key,r.reference_date,r.capture_sha256]))).size);
      await page.locator('#stats-authority').selectOption('alessandria');
      const alessandriaStats=publicStatistics(registry.records,'alessandria');
      assert.equal(alessandriaStats.total,434);
      assert.equal((await bars.allTextContents()).reduce((n,t)=>n+numeric(t),0),alessandriaStats.total);
      await page.getByRole('button',{name:'Registro',exact:true}).click();
      await page.locator('#reg-latest').uncheck();
      await page.locator('#reg-authority').selectOption('alessandria');
      await page.locator('#reg-status').selectOption('pending');
      assert.equal(numeric(await page.locator('#view-registry .section-title').last().innerText()),alessandria.filter(r=>r.source_status==='pending').length);
      await page.getByRole('button',{name:'Statistiche',exact:true}).click();
      await page.locator('#stats-authority').selectOption('cosenza');
      const cosenza=publicStatistics(registry.records,'cosenza');
      assert.equal((await bars.allTextContents()).reduce((n,t)=>n+numeric(t),0),cosenza.total);
      const pendingBar=page.locator('#view-statistics .stat-table').first().locator('[data-stat-status="pending"]');
      const pendingCount=numeric(await pendingBar.innerText());
      await pendingBar.focus();
      await pendingBar.press('Enter');
      assert.equal(await page.locator('#reg-latest').isChecked(),true);
      assert.equal(await page.locator('#reg-authority').inputValue(),'cosenza');
      assert.equal(await page.locator('#reg-status').inputValue(),'pending');
      assert.equal(numeric(await page.locator('#view-registry .section-title').last().innerText()),pendingCount);
      await page.getByRole('button',{name:'Statistiche',exact:true}).click();
      const bolognaBar=page.locator('#view-statistics .stat-table').nth(1).locator('[data-stat-authority="bologna"][data-stat-status="pending"]');
      const bolognaCount=numeric(await bolognaBar.innerText());
      assert.equal(bolognaCount,stats.latest.filter(r=>r.authority_key==='bologna'&&r.source_status==='pending').length);
      await bolognaBar.click();
      assert.equal(numeric(await page.locator('#view-registry .section-title').last().innerText()),bolognaCount);
      await page.locator('#reg-latest').uncheck();
      await page.locator('#reg-status').selectOption('listed');
      await page.getByRole('button',{name:'Registro',exact:true}).click();
      await page.locator('#reg-authority').selectOption('bologna');
      await page.locator('#reg-register').selectOption('bologna-post-sisma');
      assert.ok((await page.locator('#view-registry tbody').innerText()).includes('White List post-sisma'));
      assert.deepEqual(errors,[]);
      await page.close();
      console.log(`Public registry, source links, all sections and layout passed at ${width}px`);
    }
  } finally {await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});

// Exercise the actual approved data and failures at the network boundary.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const electoral=JSON.parse(fs.readFileSync('public-site/data/electoral.json'));
const registry=JSON.parse(fs.readFileSync('public-site/data/registry.json'));
const {publicStatistics,defaultStatisticsPeriod,publicDateDistributions}=require('../public-site/summary.js');
const dateNumber=text=>Number(text.replace(/\./g,''));
const baseURL=process.env.PUBLIC_SITE_URL||'http://127.0.0.1:8765/';

(async()=>{
  fs.mkdirSync('test-results',{recursive:true});
  const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined});
  try{
    for(const width of [1440,768,390,320]){
      const page=await browser.newPage({viewport:{width,height:900}});
      const errors=[];
      page.on('pageerror',error=>errors.push(error.message));
      let registryRequests=0;
      await page.route('**/data/registry.json',route=>{registryRequests++;return route.abort()});
      await page.route('**/robot-state/state.json',route=>route.fulfill({json:{schema_version:1,robots:{cosenza:{status:'unchanged',checked_at:'2026-09-27T20:00:00Z',last_successful_check_at:'2026-09-27T20:00:00Z',requests:2,captured_urls:[],errors:[],pending_urls:[]}}}}));
      await page.goto(baseURL+'#electoral');
      await page.locator('#electoral-event').waitFor();
      assert.equal(registryRequests,0,'electoral deep link must not download registry');
      assert.equal(await page.locator('#electoral-event option').count(),6);
      assert.equal(await page.locator('#view-electoral .electoral-grid tbody tr').count(),111);
      for(const metric of ['weighted_mean_hours','weighted_p90_hours','last_hours']){
        await page.locator('#electoral-metric').selectOption(metric);
        const scores=await page.locator('.electoral-grid tbody tr').evaluateAll(rows=>rows.map(row=>row.cells[2].textContent).filter(value=>value!=='—').map(value=>Number(value.replace(',','.'))));
        assert.deepEqual(scores,[...scores].sort((a,b)=>a-b));
      }
      for(const event of electoral.events){
        await page.locator('#electoral-event').selectOption(event.id);
        assert.equal(await page.locator('.electoral-grid tbody tr').count(),event.provinces.length);
      }
      await page.locator('#electoral-event').selectOption('overall');
      await page.locator('#electoral-query').pressSequentially('Roma');
      assert.equal(await page.locator('#electoral-query').inputValue(),'Roma');
      const rankBefore=await page.locator('.electoral-grid tbody tr').first().locator('td').first().innerText();
      await page.locator('#electoral-query').fill('');
      const roma=page.locator('.electoral-grid tbody tr').filter({has:page.getByText('ROMA',{exact:true})});
      assert.equal(await roma.locator('td').first().innerText(),rankBefore,'filter preserves national rank');
      assert.deepEqual(await page.evaluate(()=>electoralRank([{province:'B',n:1},{province:'A',n:1},{province:'C',n:2}],p=>p.n).map(p=>p.rank)),[1,1,3]);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.screenshot({path:`test-results/electoral-${width}.png`,fullPage:false});
      await page.getByRole('button',{name:'Robot',exact:true}).click();
      await page.locator('#robot-q').waitFor();
      assert.equal(await page.locator('.robot-grid tbody tr').count(),106);
      await page.locator('#robot-q').fill('cosenza');
      assert.equal(await page.locator('.robot-grid tbody tr').count(),1);
      await page.getByRole('button',{name:'Apri robot',exact:true}).click();
      assert.match(await page.locator('#view-robots').innerText(),/Nessuna variazione rilevata/);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.screenshot({path:`test-results/robots-${width}.png`,fullPage:false});
      await page.getByRole('button',{name:'Registro',exact:true}).click();
      await page.locator('[data-retry]').waitFor();
      await page.getByRole('button',{name:'Prefetture',exact:true}).click();
      await page.locator('#pref-q').waitFor();
      await page.getByRole('button',{name:'Qualità dei dati',exact:true}).click();
      await page.locator('#view-quality .section-title').first().waitFor();
      await page.getByRole('button',{name:'Tempi elettorali',exact:true}).click();
      await page.locator('#electoral-event').waitFor();
      assert.equal(registryRequests,1,'failed registry is not silently refetched by other sections');
      await page.unroute('**/data/registry.json');
      await page.getByRole('button',{name:'Registro',exact:true}).click();
      await page.locator('#reg-q').waitFor({timeout:60000});
      assert.equal(await page.locator('#reg-status').inputValue(),'listed');
      // A selected state with zero rows must remain visible after narrowing scope.
      // Previously the select displayed "Iscritte (855)" while filtering cancellations.
      await page.locator('#reg-status').selectOption('cancellation_related');
      await page.locator('#reg-authority').selectOption('agrigento');
      assert.equal(await page.locator('#reg-status').inputValue(),'cancellation_related');
      assert.equal(await page.locator('#reg-status option:checked').innerText(),'Cancellazione / cessazione (0)');
      assert.equal(await page.locator('#view-registry tbody').innerText(),'Nessun risultato.');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'reg-authority');
      await page.locator('#reg-q').fill('filtro_da_azzerare');
      await page.locator('#reg-latest').check();
      await page.getByRole('button',{name:'Azzera filtri',exact:true}).click();
      assert.equal(await page.locator('#reg-q').inputValue(),'');
      assert.equal(await page.locator('#reg-status').inputValue(),'listed');
      assert.equal(await page.locator('#reg-authority').inputValue(),'all');
      assert.equal(await page.locator('#reg-register').inputValue(),'all');
      assert.equal(await page.locator('#reg-latest').isChecked(),false);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'reg-q');

      // Page controls are available above long mobile card lists. Moving from
      // either end returns the reader to the new results, below the sticky menu.
      const firstLocator=await page.locator('.registry-grid .clickrow').first().getAttribute('data-record');
      await page.locator('#next').click();
      assert.notEqual(await page.locator('.registry-grid .clickrow').first().getAttribute('data-record'),firstLocator);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'registry-results');
      assert.ok(await page.locator('#registry-results').evaluate(el=>{
        const top=el.getBoundingClientRect().top;
        return top>=document.querySelector('.menubar').getBoundingClientRect().bottom&&top<innerHeight/2;
      }));
      await page.locator('#prev-top').click();
      assert.equal(await page.locator('.registry-grid .clickrow').first().getAttribute('data-record'),firstLocator);

      await page.getByRole('button',{name:'Prefetture',exact:true}).click();
      await page.locator('#pref-q').waitFor();
      await page.locator('#pref-q').fill('zzzz_no_prefecture');
      assert.match(await page.locator('#view-prefectures tbody').innerText(),/Nessuna Prefettura/);
      await page.getByRole('button',{name:'Qualità dei dati',exact:true}).click();
      await page.locator('#view-quality .section-title').first().waitFor();
      await page.goBack();
      await page.locator('#pref-q').waitFor();
      assert.equal(await page.locator('#pref-q').inputValue(),'zzzz_no_prefecture');
      await page.goForward();
      await page.locator('#view-quality.active .section-title').first().waitFor();
      await page.getByRole('button',{name:'Registro',exact:true}).click();
      await page.locator('#reg-q').waitFor();
      await page.locator('#reg-q').pressSequentially('zzzz_no_company');
      assert.equal(await page.locator('#view-registry tbody').innerText(),'Nessun risultato.');
      await page.locator('#reg-q').fill('');
      if(width<=600){
        assert.equal(await page.locator('.registry-grid .grid').evaluate(el=>el.scrollWidth<=el.parentElement.clientWidth),true);
        assert.ok(await page.locator('#reg-q').evaluate(el=>el.getBoundingClientRect().height>=44));
        assert.equal(await page.locator('.registry-grid .clickrow').first().locator('td').nth(4).isVisible(),true,'register identity remains visible on mobile cards');
      }
      await page.screenshot({path:`test-results/registry-${width}.png`,fullPage:false});
      await page.locator('#view-registry .clickrow').first().press('Enter');
      await page.locator('#detail.open').waitFor();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#detail').getAttribute('aria-hidden'),'true');
      assert.equal(await page.locator('.window').evaluate(el=>el.inert),false);
      await page.locator('#reg-q').focus();
      await page.keyboard.press('Escape');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'reg-q','Escape outside a dialog must not restore stale row focus');
      await page.getByRole('button',{name:'Statistiche',exact:true}).click();
      await page.locator('#stats-authority').waitFor();
      const stats=publicStatistics(registry.records),initialPeriod=defaultStatisticsPeriod(stats.latest);
      const assertDates=async(authority,period)=>{
        for(const expected of publicDateDistributions(publicStatistics(registry.records,authority).selected,period)){
          const panel=page.locator(`[data-date-distribution="${expected.key}"]`);
          for(const key of ['total','inPeriod'])assert.equal(dateNumber(await panel.locator(`[data-date-count="${key}"]`).innerText()),expected[key]);
          assert.deepEqual((await panel.locator('.date-coverage .value').allTextContents()).map(dateNumber),[expected.missing,expected.uninterpretable,expected.before,expected.after]);
          assert.deepEqual(await panel.locator('[data-date-bin]').evaluateAll(cells=>cells.map(cell=>({period:cell.dataset.dateBin,count:Number(cell.textContent.replace(/\./g,''))}))),expected.bins);
          assert.equal(await panel.locator('[role="img"]').count(),expected.inPeriod?1:0);
          if(expected.inPeriod)assert.equal(await panel.locator('.timeline-ticks').evaluate(axis=>{
            const bounds=[...axis.children].filter(el=>getComputedStyle(el).display!=='none').map(el=>el.getBoundingClientRect());
            return bounds.every((box,i)=>i===0||box.left>=bounds[i-1].right);
          }),true,'horizontal date labels must not overlap');
        }
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      };
      await assertDates('all',initialPeriod);
      assert.deepEqual(await page.locator('.timeline-y').allTextContents(),Array(2).fill(await page.locator('.timeline-y').first().textContent()),'both charts share the count scale');
      for(const key of ['pending','renewal_update_in_progress']){
        const panel=page.locator(`[data-date-distribution="${key}"]`);
        await panel.screenshot({path:`test-results/statistics-${key}-${width}.png`});
        const summary=panel.locator('summary');
        await summary.focus();await page.keyboard.press('Enter');
        assert.equal(await panel.locator('[data-date-values]').isVisible(),true);
        await page.keyboard.press('Enter');
      }
      await page.locator('#stats-authority').selectOption('bologna');
      await assertDates('bologna',initialPeriod);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'stats-authority');
      assert.match(await page.locator('[data-date-distribution="pending"] [data-date-empty]').innerText(),/Nessuna presenza con una data interpretabile/);
      await page.locator('#stats-authority').selectOption('cosenza');
      await page.locator('#stats-from-year').fill('2025');
      await page.locator('#stats-to-year').fill('2026');
      await page.locator('#stats-interval').selectOption('month');
      await page.getByRole('button',{name:'Applica periodo',exact:true}).click();
      await assertDates('cosenza',{fromYear:2025,toYear:2026,interval:'month'});
      assert.match(await page.locator('#stats-date-status').innerText(),/2025–2026/);
      await page.locator('[data-date-distribution="pending"]').screenshot({path:`test-results/statistics-months-${width}.png`});
      await page.locator('#stats-from-year').fill('2027');
      await page.getByRole('button',{name:'Applica periodo',exact:true}).click();
      assert.match(await page.locator('#stats-period-error').innerText(),/anno iniziale/);
      assert.equal(await page.locator('[data-date-distribution]').count(),0,'invalid range must not leave stale charts');
      await page.getByRole('button',{name:'Periodo iniziale',exact:true}).click();
      await assertDates('cosenza',initialPeriod);
      assert.equal(await page.evaluate(()=>document.activeElement.id),'stats-period-reset');
      await page.locator('#stats-authority').selectOption('all');
      await assertDates('all',initialPeriod);
      // The pre-existing status chart still opens the matching latest rows.
      await page.locator('[data-stat-status="pending"][data-stat-authority="all"]').click();
      await page.locator('#reg-latest').waitFor();
      assert.equal(await page.locator('#reg-latest').isChecked(),true);
      assert.equal(await page.locator('#reg-status').inputValue(),'pending');
      for(const [name,id] of [['Storico','history'],['Metodo e fonti','method']]){
        await page.getByRole('button',{name,exact:true}).click();
        await page.locator(`#view-${id} .section-title`).first().waitFor();
      }
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);
      await page.close();
    }
  }finally{await browser.close()}
  console.log('Public snapshot browser acceptance passed: desktop/tablet/320/390px, robots, electoral ranking, independent loading, recovery, registry, temporal distributions, history.');
})().catch(error=>{console.error(error);process.exit(1)});

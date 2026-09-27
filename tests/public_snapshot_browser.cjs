// Exercise the actual approved data and failures at the network boundary.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const electoral=JSON.parse(fs.readFileSync('public-site/data/electoral.json'));
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
      await page.locator('#reg-q').pressSequentially('zzzz_no_company');
      assert.equal(await page.locator('#view-registry tbody').innerText(),'Nessun risultato.');
      await page.locator('#reg-q').fill('');
      if(width<=600){
        assert.equal(await page.locator('.registry-grid .grid').evaluate(el=>el.scrollWidth<=el.parentElement.clientWidth),true);
        assert.ok(await page.locator('#reg-q').evaluate(el=>el.getBoundingClientRect().height>=44));
      }
      await page.screenshot({path:`test-results/registry-${width}.png`,fullPage:false});
      await page.locator('#view-registry .clickrow').first().press('Enter');
      await page.locator('#detail.open').waitFor();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#detail').getAttribute('aria-hidden'),'true');
      assert.equal(await page.locator('.window').evaluate(el=>el.inert),false);
      for(const [name,id] of [['Statistiche','statistics'],['Storico','history'],['Metodo e fonti','method']]){
        await page.getByRole('button',{name,exact:true}).click();
        await page.locator(`#view-${id} .section-title`).first().waitFor();
      }
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);
      await page.close();
    }
  }finally{await browser.close()}
  console.log('Public snapshot browser acceptance passed: desktop/tablet/320/390px, robots, electoral ranking, independent loading, recovery, registry, history.');
})().catch(error=>{console.error(error);process.exit(1)});

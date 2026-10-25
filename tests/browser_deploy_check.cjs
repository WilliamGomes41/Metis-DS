// Raad's deploy check in a real browser: all main pages pass on a healthy
// console, injected faults are named per page, and no authority row changes.
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE);
const fs=require('node:fs');
(async()=>{
  const base=process.env.METIS_BROWSER_BASE;
  const directory=process.env.METIS_BROWSER_OUTPUT;
  const browser=await chromium.launch({headless:true,executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  const post=(path,body)=>fetch(base+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  try {
    const manifest=await (await fetch(base+'/browser-manifest')).json();
    const before=await (await fetch(base+'/browser-domain-state')).json();
    const results={};
    const run=async(page)=>{
      await page.getByRole('button',{name:"Controleer alle pagina's",exact:true}).click();
      await page.getByRole('button',{name:'Kopieer uitslag'}).waitFor({timeout:120000});
      return page.locator('[data-deploy-page]').evaluateAll(nodes=>nodes.map(n=>({path:n.dataset.deployPage,result:n.dataset.deployResult,text:n.textContent})));
    };
    for(const username of [manifest.author, manifest.reviewer]){
      const page=await browser.newPage();
      const errors=[];
      page.on('pageerror',e=>errors.push(String(e)));
      await page.goto(base+'/login');
      await page.locator('[name=username]').fill(username);
      await page.locator('[name=password]').fill(manifest.password);
      await Promise.all([page.waitForURL(base+'/'),page.locator('button[type=submit]').click()]);
      await post('/browser-faults',{});
      let releaseNotices;
      let noticeRequests=0;
      const gate=new Promise(resolve=>{releaseNotices=resolve;});
      await page.route('**/raad/meldingen',async route=>{noticeRequests++;await gate;await route.continue();});
      const noticesStarted=page.waitForRequest(request=>request.url().endsWith('/raad/meldingen'));
      await page.getByRole('button',{name:/Open Raad/}).click();
      await noticesStarted;
      await page.getByRole('button',{name:'Sluit Raad'}).click();
      await page.getByRole('button',{name:/Open Raad/}).click();
      await page.evaluate(()=>new Promise(requestAnimationFrame));
      if(noticeRequests!==1)throw Error('reopening Raad duplicated its in-flight notices request');
      const noticesFinished=page.waitForResponse(response=>response.url().endsWith('/raad/meldingen'));
      releaseNotices();
      await noticesFinished;
      await page.unroute('**/raad/meldingen');
      if(await page.evaluate(()=>sessionStorage.getItem('metis-care-notices'))!==null)
        throw Error('protected notices persisted in session storage');
      // Missing processing access must not display a candidate count/unknown count.
      await page.getByRole('button',{name:'Sluit Raad'}).click();
      await page.route('**/raad/meldingen',route=>route.fulfill({json:{complete:true,next_offset:null,documents:[{
        snapshot_id:'publisher-fixture',title:'Publisher-only notice',processing_access:false,
        processing_blocked:true,blocked:null,reasons:[],telemetry:{errors:0}}]}}));
      await page.getByRole('button',{name:/Open Raad/}).click();
      const publisherNotice=page.getByRole('link',{name:'Publisher-only notice'}).locator('..');
      await publisherNotice.waitFor();
      const publisherText=await publisherNotice.textContent();
      if(!publisherText.includes('opgeslagen verwerkingsblokkade')||publisherText.includes('kandidaten'))
        throw Error('publisher notice exposed unavailable processing details: '+publisherText);
      await page.unroute('**/raad/meldingen');
      const healthy=await run(page);
      const paths=healthy.map(r=>r.path);
      for(const expected of ['/','/ingest','/source-selection','/review','/publish','/tree','/formation-problems','/settings','/inzicht'])
        if(!paths.includes(expected))throw Error(username+' missing page '+expected+': '+JSON.stringify(paths));
      results[username]={healthy};
      if(username===manifest.author){
        const insightContext=await browser.newContext({storageState:await page.context().storageState()});
        const insight=await insightContext.newPage();
        await insight.route('**/inzicht/api/documents?*',route=>route.fulfill({json:{documents:[],
          total:null,offset:0,limit:200,next_offset:null,telemetry_partial:false,metadata_partial:true}}));
        await insight.goto(base+'/inzicht?tab=documenten');
        await insight.waitForFunction(()=>document.querySelector('#d-status')?.textContent.includes('documentoverzicht onvolledig'));
        const text=await insight.locator('#d-status').textContent();
        if(text.includes('0 van 0'))throw Error('partial metadata claimed a complete empty document list');
        await insightContext.close();
      }

      // Playwright also reports errors from frames; the healthy pass must have none.
      if(errors.length)throw Error('page errors on a healthy console: '+errors.join('; '));
      if(username===manifest.reviewer){
        // A role refusal is reported as not checked, never as a deploy fault.
        const refused=healthy.filter(r=>r.result!=='ok');
        if(refused.length!==1||refused[0].path!=='/publish'||refused[0].result!=='skipped')
          throw Error('reviewer role refusal misreported: '+JSON.stringify(healthy));
      }
      if(username===manifest.author){
        if(healthy.some(r=>r.result!=='ok'))throw Error('healthy console reported a problem: '+JSON.stringify(healthy));
        await page.screenshot({path:directory+'/deploy-check-healthy.png'});
        await post('/browser-faults',{'/tree':'status','/publish':'banner','/review':'script','/settings':'redirect'});
        const faulty=await run(page);
        const byPath=Object.fromEntries(faulty.map(r=>[r.path,r]));
        const expect=(path,needle)=>{ if(byPath[path].result!=='problem'||!byPath[path].text.includes(needle))throw Error(path+' not reported: '+JSON.stringify(byPath[path])); };
        expect('/tree','foutstatus 500');
        expect('/publish','fixture_failure');
        expect('/publish','req-fixture');
        expect('/review','1 scriptfout');
        expect('/settings','stuurt door naar /');
        if(faulty.filter(r=>r.result!=='ok').length!==4)throw Error('unexpected failures: '+JSON.stringify(faulty));
        await page.screenshot({path:directory+'/deploy-check-faults.png'});
        // The result survives reopening the panel in the same tab.
        await page.reload();
        if(await page.locator('[data-deploy-page]').count()!==faulty.length)throw Error('result not retained after reload');
        results[username].faulty=faulty;
        const copied=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('metis-care-deploy-check')));
        if(copied.rows.length!==faulty.length)throw Error('stored result incomplete');
        // An expired session stops the run at the first sign-in redirect.
        await post('/browser-faults',{'/ingest':'signin'});
        const signin=await run(page);
        if(signin.length!==2||signin[1].path!=='/ingest'||!signin[1].text.includes('aanmelden'))
          throw Error('sign-in redirect not reported or run not stopped: '+JSON.stringify(signin));
        results[username].signin=signin;
        // A publisher refused with publisher_role_required is a fault, not a skip.
        await post('/browser-faults',{'/publish':'role'});
        const role=(await run(page)).find(r=>r.path==='/publish');
        if(role.result!=='problem'||!role.text.includes('publisher_role_required'))throw Error('own role refusal hidden: '+JSON.stringify(role));
        // Closing and reopening Raad during a run keeps one run and shows its result.
        await post('/browser-faults',{});
        await page.getByRole('button',{name:"Controleer alle pagina's",exact:true}).click();
        // The probe frame is off screen and invisible while it loads a page.
        const frameStyle=await page.locator('iframe.care-probe').evaluate(f=>{const c=getComputedStyle(f);return {visibility:c.visibility,left:parseInt(c.left)};});
        if(frameStyle.visibility!=='hidden'||frameStyle.left>-1000)throw Error('probe frame visible: '+JSON.stringify(frameStyle));
        await page.getByRole('button',{name:'Sluit Raad'}).click();
        await page.getByRole('button',{name:/Open Raad/}).click();
        if(!await page.getByRole('button',{name:"Controleer alle pagina's",exact:true}).isDisabled())throw Error('second run possible while running');
        await page.getByRole('button',{name:'Kopieer uitslag'}).waitFor({timeout:120000});
        if(await page.locator('[data-deploy-page]').count()!==healthy.length)throw Error('reopened panel missed the result');
                await post('/browser-faults',{'/ingest':'unauth'});
        const unauth=await run(page);
        if(unauth.length!==2||!unauth[1].text.includes('aanmelden'))
          throw Error('local session expiry not reported or run not stopped: '+JSON.stringify(unauth));
        await post('/browser-faults',{});
        // Another account in the same tab never sees this account's stored run.
        await page.getByRole('button',{name:'Uitloggen'}).click();
        await page.goto(base+'/login');
        await page.locator('[name=username]').fill(manifest.reviewer);
        await page.locator('[name=password]').fill(manifest.password);
        await Promise.all([page.waitForURL(base+'/'),page.locator('button[type=submit]').click()]);
        if(await page.locator('[data-care-body]').isHidden())await page.getByRole('button',{name:/Open Raad/}).click();
        await page.getByRole('heading',{name:'Controle na deploy'}).waitFor();
        if(await page.locator('[data-deploy-page]').count())throw Error('previous account result shown');
      }
      if(await page.locator('iframe.care-probe').count())throw Error('probe frame left behind');
      await page.close();
    }
    const after=await (await fetch(base+'/browser-domain-state')).json();
    if(before.sha256!==after.sha256)throw Error('deploy check changed domain authority');
    fs.writeFileSync(directory+'/deploy-check-result.json',JSON.stringify({...results,domainUnchanged:true},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});

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
      await page.getByRole('button',{name:/Open Raad/}).click();
      const healthy=await run(page);
      const paths=healthy.map(r=>r.path);
      for(const expected of ['/','/ingest','/source-selection','/review','/publish','/tree','/settings','/inzicht'])
        if(!paths.includes(expected))throw Error(username+' missing page '+expected+': '+JSON.stringify(paths));
      results[username]={healthy};
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
        await post('/browser-faults',{'/tree':'status','/publish':'banner','/review':'script'});
        const faulty=await run(page);
        const byPath=Object.fromEntries(faulty.map(r=>[r.path,r]));
        const expect=(path,needle)=>{ if(byPath[path].result!=='problem'||!byPath[path].text.includes(needle))throw Error(path+' not reported: '+JSON.stringify(byPath[path])); };
        expect('/tree','foutstatus 500');
        expect('/publish','fixture_failure');
        expect('/publish','req-fixture');
        expect('/review','1 scriptfout');
        if(faulty.filter(r=>r.result!=='ok').length!==3)throw Error('unexpected failures: '+JSON.stringify(faulty));
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
        await page.getByRole('button',{name:'Sluit Raad'}).click();
        await page.getByRole('button',{name:/Open Raad/}).click();
        if(!await page.getByRole('button',{name:"Controleer alle pagina's",exact:true}).isDisabled())throw Error('second run possible while running');
        await page.getByRole('button',{name:'Kopieer uitslag'}).waitFor({timeout:120000});
        if(await page.locator('[data-deploy-page]').count()!==8)throw Error('reopened panel missed the result');
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

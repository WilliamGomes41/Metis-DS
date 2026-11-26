const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const tasks=require('./browser_annotation_tasks.cjs');

(async()=>{
  const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
  const manifest=await(await fetch(base+'/browser-manifest')).json();
  const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base+'/login');
    await page.locator('[name=username]').fill(manifest.username);
    await page.locator('[name=password]').fill(manifest.password);
    await Promise.all([page.waitForURL(url=>url.pathname!='/login'),page.locator('button[type=submit]').click()]);
    await page.goto(base+'/ingest');
    const first='Het zorgplan is een overzicht van afspraken.',second='Controleer de huid dagelijks.';
    await page.locator('[name=file]').setInputFiles({name:'saved.html',mimeType:'text/html',
      buffer:Buffer.from('<html><body><p>'+first+'</p><p>'+second+'</p><p>Tijdens de ochtendronde.</p><p>Dit blijkt uit het onderzoek.</p></body></html>')});
    for(const [name,value] of Object.entries({title:'Opgeslagen werk terugvinden',version:'1',date:'2026-11-17',family:'test'}))
      await page.locator(`[name=${name}]`).fill(value);
    await page.locator('[name=class_]').selectOption('richtlijn');
    await page.locator('[name=review_option][value=uploader_sole]').check();
    await Promise.all([page.waitForURL(url=>url.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
    const sid=new URL(page.url()).searchParams.get('document');
    await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();
  await page.getByRole('button',{name:'Bevestig en ga annoteren',exact:true}).click();
    await page.locator('#annotation-editor-inputs:enabled').waitFor();
    const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
    const take=page.getByRole('button',{name:'Overnemen',exact:true});
    await take.waitFor();
    assert.equal((await read()).entries.length,0);
    assert.equal(await page.locator('#annotation-offer-ranges dd').count(),3);
    await page.screenshot({path:output+'/offer-desktop.png',fullPage:true});
    await take.click();
    await page.locator('#annotation-ready:enabled').waitFor();
    assert.deepEqual((await read()).entries[0].ranges.map(a=>a.role).sort(),['context','core','evidence']);
    await page.locator('dd[data-row=evidence] button.annotation-sign').first().click();
    await tasks.selectText(page,page.locator('[data-source-block]').filter({hasText:'Dit blijkt'}),'het onderzoek');
    await page.getByRole('button',{name:'Brontekst toevoegen aan Onderbouwing',exact:true}).click();
    await page.locator('dd[data-row=evidence]').getByText('het onderzoek',{exact:true}).waitFor();
    await page.locator('#annotation-ready:enabled').click();
    await take.waitFor();
    const next=page.locator('#annotation-offer-ranges dd');
    assert.equal(await next.first().innerText(),second);
    assert.equal((await read()).entries.filter(e=>e.status==='ready').length,1);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:output+'/offer-mobile.png',fullPage:true});
    await page.getByRole('button',{name:'Zelf selecteren',exact:true}).click();
    assert.equal((await read()).entries.length,1);
    await tasks.addAs(page,page.locator('[data-source-block]').filter({hasText:second}),second,'core');
    await page.locator('#annotation-ready:enabled').click();
    await page.getByText('Geen voorstel gevonden. Selecteer zelf een uitspraak.').waitFor();
    assert.equal((await read()).entries.filter(e=>e.status==='ready').length,2);
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});

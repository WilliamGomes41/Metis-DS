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
      buffer:Buffer.from('<html><body><p>'+first+'</p><p>'+second+'</p></body></html>')});
    for(const [name,value] of Object.entries({title:'Opgeslagen werk terugvinden',version:'1',date:'2026-11-17',family:'test'}))
      await page.locator(`[name=${name}]`).fill(value);
    await page.locator('[name=class_]').selectOption('richtlijn');
    await page.locator('[name=review_option][value=uploader_sole]').check();
    await Promise.all([page.waitForURL(url=>url.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
    const sid=new URL(page.url()).searchParams.get('document');
    await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();
    await page.locator('#annotation-editor-inputs:enabled').waitFor();
    assert.equal(await page.locator('#annotation-saved').count(),1,'the saved list must stay in the annotation workplace');
    const list=()=>page.locator('#annotation-saved-list li');
    const savedRow=text=>list().filter({hasText:text});
    const block=text=>page.locator('[data-source-block]').filter({hasText:text});
    const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
    const blank=()=>page.getByRole('heading',{name:'Selecteer de uitspraak in de bron',exact:true}).waitFor();
    const save=async text=>{
      await tasks.addAs(page,block(text),text,'core');
      await page.locator('#annotation-simple-type-select:enabled').waitFor();
      await page.locator('#annotation-ready:enabled').click();await blank();
      await savedRow(text).getByText('Opgeslagen',{exact:true}).waitFor();
    };
    assert.equal(await list().count(),0);
    await page.getByText('Nog geen annotaties opgeslagen.',{exact:false}).waitFor();
    await save(first);await save(second);
    assert.equal(await list().count(),2);
    let persisted=await read();
    const firstId=persisted.entries.find(item=>item.ranges.some(range=>range.quote===first)).annotation_id;
    assert(persisted.entries.every(item=>item.status==='ready'));
    assert.equal(Object.keys(persisted.object_bindings).length,0,'saving alone must not build objects');
    await page.reload();await page.locator('#annotation-editor-inputs:enabled').waitFor();
    assert.equal(await list().count(),2,'saved work survives a new page');
    await savedRow(first).getByRole('link').focus();await page.keyboard.press('Enter');
    await page.waitForURL(url=>url.searchParams.get('annotation')===firstId);
    await page.locator('#annotation-simple-rows dd[data-row=core]').getByText(first,{exact:true}).waitFor();
    assert.equal(await savedRow(first).getByRole('link').getAttribute('aria-current'),'true');

    // A failed update keeps the last committed version and prevents navigation through the list.
    await page.route('**/annotations/api',route=>route.request().method()==='POST' ? route.abort('failed') : route.continue());
    await tasks.addAs(page,block(second),second,'context');
    await page.locator('#annotation-status').filter({hasText:'Opslaan mislukt'}).waitFor();
    await savedRow(first).getByText('Wijzigingen nog niet opgeslagen; de opgeslagen versie is bewaard.',{exact:true}).waitFor();
    const oldUrl=page.url();
    await savedRow(second).getByRole('link').click();
    assert.equal(page.url(),oldUrl,'failed save must keep the active work open');
    persisted=await read();
    assert.equal(persisted.entries.find(item=>item.annotation_id===firstId).ranges.length,1);
    assert.equal(await list().count(),2);
    await page.unroute('**/annotations/api');
    page.once('dialog',dialog=>dialog.accept());
    await page.reload();await page.locator('#annotation-editor-inputs:enabled').waitFor();
    await savedRow(first).getByText('Opgeslagen',{exact:true}).waitFor();
    // Withdrawing a statement removes its row, then a new annotation can cover that same source.
    await page.locator('#annotation-simple-rows dd[data-row=core] button.annotation-sign').click();await blank();
    assert.equal(await list().count(),1);
    assert.equal((await read()).entries.find(item=>item.annotation_id===firstId).status,'withdrawn');
    await save(first);
    for(const width of [1440,390]) {
      await page.setViewportSize({width,height:1100});
      await page.evaluate(()=>window.scrollTo(0,0));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:output+'/saved-annotations-'+width+'.png',fullPage:true});
    }

    await page.locator('#annotation-saved-overview').click();
    await page.waitForURL(url=>url.searchParams.get('overview')==='true');
    await page.locator('#annotation-finalize').click();
    await page.waitForURL(url=>url.pathname==='/annotations/build');
    await page.goto(base+'/annotations?document='+sid);
    await savedRow(first).getByText('Wordt gebouwd',{exact:true}).waitFor();
    await savedRow(second).getByText('Wordt gebouwd',{exact:true}).waitFor();
    // Failed progress reads preserve the receipts and explicitly say freshness is unknown.
    let failPoll=true;
    await page.route('**/annotations/api?*',route=>{
      if(failPoll) {failPoll=false;return route.fulfill({status:503,contentType:'application/json',body:'{}'});}
      return route.continue();
    });
    await page.locator('#annotation-saved-notice').filter({hasText:'De voortgang kon niet worden opgehaald'}).waitFor();
    assert.equal(await list().count(),2);
    await page.evaluate(()=>fetch('/browser-release-build',{method:'POST'}));
    await savedRow(first).getByText('Beschikbaar voor Review',{exact:true}).waitFor({timeout:20000});
    await savedRow(second).getByText('Beschikbaar voor Review',{exact:true}).waitFor();
    assert.equal(await page.locator('#annotation-saved-notice').isVisible(),false);
    assert.equal(Object.keys((await read()).object_bindings).length,2);
    await savedRow(first).getByRole('link').click();
    await page.getByRole('button',{name:'Terug naar review',exact:true}).waitFor();
    assert.deepEqual(errors,[]);
    fs.writeFileSync(output+'/saved-annotations.json',JSON.stringify({
      savedAcrossNextAndReload:true,keyboardReopen:true,failedSaveKeepsReceipt:true,
      withdrawal:true,documentCheck:true,runningBuild:true,failedPollPreservesList:true,
      completedBuild:true,widths:[1440,390],errors
    },null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});

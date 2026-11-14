const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const tasks=require('./browser_annotation_tasks.cjs');
// #1067: the step form is retired. The card keeps the guarantees the guided form proved:
// a failed save keeps the work and retries exactly, another tab's newer save is never overwritten,
// and a new login resumes the saved work.
(async()=>{
 const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
 const manifest=await(await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
 try{
  let context=await browser.newContext({viewport:{width:1440,height:1000}});
  let page=await context.newPage();const errors=[];globalThis.metisProofPage=page;
  async function login(){
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base+'/login');await page.locator('[name=username]').fill(manifest.username);await page.locator('[name=password]').fill(manifest.password);
   await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('button[type=submit]').click()]);
  }
  await login();
  await page.goto(base+'/ingest');
  const statement='De huid wordt dagelijks gecontroleerd.',support='Onderzoek beschrijft dit verband.',extra='Bij volwassenen in de thuiszorg.';
  await page.locator('[name=file]').setInputFiles({name:'card.html',mimeType:'text/html',buffer:Buffer.from('<html><body><p>'+statement+'</p><p>'+support+'</p><p>'+extra+'</p></body></html>')});
  for(const [name,value] of Object.entries({title:'Kaart veerkracht',version:'1',date:'2026-11-13',family:'test'}))await page.locator(`[name=${name}]`).fill(value);
  await page.locator('[name=class_]').selectOption('richtlijn');await page.locator('[name=review_option][value=uploader_sole]').check();
  await Promise.all([page.waitForURL(u=>u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
  const sid=new URL(page.url()).searchParams.get('document');
  await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
  const block=text=>page.locator('[data-source-block]').filter({hasText:text.slice(0,20)});
  const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
  const row=key=>page.locator('#annotation-simple-rows dd[data-row='+key+']');
  const plus=key=>page.locator('#annotation-simple-rows dt[data-row='+key+'] button.annotation-sign');
  // Wait for what is stored, not for a status text (polled from Node: the page forbids eval).
  const stored=async test=>{for(let i=0;i<60;i++){const entry=(await read()).entries[0]||{};if(test(entry)) return;await page.waitForTimeout(250);}
    throw new Error('stored state never matched');};
  assert.equal(await page.locator('#annotation-steps').isVisible(),false);
  await tasks.selectText(page,block(statement),statement);
  await page.locator('#annotation-ready:enabled').click();
  await page.locator('#annotation-simple-type').waitFor();
  await page.locator('#annotation-simple-type-select').selectOption('explanation');
  await stored(entry=>entry.object_type==='explanation');
  const annotation=new URL(page.url()).searchParams.get('annotation');
  // 1. A failed save keeps the edit visible, offers a retry and keeps the page from closing.
  await page.route('**/annotations/api',route=>route.request().method()==='POST' ? route.abort() : route.continue());
  await plus('evidence').click();await tasks.selectText(page,block(support),support);
  await page.locator('#annotation-retry').waitFor();
  await row('evidence').getByText(support,{exact:true}).waitFor();
  assert.match(await page.locator('#annotation-status').innerText(),/^Opslaan mislukt\. /);
  assert.doesNotMatch(await page.locator('#annotation-status').innerText(),/Failed to fetch/);
  assert.equal((await read()).entries[0].ranges.some(a=>a.role==='evidence'),false);
  await page.screenshot({path:output+'/guided-failure-desktop.png',fullPage:true});
  await page.unroute('**/annotations/api');await page.locator('#annotation-retry').click();
  await stored(entry=>(entry.ranges||[]).some(a=>a.role==='evidence'));
  assert.equal((await read()).entries[0].ranges.some(a=>a.role==='evidence' && a.quote===support),true);
  // 2. Another tab saves later; this tab's older edit is refused, never written over it.
  const other=await context.newPage();
  await other.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  await other.locator('#annotation-editor-inputs:enabled').waitFor();
  await other.locator('#annotation-simple-rows dt[data-row=belongs] button.annotation-sign').click();
  await tasks.selectText(other,other.locator('[data-source-block]').filter({hasText:extra.slice(0,20)}),extra);
  await other.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await other.close();
  await page.locator('#annotation-simple-rows dd[data-row=evidence] .annotation-line').filter({hasText:support}).locator('button.annotation-sign').click();
  await page.locator('#annotation-save-conflict').waitFor();
  let entry=(await read()).entries[0];
  assert.equal(entry.ranges.some(a=>a.quote===extra),true,'the other tab’s save stays');
  assert.equal(entry.ranges.some(a=>a.quote===support),true,'the refused edit did not overwrite anything');
  await page.screenshot({path:output+'/guided-conflict-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:output+'/guided-conflict-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  // 3. Reopening shows the stored version; finishing then succeeds, and a new login resumes it.
  await page.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  await row('belongs').getByText(extra,{exact:true}).waitFor();
  await page.locator('#annotation-ready:enabled').click();
  await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
  assert.equal((await read()).entries[0].status,'ready');
  await page.screenshot({path:output+'/guided-ready-desktop.png',fullPage:true});
  await context.close();
  context=await browser.newContext({viewport:{width:390,height:844}});page=await context.newPage();globalThis.metisProofPage=page;await login();
  await page.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  await row('core').getByText(statement,{exact:true}).waitFor();
  assert.equal((await read()).entries[0].status,'ready');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.ok(await page.locator('.annotation-document').evaluate(node=>node.getBoundingClientRect().height)>120,'Source reader must remain visible on mobile');
  await page.screenshot({path:output+'/guided-resumed-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:output+'/guided-resumed-desktop.png',fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/guided-result.json',JSON.stringify({annotation,retry:true,olderEditRefused:true,resumed:true,errors}));
 }catch(error){await tasks.describeCard(globalThis.metisProofPage);throw error;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

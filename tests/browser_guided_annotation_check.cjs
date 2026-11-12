const {selectText}=require('./browser_annotation_tasks.cjs');
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
 const m=await(await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/login');await page.locator('[name=username]').fill(m.username);await page.locator('[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('button[type=submit]').click()]);
  await page.goto(base+'/ingest');
  await page.locator('[name=file]').setInputFiles({name:'guided.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Annoteren zonder omwegen</h1><p>De kwetsbare huid verklaart de pijn.</p><p>Alleen bij klachten.</p></body></html>')});
  for(const [field,value] of Object.entries({title:'Betekenis en context van een uitspraak bij kwetsbare huid',version:'1',date:'2026-11-11',family:'test'})) await page.locator(`[name=${field}]`).fill(value);
  await page.locator('[name=class_]').selectOption('richtlijn');await page.locator('[name=review_option][value=uploader_sole]').check();
  await Promise.all([page.waitForURL(u=>u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
  const sid=new URL(page.url()).searchParams.get('document');
  await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  const step=async n=>{await page.locator('#annotation-step-'+n).click();};
  const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
  const saved=()=>page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  const source=page.locator('[data-source-block]').filter({hasText:'De kwetsbare huid verklaart de pijn.'});
  const primaryCount=async()=>assert.equal(await page.locator('#annotation-controls .btn-primary:visible').count(),1);
  assert.equal(await page.locator('#annotation-source-input,.annotation-selection-help').count(),0);
  assert.equal(await page.locator('#annotation-selection').innerText(),'');
  assert.match(await page.locator('#annotation-status').innerText(),/Nog niets opgeslagen/);
  assert.equal((await read()).entries.length,0);
  assert.equal(await page.locator('#annotation-task-1').isVisible(),true);await primaryCount();
  await page.screenshot({path:output+'/guided-select-desktop.png',fullPage:true});
  await page.locator('#annotation-type').selectOption('explanation');await source.click();await page.locator('#annotation-select-block').click();
  const selectedQuote=await page.locator('#annotation-selection').innerText();
  const sourceTop=await page.locator('.annotation-document').evaluate(node=>node.scrollTop);
  await step(2);assert.equal(await page.locator('#annotation-selection').innerText(),selectedQuote);
  await step(1);assert.equal(await page.locator('.annotation-document').evaluate(node=>node.scrollTop),sourceTop);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'annotation-heading-1');
  await page.locator('#annotation-add').click();await page.locator('#annotation-add').click();
  assert.equal(await page.locator('#annotation-task-2').isVisible(),true);
  assert.equal(await page.locator('#annotation-type').isVisible(),false);await primaryCount();
  // Run the same server checks before claiming completion, without a circular draft gate.
  await step(3);await page.locator('#annotation-check').getByText(/controlepunten/).waitFor();
  assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
  assert.match(await page.locator('#annotation-check').innerText(),/onderbouwing|onderwerp|gezegd/);
  let view=await read();assert.equal(view.entries[0].status,'draft');
  assert.equal(await page.locator('#annotation-check').innerText().then(t=>t.includes('nog niet gereed')),false);
  await step(2);
  for(const [field,text] of [['subject_span','De kwetsbare huid'],['predicate_span','verklaart'],['supported_object','de pijn']]) {
   await page.locator(`[data-field="${field}"]`).click();
   await source.click();
   await selectText(page,source,text);
   await primaryCount();await page.locator('#annotation-add').click();
  }
  await page.locator('#annotation-na').check();await saved();
  // A type-change warning leaves saved work intact until explicit confirmation.
  await step(1);await page.locator('#annotation-type').selectOption('definition');
  assert.equal(await page.locator('#annotation-confirm').isVisible(),true);
  await page.locator('#annotation-confirm-cancel').click();
  assert.equal(await page.locator('#annotation-type').inputValue(),'explanation');
  assert.equal((await read()).entries[0].object_type,'explanation');await step(2);
  const annotation=(await read()).entries[0].annotation_id;
  assert.equal(new URL(page.url()).searchParams.get('annotation'),annotation,'Reload must retain the current saved annotation');
  await page.screenshot({path:output+'/guided-meaning-desktop.png',fullPage:true});
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-ready:enabled').waitFor();await primaryCount();
  // Changing an answer invalidates the previous check immediately.
  await step(2);await page.locator('[data-field=subject_span]').click();await page.locator('#annotation-fields select:visible').selectOption('uncertain');
  await step(3);await page.locator('#annotation-check').getByText(/controlepunten/).waitFor();
  assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
  await page.locator('#annotation-check button').filter({hasText:'over wie of wat'}).click();
  assert.equal(await page.locator('#annotation-task-2').isVisible(),true);
  await source.click();await selectText(page,source,'De kwetsbare huid');
  await page.locator('#annotation-add').click();
  // Answering the opened point returns to the check; other fields stayed out of view.
  await page.locator('#annotation-ready:enabled').waitFor();
  assert.equal(await page.locator('#annotation-task-3').isVisible(),true);
  // Storage failure must retain the edit and block navigation until an exact retry succeeds.
  await step(2);await page.route('**/annotations/api',route=>route.abort());
  await page.locator('#annotation-na').uncheck();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent.startsWith('Opslaan mislukt.'));
  await page.locator('#annotation-more summary').click();await page.locator('#annotation-pause').click();assert.equal(new URL(page.url()).pathname,'/annotations');
  await page.unroute('**/annotations/api');await page.locator('#annotation-retry').click();await saved();
  await page.locator('#annotation-na').check();await saved();
  await step(3);await page.locator('#annotation-ready:enabled').waitFor();
  await page.screenshot({path:output+'/guided-check-desktop.png',fullPage:true});
  // Another tab may save after the displayed check. Rechecking must refuse to
  // use its newer basis with our older writer, without silently overwriting it.
  const other=await page.context().newPage();
  await other.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  await other.locator('#annotation-step-2').click();await other.locator('#annotation-na').uncheck();
  await other.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await other.locator('#annotation-na').check();
  await other.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent.includes('opgeslagen werk is gewijzigd'));
  assert.equal((await read()).entries[0].status,'draft');
  assert.equal(await page.locator('#annotation-ready').isDisabled(),true);await other.close();
  await page.reload();await step(3);await page.locator('#annotation-ready:enabled').waitFor();
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
  view=await read();assert.equal(view.entries[0].status,'ready');
  assert.equal(view.entries[0].field_evidence.predicate_span.span.end-view.entries[0].field_evidence.predicate_span.span.start,9);
  await primaryCount();assert.equal(await page.locator('#annotation-new').isVisible(),true);
  await page.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  assert.equal(await page.locator('#annotation-task-3').isVisible(),true);
  assert.equal((await read()).entries[0].status,'ready');
  for(const [task,width] of [[1,390],[2,390],[3,390]]) {
   await page.setViewportSize({width,height:844});await step(task);await primaryCount();
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.ok(await page.locator('.annotation-document').evaluate(node=>node.getBoundingClientRect().height)>120,'Source reader must remain visible on mobile');
   await page.screenshot({path:output+`/guided-task-${task}-mobile.png`,fullPage:true});
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/guided-result.json',JSON.stringify({annotation,threeTasks:true,onePrimary:true,readOnlyCheck:true,repair:true,retry:true,readyPersisted:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

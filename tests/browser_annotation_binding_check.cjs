const tasks=require('./browser_annotation_tasks.cjs');
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.METIS_BROWSER_BASE, output=process.env.METIS_BROWSER_OUTPUT;
 const m=await(await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/login');
  await page.locator('[name=username]').fill(m.username);
  await page.locator('[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('button[type=submit]').click()]);
  await page.goto(base+'/ingest');
  await page.locator('[name=file]').setInputFiles({name:'one-binding.html',mimeType:'text/html',buffer:Buffer.from(
   '<html><body><h1>Voorbeeldbron</h1><p>Beoordeel de huid.</p><p>Alleen bij klachten.</p><p>Voor volwassenen.</p></body></html>')});
  await page.locator('[name=title]').fill('Eén contextbinding');
  await page.locator('[name=version]').fill('1');
  await page.locator('[name=date]').fill('2026-11-10');
  await page.locator('[name=class_]').selectOption('richtlijn');
  await page.locator('[name=family]').fill('test');
  await page.locator('[name=review_option][value=uploader_sole]').check();
  await Promise.all([page.waitForURL(u=>u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
  const sid=new URL(page.url()).searchParams.get('document');
  // A slow module must not discard a type choice that the controls accept.
  let releaseModule, requestedModule;
  const moduleRequested=new Promise(resolve=>{requestedModule=resolve;});
  await page.route('**/annotations/binding.mjs',async route=>{
   const gate=new Promise(resolve=>{releaseModule=resolve;});
   requestedModule();await gate;await route.continue();
  });
  await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click({noWaitAfter:true});
  await page.locator('[data-source-block]').first().waitFor();
  await moduleRequested;
  const type=page.locator('#annotation-type');
  const acceptedBeforeReady=await type.isEnabled();
  if(!acceptedBeforeReady) {
   assert.equal(await page.getByText('De annotatiewerkplek wordt klaargezet.',{exact:true}).isVisible(),true);
  }
  // Screenshots wait for fonts/load; release the held module before capturing.
  if(acceptedBeforeReady) await type.selectOption('source_disposition');
  releaseModule();await page.waitForLoadState('load');
  await page.unroute('**/annotations/binding.mjs');
  assert.deepEqual(errors,[]);
  if(!acceptedBeforeReady) await type.selectOption('source_disposition');
  assert.equal(await type.inputValue(),'source_disposition','type choice accepted before initialization was lost');
  assert.equal(await page.locator('#annotation-source-reason').isVisible(),true);
  await tasks.type(page,'');
  const initialSource=await page.locator('#annotation-source-input').inputValue();
  assert.equal(await page.locator('#annotation-add').isDisabled(),true);
  await page.locator('[data-source-block]').filter({hasText:'Beoordeel de huid.'}).click();
  await page.locator('#annotation-select-block').click();
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-type').selectOption('recommendation');
  await tasks.role(page,'condition');
  await page.locator('#annotation-essential').check();
  const condition=page.locator('[data-source-block]').filter({hasText:'Alleen bij klachten.'});
  const blockId=await condition.getAttribute('data-source-block');
  await condition.click();
  await page.locator('#annotation-select-block').click();
  await page.locator('#annotation-add').click();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  const read=()=>page.evaluate(async sid=>{const r=await fetch('/annotations/api?document='+sid);if(!r.ok)throw Error('read failed');return r.json();},sid);
  let view=await read();
  assert.equal(view.entries.length,1);
  const entry=view.entries[0], anchor={block_id:blockId,start:0,end:Array.from('Alleen bij klachten.').length};
  // One add must persist the context AND its meaning field without another selection.
  assert.deepEqual(entry.field_evidence.condition_span.span,anchor,'context binding did not bind its meaning field');
  assert.ok(entry.ranges.some(r=>r.role==='condition'&&r.required_for_meaning&&r.block_id===blockId));
  assert.equal(initialSource,'','opening the editor must not preselect the document title');
  assert.equal(entry.pending_range,null);
  const annotation=entry.annotation_id;
  await page.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  view=await read();assert.equal(view.entries[0].annotation_id,annotation);
  assert.deepEqual(view.entries[0].field_evidence.condition_span.span,anchor);
  await page.screenshot({path:output+'/binding-desktop.png',fullPage:true});
  // A new selection must not silently inherit an answer about essentiality.
  await tasks.role(page,'population');
  await page.locator('[data-source-block]').filter({hasText:'Voor volwassenen.'}).click();
  await page.locator('#annotation-select-block').click();
  assert.equal(await page.locator('#annotation-add').isDisabled(),true);
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.reload();
  assert.match(await page.locator('#annotation-selection').innerText(),/Nog te koppelen: Voor volwassenen/);
  assert.equal(await page.locator('#annotation-add').isDisabled(),true);
  assert.equal(await page.locator('#annotation-essential').isChecked(),false);
  assert.equal(await page.locator('#annotation-additional').isChecked(),false);
  await page.locator('#annotation-additional').check();
  assert.equal(await page.locator('#annotation-add').isEnabled(),true);
  await page.locator('#annotation-add').click();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  view=await read();assert.equal(view.entries[0].ranges.find(r=>r.role==='population').required_for_meaning,false);
  assert.ok(view.entries[0].field_evidence.target_group_span.span);
  await page.setViewportSize({width:390,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:output+'/binding-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/binding-result.json',JSON.stringify({annotation,conditionAndFieldStored:true,explicitEssentiality:true,initialSelection:'empty',pageErrors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

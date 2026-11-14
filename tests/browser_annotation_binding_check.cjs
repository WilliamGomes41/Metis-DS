const tasks=require('./browser_annotation_tasks.cjs');
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
// #1067: the step form with roles, essentiality and meaning fields is retired. What remains to prove here:
// a slow card module loses nothing, and text added with '+' is stored as exact source context.
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
  // A slow module keeps the card closed until it can save; nothing typed or selected is lost.
  let releaseModule, requestedModule;
  const moduleRequested=new Promise(resolve=>{requestedModule=resolve;});
  await page.route('**/annotations/binding.mjs',async route=>{
   const gate=new Promise(resolve=>{releaseModule=resolve;});
   requestedModule();await gate;await route.continue();
  });
  await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click({noWaitAfter:true});
  await page.locator('[data-source-block]').first().waitFor();
  await moduleRequested;
  // While the module is held the card cannot save; if its controls are closed, it says why.
  if(await page.locator('#annotation-editor-inputs').isDisabled())
    assert.equal(await page.getByText('De annotatiewerkplek wordt klaargezet.',{exact:true}).isVisible(),true);
  releaseModule();await page.waitForLoadState('load');
  await page.unroute('**/annotations/binding.mjs');
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  assert.equal(await page.locator('#annotation-steps').isVisible(),false);
  const row=key=>page.locator('#annotation-simple-rows dd[data-row='+key+']');
  const plus=key=>page.locator('#annotation-simple-rows dt[data-row='+key+'] button.annotation-sign');
  await tasks.selectText(page,page.locator('[data-source-block]').filter({hasText:'Beoordeel de huid.'}),'Beoordeel de huid.');
  await row('core').getByText('Beoordeel de huid.',{exact:true}).waitFor();
  await page.locator('#annotation-ready:enabled').click();
  await page.locator('#annotation-simple-type').waitFor();
  await page.locator('#annotation-simple-type-select').selectOption('recommendation');
  const condition=page.locator('[data-source-block]').filter({hasText:'Alleen bij klachten.'});
  const blockId=await condition.getAttribute('data-source-block');
  await plus('belongs').click();
  await tasks.selectText(page,condition,'Alleen bij klachten.');
  await row('belongs').getByText('Alleen bij klachten.',{exact:true}).waitFor();
  const read=()=>page.evaluate(async sid=>{const r=await fetch('/annotations/api?document='+sid);if(!r.ok)throw Error('read failed');return r.json();},sid);
  await page.waitForFunction(async sid=>((await (await fetch('/annotations/api?document='+sid)).json()).entries[0]?.ranges||[]).length===2,sid);
  const entry=(await read()).entries[0];
  const added=entry.ranges.find(r=>r.role==='context');
  assert.deepEqual({block_id:added.block_id,start:added.start,end:added.end},{block_id:blockId,start:0,end:Array.from('Alleen bij klachten.').length});
  assert.equal(added.required_for_meaning,false);
  assert.equal(entry.pending_range,null);
  // The statement is recorded as the evidence of its own type on every save.
  assert.deepEqual(entry.field_evidence.recommendation_evidence_span,{core:true});
  await page.screenshot({path:output+'/binding-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:output+'/binding-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/binding-result.json',JSON.stringify({slowModuleSafe:true,contextStoredExactly:true,typeEvidenceIsTheStatement:true,pageErrors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

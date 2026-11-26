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
  const page=await browser.newPage({viewport:{width:1440,height:1000}});globalThis.metisProofPage=page;
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
  await page.getByRole('button',{name:'Bevestig en ga annoteren',exact:true}).click({noWaitAfter:true});
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
  await tasks.selectText(page,page.locator('[data-source-block]').filter({hasText:'Beoordeel de huid.'}),'Beoordeel de huid.');
  await row('core').getByText('Beoordeel de huid.',{exact:true}).waitFor();
  // #1067: a slow check (as in CI) keeps 'Gereed' running; the kind control must wait instead of completing that save.
  await page.route('**/annotations/check**',async route=>{await new Promise(r=>setTimeout(r,1500));await route.continue();});
  await page.locator('#annotation-ready:enabled').click();
  await page.locator('#annotation-simple-type').waitFor();
  await page.locator('#annotation-simple-type-select').selectOption('recommendation');
  const condition=page.locator('[data-source-block]').filter({hasText:'Alleen bij klachten.'});
  const blockId=await condition.getAttribute('data-source-block');
  // The card renders the edit before autosave commits it. Wait for the POST
  // that actually includes this context before reading the saved annotation.
  const [contextSave]=await Promise.all([
   page.waitForResponse(response=>{
    const request=response.request();
    if(request.method()!=='POST' || new URL(response.url()).pathname!=='/annotations/api') return false;
    return request.postDataJSON().selection.ranges.some(range=>range.role==='context' && range.block_id===blockId);
   }),
   tasks.addAs(page,condition,'Alleen bij klachten.','context'),
  ]);
  assert.equal(contextSave.ok(),true,'The selected context must save successfully');
  await row('context').getByText('Alleen bij klachten.',{exact:true}).waitFor();
  const read=()=>page.evaluate(async sid=>{const r=await fetch('/annotations/api?document='+sid);if(!r.ok)throw Error('read failed');return r.json();},sid);
  const annotationId=contextSave.request().postDataJSON().annotation_id;
  const entry=(await read()).entries.find(item=>item.annotation_id===annotationId);
  assert.ok(entry,'The annotation acknowledged by autosave must be readable');
  assert.equal(entry.ranges.length,2);
  const added=entry.ranges.find(r=>r.role==='context');
  assert.ok(added,'The saved annotation must contain context');
  assert.deepEqual({block_id:added.block_id,start:added.start,end:added.end},{block_id:blockId,start:0,end:Array.from('Alleen bij klachten.').length});
  assert.equal('required_for_meaning' in added,false);
  assert.equal(entry.pending_range,null);
  // The statement is recorded as the evidence of its own type on every save.
  assert.deepEqual(entry.field_evidence.recommendation_evidence_span,{core:true});
  await page.screenshot({path:output+'/binding-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:output+'/binding-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/binding-result.json',JSON.stringify({slowModuleSafe:true,contextStoredExactly:true,typeEvidenceIsTheStatement:true,pageErrors:errors}));
 }catch(error){await tasks.describeCard(globalThis.metisProofPage);throw error;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

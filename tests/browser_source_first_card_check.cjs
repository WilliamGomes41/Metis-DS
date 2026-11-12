const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const tasks=require('./browser_annotation_tasks.cjs');
// #1060 slice 2: the worker marks the statement, the text that belongs to it and the evidence.
(async()=>{
 const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
 const manifest=await(await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/login');await page.locator('[name=username]').fill(manifest.username);await page.locator('[name=password]').fill(manifest.password);
 await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('button[type=submit]').click()]);
 await page.goto(base+'/ingest');
 const intro='De volgende mechanismen spelen mogelijk een rol bij het risico op smetten:';
 const item='Bij diabetes mellitus zou de huid vatbaarder kunnen zijn voor irritatie en infecties.';
 const support='Onderzoek beschrijft dit verband.',failing='Foutvoorbeeld voor handmatig herstel.';
 await page.locator('[name=file]').setInputFiles({name:'smetten.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Smetten</h1><p>'+intro+'</p><p>'+item+'</p><p>'+support+'</p><p>'+failing+'</p></body></html>')});
 for(const [name,value] of Object.entries({title:'Richtlijn Smetten',version:'1',date:'2026-11-12',family:'test'}))await page.locator(`[name=${name}]`).fill(value);
 await page.locator('[name=class_]').selectOption('richtlijn');await page.locator('[name=review_option][value=uploader_sole]').check();
 await Promise.all([page.waitForURL(u=>u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
 const sid=new URL(page.url()).searchParams.get('document');
 await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 const block=text=>page.locator('[data-source-block]').filter({hasText:text.slice(0,25)});
 const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
 const current=async()=>(await read()).entries.find(e=>e.annotation_id===new URL(page.url()).searchParams.get('annotation'));
 const row=key=>page.locator('#annotation-simple-rows dd[data-row='+key+']');
 const buttons=()=>page.locator('#annotation-controls button:visible').count();
 // Empty card: one instruction, no steps, no form, no competing actions.
 assert.equal(await page.locator('#annotation-steps').isVisible(),false);
 assert.equal(await page.locator('#annotation-simple-heading').innerText(),'Wijs de uitspraak aan');
 assert.equal(await page.locator('#annotation-fields, #annotation-type, #annotation-suggest').filter({visible:true}).count(),0);
 assert.equal(await buttons(),0);
 // 1. The statement. Metis derives type and parts in the background; nothing to fill in.
 await tasks.selectText(page,block(item),item);
 assert.equal(await page.locator('#annotation-simple-core').isVisible(),true);
 assert.equal(await page.locator('#annotation-simple-belongs').isVisible(),false);
 await page.locator('#annotation-simple-core').click();
 await row('evidence').and(page.locator('[data-open]')).waitFor();await row('belongs').getByText(/leunt mogelijk/).waitFor();
 // No question about what the worker just did, and no annotation switcher above the work.
 assert.equal(await page.locator('#annotation-simple-heading').isVisible(),false);
 assert.equal(await page.locator('#annotation-entry').isVisible(),false);
 assert.match(await row('core').innerText(),/Bij diabetes mellitus/);
 assert.equal(await page.locator('#annotation-simple-type').isVisible(),false);
 assert.match(await row('belongs').innerText(),/leunt mogelijk op andere tekst/);
 assert.equal(await page.locator('#annotation-simple-notes li').count(),0);
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 await page.screenshot({path:output+'/card-statement.png',fullPage:true});
 // 2. The text that belongs to it.
 await tasks.selectText(page,block(intro),intro);
 assert.equal(await page.locator('#annotation-simple-core').isVisible(),false);
 await page.locator('#annotation-simple-belongs').click();
 await row('belongs').getByText(intro).waitFor();
 // 3. The evidence choice. Then one button finishes.
 await row('evidence').getByRole('button',{name:/Staat niet in de bron/}).click();
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await page.locator('#annotation-controls .btn-primary:visible').count(),1);
 await page.screenshot({path:output+'/card-complete.png',fullPage:true});
 await page.locator('#annotation-ready').click();
 await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
 let entry=await current();
 assert.equal(entry.status,'ready');assert.equal(entry.object_type,'explanation');assert.equal(entry.evidence_not_applicable,true);
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote,a.required_for_meaning]),[['core',item,false],['context',intro,true]]);
 assert.deepEqual(entry.field_evidence.supported_object,{span:null,missing_reason:'not_stated'});
 // Metis unavailable: the only question is the type; evidence can be pointed at in the source.
 await page.locator('#annotation-new').click();
 await tasks.selectText(page,block(failing),failing);await page.locator('#annotation-simple-core').click();
 await page.locator('#annotation-simple-type').waitFor();
 await page.locator('#annotation-simple-type-select').selectOption('explanation');
 await page.waitForFunction(()=>document.getElementById('annotation-simple-type').hidden);
 await tasks.selectText(page,block(support),support);await page.locator('#annotation-simple-evidence').click();
 await row('evidence').getByText(support).waitFor();
 await page.locator('#annotation-ready:enabled').waitFor();
 entry=await current();
 assert.equal(entry.status,'draft');assert.equal(entry.object_type,'explanation');
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.evidence_function]),[['core',null],['evidence','supported_by']]);
 // A marked passage in the source opens its own annotation.
 await block(item).locator('mark[data-annotation]').first().click();
 await row('belongs').getByText(intro).waitFor();
 assert.match(await row('core').innerText(),/Bij diabetes mellitus/);
 await block(failing).locator('mark[data-annotation]').first().click();
 await row('evidence').getByText(support).waitFor();
 // Removing linked evidence reopens the choice without leaving the card.
 await row('evidence').getByRole('button',{name:/Weghalen/}).click();
 await row('evidence').and(page.locator('[data-open]')).waitFor();
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/card-mobile.png',fullPage:true});
 // The step form stays reachable as the advanced form and survives a reload.
 await page.setViewportSize({width:1440,height:1000});await tasks.advanced(page);
 assert.equal(await page.locator('#annotation-steps').isVisible(),true);
 await page.reload();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 assert.equal(await page.locator('#annotation-steps').isVisible(),true);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/source-first-card-result.json',JSON.stringify({threeRows:true,derivedInBackground:true,typeQuestionOnlyOnFailure:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

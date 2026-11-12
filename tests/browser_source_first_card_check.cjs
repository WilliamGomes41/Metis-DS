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
 assert.equal(await page.locator('#annotation-simple-heading').innerText(),'Selecteer de uitspraak in de bron');
 assert.equal(await page.locator('#annotation-fields, #annotation-type, #annotation-suggest, #annotation-entry').filter({visible:true}).count(),0);
 // Only one action exists before anything is selected: there is nothing to save yet.
 assert.deepEqual(await page.locator('#annotation-controls button:visible').allInnerTexts(),['Opslaan en bronselectie beëindigen']);
 const plus=key=>page.locator('#annotation-simple-rows dt[data-row='+key+'] button.annotation-sign');
 const minus=(key,text)=>row(key).locator('.annotation-line').filter({hasText:text}).locator('button.annotation-sign');
 // 1. Selecting is the statement: the text appears, nothing to confirm or fill in.
 await tasks.selectText(page,block(item),item.slice(0,40));
 await row('core').getByText(item.slice(0,40),{exact:true}).waitFor();
 // A new selection simply replaces it while nothing else has been done.
 await tasks.selectText(page,block(item),item);
 await row('core').getByText(item,{exact:true}).waitFor();
 assert.equal(await row('core').locator('.annotation-line').count(),1);
 assert.equal(await page.locator('#annotation-simple-heading').isVisible(),false);
 // 2. '+' on "Hoort erbij": Metis reads the statement in the background, then the next selection is added.
 await plus('belongs').click();
 await row('belongs').getByText(/leunt mogelijk op andere tekst|Selecteer de tekst in de bron/).waitFor();
 await page.waitForFunction(()=>!document.getElementById('annotation-simple-status').textContent.startsWith('Metis leest'));
 assert.equal(await page.locator('#annotation-simple-type').isVisible(),false);
 assert.equal(await plus('belongs').getAttribute('aria-pressed'),'true');
 await page.screenshot({path:output+'/card-statement.png',fullPage:true});
 await tasks.selectText(page,block(intro),intro);
 await row('belongs').getByText(intro,{exact:true}).waitFor();
 assert.equal(await plus('belongs').getAttribute('aria-pressed'),'false');
 // 3. The evidence choice. Then one button finishes.
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 await row('evidence').getByRole('button',{name:'Staat niet in de bron',exact:true}).click();
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await page.locator('#annotation-controls .btn-primary:visible').count(),1);
 await page.screenshot({path:output+'/card-complete.png',fullPage:true});
 // "+" and "−" share one column: add beside the row title, remove beside each text.
 const column=await page.evaluate(()=>[...document.querySelectorAll('#annotation-simple-rows .annotation-sign')].map(b=>Math.round(b.getBoundingClientRect().right)));
 assert.equal(new Set(column).size,1,JSON.stringify(column));
 assert.equal(await page.locator('#annotation-ready').innerText(),'Opslaan en naar volgend kennisobject');
 const first=new URL(page.url()).searchParams.get('annotation');
 await page.locator('#annotation-ready').click();
 // Saved as ready, and the card is empty for the next statement: no second click, no other route.
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 assert.equal(await page.locator('#annotation-entry').isVisible(),false);
 let entry=(await read()).entries.find(e=>e.annotation_id===first);
 assert.equal(entry.status,'ready');assert.equal(entry.object_type,'explanation');assert.equal(entry.evidence_not_applicable,true);
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote,a.required_for_meaning]),[['core',item,false],['context',intro,false]]);
 assert.deepEqual(entry.field_evidence.supported_object,{span:null,missing_reason:'not_stated'});
 assert.deepEqual(entry.required_links,[]);
 // Metis unavailable: the only question is the type. Evidence is added with '+' and removed with '−'.
 await tasks.selectText(page,block(failing),failing.slice(0,13));
 await plus('evidence').click();
 await page.locator('#annotation-simple-type').waitFor();
 await page.locator('#annotation-simple-type-select').selectOption('explanation');
 await page.waitForFunction(()=>document.getElementById('annotation-simple-type').hidden);
 await tasks.selectText(page,block(support),support);
 await row('evidence').getByText(support,{exact:true}).waitFor();
 // A statement in two pieces: '+' on "Uitspraak" adds the next piece.
 await plus('core').click();await tasks.selectText(page,block(failing),failing.slice(14));
 await row('core').getByText(failing.slice(14),{exact:true}).waitFor();
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await page.locator('#annotation-simple-type').isVisible(),false);  // the chosen type is kept
 entry=await current();
 assert.equal(entry.status,'draft');assert.equal(entry.object_type,'explanation');
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote,a.evidence_function]),
  [['core',failing.slice(0,13),null],['evidence',support,'supported_by'],['core',failing.slice(14),null]]);
 // '−' removes without asking for a reason and reopens the evidence choice.
 await minus('evidence',support).click();
 await row('evidence').and(page.locator('[data-open]')).waitFor();
 await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 entry=await current();
 assert.deepEqual(entry.ranges.map(a=>a.role),['core','core']);assert.deepEqual(entry.required_links,[]);
 await page.locator('#annotation-required-links').waitFor({state:'attached'});
 assert.equal(await page.locator('#annotation-required-links *').count(),0);
 // A marked passage in the source opens its own annotation.
 await block(item).locator('mark[data-annotation]').first().click();
 await row('belongs').getByText(intro,{exact:true}).waitFor();
 assert.match(await row('core').innerText(),/Bij diabetes mellitus/);
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/card-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 // Ending source selection saves and opens the document check, where the next phase starts.
 await page.locator('#annotation-finish:enabled').click();
 await page.waitForURL(u=>u.searchParams.get('overview')==='true');
 await page.getByRole('link',{name:'Verder aanwijzen'}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 // The step form stays reachable as the advanced form and survives a reload.
 await page.setViewportSize({width:1440,height:1000});await tasks.advanced(page);
 assert.equal(await page.locator('#annotation-steps').isVisible(),true);
 await page.reload();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 assert.equal(await page.locator('#annotation-steps').isVisible(),true);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/source-first-card-result.json',JSON.stringify({threeRows:true,derivedInBackground:true,typeQuestionOnlyOnFailure:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

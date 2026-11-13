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
 const support='Onderzoek beschrijft dit verband.',failing='Foutvoorbeeld voor handmatig herstel.',alone='De huid wordt dagelijks gecontroleerd.';
 await page.locator('[name=file]').setInputFiles({name:'smetten.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Smetten</h1><p>'+intro+'</p><p>'+item+'</p><p>'+support+'</p><p>'+failing+'</p><p>'+alone+'</p></body></html>')});
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
 // 2. Slice 4: Metis points at the introduction the item leans on. The proposal is the exact
 // source text, marked apart in the source, and is answered with '+' or '−'.
 const proposal=row('belongs').locator('.annotation-proposal');
 await proposal.getByText(intro,{exact:true}).waitFor();
 assert.equal(await proposal.locator('.annotation-proposal-label').innerText(),'Voorstel van Metis');
 assert.equal(await block(intro).locator('mark[data-proposal]').innerText(),intro);
 assert.equal(await page.locator('#annotation-simple-type').isVisible(),false);
 await page.screenshot({path:output+'/card-statement.png',fullPage:true});
 // The proposal's '+' and '−' stay in the one column of signs, and its text lines up with the other texts.
 const edges=await page.evaluate(()=>({signs:[...document.querySelectorAll('#annotation-simple-rows .annotation-line .annotation-sign:last-child')].map(b=>Math.round(b.getBoundingClientRect().right)),
  texts:[...document.querySelectorAll('#annotation-simple-rows .annotation-line p')].map(p=>Math.round(p.getBoundingClientRect().left))}));
 assert.equal(new Set(edges.signs).size,1,JSON.stringify(edges));assert.equal(new Set(edges.texts).size,1,JSON.stringify(edges));
 await proposal.locator('[data-proposal=add]').click();
 await row('belongs').locator('.annotation-line:not(.annotation-proposal)').getByText(intro,{exact:true}).waitFor();
 assert.equal(await proposal.count(),0);
 await page.waitForFunction(()=>!document.querySelector('[data-source-block] mark[data-proposal]'));
 // 3. Evidence is added when the source has it; the card asks no choice. One button finishes.
 assert.equal(await row('evidence').getByRole('button',{name:/Staat niet in de bron|niet van toepassing/}).count(),0);
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
 assert.equal(entry.status,'ready');assert.equal(entry.object_type,'explanation');assert.equal(entry.evidence_not_applicable,false);
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote,a.required_for_meaning]),[['core',item,false],['list_introduction',intro,false]]);
 assert.deepEqual(entry.field_evidence.supported_object,{span:null,missing_reason:'not_stated'});
 assert.deepEqual(entry.required_links,[]);
 // A failed check leaves a visible retry in the card instead of two dead buttons.
 await block(item).locator('mark[data-annotation]').first().click();
 await row('belongs').getByText(intro,{exact:true}).waitFor();
 await page.route('**/annotations/check**',route=>route.abort());
 await minus('belongs',intro).click();
 await page.locator('#annotation-simple-recheck').waitFor();
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 await page.unroute('**/annotations/check**');
 await page.locator('#annotation-simple-recheck').click();
 // '−' on the linked introduction answered the proposal: it does not come back.
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await row('belongs').locator('.annotation-proposal').count(),0);
 await page.locator('#annotation-ready').click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 entry=(await read()).entries.find(e=>e.annotation_id===first);
 assert.equal(entry.status,'ready');assert.deepEqual(entry.ranges.map(a=>a.role),['core']);
 assert.deepEqual(entry.declined_context.map(r=>r.quote),[intro]);
 // A statement on its own is a complete object. The rule also proposes the list introduction here
 // (the known limit of slice 4): saving points at the proposal instead of passing it by.
 await tasks.selectText(page,block(alone),alone);
 await row('core').getByText(alone,{exact:true}).waitFor();
 await row('belongs').locator('.annotation-proposal').getByText(intro,{exact:true}).waitFor();
 await page.locator('#annotation-ready:enabled').click();
 await row('belongs').getByText('Beantwoord eerst het voorstel',{exact:false}).waitFor();
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.proposal),'add');
 assert.equal((await current()).status,'draft');
 await page.screenshot({path:output+'/card-proposal-open.png',fullPage:true});
 // The worker adds text alongside Metis: '+' on the row adds any number of passages, '−' removes one.
 // Neither answers the proposal.
 for(const text of [support,item]) {await plus('belongs').click();await tasks.selectText(page,block(text),text);
  await row('belongs').locator('.annotation-line:not(.annotation-proposal)').getByText(text,{exact:true}).waitFor();}
 await minus('belongs',item).click();
 await page.waitForFunction(item=>![...document.querySelectorAll('#annotation-simple-rows dd[data-row=belongs] .annotation-line:not(.annotation-proposal) p')].some(p=>p.textContent===item),item);
 await row('belongs').locator('.annotation-proposal').getByText(intro,{exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.setViewportSize({width:1440,height:1000});
 await row('belongs').locator('[data-proposal=decline]').click();
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await row('belongs').locator('.annotation-proposal').count(),0);
 await page.locator('#annotation-ready').click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 entry=(await read()).entries.find(e=>e.ranges.some(a=>a.quote===alone));
 assert.equal(entry.status,'ready');assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote]),[['core',alone],['context',support]]);
 assert.deepEqual(entry.declined_context.map(r=>r.quote),[intro]);
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
 // '−' removes without asking for a reason; the object can still be saved without evidence.
 await minus('evidence',support).click();
 await row('evidence').getByText(/Niets gekoppeld/).waitFor();
 await page.locator('#annotation-ready:enabled').waitFor();
 entry=await current();
 assert.deepEqual(entry.ranges.map(a=>a.role),['core','core']);assert.deepEqual(entry.required_links,[]);
 await page.locator('#annotation-required-links').waitFor({state:'attached'});
 assert.equal(await page.locator('#annotation-required-links *').count(),0);
 // Removing the last piece of the statement removes the object: no empty draft stays behind.
 const second=new URL(page.url()).searchParams.get('annotation');
 await minus('core',failing.slice(14)).click();
 await page.locator('#annotation-simple-type').waitFor();
 assert.equal(await row('core').locator('.annotation-line').count(),1);
 await minus('core',failing.slice(0,13)).click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 assert.equal((await read()).entries.find(e=>e.annotation_id===second).status,'withdrawn');
 // Nothing but the work and the two ways forward: no extra menu in the card.
 assert.equal(await page.locator('#annotation-more').isVisible(),false);
 // A marked passage in the source opens its own annotation.
 await block(item).locator('mark[data-annotation]').first().click();
 await row('core').getByText(item,{exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/card-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 // Ending source selection saves and opens the document check, where the next phase starts.
 await page.locator('#annotation-finish:enabled').click();
 await page.waitForURL(u=>u.searchParams.get('overview')==='true');
 // Text that is no statement is accounted for in the document check, where it shows up, not in the card.
 const gap=page.locator('.annotation-gap').filter({has:page.locator('q',{hasText:/^Smetten$/})});
 await gap.locator('select').selectOption('structure:document_structure');
 await Promise.all([page.waitForURL(u=>u.searchParams.get('overview')==='true' && u.hash==='#annotation-gaps'),gap.getByRole('button',{name:'Vastleggen'}).click()]);
 assert.equal(await page.locator('.annotation-gap q',{hasText:/^Smetten$/}).count(),0);
 assert((await read()).entries.some(e=>e.status==='ready' && e.disposition?.reason==='document_structure' && e.ranges[0].quote==='Smetten'));
 await page.screenshot({path:output+'/document-check-gaps.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.setViewportSize({width:1440,height:1000});
 // The card no longer offers that route: a selection is the statement.
 await page.getByRole('link',{name:'Verder aanwijzen'}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 await tasks.selectText(page,block(support),support);
 await row('core').getByText(support,{exact:true}).waitFor();
 assert.equal(await page.locator('#annotation-simple').getByText(/geen uitspraak/i).count(),0);
 assert.equal(await page.locator('#annotation-steps').isVisible(),false);
 assert.equal(await page.evaluate(()=>localStorage.getItem('metis-annotation-form')),null);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/source-first-card-result.json',JSON.stringify({threeRows:true,derivedInBackground:true,typeQuestionOnlyOnFailure:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

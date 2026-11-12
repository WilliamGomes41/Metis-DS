const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const tasks=require('./browser_annotation_tasks.cjs');
(async()=>{
 const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
 const manifest=await(await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:1100}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/login');await page.locator('[name=username]').fill(manifest.username);await page.locator('[name=password]').fill(manifest.password);
 await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('button[type=submit]').click()]);
 await page.goto(base+'/ingest');
 const core='Het zorgplan is een overzicht van afspraken.';
 await page.locator('[name=file]').setInputFiles({name:'meaning.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Begrip</h1><p>'+core+'</p><p>Een zorgplan is een overzicht van afspraken.</p><p>Foutvoorbeeld voor handmatig herstel.</p></body></html>')});
 for(const [name,value] of Object.entries({title:'Voorstel controleren',version:'1',date:'2026-11-11',family:'test'}))await page.locator(`[name=${name}]`).fill(value);
 await page.locator('[name=class_]').selectOption('richtlijn');await page.locator('[name=review_option][value=uploader_sole]').check();
 await Promise.all([page.waitForURL(u=>u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
 const sid=new URL(page.url()).searchParams.get('document');
 await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 const source=page.locator('[data-source-block]').filter({hasText:core});
 const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
 const saved=()=>page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
 assert.equal(await page.locator('#annotation-type').inputValue(),'');
 assert.equal(await page.locator('#annotation-controls .btn-primary:visible').count(),1);
 await tasks.selectText(page,source,core);await page.locator('#annotation-suggest').click();
 await page.locator('#annotation-editor-inputs:disabled').waitFor();
 assert.match(await page.locator('#annotation-suggestion-note').innerText(),/stelt betekenis voor/);
 await page.screenshot({path:output+'/meaning-pending.png',fullPage:true});
 await page.getByText('Betekenisvoorstel als concept opgeslagen.',{exact:false}).waitFor();
 assert.equal(await page.locator('#annotation-task-2').isVisible(),true);
 assert.equal(await page.locator('#annotation-type-summary').innerText(),'Definitie');
 assert.equal(await page.locator('#annotation-proposal-core').innerText(),core);
 let view=await read(),entry=view.entries[0];
 assert.equal(entry.status,'draft');assert.equal(entry.object_type,'definition');assert.equal(entry.evidence_not_applicable,false);
 assert.equal(entry.ranges.length,1);assert.equal(entry.ranges[0].quote,core);
 assert.equal(entry.field_evidence.defined_term.span.start,0);assert.equal(entry.field_evidence.defined_term.span.end,12);
 assert.equal(entry.field_evidence.definiens_span.span.start,16);
 await page.screenshot({path:output+'/meaning-proposed.png',fullPage:true});
 // Correct one proposed field through the existing source-binding interaction.
 await tasks.field(page,'subject_span');await tasks.selectText(page,source,'zorgplan');await page.locator('#annotation-add').click();await saved();
 view=await read();assert.equal(view.entries[0].field_evidence.subject_span.span.start,4);
 await page.reload();assert.equal((await read()).entries[0].field_evidence.subject_span.span.start,4);
 assert.equal((await read()).entries[0].status,'draft');
 await page.setViewportSize({width:390,height:844});await tasks.step(page,2);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/meaning-corrected-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1100});
 // A new source selection during I/O invalidates the old answer; neither type
 // nor old fields may overwrite the more recent draft.
 await page.locator('#annotation-entry').selectOption('');
 const changedSource=page.locator('[data-source-block]').filter({hasText:'Een zorgplan is'});
 await tasks.selectText(page,changedSource,'Een zorgplan is een overzicht van afspraken.');
 const started=page.waitForRequest(r=>r.url().endsWith('/annotations/suggest'));
 await page.locator('#annotation-suggest').click();await started;
 await tasks.selectText(page,changedSource,'zorgplan');
 await page.locator('#annotation-suggestion-note').filter({hasText:/gewijzigd/}).waitFor();
 let latest=(await read()).entries.find(e=>e.annotation_id===new URL(page.url()).searchParams.get('annotation'));
 assert.equal(latest.object_type,null);assert.equal(latest.field_evidence.subject_span.span,null);
 // Provider failure leaves a saved core and a usable manual path.
 await page.reload();await page.locator('#annotation-entry').selectOption('');
 const failure=page.locator('[data-source-block]').filter({hasText:'Foutvoorbeeld'});
 await tasks.selectText(page,failure,'Foutvoorbeeld voor handmatig herstel.');await page.locator('#annotation-suggest').click();
 await page.locator('#annotation-suggestion-note').filter({hasText:/vul de betekenis zelf in/}).waitFor();
 assert.equal(await page.locator('#annotation-editor-inputs').isDisabled(),false);
 latest=(await read()).entries.find(e=>e.annotation_id===new URL(page.url()).searchParams.get('annotation'));
 assert.equal(latest.status,'draft');assert.equal(latest.ranges[0].quote,'Foutvoorbeeld voor handmatig herstel.');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/suggestions-result.json',JSON.stringify({singleSelection:true,proposedType:true,draftOnly:true,correctedAndResumed:true,staleRejected:true,failurePreserved:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

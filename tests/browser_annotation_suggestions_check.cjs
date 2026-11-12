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
 await page.locator('[name=file]').setInputFiles({name:'meaning.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Begrip</h1><p>'+core+'</p><p>Een zorgplan is een overzicht van afspraken.</p><p>Foutvoorbeeld voor handmatig herstel.</p><p>De huid is droog en de huid is rood.</p></body></html>')});
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
 assert.match(await page.locator('#annotation-suggestion-note').innerText(),/leest je selectie/);
 await page.screenshot({path:output+'/meaning-pending.png',fullPage:true});
 await page.locator('#annotation-review-summary dd[data-open]').first().waitFor();
 // The proposal lands on the check: no field form, only what still needs an answer.
 assert.equal(await page.locator('#annotation-task-3').isVisible(),true);
 assert.equal(await page.locator('#annotation-fields').isVisible(),false);
 assert.equal(await page.locator('#annotation-review-summary dd[data-open]').count(),1);
 assert.equal(await page.locator('#annotation-review-summary dd[data-row=evidence][data-open]').count(),1);
 assert.match(await page.locator('#annotation-check').innerText(),/Nog 1 controlepunt open/);
 assert.equal(await page.locator('#annotation-suggestion-note').innerText(),'');
 assert.match(await page.locator('#annotation-review-summary').innerText(),/Definitie/);
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 assert.equal(await page.locator('#annotation-controls .btn-primary:visible').count(),1);
 let view=await read(),entry=view.entries[0];
 assert.equal(entry.status,'draft');assert.equal(entry.object_type,'definition');assert.equal(entry.evidence_not_applicable,false);
 assert.equal(entry.ranges.length,1);assert.equal(entry.ranges[0].quote,core);
 assert.equal(entry.field_evidence.defined_term.span.start,0);assert.equal(entry.field_evidence.defined_term.span.end,12);
 assert.equal(entry.field_evidence.definiens_span.span.start,16);
 await page.screenshot({path:output+'/meaning-proposed.png',fullPage:true});
 // Correct one proposed field through the existing source-binding interaction.
 // Anything that is wrong is adjusted from the row that shows it, then back to the overview.
 await page.locator('#annotation-review-summary dd[data-row=subject_span] button').click();
 assert.equal(await page.locator('#annotation-heading-2').innerText(),'Over wie of wat gaat de uitspraak?');
 assert.equal(await page.locator('#annotation-controls button:visible').count()<=6,true);
 await tasks.selectText(page,source,'zorgplan');await page.locator('#annotation-add').click();
 await page.locator('#annotation-review-summary dd[data-row=evidence][data-open]').waitFor();await saved();
 assert.equal(await page.locator('#annotation-review-summary dd[data-row=subject_span] span').first().innerText(),'zorgplan');
 view=await read();assert.equal(view.entries[0].field_evidence.subject_span.span.start,4);
 await page.reload();assert.equal((await read()).entries[0].field_evidence.subject_span.span.start,4);
 assert.equal((await read()).entries[0].status,'draft');
 await page.setViewportSize({width:390,height:844});await tasks.step(page,3);await page.locator('#annotation-review-summary dd[data-open]').first().waitFor();
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/meaning-corrected-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1100});
 // An ambiguous literal becomes one targeted question; answering it returns to the check.
 await page.locator('#annotation-entry').selectOption('');
 const twice=page.locator('[data-source-block]').filter({hasText:'De huid is droog'});
 await tasks.selectText(page,twice,'De huid is droog en de huid is rood.');await page.locator('#annotation-suggest').click();
 await page.locator('#annotation-review-summary dd[data-open]').first().waitFor();
 const asked=page.locator('#annotation-review-summary dd[data-row=predicate_span][data-open]');
 await asked.waitFor();assert.match(await asked.innerText(),/“is” komt meer dan eens voor/);
 assert.equal(await page.locator('#annotation-review-summary dd[data-open]').count(),2);
 let open=(await read()).entries.find(e=>e.annotation_id===new URL(page.url()).searchParams.get('annotation'));
 assert.deepEqual(open.field_evidence.predicate_span,{span:null,missing_reason:'uncertain'});
 assert.equal('open_points' in open,false);
 await asked.locator('button').click();
 assert.equal(await page.locator('#annotation-heading-2').innerText(),'Wat wordt daarover gezegd?');
 assert.equal(await page.locator('#annotation-fields dt').count(),1);
 assert.equal(await page.locator('#annotation-context-tools').isVisible(),false);
 await page.screenshot({path:output+'/meaning-question.png',fullPage:true});
 await tasks.selectText(page,twice,'is');await page.locator('#annotation-add').click();
 await page.locator('#annotation-review-summary dd[data-row=evidence][data-open]').waitFor();
 assert.equal(await page.locator('#annotation-task-3').isVisible(),true);
 assert.equal(await page.locator('#annotation-review-summary dd[data-row=predicate_span][data-open]').count(),0);
 open=(await read()).entries.find(e=>e.annotation_id===open.annotation_id);
 assert.deepEqual(open.field_evidence.predicate_span.span,{block_id:open.ranges[0].block_id,start:8,end:10});
 // The remaining point is evidence: answer it in place and finish without the field form.
 await page.locator('#annotation-review-summary dd[data-row=evidence] button').click();
 assert.equal(await page.locator('#annotation-meaning').isVisible(),false);
 await page.locator('#annotation-na').check();
 await page.locator('#annotation-ready:enabled').waitFor();await page.locator('#annotation-ready').click();
 await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
 assert.equal((await read()).entries.find(e=>e.annotation_id===open.annotation_id).status,'ready');
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
 fs.writeFileSync(output+'/suggestions-result.json',JSON.stringify({singleSelection:true,onlyOpenPoints:true,targetedQuestion:true,proposedType:true,draftOnly:true,correctedAndResumed:true,staleRejected:true,failurePreserved:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

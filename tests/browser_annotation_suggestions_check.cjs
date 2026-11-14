const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const tasks=require('./browser_annotation_tasks.cjs');
// #1067: Metis' proposal is applied in the card, in the background. The worker never corrects meaning
// fields or answers targeted questions (the step form is retired); what Metis cannot establish is a signal.
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
 await page.locator('[name=file]').setInputFiles({name:'meaning.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Begrip</h1><p>'+core+'</p><p>Een zorgplan is een overzicht van afspraken.</p><p>Foutvoorbeeld voor handmatig herstel.</p><p>De huid is droog en de huid is rood.</p><p>Controleer de huid dagelijks.</p><p>Doe dit elke ochtend.</p></body></html>')});
 for(const [name,value] of Object.entries({title:'Voorstel controleren',version:'1',date:'2026-11-11',family:'test'}))await page.locator(`[name=${name}]`).fill(value);
 await page.locator('[name=class_]').selectOption('richtlijn');await page.locator('[name=review_option][value=uploader_sole]').check();
 await Promise.all([page.waitForURL(u=>u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
 const sid=new URL(page.url()).searchParams.get('document');
 await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
 const current=async()=>(await read()).entries.find(e=>e.annotation_id===new URL(page.url()).searchParams.get('annotation'));
 const row=key=>page.locator('#annotation-simple-rows dd[data-row='+key+']');
 const plus=key=>page.locator('#annotation-simple-rows dt[data-row='+key+'] button.annotation-sign');
 const reading=()=>page.waitForFunction(()=>!document.getElementById('annotation-simple-status').textContent.startsWith('Metis leest'));
 // 1. The proposal lands in the background: type and sentence parts are stored, nothing is asked.
 const source=page.locator('[data-source-block]').filter({hasText:core});
 await tasks.selectText(page,source,core);
 await plus('belongs').click();
 await page.locator('#annotation-simple-status').filter({hasText:'Metis leest'}).waitFor();
 await page.screenshot({path:output+'/meaning-pending.png',fullPage:true});
 await reading();
 // #1067: Metis' kind shows in its own row and stays correctable.
 assert.equal(await page.locator('#annotation-simple-type-select').inputValue(),'definition');
 let entry=await current();
 assert.equal(entry.object_type,'definition');assert.equal(entry.ranges[0].quote,core);
 assert.equal(entry.field_evidence.defined_term.span.start,0);assert.equal(entry.field_evidence.defined_term.span.end,12);
 assert.equal(entry.field_evidence.definiens_span.span.start,16);
 await page.screenshot({path:output+'/meaning-proposed.png',fullPage:true});
 // #1067: the route says where the work is and what follows; '?' explains each row and stays open.
 assert.equal(await page.locator('nav.ko-route [aria-current=step]').innerText(),'Annoteren');
 assert.match(await page.locator('nav.ko-route .ko-route-next').innerText(),/^Hierna: /);
 const help=page.locator('#annotation-simple-rows dt[data-row=belongs] .annotation-help-toggle');
 await help.click();
 await page.locator('#annotation-help-belongs').getByText('Niet: waarom het klopt. Dat hoort bij Onderbouwing.').waitFor();
 assert.equal(await help.getAttribute('aria-expanded'),'true');
 // A wrong kind is corrected in the card: the selections stay, the kind is stored.
 // Codex P2: the check after a kind choice answers late and re-renders the card while the control has focus.
 let slowCheck=true;
 await page.route('**/annotations/check**',async route=>{if(slowCheck) await new Promise(r=>setTimeout(r,1500));await route.continue();});
 await page.locator('#annotation-simple-type-select').selectOption('explanation');
 await page.locator('#annotation-simple-type-select').focus();
 await page.waitForTimeout(2500);slowCheck=false;
 assert.equal(await page.evaluate(()=>document.activeElement?.id),'annotation-simple-type-select','A re-render must keep the kind control focused');
 // Codex P2: once a kind is set, the empty choice cannot hide it while it is still stored.
 assert.equal(await page.locator('#annotation-simple-type-select option[value=""]').isDisabled(),true);
 await page.locator('#annotation-simple-type-select').evaluate(select=>{select.value='';select.dispatchEvent(new Event('change'));});
 assert.equal(await page.locator('#annotation-simple-type-select').inputValue(),'explanation','the control shows the stored kind');
 for(let i=0;i<60 && (await current()).object_type!=='explanation';i++) await page.waitForTimeout(250);
 entry=await current();
 assert.equal(entry.object_type,'explanation');assert.equal(entry.ranges[0].quote,core);
 assert.equal(await page.locator('#annotation-help-belongs').isVisible(),true,'the explanation stays open while working');
 // Codex P2: parts of the old kind are not stored with the new kind, where they would be built unseen.
 assert.equal(entry.field_evidence.defined_term.span,null);assert.equal(entry.field_evidence.definiens_span.span,null);
 // Switching back restores Metis' proposal for that kind (besluit William 2026-11-14), without a question.
 await page.locator('#annotation-simple-type-select').selectOption('definition');
 for(let i=0;i<60 && (await current()).object_type!=='definition';i++) await page.waitForTimeout(250);
 entry=await current();
 assert.equal(entry.object_type,'definition');
 assert.equal(entry.field_evidence.defined_term.span.start,0);assert.equal(entry.field_evidence.definiens_span.span.start,16);
 await page.screenshot({path:output+'/meaning-kind-corrected.png',fullPage:true});
 // 2. A selection made while Metis reads waits; the answer for the old statement never overwrites it.
 await page.keyboard.press('Escape');
 await page.locator('#annotation-ready:enabled').click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 const twice=page.locator('[data-source-block]').filter({hasText:'De huid is droog'});
 await tasks.selectText(page,twice,'De huid is droog en de huid is rood.');
 const started=page.waitForRequest(r=>r.url().endsWith('/annotations/suggest'));
 await plus('belongs').click();await started;
 const other=page.locator('[data-source-block]').filter({hasText:'Een zorgplan is'});
 await tasks.selectText(page,other,'Een zorgplan is een overzicht van afspraken.');
 await row('belongs').getByText('Een zorgplan is een overzicht van afspraken.',{exact:true}).waitFor();
 await reading();
 entry=await current();
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote]),[['core','De huid is droog en de huid is rood.'],['context','Een zorgplan is een overzicht van afspraken.']]);
 // An ambiguous literal is not asked: it stays open for the reviewer as a signal.
 assert.deepEqual(entry.field_evidence.predicate_span,{span:null,missing_reason:'uncertain'});
 assert.equal(await page.locator('#annotation-steps').isVisible(),false);
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:output+'/meaning-corrected-mobile.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1100});
 await page.locator('#annotation-ready:enabled').click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 // 3. Provider failure keeps the saved statement and asks only the type.
 const failure=page.locator('[data-source-block]').filter({hasText:'Foutvoorbeeld'});
 await tasks.selectText(page,failure,'Foutvoorbeeld voor handmatig herstel.');
 await page.locator('#annotation-ready:enabled').click();
 await page.locator('#annotation-simple-type').waitFor();
 entry=await current();
 assert.equal(entry.status,'draft');assert.equal(entry.ranges[0].quote,'Foutvoorbeeld voor handmatig herstel.');
 await page.screenshot({path:output+'/meaning-question.png',fullPage:true});
 // 4. Besluit William 2026-11-14: switching away and back restores Metis' proposal, also direction.
 await page.goto(base+'/annotations?'+new URLSearchParams({document:sid}));
 await page.locator('#annotation-editor-inputs:enabled').waitFor();
 const advice=page.locator('[data-source-block]').filter({hasText:'Controleer de huid'});
 await tasks.selectText(page,advice,'Controleer de huid dagelijks.');
 await plus('belongs').click();
 await page.locator('#annotation-simple-type-select:enabled').waitFor();
 const kindIs=async kind=>{for(let i=0;i<60 && (await current())?.object_type!==kind;i++) await page.waitForTimeout(250);return current();};
 entry=await kindIs('recommendation');
 assert.equal(entry.recommendation_semantics.direction,'for');
 await page.locator('#annotation-simple-type-select:enabled').selectOption('explanation');
 entry=await kindIs('explanation');assert.equal(entry.recommendation_semantics,null);
 await page.locator('#annotation-simple-type-select:enabled').selectOption('recommendation');
 entry=await kindIs('recommendation');
 assert.equal(entry.recommendation_semantics?.direction,'for','switching back restores the proposed direction');
 // Codex P2: the memory belongs to that exact statement. Change the statement, and switching back to a kind
 // remembered for the old one restores nothing of it.
 await page.locator('#annotation-simple-type-select:enabled').selectOption('explanation');
 entry=await kindIs('explanation');
 await plus('core').click();
 await tasks.selectText(page,page.locator('[data-source-block]').filter({hasText:'Doe dit elke ochtend.'}),'Doe dit elke ochtend.');
 await row('core').getByText('Doe dit elke ochtend.',{exact:true}).waitFor();
 for(let i=0;i<60 && (await current())?.ranges.filter(a=>a.role==='core').length!==2;i++) await page.waitForTimeout(250);
 await reading();await page.locator('#annotation-simple-type-select:enabled').waitFor();
 entry=await current();
 assert.equal(entry.ranges.filter(a=>a.role==='core').length,2,'the statement changed');
 assert.notEqual(entry.object_type,'recommendation');
 await page.locator('#annotation-simple-type-select:enabled').selectOption('recommendation');
 entry=await kindIs('recommendation');
 assert.equal(entry.object_type,'recommendation');
 assert.notEqual(entry.recommendation_semantics?.direction,'for','nothing of the old statement comes back');
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/suggestions-result.json',JSON.stringify({backgroundProposal:true,selectionDuringReadWaits:true,ambiguityIsASignal:true,failureAsksOnlyType:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

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
 await page.locator('[name=file]').setInputFiles({name:'meaning.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Begrip</h1><p>'+core+'</p><p>Een zorgplan is een overzicht van afspraken.</p><p>Foutvoorbeeld voor handmatig herstel.</p><p>De huid is droog en de huid is rood.</p></body></html>')});
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
 assert.equal(await page.locator('#annotation-simple-type').isVisible(),false);
 let entry=await current();
 assert.equal(entry.object_type,'definition');assert.equal(entry.ranges[0].quote,core);
 assert.equal(entry.field_evidence.defined_term.span.start,0);assert.equal(entry.field_evidence.defined_term.span.end,12);
 assert.equal(entry.field_evidence.definiens_span.span.start,16);
 await page.screenshot({path:output+'/meaning-proposed.png',fullPage:true});
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
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/suggestions-result.json',JSON.stringify({backgroundProposal:true,selectionDuringReadWaits:true,ambiguityIsASignal:true,failureAsksOnlyType:true,errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

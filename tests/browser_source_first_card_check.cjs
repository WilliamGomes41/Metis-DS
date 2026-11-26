const {withBrowserEvidence}=require('./browser_evidence.cjs');
const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const tasks=require('./browser_annotation_tasks.cjs');
// #1060 slice 2: the worker marks the statement, the text that belongs to it and the evidence.
(async()=>{
 const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
 await withBrowserEvidence(chromium, {base, output, label:'source-first-card',
   launchOptions:{executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true}}, async ({newContext})=>{
 const manifest=await(await fetch(base+'/browser-manifest')).json();
 const context=await newContext({viewport:{width:1440,height:1000}},true),page=await context.newPage(),errors=[];
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
 await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();
  await page.getByRole('button',{name:'Bevestig en ga annoteren',exact:true}).click();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 const block=text=>page.locator('[data-source-block]').filter({hasText:text.slice(0,25)});
 const read=()=>page.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
 const current=async()=>(await read()).entries.find(e=>e.annotation_id===new URL(page.url()).searchParams.get('annotation'));
 const row=key=>page.locator('#annotation-simple-rows dd[data-row='+key+']');
 const buttons=()=>page.locator('#annotation-controls button:visible').count();
 // Empty card: one instruction, no steps, no form, no competing actions.
 assert.equal(await page.locator('#annotation-steps').isVisible(),false);
 assert.equal(await page.locator('#annotation-simple-heading').innerText(),'Selecteer de uitspraak in de bron');
 // #1060 slice 5: the step form is gone, not hidden.
 assert.equal(await page.locator('#annotation-steps, #annotation-fields, #annotation-type, #annotation-suggest, #annotation-entry, #annotation-more, #annotation-task-1, #annotation-task-2, #annotation-task-3').count(),0);
 // This fixture returns no initial offer. Wait for the request to settle before counting the actions.
 await page.locator('#annotation-offer-message').getByText('Geen voorstel gevonden.',{exact:false}).waitFor();
 // Only one action exists before anything is selected: there is nothing to save yet.
 assert.deepEqual(await page.locator('#annotation-controls button:visible').allInnerTexts(),['Ik ben klaar met dit document']);
 const minus=(key,text)=>row(key).locator('.annotation-line').filter({hasText:text}).locator('button.annotation-sign');
 // 1. Selecting is the statement: the text appears, nothing to confirm or fill in.
 await tasks.selectText(page,block(item),item.slice(0,40));
 await row('core').getByText(item.slice(0,40),{exact:true}).waitFor();
 // A new selection simply replaces it while nothing else has been done.
 await tasks.selectText(page,block(item),item);
 await row('core').getByText(item,{exact:true}).waitFor();
 assert.equal(await row('core').locator('.annotation-line').count(),1);
 assert.equal(await page.locator('#annotation-simple-heading').isVisible(),false);
 // Besluit William 2026-11-15: one way to add. The menu sits next to the selection, not in the card; without a
 // statement it offers only the statement. The card has no '+' to add with.
 const menu=page.locator('#annotation-selection-menu');
 assert.deepEqual(await menu.locator('button:visible').allInnerTexts(),['Uitspraak']);
 assert.equal(await page.locator('#annotation-controls #annotation-selection-menu').count(),0);
 assert.equal(await page.locator('#annotation-simple-rows dt .annotation-sign').count(),0);
 const near=await page.evaluate(()=>{const m=document.getElementById('annotation-selection-menu').getBoundingClientRect(),r=getSelection().getRangeAt(0).getClientRects();const last=[...r].at(-1);
  return {gap:Math.round(m.top-last.bottom),inside:m.left>=document.querySelector('.annotation-document').getBoundingClientRect().left};});
 assert(near.gap>=0 && near.gap<=16 && near.inside,JSON.stringify(near));
 await page.screenshot({path:output+'/card-selection-menu.png',fullPage:true});
 // On a phone the menu stays inside the document, below the selection, and the page does not scroll sideways.
 await page.setViewportSize({width:390,height:844});
 await tasks.selectText(page,block(item),item.slice(0,40));await tasks.selectText(page,block(item),item);
 await menu.waitFor();
 const phone=await page.evaluate(()=>{const m=document.getElementById('annotation-selection-menu').getBoundingClientRect(),d=document.querySelector('.annotation-document').getBoundingClientRect();
  return {fits:m.left>=d.left && m.right<=d.right,page:document.documentElement.scrollWidth<=innerWidth};});
 assert(phone.fits && phone.page,JSON.stringify(phone));
 await menu.scrollIntoViewIfNeeded();await page.screenshot({path:output+'/card-selection-menu-mobile.png'});
 await page.setViewportSize({width:1440,height:1000});
 await row('core').getByText(item,{exact:true}).waitFor();
 // Keyboard: Tab from the source passage reaches the menu; Escape closes it and returns to the passage.
 await block(item).focus();await page.keyboard.press('Tab');
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.add),'core');
 await page.keyboard.press('Escape');
 await menu.waitFor({state:'hidden'});
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.sourceBlock!==undefined),true);
 // The selection itself stays the statement.
 await row('core').getByText(item,{exact:true}).waitFor();
 // 2. Slice 4: Metis points at the introduction the item leans on. The proposal is the exact
 // source text, marked apart in the source, and is answered with '+' or '−'.
 const proposal=row('context').locator('.annotation-proposal');
 await proposal.getByText(intro,{exact:true}).waitFor();
 assert.equal(await proposal.locator('.annotation-proposal-label').innerText(),'Voorstel van Metis');
 assert.equal(await block(intro).locator('mark[data-proposal]').innerText(),intro);
 // Before the statement is stored there is no kind to show yet.
 assert.equal(await page.locator('#annotation-simple-type-select').count(),0);
 await page.screenshot({path:output+'/card-statement.png',fullPage:true});
 // The proposal's '+' and '−' stay in the one column of signs, and its text lines up with the other texts.
 const edges=await page.evaluate(()=>({signs:[...document.querySelectorAll('#annotation-simple-rows .annotation-line .annotation-sign:last-child')].map(b=>Math.round(b.getBoundingClientRect().right)),
  texts:[...document.querySelectorAll('#annotation-simple-rows .annotation-line p')].map(p=>Math.round(p.getBoundingClientRect().left))}));
 assert.equal(new Set(edges.signs).size,1,JSON.stringify(edges));assert.equal(new Set(edges.texts).size,1,JSON.stringify(edges));
 await proposal.locator('[data-proposal=add]').click();
 await row('context').locator('.annotation-line:not(.annotation-proposal)').getByText(intro,{exact:true}).waitFor();
 assert.equal(await proposal.count(),0);
 await page.waitForFunction(()=>!document.querySelector('[data-source-block] mark[data-proposal]'));
 // #1123: in the source each passage of this object shows its role, with the same mark as its row in the card.
 const mark=text=>block(text).locator('mark[data-current]');
 const roleOf=async text=>[await mark(text).getAttribute('data-role'),await mark(text).getAttribute('title')];
 const look=(role,rowRole=role)=>page.evaluate(({role,rowRole})=>{
  const m=getComputedStyle(document.querySelector('[data-source-block] mark[data-current][data-role='+role+']'));
  const s=getComputedStyle(document.querySelector('#annotation-simple-rows dt[data-row='+rowRole+'] .annotation-row-name'),'::before');
  return {fill:m.backgroundColor,line:m.textDecorationLine+' '+m.textDecorationStyle,
   swatchFill:s.backgroundColor,swatchLine:s.borderBottomStyle,shown:s.display!=='none' && s.content!=='none'};},{role,rowRole});
 assert.deepEqual(await roleOf(item),['core','Uitspraak']);
 assert.deepEqual(await roleOf(intro),['belongs','Aanvullende context']);
 const coreLook=await look('core'),belongsLook=await look('belongs','context');
 assert.notDeepEqual([coreLook.fill,coreLook.line],[belongsLook.fill,belongsLook.line]);
 // The row name in the card carries the same mark, so the source needs no separate legend.
 for(const l of [coreLook,belongsLook]) {assert(l.shown,JSON.stringify(l));assert.equal(l.swatchFill,l.fill);}
 // The core and population can overlap. The mobile submenu offers the same actions with a keyboard.
 await page.setViewportSize({width:390,height:844});
 const population='diabetes mellitus';
 await tasks.selectText(page,block(item),population);
 await block(item).focus();await page.keyboard.press('Tab');await page.keyboard.press('ArrowRight');
 assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Toepassing');
 await page.keyboard.press('Enter');
 const application=menu.getByRole('group',{name:'Toepassing'});
 await application.waitFor();
 assert.deepEqual(await application.locator('button').allInnerTexts(),
  ['Voor wie?','In welke situatie?','Onder welke voorwaarde?']);
 assert.equal(await page.evaluate(()=>document.activeElement.dataset.add),'population');
 assert(await page.evaluate(()=>{
  const menu=document.querySelector('#annotation-selection-menu').getBoundingClientRect();
  const source=document.querySelector('.annotation-document').getBoundingClientRect();
  return menu.left>=source.left && menu.right<=source.right && document.documentElement.scrollWidth<=innerWidth;
 }));
 await menu.scrollIntoViewIfNeeded();
 await page.screenshot({path:output+'/card-application-menu-mobile.png'});
 await page.keyboard.press('Escape');
 assert.equal(await application.isVisible(),false);
 await page.keyboard.press('Enter');await page.keyboard.press('Enter');
 await row('population').getByText(population,{exact:true}).waitFor();
 await page.getByRole('button',{name:'Uitleg bij Voor wie?',exact:true}).click();
 await page.locator('#annotation-help-population').getByText('Dit mag een deel van de uitspraak zijn.',{exact:false}).waitFor();
 for(const role of ['scope','condition','exception']) {
  await tasks.addAs(page,block(support),support,role);
  await row(role).getByText(support,{exact:true}).waitFor();
 }
 await page.waitForFunction(async ({sid,population,support})=>{
  const data=await (await fetch('/annotations/api?document='+sid)).json();
  const ranges=data.entries.find(entry=>entry.annotation_id===new URL(location.href).searchParams.get('annotation'))?.ranges;
  return ranges?.some(a=>a.role==='population' && a.quote===population) &&
         ['scope','condition','exception'].every(role=>ranges.some(a=>a.role===role && a.quote===support));
 },{sid,population,support});
 await page.reload();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 await row('population').getByText(population,{exact:true}).waitFor();
 for(const [role,text] of [['population',population],...['scope','condition','exception'].map(role=>[role,support])]) {
  await minus(role,text).click();
  await row(role).getByText(text,{exact:true}).waitFor({state:'detached'});
 }
 // One literal in two application roles: removing one role clears that role's field only.
 const fieldsOf=async()=>page.evaluate(async sid=>{
  const data=await (await fetch('/annotations/api?document='+sid)).json();
  return data.entries.find(entry=>entry.annotation_id===new URL(location.href).searchParams.get('annotation'))?.field_evidence;
 },sid);
 for(const role of ['population','scope']) {
  await tasks.addAs(page,block(support),support,role);
  await row(role).getByText(support,{exact:true}).waitFor();
 }
 await page.waitForFunction(async sid=>{
  const data=await (await fetch('/annotations/api?document='+sid)).json();
  const fields=data.entries.find(entry=>entry.annotation_id===new URL(location.href).searchParams.get('annotation'))?.field_evidence;
  return fields?.target_group_span?.span && fields?.scope_span?.span;
 },sid);
 await minus('population',support).click();
 await row('population').getByText(support,{exact:true}).waitFor({state:'detached'});
 await page.waitForFunction(async sid=>{
  const data=await (await fetch('/annotations/api?document='+sid)).json();
  const entry=data.entries.find(entry=>entry.annotation_id===new URL(location.href).searchParams.get('annotation'));
  return !entry?.ranges.some(a=>a.role==='population');
 },sid);
 let fields=await fieldsOf();
 assert.equal(fields.target_group_span.span,null,JSON.stringify(fields.target_group_span));
 assert(fields.scope_span.span,JSON.stringify(fields.scope_span));
 await minus('scope',support).click();
 await row('scope').getByText(support,{exact:true}).waitFor({state:'detached'});
 await page.setViewportSize({width:1440,height:1000});
 // 3. Evidence is added when the source has it; the card asks no choice. One button finishes.
 assert.equal(await row('evidence').getByRole('button',{name:/Staat niet in de bron|niet van toepassing/}).count(),0);
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await page.locator('.annotation-task-actions .btn-primary:visible').count(),1);
 assert.equal(await page.getByRole('button',{name:'Ik ben klaar met dit document',exact:true}).count(),1);
 await page.screenshot({path:output+'/card-complete.png',fullPage:true});
 // "−" (and a proposal's "+") share one column beside each text.
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
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote,'required_for_meaning' in a]),[['core',item,false],['list_introduction',intro,false]]);
 assert.deepEqual(entry.field_evidence.supported_object,{span:null,missing_reason:'not_stated'});
 assert.equal('required_links' in entry,false);
 // A failed check leaves a visible retry in the card instead of two dead buttons.
 await block(item).locator('mark[data-annotation]').first().click();
 await row('context').getByText(intro,{exact:true}).waitFor();
 await page.route('**/annotations/check**',route=>route.abort());
 await minus('context',intro).click();
 await page.locator('#annotation-simple-recheck').waitFor();
 assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
 await page.unroute('**/annotations/check**');
 await page.locator('#annotation-simple-recheck').click();
 // '−' on the linked introduction answered the proposal: it does not come back.
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await row('context').locator('.annotation-proposal').count(),0);
 await page.locator('#annotation-ready').click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 entry=(await read()).entries.find(e=>e.annotation_id===first);
 assert.equal(entry.status,'ready');assert.deepEqual(entry.ranges.map(a=>a.role),['core']);
 assert.deepEqual(entry.declined_context.map(r=>r.quote),[intro]);
 // A statement on its own is a complete object. The rule also proposes the list introduction here
 // (the known limit of slice 4): saving points at the proposal instead of passing it by.
 await tasks.selectText(page,block(alone),alone);
 await row('core').getByText(alone,{exact:true}).waitFor();
 await row('context').locator('.annotation-proposal').getByText(intro,{exact:true}).waitFor();
 await page.locator('#annotation-ready:enabled').click();
 await row('context').getByText('Beantwoord eerst het voorstel',{exact:false}).waitFor();
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.proposal),'add');
 assert.equal((await current()).status,'draft');
 await page.screenshot({path:output+'/card-proposal-open.png',fullPage:true});
 // The worker adds text alongside Metis: 'Aanvullende context' in the menu adds any number of passages, '−' removes one.
 // Neither answers the proposal.
 for(const text of [support,item]) {await tasks.addAs(page,block(text),text,'context');
  await row('context').locator('.annotation-line:not(.annotation-proposal)').getByText(text,{exact:true}).waitFor();}
 await minus('context',item).click();
 await page.waitForFunction(item=>![...document.querySelectorAll('#annotation-simple-rows dd[data-row=context] .annotation-line:not(.annotation-proposal) p')].some(p=>p.textContent===item),item);
 await row('context').locator('.annotation-proposal').getByText(intro,{exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.setViewportSize({width:1440,height:1000});
 await row('context').locator('[data-proposal=decline]').click();
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await row('context').locator('.annotation-proposal').count(),0);
 await page.locator('#annotation-ready').click();
 await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
 entry=(await read()).entries.find(e=>e.ranges.some(a=>a.quote===alone));
 assert.equal(entry.status,'ready');assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote]),[['core',alone],['context',support]]);
 assert.deepEqual(entry.declined_context.map(r=>r.quote),[intro]);
 // Metis unavailable: the only question is the type. Evidence is added with the menu and removed with '−'.
 await tasks.addAs(page,block(failing),failing.slice(0,13),'core');
 await page.locator('#annotation-simple-type').waitFor();
 await page.locator('#annotation-simple-type-select').selectOption('explanation');
 await page.waitForFunction(()=>document.getElementById('annotation-simple-type-select')?.value==='explanation');
 // Keyboard: Tab to the menu, arrows to Onderbouwing, Enter. Focus returns to the passage, not the page top.
 await tasks.selectText(page,block(support),support);
 await block(support).focus();await page.keyboard.press('Tab');
 await page.keyboard.press('ArrowLeft');
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.add),'evidence');
 await page.keyboard.press('Enter');
 await row('evidence').getByText(support,{exact:true}).waitFor();
 await page.waitForFunction(()=>document.getElementById('annotation-selection-menu').hidden);
 // #1123: the evidence has its own mark, apart from the statement and from what belongs to it.
 await page.waitForFunction(()=>document.querySelector('[data-source-block] mark[data-current][data-role=evidence]'));
 assert.deepEqual(await roleOf(support),['evidence','Onderbouwing']);
 const evidenceLook=await look('evidence');
 assert(evidenceLook.shown,JSON.stringify(evidenceLook));
 for(const l of [coreLook,belongsLook]) assert.notDeepEqual([evidenceLook.fill,evidenceLook.line],[l.fill,l.line]);
 assert.equal(evidenceLook.swatchFill,evidenceLook.fill);assert.notEqual(evidenceLook.swatchLine,'none');
 // Passages of other objects keep their own mark: only the open object is shown per role.
 assert.equal(await page.locator('[data-source-block] mark[data-annotation][data-role]').count(),0);
 assert(await page.locator('[data-source-block] mark[data-annotation]').count()>0);
 await page.screenshot({path:output+'/card-role-marks.png',fullPage:true});
 assert.equal(await page.evaluate(()=>document.activeElement?.closest?.('[data-source-block]')?.textContent),support);
 // Codex P2: with a statement, Escape cancels the selection, so no hidden pending selection blocks finishing.
 // Start from a settled, checked card: nothing in flight that could hide a missing recheck.
 await page.locator('#annotation-ready:enabled').waitFor();
 await page.waitForFunction(()=>!/Controleren|niet opgeslagen|Opslaan…/.test(document.getElementById('annotation-simple-status').textContent+document.getElementById('annotation-status').textContent));
 await page.waitForTimeout(1000);
 await tasks.selectText(page,block(failing),failing.slice(14));
 await block(failing).focus();await page.keyboard.press('Tab');await page.keyboard.press('Escape');
 await page.waitForFunction(()=>document.getElementById('annotation-selection-menu').hidden);
 for(let i=0;i<60 && (await current())?.pending_range;i++) await page.waitForTimeout(250);
 assert.equal((await current()).pending_range,null);
 assert.equal(await page.evaluate(()=>getSelection().toString()),'');
 // Codex P2: cancelling checks again at once, like '−', so finishing is offered without a manual recheck.
 await page.waitForTimeout(1500);
 await page.locator('#annotation-ready:enabled').waitFor({timeout:5000});
 assert.equal(await page.locator('#annotation-simple-recheck').count(),0);
 // A statement in two pieces: 'Uitspraak' in the menu adds the next piece.
 await tasks.selectText(page,block(failing),failing.slice(14));
 assert.deepEqual(await page.locator('#annotation-selection-menu button:visible').allInnerTexts(),['Uitspraak','Toepassing','Uitzondering','Aanvullende context','Onderbouwing']);
 await tasks.choose(page,'core');
 await row('core').getByText(failing.slice(14),{exact:true}).waitFor();
 await page.locator('#annotation-ready:enabled').waitFor();
 assert.equal(await page.locator('#annotation-simple-type-select').inputValue(),'explanation');  // the chosen type is kept
 entry=await current();
 assert.equal(entry.status,'draft');assert.equal(entry.object_type,'explanation');
 assert.deepEqual(entry.ranges.map(a=>[a.role,a.quote,a.evidence_function]),
  [['core',failing.slice(0,13),null],['evidence',support,'supported_by'],['core',failing.slice(14),null]]);
 // '−' removes without asking for a reason; the object can still be saved without evidence.
 await minus('evidence',support).click();
 await row('evidence').getByText(/Niets gekoppeld/).waitFor();
 await page.locator('#annotation-ready:enabled').waitFor();
 entry=await current();
 assert.deepEqual(entry.ranges.map(a=>a.role),['core','core']);assert.equal('required_links' in entry,false);
 assert.equal(await page.locator('#annotation-required-links').count(),0);
 // Codex P2: a selection saved as pending comes back after a reload with its menu, so it can still be placed.
 await tasks.selectText(page,block(support),support);
 for(let i=0;i<60 && (await current())?.pending_range?.quote!==support;i++) await page.waitForTimeout(250);
 assert.equal((await current()).pending_range.quote,support);
 await page.reload();await page.locator('#annotation-editor-inputs:enabled').waitFor();
 assert.deepEqual(await page.locator('#annotation-selection-menu button:visible').allInnerTexts(),['Uitspraak','Toepassing','Uitzondering','Aanvullende context','Onderbouwing']);
 await tasks.choose(page,'evidence');
 await row('evidence').getByText(support,{exact:true}).waitFor();
 for(let i=0;i<60 && (await current())?.pending_range;i++) await page.waitForTimeout(250);
 assert.equal((await current()).pending_range,null);
 await minus('evidence',support).click();
 await row('evidence').getByText(/Niets gekoppeld/).waitFor();
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
 await page.getByRole('button',{name:'Ik ben klaar met dit document',exact:true}).click();
 await page.getByRole('heading',{name:'Documentcontrole',exact:true}).waitFor();
 assert.equal(await page.locator('form[action="/annotations/source-role"]').count(),0);
 await page.locator('[data-source-block]').filter({hasText:/^Smetten$/}).waitFor();
 await page.screenshot({path:output+'/document-check-gaps.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.setViewportSize({width:1440,height:1000});
 // The card no longer offers that route: a selection is the statement.
 await page.locator('#annotation-editor-inputs:enabled').waitFor();
 await tasks.selectText(page,block(support),support);
 await row('core').getByText(support,{exact:true}).waitFor();
 assert.equal(await page.locator('#annotation-simple').getByText(/geen uitspraak/i).count(),0);
 assert.equal(await page.locator('#annotation-steps').isVisible(),false);
 assert.equal(await page.evaluate(()=>localStorage.getItem('metis-annotation-form')),null);
 assert.deepEqual(errors,[]);
 fs.writeFileSync(output+'/source-first-card-result.json',JSON.stringify({threeRows:true,derivedInBackground:true,typeQuestionOnlyOnFailure:true,errors}));
 });
})().catch(e=>{console.error(e);process.exit(1)});

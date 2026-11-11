const tasks=require('./browser_annotation_tasks.cjs');
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const output = process.env.METIS_BROWSER_OUTPUT;
  fs.mkdirSync(output,{recursive:true});
  const m = await (await fetch(base+'/browser-manifest')).json();
  const browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  let page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  async function login(p) {
    await p.goto(base+'/login');
    await p.locator('[name=username]').fill(m.username);
    await p.locator('[name=password]').fill(m.password);
    await Promise.all([p.waitForURL(u => u.pathname!='/login'),p.locator('button[type=submit]').click()]);
    if (m.document) await p.goto(base+'/annotations?document='+m.document);
  }
  await login(page);
  const processingRequests = [];
  page.on('request', r => {if (r.url().includes('/source-selection/start')) processingRequests.push(r.url());});
  await page.goto(base+'/ingest');
  await page.locator('[name=file]').setInputFiles({name:'annotation.html',mimeType:'text/html',buffer:Buffer.from(
    '<html><body><h1>Advies</h1><p>Controleer 👩🏽‍⚕️ de huid bij café.</p><p>Alleen bij klachten.</p><p>Gelijke tekst. Gelijke tekst.</p><p>Herhaalde paragraaf.</p><p>Herhaalde paragraaf.</p><p>Onderzoek beschrijft de bevinding.</p></body></html>')});
  await page.locator('[name=title]').fill('Annotatieproef');
  await page.locator('[name=version]').fill('1.0');
  await page.locator('[name=date]').fill('2026-11-09');
  await page.locator('[name=class_]').selectOption('richtlijn');
  await page.locator('[name=family]').fill('test');
  await page.locator('[name=review_option][value=uploader_sole]').check();
  await Promise.all([page.waitForURL(u => u.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
  m.document = new URL(page.url()).searchParams.get('document');
  assert.ok(m.document);
  await page.reload();
  assert.match(await page.getByRole('status').innerText(),/Document veilig ontvangen/);
  assert.equal(await page.locator('form[action="/source-selection/start"]').count(),0);
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth<=window.innerWidth));
    await page.screenshot({path:`${output}/annotation-entry-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();
  await page.locator('[data-source-block]').first().waitFor();
  assert.equal(await page.locator('.annotation-document').count(),1);
  assert.equal(await page.locator('#annotation-source-input,.annotation-selection-help').count(),0);
  assert.equal(await page.locator('#annotation-select-block').count(),1);
  assert.equal(await page.locator('.annotation-document-heading').first().innerText(),'Advies');
  const block = page.locator('[data-source-block]').filter({hasText:'Controleer'});
  const points = await block.evaluate(p => {
    const node=p.firstChild, end=node.textContent.indexOf(' de huid');
    const r=document.createRange();r.setStart(node,0);r.setEnd(node,1);const a=r.getBoundingClientRect();
    r.setStart(node,end-1);r.setEnd(node,end);const b=r.getBoundingClientRect();
    return {x1:a.left+1,y1:a.top+a.height/2,x2:b.right,y2:b.top+b.height/2};
  });
  await page.mouse.move(points.x1,points.y1);await page.mouse.down();await page.mouse.move(points.x2,points.y2,{steps:20});await page.mouse.up();
  assert.match(await page.locator('#annotation-selection').innerText(),/Controleer 👩🏽‍⚕️/);
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-type').selectOption('recommendation');
  // Point at meaning rather than typing it. Only fields for this type appear.
  await tasks.step(page,2);
  assert.equal(await page.locator('#annotation-field option[value=defined_term]').count(),0);
  await tasks.field(page,'recommended_action');
  await tasks.selectText(page,block,'Controleer');
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-recommendation summary').click();
  await page.locator('#annotation-direction').selectOption('for');
  await tasks.selectText(page,block,'Controleer');
  await page.locator('#annotation-direction-evidence').click();await page.locator('#annotation-add').click();
  await page.locator('#annotation-strength-status').selectOption('not_stated');
  assert.equal(await page.locator('#annotation-direction-proof').innerText(),'Controleer');
  await tasks.role(page,'condition');
  await page.locator('#annotation-essential').check();
  await page.locator('[data-source-block]').filter({hasText:'Alleen bij klachten.'}).click();
  await page.locator('#annotation-select-block').click();
  await page.locator('#annotation-add').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  let saved = await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(),m.document);
  assert.equal(saved.entries.length,1);
  assert.equal(saved.entries[0].ranges[0].quote,'Controleer 👩🏽‍⚕️');
  assert.equal(saved.entries[0].ranges[1].required_for_meaning,true);
  assert.equal(saved.entries[0].ranges[1].quote,'Alleen bij klachten.');
  assert.equal(await page.locator('[data-source-block] mark[data-current]').count(),2);
  assert.deepEqual(saved.entries[0].field_evidence.recommended_action.span,{block_id:saved.entries[0].ranges[0].block_id,start:0,end:10});
  assert.ok(saved.entries[0].ranges[1].relationship_id.startsWith('link-v1:'));
  assert.equal(saved.entries[0].recommendation_semantics.direction,'for');
  assert.equal(saved.entries[0].recommendation_semantics.strength_status,'not_stated');
  // Network failure cannot yield a false saved label or navigation on Pause.
  await page.route('**/annotations/api',route => route.abort());
  await page.locator('#annotation-na').check();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent.startsWith('Opslaan mislukt.'));
  (await tasks.more(page),await page.locator('#annotation-pause').click());
  assert.equal(new URL(page.url()).pathname,'/annotations');
  await page.unroute('**/annotations/api');
  await page.locator('#annotation-retry').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  // Pause waits for the actual commit response, then a new login resumes it.
  await page.route('**/annotations/api',async route => { await new Promise(r => setTimeout(r,400));await route.continue(); });
  await tasks.type(page,'definition');
  await tasks.more(page);
  await Promise.all([page.waitForURL(u => u.pathname==='/'),page.locator('#annotation-pause').click()]);
  await context.close();
  const fresh = await browser.newContext({viewport:{width:1440,height:1000}});page = await fresh.newPage();
  await login(page);
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  assert.equal(await page.locator('#annotation-type').inputValue(),'definition');
  assert.equal(await page.locator('#annotation-ranges li').count(),2);
  const resumed=await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(),m.document);
  assert.deepEqual(resumed.entries[0].field_evidence.recommended_action,saved.entries[0].field_evidence.recommended_action);
  // The old direct ready API accepted semantically incomplete input; the guided
  // client now checks it. Keep the early Unicode/field proof, then complete a
  // literal explanation for the remaining ready/recovery scenarios.
  await tasks.type(page,'explanation');await tasks.linked(page);
  await page.locator('#annotation-ranges li').first().getByRole('button',{name:'Deze bronkoppeling verwijderen'}).click();await tasks.confirm(page);
  await tasks.step(page,1);
  await page.locator('[data-source-block]').filter({hasText:'Onderzoek beschrijft de bevinding.'}).click();
  await page.locator('#annotation-select-block').click();await page.locator('#annotation-add').click();
  for(const [field,text] of [['subject_span','Onderzoek'],['predicate_span','beschrijft'],['supported_object','de bevinding']]) {
    await tasks.field(page,field);
    await tasks.selectText(page,page.locator('[data-source-block]').filter({hasText:'Onderzoek beschrijft de bevinding.'}),text);
    await page.locator('#annotation-add').click();
  }
  // Removing essential context leaves a durable duty; ready cannot conceal it.
  await tasks.step(page,2);await tasks.linked(page);
  await page.locator('#annotation-ranges li').filter({hasText:'Voorwaarde (essentieel)'}).getByRole('button',{name:'Deze bronkoppeling verwijderen'}).click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await tasks.step(page,3);
  await page.locator('#annotation-check').getByRole('button').filter({hasText:'essentieel verband ontbreekt'}).waitFor();
  assert.equal(await page.locator('#annotation-ready').isDisabled(),true);
  await page.reload();
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  assert.match(await page.locator('#annotation-required-links').innerText(),/Essentieel verband ontbreekt/);
  await tasks.step(page,2);await page.getByRole('button',{name:'Dit verband opnieuw aanwijzen'}).click();
  await page.locator('[data-source-block]').filter({hasText:'Alleen bij klachten.'}).click();
  await page.locator('#annotation-select-block').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.reload();
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  const pendingRepair=await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(),m.document);
  assert.equal(pendingRepair.entries[0].pending_range.relationship_id,pendingRepair.entries[0].required_links[0].relationship_id);
  assert.equal(await page.locator('#annotation-role').isDisabled(),true);
  // Leaving repair mode must not secretly bind the pending condition as a core.
  await tasks.step(page,1);await tasks.step(page,2);
  assert.equal(await page.locator('#annotation-add').isDisabled(),true);
  await page.getByRole('button',{name:'Dit verband opnieuw aanwijzen'}).click();
  assert.equal(await page.locator('#annotation-role').inputValue(),'condition');
  await page.locator('#annotation-add').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await tasks.ready(page);
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
  await tasks.more(page);await page.locator('#annotation-overview').click();
  await page.waitForURL(u => u.searchParams.get('overview')==='true');
  assert.match(await page.locator('body').innerText(),/Voorwaarde.*essentieel/s);
  assert.equal(await page.getByRole('link',{name:'Deze annotatie aanpassen'}).count(),1);
  await page.getByRole('link',{name:'Deze annotatie aanpassen'}).click();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth>innerWidth),false);
    if(width===390) {
      await tasks.step(page,2);
      const sourceSection=page.locator('[data-source-block]').filter({hasText:'Alleen bij klachten.'});
      await sourceSection.click();
      await page.locator('#annotation-select-block').click();
      // Navigation stays in document flow so it cannot obscure annotation controls.
      for(const id of ['annotation-to-controls','annotation-to-source']) {
        await page.locator('#'+id).scrollIntoViewIfNeeded();
        assert.equal(await page.locator('#'+id).evaluate(a => {
          const r=a.getBoundingClientRect();
          const top=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
          return r.top>=0 && r.bottom<=innerHeight && (top===a || a.contains(top));
        }),true,'Mobile navigation must be visible and uncovered: '+id);
      }
      await page.screenshot({path:`${output}/annotation-390-selected.png`});
      await page.locator('#annotation-to-controls').click();
      assert.equal(await page.evaluate(() => document.activeElement.id),'annotation-controls');
      await page.locator('#annotation-to-source').click();
      assert.equal(await page.evaluate(() => document.activeElement.id),await sourceSection.getAttribute('id'));
      await page.locator('#annotation-to-controls').click();
      await page.locator('#annotation-discard').click();
      await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
    }
    await page.evaluate(() => {window.scrollTo(0,0);document.getElementById('annotation-controls').scrollTop=0;});
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.screenshot({path:`${output}/annotation-${width}.png`,fullPage:true});
  }
  await tasks.step(page,2);
  // Keyboard/touch alternative retains the same source-reference contract.
  await page.locator('[data-source-block]').filter({hasText:'Gelijke tekst.'}).first().click();
  await page.locator('[data-source-block]').filter({hasText:'Gelijke tekst.'}).first().focus();
  await page.keyboard.press('Control+Home');
  await page.keyboard.down('Shift');for(let i=0;i<7;i++)await page.keyboard.press('ArrowRight');await page.keyboard.up('Shift');
  await page.waitForFunction(() => document.getElementById('annotation-selection').textContent.includes('Gelijke'));
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.reload();
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  assert.match(await page.locator('#annotation-selection').innerText(),/Nog te koppelen: Gelijke/);
  await page.locator('#annotation-discard').click();
  await tasks.step(page,2);await tasks.linked(page);
  await page.locator('#annotation-ranges li').filter({hasText:'Voorwaarde (essentieel)'}).getByRole('button',{name:'Deze bronkoppeling verwijderen'}).click();
  await page.locator('#annotation-required-links input').fill('Dit verband was per vergissing essentieel gemarkeerd.');
  await page.getByRole('button',{name:'Verplichting met deze reden terugnemen'}).click();
  await tasks.ready(page);
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
  await tasks.more(page);await page.locator('#annotation-overview').click();
  await page.waitForURL(u => u.searchParams.get('overview')==='true');
  assert.match(await page.locator('body').innerText(),/verplichting teruggenomen: Dit verband was per vergissing/);
  await page.getByRole('link',{name:'Verder aanwijzen'}).click();
  await tasks.type(page,'source_disposition');
  await page.locator('#annotation-source-reason').selectOption('metadata:document_metadata');
  await page.locator('[data-source-block]').first().click();
  await page.locator('#annotation-select-block').click();
  await page.locator('#annotation-add').click();
  await tasks.ready(page);
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
  await tasks.more(page);await page.locator('#annotation-overview').click();
  await page.waitForURL(u => u.searchParams.get('overview')==='true');
  assert.match(await page.locator('body').innerText(),/Brongebruik: Documentgegevens/);
  assert.deepEqual(errors,[]);
  assert.deepEqual(processingRequests,[]);
  fs.writeFileSync(output+'/result.json',JSON.stringify({mouse:true,unicode:true,multipleRanges:true,meaningFields:true,recommendationWitness:true,essentialDuty:true,reanchor:true,explicitDischarge:true,sourceProposal:true,mobileSourceNavigation:true,serverFailure:true,pauseCommit:true,newSession:true,overview:true,keyboard:true,widths:[1440,390]},null,2));
  await browser.close();
})().catch(e => {console.error(e);process.exit(1);});

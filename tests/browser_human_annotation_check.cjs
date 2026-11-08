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
    await p.goto(base+'/annotations?document='+m.document);
  }
  await login(page);
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
  await page.getByText('Betekenis van de uitspraak aanwijzen',{exact:true}).click();
  assert.equal(await page.locator('#annotation-field option[value=defined_term]').count(),0);
  await page.locator('#annotation-field').selectOption('recommended_action');
  const coreInput=page.locator('section.annotation-source-block').filter({hasText:'Controleer'}).locator('[data-source-input]');
  await coreInput.evaluate(input => {
    input.setSelectionRange(0,'Controleer'.length);input.dispatchEvent(new Event('select'));
  });
  await page.locator('#annotation-bind-field').click();
  await page.locator('#annotation-recommendation summary').click();
  await page.locator('#annotation-direction').selectOption('for');
  await coreInput.evaluate(input => {input.setSelectionRange(0,10);input.dispatchEvent(new Event('select'));});
  await page.locator('#annotation-direction-evidence').click();
  await page.locator('#annotation-strength-status').selectOption('not_stated');
  assert.equal(await page.locator('#annotation-direction-proof').innerText(),'Controleer');
  await page.locator('#annotation-role').selectOption('condition');
  await page.locator('#annotation-essential').check();
  await page.locator('section.annotation-source-block').filter({hasText:'Alleen bij klachten.'}).locator('[data-select-block]').click();
  await page.locator('#annotation-add').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  let saved = await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(),m.document);
  assert.equal(saved.entries.length,1);
  assert.equal(saved.entries[0].ranges[0].quote,'Controleer 👩🏽‍⚕️');
  assert.equal(saved.entries[0].ranges[1].required_for_meaning,true);
  assert.equal(saved.entries[0].ranges[1].quote,'Alleen bij klachten.');
  assert.deepEqual(saved.entries[0].field_evidence.recommended_action.span,{block_id:saved.entries[0].ranges[0].block_id,start:0,end:10});
  assert.ok(saved.entries[0].ranges[1].relationship_id.startsWith('link-v1:'));
  assert.equal(saved.entries[0].recommendation_semantics.direction,'for');
  assert.equal(saved.entries[0].recommendation_semantics.strength_status,'not_stated');
  // Network failure cannot yield a false saved label or navigation on Pause.
  await page.route('**/annotations/api',route => route.abort());
  await page.locator('#annotation-na').check();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent.startsWith('Opslaan mislukt.'));
  await page.locator('#annotation-pause').click();
  assert.equal(new URL(page.url()).pathname,'/annotations');
  await page.unroute('**/annotations/api');
  await page.locator('#annotation-retry').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  // Pause waits for the actual commit response, then a new login resumes it.
  await page.route('**/annotations/api',async route => { await new Promise(r => setTimeout(r,400));await route.continue(); });
  await page.locator('#annotation-type').selectOption('definition');
  await Promise.all([page.waitForURL(u => u.pathname==='/'),page.locator('#annotation-pause').click()]);
  await context.close();
  const fresh = await browser.newContext({viewport:{width:1440,height:1000}});page = await fresh.newPage();
  await login(page);
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  assert.equal(await page.locator('#annotation-type').inputValue(),'definition');
  assert.equal(await page.locator('#annotation-ranges li').count(),2);
  const resumed=await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(),m.document);
  assert.deepEqual(resumed.entries[0].field_evidence.recommended_action,saved.entries[0].field_evidence.recommended_action);
  // Removing essential context leaves a durable duty; ready cannot conceal it.
  await page.locator('#annotation-ranges li').nth(1).getByRole('button',{name:'Bereik verwijderen'}).click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent.includes('essentieel verband ontbreekt'));
  await page.reload();
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  assert.match(await page.locator('#annotation-required-links').innerText(),/Essentieel verband ontbreekt/);
  await page.getByRole('button',{name:'Dit verband opnieuw aanwijzen'}).click();
  await page.locator('section.annotation-source-block').filter({hasText:'Alleen bij klachten.'}).locator('[data-select-block]').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.reload();
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  const pendingRepair=await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(),m.document);
  assert.equal(pendingRepair.entries[0].pending_range.relationship_id,pendingRepair.entries[0].required_links[0].relationship_id);
  assert.equal(await page.locator('#annotation-role').isDisabled(),true);
  await page.locator('#annotation-add').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Selectie gereed en opgeslagen.');
  await page.locator('#annotation-overview').click();
  await page.waitForURL(u => u.searchParams.get('overview')==='true');
  assert.match(await page.locator('body').innerText(),/Voorwaarde.*essentieel/s);
  assert.equal(await page.getByRole('link',{name:'Deze annotatie aanpassen'}).count(),1);
  await page.getByRole('link',{name:'Deze annotatie aanpassen'}).click();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth>innerWidth),false);
    if(width===390) {
      const sourceSection=page.locator('section.annotation-source-block').filter({hasText:'Alleen bij klachten.'});
      await sourceSection.locator('[data-select-block]').click();
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
  // Keyboard/touch alternative retains the same source-reference contract.
  const section=page.locator('section.annotation-source-block').filter({hasText:'Gelijke tekst.'});
  await section.locator('summary').click();
  const input=section.locator('textarea');await input.focus();await page.keyboard.press('Control+Home');
  await page.keyboard.down('Shift');for(let i=0;i<7;i++)await page.keyboard.press('ArrowRight');await page.keyboard.up('Shift');
  await page.waitForFunction(() => document.getElementById('annotation-selection').textContent.includes('Gelijke'));
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  await page.reload();
  await page.locator('#annotation-entry').selectOption(saved.entries[0].annotation_id);
  assert.match(await page.locator('#annotation-selection').innerText(),/Nog te koppelen: Gelijke/);
  await page.locator('#annotation-discard').click();
  await page.locator('#annotation-ranges li').nth(1).getByRole('button',{name:'Bereik verwijderen'}).click();
  await page.locator('#annotation-required-links input').fill('Dit verband was per vergissing essentieel gemarkeerd.');
  await page.getByRole('button',{name:'Verplichting met deze reden terugnemen'}).click();
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Selectie gereed en opgeslagen.');
  await page.locator('#annotation-overview').click();
  await page.waitForURL(u => u.searchParams.get('overview')==='true');
  assert.match(await page.locator('body').innerText(),/verplichting teruggenomen: Dit verband was per vergissing/);
  await page.getByRole('link',{name:'Verder aanwijzen'}).click();
  await page.locator('#annotation-type').selectOption('source_disposition');
  await page.locator('#annotation-source-reason').selectOption('metadata:document_metadata');
  await page.locator('[data-select-block]').first().click();
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent==='Selectie gereed en opgeslagen.');
  await page.locator('#annotation-overview').click();
  await page.waitForURL(u => u.searchParams.get('overview')==='true');
  assert.match(await page.locator('body').innerText(),/Brongebruik: Documentgegevens/);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/result.json',JSON.stringify({mouse:true,unicode:true,multipleRanges:true,meaningFields:true,recommendationWitness:true,essentialDuty:true,reanchor:true,explicitDischarge:true,sourceProposal:true,mobileSourceNavigation:true,serverFailure:true,pauseCommit:true,newSession:true,overview:true,keyboard:true,widths:[1440,390]},null,2));
  await browser.close();
})().catch(e => {console.error(e);process.exit(1);});

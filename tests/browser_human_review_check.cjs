const tasks=require('./browser_annotation_tasks.cjs');
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE, output = process.env.METIS_BROWSER_OUTPUT;
  fs.mkdirSync(output, {recursive:true});
  const m = await (await fetch(base+'/browser-manifest')).json();
  const browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE, headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const page = await context.newPage(), errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base+'/login');
  await page.locator('[name=username]').fill(m.username);
  await page.locator('[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(u => u.pathname!='/login'), page.locator('button[type=submit]').click()]);
  await page.goto(base+'/review?'+new URLSearchParams({document:m.document,object:m.object}));
  assert.equal(await page.locator('[data-ko-assessment-form]').count(),0,'The exact saved judgment must not be asked again');
  await page.screenshot({path:output+'/review-before-desktop.png',fullPage:true});
  // #1064: one entry from the review card into the same card the worker used.
  assert.equal(await page.getByRole('link',{name:/Bronselectie corrigeren|Andere plek kiezen|Oorspronkelijke annotatie/}).count(),0);
  await page.getByRole('link', {name:'Aanpassen in de kaart', exact:true}).click();
  assert.equal(new URL(page.url()).searchParams.get('annotation'),m.annotation);
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  const row = key => page.locator('#annotation-simple-rows dd[data-row='+key+']');
  await row('core').getByText('De kwetsbare huid verklaart de pijn.',{exact:true}).waitFor();
  // No note about source corrections and no other way out: one button, back to review while nothing changed.
  assert.equal(await page.locator('#annotation-current-object').isVisible(),false);
  assert.equal(await page.locator('#annotation-rebuild').innerText(),'Terug naar review');
  assert.deepEqual(await page.locator('.annotation-task-actions button:visible').allInnerTexts(),['Terug naar review']);
  await page.screenshot({path:output+'/annotation-original-desktop.png',fullPage:true});
  // The reviewer turns the context sentence into evidence: '−' on Hoort erbij, '+' on Onderbouwing.
  const moved='De beoordeling betreft volwassenen.';
  await row('belongs').locator('.annotation-line').filter({hasText:moved}).locator('button.annotation-sign').click();
  await page.locator('#annotation-simple-rows dt[data-row=evidence] button.annotation-sign').click();
  await tasks.selectText(page,page.locator('[data-source-block]').filter({hasText:'De beoordeling'}),moved);
  await row('evidence').getByText(moved,{exact:true}).waitFor();
  await page.waitForFunction(() => document.getElementById('annotation-rebuild').textContent==='Kennisobject opnieuw bouwen' && !document.getElementById('annotation-rebuild').disabled);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+'/annotation-pending-mobile.png',fullPage:true});
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
  await page.setViewportSize({width:1440,height:1000});
  // One click: saved, built with the existing build, and back on this object's review card.
  await Promise.all([page.waitForURL(u => u.pathname==='/review' && u.searchParams.get('object')===m.object),
    page.locator('#annotation-rebuild').click()]);
  await page.screenshot({path:output+'/correction-overview-desktop.png',fullPage:true});
  // While the build runs the card says so and refreshes itself; approving waits for the new version.
  for (let i=0; i<60 && await page.locator('[data-ko-rebuilding]').count(); i++) {
    assert.equal(await page.locator('[name=review_action][value=approve]').isDisabled(),true);
    await page.waitForTimeout(1000);
    await page.goto(base+'/review?'+new URLSearchParams({document:m.document,object:m.object}));
  }
  await page.waitForSelector('[data-full-knowledge-passage]');
  const current = await page.locator('[data-full-knowledge-passage]').getAttribute('data-reviewed-version');
  assert.notEqual(current,m.version);
  assert.equal(await page.locator('[data-full-knowledge-passage]').innerText(),'De kwetsbare huid verklaart de pijn.');
  assert.match(await page.locator('body').innerText(),/Onderzoek beschrijft dit verband/);
  assert.match(await page.locator('body').innerText(),/De beoordeling betreft volwassenen/);
  assert.match(await page.locator('.ko-progress').innerText(),new RegExp(current.replaceAll('.','\\.')));
  assert.match(await page.locator('.ko-progress').innerText(),new RegExp('opnieuw gebouwd na correctie van versie '+m.version.replaceAll('.','\\.')));
  assert.equal(await page.locator('[name=evidence_not_applicable]').count(),0,'Literal linked evidence must not require an NVT workaround');
  await page.screenshot({path:output+'/review-corrected-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+'/review-corrected-mobile.png',fullPage:true});
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
  for (const question of ['applicable','complete','placed_correctly'])
    await page.locator(`[name=${question}][value=yes]`).check();
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),
    page.locator('[name=review_action][value=approve]').click()]);
  assert.equal(await page.locator('[data-review-receipt]').count(),1);
  assert.equal(await page.locator('[data-ko-assessment-form]').count(),0);
  await page.goto(base+'/review?'+new URLSearchParams({document:m.document,object:m.object}));
  assert.equal(await page.locator('[data-ko-assessment-form]').count(),0);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/human-review-result.json',JSON.stringify({annotation:m.annotation,object:m.object,previous:m.version,current,screenshots:6}));
  await browser.close();
})().catch(error => {console.error(error);process.exit(1);});

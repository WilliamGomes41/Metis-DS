const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const output = process.env.METIS_BROWSER_OUTPUT;
  const m = await (await fetch(base+'/browser-manifest')).json();
  const browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    const errors = [], semanticRequests = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {if (r.url().includes('/source-selection/start')) semanticRequests.push(r.url());});
    await page.goto(base+'/login');
    await page.locator('[name=username]').fill(m.username);
    await page.locator('[name=password]').fill(m.password);
    await Promise.all([page.waitForURL(u => u.pathname!='/login'),page.locator('button[type=submit]').click()]);
    const annotationURL = base+'/annotations?document='+m.document;
    await page.goto(base+'/source-selection');
    await page.locator('#source-document').selectOption(m.document);
    await page.getByRole('button',{name:'Document selecteren',exact:true}).click();
    await page.waitForURL(u => u.pathname === '/source-selection' && u.searchParams.get('selected_document') === m.document);
    const card = page.locator(`[data-source-document="${m.document}"][data-selected=true]`);
    assert.equal(await card.locator('.source-actions a,.source-actions button').count(),2);
    assert.equal(await card.getByRole('link',{name:'Bekijk status bouwopdrachten',exact:true}).count(),1);
    assert.equal(await card.locator('[data-source-attempt],.source-estimate').count(),0);
    for (const width of [1440,390]) {
      await page.setViewportSize({width,height:1000});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth<=window.innerWidth));
      await page.screenshot({path:`${output}/annotation-source-card-${width}.png`,fullPage:true});
    }
    const started = Date.now();
    await card.getByRole('button',{name:'Annoteren',exact:true}).click();
    await page.getByRole('heading',{name:'Bron wordt voorbereid',exact:true}).waitFor({timeout:3000});
    const responseMilliseconds = Date.now()-started;
    assert.ok(responseMilliseconds<3000, 'POST should not wait for the held converter');
    await page.getByRole('status').filter({hasText:'De bron wordt uitgelezen'}).waitFor();
    assert.match(await page.locator('section.room').innerText(), /Verstreken: \d+ min \d+ sec/);
    assert.match(await page.locator('section.room').innerText(), /voorbereiding loopt door/);
    const elsewhere = await context.newPage();
    await elsewhere.goto(base+'/tree');
    assert.ok(await elsewhere.getByRole('link',{name:'Bron voorbereiden',exact:true}).count() ||
              (await elsewhere.content()).includes('Bron voorbereiden'));
    await elsewhere.close();
    await page.reload();
    await page.getByRole('heading',{name:'Bron wordt voorbereid',exact:true}).waitFor();
    for (const width of [1440,390]) {
      await page.setViewportSize({width,height:1000});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth<=window.innerWidth));
      await page.screenshot({path:`${output}/annotation-source-progress-${width}.png`,fullPage:true});
    }
    await context.request.post(base+'/browser-release');
    await page.getByRole('button',{name:'Bevestig en ga annoteren',exact:true}).click({timeout:15000});
    await page.locator('[data-source-block]').first().waitFor({timeout:15000});
    assert.equal(await page.getByRole('heading',{name:'Bron wordt voorbereid',exact:true}).count(),0);
    assert.equal(await page.locator('meta[http-equiv=refresh]').count(),0);
    await page.goto(base+'/source-selection?selected_document='+m.document);
    await card.getByRole('link',{name:'Bekijk status bouwopdrachten',exact:true}).click();
    await page.getByText('Er is nog geen bouwopdracht voor dit document.').waitFor();
    await page.goto(base+'/source-selection?selected_document='+m.document);
    await card.getByRole('link',{name:'Annoteren',exact:true}).click();
    await page.waitForURL(annotationURL);
    await page.locator('[data-source-block]').first().waitFor();
    assert.deepEqual(semanticRequests,[]);
    assert.deepEqual(errors,[]);
    fs.writeFileSync(output+'/annotation-source-progress-result.json',JSON.stringify({responseMilliseconds,errors,semanticRequests}));
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1);});

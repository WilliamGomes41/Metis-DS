const tasks=require('./browser_annotation_tasks.cjs');
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE, output = process.env.METIS_BROWSER_OUTPUT;
  fs.mkdirSync(output, {recursive:true});
  const manifest = await (await fetch(base+'/browser-manifest')).json();
  const browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE, headless:true});
  let context = await browser.newContext({viewport:{width:1440,height:1000}});
  let page = await context.newPage();globalThis.metisProofPage=page;
  const errors = [];
  async function login() {
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base+'/login');
    await page.locator('[name=username]').fill(manifest.username);
    await page.locator('[name=password]').fill(manifest.password);
    await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  }
  await login();
  const uploaded = await page.evaluate(async () => {
    const body = new FormData();
    for (const [key,value] of Object.entries({ingest_kind:'new', title:'Menselijke ketenproef',
      version:'1.0', date:'2026-11-08', class_:'richtlijn', family:'test',
      review_mode:'choice', review_option:'uploader_sole', source_status:'established'})) body.append(key,value);
    body.append('file',new Blob(['<html><body><p>De kwetsbare huid verklaart de pijn.</p></body></html>'],{type:'text/html'}),'human.html');
    const response = await fetch('/ingest',{method:'POST',body});
    const html = await response.text();
    return {status:response.status,url:response.url,error:html.match(/data-error-code="([^"]+)/)?.[1]};
  });
  assert.equal(uploaded.status, 200, JSON.stringify(uploaded));
  const sid = new URL(uploaded.url).searchParams.get('document');
  assert.ok(sid, uploaded.url);
  await page.goto(base+'/annotations?document='+sid);
  await page.getByRole('button', {name:'Bron openen voor annotatie'}).click();
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  await page.goto(base+'/annotations?document='+sid+'&overview=true');
  assert.equal(await page.locator('#annotation-finalize').count(),0);
  await page.getByRole('heading',{name:'Nog niet verantwoord bronmateriaal'}).waitFor();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    await page.screenshot({path:`${output}/human-incomplete-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('link',{name:'Verder aanwijzen'}).click();
  const core = page.locator('[data-source-block]').first();
  const points = await core.evaluate(node => {
    const text = node.firstChild, range = document.createRange();
    range.setStart(text,0); range.setEnd(text,1); const first = range.getBoundingClientRect();
    range.setStart(text,text.length-1); range.setEnd(text,text.length); const last = range.getBoundingClientRect();
    return {x1:first.left+1,y1:first.top+first.height/2,x2:last.right,y2:last.top+last.height/2};
  });
  await page.mouse.move(points.x1,points.y1); await page.mouse.down();
  await page.mouse.move(points.x2,points.y2,{steps:20}); await page.mouse.up();
  // #1067: the card is the only way in. The selection is the statement; without a provider the card asks the type.
  const row = key => page.locator('#annotation-simple-rows dd[data-row='+key+']');
  await row('core').getByText('De kwetsbare huid verklaart de pijn.',{exact:true}).waitFor();
  assert.equal(await page.locator('#annotation-steps').isVisible(),false);
  await page.locator('#annotation-ready:enabled').click();
  await page.locator('#annotation-simple-type').waitFor();
  await page.locator('#annotation-simple-type-select').selectOption('explanation');
  await page.locator('#annotation-ready:enabled').click();
  await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
  await context.close();
  context = await browser.newContext({viewport:{width:1440,height:1000}});
  page = await context.newPage(); globalThis.metisProofPage=page; await login();
  await page.goto(base+'/annotations?document='+sid);
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  const saved = await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(), sid);
  assert.equal(saved.entries.length,1); assert.equal(saved.entries[0].status,'ready');
  // A duplicate stays unsaved and points back to the original; nothing is merged or overwritten.
  await tasks.selectText(page,page.locator('[data-source-block]').first(),'De kwetsbare huid verklaart de pijn.');
  await page.locator('#annotation-ready:enabled').click();
  await page.locator('#annotation-conflict-link').waitFor({state:'visible'});
  assert.match(await page.locator('#annotation-conflict-link').getAttribute('href'),new RegExp(saved.entries[0].annotation_id));
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent.includes('horen al bij een andere annotatie'));
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    await page.screenshot({path:`${output}/human-duplicate-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1000});
  // '−' takes the refused statement away; no empty draft is left to block the document.
  await page.locator('#annotation-simple-rows dd[data-row=core] .annotation-line button.annotation-sign').click();
  await page.getByRole('heading',{name:'Selecteer de uitspraak in de bron'}).waitFor();
  const after = (await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(), sid)).entries;
  assert.equal(after.filter(entry => entry.status !== 'withdrawn').length,1);
  await page.goto(base+'/annotations?document='+sid+'&overview=true');
  await page.waitForURL(url => url.searchParams.get('overview') === 'true');
  await page.locator('#annotation-finalize').waitFor();
  assert.match(await page.locator('body').innerText(), /De kwetsbare huid verklaart de pijn\./);
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    await page.screenshot({path:`${output}/human-overview-${width}.png`,fullPage:true});
  }
  await page.locator('[name=overview_hash]').evaluate(input => {input.value='stale-view';});
  await page.locator('#annotation-finalize').click();
  await page.getByRole('heading',{name:'Document nog niet afgesloten'}).waitFor();
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    await page.screenshot({path:`${output}/human-stale-${width}.png`,fullPage:true});
  }
  await page.getByRole('link',{name:'Documentoverzicht opnieuw controleren'}).click();
  await page.locator('#annotation-finalize').click();
  await page.waitForURL(url => url.pathname === '/annotations/build');
  await page.waitForFunction(() => document.getElementById('annotation-build-status').dataset.buildState === 'succeeded', {timeout:30000});
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    await page.screenshot({path:`${output}/human-build-${width}.png`,fullPage:true});
  }
  await page.locator('#annotation-build-review').click();
  await page.waitForURL(url => url.pathname === '/review');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/result.json', JSON.stringify({upload:true,ingestChoice:'uploader_sole',mouse:true,
    exactFields:true,pause:true,newSession:true,overview:true,seal:true,durableDispatch:true,
    humanBuild:true,reviewRoute:true,widths:[1440,390]},null,2));
  await browser.close();
})().catch(async error => {console.error(error);await tasks.describeCard(globalThis.metisProofPage);process.exit(1);});

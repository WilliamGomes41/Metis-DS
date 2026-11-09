const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE, output = process.env.METIS_BROWSER_OUTPUT;
  fs.mkdirSync(output, {recursive:true});
  const manifest = await (await fetch(base+'/browser-manifest')).json();
  const browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE, headless:true});
  let context = await browser.newContext({viewport:{width:1440,height:1000}});
  let page = await context.newPage();
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
  assert.match(await page.locator('#annotation-selection').innerText(), /De kwetsbare huid verklaart de pijn\./);
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-type').selectOption('explanation');
  await page.getByText('Betekenis van de uitspraak aanwijzen',{exact:true}).click();
  const input = page.locator('#annotation-source-input');
  for (const [field,text] of [['subject_span','De kwetsbare huid'],['predicate_span','verklaart'],['supported_object','de pijn']]) {
    await page.locator('#annotation-field').selectOption(field);
    await input.evaluate((element,text) => {
      const start = element.value.indexOf(text); element.setSelectionRange(start,start+text.length);
      element.dispatchEvent(new Event('select'));
    },text);
    await page.locator('#annotation-bind-field').click();
  }
  await page.locator('#annotation-na').check();
  await page.locator('#annotation-ready').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent === 'Selectie gereed en opgeslagen.');
  await page.locator('#annotation-pause').click();
  await page.waitForURL(url => url.pathname === '/');
  await context.close();
  context = await browser.newContext({viewport:{width:1440,height:1000}});
  page = await context.newPage(); await login();
  await page.goto(base+'/annotations?document='+sid);
  const saved = await page.evaluate(async sid => (await fetch('/annotations/api?document='+sid)).json(), sid);
  assert.equal(saved.entries.length,1); assert.equal(saved.entries[0].status,'ready');
  // A duplicate stays unsaved and points back to the original; recovery never
  // silently merges the selections or discards the local context choices.
  await page.locator('#annotation-new').click();
  await page.locator('[data-source-block]').first().click();
  await page.locator('#annotation-select-block').click();
  await page.locator('#annotation-add').click();
  await page.locator('#annotation-type').selectOption('explanation');
  await page.locator('#annotation-conflict-link').waitFor({state:'visible'});
  assert.match(await page.locator('#annotation-conflict-link').getAttribute('href'),new RegExp(saved.entries[0].annotation_id));
  assert.match(await page.locator('#annotation-status').innerText(),/Opslaan mislukt/);
  for (const width of [1440,390]) {
    await page.setViewportSize({width,height:1000});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
    await page.screenshot({path:`${output}/human-duplicate-${width}.png`,fullPage:true});
  }
  await page.locator('#annotation-ranges').getByRole('button',{name:'Bereik verwijderen'}).click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent === 'Concept opgeslagen.');
  await page.locator('#annotation-withdraw').click();
  await page.waitForFunction(() => document.getElementById('annotation-status').textContent === 'Annotatie teruggenomen en opgeslagen.');
  await page.locator('#annotation-overview').click();
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
})().catch(error => {console.error(error);process.exit(1);});

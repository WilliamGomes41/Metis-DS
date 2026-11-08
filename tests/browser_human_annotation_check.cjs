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
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/result.json',JSON.stringify({mouse:true,unicode:true,multipleRanges:true,serverFailure:true,pauseCommit:true,newSession:true,overview:true,keyboard:true,widths:[1440,390]},null,2));
  await browser.close();
})().catch(e => {console.error(e);process.exit(1);});

const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  assert.equal(m.metadata_ids.length, 2);
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage();
  await page.goto(base + '/login');
  await page.locator('input[name=username]').fill(m.username);
  await page.locator('input[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  async function proof(stage, width) {
    const layout = await page.evaluate(() => ({
      width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll('body *')].filter(el => {
        const rect = el.getBoundingClientRect();
        return el.getClientRects().length && (rect.right > innerWidth + 1 || rect.left < -1);
      }).map(el => ({tag: el.tagName, class: el.className,
        right: el.getBoundingClientRect().right, left: el.getBoundingClientRect().left,
        text: el.textContent.slice(0, 160)})).slice(-12),
    }));
    assert.equal(layout.scrollWidth > layout.width, false, `${stage}-${width}: ${JSON.stringify(layout)}`);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height: 1000});
    await page.goto(base + m.review);
    assert.equal(await page.locator('form[action="/review/source-exclusions"]').count(), 0);
    assert.equal(await page.locator('input[name=source_object_ids]').count(), 0);
    await proof('review-readonly', width);
    assert.equal(await page.getByRole('link',{name:'Bronregels gemotiveerd uitsluiten in Vorming'}).count(),0);
    const sid = new URL(page.url()).searchParams.get('document');
    const oldPage = await page.goto(base+'/source-selection?document='+sid+'&task=disposition');
    assert.equal(oldPage.status(),404);
    const refused = await page.evaluate(async sid => (await fetch('/review/source-exclusions',{method:'POST',
      body:new URLSearchParams({snapshot_id:sid,source_checked:'1'})})).status,sid);
    assert.equal(refused,404);
    const after=await (await page.request.get(base+'/browser-exclusions-state')).json();
    assert.deepEqual(after.excluded,[]);
    assert.ok(after.unselected_unchanged && after.source_unchanged);
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

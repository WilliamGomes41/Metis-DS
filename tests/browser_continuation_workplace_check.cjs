const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage();
  await page.goto(base + '/login');
  await page.locator('input[name=username]').fill(m.username);
  await page.locator('input[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  async function state() { return (await page.request.get(base + '/browser-continuation-state')).json(); }
  async function proof(stage, width) {
    await page.evaluate(() => scrollTo(0, 0));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, stage);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  for (const [index, width] of [1440, 390].entries()) {
    await page.setViewportSize({width, height: 1000});
    const d = m.documents[index];
    const before = await state();
    const review = base + '/review?' + new URLSearchParams({document: d.snapshot_id, object: d.object_id});
    await page.goto(review);
    assert.equal(await page.locator('[formaction="/review/context/accept"], form[action="/review/context/accept"]').count(), 0);
    assert.equal(await page.getByRole('link', {name: 'Bronaanvulling herstellen in Vorming'}).count(), 0);
    await proof('review-continuation', width);
    const retired = await page.goto(base + '/source-selection?' + new URLSearchParams({
      document: d.snapshot_id, object: d.object_id, task: 'continuation'
    }));
    assert.equal(retired.status(), 404);
    assert.deepEqual(await state(), before);
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

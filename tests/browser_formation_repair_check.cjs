const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage();
  await page.goto(base + '/login');
  await page.locator('[name=username]').fill(m.username);
  await page.locator('[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  const state = async () => (await page.request.get(base + '/browser-repair-state')).json();
  async function proof(stage, width) {
    await page.evaluate(() => scrollTo(0, 0));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, stage);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  for (const [index, width] of [1440, 390].entries()) {
    const d = m.documents[index];
    await page.setViewportSize({width, height: 1000});
    const before = await state();
    await page.goto(base + '/review?' + new URLSearchParams({document: d.snapshot_id, object: d.object_id}));
    assert.equal(await page.locator('[name=type_action][value=type_wijzigen], [name=documentpositie_action][value=andere_kop], [name=proposed_correction]').count(), 0);
    await proof('review-before-repair', width);
    assert.equal(await page.locator('a[href*="task=repair"]').count(), 0);
    const retired = await page.goto(base + '/source-selection?' + new URLSearchParams({
      document: d.snapshot_id, object: d.object_id, task: 'repair'
    }));
    assert.equal(retired.status(), 404);
    assert.deepEqual(await state(), before);
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });

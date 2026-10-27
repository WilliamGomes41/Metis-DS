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
  await Promise.all([page.waitForURL(u => u.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  const state = async () => (await page.request.get(base + '/browser-owner-state')).json();
  const before = await state();
  async function proof(stage, width) {
    const size = await page.evaluate(() => [innerWidth, document.documentElement.scrollWidth]);
    assert.ok(size[1] <= size[0] + 1, `${stage}-${width}: ${size}`);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height: 1000});
    for (const [i, obj] of m.objects.entries()) {
      await page.goto(base + '/inzicht/document?document=' + encodeURIComponent(m.document));
      assert.equal(await page.locator('form[action="/review/resolve"],form[action="/tree/processing-recovery"],form[action="/inzicht/document/pagina-verantwoorden"]').count(), 0);
      const link = page.locator('#acties a').filter({hasText: obj.candidate_text}).first();
      const details = link.locator('xpath=ancestor::details');
      await details.locator('summary').click();
      if (i === 0) await proof('diagnosis', width);
      await link.focus();
      await Promise.all([page.waitForURL(u => u.pathname === '/source-selection'), page.keyboard.press('Enter')]);
      const url = new URL(page.url());
      assert.equal(url.searchParams.get('document'), m.document);
      assert.equal(url.searchParams.get('object'), obj.object_id);
      assert.equal(await page.locator('h1').innerText(), 'Vorming');
      assert.ok((await page.locator('body').innerText()).includes(obj.candidate_text));
      await proof('owner-' + i, width);
      await page.reload();
      assert.deepEqual(await state(), before, 'diagnosis/owner GETs and refresh preserve durable work');
    }
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

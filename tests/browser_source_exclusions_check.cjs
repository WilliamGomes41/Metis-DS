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
  for (const [index, width] of [1440, 390].entries()) {
    await page.setViewportSize({width, height: 1000});
    await page.goto(base + m.review);
    assert.equal(await page.locator('form[action="/review/source-exclusions"]').count(), 0);
    assert.equal(await page.locator('input[name=source_object_ids]').count(), 0);
    await proof('review-readonly', width);
    await page.getByRole('link', {name: 'Bronregels gemotiveerd uitsluiten in Vorming'}).focus();
    await Promise.all([page.waitForURL(url => url.pathname === '/source-selection'), page.keyboard.press('Enter')]);
    const form = page.locator('form[action="/review/source-exclusions"]');
    assert.equal(await form.count(), 1);
    assert.equal(await form.locator('input[name=source_object_ids]').count(), 2 - index);
    assert.equal(await page.locator('form[action="/review"]').count(), 0);
    for (const input of await form.locator('input[name=source_object_ids]').all()) await input.uncheck();
    await form.locator(`input[name=source_object_ids][value="${m.metadata_ids[index]}"]`).check();
    const before = await (await page.request.get(base + '/browser-exclusions-state')).json();
    assert.equal(before.excluded.length, index);
    await proof('formation-selection', width);
    await form.locator('input[name=reason]').fill('Documentmetadata gecontroleerd in de oorspronkelijke bron.');
    await form.locator('input[name=source_checked]').check();
    await Promise.all([page.waitForNavigation({waitUntil: 'domcontentloaded'}), form.locator('button[type=submit]').click()]);
    assert.equal(new URL(page.url()).pathname, '/source-selection');
    assert.equal(new URL(page.url()).searchParams.get('task'), 'disposition');
    await page.reload();
    const after = await (await page.request.get(base + '/browser-exclusions-state')).json();
    assert.deepEqual(after.excluded, m.metadata_ids.slice(0, index + 1).sort());
    assert.ok(after.unselected_unchanged && after.source_unchanged);
    assert.ok(await page.locator('[data-source-group]').count());
    await proof('formation-saved', width);
    console.log('Source exclusions with unchanged source and knowledge', width, 'PASSED');
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

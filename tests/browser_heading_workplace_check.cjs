const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  assert.equal(m.heading_ids.length, 2);
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage();
  await page.goto(base + '/login');
  await page.locator('input[name=username]').fill(m.username);
  await page.locator('input[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  async function state() { return (await page.request.get(base + '/browser-heading-state')).json(); }
  async function proof(stage, width) {
    const layout = await page.evaluate(() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll('body *')].filter(el => el.getClientRects().length &&
        (el.getBoundingClientRect().right > innerWidth + 1 || el.getBoundingClientRect().left < -1))
        .map(el => ({tag: el.tagName, class: el.className, text: el.textContent.slice(0, 160)})).slice(-12)}));
    assert.equal(layout.scrollWidth > layout.width, false, `${stage}-${width}: ${JSON.stringify(layout)}`);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  for (const [index, width] of [1440, 390].entries()) {
    await page.setViewportSize({width, height: 1000});
    const before = await state();
    await page.goto(base + '/review?document=' + m.snapshot_id + '&object=' + m.heading_ids[index]);
    assert.equal(await page.locator('form[action="/review/headings/batch-confirm"]').count(), 0);
    assert.equal(await page.locator('input[name=eindoordeel][value=goedkeuren]').count(), 0);
    assert.equal(await page.locator('input[name=eindoordeel][value=afwijzen]').count(), 1);
    await proof('review-heading', width);
    await Promise.all([page.waitForURL(url => url.pathname === '/review/bronpassage'),
      page.getByRole('link', {name: 'Open oorspronkelijke bron', exact: true}).click()]);
    await page.goBack();
    assert.deepEqual(await state(), before, 'Opening source and detail must not write');
    await page.locator('[data-heading-owner] a').focus();
    await Promise.all([page.waitForURL(url => url.pathname === '/source-selection'), page.keyboard.press('Enter')]);
    const form = page.locator('form[action="/review/headings/batch-confirm"]');
    assert.equal(await form.count(), 1);
    for (const input of await form.locator('input[name=object_ids]').all()) {
      assert.equal(await input.isChecked(), false, 'No implicit heading selection');
    }
    await form.locator(`input[name=object_ids][value="${m.heading_ids[index]}"]`).check();
    assert.equal(await form.locator('input[name=object_ids]:checked').count(), 1);
    await proof('formation-heading-selection', width);
    await Promise.all([page.waitForNavigation({waitUntil: 'domcontentloaded'}), form.locator('button[type=submit]').click()]);
    assert.equal(new URL(page.url()).pathname, '/source-selection');
    assert.equal(new URL(page.url()).searchParams.get('task'), 'structure');
    await page.reload();
    const after = await state();
    assert.deepEqual(after.approved, m.heading_ids.slice(0, index + 1).sort());
    assert.ok(after.unselected_unchanged && after.source_unchanged);
    assert.equal(await page.locator(`input[name=object_ids][value="${m.heading_ids[index]}"]`).count(), 0);
    await proof('formation-heading-saved', width);
    console.log('Heading confirmation with unchanged source and unselected objects', width, 'PASSED');
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

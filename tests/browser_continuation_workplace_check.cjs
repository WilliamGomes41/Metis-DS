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
    assert.equal(await page.getByText('Ontbrekende brontekst:', {exact: true}).count(), 1);
    await proof('review-continuation', width);
    await page.getByRole('link', {name: 'Bronaanvulling herstellen in Vorming', exact: true}).focus();
    await Promise.all([page.waitForURL(url => url.pathname === '/source-selection'), page.keyboard.press('Enter')]);
    const form = page.locator('form[action="/review/context/accept"]');
    assert.equal(await form.count(), 1);
    await Promise.all([page.waitForURL(url => url.pathname === '/review/bronpassage'),
      page.getByRole('link', {name: 'Open oorspronkelijke bron', exact: true}).click()]);
    await page.goBack();
    assert.deepEqual(await state(), before, 'Owner and source GETs must not write');
    await proof('formation-continuation', width);
    await form.locator('button[type=submit]').focus();
    await Promise.all([page.waitForNavigation({waitUntil: 'domcontentloaded'}), page.keyboard.press('Enter')]);
    assert.equal(new URL(page.url()).pathname, '/source-selection');
    assert.equal(new URL(page.url()).searchParams.get('object'), d.object_id);
    assert.equal(await page.getByRole('status').getByText('De bronaanvulling is opgeslagen.', {exact: false}).count(), 1);
    assert.equal(await form.count(), 0);
    const after = await state();
    assert.equal(after[index].object_id, d.object_id);
    assert.notEqual(after[index].version, before[index].version);
    assert.equal(after[index].status, 'needs_review');
    assert.equal(after[index].history_count, 2);
    assert.ok(after[index].merged && after[index].others_unchanged && after[index].source_unchanged);
    assert.deepEqual(after[1-index], before[1-index]);
    await page.reload();
    assert.deepEqual(await state(), after, 'Refresh must not repeat the command');
    await proof('formation-continuation-saved', width);
    await page.getByRole('link', {name: 'Deze passage beoordelen in Review', exact: true}).click();
    assert.equal(new URL(page.url()).searchParams.get('object'), d.object_id);
    assert.equal(new URL(page.url()).pathname, '/review');
    assert.deepEqual(await state(), after);
    console.log('Literal continuation with unchanged source and neighbors', width, 'PASSED');
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

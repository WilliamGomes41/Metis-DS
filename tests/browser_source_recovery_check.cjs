const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const manifest = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage();
  await page.goto(base + '/login');
  await page.locator('[name=username]').fill(manifest.username);
  await page.locator('[name=password]').fill(manifest.password);
  await Promise.all([page.waitForURL(u => u.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  const state = async () => (await page.request.get(base + '/browser-recovery-state')).json();
  const accounting = 'form[action="/inzicht/document/pagina-verantwoorden"]';
  const grant = 'form[action="/tree/processing-recovery"]';
  async function proof(stage, width) {
    const size = await page.evaluate(() => [innerWidth, document.documentElement.scrollWidth]);
    assert.ok(size[1] <= size[0] + 1, `${stage}-${width}: ${size}`);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  for (const [index, width] of [1440, 390].entries()) {
    const docs = manifest.documents[index];
    await page.setViewportSize({width, height: 1000});
    const before = await state();
    await page.goto(base + '/inzicht/document?document=' + docs.pages + '#paginas');
    assert.equal(await page.locator(accounting + ',' + grant).count(), 0);
    await page.getByRole('link', {name: 'Pagina verantwoorden in Vorming', exact: true}).focus();
    await Promise.all([page.waitForURL(u => u.pathname === '/source-selection'), page.keyboard.press('Enter')]);
    assert.equal(new URL(page.url()).hash, '#source-page-2');
    assert.equal(await page.locator('#source-page-2 ' + accounting).count(), 1);
    assert.equal(await page.locator(accounting).count(), 1);
    assert.deepEqual(await state(), before, 'Inzicht and Vorming GETs must not mutate domain work');
    await page.locator(accounting + ' [name=category]').selectOption('colofon_of_copyright');
    await page.locator(accounting + ' [name=note]').fill('Alleen copyrighttekst; gecontroleerd op de oorspronkelijke pagina.');
    await proof('pages-owner', width);
    await Promise.all([page.waitForNavigation(), page.locator(accounting + ' button').click()]);
    assert.equal(new URL(page.url()).pathname, '/source-selection');
    await page.reload();
    const accounted = await state();
    assert.equal(accounted[docs.pages].accountings, 1);
    assert.equal(accounted[docs.pages].grant, false);
    assert.equal(await page.locator(accounting).count(), 0);
    await proof('pages-recorded', width);
    await page.goto(base + '/inzicht/document?document=' + docs.recovery);
    assert.equal(await page.locator(accounting + ',' + grant).count(), 0);
    await page.getByRole('link', {name: 'Herstelvoorwaarden bekijken in Vorming', exact: true}).focus();
    await Promise.all([page.waitForURL(u => u.pathname === '/source-selection'), page.keyboard.press('Enter')]);
    assert.equal(new URL(page.url()).hash, '#processing-recovery');
    assert.deepEqual(await state(), accounted);
    await page.locator(grant + ' [name=reason]').fill('Eenmalige broncontrole; autorisatie start zelf geen verwerking.');
    await Promise.all([page.waitForNavigation(), page.locator(grant + ' button').click()]);
    assert.equal(new URL(page.url()).pathname, '/source-selection');
    await page.reload();
    const after = await state();
    assert.equal(after[docs.recovery].grant, true);
    assert.equal(after[docs.recovery].consumed, null);
    assert.equal(await page.locator(grant).count(), 0);
    for (const sid of Object.values(docs)) {
      assert.ok(after[sid].attempts_unchanged && after[sid].source_unchanged);
      assert.deepEqual(after[sid].objects, []);
      assert.deepEqual(after[sid].bindings, []);
    }
    await proof('grant-authorized-without-start', width);
    await page.goto(base + '/inzicht/document?document=' + docs.recovery);
    assert.equal(await page.locator(accounting + ',' + grant).count(), 0);
    assert.deepEqual(await state(), after);
    console.log('Source accounting and recovery grant on Vorming', width, 'PASSED');
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

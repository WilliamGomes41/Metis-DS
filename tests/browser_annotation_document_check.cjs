const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const output = process.env.METIS_BROWSER_OUTPUT;
  const manifest = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill(manifest.username);
    await page.locator('[name=password]').fill(manifest.password);
    await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);

    const workspace = base + '/annotations?document=' + manifest.snapshot_id;
    await page.goto(workspace + '&overview=true');
    await page.getByRole('button', {name: 'Bevestig en ga annoteren'}).click();
    const done = page.getByRole('button', {name: 'Ik ben klaar met dit document'});
    const final = page.getByRole('button', {name: 'Afronden en bouwen'});
    const toc = page.getByRole('navigation', {name: 'Inhoudsopgave'});
    await done.waitFor();
    assert.equal(await page.getByRole('link', {name: 'Bronselectie beëindigen en document controleren'}).count(), 0);
    assert.equal(await final.count(), 0);
    await done.click();
    await page.getByRole('heading', {name: 'Documentcontrole', exact: true}).waitFor();
    assert.equal(new URL(page.url()).pathname, '/annotations');
    const markFull = toc.getByRole('button', {name: 'Dekking hele richtlijn controleren', exact: true});
    await markFull.click();
    await toc.locator('[data-section-status="open"]').first().waitFor();
    await page.getByRole('link', {name: 'Diagnostiek', exact: true}).last().click();
    assert.ok(new URL(page.url()).hash);
    await page.waitForFunction(() => !document.querySelector('[data-confirmed-document-build]'));
    await page.screenshot({path: output + '/document-check-open.png', fullPage: true});
    await page.reload();
    await toc.locator('[data-section-status="open"]').first().waitFor();
    await page.getByRole('button', {name: 'Verder annoteren', exact: true}).click();
    await done.waitFor();
    assert.equal(await toc.locator('[data-section-status]').count(), 0);
    await done.click();
    await toc.getByRole('button', {name: 'Markeer als nagekeken: Algemeen', exact: true}).click();
    await toc.locator('[data-section-status="checked"]').first().waitFor();
    await toc.getByRole('button', {name: 'Markeer als nagekeken: Diagnostiek', exact: true}).click();
    await final.waitFor();

    await page.setViewportSize({width: 390, height: 844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.equal(await page.getByText('Overige begeleidende tekst.', {exact: true}).isVisible(), true);
    await page.screenshot({path: output + '/document-check-ready-mobile.png', fullPage: true});
    await final.click();
    await page.waitForURL(url => url.pathname === '/annotations/build');
    assert.equal(new URL(page.url()).searchParams.get('document'), manifest.snapshot_id);
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });

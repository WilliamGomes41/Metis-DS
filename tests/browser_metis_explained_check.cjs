const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const manifest = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill(manifest.username);
    await page.locator('[name=password]').fill(manifest.password);
    await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);

    async function verify(stage, width) {
      const dimensions = await page.evaluate(() => [innerWidth, document.documentElement.scrollWidth]);
      assert.ok(dimensions[1] <= dimensions[0] + 1, `${stage}: overflow ${dimensions}`);
      assert.equal(await page.locator('h1').count(), 1);
      assert.equal(await page.getByRole('main').count(), 1);
      assert.equal(await page.locator('form form').count(), 0);
      assert.equal(await page.locator('.explained-layout').evaluate(element => getComputedStyle(element).display), 'grid', 'Page stylesheet must be loaded');
      const contrast = await page.getByRole('searchbox').evaluate(input => {
        const luminance = color => {
          const rgb = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => {
            const channel = value / 255;
            return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
          });
          return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
        };
        const ink = luminance(getComputedStyle(input, '::placeholder').color);
        const paper = luminance(getComputedStyle(input).backgroundColor);
        return (Math.max(ink, paper) + 0.05) / (Math.min(ink, paper) + 0.05);
      });
      assert.ok(contrast >= 4.5, `${stage}: placeholder contrast ${contrast}`);
      await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
    }

    for (const width of [1440, 390]) {
      await page.setViewportSize({width, height: 1000});
      await page.goto(base + '/over-console');
      await page.getByRole('heading', {name: 'Van bron naar bruikbare kennis', exact: true}).waitFor();
      await verify('uitleg-overzicht', width);

      const input = page.getByRole('searchbox', {name: 'Zoek een begrip, model of onderwerp'});
      await input.fill('gold standard');
      await Promise.all([page.waitForURL(url => url.searchParams.get('q') === 'gold standard'), input.press('Enter')]);
      await page.getByRole('link', {name: 'Referentieset', exact: true}).focus();
      await Promise.all([page.waitForURL(url => url.hash === '#begrip-referentieset'), page.keyboard.press('Enter')]);
      assert.ok(await page.locator('#begrip-referentieset').isVisible());
      await verify('uitleg-begrippen', width);

      await page.goto(base + '/over-console?section=modellen');
      await page.getByRole('link', {name: 'Context- en relatiemodel', exact: true}).click();
      await page.getByRole('heading', {name: 'Context- en relatiemodel', exact: true}).waitFor();
      await page.getByRole('navigation', {name: 'Op deze modelpagina'}).getByRole('link', {name: 'Beperkingen', exact: true}).focus();
      await page.keyboard.press('Enter');
      assert.equal(new URL(page.url()).hash, '#model-grenzen');
      await page.evaluate(() => scrollTo(0, 0));
      await verify('uitleg-model', width);

      await page.getByRole('button', {name: 'Wissel tussen lichte en donkere modus'}).click();
      assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
      await verify('uitleg-model-donker', width);
      await page.getByRole('button', {name: 'Wissel tussen lichte en donkere modus'}).click();

      await page.goto(base + '/over-console?q=zzzonbestaand');
      assert.ok(await page.getByText('Geen uitleg gevonden.', {exact: false}).isVisible());
      await page.getByRole('link', {name: 'Bekijk alle begrippen', exact: true}).click();
      assert.equal(new URL(page.url()).searchParams.get('section'), 'begrippen');
      await page.goto(base + '/over-console?section=kennisbasis');
      assert.ok(await page.getByRole('heading', {name: 'De kennisbasis', exact: true}).isVisible());
    }

    const noScript = await browser.newContext({javaScriptEnabled: false, storageState: await page.context().storageState()});
    const plain = await noScript.newPage();
    await plain.goto(base + '/over-console');
    await plain.getByRole('searchbox').fill('brontrouw');
    await Promise.all([plain.waitForURL(url => url.searchParams.get('q') === 'brontrouw'), plain.getByRole('button', {name: 'Zoeken', exact: true}).click()]);
    await plain.getByRole('link', {name: 'Bron- en herkomstmodel', exact: true}).click();
    assert.ok(await plain.getByRole('heading', {name: 'Bron- en herkomstmodel', exact: true}).isVisible());
    assert.deepEqual(errors, []);
    console.log('Metis uitgelegd: desktop, mobile, dark theme, keyboard and no-JS flows PASS');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });

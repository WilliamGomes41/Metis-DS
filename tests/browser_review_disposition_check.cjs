const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

// Literal expectation from the projectlead decision (#974), not read from the page.
const FITS = {
  ja: ['goedkeuren', 'goedkeuren_na_correctie', 'afwijzen', 'later_beoordelen'],
  mist_context: ['goedkeuren_na_correctie', 'afwijzen', 'later_beoordelen'],
  samenvoegen: ['goedkeuren_na_correctie', 'afwijzen', 'later_beoordelen'],
  alleen_onderbouwing: ['goedkeuren', 'goedkeuren_na_correctie', 'afwijzen', 'later_beoordelen'],
  geen_kenniseenheid: ['afwijzen', 'later_beoordelen'],
};
const ALL = FITS.ja;

(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const out = process.env.METIS_BROWSER_OUTPUT;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const card = `${base}/review?document=${m.snapshot_id}&object=${m.objects[0]}`;
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE, args: ['--no-sandbox']});
  const events = async () => (await (await fetch(base + '/browser-review-events')).json()).count;

  async function open(width, javaScriptEnabled) {
    const context = await browser.newContext({viewport: {width, height: 1000}, deviceScaleFactor: 2, javaScriptEnabled});
    const page = await context.newPage();
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill(m.username);
    await page.locator('[name=password]').fill(m.password);
    await Promise.all([page.waitForURL((url) => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
    await page.goto(card);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow at ${width}`);
    return {context, page};
  }
  const decision = (page, value) => page.locator(`[name=eindoordeel][value=${value}]`);
  async function offered(page) {
    const result = [];
    for (const value of ALL) {
      const input = decision(page, value);
      if (await input.isVisible() && await input.isEnabled()) result.push(value);
    }
    return result;
  }
  async function arrowCycle(page, start) {
    await decision(page, start).focus();
    await page.keyboard.press('Space');
    const seen = [];
    for (let i = 0; i < 5; i += 1) {
      await page.keyboard.press('ArrowDown');
      seen.push(await page.evaluate(() => document.activeElement.value));
    }
    return [...new Set(seen)].sort();
  }
  const shoot = (page, name) => page.locator('[data-review-form]').screenshot({path: `${out}/${name}.png`});

  for (const width of [1440, 390]) {
    // With JavaScript: hidden and disabled, a judgement that stops fitting is cleared.
    let {context, page} = await open(width, true);
    assert.deepEqual(await offered(page), ALL);
    for (const [suitability, fits] of Object.entries(FITS)) {
      await page.locator(`[name=suitability][value=${suitability}]`).check();
      assert.deepEqual(await offered(page), fits, `js ${suitability}`);
      assert.deepEqual(await arrowCycle(page, fits[0]), [...fits].sort(), `keyboard js ${suitability}`);
      const scope = page.locator(`[data-decision-scope="${suitability}"]`);
      assert.equal(await scope.isVisible(), true);
    }
    await page.locator('[name=suitability][value=ja]').check();
    await decision(page, 'goedkeuren').check();
    await page.locator('[name=suitability][value=mist_context]').check();
    assert.equal(await decision(page, 'goedkeuren').isChecked(), false);
    assert.match(await page.locator('[data-decision-hint]').innerText(), /past niet bij deze keuze en is leeggemaakt/);
    await page.locator('[name=suitability][value=mist_context]').focus();
    await shoot(page, `js-mist-context-${width}`);
    await context.close();

    // Without JavaScript: CSS alone limits the choice and flags a stale one.
    ({context, page} = await open(width, false));
    for (const [suitability, fits] of Object.entries(FITS)) {
      // A fresh form: without JavaScript a checked judgement cannot be cleared.
      await page.goto(card);
      await page.locator(`[name=suitability][value=${suitability}]`).check();
      assert.deepEqual(await offered(page), fits, `no-js ${suitability}`);
      assert.deepEqual(await arrowCycle(page, fits[0]), [...fits].sort(), `keyboard no-js ${suitability}`);
    }
    await page.locator('[name=suitability][value=ja]').check();
    await decision(page, 'goedkeuren').check();
    await page.locator('[name=suitability][value=mist_context]').check();
    assert.equal(await decision(page, 'goedkeuren').isVisible(), true);
    assert.equal(await page.locator('[data-allowed-for] [data-decision-mismatch]:visible').count(), 1);
    assert.equal(await decision(page, 'goedkeuren').evaluate((node) => node.closest('label').innerText.includes('Past niet bij je keuze hierboven')), true);
    for (const name of ['documentpositie_action', 'type_action']) await page.locator(`[name=${name}][value=dit_klopt]`).check();
    const ack = page.locator('[name=relation_review_ack]');
    if (await ack.count()) await ack.check();
    await shoot(page, `nojs-mismatch-${width}`);
    const before = await events();
    const [response] = await Promise.all([page.waitForNavigation(), page.locator('[data-submit-review]').click()]);
    assert.equal(response.status(), 400);
    const banner = page.locator('[data-error-code="review_disposition_conflict"]');
    assert.equal(await banner.innerText(),
      'Je koos ‘Nee, ik mis uitleg eromheen’ met het besluit ‘Goedkeuren’. Die combinatie kan niet. ' +
      'Bij ‘Nee, ik mis uitleg eromheen’ kun je kiezen uit ‘Correctie specificeren’, ‘Afwijzen’ of ‘Later beoordelen’. ' +
      'Je beoordeling is niet opgeslagen. Ga terug naar de passage en kies een besluit dat past.');
    assert.equal(await events(), before);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({path: `${out}/nojs-conflict-page-${width}.png`, fullPage: true});
    await context.close();
  }
  await browser.close();
})().catch((error) => { console.error(error); process.exit(1); });

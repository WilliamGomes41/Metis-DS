const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const out = process.env.METIS_BROWSER_OUTPUT;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE, args: ['--no-sandbox']});
  const events = async () => (await (await fetch(base + '/browser-review-events')).json()).count;
  let index = 0;
  for (const width of [1440, 375]) {
    for (const javaScriptEnabled of [true, false]) {
      const context = await browser.newContext({viewport: {width, height: 1000}, javaScriptEnabled});
      const page = await context.newPage();
      const card = `${base}/review?document=${m.snapshot_id}&object=${m.objects[index++]}`;
      await page.goto(base + '/login');
      await page.locator('[name=username]').fill(m.username);
      await page.locator('[name=password]').fill(m.password);
      await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
      await page.goto(card);
      const before = await events();
      assert.equal(await page.locator('[data-ko-assessment-form] input[type=radio]').count(), 6);
      assert.equal(await page.locator('input[type=radio]:checked').count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      if (javaScriptEnabled) {
        assert.equal(await page.locator('[value=approve]').isDisabled(), true);
        await page.screenshot({path: `${out}/card-${width}.png`, fullPage: true});
      }
      for (const name of ['applicable', 'complete', 'placed_correctly']) {
        const radio = page.locator(`[name=${name}][value=yes]`);
        await radio.focus(); await page.keyboard.press('Space');
        assert.equal(await radio.isChecked(), true, 'native keyboard answer');
      }
      await page.locator('[name=complete][value=adjust]').check();
      if (javaScriptEnabled) {
        assert.equal(await page.locator('[value=approve]').isDisabled(), true);
        assert.equal(await page.locator('.ko-adjustment').isVisible(), true);
        const form = await page.locator('[data-ko-assessment-form]').evaluate(el => Object.fromEntries(new FormData(el)));
        const refused = await page.request.post(base + '/review', {form: {...form, review_action: 'approve'}});
        assert.equal(refused.status(), 400);
        assert.ok((await refused.text()).includes('value="adjust" required checked'));
      } else {
        const [refused] = await Promise.all([page.waitForNavigation(), page.locator('[value=approve]').click()]);
        assert.equal(refused.status(), 400);
        assert.equal(await page.locator('[name=complete][value=adjust]').isChecked(), true);
      }
      assert.equal(await events(), before, 'adjustment cannot write approval');
      await Promise.all([page.waitForURL(url => url.pathname === '/source-selection'),
        page.getByRole('link', {name: 'Correctie nodig', exact: true}).click()]);
      assert.equal(await events(), before, 'opening repair does not write');
      if (javaScriptEnabled) await page.screenshot({path: `${out}/correction-${width}.png`, fullPage: true});
      await page.goto(card);
      await Promise.all([page.waitForNavigation(), page.getByRole('button', {name: 'Later beoordelen', exact: true}).click()]);
      assert.ok(!new URL(page.url()).searchParams.has('receipt_interaction'));
      assert.equal(await events(), before, 'deferral has no durable decision');
      await page.goto(card);
      for (const name of ['applicable', 'complete', 'placed_correctly']) {
        await page.locator(`[name=${name}][value=yes]`).focus(); await page.keyboard.press('Space');
      }
      await Promise.all([page.waitForURL(url => url.searchParams.has('receipt_interaction')),
        page.getByRole('button', {name: 'Goedkeuren en opslaan', exact: true}).click()]);
      assert.equal(await page.locator('[data-review-receipt]').count(), 1);
      assert.equal(await page.locator('[data-answer=yes]').count(), 3);
      assert.equal(await page.locator('form[data-ko-assessment-form]').count(), 0);
      assert.ok(await events() > before);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      if (javaScriptEnabled) await page.screenshot({path: `${out}/receipt-${width}.png`, fullPage: true});
      await context.close();
    }
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

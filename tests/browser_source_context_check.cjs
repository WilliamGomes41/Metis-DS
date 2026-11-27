const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage();
  await page.goto(base + '/login');
  await page.locator('input[name=username]').fill(m.username);
  await page.locator('input[name=password]').fill(m.password);
  await Promise.all([page.waitForURL(url => !url.pathname.endsWith('/login')), page.locator('button[type=submit]').click()]);
  async function proof(stage, width) {
    const data = await page.evaluate(() => ({
      overflow: document.documentElement.scrollWidth > innerWidth,
      stylesheet: [...document.styleSheets].some(s => s.href?.includes('/brand/console.css') && s.cssRules.length),
      nestedForms: !!document.querySelector('form form'),
      context: document.querySelector('[data-passage-context], [data-document-context]')?.innerText,
      contextTop: document.querySelector('[data-passage-context], [data-document-context]')?.getBoundingClientRect().top,
      menuBottom: document.querySelector('.topbar, .ko-topbar')?.getBoundingClientRect().bottom,
    }));
    assert.equal(data.overflow, false);
    assert.equal(data.nestedForms, false);
    assert.ok(data.stylesheet && data.context);
    if (stage !== 'passage') {
      assert.ok(data.contextTop >= 0, 'Context task must start in the visible viewport');
      assert.ok(data.menuBottom <= data.contextTop, 'Navigation must not cover the context task');
    }
    fs.writeFileSync(`${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.json`, JSON.stringify(data, null, 2));
    await page.screenshot({path: `${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage: true});
  }
  async function openContextEvidence() {
    const evidence = page.locator('.ko-evidence');
    if (await evidence.count() && !await evidence.evaluate(element => element.open)) {
      await evidence.locator(':scope > summary').focus();
      await page.keyboard.press('Enter');
    }
  }
  const state = async () => (await (await fetch(base + '/browser-context-state')).json());
  const before = await state();
  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height: 1000});
    await page.goto(base + m.target);
    await openContextEvidence();
    assert.ok(await page.locator('[data-confirmed-source-context]').isVisible());
    assert.match(await page.locator('[data-confirmed-source-context]').innerText(), /DOEN/);
    assert.equal(await page.locator('form[action="/review/source-context"]').count(), 0);
    await proof('passage', width);
    assert.equal((await page.goto(base + m.source)).status(), 404);
    assert.deepEqual(await state(), before);
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

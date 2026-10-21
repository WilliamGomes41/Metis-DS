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
      context: document.querySelector('[data-passage-context]')?.innerText,
      contextTop: document.querySelector('[data-passage-context]')?.getBoundingClientRect().top,
      menuBottom: document.querySelector('.topbar')?.getBoundingClientRect().bottom,
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
  async function submit(form) {
    await form.locator('textarea[name=reason]').fill('Gecontroleerd in de oorspronkelijke bron.');
    await form.locator('input[name=source_checked]').check();
    await Promise.all([page.waitForURL(url => url.searchParams.get('context_saved') === 'yes'), form.locator('button[type=submit]').click()]);
  }
  for (const [width, height] of [[1440, 1000], [390, 844]]) {
    await page.setViewportSize({width, height});
    await page.goto(base + m.target);
    await proof('passage', width);
    await page.locator('[data-context-picker] > summary').click();
    const choice = page.locator('[data-context-picker] .context-choice').filter({has: page.locator(`a[href*="object=${m.source_id}"]`)}).first();
    const group = choice.locator('xpath=..');
    if (!await group.evaluate(el => el.open)) await group.locator(':scope > summary').click();
    await choice.locator('a').filter({hasText: 'Kies deze tekst als context'}).click();
    const form = page.locator('[data-source-context-form]');
    assert.equal(await form.locator('input[name=role]:checked').count(), 0);
    assert.equal(await form.locator(`input[name=target_object_ids][value="${m.target_id}"]`).isChecked(), true);
    const before = await (await page.request.get(base + '/browser-context-state')).json();
    assert.equal(before.links.length, 0);
    await proof('contextkeuze', width);
    await form.locator('input[name=role][value=label]').check();
    await submit(form);
    assert.equal(new URL(page.url()).searchParams.get('object'), m.target_id);
    const saved = await (await page.request.get(base + '/browser-context-state')).json();
    assert.equal(saved.role.role, 'label');
    assert.equal(saved.links[0].text, 'DOEN');
    assert.equal(saved.target_status, 'needs_review');
    await proof('vastgelegde-context', width);
    await page.getByRole('link', {name: 'Koppeling aanpassen of verwijderen'}).click();
    const exclude = page.locator('[data-context-action=excluded]');
    await exclude.locator('summary').click();
    assert.equal(await exclude.locator('input[name=target_object_ids]').count(), 0);
    await submit(exclude.locator('form'));
    assert.equal((await (await page.request.get(base + '/browser-context-state')).json()).links.length, 0);
    await page.goto(base + m.source);
    const reset = page.locator('[data-context-action=reset]');
    await reset.locator('summary').click();
    await submit(reset.locator('form'));
    assert.deepEqual((await (await page.request.get(base + '/browser-context-state')).json()).role, {});
    console.log('Passage-first context workflow', width, 'PASSED');
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

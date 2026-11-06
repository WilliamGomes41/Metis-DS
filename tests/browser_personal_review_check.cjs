const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE, args:['--no-sandbox']});
  const page = await browser.newPage();
  async function login(username) {
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill(username);
    await page.locator('[name=password]').fill(m.password);
    await Promise.all([page.waitForURL(url => url.pathname !== '/login'), page.locator('button[type=submit]').click()]);
  }
  async function state() { return (await page.request.get(base + '/browser-personal-state')).json(); }
  async function proof(stage, width) {
    await page.evaluate(() => scrollTo(0,0));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, stage);
    assert.equal(await page.locator('form form').count(), 0);
    await page.screenshot({path:`${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`, fullPage:true});
  }
  for (const [index,width] of [1440,390].entries()) {
    await page.setViewportSize({width,height:1000});
    await login(m.username);
    const d = m.documents[index ? 'Gemengd2' : 'Gemengd'];
    const before = await state();
    await page.goto(base + '/review');
    const card = page.locator(`[data-workboard-document="${d.snapshot_id}"]`);
    const action = card.locator('[data-personal-review-action]');
    assert.equal(await card.locator('[data-personal-open]').innerText(), '2');
    assert.equal(await action.count(), 1);
    assert.equal(await action.isVisible(), true);
    assert.equal(await card.locator('details, form, progress').count(), 0);
    assert.equal(await page.locator('[data-personal-group="waiting"]').count(), 1);
    assert.equal(await page.locator('[data-personal-group="complete"]').count(), 1);
    await proof('personal-landing',width);
    await action.focus();
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.keyboard.press('Enter')]);
    assert.equal(new URL(page.url()).searchParams.get('task'), 'contextual');
    // The existing contextual route may show its inventory before a passage.
    if (!await page.locator('[data-ko-assessment-form]').count()) {
      const passage = page.locator(`a[href*="object=${d.context}"]`).first();
      await passage.click();
    }
    const form = page.locator('[data-ko-assessment-form]');
    assert.equal(await form.locator('[name=object_id]').inputValue(),d.context);
    assert.deepEqual(await state(), before, 'Landing and detail navigation must not mutate domain work');
    for (const question of ['applicable','complete','placed_correctly']) {
      assert.equal(await form.locator(`[name=${question}]:checked`).count(),0);
      await form.locator(`[name=${question}][value=yes]`).check();
    }
    await form.locator('[name=evidence_not_applicable]').check();
    const approve = form.locator('[name=review_action][value=approve]');
    assert.equal(await approve.isEnabled(),true,'The displayed fixture proposal must be confirmable');
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}), approve.click()]);
    assert.equal(await page.locator('[data-review-receipt]').count(),1);
    assert.equal(await page.locator('[data-ko-assessment-form]').count(),0);
    assert.equal(await page.locator('[data-saved-answer][data-answer=yes]').count(),3);
    const after = await state();
    assert.notDeepEqual(after,before,'Real review POST must commit');
    await page.goto(base + '/review');
    assert.equal(await card.locator('[data-personal-open]').innerText(),'1');
    assert.equal(await action.innerText(),'Verder beoordelen');
    await page.reload();
    assert.deepEqual(await state(),after,'Refresh must not repeat review');
    await proof('personal-after-review',width);
    await page.goto(base + '/logout');
    await login(m.other);
    await page.goto(base + '/review');
    assert.equal(await card.locator('[data-personal-open]').innerText(),'1');
    assert.equal(await card.locator('[data-personal-second]').innerText(),'1');
    assert.equal(await action.innerText(),'Beginnen','Another reviewer’s activity must not start my work');
    assert.ok((await action.getAttribute('href')).includes('task=second_review'));
    await proof('personal-other-reviewer',width);
    await page.goto(base + '/logout');
    await login(m.empty);
    await page.goto(base + '/review');
    assert.equal(await page.locator('[data-personal-empty]').isVisible(),true);
    assert.equal(await page.locator('[data-personal-review-action]').count(),0);
    await page.goto(base + '/logout');
    console.log('Personal queue, real review, independent second, keyboard and GET invariance',width,'PASSED');
  }
  await browser.close();
})().catch(error => {console.error(error);process.exit(1);});

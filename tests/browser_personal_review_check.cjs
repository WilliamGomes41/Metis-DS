const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const {writeFile} = require('node:fs/promises');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE, args:['--no-sandbox']});
  const page = await browser.newPage();
  const compositor = await page.context().newCDPSession(page);
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
    if (width === 390) {
      await page.setViewportSize({width:320,height:844});
      const textZoom = await page.addStyleTag({content:
        '.ko-submit-feedback, .ko-actions > .ko-submit-status { font-size: 28px !important; }'});
      await form.locator('[value=later]').scrollIntoViewIfNeeded();
      try {
        for (const action of ['approve', 'later']) {
          const geometry = await form.evaluate((node, action) => {
            const status = node.querySelector('[data-ko-submit-status]');
            const buttons = [...node.querySelectorAll('.ko-actions button')];
            const positions = () => buttons.map(button => button.getBoundingClientRect().top);
            const before = positions();
            node.dispatchEvent(new SubmitEvent('submit', {submitter:node.querySelector(`[value="${action}"]`)}));
            const text = document.createRange();
            text.selectNodeContents(status);
            return {message:status.textContent, lines:text.getClientRects().length,
              gap:Math.min(...positions()) - status.getBoundingClientRect().bottom,
              before, after:positions()};
          }, action);
          assert.equal(geometry.message, action === 'later'
            ? 'Volgende passage wordt geopend…' : 'Review wordt opgeslagen…');
          assert.ok(geometry.gap >= 6, `Status overlaps controls at 200% text size: ${JSON.stringify(geometry)}`);
          assert.deepEqual(geometry.after, geometry.before, 'Controls stay in place at 200% text size');
          if (action === 'later') {
            assert.ok(geometry.lines > 1, 'The longer message must exercise wrapping');
            await page.screenshot({path:`${process.env.METIS_BROWSER_OUTPUT}/personal-pending-text-320.png`, fullPage:true});
          }
          await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted:true})));
        }
      } finally {
        await textZoom.evaluate(node => node.remove());
        await page.setViewportSize({width,height:1000});
      }
    }
    const approve = form.locator('[name=review_action][value=approve]');
    assert.equal(await form.locator('[name=object_id]').inputValue(),d.context);
    assert.deepEqual(await state(), before, 'Landing and detail navigation must not mutate domain work');
    assert.equal(await approve.isEnabled(),false);
    const invalidStatus = await form.evaluate(node => {
      node.requestSubmit(node.querySelector('[value=approve]'));
      return node.querySelector('[data-ko-submit-status]')?.textContent ?? '';
    });
    assert.equal(invalidStatus, '', 'An incomplete assessment never shows the saving status');
    for (const question of ['applicable','complete','placed_correctly']) {
      assert.equal(await form.locator(`[name=${question}]:checked`).count(),0);
      await form.locator(`[name=${question}][value=yes]`).check();
    }
    await form.locator('[name=evidence_not_applicable]').check();
    assert.equal(await approve.isEnabled(),true,'The displayed fixture proposal must be confirmable');
    const interaction = await form.locator('[name=interaction_id]').inputValue();
    const postBodies = [];
    const isReviewPost = request => request.method() === 'POST' && request.url() === base + '/review';
    const recordSave = request => {
      if (isReviewPost(request)) {
        postBodies.push(new URLSearchParams(request.postData()));
      }
    };
    const setPaused = async paused => {
      assert.ok((await page.request.post(base + '/browser-review-gate?paused=' + paused)).ok());
    };
    await setPaused(true);
    page.on('request', recordSave);
    try {
      await approve.focus();
      const box = await approve.boundingBox();
      const readPending = page.waitForEvent('console', message => message.text().startsWith('review-pending '));
      await form.evaluate(node => {
        node.addEventListener('submit', event => {
          const button = event.submitter;
          const status = node.querySelector('[data-ko-submit-status]');
          const {x,y,width,height} = button.getBoundingClientRect();
          const details = {
            text: status?.textContent,
            role: status?.getAttribute('role'),
            disabled: button.getAttribute('aria-disabled'),
            box: {x,y,width,height},
            statusAboveButton: !!status && status.getBoundingClientRect().bottom + 6 <= y,
            receipt: !!document.querySelector('[data-review-receipt]'),
            repeats: [],
          };
          setTimeout(() => {
            const record = repeat => details.repeats.push(repeat.defaultPrevented);
            node.addEventListener('submit', record);
            button.click();
            node.requestSubmit(button);
            node.removeEventListener('submit', record);
            console.log('review-pending ' + JSON.stringify(details));
          });
        }, {once:true});
      });
      const firstPost = page.waitForRequest(isReviewPost);
      if (width === 1440) await page.keyboard.press('Enter');
      else await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await firstPost;
      const pending = JSON.parse((await readPending).text().slice('review-pending '.length));
      assert.deepEqual(pending, {text:'Review wordt opgeslagen…', role:'status', disabled:'true',
        box, statusAboveButton:true, receipt:false, repeats:[true,true]});
      assert.deepEqual(await state(), before, 'Pending copy appears before the server writes');
      const {data} = await compositor.send('Page.captureScreenshot',{format:'png'});
      await writeFile(`${process.env.METIS_BROWSER_OUTPUT}/personal-saving-${width}.png`, Buffer.from(data,'base64'));
    } finally {
      await setPaused(false);
    }
    await page.waitForURL(url => url.searchParams.get('receipt_interaction') === interaction,
      {waitUntil:'domcontentloaded'});
    page.off('request', recordSave);
    assert.equal(postBodies.length,1);
    assert.equal(postBodies[0].get('review_action'),'approve');
    assert.equal(postBodies[0].get('interaction_id'),interaction);
    assert.equal(await page.locator('[data-review-receipt]').count(),1);
    assert.equal(await page.locator('[data-ko-assessment-form]').count(),0);
    assert.equal(await page.locator('[data-saved-answer][data-answer=yes]').count(),3);
    assert.equal(await page.evaluate(() => document.activeElement.textContent), 'Review opgeslagen');
    await proof('personal-saved-receipt',width);
    const after = await state();
    const decisions = after.events.filter(event => event.object_id === d.context &&
      event.event_type.endsWith('_review_approve') &&
      event.details?.review_interaction?.interaction_id === interaction);
    assert.equal(decisions.length,1,'One real review decision is committed');
    await page.reload();
    assert.deepEqual(await state(),after,'Refreshing the receipt must not repeat review');
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

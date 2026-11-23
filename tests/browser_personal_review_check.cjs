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
  async function checkWorkboardLayout(width) {
    const filter = page.locator('form.review-filters');
    const group = page.locator('[data-personal-group="review"]');
    const firstAction = group.locator('[data-personal-review-action]').first();
    const layout = await page.evaluate(() => ({
      viewport: innerHeight,
      scroll: scrollY,
      firstActionBottom: document.querySelector('[data-personal-review-action]').getBoundingClientRect().bottom,
    }));
    await writeFile(`${process.env.METIS_BROWSER_OUTPUT}/personal-layout-${width}.json`, JSON.stringify(layout));
    assert.equal(await filter.count(), 1, 'one shared filter form');
    if (width === 1440) {
      assert.ok((await filter.boundingBox()).y < (await group.boundingBox()).y, 'filters precede cards on desktop');
      assert.equal(new Set(await filter.locator('select, input, button').evaluateAll(
        fields => fields.map(field => Math.round(field.getBoundingClientRect().bottom)))).size, 1,
      'desktop filter controls share a row');
      return;
    }
    assert.equal(layout.scroll, 0);
    assert.ok(layout.firstActionBottom <= layout.viewport,
      `The first review action is below the viewport: ${JSON.stringify(layout)}`);
    assert.ok(await firstAction.isVisible());
    assert.ok((await group.boundingBox()).y < (await filter.boundingBox()).y, 'open work precedes filters on mobile');
    const edit = page.getByRole('link', {name: 'Filters wijzigen', exact: true});
    await edit.focus();
    await page.keyboard.press('Enter');
    assert.ok(await filter.evaluate(form => form === document.activeElement), 'filter link focuses the form');
    await filter.locator('[name=theme]').selectOption('personal');
    const query = filter.locator('[name=q]');
    await query.fill('Gemengd2');
    await Promise.all([
      page.waitForURL(url => url.searchParams.get('q') === 'Gemengd2'),
      filter.getByRole('button', {name:'Filteren', exact:true}).click(),
    ]);
    const active = edit.locator('..');
    assert.match(await active.innerText(), /Thema: personal/);
    assert.match(await active.innerText(), /Zoekterm: Gemengd2/);
    assert.equal(await page.locator('[data-workboard-document]').count(), 1);
    assert.equal(await query.inputValue(), 'Gemengd2');
    assert.equal(await filter.locator('[name=theme]').inputValue(), 'personal');
    await proof('personal-filtered',width);

    await query.focus();
    await query.fill('geen-passend-reviewdocument');
    await page.setViewportSize({width:1440,height:1000});
    await page.waitForFunction(() => !document.querySelector('#review-filters-link').getClientRects().length);
    assert.equal(await query.inputValue(), 'geen-passend-reviewdocument');
    assert.ok(await query.evaluate(input => input === document.activeElement), 'resize keeps the focused filter field');
    await page.setViewportSize({width,height:844});
    await edit.waitFor();
    await Promise.all([
      page.waitForURL(url => url.searchParams.get('q') === 'geen-passend-reviewdocument'),
      filter.getByRole('button', {name:'Filteren', exact:true}).click(),
    ]);
    assert.equal(await page.locator('[data-personal-empty]').innerText(), 'Geen documenten gevonden.');
    assert.equal(await edit.isVisible(), true);
    await page.goto(base + '/review');

    const fallback = await browser.newContext({
      javaScriptEnabled: false, viewport: {width, height: 844}, storageState: await page.context().storageState(),
    });
    try {
      const noScript = await fallback.newPage();
      await noScript.goto(base + '/review');
      await noScript.getByRole('link', {name: 'Filters wijzigen'}).press('Enter');
      assert.ok(await noScript.getByRole('form', {name: 'Reviewfilters'}).evaluate(form => form === document.activeElement));
    } finally {
      await fallback.close();
    }
  }
  for (const [index,width] of [1440,390].entries()) {
    await page.setViewportSize({width,height:width === 390 ? 844 : 1000});
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
    await checkWorkboardLayout(width);
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
      await page.reload();
      const skip = page.getByRole('link', {name:'Naar hoofdinhoud', exact:true});
      await page.keyboard.press('Tab');
      assert.ok(await skip.evaluate(link => link === document.activeElement), 'first Tab skips the Review navigation');
      await page.keyboard.press('Enter');
      const main = page.getByRole('main');
      assert.equal(await main.count(), 1);
      assert.ok(await main.evaluate(node => node === document.activeElement));
      const menu = page.getByRole('button', {name:'Menu Review'});
      await menu.click();
      assert.equal(await menu.getAttribute('aria-expanded'), 'true');
      assert.equal(await page.locator('header').getByRole('link', {name:'Instellingen', exact:true}).isVisible(), true);
      await page.keyboard.press('Escape');
      assert.equal(await menu.getAttribute('aria-expanded'), 'false');
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
    // Chromium can apply autofocus after DOMContentLoaded.
    await page.locator('[data-review-receipt] h1:focus', {hasText: /^Review opgeslagen$/})
      .waitFor({state:'visible', timeout:5000});
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

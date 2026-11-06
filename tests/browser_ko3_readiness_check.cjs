// release-control-evidence: scope/belofte opslag slop releasebewijs
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const out = process.env.METIS_BROWSER_OUTPUT;
  const phase = process.env.METIS_KO3_BROWSER_PHASE;
  const expectRows = process.env.METIS_KO3_EXPECT_OBJECT_ROWS !== '0';
  const manifest = await (await fetch(base + '/browser-manifest')).json();
  const proof = async slug => (await (await fetch(base + '/browser-proof/' + slug)).json());
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE,
    args: ['--no-sandbox']});
  const publisher = await browser.newContext({viewport: {width: 1440, height: 1000},
    ...(phase === 'after' && process.env.METIS_KO3_VIDEO === '1'
      ? {recordVideo: {dir: path.join(out, 'video'), size: {width: 1440, height: 1000}}} : {})});
  const page = await publisher.newPage();
  async function login(target, person) {
    await target.goto(base + '/login');
    await target.locator('[name=username]').fill(manifest.people[person].username);
    await target.locator('[name=password]').fill(manifest.password);
    await Promise.all([target.waitForURL(url => url.pathname !== '/login'),
      target.locator('button[type=submit]').click()]);
  }
  const card = slug => `[data-publish-document="${manifest.documents[slug].snapshot_id}"]`;
  const open = async slug => {
    await page.goto(base + '/publish?document=' + manifest.documents[slug].snapshot_id);
    await page.locator(card(slug)).scrollIntoViewIfNeeded();
  };
  const shoot = async name => {
    const scroll = await page.evaluate(() => ({x: scrollX, y: scrollY}));
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({path: path.join(out, `ko3-${name}.png`), fullPage: true});
    await page.evaluate(({x, y}) => scrollTo(x, y), scroll);
  };
  const stable = (before, after) => {
    assert.deepEqual(after.workflow_digest, before.workflow_digest, 'no workflow mutation');
    assert.deepEqual(after.canonical_digest, before.canonical_digest, 'no canonical mutation');
    assert.equal(after.source_sha256, before.source_sha256, 'immutable source identity');
  };
  const hold = async () => {
    if (process.env.METIS_KO3_VIDEO === '1') await page.waitForTimeout(8000);
  };
  await login(page, 'publisher');
  if (phase === 'before') {
    const observations = {};
    for (const slug of ['main', 'second', 'source', 'conflict']) {
      const before = await proof(slug);
      assert.deepEqual(before.blockers, manifest.documents[slug].expected_blockers);
      await open(slug);
      assert.equal(await page.locator('[data-publish-document]').first().getAttribute('data-publish-document'),
        manifest.documents[slug].snapshot_id, 'selected document comes first');
      const others = page.locator('.publication-other-documents');
      assert.equal(await others.getAttribute('open'), null, 'other documents start collapsed');
      await others.locator('summary').focus();
      await page.keyboard.press('Enter');
      assert.notEqual(await others.getAttribute('open'), null, 'other documents remain keyboard accessible');
      await page.keyboard.press('Enter');
      assert.equal(await page.locator(card(slug) + ' [data-publication-state=blocked]').count(), 1);
      assert.equal(await page.locator(card(slug) + ' [data-publish-form]').count(), 0);
      for (const code of before.curation_blockers)
        assert.ok(await page.locator(card(slug) + ` [data-blocker-code="${code}"]`).count());
      if (expectRows) {
        assert.ok(await page.locator(card(slug) + ' [data-readiness-object]').count());
        assert.equal(await page.locator(card(slug) + ' [data-object-readiness] h3').count(), 1);
        const recovery = page.locator(card(slug) + ' [data-object-readiness] a').first();
        if (await recovery.count()) {
          assert.ok((await recovery.innerText()).trim(), 'recovery link has an accessible name');
          await recovery.focus();
          await page.keyboard.press('Shift+Tab');
          await page.keyboard.press('Tab');
          assert.equal(await recovery.evaluate(link => link === document.activeElement), true,
            'recovery link is reachable in the native keyboard sequence');
        }
        if (slug === 'second')
          assert.ok(await page.locator(card(slug) + ' [data-ko-state="Tweede review"]').count());
        if (slug === 'source')
          assert.ok(await page.locator(card(slug) + ' [data-readiness-object]').filter({hasText: 'Leg de gemaakte afspraak'}).count());
        if (slug === 'conflict')
          assert.equal(await page.locator(card(slug) + ` [data-readiness-object="${manifest.documents[slug].conflict_object_id}"]`).count(), 1);
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await shoot(slug === 'main' ? 'regression' : slug === 'second' ? 'second-open' : slug === 'source' ? 'passage-open' : 'conflict');
      stable(before, await proof(slug));
      const refused = await page.evaluate(async sid => {
        const response = await fetch('/publish', {method: 'POST', credentials: 'same-origin',
          body: new URLSearchParams({snapshot_id: sid, publish_confirmed: 'yes'})});
        return {status: response.status, text: await response.text()};
      }, manifest.documents[slug].snapshot_id);
      assert.equal(refused.status, 400, 'actual publication gate refuses');
      const after = await proof(slug);
      stable(before, after);
      assert.equal(after.refusal_count, 1);
      observations[slug] = after;
    }
    await page.goto(base + '/publish');
    await shoot('badges');
    assert.equal(observations.main.publisher_badge, 4, 'publisher work counts four documents');
    assert.equal(observations.main.publishable_object_count, 1, 'one approved KO is not the document-work count');
    await page.setViewportSize({width: 375, height: 900});
    await open('source');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await shoot('mobile');
    for (const width of [768, 1024]) {
      await page.setViewportSize({width, height: 1000});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await shoot('width-' + width);
    }
    fs.writeFileSync(path.join(out, 'before-restart.json'), JSON.stringify(observations, null, 2));
  } else {
    const beforeRestart = JSON.parse(fs.readFileSync(path.join(out, 'before-restart.json')));
    for (const slug of Object.keys(beforeRestart)) {
      const restarted = await proof(slug);
      assert.deepEqual(restarted.blockers, beforeRestart[slug].blockers);
      assert.equal(restarted.refusal_count, 1);
      stable(beforeRestart[slug], restarted);
    }
    await open('main');
    await shoot('restart');
    await hold();
    const reviewerContext = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const reviewer = await reviewerContext.newPage();
    await login(reviewer, 'reviewer');
    const main = manifest.documents.main;
    await reviewer.goto(base + '/review?document=' + main.snapshot_id + '&object=' + main.pending_object_id);
    const form = reviewer.locator('[data-ko-assessment-form][action="/review"]');
    for (const question of ['applicable', 'complete', 'placed_correctly']) {
      await form.locator(`[name="${question}"][value="yes"]`).check();
    }
    const [reviewResponse] = await Promise.all([reviewer.waitForNavigation(),
      form.locator('[name=review_action][value=approve]').click()]);
    assert.ok(reviewResponse.status() < 400, await reviewer.content());
    await reviewerContext.close();
    await open('main');
    const ready = await proof('main');
    fs.writeFileSync(path.join(out, 'ready-proof.json'), JSON.stringify(ready, null, 2));
    assert.equal(ready.publication_ready, true);
    assert.deepEqual(ready.blockers, []);
    assert.equal(ready.publisher_badge, 4, 'ready remains publisher work until publishing');
    assert.equal(await page.locator(card('main') + ' [data-publication-state=ready]').count(), 1);
    if (expectRows) assert.match(await page.locator(card('main')).innerText(), /Klaar om te publiceren/);
    await shoot('ready');
    await hold();
    const publishForm = page.locator(card('main') + ' [data-publish-form]');
    await publishForm.locator('[name=publish_confirmed]').check();
    const [publishResponse] = await Promise.all([page.waitForNavigation(), publishForm.getByRole('button', {name: 'Publiceer document', exact: true}).click()]);
    assert.ok(publishResponse.status() < 400, JSON.stringify(ready.prospective_projection_errors));
    await open('main');
    assert.equal(await page.locator(card('main') + ' [data-publication-state=published]').count(), 1);
    const published = await proof('main');
    assert.equal(published.projection.length, 2);
    assert.ok(published.projection.every(row => row.type === 'definition'));
    assert.ok(published.projection.every(row => row.source_locator?.locator_value),
      'published source location survives projection');
    assert.equal(published.publisher_badge, 3);
    assert.ok(Object.values(published.states).filter(row => row.state !== null).every(row => row.state === 'Gepubliceerd'));
    await shoot('published');
    await hold();
    const withdraw = page.locator(card('main') + ' [data-withdraw-form]');
    await withdraw.locator('[name=reason]').fill('Synthetische KO-3-proef: intrekking moet na herstart behouden blijven.');
    await withdraw.locator('[name=withdraw_confirmed]').check();
    await Promise.all([page.waitForNavigation(), withdraw.getByRole('button', {name: 'Trek publicatie in', exact: true}).click()]);
    await open('main');
    const withdrawn = await proof('main');
    assert.equal(withdrawn.projection.length, 0);
    assert.equal(await page.locator(card('main') + ' [data-publication-state=withdrawn]').count(), 1);
    assert.ok(Object.values(withdrawn.states).filter(row => row.state !== null).every(row => row.state === 'Ingetrokken'));
    assert.equal(withdrawn.source_sha256, main.source_sha256);
    await shoot('withdraw');
    await hold();
    await page.setViewportSize({width: 375, height: 900});
    await open('main');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await shoot('withdraw-mobile');
    fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify({refusal_survived_restart: true,
      source_sha: process.env.METIS_KO3_SOURCE_SHA,
      method: 'Local native Chromium DOM and HTTP commands; real PostgreSQL; actual process restart; deterministic model fixture; Azure adapter with disk network transport; no Azure account or remote VM',
      published_object_count: published.projection.length, withdrawn_projection_count: withdrawn.projection.length,
      published, withdrawn, expected_object_rows: expectRows}, null, 2));
  }
  await publisher.close();
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });

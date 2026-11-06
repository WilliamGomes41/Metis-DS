// release-control-evidence: scope/belofte opslag toegang slop releasebewijs
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const out = process.env.METIS_BROWSER_OUTPUT;
  const phase = process.env.METIS_KO4_BROWSER_PHASE;
  const manifest = await (await fetch(base + '/ko4-browser-manifest')).json();
  const proof = async slug => (await (await fetch(base + '/ko4-browser-proof/' + slug)).json());
  const browser = await chromium.launch({executablePath: process.env.METIS_BROWSER_EXECUTABLE,
    args: ['--no-sandbox']});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const page = await context.newPage();
  const card = target => base + '/review?' + new URLSearchParams({document: target.snapshot_id, object: target.object_id});
  const form = target => target.locator('[data-ko-assessment-form]');
  const current = (state, id) => state.objects.find(row => row.object_id === id);
  const unchanged = (before, after) => {
    assert.deepEqual(after.workflow_digest, before.workflow_digest, 'refusal/read preserves physical PG rows');
    assert.deepEqual(after.canonical_digest, before.canonical_digest, 'no canonical mutation');
    assert.deepEqual(after.immutable_files, before.immutable_files, 'immutable source bytes preserved');
  };
  const onlyWorkflowChanges = (before, after) => {
    assert.deepEqual(after.canonical_digest, before.canonical_digest, 'review does not publish');
    assert.deepEqual(after.immutable_files, before.immutable_files, 'review does not rewrite source');
    assert.ok(after.histories.every(row => row.governance.validation_status !== 'revise'), 'no stored revise');
  };
  async function login(target, person) {
    await target.goto(base + '/login');
    await target.locator('[name=username]').fill(manifest.people[person].username);
    await target.locator('[name=password]').fill(manifest.password);
    await Promise.all([target.waitForURL(url => url.pathname !== '/login'),
      target.locator('button[type=submit]').click()]);
  }
  async function answers(target, values = {}) {
    for (const name of ['applicable', 'complete', 'placed_correctly'])
      await form(target).locator(`[name=${name}][value=${values[name] || 'yes'}]`).check();
  }
  async function shoot(target, name) {
    await target.screenshot({path: path.join(out, 'ko4-' + name + '.png'), fullPage: true});
  }
  async function viewport(target, name) {
    await shoot(target, name);
    const geometry = await target.evaluate(() => ({width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      overflow: [...document.querySelectorAll('body *')].map(node => {
        const rect = node.getBoundingClientRect();
        return {tag: node.tagName, class: node.className, right: rect.right,
          width: rect.width, text: node.textContent.slice(0, 90)};
      }).filter(row => row.right > innerWidth + .5).slice(0, 20)}));
    if (geometry.scrollWidth > geometry.width)
      fs.writeFileSync(path.join(out, 'ko4-' + name + '-overflow.json'), JSON.stringify(geometry, null, 2));
    assert.equal(geometry.scrollWidth > geometry.width, false, 'no horizontal page overflow');
  }
  async function submit(target) {
    await Promise.all([target.waitForNavigation({waitUntil: 'domcontentloaded'}),
      form(target).locator('[name=review_action][value=approve]').click()]);
  }
  async function forceSubmittedAnswers(target, payload) {
    return target.evaluate(async overrides => {
      const form = document.querySelector('[data-ko-assessment-form]');
      const values = new URLSearchParams(new FormData(form));
      values.set('review_action', 'approve');
      for (const [name, value] of Object.entries(overrides || {})) values.set(name, value);
      const response = await fetch(form.action, {method: 'POST', credentials: 'same-origin', body: values});
      return {status: response.status, body: await response.text()};
    }, payload);
  }
  async function naReceipt(target) {
    assert.equal(await target.locator('[data-review-receipt]').count(), 1);
    const saved = target.locator('[data-saved-evidence-applicability="not_applicable"]');
    assert.equal(await saved.count(), 1);
    assert.match(await saved.innerText(), /Bij deze beoordeling expliciet niet van toepassing verklaard/);
  }
  await login(page, 'reviewer');
  if (phase === 'after') {
    const previous = JSON.parse(fs.readFileSync(path.join(out, 'ko4-before-restart.json')));
    for (const slug of Object.keys(manifest.documents)) {
      const after = await proof(slug);
      unchanged(previous.states[slug], after);
      assert.deepEqual(after.objects, previous.states[slug].objects, 'restart preserves current versions');
      assert.deepEqual(after.bindings, previous.states[slug].bindings, 'restart preserves exact decisions');
    }
    await page.goto(previous.oldReceipt);
    await naReceipt(page);
    await shoot(page, 'restart-old-receipt');
    fs.writeFileSync(path.join(out, 'ko4-result.json'), JSON.stringify({
      source_sha: process.env.METIS_KO4_SOURCE_SHA, restart_preserved: true,
      linked_approval: true, explicit_not_applicable: true, correction_reopens: true,
      same_person_no_additional_decision: true, same_person_http_status: previous.samePersonHTTPStatus, viewports: [375, 768, 1024, 1440],
      evidence: previous.evidence,
    }, null, 2));
    await browser.close();
    return;
  }

  const link = manifest.documents.link;
  const beforeLink = await proof('link');
  await page.goto(card(link));
  unchanged(beforeLink, await proof('link'));
  const missingAnswers = await forceSubmittedAnswers(page);
  assert.equal(missingAnswers.status, 400, 'missing assessment cannot approve');
  unchanged(beforeLink, await proof('link'));
  for (const [name, values] of [['one-adjust', {complete: 'adjust'}],
      ['all-adjust', {applicable: 'adjust', complete: 'adjust', placed_correctly: 'adjust'}]]) {
    await answers(page, values);
    assert.equal(await form(page).locator('[value=approve]').isEnabled(), false);
    const response = await forceSubmittedAnswers(page);
    assert.equal(response.status, 400);
    assert.match(response.body, /drie antwoorden Ja|review_assessment_requires_three_yes/);
    unchanged(beforeLink, await proof('link'));
    await shoot(page, name);
  }

  const videoEnabled = process.env.METIS_KO4_VIDEO === '1';
  const filmedContext = await browser.newContext({viewport: {width: 1440, height: 1000},
    storageState: await context.storageState(), ...(videoEnabled ?
      {recordVideo: {dir: path.join(out, 'video'), size: {width: 1440, height: 1000}}} : {})});
  const filmed = await filmedContext.newPage();
  const video = filmed.video();
  const hold = async () => {if (videoEnabled) await filmed.waitForTimeout(8000);};
  await filmed.goto(card(link));
  await answers(filmed);
  const approve = form(filmed).locator('[value=approve]');
  if (await approve.isEnabled()) {
    await submit(filmed);
    assert.match(await filmed.locator('body').innerText(), /nog geen onderbouwing|knowledge_evidence_required/);
  } else {
    const response = await forceSubmittedAnswers(filmed);
    assert.equal(response.status, 400);
    assert.match(response.body, /nog geen onderbouwing|knowledge_evidence_required/);
  }
  unchanged(beforeLink, await proof('link'));
  await shoot(filmed, 'evidence-open');
  await hold();

  await filmed.goto(card({...link, object_id: link.support_object_id}));
  await filmed.getByRole('link', {name: 'Correctie nodig', exact: true}).focus();
  await Promise.all([filmed.waitForURL(url => url.pathname === '/source-selection'),
    filmed.keyboard.press('Enter')]);
  await filmed.getByRole('link', {name: 'Onderbouwing verbinden', exact: true}).click();
  const repair = filmed.locator('form[action="/review/resolve"]');
  await repair.locator('[name=claim_object_id]').selectOption(link.object_id);
  await repair.locator('[name=comment]').fill('Deze bronpassage onderbouwt de geselecteerde observatie.');
  unchanged(beforeLink, await proof('link'));
  await shoot(filmed, 'link-support');
  await hold();
  await Promise.all([filmed.waitForNavigation({waitUntil: 'domcontentloaded'}),
    repair.locator('button[type=submit]').click()]);
  const linked = await proof('link');
  fs.writeFileSync(path.join(out, 'ko4-linked-state.json'), JSON.stringify(linked, null, 2));
  fs.writeFileSync(path.join(out, 'ko4-after-link.html'), await filmed.content());
  const claim = current(linked, link.object_id);
  const support = current(linked, link.support_object_id);
  const relation = claim.confirmed_knowledge_relations.find(row => row.relation_type === 'supported_by');
  const identity = {version: relation.version, source_object_id: claim.object_id,
    source_object_version: claim.object_version, relation_type: relation.relation_type,
    target_object_id: relation.target_object_id, target_object_version: relation.target_object_version};
  const canonicalIdentity = JSON.stringify(Object.fromEntries(Object.entries(identity).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)));
  assert.equal(relation.relation_id, 'rel-' + crypto.createHash('sha256').update(canonicalIdentity).digest('hex'));
  assert.equal(relation.target_object_id, support.object_id);
  assert.equal(relation.target_object_version, support.object_version);
  onlyWorkflowChanges(beforeLink, linked);
  await filmed.goto(card(link));
  await answers(filmed);
  await shoot(filmed, 'linked-card');
  await hold();
  await submit(filmed);
  assert.equal(await filmed.locator('[data-review-receipt]').count(), 1);
  assert.equal(await filmed.locator('[data-saved-answer][data-answer=yes]').count(), 3);
  const approvedLink = await proof('link');
  assert.ok(approvedLink.bindings.some(row => row.object_id === link.object_id && row.valid
    && row.supporting_evidence?.applicability === 'linked'));
  await shoot(filmed, 'linked-receipt');
  await hold();
  await filmedContext.close();
  if (videoEnabled) await video.saveAs(path.join(out, 'ko4-review.webm'));

  const longText = manifest.documents['long-text'];
  const beforeLongText = await proof('long-text');
  await page.goto(card(longText));
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({width, height: 1000});
    await viewport(page, 'long-card-' + width);
  }
  unchanged(beforeLongText, await proof('long-text'));
  await page.setViewportSize({width: 1440, height: 1000});

  const na = manifest.documents['not-applicable'];
  const beforeNA = await proof('not-applicable');
  await page.goto(card(na));
  await answers(page);
  const notApplicable = form(page).locator('[name=evidence_not_applicable]');
  assert.equal(await notApplicable.isChecked(), false, 'N/A is never preselected');
  assert.equal(await notApplicable.isVisible(), true, 'N/A remains visible after three yes answers');
  await page.locator('.ko-evidence > summary').focus();
  const keyboardTrace = [];
  for (let step = 0; step < 12; step++) {
    await page.keyboard.press('Tab');
    keyboardTrace.push(await page.evaluate(() => ({tag: document.activeElement.tagName,
      name: document.activeElement.getAttribute('name'), text: document.activeElement.textContent.slice(0, 80)})));
    if (await notApplicable.evaluate(input => input === document.activeElement)) break;
  }
  fs.writeFileSync(path.join(out, 'ko4-keyboard.json'), JSON.stringify(keyboardTrace, null, 2));
  assert.equal(await notApplicable.evaluate(input => input === document.activeElement), true, 'N/A is natively keyboard reachable');
  await page.keyboard.press('Space');
  assert.equal(await notApplicable.isChecked(), true);
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({width, height: 1000});
    await viewport(page, 'na-card-' + width);
  }
  await shoot(page, 'not-applicable-card');
  await submit(page);
  const oldReceipt = page.url();
  await naReceipt(page);
  const approvedNA = await proof('not-applicable');
  const naObject = current(approvedNA, na.object_id);
  assert.ok(approvedNA.bindings.some(row => row.object_id === na.object_id && row.valid
    && row.object_version === naObject.object_version
    && row.supporting_evidence?.applicability === 'not_applicable'));
  onlyWorkflowChanges(beforeNA, approvedNA);
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({width, height: 1000});
    await viewport(page, 'na-receipt-' + width);
  }
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto(card(na));
  await page.getByRole('link', {name: 'Correctie nodig', exact: true}).click();
  const sourceRepair = page.locator('form[action="/review/resolve"]');
  const unit = sourceRepair.locator('[name=source_unit_ids] option').filter({hasText: na.correction_text});
  assert.equal(await unit.count(), 1);
  await sourceRepair.locator('[name=source_unit_ids]').selectOption(await unit.getAttribute('value'));
  await sourceRepair.locator('[name=comment]').fill('Deze preciezere bronzin vormt het nieuwe voorstel.');
  await Promise.all([page.waitForNavigation({waitUntil: 'domcontentloaded'}),
    sourceRepair.locator('button[type=submit]').click()]);
  const corrected = await proof('not-applicable');
  const newObject = current(corrected, na.object_id);
  assert.notEqual(newObject.object_version, naObject.object_version);
  assert.equal(newObject.content.clean_text, na.correction_text);
  assert.equal(newObject.governance.validation_status, 'needs_review');
  assert.ok(!corrected.bindings.some(row => row.object_id === na.object_id && row.valid));
  onlyWorkflowChanges(approvedNA, corrected);
  await page.goto(card(na));
  assert.equal(await form(page).locator('[name=evidence_not_applicable]').isChecked(), false);
  await answers(page);
  const inherited = await forceSubmittedAnswers(page);
  assert.equal(inherited.status, 400, 'new version cannot inherit the old N/A decision');
  unchanged(corrected, await proof('not-applicable'));
  await shoot(page, 'correction-open');
  await page.goto(oldReceipt);
  await naReceipt(page);
  assert.match(await page.locator('body').innerText(), /inmiddels een nieuwere versie/);
  await shoot(page, 'old-receipt');

  const second = manifest.documents.second;
  const secondaryContext = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const secondary = await secondaryContext.newPage();
  await login(secondary, 'second');
  await secondary.goto(card(second));
  assert.equal(await form(secondary).getAttribute('action'), '/review/second-review');
  await answers(secondary);
  const beforeSecond = await proof('second');
  const missingNA = await forceSubmittedAnswers(secondary);
  assert.equal(missingNA.status, 400, 'second reviewer must make their own N/A choice');
  unchanged(beforeSecond, await proof('second'));
  const borrowed = await form(secondary).evaluate(node => Object.fromEntries(new FormData(node)));
  const samePerson = await page.evaluate(async payload => {
    const response = await fetch('/review/second-review', {method: 'POST', credentials: 'same-origin',
      body: new URLSearchParams({...payload, review_action: 'approve', evidence_not_applicable: 'yes'})});
    return {status: response.status, url: response.url, body: await response.text()};
  }, borrowed);
  unchanged(beforeSecond, await proof('second'));
  if (samePerson.status < 400)
    assert.ok(!samePerson.body.includes('<h1>Review opgeslagen</h1>'), 'a replay/no-op cannot invent a new saved second decision');
  await shoot(secondary, 'second-open');
  await form(secondary).locator('[name=evidence_not_applicable]').check();
  await submit(secondary);
  assert.equal(await secondary.locator('[data-review-receipt]').count(), 1);
  const afterSecond = await proof('second');
  assert.equal(current(afterSecond, second.object_id).object_version,
    current(beforeSecond, second.object_id).object_version);
  assert.equal(afterSecond.bindings.filter(row => row.valid && row.object_id === second.object_id).length, 2);
  onlyWorkflowChanges(beforeSecond, afterSecond);
  await shoot(secondary, 'second-receipt');
  await secondaryContext.close();
  const states = {};
  for (const slug of Object.keys(manifest.documents)) states[slug] = await proof(slug);
  fs.writeFileSync(path.join(out, 'ko4-before-restart.json'), JSON.stringify({states, oldReceipt,
    samePersonHTTPStatus: samePerson.status,
    evidence: ['missing/negative answers', 'missing evidence',
      'native support repair', 'exact linked approval', 'explicit N/A', 'new open correction',
      'old receipt stability', 'independent second approval', 'immutable source/canonical state']}, null, 2));
  await browser.close();
})().catch(error => {console.error(error); process.exit(1);});

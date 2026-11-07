const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async () => {
  const base = process.env.METIS_BROWSER_BASE;
  const m = await (await fetch(base + '/browser-manifest')).json();
  const browser = await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE, args:['--no-sandbox']});
  const page = await browser.newPage();
  const state = async () => (await page.request.get(base + '/browser-content-state')).json();
  async function login(username) {
    await page.goto(base+'/login');
    await page.locator('[name=username]').fill(username);
    await page.locator('[name=password]').fill(m.password);
    await Promise.all([page.waitForURL(u=>u.pathname!='/login'),page.locator('button[type=submit]').click()]);
  }
  async function proof(stage,width) {
    assert.equal(await page.locator('form form').count(),0);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,stage);
    await page.screenshot({path:`${process.env.METIS_BROWSER_OUTPUT}/${stage}-${width}.png`,fullPage:true});
  }
  for (const [index,width] of [1440,390].entries()) {
    const d=m.documents[index];
    await page.setViewportSize({width,height:1000});
    await login(m.username);
    const before=await state();
    await page.goto(base+'/review?'+new URLSearchParams({document:d.snapshot_id,task:'contextual'}));
    assert.equal(await page.locator('[data-content-review-workplace]').count(),1);
    assert.equal(await page.evaluate(()=>window.MetisPageReadiness('/review').verdict),'pass');
    const batch=page.locator('form[action="/review/normal-risk/batch-confirm"]');
    assert.equal(await batch.count(),1);
    assert.equal(await batch.locator('[name=object_ids]:checked').count(),0);
    assert.equal(await page.locator('[data-review-task-dashboard]').count(),0);
    await proof('content-workplace',width);
    // The existing explicit group selection sends one existing command.
    await batch.locator('[name=object_ids]').first().check();
    await batch.locator('[name=object_ids]').nth(1).check();
    for (const question of ['applicable','complete','placed_correctly']) {
      await batch.locator(`[name=${question}][value=yes]`).check();
    }
    await batch.locator('[name=evidence_not_applicable]').check();
    assert.deepEqual(await state(),before,'GET and selection cannot write');
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),batch.locator('button[type=submit]').click()]);
    const committed=await state();
    for(const oid of d.batch) assert.ok(committed.bindings.flat().some(r=>r.object_id===oid && r.valid && r.decision==='approve'));
    await page.goto(base+'/review?'+new URLSearchParams({document:d.snapshot_id,object:d.context,task:'contextual'}));
    const review=page.locator('[data-ko-assessment-form]');
    assert.equal(await review.locator('[name=object_id]').inputValue(),d.context);
    // Carry the pinned review revision to the sole owner and back; no mutation.
    const repair=page.getByRole('link',{name:'Correctie nodig',exact:true});
    const origin=new URL(await repair.getAttribute('href'),base).searchParams.get('review_revision');
    assert.ok(origin);
    await repair.focus();
    await Promise.all([page.waitForURL(u=>u.pathname==='/source-selection'),page.keyboard.press('Enter')]);
    const back=page.getByRole('link',{name:'Deze passage beoordelen in Review',exact:true});
    assert.equal(new URL(await back.getAttribute('href'),base).searchParams.get('review_revision'),origin);
    await back.click();
    assert.equal(new URL(page.url()).searchParams.get('object'),d.context);
    assert.deepEqual(await state(),committed,'Owner/return does not mutate or transfer approval');
    for (const question of ['applicable','complete','placed_correctly']) {
      assert.equal(await review.locator(`[name=${question}]:checked`).count(),0);
      await review.locator(`[name=${question}][value=yes]`).check();
    }
    await review.locator('[name=evidence_not_applicable]').check();
    const approve=review.locator('[name=review_action][value=approve]');
    assert.equal(await approve.isEnabled(),true,'The displayed fixture proposal must be confirmable');
    await proof('content-individual',width);
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),approve.click()]);
    assert.equal(await page.locator('[data-review-receipt]').count(),1);
    assert.equal(await page.locator('[data-ko-assessment-form]').count(),0);
    assert.equal(await page.locator('[data-saved-answer][data-answer=yes]').count(),3);
    await page.goto(base+'/logout'); await login(m.other);
    await page.goto(base+'/review?'+new URLSearchParams({document:d.second_snapshot,task:'second_review'}));
    assert.equal(await page.locator('form[action="/review/normal-risk/batch-confirm"]').count(),0);
    await page.locator(`a[href*="object=${d.second}"]`).first().click();
    await proof('content-second',width);
    const second=page.locator('[data-ko-assessment-form][action="/review/second-review"]');
    const beforeSecond=await state();
    const original=beforeSecond.objects.flat().find(row=>row.object_id===d.second);
    assert.ok(original);
    for (const question of ['applicable','complete','placed_correctly']) {
      assert.equal(await second.locator(`[name=${question}]:checked`).count(),0);
      await second.locator(`[name=${question}][value=yes]`).check();
    }
    await second.locator('[name=evidence_not_applicable]').check();
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),second.locator('[name=review_action][value=approve]').click()]);
    assert.equal(await page.locator('[data-review-receipt]').count(),1);
    assert.equal(await page.locator('[data-saved-answer][data-answer=yes]').count(),3);
    const after=await state();
    assert.ok(after.bindings.flat().some(r=>r.object_id===d.second && r.valid && r.decision==='approve'));
    const current=after.objects.flat().find(row=>row.object_id===d.second);
    assert.equal(current.object_version,original.object_version,'Second review must preserve the reviewed version');
    assert.equal(current.provenance.canonical_object_hash,original.provenance.canonical_object_hash,
      'Second review must preserve the canonical object tuple');
    await page.reload(); assert.deepEqual(await state(),after);
    await page.goto(base+'/logout');
    console.log('Unified first/batch/independent second/owner return',width,'PASSED');
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});

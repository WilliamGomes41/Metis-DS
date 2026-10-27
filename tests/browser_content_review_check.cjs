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
    assert.deepEqual(await state(),before,'GET and selection cannot write');
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),batch.locator('button[type=submit]').click()]);
    const committed=await state();
    for(const oid of d.batch) assert.ok(committed.bindings.flat().some(r=>r.object_id===oid && r.valid && r.decision==='approve'));
    await page.goto(base+'/review?'+new URLSearchParams({document:d.snapshot_id,object:d.context,task:'contextual'}));
    const review=page.locator('[data-review-form]');
    assert.equal(await review.locator('[name=object_id]').inputValue(),d.context);
    // Carry the pinned review revision to the sole owner and back; no mutation.
    const repair=page.getByRole('link',{name:'Passage herstellen in Vorming',exact:true});
    const origin=new URL(await repair.getAttribute('href'),base).searchParams.get('review_revision');
    assert.ok(origin);
    await repair.focus();
    await Promise.all([page.waitForURL(u=>u.pathname==='/source-selection'),page.keyboard.press('Enter')]);
    const back=page.getByRole('link',{name:'Deze passage beoordelen in Review',exact:true});
    assert.equal(new URL(await back.getAttribute('href'),base).searchParams.get('review_revision'),origin);
    await back.click();
    assert.equal(new URL(page.url()).searchParams.get('object'),d.context);
    assert.deepEqual(await state(),committed,'Owner/return does not mutate or transfer approval');
    await review.locator('[name=suitability][value=ja]').check();
    await review.locator('[name=documentpositie_action][value=dit_klopt]').check();
    await review.locator('[name=type_action][value=dit_klopt]').check();
    await review.locator('[name=recommendation_direction][value=for]').check();
    await review.locator('[name=recommendation_strength_level][value=not_stated]').check();
    await review.locator('[name=eindoordeel][value=goedkeuren]').check();
    if(await review.locator('[name=relation_review_ack]').count()) await review.locator('[name=relation_review_ack]').check();
    await proof('content-individual',width);
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),review.locator('[data-submit-review]').click()]);
    await page.goto(base+'/logout'); await login(m.other);
    await page.goto(base+'/review?'+new URLSearchParams({document:d.second_snapshot,task:'second_review'}));
    assert.equal(await page.locator('form[action="/review/normal-risk/batch-confirm"]').count(),0);
    await page.locator(`a[href*="object=${d.second}"]`).first().click();
    await proof('content-second',width);
    const second=page.locator('form[action="/review/second-review"]');
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),second.locator('[name=action][value=approve]').click()]);
    const after=await state();
    assert.ok(after.bindings.flat().some(r=>r.object_id===d.second && r.valid && r.decision==='approve'));
    await page.reload(); assert.deepEqual(await state(),after);
    await page.goto(base+'/logout');
    console.log('Unified first/batch/independent second/owner return',width,'PASSED');
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});

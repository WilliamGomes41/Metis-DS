const assert = require('node:assert/strict');
const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const {withBrowserEvidence} = require('./browser_evidence.cjs');
const {selectText} = require('./browser_annotation_tasks.cjs');

(async () => {
  const base = process.env.METIS_BROWSER_BASE, output = process.env.METIS_BROWSER_OUTPUT;
  const fixture = await (await fetch(base+'/browser-manifest')).json();
  await withBrowserEvidence(chromium, {base, output, label:'strength-label',
    launchOptions:{executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true}}, async ({newContext}) => {
    const context = await newContext({viewport:{width:1440,height:1000}},true);
    const page = await context.newPage();
    await page.goto(base+'/login');
    await page.locator('[name=username]').fill(fixture.username);
    await page.locator('[name=password]').fill(fixture.password);
    await Promise.all([page.waitForURL(url=>url.pathname!='/login'),page.locator('button[type=submit]').click()]);
    await page.goto(base+'/annotations?'+new URLSearchParams({document:fixture.snapshot,annotation:fixture.annotation}));
    await page.locator('#annotation-editor-inputs:enabled').waitFor();

    const block = page.locator('[data-source-block]').filter({hasText:fixture.label});
    const button = page.locator('#annotation-selection-menu').getByRole('button',{name:'Sterktelabel',exact:true});
    const row = page.locator('#annotation-simple-rows dd[data-row=strength_label]');
    await selectText(page,block,fixture.label);
    await button.waitFor();
    await page.screenshot({path:output+'/annotation-strength-label-desktop.png'});

    await page.setViewportSize({width:390,height:844});
    await selectText(page,block,fixture.label.slice(0,-1));
    await selectText(page,block,fixture.label);
    await button.scrollIntoViewIfNeeded();
    assert(await page.evaluate(()=>{
      const menu=document.querySelector('#annotation-selection-menu').getBoundingClientRect();
      const source=document.querySelector('.annotation-document').getBoundingClientRect();
      return menu.left>=source.left && menu.right<=source.right && document.documentElement.scrollWidth<=innerWidth;
    }));
    await page.screenshot({path:output+'/annotation-strength-label-mobile.png'});
    await button.click();
    const quote = row.getByText(fixture.label,{exact:true});
    await quote.waitFor();
    const stored = ({snapshot,annotation,label})=>fetch('/annotations/api?document='+snapshot)
      .then(response=>response.json())
      .then(result=>result.entries.find(entry=>entry.annotation_id===annotation)?.recommendation_strength_label?.quote===label);
    await page.waitForFunction(stored,fixture);
    await page.reload();
    await quote.waitFor();
    await row.getByRole('button',{name:'Sterktelabel weghalen'}).click();
    await quote.waitFor({state:'detached'});
    await page.waitForFunction(async fixture=>{
      const response=await fetch('/annotations/api?document='+fixture.snapshot);
      const entry=(await response.json()).entries.find(row=>row.annotation_id===fixture.annotation);
      return entry && !entry.recommendation_strength_label;
    },fixture);
  });
})().catch(error=>{console.error(error);process.exit(1);});

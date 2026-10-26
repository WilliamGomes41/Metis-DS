const {chromium} = require(process.env.METIS_PLAYWRIGHT_MODULE);
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.METIS_BROWSER_EXECUTABLE});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const base = process.env.METIS_BROWSER_BASE;
  const output = process.env.METIS_BROWSER_OUTPUT;
  const manifest = await (await page.request.get(base+'/browser-manifest')).json();
  await page.goto(base+'/login');
  await page.locator('[name=username]').fill('author');
  await page.locator('[name=password]').fill('fixture-only');
  await Promise.all([page.waitForURL(base+'/'), page.locator('button[type=submit]').click()]);
  const expected = ['Inleveren','Bronselectie','Review','Publicatie','Documenten'];
  const titles = await page.locator('.home-tile-title').allTextContents();
  if (JSON.stringify(titles)!==JSON.stringify(expected)) throw Error('workflow order '+JSON.stringify(titles));
  await page.screenshot({path:output+'/home.png',fullPage:true});
  await page.goto(base+'/ingest');
  await page.locator('[name=file]').setInputFiles({name:'fixture.html',mimeType:'text/html',
    buffer:Buffer.from('<html><body><p>Gebruik geen zalf.</p></body></html>')});
  await page.locator('[name=title]').fill('Source browser proof');
  await page.locator('[name=version]').fill('1');
  await page.locator('[name=date]').fill('2026-10-09');
  await page.locator('[name=family]').fill('fixture');
  await page.locator('[name=review_option][value=one_other]').check();
  await page.locator('[name=review_reviewers]').selectOption(manifest.reviewer);
  await Promise.all([page.waitForURL('**/source-selection?**'), page.locator('#ingest-submit').click()]);
  const sid = new URL(page.url()).searchParams.get('document');
  if (await page.locator('select[name=document]').inputValue()!==sid) throw Error('selected document');
  await page.getByRole('button',{name:'Starten',exact:true}).waitFor();
  if (!(await page.locator('[role=status]').allTextContents()).some(t=>t.includes('nog niet gestart'))) throw Error('receipt auto-started');
  await page.screenshot({path:output+'/received.png',fullPage:true});
  await page.getByRole('link',{name:'Bekijk diagnose in Inzicht',exact:true}).click();
  await page.getByRole('heading',{name:'Oordeel',exact:true}).waitFor();
  const diagnosisURL = new URL(page.url());
  if (diagnosisURL.pathname!=='/inzicht/document' || diagnosisURL.searchParams.get('document')!==sid)
    throw Error('diagnosis lost selected source '+page.url());
  await page.locator('.diagnosis-verdict[role=status]').waitFor();
  if ((await page.locator('.diagnosis-facts dd').last().innerText()).trim()!=='0')
    throw Error('diagnosis started processing the received source');
  await page.getByRole('link',{name:'Blokkade en bewijs per verwerkingspoging onderzoeken',exact:true}).click();
  await page.getByRole('heading',{name:'Blokkade en bewijs',exact:true}).waitFor();
  // Use the browser's authenticated fetch: its localhost Secure-cookie handling
  // differs from Playwright's standalone APIRequestContext over plain HTTP.
  const diagnostic = await page.evaluate(async sid => {
    const response = await fetch('/inzicht/document/blokkade?document='+encodeURIComponent(sid)+'&download=1');
    if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) {
      throw Error('diagnostic download did not return authenticated JSON: '+response.status+' '+new URL(response.url).pathname);
    }
    return response.json();
  }, sid);
  if (diagnostic.schema!=='blockage-report-v1' || diagnostic.context.snapshot_id!==sid || diagnostic.attempts.length!==0) throw Error('diagnostic changed or lost the received document');
  if (diagnostic.follow_up.some(a=>a.observed_conditions_met!==null || a.execution_authorized)) throw Error('unchecked diagnostic authorized work');
  await page.setViewportSize({width:390,height:844});
  await page.locator('details').last().evaluate(e=>{e.open=true;});
  if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw Error('blockage mobile overflow');
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(base+'/source-selection?document='+sid);
  await page.reload();
  await page.getByRole('button',{name:'Starten',exact:true}).click();
  await page.waitForURL('**/source-selection?**');
  await page.getByRole('link',{name:'Naar Review',exact:true}).waitFor({timeout:15000});
  await page.screenshot({path:output+'/formed.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw Error('mobile overflow');
  await page.screenshot({path:output+'/mobile.png',fullPage:true});
  await page.getByRole('link',{name:'Naar Review',exact:true}).click();
  await page.waitForURL(url => url.pathname === '/review' || url.pathname === '/review/trajectory');
  const reviewURL = new URL(page.url());
  if (reviewURL.searchParams.get('document')!==sid) throw Error('review lost selected source '+page.url());
  console.log('BROWSER_REVIEW_URL='+page.url());
  if (reviewURL.pathname !== '/review/trajectory') throw Error('unassigned uploader bypassed review assignment');
  await page.getByRole('button',{name:'Uitloggen',exact:true}).click();
  await page.goto(base+'/login');
  await page.locator('[name=username]').fill('reviewer');
  await page.locator('[name=password]').fill('fixture-only');
  await Promise.all([page.waitForURL(base+'/'), page.locator('button[type=submit]').click()]);
  await page.goto(base+'/source-selection?document='+sid);
  await page.getByRole('link',{name:'Naar Review',exact:true}).click();
  await page.waitForURL(url => url.pathname === '/review' && url.searchParams.get('document')===sid);
  await page.getByRole('heading',{name:'Review',exact:true}).waitFor();
  await page.screenshot({path:output+'/review.png',fullPage:true});
  await page.goto(base+'/inzicht/document?document='+encodeURIComponent(sid));
  await page.getByRole('heading',{name:'Oordeel',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Wat Metis met dit document deed',exact:true}).waitFor();
  const technical = page.locator('.diagnosis-verdict details');
  await technical.locator('summary').focus();
  await page.keyboard.press('Enter');
  if (!await technical.evaluate(node=>node.open)) throw Error('diagnosis keyboard disclosure did not open');
  await page.keyboard.press('Enter');
  if (await technical.evaluate(node=>node.open)) throw Error('diagnosis keyboard disclosure did not close');
  fs.mkdirSync(output+'/diagnosis',{recursive:true});
  for (const width of [320,390,1280]) {
    await page.setViewportSize({width,height:1000});
    const layout=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
      smallTargets:[...document.querySelectorAll('.document-diagnosis a,.document-diagnosis summary,.document-diagnosis button')]
        .filter(node=>node.getBoundingClientRect().height>0 && node.getBoundingClientRect().height<44)
        .map(node=>({text:node.textContent,height:node.getBoundingClientRect().height}))}));
    if (layout.scrollWidth>layout.width || layout.smallTargets.length)
      throw Error('diagnosis layout failed: '+JSON.stringify(layout));
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:output+'/diagnosis/'+width+'.png',fullPage:true});
  }
  if (errors.length) throw Error('script errors '+JSON.stringify(errors));
  fs.writeFileSync(output+'/browser-result.json',JSON.stringify({layout:titles,selected:sid,
    receiptDidNotStart:true,explicitStart:true,reviewOpened:true,unassignedUploaderDirectedToTrajectory:true,namedReviewerEnteredReview:true,
    blockageOpenedBeforeProcessing:true,blockageDownloadReadOnly:true,blockageMobileOverflow:false,mobileOverflow:false,
    diagnosisViewports:[320,390,1280],diagnosisKeyboardDisclosure:true,pageErrors:errors},null,2));
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

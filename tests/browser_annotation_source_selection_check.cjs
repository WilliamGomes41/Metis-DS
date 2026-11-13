const {chromium}=require(process.env.METIS_PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const base=process.env.METIS_BROWSER_BASE,output=process.env.METIS_BROWSER_OUTPUT;
 const manifest=await(await fetch(base+'/browser-manifest')).json();
 const browser=await chromium.launch({executablePath:process.env.METIS_BROWSER_EXECUTABLE,headless:true});
 require('./browser_annotation_tasks.cjs').useAdvancedForm(browser);
 try {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(base+'/login');await page.locator('[name=username]').fill(manifest.username);await page.locator('[name=password]').fill(manifest.password);
  await Promise.all([page.waitForURL(url=>url.pathname!='/login'),page.locator('button[type=submit]').click()]);
  await page.goto(base+'/ingest');
  const emoji='👩🏽‍⚕️',text='A '+emoji+' B.';
  await page.locator('[name=file]').setInputFiles({name:'source-only.html',mimeType:'text/html',buffer:Buffer.from('<html><body><h1>Bronselectie</h1><p>'+text+'</p><p>'+text+'</p></body></html>')});
  for(const [field,value] of Object.entries({title:'Selecteren in de bron',version:'1',date:'2026-11-11',family:'test'})) await page.locator(`[name=${field}]`).fill(value);
  await page.locator('[name=class_]').selectOption('richtlijn');await page.locator('[name=review_option][value=uploader_sole]').check();
  await Promise.all([page.waitForURL(url=>url.pathname==='/annotations'),page.locator('#ingest-submit').click()]);
  const sid=new URL(page.url()).searchParams.get('document');
  await page.getByRole('button',{name:'Bron openen voor annotatie',exact:true}).click();
  await page.locator('#annotation-editor-inputs:enabled').waitFor();
  assert.equal(await page.locator('#annotation-source-input,.annotation-selection-help').count(),0,'The duplicate selection field must be removed');
  assert.equal(await page.getByText('Huidige passage',{exact:true}).count(),0);
  assert.equal(await page.locator('#annotation-add').isDisabled(),true,'No initial passage is selected');
  await page.screenshot({path:output+'/source-only-desktop.png',fullPage:true});
  await page.locator('#annotation-type').selectOption('recommendation');
  const block=page.locator('[data-source-block]').filter({hasText:text}).first();
  const firstId=await block.getAttribute('data-source-block');
  await block.focus();await page.keyboard.press('Home');await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowRight');
  await page.keyboard.press('Shift+ArrowRight');
  assert.equal(await page.evaluate(()=>getSelection().toString()),emoji,'One key must select the complete emoji grapheme');
  assert.match(await page.locator('#annotation-selection').innerText(),new RegExp(emoji));
  await page.locator('#annotation-add').click();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  const read=p=>p.evaluate(async sid=>(await fetch('/annotations/api?document='+sid)).json(),sid);
  let saved=(await read(page)).entries[0];
  assert.equal(saved.ranges[0].block_id,firstId);assert.equal(saved.ranges[0].start,2);assert.equal(saved.ranges[0].end,7);assert.equal(saved.ranges[0].quote,emoji);
  // Reversed keyboard selection must also cross the newly rendered <mark>.
  await block.focus();await page.keyboard.press('End');
  for(let n=0;n<3;n++) await page.keyboard.press('ArrowLeft');
  await page.keyboard.press('Shift+ArrowLeft');
  assert.equal(await page.evaluate(()=>getSelection().toString()),emoji);
  await page.keyboard.type('x');assert.equal(await block.textContent(),text,'The source remains read-only');
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  const annotation=saved.annotation_id;
  await page.reload();
  saved=(await read(page)).entries[0];assert.equal(saved.pending_range.block_id,firstId);assert.equal(saved.pending_range.quote,emoji);assert.equal(saved.pending_range.start,2);assert.equal(saved.pending_range.end,7);
  await page.screenshot({path:output+'/source-keyboard-desktop.png',fullPage:true});
  await page.locator('#annotation-discard').click();
  await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,storageState:await context.storageState()});
  const touchPage=await mobile.newPage();touchPage.on('pageerror',error=>errors.push(error.message));
  await touchPage.goto(base+'/annotations?'+new URLSearchParams({document:sid,annotation}));
  const other=touchPage.locator('[data-source-block]').filter({hasText:text}).last();
  const secondId=await other.getAttribute('data-source-block');assert.notEqual(firstId,secondId);
  await other.tap();
  // Replay the browser's selected DOM range and touch-end callback. This is
  // emulated touch event coverage, not a physical-device/OS selection test.
  await other.evaluate((node,emoji)=>{
   node.dispatchEvent(new Event('touchstart',{bubbles:true}));
   const range=document.createRange();range.setStart(node.firstChild,2);range.setEnd(node.firstChild,2+emoji.length);
   const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
   node.dispatchEvent(new Event('touchend',{bubbles:true}));
  },emoji);
  await touchPage.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Concept opgeslagen.');
  saved=(await read(touchPage)).entries[0];assert.equal(saved.pending_range.block_id,secondId);assert.equal(saved.pending_range.quote,emoji);assert.equal(saved.pending_range.start,2);assert.equal(saved.pending_range.end,7);
  assert.equal(await touchPage.locator('#annotation-source-input,.annotation-selection-help').count(),0);
  assert.ok(await touchPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await touchPage.screenshot({path:output+'/source-touch-mobile.png',fullPage:true});
  await touchPage.reload();assert.match(await touchPage.locator('#annotation-selection').innerText(),new RegExp(emoji));
  await touchPage.screenshot({path:output+'/source-resumed-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(output+'/source-selection-result.json',JSON.stringify({sourceOnly:true,keyboardGraphemes:true,reversedAcrossMarks:true,readOnly:true,pendingResumed:true,emulatedTouchEvents:true,distinctSourceBlocks:true,errors}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});

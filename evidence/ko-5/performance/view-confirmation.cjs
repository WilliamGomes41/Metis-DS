// Parse the separately captured response with existing product/test selectors.
const fs=require('fs');
const assert=require('assert');
const {chromium}=require('/tmp/metis-saved-browser/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 for(const side of ['base','head']){
  const page=await browser.newPage();
  // Keep native inline assessment behavior; block all external transports.
  await page.route('**/*',route=>route.abort());
  await page.setContent(fs.readFileSync(`/workspace/ko5-perf-final-evidence/view-${side}.html`,'utf8'),{waitUntil:'domcontentloaded'});
  const capture=JSON.parse(fs.readFileSync(`/workspace/ko5-perf-final-evidence/view-${side}-capture.json`));
  const dom=await page.evaluate(()=>{
   const form=document.querySelector('[data-ko-assessment-form]');
   const source=document.querySelector('.ko-source-panel, [data-document-context]');
   return {h1:[...document.querySelectorAll('h1')].map(x=>x.textContent.trim()),
    form:form?{method:form.method,action:form.getAttribute('action'),canApprove:form.getAttribute('data-can-approve'),
      legends:[...form.querySelectorAll('legend')].map(x=>x.textContent.trim()),
      answers:Object.fromEntries(['applicable','complete','placed_correctly'].map(name=>[name,
        [...form.querySelectorAll(`input[type=radio][name="${name}"]`)].map(x=>({value:x.value,checked:x.checked,disabled:x.disabled}))])),
      identity:Object.fromEntries([...form.querySelectorAll('input[type=hidden]')].filter(x=>['snapshot_id','object_id'].includes(x.name)).map(x=>[x.name,x.value])),
      approve:[...form.querySelectorAll('button')].filter(x=>x.value==='approve').map(x=>({text:x.textContent.trim(),disabled:x.disabled})),
      later:[...form.querySelectorAll('button')].filter(x=>x.value==='later').map(x=>x.textContent.trim())}:null,
    sourcePanel:source?{selector:source.className||'[data-document-context]',text:source.textContent.trim()}:null,
    passage:[...document.querySelectorAll('[data-full-knowledge-passage]')].map(x=>x.textContent.trim()),
    readonlyObjectView:!!document.querySelector('[data-ko-object-view]'),
    errorBanner:!!document.querySelector('[data-error-code]'),
    receipt:!!document.querySelector('[data-review-receipt]')};
  });
  fs.writeFileSync(`/workspace/ko5-perf-final-evidence/view-${side}-semantic.json`,JSON.stringify({...capture,dom},null,2));
  assert.deepEqual(dom.h1,['Review']);
  assert(dom.form,'normal assessment form absent');
  assert.equal(dom.form.action,'/review');
  assert.equal(dom.form.method,'post');
  assert.deepEqual(dom.form.legends,['Is dit toepasbaar?','Is dit compleet?','Staat dit op de juiste plek?']);
  for(const answers of Object.values(dom.form.answers)){
   assert.deepEqual(answers.map(x=>x.value),['yes','adjust']);
   assert(answers.every(x=>!x.checked&&!x.disabled),'assessment must be unselected and enabled');
  }
  assert.equal(dom.form.identity.object_id,capture.object_id);
  assert.equal(dom.form.identity.snapshot_id,capture.snapshot_id);
  assert(dom.sourcePanel&&dom.sourcePanel.text.includes('Begrip 0'),'native source context absent');
  assert(dom.passage.some(x=>x.includes('Begrip 0')),'candidate passage absent');
  assert(!dom.readonlyObjectView&&!dom.errorBanner&&!dom.receipt,'unexpected alternate page');
  assert.equal(dom.form.canApprove,'true');
  // Native JS requires all three affirmative answers before enabling approval.
  assert.deepEqual(dom.form.approve,[{text:'Goedkeuren en opslaan',disabled:true}]);
  assert.deepEqual(dom.form.later,['Later beoordelen']);
  console.log(`${side}: ordinary actionable Review card confirmed, three unselected native question groups, source context and submit form`);
  await page.close();
 }
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});

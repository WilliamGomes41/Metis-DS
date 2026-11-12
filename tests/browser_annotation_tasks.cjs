// Public guided UI actions shared by native browser regressions.
const assert=require('node:assert/strict');
// #1060: the step form is the advanced form; the default card needs no steps.
async function advanced(page) {
 await page.locator('#annotation-editor-inputs:enabled').waitFor();
 if(await page.locator('#annotation-steps').isVisible()) return;
 const details=page.locator('#annotation-more');
 if(!await details.evaluate(node=>node.open)) await details.locator(':scope > summary').click();
 await page.locator('#annotation-advanced').click();
}
async function step(page,n) {await advanced(page);await page.locator('#annotation-step-'+n).click();}
async function open(page,id) {
 const details=page.locator('#annotation-'+id);
 if(!await details.evaluate(node=>node.open)) await details.locator(':scope > summary').click();
}
async function type(page,value) {
 await step(page,1);await page.locator('#annotation-type').selectOption(value);
 if(await page.locator('#annotation-confirm').isVisible()) await page.locator('#annotation-confirm-accept').click();
}
async function role(page,value) {
 await step(page,2);await open(page,'context-tools');await page.locator('#annotation-role').selectOption(value);
}
async function field(page,value) {await step(page,2);await page.locator(`[data-field="${value}"]`).click();}
async function ready(page) {
 await step(page,3);await page.locator('#annotation-ready:enabled').waitFor();await page.locator('#annotation-ready').click();
 await page.waitForFunction(()=>document.getElementById('annotation-status').textContent==='Klaar voor documentcontrole en opgeslagen.');
}
async function more(page) {await open(page,'more');}
async function linked(page) {await open(page,'linked');}
async function confirm(page) {await page.locator('#annotation-confirm-accept').click();}
// Proofs of the step form keep it open across pages and reloads, as a user who chose it would.
function useAdvancedForm(browser) {
 const create=browser.newContext.bind(browser);
 browser.newContext=async options=>{
  const context=await create(options);
  await context.addInitScript(()=>{try {localStorage.setItem('metis-annotation-form','uitgebreid');} catch(_) {}});
  return context;
 };
}
module.exports={useAdvancedForm,advanced,step,open,type,role,field,ready,more,linked,confirm};

// Select real source DOM text; field-binding workflows use the same capture
// boundary as keyboard/mouse selection, without a duplicate textarea.
async function selectText(page,source,text) {
 await source.evaluate((node,text)=>{
  const start=node.textContent.indexOf(text);
  if(start<0) throw Error('Requested words are absent from this source block');
  const point=position=>{
   const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let child;
   while((child=walker.nextNode())) {if(position<=child.length)return [child,position];position-=child.length;}
   throw Error('Source selection is outside the block');
  };
  const a=point(start),b=point(start+text.length),range=document.createRange();
  range.setStart(a[0],a[1]);range.setEnd(b[0],b[1]);
  const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
  node.dispatchEvent(new KeyboardEvent('keyup',{key:'Shift',bubbles:true}));
 },text);
}
module.exports.selectText=selectText;

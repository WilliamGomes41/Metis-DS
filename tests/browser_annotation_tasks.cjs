// Public guided UI actions shared by native browser regressions.
const assert=require('node:assert/strict');
async function step(page,n) {await page.locator('#annotation-step-'+n).click();}
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
module.exports={step,open,type,role,field,ready,more,linked,confirm};

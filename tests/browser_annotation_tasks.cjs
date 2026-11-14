// Public guided UI actions shared by native browser regressions.
const assert=require('node:assert/strict');
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

// On a failed proof, write what the card showed, so a CI-only failure can be read from the log.
async function describeCard(page) {
  if(!page || page.isClosed()) return;
  try {
    const state=await page.evaluate(()=>{
      const text=id=>document.getElementById(id)?.innerText ?? null;
      const kind=document.getElementById('annotation-simple-type-select');
      return {url:location.href,status:text('annotation-status'),simpleStatus:text('annotation-simple-status'),
        notes:text('annotation-simple-notes'),rows:text('annotation-simple-rows'),
        inputsDisabled:document.getElementById('annotation-editor-inputs')?.disabled ?? null,
        kind:kind ? {value:kind.value,disabled:kind.disabled} : null,
        ready:document.getElementById('annotation-ready') ? {disabled:document.getElementById('annotation-ready').disabled} : null};
    });
    console.error('CARD STATE '+JSON.stringify(state));
  } catch(error) {console.error('CARD STATE unavailable: '+error.message);}
}
module.exports.describeCard=describeCard;

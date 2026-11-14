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

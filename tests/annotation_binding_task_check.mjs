import assert from 'node:assert/strict';
import {bindRange} from '../src/vorming/human_annotation_binding.mjs';
const span={block_id:'condition',start:0,end:5};
const selected={...span,quote:'Alleen'};
const contract={context_bindings:{condition:'condition_span'}};
const initial={annotation_id:'annotation',ranges:[],status:'ready',
  pending_range:selected,field_evidence:{condition_span:{span:null,missing_reason:'uncertain'}}};
const options={role:'condition',evidenceFunction:null};
const snapshot=JSON.stringify(initial);
assert.throws(()=>bindRange(initial,null,options,contract),/Wijs eerst/);
const bound=bindRange(initial,selected,options,contract);
assert.equal(JSON.stringify(initial),snapshot,'local failure/success must not mutate the previous draft');
assert.deepEqual(bound.entry.field_evidence.condition_span,{span,missing_reason:null});
// #1060 deel 2: a linked range has no essential flag at all.
assert.equal('required_for_meaning' in bound.entry.ranges[0],false);
assert.equal(bound.entry.status,'draft');assert.equal(bound.entry.pending_range,null);
for(const previous of [{span:{...span,block_id:'other'},missing_reason:null},{core:true}]) {
  const current=structuredClone(initial);current.field_evidence.condition_span=previous;
  const result=bindRange(current,selected,options,contract);
  assert.deepEqual(result.entry.field_evidence.condition_span,previous);
  assert.equal(result.entry.ranges.length,1);assert.equal(result.fieldBinding,'preserved');
}

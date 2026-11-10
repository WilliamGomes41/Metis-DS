import assert from 'node:assert/strict';
import {bindRange} from '../src/vorming/human_annotation_binding.mjs';
const span={block_id:'condition',start:0,end:5};
const selected={...span,quote:'Alleen'};
const contract={context_bindings:{condition:'condition_span'}};
const initial={annotation_id:'annotation',ranges:[],required_links:[],status:'ready',
  pending_range:selected,field_evidence:{condition_span:{span:null,missing_reason:'uncertain'}}};
const options={role:'condition',essential:true,evidenceFunction:null};
const snapshot=JSON.stringify(initial);
assert.throws(()=>bindRange(initial,null,options,contract),/Wijs eerst/);
assert.throws(()=>bindRange(initial,selected,{...options,essential:null},contract),/Kies of/);
const bound=bindRange(initial,selected,options,contract);
assert.equal(JSON.stringify(initial),snapshot,'local failure/success must not mutate the previous draft');
assert.deepEqual(bound.entry.field_evidence.condition_span,{span,missing_reason:null});
assert.equal(bound.entry.ranges[0].required_for_meaning,true);
assert.equal(bound.entry.status,'draft');assert.equal(bound.entry.pending_range,null);
for(const previous of [{span:{...span,block_id:'other'},missing_reason:null},{core:true}]) {
  const current=structuredClone(initial);current.field_evidence.condition_span=previous;
  const result=bindRange(current,selected,options,contract);
  assert.deepEqual(result.entry.field_evidence.condition_span,previous);
  assert.equal(result.entry.ranges.length,1);assert.equal(result.fieldBinding,'preserved');
}
const repair=structuredClone(initial);
repair.required_links=[{relationship_id:'original-essential-id',role:'condition',required_for_meaning:true,evidence_function:null},
  {relationship_id:'other-duty',role:'condition',required_for_meaning:true,evidence_function:null}];
const restored=bindRange(repair,selected,{role:'population',essential:false,repairingLink:'original-essential-id'},contract);
assert.equal(restored.entry.ranges[0].relationship_id,'original-essential-id');
assert.equal(restored.entry.ranges[0].role,'condition');
assert.equal(restored.entry.ranges[0].required_for_meaning,true);
assert.deepEqual(restored.entry.required_links,[repair.required_links[1]]);

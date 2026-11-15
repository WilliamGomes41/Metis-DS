/* Builds one existing save command; durable validation stays in the kernel. */
// #1060 slice 5: the card links nothing as essential and repairs no essential link, so the binding
// does neither. The stored field required_for_meaning stays (false) until its consequences are known.
export function bindRange(current, selected, options, contract) {
  if (!selected) throw new Error('Wijs eerst tekst in één bronblok aan.');
  const entry = JSON.parse(JSON.stringify(current));
  const role = options.role;
  const anchor = {block_id:selected.block_id,start:selected.start,end:selected.end};
  const added = {...anchor,quote:selected.quote,role,required_for_meaning:false,
    evidence_function:role === 'evidence' ? options.evidenceFunction : null};
  if (role !== 'core') added.relationship_id = 'link-v1:'+JSON.stringify([entry.annotation_id,role,anchor.block_id,anchor.start,anchor.end]);
  const field = !entry.disposition && contract.context_bindings[role];
  let fieldBinding = null;
  if (field) {
    const previous = entry.field_evidence[field];
    if (!previous) throw new Error('Het betekenisveld ontbreekt. Herlaad eerst de annotatie.');
    const same = previous.span && ['block_id','start','end'].every(key => previous.span[key] === anchor[key]);
    if (previous.core || previous.span && !same) fieldBinding = 'preserved';
    else {entry.field_evidence[field] = {span:anchor,missing_reason:null};fieldBinding = 'bound';}
  }
  entry.ranges.push(added);
  entry.pending_range = null;
  entry.status = 'draft';
  return {entry,field,fieldBinding};
}

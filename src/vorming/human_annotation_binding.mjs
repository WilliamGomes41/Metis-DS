/* Builds one existing save command; durable validation stays in the kernel. */
export function bindRange(current, selected, options, contract) {
  if (!selected) throw new Error('Wijs eerst tekst in één bronblok aan.');
  const entry = JSON.parse(JSON.stringify(current));
  const restoring = entry.required_links.find(link => link.relationship_id === options.repairingLink && link.required_for_meaning);
  const role = restoring?.role || options.role;
  const essential = restoring ? true : role === 'core' ? false : options.essential;
  if (role !== 'core' && typeof essential !== 'boolean')
    throw new Error('Kies of dit bereik essentieel is voor de betekenis.');
  const anchor = {block_id:selected.block_id,start:selected.start,end:selected.end};
  const added = {...anchor,quote:selected.quote,role,required_for_meaning:essential,
    evidence_function:restoring ? restoring.evidence_function : role === 'evidence' ? options.evidenceFunction : null};
  if (role !== 'core') added.relationship_id = restoring?.relationship_id ||
    'link-v1:'+JSON.stringify([entry.annotation_id,role,anchor.block_id,anchor.start,anchor.end]);
  const field = !entry.disposition && contract.context_bindings[role];
  let fieldBinding = null;
  if (field) {
    const previous = entry.field_evidence[field];
    if (!previous) throw new Error('Het betekenisveld ontbreekt. Herlaad eerst de annotatie.');
    const same = previous.span && ['block_id','start','end'].every(key => previous.span[key] === anchor[key]);
    if (previous.core || previous.span && !same) fieldBinding = 'preserved';
    else {entry.field_evidence[field] = {span:anchor,missing_reason:null};fieldBinding = 'bound';}
  }
  if (restoring) entry.required_links = entry.required_links.filter(link => link.relationship_id !== restoring.relationship_id);
  entry.ranges.push(added);
  entry.pending_range = null;
  entry.status = 'draft';
  return {entry,field,fieldBinding};
}

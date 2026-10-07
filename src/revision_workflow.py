#!/usr/bin/env python3
"""Create a new immutable object version from an explicit reviewed revision patch."""
from __future__ import annotations
import argparse, json, re
from copy import deepcopy
from pathlib import Path
from typing import Any
from src.integrity_kernel import stable_hash, stamp_canonical_hashes, schema_errors
from src.review_ledger import append_event

ALLOWED_ROOTS={'content','logic','relations','risk','uncertainty','structure','decision_graph'}

def bump_patch(v:str)->str:
    m=re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?',v)
    if not m: raise ValueError('object_version_must_be_semver_like')
    major,minor,patch=int(m.group(1)),int(m.group(2)),int(m.group(3) or 0)
    return f'{major}.{minor}.{patch+1}'

def set_path(obj:dict[str,Any], path:str, value:Any)->None:
    parts=path.split('.')
    if not parts or parts[0] not in ALLOWED_ROOTS: raise ValueError(f'patch_path_not_allowed:{path}')
    cur:Any=obj
    for key in parts[:-1]:
        if isinstance(cur,dict) and key in cur: cur=cur[key]
        else: raise ValueError(f'patch_path_missing:{path}')
    if not isinstance(cur,dict): raise ValueError(f'patch_parent_not_object:{path}')
    cur[parts[-1]]=value

def create_revision(obj:dict[str,Any], patch:dict[str,Any], *, actor:str, schema_path:Path, ledger:Path|None=None, snapshot_id:str|None=None)->dict[str,Any]:
    if obj['governance']['validation_status']!='revise': raise ValueError('source_object_not_in_revise_state')
    if not patch.get('reason'): raise ValueError('revision_reason_required')
    ops=patch.get('operations') or []
    if not ops: raise ValueError('revision_operations_required')
    x=deepcopy(obj); previous=x['object_version']; x['object_version']=patch.get('new_object_version') or bump_patch(previous)
    if _version(x['object_version']) <= _version(previous):
        raise ValueError('revision_version_not_increasing')
    for op in ops:
        if op.get('op')!='set': raise ValueError('only_set_operation_supported')
        set_path(x,op['path'],op.get('value'))
    g=x['governance']; g['validation_status']='needs_review'; g['validated_by']=None; g['validation_date']=None; g['review_snapshot_hash']=None
    g['publication_status']='unpublished'; g['second_review']={'required':x['risk']['requires_second_review'],'status':'pending' if x['risk']['requires_second_review'] else 'not_required','reviewer':None,'review_date':None,'snapshot_hash':None}
    p=x['provenance']; p['previous_object_version']=previous; p['revision_reason']=patch['reason']; p['revision_patch_hash']=stable_hash(patch)
    if snapshot_id is not None:
        x = revise_object(obj, x, snapshot_id=snapshot_id, reason=patch['reason'], actor=actor, force=True)
    stamp_canonical_hashes(x)
    errs=schema_errors(x,schema_path)
    if errs: raise ValueError('revision_schema_invalid:'+' | '.join(errs))
    if ledger: append_event(ledger,event_type='revision_created',object_id=x['object_id'],object_version=x['object_version'],actor=actor,
                            details={'previous_object_version':previous,'revision_patch_hash':x['provenance']['revision_patch_hash'],'reason':patch['reason']})
    return x

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--object',type=Path,required=True); ap.add_argument('--patch',type=Path,required=True); ap.add_argument('--schema',type=Path,required=True)
    ap.add_argument('--actor',required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--ledger',type=Path)
    a=ap.parse_args(); obj=json.loads(a.object.read_text()); patch=json.loads(a.patch.read_text()); x=create_revision(obj,patch,actor=a.actor,schema_path=a.schema,ledger=a.ledger)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'status':'PASS','object_id':x['object_id'],'object_version':x['object_version']},indent=2)); return 0

# The cutover is an object-level durable contract, never a deployment timestamp.
LINEAGE_KEY = "revision_lineage"
LINEAGE_CONTRACT = "knowledge-revision-lineage-v1"


def lineage_evidence(obj):
    return (obj.get("metadata") or {}).get(LINEAGE_KEY)


def knowledge_revision(obj):
    """Scope includes blocked selected candidates; excludes source/structure/boom."""
    if lineage_evidence(obj) is not None:
        return True
    from src.admission_gate_v1 import is_boom_object
    from src.knowledge_path_v1 import is_structural_projection
    from src.source_accountability_v1 import is_source_record
    if (obj.get("object_type") == "document" or is_boom_object(obj)
            or is_structural_projection(obj) or is_source_record(obj)):
        return False
    semantic = (obj.get("metadata") or {}).get("semantic_passage") or {}
    return semantic.get("selection_origin") == "proposal_selected"


def _version(value):
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", str(value))
    if not match:
        raise ValueError("object_version_must_be_semver_like")
    return tuple(int(part or 0) for part in match.groups())


def _meaning(obj):
    from src.integrity_kernel import canonical_object_payload
    payload = canonical_object_payload(obj)
    payload.pop("object_version", None)
    metadata = payload.get("metadata") or {}
    metadata.pop(LINEAGE_KEY, None)
    if not metadata:
        payload.pop("metadata", None)
    provenance = payload.get("provenance") or {}
    for field in ("previous_object_version", "revision_reason", "revision_patch_hash"):
        provenance.pop(field, None)
    return payload


def revise_object(previous, proposed, *, snapshot_id, reason, actor, force=False):
    """Prepare one successor; locked persistence validates the exact predecessor.

    Pure preparation does not grant review authority or perform durable writes.
    The caller supplies the actual current row, never a reconstructed predecessor.
    """
    from src.integrity_kernel import compute_canonical_object_hash
    if not (knowledge_revision(previous) or knowledge_revision(proposed)):
        return deepcopy(proposed)
    if not snapshot_id or not reason or not actor:
        raise ValueError("revision_evidence_required")
    if previous.get("object_id") != proposed.get("object_id"):
        raise ValueError("revision_object_identity_mismatch")
    if previous.get("document_id") != proposed.get("document_id") or previous.get("source") != proposed.get("source"):
        raise ValueError("revision_source_identity_mismatch")
    if not force and _meaning(previous) == _meaning(proposed):
        return deepcopy(previous) if proposed == previous else _unchanged_revision(previous, proposed)
    result = deepcopy(proposed)
    old_version = str(previous["object_version"])
    desired = str(proposed["object_version"])
    result["object_version"] = desired if _version(desired) > _version(old_version) else bump_patch(old_version)
    _rebind_relations(result, previous, desired)
    edge = {
        "contract": LINEAGE_CONTRACT,
        "snapshot_id": str(snapshot_id),
        "object_id": str(previous["object_id"]),
        "previous_object_version": old_version,
        "previous_canonical_object_hash": compute_canonical_object_hash(previous),
        "previous_lineage": "strict" if lineage_evidence(previous) else "legacy_unverified",
        "actor": str(actor),
        "reason": str(reason),
    }
    result.setdefault("metadata", {})[LINEAGE_KEY] = edge
    provenance = result.setdefault("provenance", {})
    provenance["previous_object_version"] = old_version
    provenance["revision_reason"] = str(reason)
    provenance["revision_patch_hash"] = stable_hash(edge)
    governance = result.setdefault("governance", {})
    governance.update(validation_status="needs_review", validated_by=None,
                      validation_date=None, review_snapshot_hash=None, publication_status="unpublished")
    required = bool((result.get("risk") or {}).get("requires_second_review"))
    governance["second_review"] = {"required": required, "status": "pending" if required else "not_required",
                                   "reviewer": None, "review_date": None, "snapshot_hash": None}
    return stamp_canonical_hashes(result)


def _unchanged_revision(previous, proposed):
    """A governance-only decision retains its exact canonical tuple."""
    result = deepcopy(proposed)
    result["object_version"] = previous["object_version"]
    result["provenance"] = deepcopy(previous["provenance"])
    metadata = result.setdefault("metadata", {})
    if lineage_evidence(previous) is not None:
        metadata[LINEAGE_KEY] = deepcopy(lineage_evidence(previous))
    else:
        metadata.pop(LINEAGE_KEY, None)
    return stamp_canonical_hashes(result)


def current_revisions(rows, *, snapshot_id=None):
    """One append-order projection for file and PostgreSQL; no semver guessing.

    Legacy rows retain their historical selection rule. Strict edges must refer
    to the exact immediately preceding stored revision in this WorkingRevision.
    """
    from src.integrity_kernel import compute_canonical_object_hash
    current = {}
    seen = set()
    for row in rows:
        oid, version = row["object_id"], row["object_version"]
        identity = (oid, version)
        if identity in seen and (knowledge_revision(row) or knowledge_revision(current.get(oid, {}))):
            raise ValueError("revision_identity_duplicate")
        seen.add(identity)
        edge = lineage_evidence(row)
        if edge is None and oid in current and lineage_evidence(current[oid]) is not None:
            raise ValueError("revision_lineage_downgrade")
        if edge is not None:
            previous = current.get(oid)
            if not isinstance(edge, dict) or edge.get("contract") != LINEAGE_CONTRACT:
                raise ValueError("revision_lineage_contract_invalid")
            if previous is None:
                raise ValueError("revision_predecessor_missing")
            provenance = row.get("provenance") or {}
            if (edge.get("object_id") != oid
                    or edge.get("previous_object_version") != previous["object_version"]
                    or provenance.get("previous_object_version") != previous["object_version"]
                    or edge.get("previous_canonical_object_hash") != compute_canonical_object_hash(previous)):
                raise ValueError("revision_predecessor_mismatch")
            if _version(version) <= _version(previous["object_version"]):
                raise ValueError("revision_version_not_increasing")
            if (not edge.get("snapshot_id") or snapshot_id is not None and edge["snapshot_id"] != snapshot_id
                    or row.get("document_id") != previous.get("document_id")
                    or row.get("source") != previous.get("source")):
                raise ValueError("revision_scope_mismatch")
            if (edge.get("previous_lineage") != ("strict" if lineage_evidence(previous) else "legacy_unverified")
                    or not edge.get("reason") or not edge.get("actor")
                    or provenance.get("revision_reason") != edge["reason"]
                    or provenance.get("revision_patch_hash") != stable_hash(edge)
                    or provenance.get("canonical_object_hash") != compute_canonical_object_hash(row)):
                raise ValueError("revision_evidence_invalid")
        current[oid] = row
    return list(current.values())


def validate_revision_write(previous, submitted, *, snapshot_id):
    """Called under the existing file lock / PostgreSQL row lock and CAS."""
    from src.integrity_kernel import compute_canonical_object_hash
    old_current = {row["object_id"]: row for row in current_revisions(previous, snapshot_id=snapshot_id)}
    new_current = {row["object_id"]: row for row in current_revisions(submitted, snapshot_id=snapshot_id)}
    old = {(row["object_id"], row["object_version"]): row for row in previous}
    new = {(row["object_id"], row["object_version"]): row for row in submitted}
    protected_ids = {row["object_id"] for row in previous + submitted if knowledge_revision(row)}
    retained_order = [(row["object_id"], row["object_version"]) for row in submitted
                      if (row["object_id"], row["object_version"]) in old
                      and row["object_id"] in protected_ids]
    original_order = [identity for identity, row in old.items() if identity[0] in protected_ids]
    for oid in protected_ids:
        if ([identity for identity in retained_order if identity[0] == oid]
                != [identity for identity in original_order if identity[0] == oid]):
            raise ValueError("revision_history_reordered")
    for identity, before in old.items():
        after = new.get(identity)
        if identity[0] not in protected_ids:
            continue
        if after is None:
            raise ValueError("revision_history_removed")
        if compute_canonical_object_hash(before) != compute_canonical_object_hash(after):
            raise ValueError("revision_content_changed_in_place")
        if (new_current[identity[0]]["object_version"] != identity[1]
                or old_current[identity[0]] != before) and after != before:
            raise ValueError("revision_history_changed")
    sealed = any((row.get("governance") or {}).get("publication_status") == "published" for row in previous)
    for identity, after in new.items():
        if identity in old:
            continue
        before = old_current.get(identity[0])
        if before is not None and (knowledge_revision(before) or knowledge_revision(after)):
            if sealed:
                raise ValueError("published_working_revision_immutable")
            if not lineage_evidence(after):
                raise ValueError("revision_predecessor_required")
    # No stale command can add an alternative successor to the now-current row.
    appended = [row for row in submitted if (row["object_id"], row["object_version"]) not in old]
    if appended:
        current_revisions(previous + appended, snapshot_id=snapshot_id)

if __name__=='__main__': raise SystemExit(main())


def reprocessed_history(previous, generated, *, snapshot_id, actor):
    """Retain knowledge history through same-source preparation/recovery.

    New identities remain initial candidates; this never matches text or sources.
    Removed knowledge candidates become terminal without erasing their history.
    """
    from src.integrity_kernel import compute_canonical_object_hash
    prior = {row["object_id"]: row for row in current_revisions(previous, snapshot_id=snapshot_id)}
    retained_ids = {row["object_id"] for row in previous + generated if knowledge_revision(row)}
    retained = [deepcopy(row) for row in previous if row["object_id"] in retained_ids]
    new_ids = {row["object_id"] for row in generated}
    for oid, row in prior.items():
        if knowledge_revision(row) and oid not in new_ids:
            if (row.get("governance") or {}).get("validation_status") == "superseded":
                continue
            retired = revise_object(row, row, snapshot_id=snapshot_id, actor=actor,
                                    reason="same-source candidate retirement", force=True)
            retired["governance"]["validation_status"] = "superseded"
            retained.append(retired)
    for row in generated:
        old = prior.get(row["object_id"])
        if old is None or not (knowledge_revision(old) or knowledge_revision(row)):
            retained.append(deepcopy(row))
            continue
        if compute_canonical_object_hash(old) == compute_canonical_object_hash(row):
            continue
        updated = revise_object(old, row, snapshot_id=snapshot_id,
                                reason="same-source re-extraction/recovery", actor=actor,
                                force=(old.get("governance") or {}).get("validation_status") == "superseded")
        if updated["object_version"] == old["object_version"]:
            continue
        retained.append(updated)
    order = {}
    for row in previous + generated:
        order.setdefault(row["object_id"], len(order))
    return sorted(retained, key=lambda row: order[row["object_id"]])

def _rebind_relations(result, previous, staged_version):
    """Rebuild IDs for the new source endpoint, never infer a new target."""
    from src.knowledge_relations_v1 import (build_knowledge_relation,
        validate_knowledge_relation_set, relation_sort_key)
    remap = {}
    for field in ("proposed_knowledge_relations", "confirmed_knowledge_relations"):
        if field not in result:
            continue
        relations = result[field]
        # Accept the caller's freshly prepared set or the predecessor's exact set.
        if (validate_knowledge_relation_set(relations, source_object_id=result["object_id"],
                source_object_version=staged_version)
                and validate_knowledge_relation_set(relations, source_object_id=result["object_id"],
                source_object_version=previous["object_version"])):
            raise ValueError("revision_relation_evidence_invalid")
        rebuilt = []
        for relation in relations:
            new = build_knowledge_relation(source_object_id=result["object_id"],
                source_object_version=result["object_version"], relation_type=relation["relation_type"],
                target_object_id=relation["target_object_id"], target_object_version=relation["target_object_version"])
            remap[relation["relation_id"]] = new["relation_id"]
            rebuilt.append(new)
        result[field] = sorted(rebuilt, key=relation_sort_key)
    metadata = result.get("metadata") or {}
    # Source spans/evidence are preserved; only the exact source-endpoint IDs change.
    evidence = metadata.get("knowledge_relation_evidence")
    if isinstance(evidence, dict):
        for row in evidence.get("relations") or []:
            if row.get("relation_id") in remap:
                row["relation_id"] = remap[row["relation_id"]]
    review = metadata.get("knowledge_relation_review")
    if isinstance(review, dict):
        if review == (previous.get("metadata") or {}).get("knowledge_relation_review"):
            # Historical confirmation lives on the predecessor, not on a fresh review.
            metadata.pop("knowledge_relation_review", None)
        else:
            review["source_object_version_after"] = result["object_version"]
            review["confirmed_relation_ids"] = [r["relation_id"] for r in result.get("confirmed_knowledge_relations", [])]

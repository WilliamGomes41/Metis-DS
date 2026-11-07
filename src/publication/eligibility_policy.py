#!/usr/bin/env python3
"""Single fail-closed publication eligibility policy."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from src.integrity_kernel import exact_review_snapshot_hash, schema_errors, validate_hashes, validate_source_fragments, validate_source_integrity


def publication_errors(obj: dict[str, Any], *, schema_path: Path, verified_sources: dict[str,str] | None = None,
                       raw_objects: dict[str,dict[str,Any]] | None = None,
                       bindings: list[dict[str, Any]] | None = None, review_path: str = "richtlijn") -> list[str]:
    errors=[]
    errors += [f'schema:{x}' for x in schema_errors(obj,schema_path)]
    errors += validate_hashes(obj)
    errors += validate_source_integrity(obj.get('source') or {}, verified_sources)
    errors += validate_source_fragments(obj, raw_objects)
    # For PDF canonical sources, exact page coordinates are required before publication.
    if (obj.get('source') or {}).get('source_type') == 'pdf' and obj.get('object_type') != 'document':
        refs = (obj.get('provenance') or {}).get('source_fragments') or []
        if any(r.get('coordinate_status') != 'available' or not r.get('bbox') for r in refs):
            errors.append('source_fragment_coordinates_unavailable')
    g=obj.get('governance') or {}
    if g.get('validation_status')!='approved': errors.append('validation_status_not_approved')
    if not g.get('validated_by'): errors.append('validated_by_missing')
    if not g.get('validation_date'): errors.append('validation_date_missing')
    if g.get('review_snapshot_hash') != exact_review_snapshot_hash(obj): errors.append('review_snapshot_not_exact_object')
    # Offline JSONL has no durable review authority. Exact binding facts are
    # mandatory; governance mirrors cannot authorize publication.
    from src.review.review_duty_v1 import exact_current_approver_ids, review_stage
    approvers = exact_current_approver_ids(obj, bindings or ())
    if not approvers:
        errors.append('object_tuple_required')
    if review_stage(obj, review_path=review_path, bindings=bindings or ()) is not None:
        errors.append('current_review_duty_open')
    if (obj.get('uncertainty') or {}).get('has_uncertainty'): errors.append('unresolved_uncertainty')
    return sorted(set(errors))

"""Explicit migration command. Queries never call this module."""
from copy import deepcopy
import re

from src.source_representation_v1 import (
    load, prepare, provenance, accept_local, accept_postgres,
    SourceRepresentationError, MISSING,
)


def migrate(console, *, actor_id, snapshot_id, command_id, expected_revision,
            reason, dry_run=True, correction_revision=0):
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
    from src.source_selection_v1 import authorize
    if not reason.strip() or len(reason) > 4000 or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", command_id):
        raise ConsoleError("source_representation_command_invalid")
    console._require_role(actor_id, "researcher")
    envelope = deepcopy(console._envelope(snapshot_id))
    authorize(console, actor_id, envelope)
    if actor_id != envelope.get("uploader_account_id") and actor_id not in envelope.get("named_reviewers", []):
        raise ConsoleError("reviewer_not_named_on_snapshot")
    revision = console.objects_revision(snapshot_id)
    if not expected_revision or revision != expected_revision:
        raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
    try:
        existing = load(console, envelope)
    except SourceRepresentationError as exc:
        if str(exc) != MISSING:
            raise ConsoleError(str(exc)) from exc
    else:
        if existing.representation["key"]["correction_revision"] != correction_revision:
            raise ConsoleError("source_representation_successor_required")
        return {"snapshot_id": snapshot_id, "representation_id": existing.representation["representation_id"],
                "dry_run": dry_run, "idempotent": True}
    path, _ = console._verified_source_bytes(envelope)
    from src.docling_contract_v1 import stored_fragments
    fragments = stored_fragments(envelope)
    if fragments is None:
        if console.snapshot_is_published(snapshot_id):
            raise ConsoleError("source_representation_successor_required")
        fragments = console._extract_historical_source_for_migration(envelope, path)
    record = prepare(envelope, fragments, correction_revision=correction_revision)
    # Existing exact span/source contracts prove semantic preservation, not an
    # LLM similarity judgement. Invalid legacy evidence is not silently repaired.
    from src.knowledge_materialisation_v1 import validate_materialised_candidate
    for obj in console.snapshot_objects(snapshot_id):
        semantic = obj.get("semantic_passage") or (obj.get("metadata") or {}).get("semantic_passage") or {}
        if semantic.get("spans"):
            try:
                validate_materialised_candidate(obj, fragments=fragments)
            except ValueError as exc:
                raise ConsoleError("source_representation_migration_not_equivalent") from exc
    result = {"snapshot_id": snapshot_id, "representation_id": record["representation_id"],
              "payload_hash": record["payload_hash"], "dry_run": dry_run, "idempotent": False}
    if dry_run:
        return result
    with console._reprocessing_transaction(snapshot_id):
        current = console._envelope(snapshot_id)
        console._require_role(actor_id, "researcher")
        authorize(console, actor_id, current)
        if actor_id != current.get("uploader_account_id") and actor_id not in current.get("named_reviewers", []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if console.objects_revision(snapshot_id) != revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=console.objects_revision(snapshot_id))
        if any(current[k] != envelope[k] for k in ("sha256", "document_id", "source_id")):
            raise ConsoleError("source_representation_conflict")
        console._verified_source_bytes(current)
        evidence = provenance(current, actor_id=actor_id, command_id=command_id, reason=reason)
        documents = getattr(console, "workflow_document_store", None)
        if documents is None:
            accept_local(console, current, record, evidence)
        else:
            with documents._connect() as con:
                accept_postgres(con, current, record, evidence)
    return result

"""Reviewer-owned literal source context in the existing versioned object store.

The target's hashed metadata owns its context evidence. Source role metadata
classifies the source fragment; incoming targets are derived, never a second
relation store. See docs/SOURCE_CONTEXT_REVIEW_CONTRACT.md.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from src.integrity_kernel import stable_hash, stamp_canonical_hashes, schema_errors
from src.publish_authorization_v1 import invalidate_for_object
from src.review_ledger import append_event, read_events

ROLE_KEY = "source_role_review"
LINKS_KEY = "confirmed_source_context"
CONTRACT = "source-context-review-v1"
EVENT = "source_context_review"


def literal_identity(obj: dict[str, Any]) -> str:
    return stable_hash({
        "content": obj.get("content") or {},
        "source": obj.get("source") or {},
        "fragments": (obj.get("provenance") or {}).get("source_fragments") or [],
        "semantic_spans": ((obj.get("metadata") or {}).get("semantic_passage") or {}).get("spans") or [],
    })


def role_of(obj: dict[str, Any]) -> dict[str, Any]:
    row = (obj.get("metadata") or {}).get(ROLE_KEY)
    return deepcopy(row) if isinstance(row, dict) else {}


def links_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (obj.get("metadata") or {}).get(LINKS_KEY)
    return deepcopy([row for row in rows if isinstance(row, dict)]) if isinstance(rows, list) else []


def context_issues(objects: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    rows = list(objects)
    by_id = {str(row.get("object_id") or ""): row for row in rows}
    issues: dict[str, list[str]] = {}
    referenced: set[str] = set()
    for target in rows:
        target_id = str(target.get("object_id") or "")
        raw = (target.get("metadata") or {}).get(LINKS_KEY)
        if raw is not None and not isinstance(raw, list):
            issues.setdefault(target_id, []).append("source_context_invalid")
            continue
        for link in raw or []:
            if not isinstance(link, dict):
                issues.setdefault(target_id, []).append("source_context_invalid")
                continue
            source_id = str(link.get("source_object_id") or "")
            source = by_id.get(source_id)
            source_role = role_of(source) if source else {}
            valid = bool(
                source and source_id != target_id
                and link.get("version") == CONTRACT
                and source_role.get("version") == CONTRACT
                and source_role.get("role") in {"label", "context"}
                and source_role.get("command_id") == link.get("command_id")
                and link.get("source_object_version") == source.get("object_version")
                and link.get("source_literal_hash") == literal_identity(source)
                and source_role.get("literal_hash") == literal_identity(source)
                and link.get("target_literal_hash") == literal_identity(target)
                and link.get("text") == str((source.get("content") or {}).get("clean_text") or "")
                and link.get("source_fragments") == (source.get("provenance") or {}).get("source_fragments")
                and link.get("reviewer_id") == source_role.get("reviewer_id")
                and link.get("target_object_id") == target_id
                and link.get("role") == source_role.get("role")
                and link.get("source_sha256") == source_role.get("source_sha256") == (source.get("source") or {}).get("source_checksum")
                and link.get("source_sha256") == (target.get("source") or {}).get("source_checksum")
                and bool(link.get("command_id")) and bool(link.get("reviewer_id"))
                and bool(link.get("reason"))
            )
            if valid:
                referenced.add(source_id)
            else:
                issues.setdefault(target_id, []).append("source_context_stale")
                if source:
                    issues.setdefault(source_id, []).append("source_context_stale")
    for source in rows:
        raw_role = (source.get("metadata") or {}).get(ROLE_KEY)
        if raw_role is not None and not isinstance(raw_role, dict):
            issues.setdefault(str(source.get("object_id") or ""), []).append("source_context_invalid")
            continue
        role = role_of(source)
        if not role:
            continue
        source_id = str(source.get("object_id") or "")
        if (role.get("version") != CONTRACT or role.get("role") not in {"label", "context", "excluded"}
                or role.get("literal_hash") != literal_identity(source)
                or not role.get("reason") or not role.get("reviewer_id") or not role.get("command_id")):
            issues.setdefault(source_id, []).append("source_context_invalid")
        elif role.get("role") in {"label", "context"} and source_id not in referenced:
            issues.setdefault(source_id, []).append("source_context_target_required")
    return {key: sorted(set(value)) for key, value in issues.items()}


def projections(objects: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = list(objects)
    issues = context_issues(rows)
    result = {str(row.get("object_id") or ""): {
        "role": role_of(row), "links": links_of(row),
        "target_object_ids": [], "issues": issues.get(str(row.get("object_id") or ""), []),
    } for row in rows}
    for oid, evidence in result.items():
        for link in evidence["links"]:
            source = result.get(str(link.get("source_object_id") or ""))
            if source is not None and oid not in source["target_object_ids"]:
                source["target_object_ids"].append(oid)
    return result


def projection(obj: dict[str, Any], objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return projections(objects)[str(obj.get("object_id") or "")]


def confirm_source_context(console: Any, **command: Any) -> dict[str, Any]:
    """Serialize the snapshot before reading, through the real DB commit."""
    documents = getattr(console, "workflow_document_store", None)
    reviews = getattr(console, "workflow_review_store", None)
    if documents is None and reviews is None:
        return _confirm_source_context(console, **command)
    from src.operations_console_v1 import ConsoleError
    from src.workflows.workflow_transaction_v1 import workflow_transaction, workflow_transaction_active
    if documents is None or reviews is None or workflow_transaction_active():
        raise ConsoleError("source_context_independent_transaction_required")
    with console._store_write_lock():
        try:
            with workflow_transaction(reviews) as connection:
                connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                                   (command["snapshot_id"],))
                result = _confirm_source_context(console, **command)
            return result
        except Exception:
            # Mirrors may have been written before the outer commit failed.
            # Rebuild from rolled-back authority; never restore it with writes.
            console._reload_store_locked()
            console._remirror_review_runtime()
            raise


def _confirm_source_context(console: Any, *, actor_id: str, snapshot_id: str,
                           source_object_id: str, role: str, target_object_ids: Iterable[str],
                           reason: str, command_id: str, expected_revision: str) -> dict[str, Any]:
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT, utc_now
    from src.revision_workflow import bump_patch
    from src.passage_register_v1 import passage_register_record

    if role not in {"label", "context", "excluded"}:
        raise ConsoleError("source_context_role_invalid")
    if not reason.strip() or len(reason) > 4000:
        raise ConsoleError("source_context_reason_required")
    if not command_id.strip() or len(command_id) > 128 or not expected_revision:
        raise ConsoleError("source_context_command_required")
    targets = sorted(set(str(value).strip() for value in target_object_ids if str(value).strip()))
    if len(targets) > 100 or (role == "excluded" and targets) or (role != "excluded" and not targets):
        raise ConsoleError("source_context_target_required")
    payload_hash = stable_hash({"actor_id": actor_id, "snapshot_id": snapshot_id,
                               "source_object_id": source_object_id, "role": role,
                               "targets": targets, "reason": reason.strip()})
    with console._store_write_lock():
        console._reload_store_locked()
        reviewer = console._require_role(actor_id, "reviewer")
        envelope = console._envelope(snapshot_id)
        if actor_id not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if console.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_working_revision_immutable")
        for event in read_events(console._ledger_path):
            details = event.get("details") or {}
            if event.get("event_type") == EVENT and details.get("snapshot_id") == snapshot_id and details.get("command_id") == command_id:
                if details.get("payload_hash") != payload_hash:
                    raise ConsoleError("source_context_command_conflict")
                return {**deepcopy(details["result"]), "idempotent": True}
        current, revision = console.snapshot_objects_and_revision(snapshot_id)
        if revision != expected_revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
        by_id = {row["object_id"]: row for row in current}
        source = by_id.get(source_object_id)
        if not source or source.get("object_type") == "document":
            raise ConsoleError("unknown_object")
        if links_of(source):
            raise ConsoleError("source_context_target_invalid")
        console._require_open_original(snapshot_id, source_object_id)
        fragments = (source.get("provenance") or {}).get("source_fragments") or []
        if not fragments or not str((source.get("content") or {}).get("clean_text") or ""):
            raise ConsoleError("source_context_evidence_required")
        for oid in targets:
            target = by_id.get(oid)
            if not target or oid == source_object_id or target.get("object_type") in {"document", "heading", "path"} or role_of(target):
                raise ConsoleError("source_context_target_invalid")
        now = utc_now()
        changed: dict[str, dict[str, Any]] = {}
        source_after = deepcopy(source)
        source_after["object_version"] = bump_patch(str(source["object_version"]))
        source_after.setdefault("metadata", {})[ROLE_KEY] = {
            "version": CONTRACT, "role": role, "command_id": command_id,
            "reviewer_id": actor_id, "reviewer": reviewer["username"], "reviewed_at": now,
            "reason": reason.strip(), "literal_hash": literal_identity(source),
            "source_sha256": envelope["sha256"],
        }
        source_after["metadata"]["passage_register"] = passage_register_record(
            status="excluded_with_reason" if role == "excluded" else "used_as_context",
            reason_codes=["reviewer_confirmed_source_role"], source="review",
        )
        governance = source_after.setdefault("governance", {})
        governance.update(validation_status="rejected", validated_by=reviewer["username"],
                          validation_date=now[:10], review_snapshot_hash=None, publication_status="unpublished")
        changed[source_object_id] = source_after
        for oid, original in by_id.items():
            previous = links_of(original)
            retained = [link for link in previous if link.get("source_object_id") != source_object_id]
            if oid not in targets and len(retained) == len(previous):
                continue
            updated = deepcopy(original)
            updated["object_version"] = bump_patch(str(original["object_version"]))
            if oid in targets:
                retained.append({
                    "version": CONTRACT, "command_id": command_id, "source_object_id": source_object_id,
                    "source_object_version": source_after["object_version"],
                    "source_literal_hash": literal_identity(source_after), "target_literal_hash": literal_identity(updated),
                    "target_object_version_at_confirmation": updated["object_version"],
                    "target_object_id": oid,
                    "text": str((source_after.get("content") or {}).get("clean_text") or ""),
                    "source_fragments": deepcopy(fragments), "source_sha256": envelope["sha256"],
                    "role": role, "reason": reason.strip(), "reviewer_id": actor_id, "reviewed_at": now,
                })
            if retained:
                updated.setdefault("metadata", {})[LINKS_KEY] = retained
            else:
                updated.setdefault("metadata", {}).pop(LINKS_KEY, None)
            governance = updated.setdefault("governance", {})
            governance.update(validation_status="needs_review", validated_by=None,
                              validation_date=None, review_snapshot_hash=None, publication_status="unpublished")
            second = governance.get("second_review")
            if isinstance(second, dict) and second.get("required"):
                second.update(status="pending", reviewer=None, review_date=None, snapshot_hash=None)
            changed[oid] = updated
        history = console._load_objects(snapshot_id, remember=False)
        bindings = deepcopy(console._bindings)
        for oid, updated in changed.items():
            stamp_canonical_hashes(updated)
            errors = schema_errors(updated, console.schema_path)
            if errors:
                raise ConsoleError("revision_schema_invalid", " | ".join(errors))
            history.append(updated)
            bindings[snapshot_id] = invalidate_for_object(bindings.get(snapshot_id, []), oid)
        result = {"snapshot_id": snapshot_id, "source_object_id": source_object_id,
                  "source_object_version": source_after["object_version"], "role": role,
                  "target_versions": {oid: changed[oid]["object_version"] for oid in targets},
                  "command_id": command_id, "idempotent": False}
        console._commit_prepared_store(
            objects=(snapshot_id, history), bindings=bindings, expected_revision=revision,
            snapshot_id=snapshot_id,
            ledger_fn=lambda: append_event(console._ledger_path, event_type=EVENT,
                object_id=source_object_id, object_version=source_after["object_version"], actor=reviewer["username"],
                details={"snapshot_id": snapshot_id, "actor_account_id": actor_id, "command_id": command_id,
                         "payload_hash": payload_hash, "reason": reason.strip(), "result": deepcopy(result)}),
        )
        return result

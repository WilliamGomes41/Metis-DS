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


def confirm_source_exclusions(console: Any, *, actor_id: str, snapshot_id: str,
                              source_object_ids: Iterable[str], reason: str,
                              command_id: str, expected_revision: str) -> dict[str, Any]:
    """Confirm an exact non-knowledge batch in one existing workflow commit.

    Only proposed metadata/structure qualifies. Unformed substantive content
    needs the existing individual source-context/repair command. Model roles
    never close the passage register by themselves.
    """
    from contextlib import nullcontext
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT, utc_now
    from src.passage_register_v1 import passage_register_record
    from src.revision_workflow import bump_patch
    from src.source_accountability_v1 import evidence_of
    from src.workflows.workflow_transaction_v1 import workflow_transaction, workflow_transaction_active

    ids = sorted(set(source_object_ids))
    if (not ids or len(ids) > 4096 or any(not isinstance(oid, str) or not oid for oid in ids)
            or not reason.strip() or len(reason) > 4000 or not command_id.strip()
            or len(command_id) > 128 or not expected_revision):
        raise ConsoleError("source_context_command_required")
    documents = getattr(console, "workflow_document_store", None)
    reviews = getattr(console, "workflow_review_store", None)
    if (documents is None) != (reviews is None) or workflow_transaction_active():
        raise ConsoleError("source_context_independent_transaction_required")
    event_type = "source_exclusions_confirmed"
    payload_hash = stable_hash({"actor_id": actor_id, "snapshot_id": snapshot_id,
                               "source_object_ids": ids, "reason": reason.strip()})
    with console._store_write_lock():
        try:
            with workflow_transaction(reviews) if reviews is not None else nullcontext() as connection:
                if connection is not None:
                    connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                                       (snapshot_id,))
                console._reload_store_locked()
                reviewer = console._require_role(actor_id, "reviewer")
                envelope = console._envelope(snapshot_id)
                if actor_id not in (envelope.get("named_reviewers") or []):
                    raise ConsoleError("reviewer_not_named_on_snapshot")
                if console.snapshot_is_published(snapshot_id):
                    raise ConsoleError("published_working_revision_immutable")
                for event in read_events(console._ledger_path):
                    details = event.get("details") or {}
                    if (event.get("event_type") == event_type and details.get("snapshot_id") == snapshot_id
                            and details.get("command_id") == command_id):
                        if details.get("payload_hash") != payload_hash:
                            raise ConsoleError("source_context_command_conflict")
                        return {**deepcopy(details["result"]), "idempotent": True}
                current, revision = console.snapshot_objects_and_revision(snapshot_id)
                if revision != expected_revision:
                    raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
                by_id = {row["object_id"]: row for row in current}
                path, _ = console._verified_source_bytes(envelope)
                fragments = console._read_source_fragments(envelope, path)
                changed = []
                now = utc_now()
                for oid in ids:
                    source = by_id.get(oid)
                    evidence = evidence_of(source) if source else {}
                    if (not evidence or evidence["proposed_role"] not in {"metadata", "structure"}
                            or role_of(source) or links_of(source)
                            or source.get("confirmed_object_type")
                            or (source.get("governance") or {}).get("validation_status") != "needs_review"):
                        raise ConsoleError("source_exclusion_not_proposed")
                    console._require_open_original(snapshot_id, oid)
                    if not verify_literal_source(source, fragments, envelope["sha256"]):
                        raise ConsoleError("source_context_evidence_invalid")
                    updated = deepcopy(source)
                    updated["object_version"] = bump_patch(str(source["object_version"]))
                    metadata = updated.setdefault("metadata", {})
                    metadata[ROLE_KEY] = {"version": CONTRACT, "role": "excluded", "command_id": command_id,
                        "reviewer_id": actor_id, "reviewer": reviewer["username"], "reviewed_at": now,
                        "reason": reason.strip(), "literal_hash": literal_identity(source),
                        "source_sha256": envelope["sha256"]}
                    metadata["passage_register"] = passage_register_record(status="excluded_with_reason",
                        reason_codes=["reviewer_confirmed_source_role"], source="review")
                    governance = updated.setdefault("governance", {})
                    governance.update(validation_status="rejected", validated_by=reviewer["username"],
                        validation_date=now[:10], review_snapshot_hash=None, publication_status="unpublished")
                    second = governance.get("second_review")
                    if isinstance(second, dict) and second.get("required"):
                        second.update(status="pending", reviewer=None, review_date=None, snapshot_hash=None)
                    stamp_canonical_hashes(updated)
                    errors = schema_errors(updated, console.schema_path)
                    if errors:
                        raise ConsoleError("revision_schema_invalid", " | ".join(errors))
                    changed.append(updated)
                history = console._load_objects(snapshot_id, remember=False) + changed
                bindings = deepcopy(console._bindings)
                for oid in ids:
                    bindings[snapshot_id] = invalidate_for_object(bindings.get(snapshot_id, []), oid)
                result = {"snapshot_id": snapshot_id, "command_id": command_id, "idempotent": False,
                          "source_versions": {row["object_id"]: row["object_version"] for row in changed}}
                console._commit_prepared_store(objects=(snapshot_id, history), bindings=bindings,
                    snapshot_id=snapshot_id, expected_revision=revision,
                    ledger_fn=lambda: append_event(console._ledger_path, event_type=event_type,
                        object_id=ids[0], object_version=result["source_versions"][ids[0]], actor=reviewer["username"],
                        details={"snapshot_id": snapshot_id, "actor_account_id": actor_id,
                            "command_id": command_id, "payload_hash": payload_hash,
                            "reason": reason.strip(), "result": deepcopy(result)}))
            return result
        except Exception:
            console._reload_store_locked()
            remirror = getattr(console, "_remirror_review_runtime", None)
            if remirror is not None:
                remirror()
            raise


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

    if role not in {"label", "context", "excluded", "reset"}:
        raise ConsoleError("source_context_role_invalid")
    if not reason.strip() or len(reason) > 4000:
        raise ConsoleError("source_context_reason_required")
    if not command_id.strip() or len(command_id) > 128 or not expected_revision:
        raise ConsoleError("source_context_command_required")
    targets = sorted(set(str(value).strip() for value in target_object_ids if str(value).strip()))
    if len(targets) > 100 or (role in {"excluded", "reset"} and targets) or (role in {"label", "context"} and not targets):
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
        metadata = source_after.setdefault("metadata", {})
        metadata[ROLE_KEY] = {
            "version": CONTRACT, "role": role, "command_id": command_id,
            "reviewer_id": actor_id, "reviewer": reviewer["username"], "reviewed_at": now,
            "reason": reason.strip(), "literal_hash": literal_identity(source),
            "source_sha256": envelope["sha256"],
        }
        if role == "reset":
            metadata.pop(ROLE_KEY, None)
        source_after["metadata"]["passage_register"] = passage_register_record(
            status="not_yet_assessed" if role == "reset" else "excluded_with_reason" if role == "excluded" else "used_as_context",
            reason_codes=["reviewer_confirmed_source_role"], source="review",
        )
        governance = source_after.setdefault("governance", {})
        governance.update(validation_status="needs_review" if role == "reset" else "rejected",
                          validated_by=None if role == "reset" else reviewer["username"],
                          validation_date=None if role == "reset" else now[:10], review_snapshot_hash=None,
                          publication_status="unpublished")
        second = governance.get("second_review")
        if isinstance(second, dict) and second.get("required"):
            second.update(status="pending", reviewer=None, review_date=None, snapshot_hash=None)
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
        # Re-admit only the explicitly changed targets against verified source.
        # This is part of the same object/binding/audit transaction, no backfill.
        from src.admission_gate_v1 import apply_admission_gate
        path, data = console._verified_source_bytes(envelope)
        extracted = console._extract(envelope["content_kind"], path,
                                     document_id=envelope["document_id"], source_id=envelope["source_id"])
        if not verify_literal_source(source, extracted, envelope["sha256"]):
            raise ConsoleError("source_context_evidence_invalid")
        for oid, updated in changed.items():
            disposition = deepcopy(updated.get("governance") or {}) if oid == source_object_id else None
            updated = console._prepare_knowledge_revision(snapshot_id, by_id[oid], updated,
                reason="source-context change: " + reason.strip(), actor=reviewer["username"])
            if disposition is not None:
                updated["governance"] = disposition
            changed[oid] = updated
        proposed = [changed.get(row["object_id"], row) for row in current]
        gated = apply_admission_gate(proposed, klasse=envelope["class"], fragments=extracted,
                                     document_version=envelope["version"], source_hash=envelope["sha256"])
        from src.passage_register_v1 import apply_passage_register
        gated = apply_passage_register(gated)
        for row in gated:
            if row["object_id"] in changed and row["object_id"] != source_object_id:
                changed[row["object_id"]] = row
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
                  "affected_target_versions": {oid: row["object_version"] for oid, row in changed.items()
                                               if oid != source_object_id},
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


def verify_literal_source(obj: dict[str, Any], fragments: list[dict[str, Any]], source_hash: str) -> bool:
    """Reconstruct from source, never from a model's source_bound/status claim."""
    from src.object_taxonomy_v1 import normalize_visible_prose
    from src.knowledge_materialisation_v1 import _read_source_blocks
    from src.source_layout_v1 import mapped_raw_spans
    refs = (obj.get("provenance") or {}).get("source_fragments") or []
    by_id = {f.get("fragment_id"): f for f in fragments}
    if not source_hash or (obj.get("source") or {}).get("source_checksum") != source_hash or not refs:
        return False
    if any(r.get("raw_object_id") not in by_id or
           r.get("raw_content_hash") != by_id[r["raw_object_id"]].get("fragment_hash") for r in refs):
        return False
    if any(by_id[r["raw_object_id"]].get("source_id") is not None and
           by_id[r["raw_object_id"]]["source_id"] != (obj.get("source") or {}).get("source_id") for r in refs):
        return False
    text = str((obj.get("content") or {}).get("clean_text") or "")
    semantic = (obj.get("metadata") or {}).get("semantic_passage")
    if not semantic:
        # Legacy/source-unit correction: retain exact whole-fragment provenance.
        literal = normalize_visible_prose(" ".join(str(by_id[r["raw_object_id"]].get("clean_text") or
            by_id[r["raw_object_id"]].get("raw_text") or "") for r in refs))
        return normalize_visible_prose(text) == literal
    try:
        blocks = _read_source_blocks(fragments, include_headings=True)
        parts, mapping = [], []
        for span in semantic["spans"]:
            public, fragment = blocks[span["block_id"]]
            lo, hi = span["start"], span["end"]
            if type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= len(public["text"]):
                return False
            parts.append(public["text"][lo:hi])
            mapping.extend(mapped_raw_spans(fragment, start=lo, end=hi))
        if semantic.get("version") == "semantic-passage-v1.0.0":
            mapping = [row for row in mapping if row.get("kind") != "join_separator"]
        elif semantic.get("version") != "semantic-passage-v1.1.0":
            return False
        return (normalize_visible_prose(" ".join(parts)) == text and
                (semantic.get("source_mapping") == mapping or
                 (semantic.get("version") == "semantic-passage-v1.0.0" and "source_mapping" not in semantic)))
    except (KeyError, TypeError, ValueError):
        return False


def context_realization(candidate: dict[str, Any], *, obj: dict[str, Any] | None = None,
                        objects: Iterable[dict[str, Any]] = (),
                        fragments: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Check each identified requirement independently of scan dispositions.

    This proves realization of identified context, never completeness of detection.
    Client-supplied status booleans and linked-text claims are deliberately ignored.
    """
    from src.context_scan_v1 import required_context
    from src.object_taxonomy_v1 import normalize_visible_prose
    rows = list(objects)
    by_id = {r.get("object_id"): r for r in rows}
    source_hash = str(candidate.get("source_hash") or "")
    text = normalize_visible_prose(str(candidate.get("candidate_text") or ""))
    source = normalize_visible_prose(str(candidate.get("source_text_exact") or ""))
    valid_source = verify_literal_source(obj, fragments, source_hash) if obj is not None and fragments is not None else text in source
    if obj is not None and (obj.get('source') or {}).get('version') is not None:
        valid_source = valid_source and str(obj['source']['version']) == str(candidate.get('document_version'))
    linked = []
    issues = context_issues(rows) if rows else {}
    if obj is not None and not issues.get(str(obj.get("object_id") or "")):
        for link in links_of(obj):
            owner = by_id.get(link.get("source_object_id"))
            if (owner and fragments is not None and verify_literal_source(owner, fragments, source_hash)
                    and valid_source):
                linked.append(link)
    if obj is not None and fragments is not None and valid_source:
        linked.extend(source_bound_relation_context(obj, rows, fragments, source_hash))
    realized, unresolved = [], []
    from src.source_bound_fields_v2 import validated_context
    bound_context = []
    if obj is not None and fragments is not None:
        try:
            bound_context = validated_context(obj, fragments, source_hash)
        except (ValueError, KeyError, TypeError):
            valid_source = False
    for context in bound_context:
        row = {"role": context["role"], "origin": "source_bound_proposal", "text": context["text"], "span": context["span"]}
        if context["unresolved_reason"]:
            unresolved.append({**row, "reason": context["unresolved_reason"]})
        elif valid_source:
            realized.append({**row, "realization": "source_bound_context"})
    explicit_links = [r for r in bound_context if not r["unresolved_reason"] and r["role"] != "support"]
    for requirement in required_context(candidate.get("context_scan") or {}):
        literal = requirement["text"]
        if valid_source and literal in text:
            realized.append({**requirement, "realization": "inline"})
        else:
            explicit = next((entry for entry in explicit_links if literal in normalize_visible_prose(entry["text"])), None)
            binding = next((link for link in linked if literal in normalize_visible_prose(link["text"])), None)
            if valid_source and explicit:
                realized.append({**requirement, "realization": "source_bound_context", "span": explicit["span"]})
            elif valid_source and binding:
                realized.append({**requirement, "realization": "source_context_binding",
                                 "source_object_id": binding["source_object_id"],
                                 "source_object_version": binding["source_object_version"],
                                 "command_id": binding["command_id"]})
            else:
                unresolved.append({**requirement, "reason": "context_necessary_unresolved"})
    return {"version": "source-context-admission-v2", "object_id": candidate.get("candidate_id"),
            "object_version": obj.get("object_version") if obj else candidate.get("document_version"),
            "source_hash": source_hash, "literal_hash": literal_identity(obj) if obj else None,
            "realized": realized, "unresolved": unresolved,
            "source_integrity": "verified" if valid_source else "unverified",
            "detection_completeness": "not_proven"}


def source_bound_relation_context(obj: dict[str, Any], objects: list[dict[str, Any]],
                                  fragments: list[dict[str, Any]], source_hash: str) -> list[dict[str, Any]]:
    """Use existing applies_if/except_if proposal evidence, never bare relations."""
    from src.knowledge_relation_proposal_v1 import relation_proposal_admission_codes, relation_evidence_map
    from src.knowledge_relations_v1 import proposed_knowledge_relations_of
    from src.semantic_passage_v1 import _reconstructed_blocks, source_fragment_ids_for_text
    if relation_proposal_admission_codes(obj, objects=objects):
        return []
    by_id = {r.get('object_id'): r for r in objects}
    blocks = {p['block_id']: (p, f) for p, f in _reconstructed_blocks(fragments)}
    evidence = relation_evidence_map(obj)
    result = []
    for relation in proposed_knowledge_relations_of(obj):
        if relation.get('relation_type') not in {'applies_if', 'except_if'}:
            continue
        target = by_id.get(relation.get('target_object_id'))
        record = evidence.get(relation.get('relation_id'))
        if not target or not record or not verify_literal_source(target, fragments, source_hash):
            continue
        try:
            for field, owner in (('source_spans', obj), ('target_spans', target)):
                spans = record[field]
                declared = ((owner.get('metadata') or {}).get('semantic_passage') or {}).get('spans')
                if declared is None or [{k: r[k] for k in ('block_id', 'start', 'end')} for r in spans] != declared:
                    raise ValueError('relation_selection_mismatch')
            for span in record['source_spans'] + record['target_spans'] + record['evidence_spans']:
                p, f = blocks[span['block_id']]
                lo, hi = span['start'], span['end']
                if type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= len(p['text']):
                    raise ValueError('relation_bounds')
                if span['source_fragment_ids'] != source_fragment_ids_for_text(f, start=lo, end=hi):
                    raise ValueError('relation_source_mismatch')
        except (KeyError, ValueError, TypeError):
            continue
        result.append({'text': target['content']['clean_text'], 'source_object_id': target['object_id'],
                       'source_object_version': target['object_version'], 'command_id': relation['relation_id']})
    return result

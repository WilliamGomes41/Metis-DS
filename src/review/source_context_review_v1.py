"""Reviewer-owned literal source context in the existing versioned object store.

The target's hashed metadata owns its context evidence. Source role metadata
classifies the source fragment; incoming targets are derived, never a second
relation store. See docs/SOURCE_CONTEXT_REVIEW_CONTRACT.md.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from src.integrity_kernel import stable_hash, stamp_canonical_hashes, schema_errors
from src.publication.publish_authorization_v1 import invalidate_for_object
from src.review.review_ledger import append_event, read_events

ROLE_KEY = "source_role_review"
LINKS_KEY = "confirmed_source_context"
CONTRACT = "source-context-review-v1"
EVENT = "source_context_review"


def literal_identity(obj: dict[str, Any]) -> str:
    from src.review.review_card_facts_v1 import ReviewObjectFacts
    if isinstance(obj, ReviewObjectFacts):
        return obj.proof['literal_identity']
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
    needs the existing individual source-context/repair command or the
    section-bound group command below. Model roles never close the passage
    register by themselves.
    """
    from src.operations_console_v1 import ConsoleError
    from src.vorming.source_accountability_v1 import evidence_of

    ids = sorted(set(source_object_ids))
    if (not ids or len(ids) > 4096 or any(not isinstance(oid, str) or not oid for oid in ids)
            or not reason.strip() or len(reason) > 4000):
        raise ConsoleError("source_context_command_required")
    payload_hash = stable_hash({"actor_id": actor_id, "snapshot_id": snapshot_id,
                               "source_object_ids": ids, "reason": reason.strip()})

    def body(ctx):
        changed = []
        for oid in ids:
            source = ctx["by_id"].get(oid)
            evidence = evidence_of(source) if source else {}
            if not evidence or evidence["proposed_role"] not in {"metadata", "structure"} or not _open_source(source):
                raise ConsoleError("source_exclusion_not_proposed")
            changed.append(_excluded_version(console, ctx, source, reason=reason, command_id=command_id))
        result = {"snapshot_id": snapshot_id, "command_id": command_id, "idempotent": False,
                  "source_versions": {row["object_id"]: row["object_version"] for row in changed}}
        return changed, result, {"reason": reason.strip()}

    return _source_batch(console, actor_id=actor_id, snapshot_id=snapshot_id, command_id=command_id,
                         expected_revision=expected_revision, event_type="source_exclusions_confirmed",
                         payload_hash=payload_hash, body=body)


GROUP_EVENT = "source_group_confirmed"
GROUP_RESET_EVENT = "source_group_reset"
GROUP_MAX = 50


def group_members_hash(rows: Iterable[dict[str, Any]]) -> str:
    """What the reviewer saw: exact member identity, version and literal."""
    return stable_hash(sorted([str(row["object_id"]), str(row["object_version"]), literal_identity(row)]
                              for row in rows))


def source_group_candidates(objects: Iterable[dict[str, Any]], *, review_path: str = "richtlijn",
                            bindings=None, fragments=None) -> dict[tuple[tuple[str, ...], str], list[dict[str, Any]]]:
    """Open source passages per (exact section path, proposed reason), in source order (B6 3.1).

    A proposal, never a stored state: derived from the current objects on
    every read. Any model role qualifies here; closing needs a human command.
    """
    from src.vorming.source_containers_v1 import partition
    from src.vorming.source_accountability_v1 import evidence_of
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in partition(list(objects), review_path=review_path, bindings=bindings, fragments=fragments)["source"]:
        record = row["record"]
        if row["usage"]["human_action"] != "source_disposition" or not _open_source(record):
            continue
        # The model's proposed reason (unformed_meaning / uncertain_source_role), as shown.
        groups.setdefault((section_path_of(record), str(evidence_of(record).get("reason") or "")), []).append(record)
    return groups


def section_path_of(obj: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(part) for part in ((obj.get("structure") or {}).get("section_path")
                                        or (obj.get("metadata") or {}).get("section_path") or []))


def confirm_source_group(console: Any, *, actor_id: str, snapshot_id: str, section_path: Iterable[str],
                         group_reason: str, shown_object_ids: Iterable[str], source_object_ids: Iterable[str],
                         members_hash: str, reason: str, command_id: str,
                         expected_revision: str) -> dict[str, Any]:
    """Exclude a reviewer-confirmed group of open source passages in one section.

    The reviewer saw `shown_object_ids` (members_hash binds their exact
    versions and literals) and confirmed `source_object_ids`, the shown set
    minus what they marked as knowledge. All-or-nothing; max 50 members.
    """
    from src.operations_console_v1 import ConsoleError

    path = tuple(str(part) for part in section_path)
    shown = list(dict.fromkeys(str(oid) for oid in shown_object_ids))
    ids = sorted(set(str(oid) for oid in source_object_ids))
    if (not ids or len(shown) > GROUP_MAX or not set(ids) <= set(shown)
            or not members_hash or not reason.strip() or len(reason) > 4000):
        raise ConsoleError("source_group_command_invalid")
    payload_hash = stable_hash({"actor_id": actor_id, "snapshot_id": snapshot_id, "section_path": list(path),
                               "group_reason": group_reason, "shown": sorted(shown), "source_object_ids": ids,
                               "members_hash": members_hash, "reason": reason.strip()})

    def body(ctx):
        groups = source_group_candidates(ctx["current"], review_path=ctx["review_path"])
        eligible = {row["object_id"]: row for row in groups.get((path, group_reason), [])}
        if any(oid not in eligible for oid in shown):
            raise ConsoleError("source_group_members_changed")
        if group_members_hash(eligible[oid] for oid in shown) != members_hash:
            raise ConsoleError("source_group_members_changed")
        changed = [_excluded_version(console, ctx, eligible[oid], reason=reason, command_id=command_id, group=True)
                   for oid in ids]
        members = [{"object_id": row["object_id"], "old_version": eligible[row["object_id"]]["object_version"],
                    "new_version": row["object_version"], "literal_hash": literal_identity(row)} for row in changed]
        result = {"snapshot_id": snapshot_id, "command_id": command_id, "idempotent": False,
                  "section_path": list(path), "group_reason": group_reason, "members": members,
                  "source_versions": {row["object_id"]: row["object_version"] for row in changed}}
        return changed, result, {"reason": reason.strip(), "members_hash": members_hash}

    return _source_batch(console, actor_id=actor_id, snapshot_id=snapshot_id, command_id=command_id,
                         expected_revision=expected_revision, event_type=GROUP_EVENT,
                         payload_hash=payload_hash, body=body)


def reset_source_group(console: Any, *, actor_id: str, snapshot_id: str, group_command_id: str,
                       reason: str, command_id: str, expected_revision: str) -> dict[str, Any]:
    """Undo one confirmed group, only if no member changed since (B6 3.5)."""
    from src.operations_console_v1 import ConsoleError

    if not group_command_id.strip() or not reason.strip() or len(reason) > 4000:
        raise ConsoleError("source_group_command_invalid")
    payload_hash = stable_hash({"actor_id": actor_id, "snapshot_id": snapshot_id,
                               "group_command_id": group_command_id, "reason": reason.strip()})

    def body(ctx):
        group = next((event.get("details") or {} for event in read_events(console._ledger_path)
                      if event.get("event_type") == GROUP_EVENT
                      and (event.get("details") or {}).get("snapshot_id") == snapshot_id
                      and (event.get("details") or {}).get("command_id") == group_command_id), None)
        if group is None:
            raise ConsoleError("source_group_unknown")
        changed = []
        history = {(row["object_id"], row["object_version"]): row
                   for row in console._load_objects(snapshot_id, remember=False)}
        for member in group["result"]["members"]:
            current = ctx["by_id"].get(member["object_id"])
            role = role_of(current) if current else {}
            if (not current or current.get("object_version") != member["new_version"]
                    or role.get("command_id") != group_command_id or role.get("role") != "excluded"):
                raise ConsoleError("source_group_members_changed")
            prior = history.get((member["object_id"], member["old_version"]))
            if prior is None:
                raise ConsoleError("source_group_members_changed")
            updated = source_role_version(current, role="reset", command_id=command_id, actor_id=actor_id,
                                          reviewer=ctx["reviewer"]["username"], now=ctx["now"], reason=reason,
                                          source_sha256=ctx["envelope"]["sha256"])
            # Undo restores the pre-group register (e.g. extract-owned not_yet_assessed),
            # so machine and linked-target closure apply again exactly as before (3.5).
            restored = deepcopy((prior.get("metadata") or {}).get("passage_register"))
            if restored is None:
                updated["metadata"].pop("passage_register", None)
            else:
                updated["metadata"]["passage_register"] = restored
            changed.append(_sealed(console, updated))
        result = {"snapshot_id": snapshot_id, "command_id": command_id, "idempotent": False,
                  "group_command_id": group_command_id,
                  "source_versions": {row["object_id"]: row["object_version"] for row in changed}}
        return changed, result, {"reason": reason.strip(), "group_command_id": group_command_id}

    return _source_batch(console, actor_id=actor_id, snapshot_id=snapshot_id, command_id=command_id,
                         expected_revision=expected_revision, event_type=GROUP_RESET_EVENT,
                         payload_hash=payload_hash, body=body)


def source_role_version(source: dict[str, Any], *, role: str, command_id: str, actor_id: str, reviewer: str,
                        now: str, reason: str, source_sha256: str, group: bool = False) -> dict[str, Any]:
    """The source-role successor shared by the batch and group commands.

    It mirrors the single-passage command's own writer (_confirm_source_context);
    a test keeps both outcomes equal. Consolidating that writer here is a
    separate, high-rewrite-risk change.
    """
    from src.vorming.passage_register_v1 import passage_register_record
    from src.review.revision_workflow import bump_patch
    updated = deepcopy(source)
    updated["object_version"] = bump_patch(str(source["object_version"]))
    metadata = updated.setdefault("metadata", {})
    metadata[ROLE_KEY] = {
        "version": CONTRACT, "role": role, "command_id": command_id,
        "reviewer_id": actor_id, "reviewer": reviewer, "reviewed_at": now,
        "reason": reason.strip(), "literal_hash": literal_identity(source),
        "source_sha256": source_sha256,
    }
    if group:
        metadata[ROLE_KEY]["group"] = True
    if role == "reset":
        metadata.pop(ROLE_KEY, None)
    metadata["passage_register"] = passage_register_record(
        status="not_yet_assessed" if role == "reset" else "excluded_with_reason" if role == "excluded" else "used_as_context",
        reason_codes=["reviewer_confirmed_source_role"], source="review",
    )
    governance = updated.setdefault("governance", {})
    governance.update(validation_status="needs_review" if role == "reset" else "rejected",
                      validated_by=None if role == "reset" else reviewer,
                      validation_date=None if role == "reset" else now[:10], review_snapshot_hash=None,
                      publication_status="unpublished")
    second = governance.get("second_review")
    if isinstance(second, dict) and second.get("required"):
        second.update(status="pending", reviewer=None, review_date=None, snapshot_hash=None)
    return updated


def _open_source(source: dict[str, Any]) -> bool:
    return bool(source and not role_of(source) and not links_of(source)
                and not source.get("confirmed_object_type")
                and (source.get("governance") or {}).get("validation_status") == "needs_review")


def _excluded_version(console: Any, ctx: dict[str, Any], source: dict[str, Any], *, reason: str,
                      command_id: str, group: bool = False) -> dict[str, Any]:
    """The one exclusion write shared by the batch and the group command."""
    from src.operations_console_v1 import ConsoleError
    ctx["require_open_original"](source)
    if not verify_literal_source(source, ctx["fragments"], ctx["envelope"]["sha256"]):
        raise ConsoleError("source_context_evidence_invalid")
    updated = source_role_version(source, role="excluded", command_id=command_id, actor_id=ctx["actor_id"],
                                  reviewer=ctx["reviewer"]["username"], now=ctx["now"], reason=reason,
                                  source_sha256=ctx["envelope"]["sha256"], group=group)
    return _sealed(console, updated)


def _sealed(console: Any, updated: dict[str, Any]) -> dict[str, Any]:
    from src.operations_console_v1 import ConsoleError
    stamp_canonical_hashes(updated)
    errors = schema_errors(updated, console.schema_path)
    if errors:
        raise ConsoleError("revision_schema_invalid", " | ".join(errors))
    return updated


def _source_batch(console: Any, *, actor_id: str, snapshot_id: str, command_id: str, expected_revision: str,
                  event_type: str, payload_hash: str, body) -> dict[str, Any]:
    """One authorized, idempotent, revision-pinned commit of source-role writes."""
    from contextlib import nullcontext
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT, utc_now
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    from src.workflows.workflow_transaction_v1 import workflow_transaction, workflow_transaction_active

    if not command_id.strip() or len(command_id) > 128 or not expected_revision:
        raise ConsoleError("source_context_command_required")
    documents = getattr(console, "workflow_document_store", None)
    reviews = getattr(console, "workflow_review_store", None)
    if (documents is None) != (reviews is None) or workflow_transaction_active():
        raise ConsoleError("source_context_independent_transaction_required")
    with console._store_write_lock():
        try:
            with workflow_transaction(reviews) if reviews is not None else nullcontext() as connection:
                if connection is not None:
                    reviews._lock_authorizations(connection)
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
                path, freeze_bytes = console._verified_source_bytes(envelope)
                ctx = {"actor_id": actor_id, "snapshot_id": snapshot_id, "reviewer": reviewer,
                       "envelope": envelope, "current": current, "now": utc_now(),
                       "by_id": {row["object_id"]: row for row in current},
                       "fragments": console._read_source_fragments(envelope, path),
                       "review_path": review_path_for_klasse(envelope["class"])}
                # One source read and one PDF open per command, not per member:
                # per-member reopening held the transaction for minutes (incident 2026-10-30).
                with console._open_original_reader(envelope, freeze_bytes) as require_open_original:
                    ctx["require_open_original"] = require_open_original
                    changed, result, extra = body(ctx)
                history = console._load_objects(snapshot_id, remember=False) + changed
                bindings = deepcopy(console._bindings)
                for row in changed:
                    bindings[snapshot_id] = invalidate_for_object(bindings.get(snapshot_id, []), row["object_id"])
                first = changed[0]
                console._commit_prepared_store(objects=(snapshot_id, history), bindings=bindings,
                    snapshot_id=snapshot_id, expected_revision=revision,
                    ledger_fn=lambda: append_event(console._ledger_path, event_type=event_type,
                        object_id=first["object_id"], object_version=first["object_version"],
                        actor=reviewer["username"],
                        details={"snapshot_id": snapshot_id, "actor_account_id": actor_id,
                                 "command_id": command_id, "payload_hash": payload_hash,
                                 **extra, "result": deepcopy(result)}))
            return result
        except Exception:
            console._reload_store_locked()
            refresh = getattr(console, "_refresh_review_runtime", None)
            if refresh is not None:
                refresh()
            raise


def role_of(obj: dict[str, Any]) -> dict[str, Any]:
    row = (obj.get("metadata") or {}).get(ROLE_KEY)
    return deepcopy(row) if isinstance(row, dict) else {}


def links_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (obj.get("metadata") or {}).get(LINKS_KEY)
    return deepcopy([row for row in rows if isinstance(row, dict)]) if isinstance(rows, list) else []


def context_issues(objects: Iterable[dict[str, Any]]) -> dict[str, list[str]]:
    from src.review.review_card_facts_v1 import literal_link_matches, literal_refs_match
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
                and literal_link_matches(target, link, source)
                and literal_refs_match(target, link, source)
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


def _context_submission(*, actor_id, snapshot_id, source_object_id, role, target_object_ids,
                        reason, command_id, expected_revision):
    from src.operations_console_v1 import ConsoleError
    if role not in {'label', 'context', 'excluded', 'reset'}:
        raise ConsoleError('source_context_role_invalid')
    if not reason.strip() or len(reason) > 4000:
        raise ConsoleError('source_context_reason_required')
    if not command_id.strip() or len(command_id) > 128 or not expected_revision:
        raise ConsoleError('source_context_command_required')
    targets = sorted(set(str(value).strip() for value in target_object_ids if str(value).strip()))
    if len(targets) > 100 or (role in {'excluded', 'reset'} and targets) or (role in {'label', 'context'} and not targets):
        raise ConsoleError('source_context_target_required')
    payload_hash = stable_hash({'actor_id': actor_id, 'snapshot_id': snapshot_id,
        'source_object_id': source_object_id, 'role': role, 'targets': targets, 'reason': reason.strip()})
    return targets, payload_hash


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
    from src.review.review_command_v1 import execute_review_command
    targets, payload_hash = _context_submission(**command)
    command['target_object_ids'] = targets
    sid, oid = command['snapshot_id'], command['source_object_id']

    def completed(current):
        if command['actor_id'] not in current.get('named_reviewers', []):
            raise ConsoleError('reviewer_not_named_on_snapshot')
        if console.snapshot_is_published(sid):
            raise ConsoleError('published_working_revision_immutable')
        event = reviews.source_command_receipt(sid, EVENT, command['command_id'])
        if event is None:
            return None
        details = event['details']
        if details.get('payload_hash') != payload_hash:
            raise ConsoleError('source_context_command_conflict')
        return {**deepcopy(details['result']), 'idempotent': True}

    return execute_review_command(console, {'actor_id': command['actor_id'], 'snapshot_id': sid,
        'object_id': oid, 'expected_revision': command['expected_revision'],
        '_dependency_ids': targets, '_original_ids': [oid]},
        lambda internal: _confirm_source_context(console, **{**command,
            'expected_revision': internal['expected_revision']}), completed_command=completed)


def _confirm_source_context(console: Any, *, actor_id: str, snapshot_id: str,
                           source_object_id: str, role: str, target_object_ids: Iterable[str],
                           reason: str, command_id: str, expected_revision: str) -> dict[str, Any]:
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT, utc_now
    from src.review.revision_workflow import bump_patch
    from src.vorming.passage_register_v1 import passage_register_record

    targets, payload_hash = _context_submission(actor_id=actor_id, snapshot_id=snapshot_id,
        source_object_id=source_object_id, role=role, target_object_ids=target_object_ids,
        reason=reason, command_id=command_id, expected_revision=expected_revision)
    from src.review.review_command_state_v1 import active_review_command, review_bindings_view
    scoped = active_review_command(console, snapshot_id)
    with console._store_write_lock():
        console._reload_store_locked()
        reviewer = console._require_role(actor_id, "reviewer")
        envelope = console._envelope(snapshot_id)
        if actor_id not in (envelope.get("named_reviewers") or []):
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if console.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_working_revision_immutable")
        for event in [] if scoped is not None else read_events(console._ledger_path):
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
        from src.vorming.admission_gate_v1 import apply_admission_gate
        path, data = console._verified_source_bytes(envelope)
        extracted = scoped.inputs.fragments if scoped is not None else console._extract(envelope["content_kind"], path,
                                     document_id=envelope["document_id"], source_id=envelope["source_id"],
                                     assess_pages=envelope["class"] != "beslisboom",
                                     accounted_pages=envelope.get("source_page_accountings"))
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
        from src.vorming.passage_register_v1 import apply_passage_register
        gated = apply_passage_register(gated)
        for row in gated:
            if row["object_id"] in changed and row["object_id"] != source_object_id:
                changed[row["object_id"]] = row
        history = console._load_objects(snapshot_id, remember=False)
        bindings = deepcopy(review_bindings_view(console))
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


def verify_literal_source(obj: dict[str, Any], fragments: list[dict[str, Any]], source_hash: str,
                          *, source_blocks=None) -> bool:
    """Reconstruct from source, never from a model's source_bound/status claim.

    source_blocks may carry the caller's full-source view of these same,
    unchanged fragments; every check below still runs per object.
    """
    from src.review.review_card_facts_v1 import ReviewFactSources
    if isinstance(fragments, ReviewFactSources):
        return bool(source_hash and (obj.get('source') or {}).get('source_checksum') == source_hash
                    and fragments.proof_for(obj)['literal'])
    from src.object_taxonomy_v1 import normalize_visible_prose
    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
    from src.vorming.source_layout_v1 import mapped_raw_spans
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
        blocks = (source_blocks if source_blocks is not None
                  else _read_source_blocks(fragments, include_headings=True))
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
    from src.vorming.context_scan_v1 import required_context
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
    from src.vorming.source_bound_fields_v2 import validated_context
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
    from src.vorming.knowledge_relation_proposal_v1 import relation_proposal_admission_codes, relation_evidence_map
    from src.knowledge_relations_v1 import proposed_knowledge_relations_of
    from src.vorming.semantic_passage_v1 import _reconstructed_blocks, source_fragment_ids_for_text
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

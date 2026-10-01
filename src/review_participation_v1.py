"""Participation commands on the existing WorkingRevision transaction.

The envelope is authoritative. Governance is its checked projection; immutable
clinical payloads and exact approvals are never rebound to another identity.
"""
from copy import deepcopy
from typing import Any

from src.integrity_kernel import stable_hash, stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError, utc_now
from src.review_ledger import read_events, append_event
from src.review_policy_v1 import MANAGED_CONTRACT, participants, required_reviewers, validate_policy
from src.revision_workflow import bump_patch

EVENT = "review_participation_changed"


def execute(console, **command):
    documents = getattr(console, "workflow_document_store", None)
    reviews = getattr(console, "workflow_review_store", None)
    if documents is None and reviews is None:
        return _execute(console, **command)
    from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction, workflow_transaction_active
    if documents is None or reviews is None or workflow_transaction_active():
        raise ConsoleError("participation_independent_transaction_required")
    bind_workflow_stores(documents, reviews, getattr(console, "workflow_identity_store", None),
                         getattr(console, "workflow_remaining_store", None))
    with console._store_write_lock():
        try:
            with workflow_transaction(reviews) as connection:
                connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                                   (command["snapshot_id"],))
                return _execute(console, **command)
        except Exception:
            console._reload_store_locked()
            console._remirror_review_runtime()
            raise


def _reviewer(console, account_id):
    actor = console._require_role(account_id, "reviewer")
    from src.four_eyes_v1 import reviewer_is_agent
    if actor.get("retirement") or actor.get("blocked") or actor.get("disabled") or reviewer_is_agent(actor):
        raise ConsoleError("reviewer_unavailable")
    return actor


def _execute(console, *, actor_id: str, snapshot_id: str, command_id: str,
             expected_revision: str, reason: str, action: str, reviewer_id: str,
             replacement_id: str = "") -> dict[str, Any]:
    if not reason.strip() or not command_id.strip() or len(command_id) > 128 or not expected_revision:
        raise ConsoleError("participation_command_required")
    if action not in {"add_optional", "add_required", "archive", "replace"}:
        raise ConsoleError("participation_action_invalid")
    payload = dict(actor_id=actor_id, snapshot_id=snapshot_id, reason=reason, action=action,
                   reviewer_id=reviewer_id, replacement_id=replacement_id)
    payload_hash = stable_hash(payload)
    with console._store_write_lock():
        console._reload_store_locked()
        account = console._account(actor_id)
        if account.get("retirement") or account.get("blocked") or account.get("disabled"):
            raise ConsoleError("reviewer_unavailable")
        publisher = "publisher" in account["roles"]
        env = deepcopy(console._envelope(snapshot_id))
        if not publisher:
            _reviewer(console, actor_id)
            if actor_id not in env["named_reviewers"] or action != "add_optional" or reviewer_id == actor_id:
                raise ConsoleError("participation_publisher_required")
        if console.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_working_revision_immutable")
        for event in read_events(console._ledger_path):
            d = event.get("details") or {}
            if event.get("event_type") == EVENT and d.get("snapshot_id") == snapshot_id and d.get("command_id") == command_id:
                if d.get("payload_hash") != payload_hash:
                    raise ConsoleError("participation_command_conflict")
                return {**deepcopy(d["result"]), "idempotent": True}
        objects, revision = console.snapshot_objects_and_revision(snapshot_id)
        if revision != expected_revision:
            raise ConsoleError("snapshot_object_write_conflict", current_revision=revision)
        if not any(o["object_type"] == "document" for o in objects):
            raise ConsoleError("participation_document_not_ready")
        old = deepcopy(env.get("review_policy"))
        from src.review_policy_v1 import object_policy
        if any(object_policy(o) != old for o in objects):
            raise ConsoleError("review_policy_projection_mismatch")
        if old and old["contract"] == MANAGED_CONTRACT:
            policy = deepcopy(old)
        else:
            if not old and not publisher:
                raise ConsoleError("legacy_participation_activation_requires_publisher")
            from src.four_eyes_v1 import requires_four_eyes
            ids = list(dict.fromkeys(env["named_reviewers"]))
            if not ids:
                raise ConsoleError("review_primary_missing")
            policy = {"contract": MANAGED_CONTRACT, "revision": old["revision"] if old else 0,
                      "primary": old["primary"] if old else ids[0],
                      "assignments": [{**r, "status": "active"} for r in (old["assignments"] if old else
                          [{"reviewer_id": i, "participation": "required"} for i in ids[1:]])],
                      "review_basis": old,
                      "minimum_required": len(required_reviewers(old)) if old else
                          max(len(ids), 2 if any(requires_four_eyes(o) for o in objects) else 1)}
        rows = policy["assignments"]
        target = next((r for r in rows if r["reviewer_id"] == reviewer_id), None)
        before = deepcopy(policy)
        removed = set()
        if action.startswith("add_"):
            _reviewer(console, reviewer_id)
            if reviewer_id in participants(policy):
                raise ConsoleError("reviewer_already_assigned")
            if target and target["participation"] == "required" and action == "add_optional":
                raise ConsoleError("required_participation_cannot_be_downgraded")
            if target:
                rows.remove(target)
                removed.add(reviewer_id)  # a new participation never revives previous approvals
            rows.append({"reviewer_id": reviewer_id, "participation": action.removeprefix("add_"), "status": "active"})
        elif action == "archive":
            if reviewer_id == policy["primary"]:
                raise ConsoleError("primary_replacement_required")
            if not target or target["status"] != "active":
                raise ConsoleError("active_participation_required")
            target["status"] = "archived"
            removed.add(reviewer_id)
        else:
            if reviewer_id != policy["primary"] and not target:
                raise ConsoleError("participation_not_found")
            _reviewer(console, replacement_id)
            if replacement_id == reviewer_id or replacement_id in participants(policy) or any(r["reviewer_id"] == replacement_id and r["participation"] == "required" for r in rows):
                raise ConsoleError("independent_replacement_required")
            rows[:] = [r for r in rows if r["reviewer_id"] != replacement_id]
            if reviewer_id == policy["primary"]:
                policy["primary"] = replacement_id
            else:
                target["reviewer_id"] = replacement_id
                target["status"] = "active"
            removed.update({reviewer_id, replacement_id})
        policy["revision"] += 1
        try:
            validate_policy(policy)
        except ValueError as exc:
            raise ConsoleError(str(exc)) from exc
        # An unavailable existing person may remain an outstanding duty so that
        # a publisher can resolve several absences in separate safe commands.
        bindings = deepcopy(console._bindings)
        retired = [deepcopy(b) for b in bindings.get(snapshot_id, []) if b.get("reviewer_id") in removed]
        for b in bindings.get(snapshot_id, []):
            if b.get("reviewer_id") in removed:
                b["valid"] = False
        graph_reviews = env.get("decision_graph_reviews", [])
        retired_graph = [deepcopy(r) for r in graph_reviews if r["reviewer_id"] in removed]
        env["decision_graph_reviews"] = [r for r in graph_reviews if r["reviewer_id"] not in removed]
        history_entry = {**payload, "at": utc_now(), "command_id": command_id, "before": before,
                         "after": deepcopy(policy), "retired_bindings": retired, "retired_graph_reviews": retired_graph}
        env.setdefault("review_participation_history", []).append(history_entry)
        env["review_policy"] = policy
        env["named_reviewers"] = participants(policy)
        history = console._load_objects(snapshot_id, remember=False)
        current_keys = {(o["object_id"], o["object_version"]) for o in objects}
        document = None
        for o in history:
            if (o["object_id"], o["object_version"]) not in current_keys:
                continue
            if o["object_type"] == "document":
                document = deepcopy(o)
                continue
            o.setdefault("governance", {})["review_policy"] = deepcopy(policy)
        document["object_version"] = bump_patch(document["object_version"])
        document.setdefault("metadata", {})["participation_revision"] = command_id
        document.setdefault("governance", {})["review_policy"] = deepcopy(policy)
        stamp_canonical_hashes(document)
        history.append(document)
        envelopes = deepcopy(console._envelopes); envelopes[snapshot_id] = env
        result = {"snapshot_id": snapshot_id, "command_id": command_id, "policy_revision": policy["revision"], "idempotent": False}
        console._commit_prepared_store(objects=(snapshot_id, history), envelopes=envelopes, bindings=bindings,
            expected_revision=revision, snapshot_id=snapshot_id,
            ledger_fn=lambda: append_event(console._ledger_path, event_type=EVENT, object_id=snapshot_id,
                object_version="", actor=account["username"], details={**history_entry, "snapshot_id": snapshot_id,
                    "payload_hash": payload_hash, "result": result}))
        return result

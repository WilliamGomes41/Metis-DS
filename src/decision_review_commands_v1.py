"""Policy and graph commands use the existing snapshot transaction and audit log."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.decision_graph_v1 import graph_issues, review_target
from src.integrity_kernel import stable_hash, stamp_canonical_hashes
from src.review_ledger import append_event, read_events
from src.review_policy_v1 import participants, project_policy
from src.revision_workflow import bump_patch

EVENT = "decision_review_command"


def execute(console: Any, **command: Any) -> dict[str, Any]:
    from src.operations_console_v1 import ConsoleError
    documents = getattr(console, "workflow_document_store", None)
    reviews = getattr(console, "workflow_review_store", None)
    if documents is None and reviews is None:
        return _execute(console, **command)
    from src.workflows.workflow_transaction_v1 import workflow_transaction, workflow_transaction_active
    if documents is None or reviews is None or workflow_transaction_active():
        raise ConsoleError("decision_review_independent_transaction_required")
    with console._store_write_lock():
        try:
            with workflow_transaction(reviews) as connection:
                connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                                   (command["snapshot_id"],))
                result = _execute(console, **command)
            return result
        except Exception:
            console._reload_store_locked()
            console._remirror_review_runtime()
            raise


def _execute(console: Any, *, action: str, actor_id: str, snapshot_id: str,
             command_id: str, expected_revision: str, reason: str,
             policy: dict[str, Any] | None = None, graph: dict[str, Any] | None = None) -> dict[str, Any]:
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT, utc_now
    if not command_id.strip() or len(command_id) > 128 or not expected_revision or not reason.strip():
        raise ConsoleError("decision_review_command_required")
    payload_hash = stable_hash({"action": action, "actor": actor_id, "snapshot": snapshot_id,
                               "reason": reason, "policy": policy, "graph": graph})
    with console._store_write_lock():
        console._reload_store_locked()
        account = console._require_role(actor_id, "reviewer")
        envelope = deepcopy(console._envelope(snapshot_id))
        if actor_id not in envelope["named_reviewers"]:
            raise ConsoleError("reviewer_not_named_on_snapshot")
        if console.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_working_revision_immutable")
        for event in read_events(console._ledger_path):
            d = event.get("details") or {}
            if event.get("event_type") == EVENT and d.get("snapshot_id") == snapshot_id and d.get("command_id") == command_id:
                if d.get("payload_hash") != payload_hash:
                    raise ConsoleError("decision_review_command_conflict")
                return {**deepcopy(d["result"]), "idempotent": True}
        current, revision = console.snapshot_objects_and_revision(snapshot_id)
        if revision != expected_revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
        old_policy = envelope.get("review_policy")
        prior_graph_hash = stable_hash(envelope.get("decision_graph"))
        if action == "policy":
            # Ownership is the current primary; a publisher can also administer
            # participation, but must still possess reviewer rights here.
            owner = old_policy["primary"] if old_policy else envelope["uploader_account_id"]
            if actor_id != owner and "publisher" not in account["roles"]:
                raise ConsoleError("review_policy_owner_required")
            policy = console._validated_review_policy(policy)
            if policy["revision"] != (old_policy["revision"] + 1 if old_policy else 1):
                raise ConsoleError("review_policy_revision_conflict")
            envelope["review_policy"] = policy
            envelope["named_reviewers"] = participants(policy)
            envelope["decision_graph_reviews"] = []
        elif action not in {"graph", "confirm"} or not old_policy or "decision_graph" not in envelope:
            raise ConsoleError("decision_graph_not_available")
        bindings = deepcopy(console._bindings)
        history = console._load_objects(snapshot_id, remember=False)
        from src.decision_graph_v1 import verify_source_evidence
        try:
            verify_source_evidence(console, envelope)
        except ValueError as exc:
            raise ConsoleError(str(exc)) from exc
        changed_routes = {}
        if action == "confirm":
            graph = envelope["decision_graph"]
            issues = graph_issues(graph, current, envelope["decision_graph_evidence"])
            if issues:
                raise ConsoleError("decision_graph_incomplete", ",".join(issues))
            # Confirming routes cannot substitute for this person's passage review.
            from src.review_duty_v1 import exact_current_approver_ids
            from src.source_context_review_v1 import role_of
            for obj in current:
                if obj.get("object_type") == "document" or role_of(obj):
                    continue
                if actor_id not in exact_current_approver_ids(obj, console.object_review_bindings(snapshot_id)):
                    raise ConsoleError("decision_graph_passage_review_required")
            target = review_target(graph, current, old_policy)
            rows = envelope.get("decision_graph_reviews", [])
            envelope["decision_graph_reviews"] = [r for r in rows if r["reviewer_id"] != actor_id] + [
                {"reviewer_id": actor_id, "target": target, "at": utc_now(), "reason": reason}]
        elif action == "graph":
            issues = graph_issues(graph, current, envelope["decision_graph_evidence"])
            # Incomplete structure may be saved for repair, malformed or
            # ungrounded claims may not become a draft graph.
            invalid = [i for i in issues if any(t in i for t in ("invalid", "mismatch", "stale", "evidence_missing", "not_literal"))]
            if invalid:
                raise ConsoleError("decision_graph_invalid", ",".join(invalid))
            from src.decision_graph_v1 import route_contexts
            contexts = route_contexts(graph)
            changed_routes = {o["object_id"]: contexts[o["object_id"]] for o in current
                              if o["object_id"] in contexts and (o.get("metadata") or {}).get("route_context_hash") != contexts[o["object_id"]]}
            envelope["decision_graph"] = deepcopy(graph)
            envelope["decision_graph_reviews"] = []
        # A hash-bound document revision serializes envelope-only changes with
        # concurrent object/review/publication commands on every storage backend.
        updated = []
        for original in current:
            if action != "policy" and original.get("object_type") != "document" and original["object_id"] not in changed_routes:
                continue
            obj = deepcopy(original)
            obj["object_version"] = bump_patch(obj["object_version"])
            if obj["object_id"] in changed_routes:
                obj.setdefault("metadata", {})["route_context_hash"] = changed_routes[obj["object_id"]]
                for node in envelope["decision_graph"]["nodes"]:
                    if node["object_id"] == obj["object_id"]:
                        node["object_version"] = obj["object_version"]
            if action == "policy" or obj["object_id"] in changed_routes:
                project_policy([obj], policy if action == "policy" else old_policy)
                obj["governance"]["validation_status"] = "needs_review"
                for b in bindings.get(snapshot_id, []):
                    if b["object_id"] == obj["object_id"]:
                        b["valid"] = False
            if obj.get("object_type") == "document":
                obj.setdefault("metadata", {})["decision_review_revision"] = command_id
            stamp_canonical_hashes(obj)
            updated.append(obj)
        history.extend(updated)
        envelopes = deepcopy(console._envelopes)
        envelopes[snapshot_id] = envelope
        result = {"snapshot_id": snapshot_id, "action": action, "command_id": command_id, "idempotent": False}
        console._commit_prepared_store(objects=(snapshot_id, history), envelopes=envelopes,
            bindings=bindings, expected_revision=revision, snapshot_id=snapshot_id,
            ledger_fn=lambda: append_event(console._ledger_path, event_type=EVENT,
                object_id=snapshot_id, object_version="", actor=account["username"],
                details={"snapshot_id": snapshot_id, "command_id": command_id, "payload_hash": payload_hash,
                         "prior_graph_hash": prior_graph_hash, "graph_hash": stable_hash(envelope.get("decision_graph")),
                         "prior_policy": old_policy, "policy": envelope.get("review_policy"),
                         "reason": reason, "actor_account_id": actor_id, "result": result}))
        return result

"""Receive successor work under short parent registration/activation guards."""
from contextlib import nullcontext
from copy import deepcopy
from typing import Any


def _authorized(console, actor_id, envelope):
    from src.operations_console_v1 import ConsoleError
    actor = console._require_role(actor_id, "researcher")
    console._require_role(actor_id, "reviewer")
    policy = envelope.get("review_policy")
    owner = policy["primary"] if policy else envelope["uploader_account_id"]
    if actor_id != owner and "publisher" not in actor["roles"]:
        raise ConsoleError("review_policy_owner_required")


def assert_parent_current(console, envelope):
    """Activation already owns child transaction; also fence the parent writer."""
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    guard = envelope["successor_guard"]
    documents = getattr(console, "workflow_document_store", None)
    with workflow_transaction(documents) if documents is not None else nullcontext() as connection:
        if connection is not None:
            connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                               (guard["snapshot_id"],))
        parent = console._envelope(guard["snapshot_id"])
        _authorized(console, guard["actor_id"], parent)
        if (console.objects_revision(parent["snapshot_id"]) != guard["revision"]
                or parent.get("review_policy") != guard["policy"]
                or parent["sha256"] != guard["source_hash"]
                or parent["version"] != guard["source_version"]):
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)


def execute(console: Any, *, actor_id: str, snapshot_id: str, command_id: str,
            expected_revision: str, reason: str, policy: dict | None = None,
            class_: str | None = None, receive_only: bool = False) -> dict:
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
    from src.workflows.workflow_transaction_v1 import bind_workflow_stores
    if not reason.strip() or not command_id.strip() or not expected_revision:
        raise ConsoleError("decision_review_command_required")
    documents = getattr(console, "workflow_document_store", None)
    if documents is not None:
        reviews = getattr(console, "workflow_review_store", None)
        if reviews is None:
            raise ConsoleError("decision_review_independent_transaction_required")
        bind_workflow_stores(documents, reviews, getattr(console, "workflow_identity_store", None),
                             getattr(console, "workflow_remaining_store", None))
    # Read/verify bytes outside the parent row lock. Registration rechecks the
    # exact parent revision and policy; neither published history nor review is
    # mutated by this command.
    console.list_envelopes()
    env = deepcopy(console._envelope(snapshot_id))
    _authorized(console, actor_id, env)
    successor_policy = deepcopy(policy or env.get("review_policy"))
    if successor_policy is None:
        raise ConsoleError("explicit_review_policy_required")
    if policy is None:
        successor_policy["revision"] += 1
    successor_policy = console._validated_review_policy(successor_policy)
    if successor_policy["revision"] != ((env.get("review_policy") or {}).get("revision", 0) + 1):
        raise ConsoleError("review_policy_revision_conflict")
    path, data = console._verified_source_bytes(env)

    def guard(prepared):
        parent = console._envelope(snapshot_id)
        _authorized(console, actor_id, parent)
        if (console.objects_revision(snapshot_id) != expected_revision
                or parent.get("review_policy") != env.get("review_policy")
                or parent["sha256"] != env["sha256"] or parent["version"] != env["version"]):
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
        for candidate in console.list_envelopes():
            if (candidate.get("replaces_snapshot_id") == snapshot_id
                    and candidate.get("review_policy") == successor_policy
                    and candidate["class"] == prepared["class"]
                    and not console.snapshot_is_published(candidate["snapshot_id"])):
                raise ConsoleError("review_successor_already_exists")
        prepared["successor_guard"] = {"snapshot_id": snapshot_id, "revision": expected_revision,
                                       "policy": deepcopy(parent.get("review_policy")), "actor_id": actor_id,
                                       "source_hash": parent["sha256"], "source_version": parent["version"]}

    receipt = console.ingest(actor_id=actor_id, ingest_kind="new_version", title=env["title"],
        version=env["version"], date=env["date"], live_url=env.get("live_url") or "",
        class_=class_ or env["class"], family=env["family"], named_reviewers=[],
        filename=path.name, data=data, replaces_snapshot_id=snapshot_id,
        review_policy=successor_policy, source_status=env.get("source_declaration", {}).get("status", "unknown"),
        command_id=command_id, revision_reason=reason, _receive_only=True,
        _registration_boundary=lambda: console._reprocessing_transaction(snapshot_id), _registration_guard=guard)
    if receive_only or console.snapshot_objects(receipt["snapshot_id"]):
        return receipt
    # Synchronous kernel compatibility. The HTTP form uses receive_only and a
    # later explicit selection command instead. No outer lock wraps preparation.
    sid = receipt["snapshot_id"]
    attempt, fresh = console.reserve_source_selection(actor_id=actor_id, snapshot_id=sid,
        command_id="successor-" + command_id[:118], expected_revision=console.objects_revision(sid))
    return console.execute_source_selection(actor_id=actor_id, snapshot_id=sid, attempt=attempt) if fresh else receipt

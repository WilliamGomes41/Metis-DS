"""Explicit successor work reuses immutable source and the existing ingest lineage."""
from contextlib import nullcontext
from copy import deepcopy
from typing import Any


def execute(console: Any, *, actor_id: str, snapshot_id: str, command_id: str,
            expected_revision: str, reason: str, policy: dict | None = None,
            class_: str | None = None) -> dict:
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
    from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction
    documents = getattr(console, "workflow_document_store", None)
    reviews = getattr(console, "workflow_review_store", None)
    if not reason.strip() or not command_id.strip() or not expected_revision:
        raise ConsoleError("decision_review_command_required")
    if documents is not None:
        if reviews is None:
            raise ConsoleError("decision_review_independent_transaction_required")
        bind_workflow_stores(documents, reviews, getattr(console, "workflow_identity_store", None),
                             getattr(console, "workflow_remaining_store", None))
    with console._store_write_lock():
        try:
            with workflow_transaction(documents) if documents is not None else nullcontext() as connection:
                if connection is not None:
                    connection.execute("SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE", (snapshot_id,))
                console._reload_store_locked()
                actor = console._require_role(actor_id, "researcher")
                console._require_role(actor_id, "reviewer")
                env = console._envelope(snapshot_id)
                prior_policy = env.get("review_policy")
                owner = prior_policy["primary"] if prior_policy else env["uploader_account_id"]
                if actor_id != owner and "publisher" not in actor["roles"]:
                    raise ConsoleError("review_policy_owner_required")
                if console.objects_revision(snapshot_id) != expected_revision:
                    raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                successor_policy = deepcopy(policy or prior_policy)
                if successor_policy is None:
                    raise ConsoleError("explicit_review_policy_required")
                if policy is None:
                    successor_policy["revision"] += 1
                successor_policy = console._validated_review_policy(successor_policy)
                if successor_policy["revision"] != (prior_policy["revision"] + 1 if prior_policy else 1):
                    raise ConsoleError("review_policy_revision_conflict")
                path, data = console._verified_source_bytes(env)
                return console.ingest(actor_id=actor_id, ingest_kind="new_version", title=env["title"],
                    version=env["version"], date=env["date"], live_url=env.get("live_url") or "",
                    class_=class_ or env["class"], family=env["family"], named_reviewers=[],
                    filename=path.name, data=data, replaces_snapshot_id=snapshot_id,
                    review_policy=successor_policy, source_status=env.get("source_declaration", {}).get("status", "unknown"),
                    command_id=command_id, revision_reason=reason)
        except Exception:
            if documents is not None:
                console._reload_store_locked()
                console._remirror_review_runtime()
            raise

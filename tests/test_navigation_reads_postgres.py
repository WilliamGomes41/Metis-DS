"""Native PostgreSQL proof for bounded explicit-policy navigation (#490).

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.console_performance_v1 import performance_scope
from src.review_policy_v1 import CONTRACT, project_policy
from src.publish_authorization_v1 import tuple_record
from src.review_workboard_v1 import review_workboard_items
from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores
from tests.test_console_badge_counts_postgres_v1 import ROOT, _envelope
from tests.test_console_navigation_performance import NavigationProbe
from tests.test_review_workboard_heading_advance_postgres_v1 import workflow_postgres


@pytest.mark.parametrize("object_count", [2, 200])
def test_native_navigation_count_matches_workboard_with_five_connections(
    tmp_path, workflow_postgres, object_count,
):
    identity = PostgresWorkflowIdentityStore(workflow_postgres)
    documents = PostgresConcurrentWorkflowDocumentStore(workflow_postgres)
    reviews = PostgresWorkflowReviewStore(workflow_postgres)
    remaining = PostgresWorkflowRemainingStore(workflow_postgres)
    bind_workflow_stores(identity, documents, reviews, remaining)
    console = FastBadgePostgresCompleteWorkflowDurablePublicationConsole(
        root=ROOT, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
        canonical_publication_store=None, immutable_source_store=None,
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews, workflow_remaining_store=remaining,
    )
    accounts = [console.create_account(username=f"synthetic-reviewer-{i}",
                                      password=__name__, roles=["reviewer", "researcher"])
                for i in range(2)]
    primary, secondary = [a["account_id"] for a in accounts]
    fixture = NavigationProbe(count=object_count)
    policy = {"contract": CONTRACT, "revision": 1, "primary": primary,
              "assignments": [{"reviewer_id": secondary, "participation": "required"}]}
    for n, (sid, objects) in enumerate(fixture.objects.items()):
        envelope = _envelope(snapshot_id=sid, token=str(n) * 32, account_id=primary, reviewer=True)
        envelope["named_reviewers"] = [primary, secondary]
        envelope["review_policy"] = deepcopy(policy)
        project_policy(objects, policy)
        documents.write_bundle(envelope=envelope, objects=objects)

    account = console._account(primary)
    expected = sum(item["work_state"] in {"review", "disposition", "technical_repair"}
                   for item in review_workboard_items(console, account=account))
    with performance_scope() as metrics:
        counts = console.waiting_task_counts(primary)
    assert counts["review"] == expected == 2
    assert metrics.connections == 5 and metrics.queries == 5
    for sid, objects in fixture.objects.items():
        obj = objects[0]
        reviews.replace_snapshot_bindings(sid, [tuple_record(
            object_id=obj["object_id"], object_version=obj["object_version"],
            canonical_object_hash=obj["provenance"]["canonical_object_hash"],
            confirmed_object_type="recommendation", reviewer="synthetic-reviewer-0",
            reviewer_id=primary, decision="approve")])
    with performance_scope() as metrics:
        scoped = reviews.read_bindings(["synthetic-0"])
    assert set(scoped) == {"synthetic-0"}
    assert metrics.connections == 1 and metrics.queries == 1
    reviews.replace_snapshot_bindings("synthetic-1", [])

    # A new independent read must observe a changed pre-review outcome.
    envelope = documents.get_envelope("synthetic-0")
    from src.operations_console_v1 import PRE_REVIEW_BLOCKED
    envelope["publication_eligibility"] = PRE_REVIEW_BLOCKED
    documents.write_bundle(envelope=envelope, objects=documents.list_document_objects("synthetic-0"))
    assert console.waiting_task_counts(primary)["review"] == 1

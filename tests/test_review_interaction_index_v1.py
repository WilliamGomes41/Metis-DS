"""Global interaction identity stays indexed without changing audit authority.

# release-control-evidence: scope/belofte opslag kwaliteit metrics slop releasebewijs
"""
from pathlib import Path

import psycopg
import pytest

from src.review.review_interaction_v1 import validate_review_interaction_identity
from src.workflows.workflow_transaction_v1 import workflow_transaction
from tests.test_review_command_storage_v1 import seed
from tests.test_workflow_postgres_concurrency import _envelope, _objects


def test_native_global_interaction_lookup_uses_additive_index(complete_postgres, monkeypatch):
    documents, reviews, sid, reviewer = seed(complete_postgres)
    other_sid = "snap-index-target"
    envelope = documents.get_envelope(sid)
    documents.write_bundle(envelope=_envelope(other_sid, envelope["uploader_account_id"], reviewer),
                           objects=_objects("target"))
    with workflow_transaction(reviews):
        with reviews.buffered():
            for number in range(2000):
                details = {"snapshot_id": sid, "number": number}
                if number % 2:
                    details["review_interaction"] = {"interaction_id": f"noise-{number}"}
                reviews.append_event(event_type="synthetic-index-workload", object_id="delta-b", object_version="1.0",
                                     actor="reviewer", details=details)
    identity = {"interaction_id": "global-collision", "reviewer_account_id": reviewer,
                "snapshot_id": sid, "canonical_task": "passage"}
    foreign = reviews.append_event(event_type="review", object_id="delta-a", object_version="1.0",
        actor="reviewer", details={"snapshot_id": sid, "review_interaction": identity})
    local = reviews.append_event(event_type="review", object_id="target-a", object_version="1.0",
        actor="reviewer", details={"snapshot_id": other_sid})
    migration = Path(__file__).resolve().parents[1] / "db/migrations/025_review_interaction_identity_lookup.sql"
    with reviews._connect() as con:
        before = con.execute("SELECT event_id,event_hash,ctid::text AS physical,xmin::text AS writer "
                             "FROM workflow.review_events ORDER BY event_id").fetchall()
        con.execute(migration.read_text())
        con.execute(migration.read_text())
        assert con.execute("SELECT event_id,event_hash,ctid::text AS physical,xmin::text AS writer "
                           "FROM workflow.review_events ORDER BY event_id").fetchall() == before
        index = con.execute(
            "SELECT i.indisunique,i.indisvalid,pg_get_expr(i.indpred,i.indrelid) AS predicate "
            "FROM pg_index i WHERE i.indexrelid='workflow.workflow_review_events_interaction_identity'::regclass"
        ).fetchone()
        assert not index["indisunique"] and index["indisvalid"] and "IS NOT NULL" in index["predicate"]
        con.execute("ANALYZE workflow.review_events")

    captured = []
    original = psycopg.Cursor.execute
    def observe(cursor, query, params=None, *args, **kwargs):
        if isinstance(query, str) and query.startswith("SELECT event_payload FROM workflow.review_events WHERE "):
            captured.append((query, params))
        return original(cursor, query, params, *args, **kwargs)
    monkeypatch.setattr(psycopg.Cursor, "execute", observe)
    result = reviews.read_review_command_events(other_sid, ["target-a"], interaction_id="global-collision")
    assert result == [foreign, local]
    with pytest.raises(ValueError, match="review_interaction_identity_conflict"):
        validate_review_interaction_identity({**identity, "snapshot_id": other_sid}, result)
    assert len(captured) == 1
    query, parameters = captured[0]
    with reviews._connect() as con:
        plan = con.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + query, parameters).fetchone()["QUERY PLAN"][0]["Plan"]
    def nodes(node):
        yield node
        for child in node.get("Plans", []):
            yield from nodes(child)
    plans = list(nodes(plan))
    assert any(node.get("Index Name") == "workflow_review_events_interaction_identity" for node in plans), plan
    assert not any(node.get("Node Type") == "Seq Scan" and node.get("Relation Name") == "review_events" for node in plans), plan

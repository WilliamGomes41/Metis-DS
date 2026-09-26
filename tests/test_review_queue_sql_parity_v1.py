"""Execute the production summary SQL against PostgreSQL, compare object sets.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from contextlib import contextmanager
from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.publication_readiness_v1 import review_followup_queues
from src.review_duty_v1 import reviewer_route_for, reviewer_route_counts
from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
from tests.test_vsa_review_workboard_v1 import _obj


@pytest.fixture
def summary_database():
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN required for PostgreSQL queue parity")
    import psycopg
    from psycopg.rows import dict_row
    schema = "review_parity_" + uuid4().hex
    con = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
    con.execute(f"CREATE SCHEMA {schema}")
    # Isolated test schema: only columns consumed by the read-only query.
    definitions = {
        "documents": "snapshot_id text, class text, envelope_payload jsonb, publication_eligibility text",
        "document_reviewers": "snapshot_id text, account_id text",
        "document_objects": "snapshot_id text, object_id text, position int, payload jsonb",
        "accounts": "account_id text, username text, display_name text",
        "publish_authorizations": "snapshot_id text, object_id text, reviewer_account_id text, valid bool, decision text, object_version text, canonical_object_hash text, confirmed_object_type text",
    }
    for table, columns in definitions.items():
        con.execute(f"CREATE TABLE {schema}.{table} ({columns})")
    captured = {}

    def execute(sql, params):
        sql = sql.replace("workflow.", f"{schema}.")
        captured.update(sql=sql, params=params)
        return con.execute(sql, params)

    @contextmanager
    def connect():
        yield SimpleNamespace(execute=execute)

    subject = _PostgresBadgeCountsMixin()
    subject.workflow_document_store = SimpleNamespace(_connect=connect)
    try:
        yield con, schema, subject, captured
    finally:
        con.execute(f"DROP SCHEMA {schema} CASCADE")
        con.close()


@pytest.mark.parametrize("kind", ["richtlijn", "beslisboom"])
def test_sql_sets_match_domain_queues_including_missing_admission(summary_database, kind):
    from psycopg.types.json import Jsonb
    con, schema, subject, captured = summary_database
    path = "boom" if kind == "beslisboom" else "tekst"
    objects = [_obj(f"allowed-{i}", "recommendation") for i in range(5)]
    objects += [_obj(f"missing-{i}", "recommendation", gate_result=None) for i in range(338)]
    objects += [
        _obj("heading", "heading", gate_result=None),
        _obj("path", "path", gate_result=None),
        _obj("blocked", "recommendation", gate_result="blocked"),
        _obj("confirmed", "explanation", gate_result=None),
        _obj("batch", "definition"),
        _obj("relations", "definition"),
        _obj("second", "exception"),
        _obj("second-missing", "exception", gate_result=None),
        _obj("stale-governance", "definition", validation_status="approved"),
        _obj("revised", "recommendation", validation_status="revise"),
        _obj("invalid-register", "recommendation", gate_result=None),
        _obj("superseded-invalid-register", "recommendation", gate_result=None, validation_status="superseded"),
        _obj("excluded", "recommendation", gate_result="blocked", validation_status="rejected"),
        _obj("risk-flag-only", "definition"),
        _obj("risk-unknown-field", "definition"),
        _obj("risk-logic", "definition"),
        _obj("risk-metadata", "definition"),
        _obj("empty-section", "definition", section_path=[" "]),
        _obj("unknown-gate", "recommendation", gate_result="unknown"),
    ]
    for obj in objects:
        obj.update(object_version="1.0", provenance={"canonical_object_hash": obj["object_id"]})
    by_id = {o["object_id"]: o for o in objects}
    for object_id in ("confirmed", "second", "second-missing"):
        by_id[object_id]["confirmed_object_type"] = by_id[object_id]["object_type"]
    by_id["relations"]["proposed_knowledge_relations"] = [{"relation_type": "supported_by"}]
    by_id["risk-flag-only"]["risk"] = {"requires_second_review": True}
    by_id["risk-unknown-field"]["risk"] = {"risk_fields": ["not-a-risk-field"]}
    by_id["risk-logic"]["logic"] = {"score_points": 0}
    by_id["risk-metadata"]["metadata"]["dosage"] = "5 mg"
    for object_id in ("invalid-register", "superseded-invalid-register"):
        by_id[object_id]["metadata"]["passage_register"] = {}
    by_id["excluded"]["metadata"]["passage_register"].update(status="excluded_with_reason", source="review")
    bindings = []
    for object_id in ("second", "second-missing", "risk-flag-only", "risk-unknown-field", "risk-logic", "risk-metadata"):
        bindings.append(dict(object_id=object_id, object_version="1.0", canonical_object_hash=object_id,
                             confirmed_object_type=by_id[object_id].get("confirmed_object_type", ""), reviewer_id="a", valid=True, decision="approve"))
    envelope = dict(snapshot_id="snap", title="Parity", version="1.0", **{"class": kind})
    con.execute(f"INSERT INTO {schema}.documents VALUES (%s,%s,%s,%s)", ("snap", kind, Jsonb(envelope), "blocked_pending_review"))
    for actor in ("a", "b"):
        con.execute(f"INSERT INTO {schema}.accounts VALUES (%s,%s,%s)", (actor, actor, actor))
        con.execute(f"INSERT INTO {schema}.document_reviewers VALUES (%s,%s)", ("snap", actor))
    # An older allowed version must not hide the current missing Admission.
    older = deepcopy(by_id["missing-0"])
    older["metadata"]["admission"] = {"gate_result": "allowed"}
    for position, obj in enumerate([older, *objects]):
        con.execute(f"INSERT INTO {schema}.document_objects VALUES (%s,%s,%s,%s)", ("snap", obj["object_id"], position, Jsonb(obj)))
    for binding in bindings:
        con.execute(f"INSERT INTO {schema}.publish_authorizations VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    ("snap", binding["object_id"], "a", True, "approve", "1.0", binding["canonical_object_hash"], binding["confirmed_object_type"]))
    for actor in ("a", "b"):
        summary = subject.review_workboard_summaries(actor, "snap")["snap"]
        expected = reviewer_route_counts(objects, review_path=path, reviewer_id=actor, bindings=bindings)
        for key, value in expected.items():
            assert summary[key] == value, (kind, actor, key)
        # Query the actual production CTE rows rather than infer sets from totals.
        ctes = captured["sql"].rsplit("SELECT a.snapshot_id,", 1)[0]
        rows = con.execute(ctes + "SELECT * FROM duty_rows", captured["params"]).fetchall()
        for task, predicate in {
            "structure": lambda r: r["structure_review_duty"] and r["first_review_open"],
            "contextual": lambda r: r["contextual_review_duty"] and r["first_review_open"],
            "batch": lambda r: r["batch_review_duty"],
            "second_review": lambda r: r["second_review_open"] and not r["reviewer_has_approved"],
        }.items():
            sql_ids = {r["object_id"] for r in rows if predicate(r)}
            python_ids = {o["object_id"] for o in objects
                          if (route := reviewer_route_for(o, review_path=path, reviewer_id=actor, bindings=bindings))
                          and route["actionable"] and route["canonical_task"] == task}
            assert sql_ids == python_ids, (kind, actor, task, sql_ids ^ python_ids)
        followups = review_followup_queues(objects, review_path=path, bindings=bindings)
        assert summary["blocked_count"] == len(followups["repair"])
        assert summary["closure_gap_count"] == len(followups["disposition"])
        for task in ("repair", "disposition"):
            sql_ids = {
                r["object_id"] for r in rows
                if r["unresolved_closure"] and not r["review_duty_open"]
                and ((not r["boom"] and r["gate_result"] == "blocked") == (task == "repair"))
            }
            assert sql_ids == {obj["object_id"] for obj in followups[task]}

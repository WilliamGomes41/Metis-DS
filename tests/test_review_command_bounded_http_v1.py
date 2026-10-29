"""Real task-v1 POSTs reject document-wide storage work and preserve peers.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit metrics slop releasebewijs
"""
from contextlib import contextmanager
import html
import re

from fastapi.testclient import TestClient
import pytest

from tests.test_review_formation_problems import FIRST, SECOND, execute, received


def submission(page, sid, obj, comment="bounded native draft"):
    revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text)
    assert revision and revision.group(1).startswith("review-generation-v1:")
    return {"snapshot_id": sid, "object_id": obj["object_id"], "snapshot_revision": revision.group(1),
            "suitability": "ja", "documentpositie_action": "dit_klopt", "type_action": "dit_klopt",
            "confirmed_object_type": "recommendation", "eindoordeel": "goedkeuren", "decision": "approve",
            "recommendation_direction": "against" if "geen" in obj["content"]["clean_text"] else "for",
            "recommendation_strength_level": "not_stated", "relation_review_ack": "1", "comment": comment}


def physical_state(console, sid):
    with console.workflow_document_store._connect() as con:
        objects = con.execute(
            "SELECT object_id,object_version,position,payload,ctid::text AS physical,xmin::text AS writer "
            "FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position", (sid,),
        ).fetchall()
        bindings = con.execute(
            "SELECT authorization_id,object_id,position,authorization_payload,ctid::text AS physical,xmin::text AS writer "
            "FROM workflow.publish_authorizations WHERE snapshot_id=%s ORDER BY position NULLS LAST,authorization_id", (sid,),
        ).fetchall()
        document = con.execute(
            "SELECT revision,object_generation,envelope_payload FROM workflow.documents WHERE snapshot_id=%s", (sid,),
        ).fetchone()
    return {"objects": objects, "bindings": bindings, "document": document}


@contextmanager
def bounded_post_only(console, sid, monkeypatch):
    """A query guard surrounds only the request whose boundedness is promised."""
    documents, reviews = console.workflow_document_store, console.workflow_review_store
    with monkeypatch.context() as guard:
        def forbidden(name):
            def fail(*args, **kwargs):
                raise AssertionError("Unbounded Review POST call: " + name)
            return fail
        for name in ("list_document_objects", "objects_revision", "write_bundle"):
            guard.setattr(documents, name, forbidden(name))
        guard.setattr(reviews, "read_events", forbidden("read_events"))
        original = reviews.read_bindings
        def scoped_bindings(snapshot_ids=None, *, object_ids=None):
            assert snapshot_ids == [sid], "Unscoped Review POST binding snapshots"
            assert object_ids is not None, "Unscoped Review POST binding objects"
            return original(snapshot_ids, object_ids=object_ids)
        guard.setattr(reviews, "read_bindings", scoped_bindings)
        yield


@pytest.mark.parametrize("size", [32, 128])
def test_native_compact_post_is_bounded_and_preserves_independent_rows(
    tmp_path, production_console, production_app, monkeypatch, size,
):
    texts = [FIRST, SECOND, *[f"Gebruik geen middel {i:04d} bij deze synthetische situatie; "
        "bespreek de beschreven waarneming en leg de gemaakte keuze vast volgens deze afzonderlijke passage."
        for i in range(size - 2)]]
    source = ("<html><body><h1>Adviezen</h1>" + "".join(f"<p>{text}</p>" for text in texts)
              + "</body></html>").encode()
    console, sid, author, _reviewer, _calls, mode, _provider = received(
        tmp_path, production_console, monkeypatch, source_html=source, all_blocks=True)
    mode["broken"] = False
    execute(console, sid, author, "native-bounded-post-proof")
    candidates = [obj for obj in console.snapshot_objects(sid) if obj.get("proposed_object_type") == "recommendation"]
    assert len(candidates) == size
    focal = next(obj for obj in candidates if obj["content"]["clean_text"] == FIRST)
    second = next(obj for obj in candidates if obj["content"]["clean_text"] == SECOND)
    independent = candidates[-1]
    draft = '</textarea><img src=x onerror="alert(1)"><b>native draft & "choice"</b>'
    with TestClient(production_app(console), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "fixture-only"},
                           follow_redirects=False).status_code == 303
        # Seed a genuine independent approval before the guarded requests.
        other_page = client.get("/review", params={"document": sid, "object": independent["object_id"]})
        assert other_page.status_code == 200
        assert client.post("/review", data=submission(other_page, sid, independent),
                           follow_redirects=False).status_code == 303
        page = client.get("/review", params={"document": sid, "object": focal["object_id"]})
        assert page.status_code == 200
        data = submission(page, sid, focal, draft)
        before = physical_state(console, sid)
        assert any(row["object_id"] == independent["object_id"] for row in before["bindings"])
        with bounded_post_only(console, sid, monkeypatch):
            refused = client.post("/review", data={**data, "source_discrepancy": "context_ontbreekt"},
                                  follow_redirects=False)
        assert refused.status_code == 400
        assert html.escape(draft, quote=True) in refused.text
        assert draft not in refused.text
        assert physical_state(console, sid) == before
        with bounded_post_only(console, sid, monkeypatch):
            saved = client.post("/review", data=data, follow_redirects=False)
        assert saved.status_code == 303
        winner = physical_state(console, sid)
        unrelated = lambda state: [row for row in state["objects"] if row["object_id"] != focal["object_id"]]
        assert unrelated(winner) == unrelated(before)
        assert [row for row in winner["bindings"] if row["object_id"] != focal["object_id"]] == before["bindings"]
        assert any(row["object_id"] == focal["object_id"] and row["payload"]["governance"]["validation_status"] == "approved"
                   for row in winner["objects"])
        with bounded_post_only(console, sid, monkeypatch):
            stale = client.post("/review", data=data, follow_redirects=False)
        assert stale.status_code == 409
        assert html.escape(draft, quote=True) in stale.text
        assert physical_state(console, sid) == winner
        # The post-commit GET owns queue navigation and must select a real next passage.
        next_page = client.get(saved.headers["location"], follow_redirects=False)
        assert next_page.status_code == 200
        assert f'id="review-form-{second["object_id"]}"' in next_page.text
        assert f'id="review-form-{focal["object_id"]}"' not in next_page.text

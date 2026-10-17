"""R2 native reproduction: object loss via write_bundle (object/revise scenario).

Two real console instances share one throwaway PostgreSQL database and one
runtime (so they share the process store lock). Instance A gets an injected
fault inside a supported review command (review_object approve). After A's
document context has rolled back and released the lock, but before A's
post-rollback step runs (_restore_review_state on main, the remirror after
the fix), instance B reviews object B with decision "revise" and then applies
the correction via correct_object, which writes a new object version. B's
corrected object (content and object_version), B's binding and B's audit
events MOET survive A's post-rollback step; a blind write_bundle of A's
pre-mutation copy MAG NIET overwrite them (see WilliamGomes41/Metis#33).
"""
import fcntl

from src.proportionate_review_v1 import normal_risk_batch_queue
from tests.test_workflow_chain_recovery_v1 import recovery_postgres as workflow_postgres  # noqa: F401


from tests.complete_workflow_support import complete_console as _console


def _approve(console, actor, sid, object_id, obj_type):
    return console.review_object(
        actor_id=actor, snapshot_id=sid, object_id=object_id, decision="approve",
        confirmed_object_type=obj_type, suitability="ja", eindoordeel="goedkeuren",
        type_action="dit_klopt",
    )


def test_r2_restore_after_lock_release_overwrites_concurrent_correction_object(workflow_postgres, tmp_path, monkeypatch):
    a = _console(tmp_path, workflow_postgres)
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(a)
    researcher = a.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = a.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = a.ingest(
        actor_id=researcher["account_id"], filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
             b'<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>'
             b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-20", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    queue = normal_risk_batch_queue(a.snapshot_objects(sid), review_path="richtlijn",
                                    fragments=a.review_source_fragments(sid),
                                    bindings=a.object_review_bindings(sid))
    assert len(queue) == 2
    obj_a, obj_b = queue
    from src.proportionate_review_v1 import _batch_type
    type_a, type_b = _batch_type(obj_a), _batch_type(obj_b)

    b = _console(tmp_path, workflow_postgres)  # second real instance, same DB + runtime
    rid = reviewer["account_id"]
    lock_path = tmp_path / "runtime" / "store.lock"
    seen = {}

    # Fault injection inside A's supported review command, after its writes.
    original_commit = a._commit_prepared_store

    def faulty_commit(**kwargs):
        original_commit(**kwargs)
        raise RuntimeError("r2_injected_fault")

    monkeypatch.setattr(a, "_commit_prepared_store", faulty_commit)

    # Hook the post-rollback step: _restore_review_state on main, the remirror
    # after the fix. B interleaves where A's step runs without the lock.
    hook_name = "_restore_review_state" if hasattr(a, "_restore_review_state") else "_remirror_after_rollback"
    original_restore = getattr(a, hook_name)

    def run_b():
        # B commits a second change through the normal path.
        text = obj_b["content"]["clean_text"].rstrip(".")
        b.review_object(actor_id=rid, snapshot_id=sid, object_id=obj_b["object_id"], decision="revise",
                        comment="Corrigeer de formulering.", proposed_correction=text)
        seen["b_revised"] = b.correct_object(
            actor_id=rid, snapshot_id=sid, object_id=obj_b["object_id"],
            patch={"reason": "r2 concurrent correction",
                   "operations": [{"op": "set", "path": "content.clean_text", "value": text}]},
        )
        seen["events_after_b"] = b.workflow_review_store.read_events()
        seen["bindings_after_b"] = [x for x in b.workflow_review_store.read_bindings().get(sid, [])
                                    if x["object_id"] == obj_b["object_id"]]
        seen["obj_after_b"] = next(o for o in b.workflow_document_store.list_document_objects(sid)
                                      if o["object_id"] == obj_b["object_id"])
        seen["objs_after_b"] = b.workflow_document_store.list_document_objects(sid)

    def interleave_then_restore(*args, **kwargs):
        seen.setdefault("restore_depths", []).append(a._store_lock_depth)
        if a._store_lock_depth > 0:
            # Nested review contexts (closed_review_loop) restore while the
            # outer context still holds the lock; only the outermost restore
            # runs after release.
            return original_restore(*args, **kwargs)
        # Prove A no longer holds the store lock (thread depth + flock free).
        seen["a_lock_depth"] = a._store_lock_depth
        with open(lock_path, "a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        run_b()
        return original_restore(*args, **kwargs)

    monkeypatch.setattr(a, hook_name, interleave_then_restore)

    try:
        _approve(a, rid, sid, obj_a["object_id"], type_a)
    except RuntimeError as exc:
        assert str(exc) == "r2_injected_fault"
    else:
        raise AssertionError("fault was not injected")

    if "events_after_b" not in seen:
        # No post-rollback step ran without the lock: B commits after A.
        seen["a_lock_depth"] = a._store_lock_depth
        run_b()
    assert seen["a_lock_depth"] == 0
    print("R2_RESTORE_DEPTHS", seen["restore_depths"])
    print("R2_B_STATUS", obj_b["governance"]["validation_status"], "->", seen["obj_after_b"]["governance"]["validation_status"], "clean_text_changed", seen["obj_after_b"]["content"]["clean_text"] != obj_b["content"]["clean_text"])
    assert seen["obj_after_b"] != obj_b, "precondition: B object change committed"

    fresh = _console(tmp_path, workflow_postgres)
    b_obj = next(o for o in fresh.workflow_document_store.list_document_objects(sid)
                 if o["object_id"] == obj_b["object_id"])
    b_bindings = [x for x in fresh.workflow_review_store.read_bindings().get(sid, [])
                  if x["object_id"] == obj_b["object_id"]]
    events = fresh.workflow_review_store.read_events()
    report = {
        "b_object_survived": b_obj == seen["obj_after_b"],
        "b_bindings_now": len(b_bindings),
        "b_bindings_after_b": len(seen["bindings_after_b"]),
        "events_after_b": len(seen["events_after_b"]),
        "events_now": len(events),
    }
    print("R2_REPORT", report)
    print("R2_OBJ", {"b_version_after_b": seen["b_revised"]["object_version"],
                     "b_version_now": b_obj["object_version"], "orig": obj_b["object_version"]})
    objs_now = fresh.workflow_document_store.list_document_objects(sid)
    versions_after_b = sorted((o["object_id"], o["object_version"]) for o in seen["objs_after_b"])
    versions_now = sorted((o["object_id"], o["object_version"]) for o in objs_now)
    print("R2_VERSIONS", {"after_b": len(versions_after_b), "now": len(versions_now),
                          "lost": sorted(set(versions_after_b) - set(versions_now))})
    assert objs_now == seen["objs_after_b"], f"B correct_object change overwritten by A restore (write_bundle): {report}"
    assert b_obj == seen["obj_after_b"], f"B correct_object change overwritten by A restore (write_bundle): {report}"
    assert events[: len(seen["events_after_b"])] == seen["events_after_b"], f"B audit lost: {report}"
    assert b_bindings == seen["bindings_after_b"], f"B binding overwritten by A restore: {report}"

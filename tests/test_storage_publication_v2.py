from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from jsonschema import Draft202012Validator

from src.canonical_store import (
    create_release,
    emergency_unpublish,
    export_published,
    import_approved,
    init_db,
    publish_release,
    recompute_content_hash,
    first_review_snapshot_hash,
    status,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/knowledge_object.schema.v1.0.json"
REAL_INPUT = ROOT / "output/v2/fractuurpreventie_page15_semantic_v2.jsonl"


def semantic_rows():
    return [json.loads(x) for x in REAL_INPUT.read_text(encoding="utf-8").splitlines() if x.strip()]


def make_approved(*, high_risk: bool = False, version: str = "1.0"):
    source = next(o for o in semantic_rows() if (o["risk"]["requires_second_review"] if high_risk else not o["risk"]["requires_second_review"]) and o["object_type"] != "document")
    obj = copy.deepcopy(source)
    obj["object_version"] = version
    obj["source"]["source_checksum"] = "a" * 64
    obj["source"]["integrity_status"] = "verified"
    obj["uncertainty"] = {"has_uncertainty": False, "items": []}
    g = obj["governance"]
    g["validation_status"] = "approved"
    g["publication_status"] = "unpublished"
    g["validated_by"] = "Reviewer A"
    g["validation_date"] = "2026-08-19"
    g["review_snapshot_hash"] = first_review_snapshot_hash(obj)
    g["release_owner"] = None
    g["release_date"] = None
    if obj["risk"]["requires_second_review"]:
        g["second_review"] = {
            "required": True,
            "status": "approved",
            "reviewer": "Reviewer B",
            "review_date": "2026-08-19",
            "snapshot_hash": obj["provenance"]["content_hash"],
        }
    else:
        g["second_review"] = {
            "required": False,
            "status": "not_required",
            "reviewer": None,
            "review_date": None,
            "snapshot_hash": None,
        }
    assert not list(Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(obj))
    return obj


def write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in rows), encoding="utf-8")


def write_release(path: Path, obj, *, release_id="release-1", release_version="2026.08.1", action="publish", replaces=None, owner="Release Owner"):
    item = {
        "object_id": obj["object_id"],
        "object_version": obj["object_version"],
        "content_hash": obj["provenance"]["content_hash"],
        "action": action,
    }
    if replaces is not None:
        item["replaces_object_version"] = replaces
    spec = {
        "release_id": release_id,
        "release_version": release_version,
        "release_owner": owner,
        "notes": "test release",
        "items": [item],
    }
    path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")


def test_real_unreviewed_dataset_cannot_enter_canonical_store(tmp_path: Path):
    db = tmp_path / "store.db"
    rep = import_approved(db, REAL_INPUT, SCHEMA_PATH, "technical-test")
    assert rep["input_objects"] == 21
    assert rep["imported_objects"] == 0
    assert rep["blocked_objects"] == 21
    assert status(db)["canonical_approved_versions"] == 0


def test_approved_verified_object_imports(tmp_path: Path):
    obj = make_approved()
    inp = tmp_path / "approved.jsonl"; write_jsonl(inp, [obj])
    db = tmp_path / "store.db"
    rep = import_approved(db, inp, SCHEMA_PATH, "technical-test")
    assert rep["imported_objects"] == 1
    assert rep["blocked_objects"] == 0


def test_high_risk_requires_second_review(tmp_path: Path):
    obj = make_approved(high_risk=True)
    obj["governance"]["second_review"]["status"] = "pending"
    obj["governance"]["second_review"]["reviewer"] = None
    obj["governance"]["second_review"]["review_date"] = None
    obj["governance"]["second_review"]["snapshot_hash"] = None
    inp = tmp_path / "bad.jsonl"; write_jsonl(inp, [obj])
    rep = import_approved(tmp_path / "store.db", inp, SCHEMA_PATH, "technical-test")
    assert rep["imported_objects"] == 0
    assert "second_review_incomplete" in rep["blocked"][0]["errors"]


def test_release_publication_does_not_mutate_canonical_json(tmp_path: Path):
    obj = make_approved()
    inp = tmp_path / "approved.jsonl"; write_jsonl(inp, [obj])
    db = tmp_path / "store.db"
    assert import_approved(db, inp, SCHEMA_PATH, "technical-test")["blocked_objects"] == 0
    spec = tmp_path / "release.json"; write_release(spec, obj)
    assert create_release(db, spec, "release-preparer")["status"] == "PASS"
    assert publish_release(db, "release-1", "release-publisher")["status"] == "PASS"
    with sqlite3.connect(db) as con:
        stored = json.loads(con.execute("SELECT canonical_json FROM canonical_object_versions").fetchone()[0])
        registry = con.execute("SELECT state, object_version FROM publication_registry WHERE object_id=?", (obj["object_id"],)).fetchone()
    assert stored["governance"]["publication_status"] == "unpublished"
    assert stored["governance"]["validation_status"] == "approved"
    assert registry == ("active", obj["object_version"])
    out = tmp_path / "published.jsonl"
    assert export_published(db, out)["published_objects"] == 1


def test_emergency_unpublish_removes_external_visibility_not_canonical_truth(tmp_path: Path):
    obj = make_approved()
    inp = tmp_path / "approved.jsonl"; write_jsonl(inp, [obj])
    db = tmp_path / "store.db"
    import_approved(db, inp, SCHEMA_PATH, "technical-test")
    spec = tmp_path / "release.json"; write_release(spec, obj)
    create_release(db, spec, "release-preparer"); publish_release(db, "release-1", "release-publisher")
    rep = emergency_unpublish(db, obj["object_id"], "incident-owner", "Clinical safety incident")
    assert rep["status"] == "PASS"
    out = tmp_path / "published.jsonl"
    assert export_published(db, out)["published_objects"] == 0
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM canonical_object_versions").fetchone()[0] == 1
        ev = [x[0] for x in con.execute("SELECT event_type FROM audit_events ORDER BY event_id").fetchall()]
    assert "emergency_unpublished" in ev


def test_content_hash_is_recomputed_on_import(tmp_path: Path):
    obj = make_approved()
    obj["content"]["clean_text"] += " silently changed"
    # Deliberately do not update provenance hash.
    inp = tmp_path / "tampered.jsonl"; write_jsonl(inp, [obj])
    rep = import_approved(tmp_path / "store.db", inp, SCHEMA_PATH, "technical-test")
    assert "content_hash_mismatch" in rep["blocked"][0]["errors"]


def test_same_version_cannot_be_replaced_with_different_content(tmp_path: Path):
    obj = make_approved()
    inp = tmp_path / "a.jsonl"; write_jsonl(inp, [obj])
    db = tmp_path / "store.db"
    assert import_approved(db, inp, SCHEMA_PATH, "technical-test")["imported_objects"] == 1
    changed = copy.deepcopy(obj)
    changed["content"]["clean_text"] += " updated"
    changed["content"]["raw_text"] += " updated"
    changed["provenance"]["content_hash"] = recompute_content_hash(changed)
    changed["governance"]["review_snapshot_hash"] = first_review_snapshot_hash(changed)
    inp2 = tmp_path / "b.jsonl"; write_jsonl(inp2, [changed])
    rep = import_approved(db, inp2, SCHEMA_PATH, "technical-test")
    assert "immutable_version_content_conflict" in rep["blocked"][0]["errors"]


def test_supersession_moves_publication_pointer_and_keeps_history(tmp_path: Path):
    old = make_approved(version="1.0")
    db = tmp_path / "store.db"
    p = tmp_path / "old.jsonl"; write_jsonl(p, [old]); import_approved(db, p, SCHEMA_PATH, "technical-test")
    r1 = tmp_path / "r1.json"; write_release(r1, old, release_id="r1", release_version="1.0")
    create_release(db, r1, "prep"); assert publish_release(db, "r1", "publisher")["status"] == "PASS"

    new = copy.deepcopy(old)
    new["object_version"] = "1.1"
    new["content"]["clean_text"] += " Nieuwe versie."
    new["content"]["raw_text"] += " Nieuwe versie."
    new["provenance"]["content_hash"] = recompute_content_hash(new)
    new["governance"]["review_snapshot_hash"] = first_review_snapshot_hash(new)
    p2 = tmp_path / "new.jsonl"; write_jsonl(p2, [new]); assert import_approved(db, p2, SCHEMA_PATH, "technical-test")["imported_objects"] == 1
    r2 = tmp_path / "r2.json"; write_release(r2, new, release_id="r2", release_version="1.1", action="supersede", replaces="1.0")
    create_release(db, r2, "prep"); assert publish_release(db, "r2", "publisher")["status"] == "PASS"
    with sqlite3.connect(db) as con:
        current = con.execute("SELECT object_version, release_id FROM publication_registry WHERE object_id=?", (old["object_id"],)).fetchone()
        versions = con.execute("SELECT object_version FROM canonical_object_versions WHERE object_id=? ORDER BY object_version", (old["object_id"],)).fetchall()
        events = [x[0] for x in con.execute("SELECT event_type FROM audit_events WHERE entity_id=? ORDER BY event_id", (old["object_id"],)).fetchall()]
    assert current == ("1.1", "r2")
    assert versions == [("1.0",), ("1.1",)]
    assert "superseded" in events


def test_release_creation_is_atomic_if_any_item_missing(tmp_path: Path):
    obj = make_approved()
    db = tmp_path / "store.db"
    inp = tmp_path / "approved.jsonl"; write_jsonl(inp, [obj]); import_approved(db, inp, SCHEMA_PATH, "technical-test")
    spec = {
        "release_id": "mixed", "release_version": "mixed-1", "release_owner": "Release Owner",
        "items": [
            {"object_id": obj["object_id"], "object_version": obj["object_version"], "content_hash": obj["provenance"]["content_hash"], "action": "publish"},
            {"object_id": "missing", "object_version": "1.0", "content_hash": "x" * 64, "action": "publish"},
        ],
    }
    path = tmp_path / "mixed.json"; path.write_text(json.dumps(spec), encoding="utf-8")
    rep = create_release(db, path, "prep")
    assert rep["status"] == "BLOCKED"
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM publication_releases").fetchone()[0] == 0


def test_release_owner_required(tmp_path: Path):
    obj = make_approved()
    db = tmp_path / "store.db"
    inp = tmp_path / "approved.jsonl"; write_jsonl(inp, [obj]); import_approved(db, inp, SCHEMA_PATH, "technical-test")
    spec = tmp_path / "release.json"; write_release(spec, obj, owner="")
    rep = create_release(db, spec, "prep")
    assert rep["status"] == "BLOCKED"


def test_withdraw_release_hides_only_objects_still_pointing_to_that_release(tmp_path: Path):
    from src.canonical_store import withdraw_release
    obj = make_approved()
    db = tmp_path / "store.db"
    inp = tmp_path / "approved.jsonl"; write_jsonl(inp, [obj]); import_approved(db, inp, SCHEMA_PATH, "technical-test")
    spec = tmp_path / "release.json"; write_release(spec, obj, release_id="withdraw-me", release_version="w1")
    create_release(db, spec, "prep"); publish_release(db, "withdraw-me", "publisher")
    rep = withdraw_release(db, "withdraw-me", "incident-owner", "Release-level safety incident")
    assert rep["status"] == "PASS"
    assert rep["withdrawn_active_objects"] == 1
    out = tmp_path / "published.jsonl"
    assert export_published(db, out)["published_objects"] == 0
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT status FROM publication_releases WHERE release_id='withdraw-me'").fetchone()[0] == "withdrawn"
        assert con.execute("SELECT COUNT(*) FROM canonical_object_versions").fetchone()[0] == 1

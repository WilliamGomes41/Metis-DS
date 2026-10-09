"""Immutable, versioned source blocks. Production storage is workflow PostgreSQL.

Preparation is a command operation. Loading and resolving accepted blocks are
queries and never call an extractor, reconstructor or model.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path

from src.integrity_kernel import stable_hash

VERSION = "source-representation-v1"
PREPARED = "_prepared_source_representation"
MISSING = "source_representation_migration_required"
INVALID = "source_representation_invalid"
CONFLICT = "source_representation_conflict"


class SourceRepresentationError(ValueError):
    pass


class _FrozenDict(dict):
    def _immutable(self, *args, **kwargs):
        raise SourceRepresentationError("source_representation_carrier_immutable")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable
    def __deepcopy__(self, memo):
        return self


class _FrozenList(list):
    def _immutable(self, *args, **kwargs):
        raise SourceRepresentationError("source_representation_carrier_immutable")
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = __iadd__ = __imul__ = _immutable
    def __deepcopy__(self, memo):
        return self


def _freeze(value):
    if isinstance(value, dict):
        return _FrozenDict({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return _FrozenList(_freeze(v) for v in value)
    return value


class SourceFragments(_FrozenList):
    """Immutable disposable carrier; durable database remains the authority."""
    def __init__(self, record):
        validate_record(record)
        self._record = _freeze(deepcopy(record))
        list.__init__(self, self._record["fragments"])
        self._views = {name: {public["block_id"]: (public, source) for public, source in rows}
                       for name, rows in self._record["views"].items()}

    @property
    def representation(self):
        return self._record

    @property
    def extraction_record(self):
        # Command producers may stamp their own extraction evidence.
        record = self._record.get("extraction_record")
        return json.loads(json.dumps(record)) if record is not None else None


def preserve_fragments(fragments):
    return fragments if isinstance(fragments, SourceFragments) else list(fragments)


def stored_blocks(fragments, *, include_headings=False):
    if not isinstance(fragments, SourceFragments):
        return None
    # Frozen carriers cannot be edited into stale source evidence. Returning a
    # fresh index protects caller-local keys without copying the whole document.
    return dict(fragments._views["full" if include_headings else "selection"])


def prepare(envelope, fragments, *, correction_revision=0):
    """Build both existing views outside the write transaction, without models."""
    from src.semantic_passage_v1 import _reconstructed_blocks, SEMANTIC_PASSAGE_VERSION
    from src.source_reconstruction_v1 import RECONSTRUCTION_VERSION
    from src.object_taxonomy_v1 import extract_object_type
    if type(correction_revision) is not int or correction_revision < 0:
        raise SourceRepresentationError(INVALID)
    if isinstance(fragments, SourceFragments):
        validate_record(fragments.representation, envelope)
        if fragments.representation["key"]["correction_revision"] != correction_revision:
            raise SourceRepresentationError("source_representation_successor_required")
        return json.loads(json.dumps(fragments.representation, ensure_ascii=False))
    raw = deepcopy(list(fragments))
    extraction = deepcopy(getattr(fragments, "extraction_record", None))
    if extraction is not None:
        extraction.pop("metrics", None)
        extraction.pop("record_hash", None)
    key = {"source_sha256": envelope["sha256"],
           "document_id": envelope["document_id"], "source_id": envelope["source_id"],
           "extractor_versions": sorted({str(f.get("parser_version") or "legacy-unversioned") for f in raw}),
           "extractor_contract_hash": stable_hash({k: v for k, v in (extraction or {}).items()
               if k not in {"record_hash", "prepared_fragments", "prepared_fragments_hash"}}),
           "fragments_hash": stable_hash(raw), "reconstruction_version": RECONSTRUCTION_VERSION,
           "block_version": SEMANTIC_PASSAGE_VERSION, "schema_version": VERSION,
           "correction_revision": correction_revision}
    result = {"version": VERSION, "representation_id": "sr_" + stable_hash(key),
              "key": key, "fragments": raw, "extraction_record": extraction,
              "views": {"full": _reconstructed_blocks(raw),
                        "selection": _reconstructed_blocks([f for f in raw if extract_object_type(f)[0] != "heading"])}}
    # JSON is the durable format in both supported backends.
    result = json.loads(json.dumps(result, ensure_ascii=False))
    result["payload_hash"] = stable_hash(result)
    validate_record(result)
    return result


def validate_record(record, envelope=None):
    try:
        if record["version"] != VERSION or record["key"]["schema_version"] != VERSION:
            raise ValueError()
        if record["representation_id"] != "sr_" + stable_hash(record["key"]):
            raise ValueError()
        if record["payload_hash"] != stable_hash({k: v for k, v in record.items() if k != "payload_hash"}):
            raise ValueError()
        if stable_hash(record["fragments"]) != record["key"]["fragments_hash"]:
            raise ValueError()
        if envelope is not None and any(record["key"][k] != envelope[e] for k, e in
                (("source_sha256", "sha256"), ("document_id", "document_id"), ("source_id", "source_id"))):
            raise ValueError()
        ids = [f["fragment_id"] for f in record["fragments"]]
        if len(ids) != len(set(ids)):
            raise ValueError()
        raw = {f["fragment_id"]: f for f in record["fragments"]}
        if set(record["views"]) != {"full", "selection"}:
            raise ValueError()
        for view in record["views"].values():
            seen = set()
            for public, source in view:
                bid = public["block_id"]
                if bid in seen or public["text"] != source["clean_text"]:
                    raise ValueError()
                seen.add(bid)
                if any(fid not in raw for fid in public["source_fragment_ids"]):
                    raise ValueError()
                cursor = 0
                for span in source.get("_raw_source_mapping", []):
                    if span["start"] != cursor or not cursor < span["end"] <= len(public["text"]):
                        raise ValueError()
                    cursor = span["end"]
                    if span.get("kind") == "join_separator":
                        if any(span[k] not in raw for k in ("left_fragment_id", "right_fragment_id")):
                            raise ValueError()
                    else:
                        fragment = raw[span["fragment_id"]]
                        if not 0 <= span["raw_start"] < span["raw_end"] <= len(fragment["raw_text"]):
                            raise ValueError()
                # Empty mappings occur on legacy extractors and remain a technical
                # lineage failure under existing validators; do not invent spans.
                if source.get("_raw_source_mapping") and cursor != len(public["text"]):
                    raise ValueError()
        return record
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise SourceRepresentationError(INVALID) from exc


def provenance(envelope, *, actor_id=None, command_id=None, reason="processing"):
    from datetime import datetime, timezone
    attempts = envelope.get("processing_attempts") or []
    attempt = attempts[-1] if attempts else {}
    return {"snapshot_id": envelope["snapshot_id"], "source_sha256": envelope["sha256"],
            "actor_id": actor_id or attempt.get("actor_id") or envelope.get("uploader_account_id"),
            "command_id": command_id or attempt.get("command_id") or (envelope.get("ingest_command") or {}).get("id"),
            "attempt_id": attempt.get("attempt_id"), "reason": reason,
            "accepted_at": datetime.now(timezone.utc).isoformat()}


def accept_postgres(connection, envelope, record, evidence):
    """Called under the existing workflow transaction; constraints fence races."""
    validate_record(record, envelope)
    rid = record["representation_id"]
    connection.execute(
        "INSERT INTO workflow.source_representations(representation_id,payload_hash,payload) "
        "VALUES(%s,%s,%s::jsonb) ON CONFLICT(representation_id) DO NOTHING",
        (rid, record["payload_hash"], json.dumps(record, ensure_ascii=False)))
    existing = connection.execute(
        "SELECT payload_hash FROM workflow.source_representations WHERE representation_id=%s", (rid,)).fetchone()
    if existing["payload_hash"] != record["payload_hash"]:
        raise SourceRepresentationError(CONFLICT)
    connection.execute(
        "INSERT INTO workflow.source_representation_bindings(snapshot_id,representation_id,evidence) "
        "VALUES(%s,%s,%s::jsonb) ON CONFLICT(snapshot_id) DO NOTHING",
        (envelope["snapshot_id"], rid, json.dumps(evidence)))
    bound = connection.execute(
        "SELECT representation_id FROM workflow.source_representation_bindings WHERE snapshot_id=%s",
        (envelope["snapshot_id"],)).fetchone()
    if bound["representation_id"] != rid:
        raise SourceRepresentationError(CONFLICT)
    return rid


def _local_path(console):
    return Path(console.runtime) / "source_representations.sqlite3"


@contextmanager
def _local_connection(console, *, write=False):
    path = _local_path(console)
    if not write and not path.is_file():
        raise SourceRepresentationError(MISSING)
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path) if write else f"file:{path}?mode=ro", uri=not write, timeout=10)
    try:
        with connection:
            if write:
                connection.execute("CREATE TABLE IF NOT EXISTS representations "
                                   "(representation_id TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS bindings "
                                   "(snapshot_id TEXT PRIMARY KEY,representation_id TEXT NOT NULL,evidence TEXT NOT NULL)")
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
            yield connection
    finally:
        connection.close()


def accept_local(console, envelope, record, evidence):
    validate_record(record, envelope)
    rid = record["representation_id"]
    with _local_connection(console, write=True) as con:
        con.execute("INSERT OR IGNORE INTO representations VALUES(?,?,?)",
                    (rid, record["payload_hash"], json.dumps(record, ensure_ascii=False)))
        if con.execute("SELECT payload_hash FROM representations WHERE representation_id=?", (rid,)).fetchone()[0] != record["payload_hash"]:
            raise SourceRepresentationError(CONFLICT)
        con.execute("INSERT OR IGNORE INTO bindings VALUES(?,?,?)", (envelope["snapshot_id"], rid, json.dumps(evidence)))
        if con.execute("SELECT representation_id FROM bindings WHERE snapshot_id=?", (envelope["snapshot_id"],)).fetchone()[0] != rid:
            raise SourceRepresentationError(CONFLICT)
    return rid


def load(console, envelope):
    documents = getattr(console, "workflow_document_store", None)
    if documents is not None:
        try:
            with documents._connect() as con:
                row = con.execute(
                    "SELECT r.payload,r.payload_hash,r.representation_id FROM workflow.source_representation_bindings b "
                    "JOIN workflow.source_representations r USING(representation_id) WHERE b.snapshot_id=%s",
                    (envelope["snapshot_id"],)).fetchone()
        except Exception as exc:
            raise SourceRepresentationError("source_representation_store_unavailable") from exc
        record = row["payload"] if row else None
        if isinstance(record, str):
            record = json.loads(record)
    else:
        with _local_connection(console) as con:
            row = con.execute("SELECT r.payload,r.payload_hash,r.representation_id FROM bindings b JOIN representations r "
                              "USING(representation_id) WHERE b.snapshot_id=?", (envelope["snapshot_id"],)).fetchone()
        record = json.loads(row[0]) if row else None
    if record is None:
        raise SourceRepresentationError(MISSING)
    validate_record(record, envelope)
    expected_hash = row["payload_hash"] if documents is not None else row[1]
    expected_id = row["representation_id"] if documents is not None else row[2]
    if record["payload_hash"] != expected_hash or record["representation_id"] != expected_id:
        raise SourceRepresentationError(INVALID)
    return SourceFragments(record)

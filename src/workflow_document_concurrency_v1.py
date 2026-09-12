"""Multi-instance optimistic merge for PostgreSQL workflow document objects."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any, Mapping

from src.operations_console_v1 import SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text


class PostgresConcurrentWorkflowDocumentStore(PostgresWorkflowDocumentRuntimeStore):
    """Merge independent object edits while preserving same-object conflict detection."""

    REVISION_PREFIX = "m2."

    @staticmethod
    def _object_identity(row: Mapping[str, Any]) -> tuple[str, str]:
        return str(row.get("object_id") or ""), str(row.get("object_version") or "")

    @staticmethod
    def _object_hash(row: Mapping[str, Any]) -> str:
        return hashlib.sha256(_json_text(dict(row)).encode("utf-8")).hexdigest()

    @classmethod
    def _validate_rows(cls, rows: list[dict[str, Any]]) -> None:
        identities = [cls._object_identity(row) for row in rows]
        if any(not a or not b for a, b in identities) or len(set(identities)) != len(identities):
            raise WorkflowDocumentStoreError("workflow_object_identity_invalid")

    @classmethod
    def _revision_token(cls, rows: list[dict[str, Any]]) -> str:
        cls._validate_rows(rows)
        payload = {
            "snapshot": cls._revision(rows),
            "objects": [
                [object_id, object_version, cls._object_hash(row)]
                for row in rows
                for object_id, object_version in [cls._object_identity(row)]
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        return cls.REVISION_PREFIX + encoded

    @classmethod
    def _decode_revision(cls, revision: str) -> dict[tuple[str, str], str] | None:
        if not revision.startswith(cls.REVISION_PREFIX):
            return None
        encoded = revision[len(cls.REVISION_PREFIX) :]
        encoded += "=" * (-len(encoded) % 4)
        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8"))
            rows = payload["objects"]
            return {(str(row[0]), str(row[1])): str(row[2]) for row in rows}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT) from exc

    def objects_revision(self, snapshot_id: str) -> str:
        return self._revision_token(self.list_document_objects(snapshot_id))

    @classmethod
    def _merge_objects(
        cls,
        *,
        current: list[dict[str, Any]],
        submitted: list[dict[str, Any]],
        expected_revision: str | None,
    ) -> list[dict[str, Any]]:
        cls._validate_rows(current)
        cls._validate_rows(submitted)
        if expected_revision is None:
            return submitted

        base_hashes = cls._decode_revision(expected_revision)
        if base_hashes is None:
            if cls._revision(current) != expected_revision:
                raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
            return submitted

        current_map = {cls._object_identity(row): row for row in current}
        submitted_map = {cls._object_identity(row): row for row in submitted}
        result: dict[tuple[str, str], dict[str, Any]] = {}

        for identity in set(base_hashes) | set(current_map) | set(submitted_map):
            base_hash = base_hashes.get(identity)
            current_row = current_map.get(identity)
            submitted_row = submitted_map.get(identity)
            current_hash = cls._object_hash(current_row) if current_row is not None else None
            submitted_hash = cls._object_hash(submitted_row) if submitted_row is not None else None

            if base_hash is not None:
                if submitted_row is None:
                    if current_hash not in (None, base_hash):
                        raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                    continue
                if submitted_hash == base_hash:
                    if current_row is not None:
                        result[identity] = current_row
                    continue
                if current_hash == base_hash:
                    result[identity] = submitted_row
                    continue
                if current_hash == submitted_hash:
                    result[identity] = current_row
                    continue
                raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)

            if submitted_row is not None and current_row is not None:
                if submitted_hash != current_hash:
                    raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                result[identity] = current_row
            elif submitted_row is not None:
                result[identity] = submitted_row
            elif current_row is not None:
                result[identity] = current_row

        order: list[tuple[str, str]] = []
        for row in current:
            identity = cls._object_identity(row)
            if identity in result and identity not in order:
                order.append(identity)
        for row in submitted:
            identity = cls._object_identity(row)
            if identity in result and identity not in order:
                order.append(identity)
        return [result[identity] for identity in order]

    def write_bundle(
        self,
        *,
        envelope: Mapping[str, Any],
        objects: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
    ) -> str:
        snapshot_id = str(envelope.get("snapshot_id") or "")
        if not snapshot_id:
            raise WorkflowDocumentStoreError("workflow_document_metadata_incomplete")
        try:
            with self._connect() as con:
                with con.transaction():
                    exists = con.execute(
                        "SELECT snapshot_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                        (snapshot_id,),
                    ).fetchone()
                    current_objects: list[dict[str, Any]] = []
                    if exists is not None:
                        current_objects = self._objects_locked(con, snapshot_id)
                    elif expected_revision not in (None, ""):
                        raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)

                    self._write_envelope_locked(con, envelope)
                    next_objects = current_objects
                    if objects is not None:
                        next_objects = self._merge_objects(
                            current=current_objects,
                            submitted=objects,
                            expected_revision=expected_revision,
                        )
                        con.execute("DELETE FROM workflow.document_objects WHERE snapshot_id=%s", (snapshot_id,))
                        for position, obj in enumerate(next_objects):
                            con.execute(
                                "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) "
                                "VALUES(%s,%s,%s,%s::jsonb,%s)",
                                (snapshot_id, obj["object_id"], obj["object_version"], _json_text(obj), position),
                            )
            return self._revision_token(next_objects)
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_bundle_write_failed") from exc

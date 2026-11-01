"""Multi-instance optimistic merge for PostgreSQL workflow document objects."""
from __future__ import annotations

from src.review.revision_workflow import current_revisions, validate_revision_write

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from src.operations_console_v1 import PUBLISHED_ENVELOPE_STATES, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text


PUBLISHED_WORKING_REVISION_IMMUTABLE = "published_working_revision_immutable"
_PUBLICATION_PROJECTION_FIELDS = frozenset(
    {
        "state",
        "published",
        "release_id",
        "release_version",
        "published_at",
        "published_by",
    }
)
_DATABASE_MANAGED_LIFECYCLE_PROJECTION_FIELDS = frozenset(
    {
        "logical_document_id",
        "source_snapshot_id",
        "source_version",
        "working_revision_id",
        "working_revision_number",
        "topic_id",
    }
)


def _instant(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class PostgresConcurrentWorkflowDocumentStore(PostgresWorkflowDocumentRuntimeStore):
    """Merge independent object edits while preserving same-object conflict detection.

    A durable canonical publication also seals the corresponding WorkingRevision.
    Publication metadata may still be reconciled into the workflow envelope, but
    the working payload, objects and reviewer state are no longer writable.
    """

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

    def revision_for_rows(self, rows: list[dict[str, Any]]) -> str:
        return self._revision_token(rows)

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

    def review_command_histories(self, snapshot_id: str, object_ids: list[str]) -> list[dict[str, Any]]:
        """Raw append-order history for the command's explicit identity closure."""
        if not object_ids:
            return []
        try:
            with self._connect() as con:
                rows = con.execute(
                    "SELECT position,payload FROM workflow.document_objects WHERE snapshot_id=%s "
                    "AND object_id=ANY(%s) ORDER BY position", (snapshot_id, sorted(set(object_ids))),
                ).fetchall()
            if any(row["position"] is None for row in rows):
                raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
            return [self._payload(row["payload"]) for row in rows]
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_objects_read_failed") from exc

    def review_command_heading_ids(self, snapshot_id: str) -> list[str]:
        """Current structural candidates; selected full histories are validated later."""
        probes = [json.dumps({key: kind})
                  for key in ('object_type', 'confirmed_object_type', 'proposed_object_type')
                  for kind in ('heading', 'path')]
        try:
            with self._connect() as con:
                rows = con.execute("""
                    WITH latest AS MATERIALIZED (
                      SELECT object_id,max(position) AS position
                      FROM workflow.document_objects WHERE snapshot_id=%s GROUP BY object_id
                    )
                    SELECT d.object_id FROM latest
                    JOIN workflow.document_objects d ON d.snapshot_id=%s
                      AND d.object_id=latest.object_id AND d.position=latest.position
                    WHERE d.payload @> ANY(%s::jsonb[])
                    """, (snapshot_id, snapshot_id, probes)).fetchall()
            return [str(row['object_id']) for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_review_context_read_failed') from exc

    def review_command_neighbor_ids(self, snapshot_id: str, object_ids: list[str]) -> list[str]:
        """Current incoming dependencies, excluding superseded historical edges.

        Position is only a candidate prefilter. The command subsequently loads
        complete histories of the selected identities and validates their lineage.
        """
        if not object_ids:
            return []
        probes = [json.dumps({key: [{'target_object_id': oid}]})
                  for oid in sorted(set(object_ids)) for key in (
                      'proposed_knowledge_relations', 'confirmed_knowledge_relations',
                      'relations', 'confirmed_relations')]
        probes.extend(json.dumps({'metadata': {'confirmed_source_context': [{'source_object_id': oid}]}})
                      for oid in sorted(set(object_ids)))
        try:
            with self._connect() as con:
                rows = con.execute("""
                    SELECT DISTINCT neighbor.object_id FROM unnest(%s::jsonb[]) AS wanted(probe)
                    CROSS JOIN LATERAL (
                      SELECT d.object_id FROM workflow.document_objects d
                      WHERE d.snapshot_id=%s AND d.payload @> wanted.probe
                        AND d.position=(SELECT max(latest.position) FROM workflow.document_objects latest
                            WHERE latest.snapshot_id=d.snapshot_id AND latest.object_id=d.object_id)
                      OFFSET 0
                    ) neighbor
                    """, (probes, snapshot_id)).fetchall()
            return [str(row['object_id']) for row in rows]
        except Exception as exc:
            raise WorkflowDocumentStoreError('workflow_review_context_read_failed') from exc

    def apply_review_changes(
        self, snapshot_id: str, before_objects: list[dict[str, Any]],
        after_objects: list[dict[str, Any]], envelope_before: dict[str, Any],
        envelope_after: dict[str, Any], commit_count: int = 1, *,
        transitions: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        """Commit validated object/envelope deltas without replacing unrelated rows.

        The caller owns review semantics and its precondition. This storage
        boundary independently protects sealing, captured history, append order
        and the only supported envelope delta (review-pass evidence).
        """
        from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore

        if (not snapshot_id or envelope_before.get("snapshot_id") != snapshot_id
                or envelope_after.get("snapshot_id") != snapshot_id):
            raise WorkflowDocumentStoreError("workflow_document_metadata_incomplete")
        if type(commit_count) is not int or commit_count < 0:
            raise WorkflowDocumentStoreError("workflow_review_commit_count_invalid")
        changed_fields = {key for key in set(envelope_before) | set(envelope_after)
                          if (key in envelope_before) != (key in envelope_after)
                          or envelope_before.get(key) != envelope_after.get(key)}
        if changed_fields - {"review_passes"}:
            raise WorkflowDocumentStoreError("workflow_review_envelope_delta_unsupported")
        if commit_count == 0 and (before_objects != after_objects or changed_fields):
            raise WorkflowDocumentStoreError("workflow_review_commit_count_invalid")
        self._validate_rows(before_objects)
        self._validate_rows(after_objects)
        before_ids = [self._object_identity(row) for row in before_objects]
        after_ids = [self._object_identity(row) for row in after_objects]
        before_set = set(before_ids)
        if after_ids[:len(before_ids)] != before_ids:
            raise WorkflowDocumentStoreError("workflow_review_history_removal_or_reorder")
        object_ids = sorted({identity[0] for identity in [*before_ids, *after_ids]})
        try:
            with self._connect() as con:
                with con.transaction():
                    con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
                    PostgresWorkflowReviewStore._lock_authorizations(con)
                    document = con.execute(
                        "SELECT state,document_storage_version,CASE WHEN document_storage_version=1 THEN "
                        "(SELECT metadata->'review_passes' FROM workflow.document_inputs i WHERE i.snapshot_id=d.snapshot_id) "
                        "ELSE envelope_payload->'review_passes' END AS review_passes "
                        "FROM workflow.documents d WHERE snapshot_id=%s FOR UPDATE", (snapshot_id,),
                    ).fetchone()
                    if document is None:
                        raise WorkflowDocumentStoreError("unknown_snapshot")
                    if (document["state"] in PUBLISHED_ENVELOPE_STATES
                            or self._release_history_locked(con, snapshot_id) is not None):
                        raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
                    rows = con.execute(
                        "SELECT position,payload FROM workflow.document_objects WHERE snapshot_id=%s "
                        "AND object_id=ANY(%s) ORDER BY position FOR UPDATE", (snapshot_id, object_ids),
                    ).fetchall() if object_ids else []
                    if any(row["position"] is None for row in rows):
                        raise WorkflowDocumentStoreError("workflow_document_cutover_not_prepared")
                    current = [self._payload(row["payload"]) for row in rows]
                    if current != before_objects:
                        raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                    # Existing mixins can legally update current governance and
                    # then append a successor in the SAME outer transaction.
                    # Validate their full transition sequence, never waive the
                    # immutable-history guard on a flattened final diff.
                    previous = current
                    for proposed in transitions if transitions is not None else [after_objects]:
                        validate_revision_write(previous, proposed, snapshot_id=snapshot_id)
                        previous = proposed
                    if previous != after_objects or (transitions is not None and len(transitions) > commit_count):
                        raise WorkflowDocumentStoreError('workflow_review_transition_chain_invalid')
                    before_map = {self._object_identity(row): row for row in current}
                    for obj in after_objects:
                        identity = self._object_identity(obj)
                        if identity in before_set and before_map[identity] != obj:
                            con.execute(
                                "UPDATE workflow.document_objects SET payload=%s::jsonb,revision=revision+1,"
                                "updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s AND object_id=%s AND object_version=%s",
                                (_json_text(obj), snapshot_id, *identity),
                            )
                    additions = [obj for obj in after_objects if self._object_identity(obj) not in before_set]
                    if additions:
                        tail = con.execute(
                            "SELECT COALESCE(max(position),-1) AS position FROM workflow.document_objects "
                            "WHERE snapshot_id=%s", (snapshot_id,),
                        ).fetchone()["position"]
                        for offset, obj in enumerate(additions, 1):
                            con.execute(
                                "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) "
                                "VALUES(%s,%s,%s,%s::jsonb,%s)",
                                (snapshot_id, obj["object_id"], obj["object_version"], _json_text(obj), tail + offset),
                            )
                    if "review_passes" in changed_fields:
                        previous = envelope_before.get("review_passes") or {}
                        following = envelope_after.get("review_passes") or {}
                        current_passes = document["review_passes"] or {}
                        if not all(isinstance(value, dict) for value in (previous, following, current_passes)):
                            raise WorkflowDocumentStoreError("workflow_review_envelope_delta_unsupported")
                        if set(previous) - set(following):
                            raise WorkflowDocumentStoreError("workflow_review_envelope_delta_unsupported")
                        changes = {actor: value for actor, value in following.items()
                                   if actor not in previous or previous[actor] != value}
                        for actor in changes:
                            if ((actor in current_passes) != (actor in previous)
                                    or current_passes.get(actor) != previous.get(actor)):
                                raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                        if document['document_storage_version']==1:
                            con.execute("UPDATE workflow.document_inputs SET metadata=jsonb_set(metadata,'{review_passes}',"
                                "COALESCE(NULLIF(metadata->'review_passes','null'::jsonb),'{}'::jsonb)||%s::jsonb,true) "
                                "WHERE snapshot_id=%s",(_json_text(changes),snapshot_id))
                            if commit_count>1:
                                con.execute('UPDATE workflow.documents SET revision=revision+%s WHERE snapshot_id=%s',
                                    (commit_count-1,snapshot_id))
                        else:
                            con.execute(
                                "UPDATE workflow.documents SET revision=revision+%s,updated_at=CURRENT_TIMESTAMP, "
                                "envelope_payload=jsonb_set(envelope_payload,"
                                "'{review_passes}',COALESCE(NULLIF(envelope_payload->'review_passes','null'::jsonb),"
                                "'{}'::jsonb)||%s::jsonb,true) WHERE snapshot_id=%s", (commit_count, _json_text(changes), snapshot_id),
                            )
                    elif commit_count:
                        con.execute(
                            "UPDATE workflow.documents SET revision=revision+%s,updated_at=CURRENT_TIMESTAMP "
                            "WHERE snapshot_id=%s", (commit_count, snapshot_id),
                        )
                    from src.workflows.review_card_inputs_postgres_v1 import maintain
                    maintain(self, con, snapshot_id, after_objects)
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_bundle_write_failed") from exc

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

    @staticmethod
    def _working_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {
            str(key): value
            for key, value in payload.items()
            if str(key) not in _PUBLICATION_PROJECTION_FIELDS
        }

    @classmethod
    def _assert_working_payload_unchanged(
        cls,
        *,
        current_payload: Mapping[str, Any],
        submitted: Mapping[str, Any],
    ) -> None:
        """Allow omission, but never alteration, of DB-managed identity projections.

        Migration 008 enriches ``envelope_payload`` inside PostgreSQL with lifecycle
        identity fields. A caller may legitimately hold a pre-enrichment envelope
        while reconciling release metadata. Missing database-managed projections are
        therefore filled from the locked current row for comparison. Supplying a
        conflicting value remains an immutable-working-revision violation.
        """
        current_working = cls._working_payload(current_payload)
        submitted_working = cls._working_payload(submitted)
        for field in _DATABASE_MANAGED_LIFECYCLE_PROJECTION_FIELDS:
            if field in current_working and field not in submitted_working:
                submitted_working[field] = current_working[field]
        if current_working != submitted_working:
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)

    @staticmethod
    def _release_history_locked(con: Any, snapshot_id: str) -> Mapping[str, Any] | None:
        """Read immutable publication history from canonical PostgreSQL authority.

        Local/test workflow databases may exist without canonical tables. In that
        topology there is no durable publication authority to seal against.
        """
        tables = con.execute(
            "SELECT to_regclass('publication_releases') AS releases, "
            "to_regclass('audit_events') AS events"
        ).fetchone()
        if not tables or tables["releases"] is None or tables["events"] is None:
            return None
        return con.execute(
            """
            SELECT rel.release_id,
                   rel.release_version,
                   rel.release_owner,
                   rel.status,
                   rel.published_at
            FROM audit_events ev
            JOIN publication_releases rel ON rel.release_id=ev.entity_id
            WHERE ev.entity_type='release'
              AND ev.event_type='release_published'
              AND ev.details->>'snapshot_id'=%s
              AND rel.status IN ('published','withdrawn')
            ORDER BY rel.published_at DESC NULLS LAST
            LIMIT 1
            """,
            (snapshot_id,),
        ).fetchone()

    @classmethod
    def _assert_release_projection_reconciliation(
        cls,
        *,
        current_payload: Mapping[str, Any],
        submitted: Mapping[str, Any],
        release: Mapping[str, Any],
    ) -> None:
        cls._assert_working_payload_unchanged(
            current_payload=current_payload,
            submitted=submitted,
        )

        submitted_state = str(submitted.get("state") or "")
        release_status = str(release.get("status") or "")
        if submitted_state not in PUBLISHED_ENVELOPE_STATES:
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
        if release_status == "withdrawn":
            if submitted_state != "withdrawn":
                raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
        elif release_status == "published":
            if submitted_state not in {"published", "superseded"}:
                raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
        else:
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)

        if str(submitted.get("release_id") or "") != str(release["release_id"]):
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
        if str(submitted.get("release_version") or "") != str(release["release_version"]):
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
        if str(submitted.get("published_by") or "") != str(release["release_owner"]):
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
        if _instant(submitted.get("published_at")) != _instant(release["published_at"]):
            raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)

    def _write_release_projection_locked(
        self,
        con: Any,
        *,
        snapshot_id: str,
        envelope: Mapping[str, Any],
        current_payload: Mapping[str, Any],
    ) -> None:
        """Update only rebuildable release projection fields after sealing.

        Reviewer rows and working-object rows are deliberately untouched. The
        workflow state is copied from the already-validated historical projection
        instead of being hard-coded back to ``published``.
        """
        if '_document_inputs' in current_payload:
            self._write_envelope_locked(con,envelope)
            return
        stored = dict(envelope)
        if stored.get("processing_storage") == "task-v1":
            stored.pop("processing_attempts",None)
        for field in _DATABASE_MANAGED_LIFECYCLE_PROJECTION_FIELDS:
            if field not in stored and field in current_payload:
                stored[field] = current_payload[field]
        con.execute(
            "UPDATE workflow.documents SET "
            "state=%s,envelope_payload=%s::jsonb,"
            "revision=revision+1,updated_at=CURRENT_TIMESTAMP "
            "WHERE snapshot_id=%s",
            (str(envelope.get("state") or ""), _json_text(stored), snapshot_id),
        )

    def write_bundle(
        self,
        *,
        envelope: Mapping[str, Any],
        objects: list[dict[str, Any]] | None = None,
        expected_revision: str | None = None,
        review_card_preparation=None,
        formation_activation_ref=None,
        document_storage_admission=False,
    ) -> str:
        snapshot_id = str(envelope.get("snapshot_id") or "")
        if not snapshot_id:
            raise WorkflowDocumentStoreError("workflow_document_metadata_incomplete")
        if formation_activation_ref is not None and objects is None:
            raise WorkflowDocumentStoreError('formation_evidence_activation_objects_required')
        try:
            with self._connect() as con:
                with con.transaction():
                    if expected_revision == "":
                        con.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (snapshot_id,))
                    existing = con.execute(
                        "SELECT d.snapshot_id,d.topic_id,workflow.current_document_envelope(d) AS envelope_payload,t.display_name "
                        "FROM workflow.documents d "
                        "LEFT JOIN workflow.topics t ON t.topic_id=d.topic_id "
                        "WHERE d.snapshot_id=%s FOR UPDATE OF d",
                        (snapshot_id,),
                    ).fetchone()
                    current_objects: list[dict[str, Any]] = []
                    if existing is not None:
                        if expected_revision == "":
                            raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                        current_objects = self._objects_locked(con, snapshot_id)
                        release_history = self._release_history_locked(con, snapshot_id)
                        if release_history is not None:
                            if objects is not None:
                                raise WorkflowDocumentStoreError(PUBLISHED_WORKING_REVISION_IMMUTABLE)
                            current_payload = self._payload(existing["envelope_payload"])
                            if current_payload.get("processing_storage") == "task-v1":
                                current_payload = self._envelope_from_row(con,existing)
                            topic_id = str(existing.get("topic_id") or "")
                            display_name = str(existing.get("display_name") or "")
                            if not topic_id or not display_name:
                                raise WorkflowDocumentStoreError("workflow_topic_identity_not_prepared")
                            current_payload["topic_id"] = topic_id
                            current_payload["family"] = display_name
                            self._assert_release_projection_reconciliation(
                                current_payload=current_payload,
                                submitted=envelope,
                                release=release_history,
                            )
                            self._write_release_projection_locked(
                                con,
                                snapshot_id=snapshot_id,
                                envelope=envelope,
                                current_payload=current_payload,
                            )
                            return self._revision_token(current_objects)
                    elif expected_revision not in (None, ""):
                        raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)

                    if objects is not None:
                        from src.workflows.formation_task_store_v1 import FormationTaskStore
                        FormationTaskStore.assert_activation(con,envelope,formation_activation_ref)
                    self._write_envelope_locked(con, envelope,document_storage_admission=document_storage_admission)
                    from src.workflows.review_card_inputs_postgres_v1 import publish_preparation
                    publish_preparation(self, con, snapshot_id, review_card_preparation)
                    next_objects = current_objects
                    if objects is not None:
                        current_revisions(objects, snapshot_id=snapshot_id)
                        next_objects = self._merge_objects(
                            current=current_objects,
                            submitted=objects,
                            expected_revision=None if existing is None and expected_revision == "" else expected_revision,
                        )
                        validate_revision_write(current_objects, next_objects, snapshot_id=snapshot_id)
                        self._write_objects_locked(con, snapshot_id, current_objects, next_objects)
                        from src.workflows.review_card_inputs_postgres_v1 import maintain
                        maintain(self, con, snapshot_id, next_objects, complete=True, preparation=review_card_preparation)
            return self._revision_token(next_objects)
        except WorkflowDocumentStoreError:
            raise
        except Exception as exc:
            raise WorkflowDocumentStoreError("workflow_document_bundle_write_failed") from exc

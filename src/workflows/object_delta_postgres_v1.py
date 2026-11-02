"""Transaction-local proof of actual full-writer SQL under the document owner.

The original revision validator still decides which transition is permitted.
This owner checks the physical write without reading/validating its history a
second time. Nothing here is persisted except the existing derived frontiers.
"""
from collections import Counter, defaultdict
from copy import deepcopy

from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text

CONFLICT = 'snapshot_object_write_conflict'


def _epochs(con, sid):
    return {row['object_id']: row['mutation_epoch'] for row in con.execute(
        'SELECT object_id,mutation_epoch FROM workflow.object_revision_frontiers '
        'WHERE snapshot_id=%s ORDER BY object_id FOR UPDATE', (sid,)).fetchall()}


class PhysicalObjectHistory(list):
    """Exact locked rows, tied to their originating store/connection/snapshot."""

    def __init__(self, store, con, sid, rows, epochs):
        super().__init__(deepcopy(row['payload']) for row in rows)
        self.owner, self.connection, self.snapshot_id = store, con, sid
        self.rows = {(row['object_id'], row['object_version']):
                     (row['position'], _json_text(row['payload'])) for row in rows}
        self.epochs = epochs


def capture(store, con, sid):
    from src.workflows.revision_frontiers_postgres_v1 import supported, _check_physical
    prepared = supported(store, con)
    epochs = _epochs(con, sid) if prepared else None
    rows = con.execute('SELECT object_id,object_version,position,payload '
        'FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position FOR UPDATE', (sid,)).fetchall()
    if any(row['position'] is None for row in rows):
        raise WorkflowDocumentStoreError('workflow_document_cutover_not_prepared')
    _check_physical(rows)
    return PhysicalObjectHistory(store, con, sid, rows, epochs)


class VerifiedObjectDelta:
    def __init__(self, baseline, following, affected):
        self.baseline = baseline
        self.following = deepcopy(list(following))
        self.affected = dict(affected)

    def seal(self, store, con, sid, current):
        from src.workflows.revision_frontiers_postgres_v1 import _certificate, _install
        from src.review.revision_workflow import historical_revision_inputs
        before = self.baseline
        if before.owner is not store or before.connection is not con or before.snapshot_id != sid:
            raise WorkflowDocumentStoreError(CONFLICT)
        if before.epochs is None:
            return
        expected = dict(before.epochs)
        for oid, count in self.affected.items():
            expected[oid] = expected.get(oid, 0) + count
        if _epochs(con, sid) != expected:
            raise WorkflowDocumentStoreError(CONFLICT)
        # Epochs detect extra UPDATE/DELETE/INSERT, including hidden history and
        # same-connection AFTER-trigger writes. Physical metadata also protects
        # the complete identity/order/count, without detoasting payloads again.
        physical = con.execute('SELECT object_id,object_version,position '
            'FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position', (sid,)).fetchall()
        wanted = [(obj['object_id'], obj['object_version'], pos) for pos, obj in enumerate(self.following)]
        if [(row['object_id'], row['object_version'], row['position']) for row in physical] != wanted:
            raise WorkflowDocumentStoreError(CONFLICT)
        grouped = defaultdict(list)
        for position, obj in enumerate(self.following):
            grouped[obj['object_id']].append((position, obj))
        if ({obj['object_id']: _json_text(obj) for obj in current}
                != {oid: _json_text(items[-1][1]) for oid, items in grouped.items()}):
            raise WorkflowDocumentStoreError(CONFLICT)
        for obj in current:
            oid = obj['object_id']
            items = grouped[oid]
            cert = _certificate(obj, snapshot_id=sid, epoch=expected[oid], count=len(items),
                first=items[0][0], position=items[-1][0],
                historical=historical_revision_inputs([row for _, row in items[:-1]]))
            _install(con, sid, oid, cert)


def write(store, con, sid, before, following):
    """Every own DML must return exactly its planned physical row and payload."""
    if (not isinstance(before, PhysicalObjectHistory) or before.owner is not store
            or before.connection is not con or before.snapshot_id != sid):
        raise WorkflowDocumentStoreError(CONFLICT)
    stored = before.rows
    if {(obj['object_id'], obj['object_version']): _json_text(obj) for obj in before} != {
            key: raw for key, (_, raw) in stored.items()}:
        raise WorkflowDocumentStoreError(CONFLICT)
    kept = {(obj['object_id'], obj['object_version']) for obj in following}
    affected = Counter()

    def verify(cursor, identity, position, raw):
        row = cursor.fetchone()
        if (cursor.rowcount != 1 or row is None
                or (row['snapshot_id'], row['object_id'], row['object_version']) != (sid, *identity)
                or row['position'] != position or _json_text(row['payload']) != raw):
            raise WorkflowDocumentStoreError(CONFLICT)
        affected[identity[0]] += 1

    returning = ' RETURNING snapshot_id,object_id,object_version,position,payload'
    for identity in sorted(set(stored) - kept):
        cursor = con.execute('DELETE FROM workflow.document_objects WHERE snapshot_id=%s '
            'AND object_id=%s AND object_version=%s' + returning, (sid, *identity))
        verify(cursor, identity, *stored[identity])
    for position, obj in enumerate(following):
        identity = (obj['object_id'], obj['object_version'])
        raw = _json_text(obj)
        if identity not in stored:
            cursor = con.execute('INSERT INTO workflow.document_objects '
                '(snapshot_id,object_id,object_version,payload,position) VALUES(%s,%s,%s,%s::jsonb,%s)' + returning,
                (sid, *identity, raw, position))
        elif stored[identity][1] != raw:
            cursor = con.execute('UPDATE workflow.document_objects SET payload=%s::jsonb,position=%s,'
                'revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE snapshot_id=%s '
                'AND object_id=%s AND object_version=%s' + returning, (raw, position, sid, *identity))
        elif stored[identity][0] != position:
            cursor = con.execute('UPDATE workflow.document_objects SET position=%s WHERE snapshot_id=%s '
                'AND object_id=%s AND object_version=%s' + returning, (position, sid, *identity))
        else:
            continue
        verify(cursor, identity, position, raw)
    return VerifiedObjectDelta(before, following, affected)

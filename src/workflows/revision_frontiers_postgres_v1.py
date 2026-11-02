"""Derived historical validation under the existing workflow document owner.

Full preparation seals exact physical history once. A prepared mutation reads
raw current heads and independently validates/reseals only its ordered delta.
"""
from collections import defaultdict
from uuid import uuid4

from src.integrity_kernel import compute_canonical_object_hash, stable_hash, KERNEL_VERSION, SHA256_RE
from src.review.revision_window_v1 import RevisionWindow
from src.review.revision_workflow import current_revisions, LINEAGE_CONTRACT, historical_revision_inputs
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text

CONTRACT = 'object-revision-frontier-v1/' + LINEAGE_CONTRACT + '/' + KERNEL_VERSION
CONFLICT = 'snapshot_object_write_conflict'


def available(con):
    return con.execute("SELECT to_regclass('workflow.object_revision_frontiers') AS name").fetchone()['name'] is not None


def supported(store, con):
    # Cache schema presence only, never a frontier, data or authorization result.
    if getattr(store, '_revision_frontier_schema', False):
        return True
    if available(con):
        row = con.execute("SELECT (SELECT count(*) FROM pg_trigger WHERE "
            "tgrelid='workflow.document_objects'::regclass AND NOT tgisinternal AND tgenabled IN ('O','A') "
            "AND tgname IN ('zz_object_revision_frontier_change','zz_object_revision_frontier_truncate'))=2 "
            "AND EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='workflow.document_objects'::regclass "
            "AND confrelid='workflow.object_revision_frontiers'::regclass AND contype='f' AND condeferrable "
            "AND condeferred AND convalidated AND conname='workflow_object_revision_frontier_fk') "
            "AND EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='workflow.object_revision_frontiers'::regclass "
            "AND contype='c' AND convalidated AND conname='workflow_revision_frontier_integrity') "
            "AND to_regprocedure('workflow.revision_source_sequence(jsonb)') IS NOT NULL AS ready").fetchone()
        if row['ready']:
            store._revision_frontier_schema = True
            return True
    return False


def heads(con, sid, ids):
    return con.execute('SELECT o.object_id,o.object_version,o.position,o.payload FROM unnest(%s::text[]) wanted(object_id) '
        'CROSS JOIN LATERAL (SELECT object_id,object_version,position,payload FROM workflow.document_objects '
        'WHERE snapshot_id=%s AND object_id=wanted.object_id ORDER BY position DESC LIMIT 1) o',
        (sorted(set(ids)), sid)).fetchall() if ids else []


def capture(store, con, sid, ids):
    if not supported(store, con):
        return None
    wanted = ('(SELECT f.object_id FROM workflow.object_revision_frontiers f WHERE f.snapshot_id=%s '
              'AND EXISTS(SELECT 1 FROM workflow.document_objects o WHERE o.snapshot_id=f.snapshot_id '
              'AND o.object_id=f.object_id))' if ids is None else 'unnest(%s::text[])')
    records = con.execute("SELECT wanted.object_id,o.object_version,f.mutation_epoch,f.certificate,"
        "f.certificate_hash=encode(sha256(convert_to(f.certificate::text,'UTF8')),'hex') AS intact,o.position,o.payload "
        'FROM ' + wanted + ' wanted(object_id) LEFT JOIN LATERAL '
        '(SELECT object_version,position,payload FROM workflow.document_objects WHERE snapshot_id=%s '
        'AND object_id=wanted.object_id ORDER BY position DESC LIMIT 1) o ON true '
        'LEFT JOIN workflow.object_revision_frontiers f ON f.snapshot_id=%s AND f.object_id=wanted.object_id',
        (sid if ids is None else sorted(set(ids)), sid, sid)).fetchall()
    certs = {}
    for record in records:
        if record['payload'] is None and record['mutation_epoch'] is None:
            continue  # unknown dependency; the existing kernel decides its use
        cert = record['certificate']
        if (not isinstance(cert, dict) or cert.get('contract') != CONTRACT
                or cert.get('snapshot_id') != sid or cert.get('object_id') != record['object_id']
                or cert.get('epoch') != record['mutation_epoch']
                or not isinstance(cert.get('issuance'), str) or len(cert['issuance']) != 32
                or any(type(cert.get(key)) is not int for key in ('epoch', 'history_count', 'first_position', 'head_position'))
                or cert['history_count'] < 1 or not 0 <= cert['first_position'] <= cert['head_position']
                or any(type(cert.get(key)) is not bool for key in ('historical_has_knowledge', 'historical_has_publication'))
                or not isinstance(cert.get('head_version'), str) or not cert['head_version']
                or any(not isinstance(cert.get(key), str) or not SHA256_RE.fullmatch(cert[key])
                       for key in ('raw_hash', 'canonical_hash'))
                or not record['intact']):
            return None
        certs[record['object_id']] = cert
    actual = [row for row in records if row['payload'] is not None]
    if set(certs) != {row['payload']['object_id'] for row in actual}:
        return None
    for row in actual:
        obj, position = row['payload'], row['position']
        cert = certs[obj['object_id']]
        if (position is None or position != cert['head_position']
                or obj['object_id'] != row['object_id'] or obj['object_version'] != row['object_version']
                or obj['object_version'] != cert['head_version']
                or stable_hash(obj) != cert['raw_hash']
                or compute_canonical_object_hash(obj) != cert['canonical_hash']):
            return None
    actual.sort(key=lambda row: certs[row['payload']['object_id']]['first_position'])
    return RevisionWindow([row['payload'] for row in actual], owner=store, snapshot_id=sid, frontiers=certs)


def _certificate(obj, *, snapshot_id, epoch, count, first, position, historical):
    structure = obj.get('structure') or {}
    sequence = structure.get('sequence', 0) if isinstance(structure, dict) else None
    return {'contract': CONTRACT, 'issuance': uuid4().hex, 'epoch': epoch,
        **historical,
        'snapshot_id': snapshot_id, 'object_id': obj['object_id'],
        'source_sequence': sequence, 'object_type': obj.get('object_type'),
        'history_count': count, 'first_position': first, 'head_position': position,
        'head_version': obj['object_version'], 'canonical_hash': compute_canonical_object_hash(obj),
        'raw_hash': stable_hash(obj)}


def _check_physical(rows):
    if any(not isinstance(row['payload'], dict) or row['object_id'] != row['payload'].get('object_id')
           or row['object_version'] != row['payload'].get('object_version') for row in rows):
        raise WorkflowDocumentStoreError('revision_frontier_identity_mismatch')


def admission_neighbors(store, con, sid, ids):
    """The gate's actual adjacent non-document records, including heading sentinels.

    Incomplete legacy indexing uses the named full compatibility path, never a
    subset that silently changes admission context. All object IDs are covered
    by the deferred storage FK; this lookup never scans retained history.
    """
    if not supported(store, con):
        return None
    invalid = con.execute('SELECT 1 FROM workflow.object_revision_frontiers f WHERE snapshot_id=%s '
        'AND (certificate IS NULL OR workflow.revision_source_sequence(certificate) IS NULL) '
        'AND EXISTS(SELECT 1 FROM workflow.document_objects o WHERE o.snapshot_id=f.snapshot_id '
        'AND o.object_id=f.object_id) LIMIT 1', (sid,)).fetchone()
    if invalid:
        return None
    rows = con.execute("""
        WITH centres AS (
          SELECT workflow.revision_source_sequence(certificate) AS sequence,
                 (certificate->>'first_position')::integer AS first_position
          FROM workflow.object_revision_frontiers WHERE snapshot_id=%s AND object_id=ANY(%s))
        SELECT DISTINCT neighbour.object_id FROM centres c CROSS JOIN LATERAL (
          (SELECT f.object_id FROM workflow.object_revision_frontiers f WHERE f.snapshot_id=%s
             AND f.certificate IS NOT NULL AND f.certificate->>'object_type' IS DISTINCT FROM 'document'
             AND (workflow.revision_source_sequence(f.certificate),(f.certificate->>'first_position')::integer)
                 < (c.sequence,c.first_position)
           ORDER BY workflow.revision_source_sequence(f.certificate) DESC,
                    (f.certificate->>'first_position')::integer DESC LIMIT 1)
          UNION ALL
          (SELECT f.object_id FROM workflow.object_revision_frontiers f WHERE f.snapshot_id=%s
             AND f.certificate IS NOT NULL AND f.certificate->>'object_type' IS DISTINCT FROM 'document'
             AND (workflow.revision_source_sequence(f.certificate),(f.certificate->>'first_position')::integer)
                 > (c.sequence,c.first_position)
           ORDER BY workflow.revision_source_sequence(f.certificate),
                    (f.certificate->>'first_position')::integer LIMIT 1)
        ) neighbour
        """, (sid, sorted(set(ids)), sid, sid)).fetchall()
    return [row['object_id'] for row in rows]


def _install(con, sid, oid, cert):
    raw = _json_text(cert)
    changed = con.execute("UPDATE workflow.object_revision_frontiers SET certificate=%s::jsonb,"
        "certificate_hash=encode(sha256(convert_to((%s::jsonb)::text,'UTF8')),'hex') "
        'WHERE snapshot_id=%s AND object_id=%s AND mutation_epoch=%s',
        (raw, raw, sid, oid, cert['epoch']))
    if changed.rowcount != 1:
        raise WorkflowDocumentStoreError(CONFLICT)


def seal_complete(store, con, sid, proposed):
    """Only complete raw physical history can issue a new historical boundary."""
    if not supported(store, con):
        return
    ids = sorted({obj['object_id'] for obj in proposed})
    if not ids:
        return
    for oid in ids:
        con.execute('INSERT INTO workflow.object_revision_frontiers(snapshot_id,object_id) VALUES(%s,%s) '
                    'ON CONFLICT DO NOTHING', (sid, oid))
    # Lock before the physical read. Reading a newer epoch after an older raw
    # history could otherwise certify that stale history after a direct writer.
    epochs = {row['object_id']: row['mutation_epoch'] for row in con.execute(
        'SELECT object_id,mutation_epoch FROM workflow.object_revision_frontiers '
        'WHERE snapshot_id=%s AND object_id=ANY(%s) ORDER BY object_id FOR UPDATE', (sid, ids)).fetchall()}
    physical = con.execute('SELECT object_id,object_version,position,payload FROM workflow.document_objects '
        'WHERE snapshot_id=%s AND object_id=ANY(%s) ORDER BY position', (sid, ids)).fetchall()
    _check_physical(physical)
    rows = [row['payload'] for row in physical]
    if any(row['position'] is None for row in physical) or _json_text(rows) != _json_text(list(proposed)):
        raise WorkflowDocumentStoreError('revision_frontier_history_mismatch')
    current = {row['object_id']: row for row in current_revisions(rows, snapshot_id=sid)}
    grouped = defaultdict(list)
    for row in physical:
        grouped[row['payload']['object_id']].append(row)
    for oid, items in grouped.items():
        cert = _certificate(current[oid], snapshot_id=sid, epoch=epochs[oid], count=len(items),
            first=items[0]['position'], position=items[-1]['position'],
            historical=historical_revision_inputs([row['payload'] for row in items[:-1]]))
        _install(con, sid, oid, cert)


def check_current(store, con, sid, before):
    if before.owner is not store or before.snapshot_id != sid:
        raise WorkflowDocumentStoreError('revision_window_mismatch')
    current = capture(store, con, sid, before.frontiers)
    if (current is None or current.frontiers != before.frontiers
            or _json_text(list(current)) != _json_text(list(before))):
        raise WorkflowDocumentStoreError(CONFLICT)
    return current


def seal_delta(store, con, sid, before, after, affected):
    """Own SQL rowcounts plus native epochs protect unseen history, including
    an extra write made on this same connection after the earlier check.
    """
    old = before.frontiers
    ids = sorted({obj['object_id'] for obj in after})
    actual = {row['payload']['object_id']: row for row in heads(con, sid, ids)}
    _check_physical(list(actual.values()))
    epochs = {row['object_id']: row['mutation_epoch'] for row in con.execute(
        'SELECT object_id,mutation_epoch FROM workflow.object_revision_frontiers '
        'WHERE snapshot_id=%s AND object_id=ANY(%s) FOR UPDATE', (sid, ids)).fetchall()}
    visible = defaultdict(list)
    for obj in after:
        visible[obj['object_id']].append(obj)
    positions = {}
    for oid in ids:
        previous = old.get(oid)
        count = affected.get(oid, 0)
        if epochs.get(oid) != (previous['epoch'] if previous else 0) + count:
            raise WorkflowDocumentStoreError(CONFLICT)
        head = actual[oid]
        if stable_hash(head['payload']) != stable_hash(visible[oid][-1]):
            raise WorkflowDocumentStoreError(CONFLICT)
        cert = previous
        if count:
            base_count = previous['history_count'] if previous else 0
            added = len(visible[oid]) - (1 if previous else 0)
            first = previous['first_position'] if previous else con.execute(
                'SELECT position FROM workflow.document_objects WHERE snapshot_id=%s AND object_id=%s '
                'ORDER BY position LIMIT 1', (sid, oid)).fetchone()['position']
            cert = _certificate(head['payload'], snapshot_id=sid, epoch=epochs[oid], count=base_count + added,
                first=first, position=head['position'], historical={key: value or bool((previous or {}).get(key))
                    for key, value in historical_revision_inputs(visible[oid][:-1]).items()})
            _install(con, sid, oid, cert)
        positions[oid] = {'n': cert['history_count'], 'first_position': cert['first_position'], 'positioned': True}
    return positions


def prepare(store, sid):
    """Explicit retained-data preparation; validation is outside write locks."""
    with store._connect() as con:
        with con.transaction():
            con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            if not supported(store, con):
                raise WorkflowDocumentStoreError('revision_frontier_schema_unprepared')
            if con.execute('SELECT 1 FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone() is None:
                raise WorkflowDocumentStoreError('unknown_snapshot')
            physical = con.execute('SELECT object_id,object_version,position,payload FROM workflow.document_objects '
                'WHERE snapshot_id=%s ORDER BY position', (sid,)).fetchall()
            epochs = {row['object_id']: row['mutation_epoch'] for row in con.execute(
                'SELECT object_id,mutation_epoch FROM workflow.object_revision_frontiers WHERE snapshot_id=%s',
                (sid,)).fetchall()}
    if any(row['position'] is None for row in physical):
        raise WorkflowDocumentStoreError('workflow_document_cutover_not_prepared')
    _check_physical(physical)
    current = {row['object_id']: row for row in current_revisions(
        [row['payload'] for row in physical], snapshot_id=sid)}
    grouped = defaultdict(list)
    for row in physical:
        grouped[row['payload']['object_id']].append(row)
    certificates = {oid: _certificate(current[oid], snapshot_id=sid, epoch=epochs.get(oid, 0), count=len(rows),
        first=rows[0]['position'], position=rows[-1]['position'],
        historical=historical_revision_inputs([row['payload'] for row in rows[:-1]])) for oid, rows in grouped.items()}
    with store._connect() as con:
        with con.transaction():
            if con.execute('SELECT 1 FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (sid,)).fetchone() is None:
                raise WorkflowDocumentStoreError('unknown_snapshot')
            for oid in sorted(certificates):
                con.execute('INSERT INTO workflow.object_revision_frontiers(snapshot_id,object_id) VALUES(%s,%s) '
                    'ON CONFLICT DO NOTHING', (sid, oid))
                _install(con, sid, oid, certificates[oid])
    return {'snapshot_id': sid, 'objects': len(certificates), 'status': 'prepared'}

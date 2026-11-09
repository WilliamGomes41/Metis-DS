"""Publisher-only test lineage removal inside the existing PostgreSQL kernel.

Normal unpublished deletion, published immutability and Blob retention remain
under their existing owners. This command removes a complete confirmed lineage,
preserves the global review hash chain and fences stale snapshot resurrection.
"""
import os
import re
from datetime import datetime, timezone
from psycopg.errors import LockNotAvailable

from src.integrity_kernel import stable_hash
from src.operations_console_v1 import ConsoleError
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.workflows.workflow_transaction_v1 import (
    bind_workflow_stores, workflow_transaction, workflow_transaction_active,
)

CANONICAL_TABLES = ('source_snapshots', 'canonical_object_versions', 'canonical_object_sources',
    'publication_releases', 'publication_release_items', 'publication_registry', 'audit_events')
DELETE_TABLES = tuple('public.' + name for name in CANONICAL_TABLES) + (
    'workflow.documents', 'workflow.publication_refusals', 'workflow.view_checks')
DELETE_PRIVILEGES = {table: ('SELECT', 'DELETE') for table in DELETE_TABLES}
SNAPSHOT_FENCE_LOCK = 2110039  # Shared with migration 039's FK-less operational-row guard.
TRIGGERS = {('workflow.documents', 'refuse_deleted_test_document'),
            ('workflow.review_events', 'guard_test_deletion_ledger'),
            ('workflow.view_checks', 'refuse_deleted_test_view_check'),
            ('workflow.publication_refusals', 'refuse_deleted_test_publication_refusal'),
            ('source_snapshots', 'refuse_deleted_test_source')}


def enabled():
    return os.environ.get('CONSOLE_TEST_DOCUMENT_DELETION', 'off') == 'on'


def _authorize(console, actor_id):
    console._require_role(actor_id, 'publisher')
    if not enabled():
        raise ConsoleError('test_document_deletion_disabled')
    store = getattr(console, 'workflow_document_store', None)
    canonical = getattr(console, 'canonical_publication_store', None)
    if (store is None or not isinstance(canonical, PostgresCanonicalPublicationStore)
            or store.config != canonical.config):
        raise ConsoleError('test_document_deletion_database_mismatch')
    return store


def _storage(con):
    if con.execute("SELECT to_regclass('workflow.deleted_test_snapshots') AS name").fetchone()['name'] is None:
        raise ConsoleError('test_document_deletion_storage_not_ready')
    guards = {(r['relation'], r['tgname']) for r in con.execute(
        "SELECT tgrelid::regclass::text AS relation,tgname FROM pg_trigger "
        "WHERE tgname=ANY(%s) AND tgenabled IN ('O','A')",
        ([name for _, name in TRIGGERS],)).fetchall()}
    if guards != TRIGGERS:
        raise ConsoleError('test_document_deletion_storage_not_ready')
    if any(not con.execute('SELECT has_table_privilege(current_user,%s,%s) AS ok',
                           (table, privilege)).fetchone()['ok']
           for table, privileges in DELETE_PRIVILEGES.items() for privilege in privileges):
        raise ConsoleError('test_document_deletion_grants_required')


def _inventory(con, snapshot_id):
    selected = con.execute('SELECT snapshot_id,title,logical_document_id FROM workflow.documents WHERE snapshot_id=%s',
                           (snapshot_id,)).fetchone()
    if selected is None:
        raise ConsoleError('unknown_snapshot')
    logical = selected['logical_document_id']
    if not logical:
        raise ConsoleError('test_document_deletion_lineage_required')
    documents = con.execute('SELECT snapshot_id,title,source_version,source_sha256,working_revision_id,object_generation '
        'FROM workflow.documents WHERE logical_document_id=%s ORDER BY snapshot_id', (logical,)).fetchall()
    snapshots = {r['snapshot_id'] for r in documents}
    history = con.execute("SELECT entity_id,details FROM public.audit_events WHERE entity_type='release' "
        "AND event_type='release_published' AND (details->>'logical_document_id'=%s "
        "OR details->>'snapshot_id'=ANY(%s)) ORDER BY entity_id", (logical, sorted(snapshots))).fetchall()
    for event in history:
        details = event['details']
        if details.get('logical_document_id') and details['logical_document_id'] != logical:
            raise ConsoleError('test_document_deletion_shared_release')
        if details.get('snapshot_id'):
            snapshots.add(details['snapshot_id'])
    snapshots = sorted(snapshots)
    if con.execute('SELECT 1 FROM workflow.documents WHERE snapshot_id=ANY(%s) '
                   'AND logical_document_id<>%s LIMIT 1', (snapshots, logical)).fetchone():
        raise ConsoleError('test_document_deletion_shared_release')
    if con.execute('SELECT 1 FROM workflow.documents WHERE replaces_snapshot_id=ANY(%s) '
                   'AND NOT(snapshot_id=ANY(%s)) LIMIT 1', (snapshots, snapshots)).fetchone():
        raise ConsoleError('test_document_deletion_cross_lineage_successor')
    objects = con.execute('SELECT s.object_id,s.object_version,c.content_hash FROM public.canonical_object_sources s '
        'JOIN public.canonical_object_versions c USING(object_id,object_version) WHERE s.snapshot_id=ANY(%s) '
        'ORDER BY s.object_id,s.object_version', (snapshots,)).fetchall()
    releases = {e['entity_id'] for e in history}
    releases.update(r['release_id'] for r in con.execute('SELECT DISTINCT i.release_id FROM public.publication_release_items i '
        'JOIN public.canonical_object_sources s USING(object_id,object_version) WHERE s.snapshot_id=ANY(%s)', (snapshots,)).fetchall())
    releases = sorted(releases)
    if con.execute('SELECT 1 FROM public.publication_release_items i LEFT JOIN public.canonical_object_sources s '
        'USING(object_id,object_version) WHERE i.release_id=ANY(%s) '
        'AND (s.snapshot_id IS NULL OR NOT(s.snapshot_id=ANY(%s))) LIMIT 1', (releases, snapshots)).fetchone():
        raise ConsoleError('test_document_deletion_shared_release')
    if con.execute("SELECT 1 FROM public.audit_events WHERE entity_type='release' AND entity_id=ANY(%s) "
        "AND event_type='release_published' AND ((COALESCE(details->>'logical_document_id','')<>'' "
        "AND details->>'logical_document_id'<>%s) OR (COALESCE(details->>'snapshot_id','')<>'' "
        "AND NOT(details->>'snapshot_id'=ANY(%s)))) LIMIT 1", (releases, logical, snapshots)).fetchone():
        raise ConsoleError('test_document_deletion_shared_release')
    attempts = con.execute('SELECT snapshot_id,attempt_id,payload FROM workflow.processing_attempts '
                           'WHERE snapshot_id=ANY(%s) ORDER BY attempt_id', (snapshots,)).fetchall()
    inline = con.execute("SELECT snapshot_id,envelope_payload->'processing_attempts' AS attempts FROM workflow.documents "
                         'WHERE snapshot_id=ANY(%s)', (snapshots,)).fetchall()
    running = sorted({r['snapshot_id'] for r in attempts if r['payload'].get('state') == 'running'} |
        {r['snapshot_id'] for r in inline if any(a.get('state') == 'running' for a in r['attempts'] or [])})
    versions = []
    for document in documents:
        sid = document['snapshot_id']
        counts = con.execute('SELECT '
            '(SELECT count(*) FROM workflow.document_objects WHERE snapshot_id=%s) AS objects,'
            '(SELECT count(*) FROM workflow.annotation_heads WHERE snapshot_id=%s) AS annotations,'
            '(SELECT count(*) FROM workflow.review_events WHERE snapshot_id=%s) AS reviews,'
            '(SELECT generation FROM workflow.annotation_sets WHERE snapshot_id=%s) AS annotation_generation',
            (sid, sid, sid, sid)).fetchone()
        versions.append({**document, **counts})
    registry = con.execute('SELECT object_id,object_version,release_id,state FROM public.publication_registry '
                           'WHERE release_id=ANY(%s) ORDER BY object_id', (releases,)).fetchall()
    plan = {'snapshot_id':snapshot_id, 'logical_document_id':logical, 'title':selected['title'],
        'snapshot_ids':snapshots, 'versions':versions, 'release_ids':releases,
        'historical_snapshot_ids':sorted(set(snapshots)-{r['snapshot_id'] for r in documents}),
        'canonical_objects':objects, 'registry':registry, 'running_snapshots':running}
    plan['fingerprint'] = stable_hash(plan)
    return plan


def preview(console, *, actor_id, snapshot_id):
    store = _authorize(console, actor_id)
    with store._connect() as con:
        con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        _storage(con)
        return _inventory(con, snapshot_id)


def receipt(console, *, actor_id, command_id):
    store = _authorize(console, actor_id)
    with store._connect() as con:
        _storage(con)
        row = con.execute('SELECT result FROM workflow.test_document_deletions WHERE command_id=%s', (command_id,)).fetchone()
    if row is None:
        raise ConsoleError('test_document_deletion_receipt_missing')
    return row['result']


def delete(console, *, actor_id, snapshot_id, command_id, expected_plan, confirm_title, reason, confirmed_test=False):
    store = _authorize(console, actor_id)
    if confirmed_test is not True:
        raise ConsoleError('test_document_deletion_confirmation_required')
    if (not isinstance(command_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', command_id)
            or not isinstance(expected_plan, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_plan)
            or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000):
        raise ConsoleError('test_document_deletion_command_invalid')
    if workflow_transaction_active():
        raise ConsoleError('test_document_deletion_independent_transaction_required')
    request_hash = stable_hash({'actor_id':actor_id,'snapshot_id':snapshot_id,'expected_plan':expected_plan,
                               'confirm_title':confirm_title,'reason':reason.strip()})
    bind_workflow_stores(store, console.workflow_review_store, console.workflow_identity_store)
    with console._store_write_lock():
        with workflow_transaction(store) as con:
            _storage(con)
            console.workflow_review_store._lock_authorizations(con)
            account = con.execute('SELECT username,roles,retirement FROM workflow.accounts WHERE account_id=%s FOR UPDATE',
                                  (actor_id,)).fetchone()
            if account is None or account['retirement'] is not None or 'publisher' not in account['roles']:
                raise ConsoleError('publisher_role_required')
            previous = con.execute('SELECT request_hash,result FROM workflow.test_document_deletions WHERE command_id=%s',
                                   (command_id,)).fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    raise ConsoleError('test_document_deletion_command_conflict')
                return previous['result']
            console.workflow_review_store._lock_review_ledger(con)
            # The document table excludes inline attempt starts. Operational
            # attempts have their own writer boundary; their document row lock
            # alone is compatible with the table lock above. NOWAIT refuses an
            # already-active writer instead of reversing its row-lock order.
            try:
                con.execute('LOCK TABLE workflow.documents IN SHARE ROW EXCLUSIVE MODE NOWAIT')
                con.execute('LOCK TABLE workflow.processing_attempts IN SHARE ROW EXCLUSIVE MODE NOWAIT')
            except LockNotAvailable as exc:
                raise ConsoleError('test_document_deletion_busy') from exc
            selected = con.execute('SELECT logical_document_id FROM workflow.documents WHERE snapshot_id=%s', (snapshot_id,)).fetchone()
            if selected is None:
                raise ConsoleError('unknown_snapshot')
            try:
                con.execute('SELECT snapshot_id FROM workflow.documents WHERE logical_document_id=%s '
                    'ORDER BY snapshot_id FOR UPDATE NOWAIT', (selected['logical_document_id'],)).fetchall()
            except LockNotAvailable as exc:
                raise ConsoleError('test_document_deletion_busy') from exc
            if not con.execute('SELECT pg_try_advisory_xact_lock(2110023,hashtext(%s)) AS locked',
                               (selected['logical_document_id'],)).fetchone()['locked']:
                raise ConsoleError('test_document_deletion_busy')
            try:
                for table in CANONICAL_TABLES:
                    con.execute('LOCK TABLE public.'+table+' IN SHARE ROW EXCLUSIVE MODE NOWAIT')
            except LockNotAvailable as exc:
                raise ConsoleError('test_document_deletion_busy') from exc
            plan = _inventory(con, snapshot_id)
            for sid in plan['snapshot_ids']:
                if not con.execute('SELECT pg_try_advisory_xact_lock(%s,hashtext(%s)) AS locked',
                                   (SNAPSHOT_FENCE_LOCK,sid)).fetchone()['locked']:
                    raise ConsoleError('test_document_deletion_busy')
            if plan['fingerprint'] != expected_plan:
                raise ConsoleError('test_document_deletion_plan_changed')
            if confirm_title != plan['title']:
                raise ConsoleError('delete_title_confirmation_required')
            if plan['running_snapshots']:
                raise ConsoleError('test_document_deletion_processing_running')
            result = {'deleted':True,'command_id':command_id,'logical_document_id':plan['logical_document_id'],
                'snapshot_ids':plan['snapshot_ids'],'versions':len(plan['snapshot_ids']),
                'publications':len(plan['release_ids']),'canonical_objects':len(plan['canonical_objects']),
                'recorded_at':datetime.now(timezone.utc).isoformat(),
                'retained':['control_history','source_files_and_backups']}
            import json
            con.execute('INSERT INTO workflow.test_document_deletions(command_id,actor_id,logical_document_id,request_hash,reason,result) '
                'VALUES(%s,%s,%s,%s,%s,%s::jsonb)', (command_id,actor_id,plan['logical_document_id'],request_hash,reason.strip(),json.dumps(result)))
            for sid in plan['snapshot_ids']:
                con.execute('INSERT INTO workflow.deleted_test_snapshots(snapshot_id,command_id,logical_document_id) VALUES(%s,%s,%s)',
                            (sid,command_id,plan['logical_document_id']))
            ids, releases = plan['snapshot_ids'], plan['release_ids']
            con.execute('DELETE FROM public.publication_registry WHERE release_id=ANY(%s)', (releases,))
            con.execute('DELETE FROM public.publication_release_items WHERE release_id=ANY(%s)', (releases,))
            con.execute("DELETE FROM public.audit_events WHERE (entity_type='release' AND entity_id=ANY(%s)) "
                "OR details->>'snapshot_id'=ANY(%s) OR details->>'release_id'=ANY(%s) "
                "OR details->>'logical_document_id'=%s", (releases,ids,releases,plan['logical_document_id']))
            keys = plan['canonical_objects']
            con.execute('DELETE FROM public.canonical_object_sources WHERE snapshot_id=ANY(%s)', (ids,))
            con.execute('DELETE FROM public.canonical_object_versions WHERE (object_id,object_version) IN '
                '(SELECT * FROM unnest(%s::text[],%s::text[]))',
                ([r['object_id'] for r in keys],[r['object_version'] for r in keys]))
            con.execute('DELETE FROM public.publication_releases WHERE release_id=ANY(%s)', (releases,))
            con.execute('DELETE FROM public.source_snapshots WHERE snapshot_id=ANY(%s)', (ids,))
            # Preserve global hash-chain bodies/hashes, as in delete_document.
            con.execute('UPDATE workflow.review_events SET snapshot_id=NULL WHERE snapshot_id=ANY(%s)', (ids,))
            con.execute('DELETE FROM workflow.publication_refusals WHERE snapshot_id=ANY(%s)', (ids,))
            con.execute('DELETE FROM workflow.view_checks WHERE snapshot_id=ANY(%s)', (ids,))
            con.execute("SELECT set_config('metis.document_storage_writer','v1',true)")
            con.execute('DELETE FROM workflow.documents WHERE snapshot_id=ANY(%s)', (ids,))
            console.workflow_review_store.append_event(event_type='test_document_deleted',
                object_id=plan['logical_document_id'],object_version='',actor=account['username'],
                details={'command_id':command_id,'logical_document_id':plan['logical_document_id'],
                         'snapshot_count':len(ids),'release_count':len(releases)})
        # Reload only after the authoritative commit. A refresh failure cannot
        # make a completed deletion appear failed; the durable receipt is final.
        for sid in plan['snapshot_ids']:
            console._envelopes.pop(sid, None)
            console._bindings.pop(sid, None)
        return result

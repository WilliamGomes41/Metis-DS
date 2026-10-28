"""Refusal records in the evidence export, and retired file-store records in offline backups.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: releasebewijs

Rules (B18): the per-document evidence export MOET contain that document's refusal records and
NOOIT another document's. Since D6b no runtime path writes the JSONL file store; the offline runtime
backup still carries such legacy files byte-identical.
"""
import json
import csv
import io
from zipfile import ZipFile

import src.publication.publication_refusal_store_v1 as store
from src.vorming.processing_evidence_export_v1 import processing_evidence_tables
from src.runtime_data_inventory_v1 import (
    INVENTORY_CATEGORIES, export_runtime_data, inventory_runtime_data, restore_runtime_data,
)

RUNTIME = 'output/runtime/operations-console'


def _legacy_append(path, *, snapshot_id, actor):
    """A record as the retired file store wrote it (no runtime writer since D6b)."""
    from datetime import datetime, timezone
    record = store._record(store._key(snapshot_id, ['r'], actor), '1', 'rev', datetime.now(timezone.utc),
                           store.STORE_STATUS)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n')


def _seed(root):
    path = root / RUNTIME / store.FILE_NAME
    for sid, actor in (('snap-a', 'acc-1'), ('snap-b', 'acc-2')):
        _legacy_append(path, snapshot_id=sid, actor=actor)
    return path


def test_evidence_export_contains_only_this_documents_refusals(tmp_path):
    path = _seed(tmp_path)
    tables, manifest = processing_evidence_tables(
        snapshot_id='snap-a', revision='rev', envelope={}, objects=[], refusals=store.read_records(path))
    rows = tables['publication_refusals']
    assert [r['refusal_snapshot_id'] for r in rows] == ['snap-a']
    assert 'actor' not in rows[0] and rows[0]['store_status'] == store.STORE_STATUS
    [entry] = [m for m in manifest if m['dataset'] == 'publication_refusals.csv']
    assert entry['row_count'] == 1 and entry['availability'] == 'recorded'


def test_evidence_export_without_store_reads_marks_not_recorded(tmp_path):
    tables, manifest = processing_evidence_tables(snapshot_id='snap-a', revision='rev', envelope={}, objects=[])
    assert tables['publication_refusals'] == []
    [entry] = [m for m in manifest if m['dataset'] == 'publication_refusals.csv']
    assert entry['availability'] == 'not_recorded'


def test_runtime_backup_contains_and_restores_the_refusal_store(tmp_path):
    root = tmp_path / 'data'
    path = _seed(root)
    assert 'publication_refusals' in INVENTORY_CATEGORIES
    [category] = [c for c in inventory_runtime_data(root)['categories'] if c['category'] == 'publication_refusals']
    assert category['present'] and category['count'] == 2
    archive = tmp_path / 'backup.zip'
    export_runtime_data(root, archive)
    restored = tmp_path / 'restored'
    restore_runtime_data(archive, restored)
    assert (restored / RUNTIME / store.FILE_NAME).read_bytes() == path.read_bytes()


def test_backup_includes_the_rotated_generation(tmp_path):
    root = tmp_path / 'data'
    path = _seed(root)
    rotated = store.rotated_path(path)
    rotated.write_bytes(path.read_bytes())
    [category] = [c for c in inventory_runtime_data(root)['categories'] if c['category'] == 'publication_refusals']
    assert f'{RUNTIME}/{store.FILE_NAME}.1' in category['files']


def test_export_route_reads_postgres_table_when_present(monkeypatch):
    from src import operations_console_app as app_module
    calls = []

    class FakePg:
        def records_for(self, snapshot_id):
            calls.append(snapshot_id)
            return [{'snapshot_id': snapshot_id}]
    monkeypatch.setattr(store, 'postgres_store', lambda state: FakePg())
    assert app_module._refusal_records(object(), 'snap-a') == [{'snapshot_id': 'snap-a'}] and calls == ['snap-a']


# --- Sherlock FAIL #641 (1): corrupt or unreadable refusal records MOETEN be reported, NOOIT silently dropped ---

def test_unreadable_refusal_store_is_reported_not_swallowed(monkeypatch, caplog):
    import logging
    from src import operations_console_app as app_module

    class Broken:
        def records_for(self, snapshot_id):
            raise OSError('database gone password=hunter2')
    monkeypatch.setattr(store, 'postgres_store', lambda state: Broken())
    issues = []
    with caplog.at_level(logging.WARNING):
        assert app_module._refusal_records(object(), 'snap-a', issues=issues) is None
    assert issues == ['store_unreadable:OSError']
    assert 'publication_refusal_export_issue' in caplog.text and 'hunter2' not in caplog.text
    tables, manifest = processing_evidence_tables(snapshot_id='snap-a', revision='rev', envelope={}, objects=[],
                                                  refusals=None, refusal_issues=issues)
    [entry] = [m for m in manifest if m['dataset'] == 'publication_refusals.csv']
    assert entry['availability'] == 'unreadable' and 'store_unreadable:OSError' in entry['limitation']


def test_manifest_text_describes_the_current_store():
    # Sherlock FAIL #641 (2): the manifest MAG NIET still call the file store the store "until a PostgreSQL table".
    tables, manifest = processing_evidence_tables(snapshot_id='snap-a', revision='rev', envelope={}, objects=[], refusals=[])
    [entry] = [m for m in manifest if m['dataset'] == 'publication_refusals.csv']
    text = entry['limitation']
    assert 'until a PostgreSQL table' not in text and 'within 10 minutes' not in text
    assert 'workflow.publication_refusals' in text and 'file topology' not in text
    assert 'fixed 10-minute window' in text


# --- Lex advice / Metis GO (2026-10-16): actor identifiers MAG NIET be exported ---

def test_actor_columns_are_not_in_the_export_schemas():
    from src.vorming.processing_evidence_export_v1 import SCHEMAS
    for name in ('publication_refusals', 'processing_attempts', 'processing_recovery'):
        assert not {'actor', 'actor_id'} & set(SCHEMAS[name]), name


def test_no_plain_account_id_appears_anywhere_in_the_export(tmp_path):
    account = 'acc-lex-7f3a91'
    path = tmp_path / store.FILE_NAME
    _legacy_append(path, snapshot_id='snap-a', actor=account)
    envelope = {
        'processing_attempts': [{'attempt_id': 'pa-1', 'command_id': 'c-1', 'actor_id': account, 'state': 'failed'}],
        'processing_recovery': {'authorization_id': 'auth-1', 'actor_id': account, 'reason': 'r', 'consumed_by': 'pa-1'},
    }
    tables, manifest = processing_evidence_tables(snapshot_id='snap-a', revision='rev', envelope=envelope,
                                                  objects=[], refusals=store.read_records(path))
    assert tables['publication_refusals'] and tables['processing_attempts'] and tables['processing_recovery']
    assert account not in json.dumps([tables, manifest], default=str)


def test_export_schema_is_v15_without_actor_columns():
    # Metis 2026-10-16: removing actor/actor_id is a schema change; closes OPENVRAAG-EXP-1.
    from src.vorming.processing_evidence_export_v1 import PROJECTOR_VERSION, SCHEMAS, VERSION
    assert VERSION == PROJECTOR_VERSION == 'processing-evidence-export-v16'
    assert not any({'actor', 'actor_id'} & set(fields) for fields in SCHEMAS.values())


# --- concurrent / stale: backup bytes and manifest digest MOETEN come from one snapshot ---

def _member_digests_match(archive):
    import hashlib, zipfile
    with zipfile.ZipFile(archive) as zipf:
        manifest = json.loads(zipf.read('inventory_manifest.json'))
        return {m: hashlib.sha256(zipf.read(m)).hexdigest() == d for m, d in manifest['files'].items()}


def test_stale_rotated_generation_is_archived_byte_identical(tmp_path):
    import src.runtime_data_inventory_v1 as inventory
    path = _seed(tmp_path)
    rotated = path.with_name(path.name + '.1')
    rotated.write_bytes(path.read_bytes())
    archive = tmp_path / 'backup.zip'
    inventory.export_runtime_data(tmp_path, archive)
    digests = _member_digests_match(archive)
    assert any(m.endswith('.jsonl.1') for m in digests) and all(digests.values())

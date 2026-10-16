"""Refusal store (TIJDELIJK file store) is part of the evidence export and the runtime backup.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery
# release-control-evidence: releasebewijs

Rules (B18): the per-document evidence export MOET contain that document's refusal records and
NOOIT another document's; the runtime backup MOET contain the store file and restore it byte-identical.
"""
import csv
import io
from zipfile import ZipFile

import src.publication_refusal_store_v1 as store
from src.processing_evidence_export_v1 import processing_evidence_tables
from src.runtime_data_inventory_v1 import (
    INVENTORY_CATEGORIES, export_runtime_data, inventory_runtime_data, restore_runtime_data,
)

RUNTIME = 'output/runtime/operations-console'


def _seed(root):
    path = root / RUNTIME / store.FILE_NAME
    for sid, actor in (('snap-a', 'acc-1'), ('snap-b', 'acc-2')):
        store.append_refusal(path, snapshot_id=sid, object_version='1', actor=actor, reason_codes=['r'], revision='rev')
    return path


def test_evidence_export_contains_only_this_documents_refusals(tmp_path):
    path = _seed(tmp_path)
    tables, manifest = processing_evidence_tables(
        snapshot_id='snap-a', revision='rev', envelope={}, objects=[], refusals=store.read_records(path))
    rows = tables['publication_refusals']
    assert [r['refusal_snapshot_id'] for r in rows] == ['snap-a']
    assert rows[0]['actor'] == 'acc-1' and rows[0]['store_status'] == store.STORE_STATUS
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

def test_corrupt_refusal_records_are_reported_in_the_export_manifest(tmp_path, monkeypatch, caplog):
    import logging
    from src import operations_console_app as app_module
    path = _seed(tmp_path)
    with path.open('a', encoding='utf-8') as handle:
        handle.write('{not json\n')
    monkeypatch.setattr(store, 'postgres_store', lambda state: None)
    monkeypatch.setattr(store, 'store_path', lambda state: path)
    issues = []
    with caplog.at_level(logging.WARNING):
        records = app_module._refusal_records(object(), 'snap-a', issues=issues)
    assert len(records) == 2 and issues == ['corrupt_record:JSONDecodeError']
    assert 'publication_refusal_export_issue' in caplog.text
    tables, manifest = processing_evidence_tables(snapshot_id='snap-a', revision='rev', envelope={}, objects=[],
                                                  refusals=records, refusal_issues=issues)
    [entry] = [m for m in manifest if m['dataset'] == 'publication_refusals.csv']
    assert entry['availability'] == 'recorded_with_skipped_records' and '1 corrupt' in entry['limitation']


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
    assert 'workflow.publication_refusals' in text and 'single-worker file topology' in text
    assert 'fixed 10-minute window' in text

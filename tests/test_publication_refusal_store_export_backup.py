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

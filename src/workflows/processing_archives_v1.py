"""Exact diagnostic provenance owned by FormationTaskStore, never activation proof.

No automatic callers: preparation/migration commands must explicitly retain an
individual historical record. Reads never prepare, rebuild or activate work.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

from src.vorming.source_preparation_context_v1 import SourceIdentity
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_transaction_active


KINDS = frozenset({'semantic_replay', 'quality_processing_run','tree_formation'})
TREE_FIELDS=frozenset({'decision_graph_evidence','decision_tree_formation','decision_tree_construction'})
HEADER = 'archive_id,layout,snapshot_id,kind,record_key,binding,revision_hash,payload_hash'


def fail(code):
    raise WorkflowDocumentStoreError('processing_archive_' + code)


def encoded(value):
    # Text retains JSON numeric types/spelling across PostgreSQL roundtrips.
    # JSONB normalization would otherwise invalidate existing hashes (e.g. 1e20).
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise WorkflowDocumentStoreError('processing_archive_json_invalid') from error


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def decoded_payload(text):
    try:
        payload = json.loads(text)
        if not isinstance(payload, dict) or encoded(payload) != text:
            fail('json_invalid')
        return payload
    except (TypeError, ValueError) as error:
        raise WorkflowDocumentStoreError('processing_archive_json_invalid') from error


def source_binding(envelope):
    result = asdict(SourceIdentity.from_envelope(envelope))
    for key in ('logical_document_id', 'working_revision_id'):
        result[key] = envelope.get(key)
    if any(not isinstance(v, str) or not v or len(v) > 1024 for v in result.values()):
        fail('binding_invalid')
    return result


def validate_key(kind, record_key):
    if kind not in KINDS or not isinstance(record_key, str) or not 0 < len(record_key) <= 256:
        fail('identity_invalid')


def reference(header):
    return {key: header[key] for key in ('layout', 'archive_id', 'kind', 'record_key', 'payload_hash')}


def archive_id(header):
    return digest(encoded({key: header[key] for key in
        ('layout', 'snapshot_id', 'kind', 'record_key', 'binding', 'revision_hash', 'payload_hash')}))


@dataclass(frozen=True)
class PreparedProcessingArchive:
    header_text: str
    payload_text: str
    observed_revision: str


class ProcessingArchives:
    def prepare_processing_archive(self, envelope, *, kind, record_key, observed_revision, payload):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        validate_key(kind, record_key)
        if not isinstance(observed_revision, str) or not observed_revision:
            fail('revision_invalid')
        if not isinstance(payload, dict):
            fail('json_invalid')
        text = encoded(payload)
        header = {'layout': 1, 'snapshot_id': envelope['snapshot_id'], 'kind': kind,
                  'record_key': record_key, 'binding': source_binding(envelope),
                  'revision_hash': digest(observed_revision), 'payload_hash': digest(text)}
        header['archive_id'] = archive_id(header)
        return PreparedProcessingArchive(encoded(header), text, observed_revision)

    def retain_processing_archive(self, prepared):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        # Check complete serialized input before opening the write transaction.
        header = json.loads(prepared.header_text)
        self._check_archive_header(header)
        if (digest(prepared.payload_text) != header['payload_hash']
                or not isinstance(prepared.observed_revision, str) or not prepared.observed_revision
                or digest(prepared.observed_revision) != header['revision_hash']):
            fail('integrity_failed')
        decoded_payload(prepared.payload_text)
        with self.documents._connect() as con:
            con.execute('INSERT INTO workflow.processing_archives '
                '(archive_id,layout,snapshot_id,kind,record_key,binding,revision_hash,payload_hash,payload_text,observed_revision) '
                'VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (header['archive_id'], header['layout'], header['snapshot_id'], header['kind'],
                 header['record_key'], encoded(header['binding']), header['revision_hash'], header['payload_hash'],
                 prepared.payload_text, prepared.observed_revision))
            # All bindings and the content hash are part of archive_id. No full
            # historical payload read/equality comparison on a duplicate write.
            row = con.execute('SELECT ' + HEADER + ' FROM workflow.processing_archives '
                'WHERE snapshot_id=%s AND kind=%s AND record_key=%s',
                (header['snapshot_id'], header['kind'], header['record_key'])).fetchone()
            if row is None or encoded(row) != prepared.header_text:
                fail('conflict')
        return reference(row)

    @staticmethod
    def _check_archive_header(header, *, envelope=None):
        if type(header.get('layout')) is not int or header['layout'] != 1:
            fail('layout_unsupported')
        validate_key(header.get('kind'), header.get('record_key'))
        binding = header.get('binding')
        required = set(SourceIdentity.__dataclass_fields__) | {'logical_document_id', 'working_revision_id'}
        if (not isinstance(binding, dict) or set(binding) != required
                or any(not isinstance(v, str) or not 0 < len(v) <= 1024 for v in binding.values())
                or binding['snapshot_id'] != header.get('snapshot_id')):
            fail('binding_invalid')
        if envelope is not None and binding != source_binding(envelope):
            fail('source_mismatch')
        if header.get('archive_id') != archive_id(header):
            fail('integrity_failed')

    def processing_archive_header(self, envelope, *, kind, record_key):
        validate_key(kind, record_key)
        with self.documents._connect() as con:
            row = con.execute('SELECT ' + HEADER + ' FROM workflow.processing_archives '
                'WHERE snapshot_id=%s AND kind=%s AND record_key=%s',
                (envelope['snapshot_id'], kind, record_key)).fetchone()
        if row is None:
            return None  # Legacy absence is not a corrupt/missing explicit pin.
        self._check_archive_header(row, envelope=envelope)
        return reference(row)

    def read_processing_archive(self, ref, *, envelope):
        if not isinstance(ref, dict) or type(ref.get('layout')) is not int or ref['layout'] != 1:
            fail('layout_unsupported')
        if set(ref) != {'layout', 'archive_id', 'kind', 'record_key', 'payload_hash'}:
            fail('reference_invalid')
        with self.documents._connect() as con:
            row = con.execute('SELECT ' + HEADER + ',payload_text,observed_revision FROM workflow.processing_archives '
                'WHERE archive_id=%s', (ref['archive_id'],)).fetchone()
        if row is None:
            fail('missing')
        text = row.pop('payload_text')
        revision = row.pop('observed_revision')
        self._check_archive_header(row, envelope=envelope)
        if (encoded(reference(row)) != encoded(ref) or digest(text) != row['payload_hash']
                or digest(revision) != row['revision_hash']):
            fail('integrity_failed')
        return decoded_payload(text)

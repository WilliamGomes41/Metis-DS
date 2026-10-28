"""A passage's temporary read inputs; PostgreSQL and review commands still own truth."""
from dataclasses import dataclass
import base64
import json

from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
from src.workflows.workflow_transaction_v1 import workflow_read_transaction
from src.request_diagnostics_v1 import diagnostic_phase

PREFIX = 'review-generation-v1:'


@dataclass(frozen=True)
class ReviewDocumentInputs:
    envelope: dict
    objects: list
    bindings: list
    revision: str
    fragments: object


@dataclass(frozen=True)
class ReviewPassageInputs(ReviewDocumentInputs):
    source_available: bool
    choice_page: int = 0
    choice_total: int = 0
    choice_query: str = ''


@diagnostic_phase('review_capture')
def read_review_document(console, account, snapshot_id):
    """Capture exact document inputs, excluding unused processing archives.

    Queue membership needs all current objects. Capture history only once so
    existing document/batch forms keep their ordinary objectset revision.
    Source work and hashing happen after the bounded SQL transaction closes.
    """
    from src.review.revision_workflow import current_revisions
    store = console.workflow_document_store
    try:
        with workflow_read_transaction(store):
            envelope, _generation = store.review_document_input(snapshot_id)
            if ('reviewer' not in account.get('roles', [])
                    or account['account_id'] not in envelope.get('named_reviewers', [])):
                raise ConsoleError('reviewer_not_named_on_snapshot')
            if envelope['_review_check_formation']:
                # Uncertain/open formation needs its complete captured evidence,
                # not another envelope generation fetched during rendering.
                envelope = store.get_envelope(snapshot_id)
                if envelope is None:
                    raise WorkflowDocumentStoreError('unknown_snapshot')
                envelope['_review_check_formation'] = True
            rows = store.list_document_objects(snapshot_id)
            bindings = console.workflow_review_store.read_bindings([snapshot_id]).get(snapshot_id, [])
    except WorkflowDocumentStoreError as exc:
        if str(exc) == 'unknown_snapshot':
            raise ConsoleError('unknown_snapshot') from exc
        raise ConsoleError('workflow_document_unavailable') from exc
    except WorkflowReviewStoreError as exc:
        raise ConsoleError('workflow_review_unavailable') from exc
    objects = current_revisions(rows, snapshot_id=snapshot_id)
    with diagnostic_phase('review_revision'):
        revision = store.revision_for_rows(rows)
    reads = console._document_reads()
    if reads is not None:
        reads.envelopes[snapshot_id] = envelope
        reads.objects[snapshot_id] = (rows, revision)
        reads.current_objects[snapshot_id] = objects
        reads.bindings[snapshot_id] = bindings
    from src.publish_authorization_v1 import still_matches
    by_id = {obj['object_id']: obj for obj in objects}
    bindings = [{**row, 'valid': bool(by_id.get(row.get('object_id')))
                 and still_matches(row, by_id[row['object_id']])} for row in bindings]
    fragments = console.review_source_fragments(snapshot_id, envelope=envelope)
    if fragments is not None:
        from src.vorming.prepared_source_views_v1 import prepare
        fragments = prepare(fragments).fragments
    return ReviewDocumentInputs(envelope, objects, bindings, revision, fragments)


def _revision(snapshot_id, generation):
    return PREFIX + base64.urlsafe_b64encode(json.dumps([snapshot_id, generation]).encode()).decode()


def resolve_review_revision(console, snapshot_id, revision):
    """Translate a checked read generation to the kernel's unchanged CAS input.

    Existing writers advance the document revision; task-storage object writes
    also advance object_generation through the existing PG trigger.
    Capture generation and rows in one snapshot. Later writes are still rejected
    by the command's own objectset-token check, under its existing write lock.
    """
    if not revision.startswith(PREFIX):
        return revision
    try:
        if len(revision) > 512:
            raise ValueError()
        payload = json.loads(base64.b64decode(revision[len(PREFIX):], altchars=b'-_', validate=True))
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValueError()
        identity, generation = payload
        if identity != snapshot_id or not isinstance(generation, str):
            raise ValueError()
        # Scan each counter once; form input must not enter a backtracking regex.
        document_revision, _, object_generation = generation.partition(':')
        if not document_revision.isdecimal() or not object_generation.isdecimal():
            raise ValueError()
        store = console.workflow_document_store
        with workflow_read_transaction(store):
            _envelope, current = store.review_document_input(snapshot_id)
            if current != generation:
                raise ValueError()
            rows = store.list_document_objects(snapshot_id)
        return store.revision_for_rows(rows)
    except (ValueError, TypeError, WorkflowDocumentStoreError) as exc:
        raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT) from exc


def _outgoing_ids(obj):
    ids = set()
    for key in ('proposed_knowledge_relations', 'confirmed_knowledge_relations', 'relations', 'confirmed_relations'):
        for edge in obj.get(key) or []:
            if isinstance(edge, dict) and edge.get('target_object_id'):
                ids.add(str(edge['target_object_id']))
    for edge in (obj.get('metadata') or {}).get('confirmed_source_context') or []:
        if isinstance(edge, dict) and edge.get('source_object_id'):
            ids.add(str(edge['source_object_id']))
    return ids


def read_review_passage(console, account, snapshot_id, object_id, *, context_target='',
                        choice_page=0, choice_query=''):
    """Capture the required connected context; never infer review permission."""
    store = console.workflow_document_store
    try:
        with workflow_read_transaction(store):
            envelope, generation = store.review_document_input(snapshot_id)
            if ('reviewer' not in account.get('roles', [])
                    or account['account_id'] not in envelope.get('named_reviewers', [])):
                raise ConsoleError('reviewer_not_named_on_snapshot')
            pending = {object_id, *([context_target] if context_target else [])}
            pending.update(store.review_heading_ids(snapshot_id))
            choice_page = max(choice_page, 1)
            choices, choice_total = store.review_choice_ids(snapshot_id, object_id,
                query=choice_query, page=choice_page)
            pending.update(choices)
            seen, objects = set(), []
            while pending:
                seen.update(pending)
                loaded = store.review_object_histories(snapshot_id, sorted(pending))
                objects.extend(loaded)
                blocks = [span['block_id'] for obj in loaded
                          if (obj.get('metadata') or {}).get('source_accountability')
                          for span in ((obj.get('metadata') or {}).get('semantic_passage') or {}).get('spans', [])
                          if isinstance(span, dict) and 'block_id' in span]
                outgoing = set().union(*(_outgoing_ids(obj) for obj in loaded)) if loaded else set()
                pending = (outgoing | set(store.review_neighbor_ids(snapshot_id, sorted(pending), blocks))) - seen
            if not any(obj['object_id'] == object_id for obj in objects):
                raise ConsoleError('unknown_object')
            bindings = console.workflow_review_store.read_bindings([snapshot_id], object_ids=sorted(seen)).get(snapshot_id, [])
    except WorkflowDocumentStoreError as exc:
        if str(exc) == 'unknown_snapshot':
            raise ConsoleError('unknown_snapshot') from exc
        raise ConsoleError('workflow_document_unavailable') from exc
    except WorkflowReviewStoreError as exc:
        raise ConsoleError('workflow_review_unavailable') from exc
    # All source I/O and rendering occur after the bounded SQL capture closes.
    reads = console._document_reads()
    if reads is not None:
        reads.envelopes[snapshot_id] = envelope
    from src.publish_authorization_v1 import still_matches
    by_id = {obj['object_id']: obj for obj in objects}
    bindings = [{**row, 'valid': bool(by_id.get(row.get('object_id')))
                 and still_matches(row, by_id[row['object_id']])} for row in bindings]
    fragments = console.review_source_fragments(snapshot_id, envelope=envelope)
    if fragments is not None:
        from src.vorming.source_reconstruction_v1 import review_source_window
        from src.vorming.prepared_source_views_v1 import prepare
        fragments = prepare(review_source_window(fragments, objects)).fragments
    try:
        from src.review.open_original_v1 import open_source_passage, OpenOriginalError
        _, frozen = console._verified_source_bytes(envelope)
        open_source_passage(freeze_bytes=frozen, content_kind=envelope['content_kind'], locator=None,
                            object_record=by_id[object_id])
        available = True
    except (ConsoleError, OpenOriginalError):
        available = False
    return ReviewPassageInputs(envelope, objects, bindings, _revision(snapshot_id, generation), fragments,
                              available, choice_page, choice_total, choice_query)

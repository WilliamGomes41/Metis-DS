"""Bounded native execution of the existing Review kernel and its MRO.

The public domain operation remains review_object. This adapter supplies its
explicit inputs and commits the staged changes through the existing authorities.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
import json

from src.console_read_snapshot_v1 import detached_document_reads
from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.request_diagnostics_v1 import diagnostic_phase
from src.review.review_command_state_v1 import (
    ReviewCommandInputs, review_command_scope, GenerationPrecondition,
    ObjectSetPrecondition, UnconditionalReview,
)
from src.review.review_ledger import buffer_events
from src.review.revision_workflow import current_revisions
from src.workflows.store_command_v1 import open_store_command, close_store_command
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
from src.workflows.workflow_transaction_v1 import workflow_transaction


@dataclass(frozen=True)
class ReviewCommandResult:
    snapshot_id: str
    object_id: str


def generation_precondition(snapshot_id, token):
    """Decode only; authoritative counter comparison belongs under the lock."""
    from src.review.review_passage_read_v1 import PREFIX
    if not token or not token.startswith(PREFIX):
        return None
    try:
        if len(token) > 512:
            raise ValueError()
        payload = json.loads(base64.b64decode(token[len(PREFIX):], altchars=b'-_', validate=True))
        if not isinstance(payload, list) or len(payload) != 2 or payload[0] != snapshot_id:
            raise ValueError()
        value = payload[1]
        if not isinstance(value, str):
            raise ValueError()
        revision, separator, generation = value.partition(':')
        if not separator or not revision.isdecimal() or not generation.isdecimal():
            raise ValueError()
        return value
    except (ValueError, TypeError) as exc:
        raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT) from exc


def _source_identity(envelope):
    extraction = envelope.get('prepared_source_extraction') or {}
    return (envelope.get('sha256'), envelope.get('version'), envelope.get('content_kind'),
            envelope.get('source_snapshot_id'), extraction.get('version'),
            extraction.get('record_hash'), extraction.get('fragments_hash'))


def _outgoing(obj, *, children=False):
    out = {str(obj['parent_object_id'])} if obj.get('parent_object_id') else set()
    for key in ('proposed_knowledge_relations', 'confirmed_knowledge_relations', 'relations', 'confirmed_relations'):
        for edge in obj.get(key) or []:
            if (isinstance(edge, dict) and edge.get('target_object_id')
                    and (children or edge.get('relation_type') != 'parent')):
                out.add(str(edge['target_object_id']))
    for edge in (obj.get('metadata') or {}).get('confirmed_source_context') or []:
        if isinstance(edge, dict) and edge.get('source_object_id'):
            out.add(str(edge['source_object_id']))
    return out


def capture_histories(console, snapshot_id, object_id, command):
    """Mutation dependencies, never the GET picker or its recursive users."""
    store = console.workflow_document_store
    pending = {object_id}
    if command.get('parent_choice'):
        pending.add(str(command['parent_choice']))
    # Parent inference uses the existing global heading/TOC disambiguation rule.
    # Explicit parent confirmation uses the same TOC/body rule. This dependency
    # is all current headings and therefore grows with structural head count.
    if command.get('parent_choice') or command.get('documentpositie_action') == 'dit_klopt':
        pending.update(store.review_command_heading_ids(snapshot_id))
    pending.update(store.review_command_neighbor_ids(snapshot_id, [object_id]))
    seen = set()
    while pending:
        seen.update(pending)
        rows = store.review_command_histories(snapshot_id, sorted(pending))
        live = current_revisions(rows, snapshot_id=snapshot_id)
        outgoing = set()
        for obj in live:
            outgoing.update(_outgoing(obj, children=obj['object_id'] == object_id))
        pending = outgoing - seen
    histories = store.review_command_histories(snapshot_id, sorted(seen))
    if not any(row['object_id'] == object_id for row in histories):
        raise ConsoleError('unknown_object')
    return histories


def execute_review_command(console, submitted, invoke):
    """Enclose the entire existing MRO in one request-owned native command."""
    command = dict(submitted)
    compact = command.pop('_compact_result', False)
    interaction_id = str(command.pop('_interaction_id', '') or '')
    if not interaction_id:
        interaction_id = str((command.get('interaction_evidence') or {}).get('interaction_id') or '')
    sid, oid = str(command.get('snapshot_id') or ''), str(command.get('object_id') or '')
    expected = command.get('expected_revision')
    generation = generation_precondition(sid, expected)
    precondition = (GenerationPrecondition(sid, generation) if generation is not None else
        ObjectSetPrecondition(expected) if expected is not None else UnconditionalReview())
    documents, reviews = console.workflow_document_store, console.workflow_review_store
    changes = None
    with detached_document_reads():
        console._require_role(command['actor_id'], 'reviewer')
        envelope = console._envelope(sid)
        if command['actor_id'] not in envelope.get('named_reviewers', []):
            raise ConsoleError('reviewer_not_named_on_snapshot')
        console._require_mutable_working_revision(sid)
        source_path = frozen = fragments = None
        source_failure = None
        with diagnostic_phase('review_source_prepare'):
            try:
                source_path, frozen = console._verified_source_bytes(envelope)
                fragments = console._read_source_fragments(envelope, source_path)
                from src.vorming.prepared_source_views_v1 import prepare
                fragments = prepare(fragments).fragments
            except ConsoleError as exc:
                # Existing safe disposition/defer paths need no source. Keep
                # their contract; the original kernel raises this pinned error
                # if its chosen branch actually requires source validation.
                source_failure = exc.code
                fragments = None
        identity = _source_identity(envelope)
        try:
            with console._store_write_lock():
                owner, token = open_store_command(console)
                owner.fresh = True
                try:
                    with diagnostic_phase('store_transaction'), workflow_transaction(reviews) as con:
                        reviews._lock_authorizations(con)
                        console._lock_document_row(con, sid)
                        console._require_role(command['actor_id'], 'reviewer', current=True)
                        current, counters = documents.review_document_input(sid, command=True)
                        if _source_identity(current) != identity:
                            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                        if generation is not None:
                            if generation != counters:
                                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                        elif expected is not None:
                            # Explicit old-token compatibility; the compact POST
                            # never enters this whole-objectset equality adapter.
                            actual = documents.objects_revision(sid)
                            if actual != expected:
                                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=actual)
                        histories = capture_histories(console, sid, oid, command)
                        object_ids = sorted({row['object_id'] for row in histories})
                        bindings = reviews.read_bindings([sid], object_ids=object_ids).get(sid, [])
                        inputs = ReviewCommandInputs(console, sid, current, histories, bindings,
                            fragments, frozen, source_path, oid, interaction_id, precondition, source_failure)
                        with review_command_scope(inputs) as changes, buffer_events(console._ledger_path):
                            # The original precondition has just been checked in
                            # its own contract. Nested existing validators use
                            # the captured workspace's internal revision.
                            command['expected_revision'] = changes.revision if expected is not None else None
                            if (interaction_id and command.get('decision') != 'later'
                                    and command.get('interaction_evidence') is None):
                                from src.review.beslisboom_path_v1 import review_path_for_klasse
                                from src.review.review_duty_v1 import review_duty_for
                                from src.review.review_interaction_v1 import build_review_interaction_evidence
                                live = current_revisions(histories, snapshot_id=sid)
                                focal = next(row for row in live if row['object_id'] == oid)
                                path = review_path_for_klasse(current['class'])
                                duty = review_duty_for(focal, review_path=path, bindings=bindings, fragments=fragments)
                                command['interaction_evidence'] = build_review_interaction_evidence(
                                    interaction_id=interaction_id, interaction_kind='contextual',
                                    reviewer_account_id=command['actor_id'], snapshot_id=sid,
                                    review_stage=str((duty or {}).get('stage') or 'first_review'),
                                    focal=focal, objects=live, review_path=path)
                            try:
                                result = invoke(command)
                            except ConsoleError as exc:
                                # Detached baseline for the bounded error view;
                                # no failed staged mutation becomes presentation truth.
                                exc.review_command_inputs = inputs
                                try:
                                    console._require_open_original(sid, oid)
                                    exc.review_source_available = True
                                except ConsoleError:
                                    exc.review_source_available = False
                                raise
                            if changes.commit_count:
                                reviews.apply_review_binding_delta(sid, inputs.bindings, changes.bindings)
                                documents.apply_review_changes(sid, inputs.histories, changes.histories,
                                    inputs.envelope, changes.envelope, commit_count=changes.commit_count,
                                    transitions=changes.object_transitions)
                finally:
                    close_store_command(token)
        except WorkflowReviewStoreError as exc:
            raise ConsoleError('workflow_review_write_failed') from exc
        except WorkflowDocumentStoreError as exc:
            code = str(exc)
            if code not in {SNAPSHOT_OBJECT_WRITE_CONFLICT, 'published_working_revision_immutable'}:
                code = 'workflow_document_write_failed'
            if code == SNAPSHOT_OBJECT_WRITE_CONFLICT and not compact:
                raise ConsoleError(code, current_revision=documents.objects_revision(sid)) from exc
            raise ConsoleError(code) from exc
    if compact:
        return ReviewCommandResult(sid, oid)
    # Legacy list results are a deliberate read adapter after the transaction,
    # rather than a reason to materialize unrelated histories inside the write.
    if isinstance(result, list):
        with detached_document_reads():
            return console.snapshot_objects(sid)
    return result

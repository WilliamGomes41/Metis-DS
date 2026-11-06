"""Bounded native execution of the existing Review kernel and its MRO.

The public domain operation remains review_object. This adapter supplies its
explicit inputs and commits the staged changes through the existing authorities.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import dataclass
import json
from contextlib import ExitStack

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


def capture_histories(console, snapshot_id, object_id, command, *, admission_context=False):
    """Mutation dependencies, never the GET picker or its recursive users."""
    store = console.workflow_document_store
    pending = {object_id}
    focals = set(command.get('_focal_ids') or [object_id])
    pending.update(command.get('_dependency_ids') or [])
    if command.get('parent_choice'):
        pending.add(str(command['parent_choice']))
    # Parent inference uses the existing global heading/TOC disambiguation rule.
    # Explicit parent confirmation uses the same TOC/body rule. This dependency
    # is all current headings and therefore grows with structural head count.
    if (command.get('_all_headings') or command.get('parent_choice')
            or command.get('_review_assessment') is not None
            or command.get('documentpositie_action') == 'dit_klopt'):
        pending.update(store.review_command_heading_ids(snapshot_id))
    pending.update(store.review_command_neighbor_ids(snapshot_id, sorted(focals)))
    if admission_context:
        pending.update(store.review_command_neighbor_ids(snapshot_id, sorted(pending)))
        # Source group eligibility also consumes automatic context-by-span,
        # which has no object-ID edge and need not be an adjacent paragraph.
        # Use the existing generated block index; the original partition owner
        # still decides exact interval coverage and candidate eligibility.
        from src.vorming.source_accountability_v1 import evidence_of
        sources = store.review_command_current_heads(snapshot_id, sorted(pending))
        blocks = set()
        for obj in sources:
            spans = evidence_of(obj).get('spans')
            if isinstance(spans, list):
                blocks.update(span['block_id'] for span in spans if isinstance(span, dict)
                              and isinstance(span.get('block_id'), str))
        pending.update(store.review_neighbor_ids(snapshot_id, [], sorted(blocks)))
        neighbours = store.source_admission_neighbor_ids(snapshot_id, sorted(pending))
        if neighbours is None:
            # Explicit existing-data compatibility until complete preparation.
            histories = store.list_document_objects(snapshot_id)
            current_revisions(histories, snapshot_id=snapshot_id)
            return histories
        pending.update(neighbours)
    seen = set()
    while pending:
        seen.update(pending)
        # Candidate discovery needs current raw heads, not historical payloads.
        # The complete selected prefix is checked by its owner-issued frontier
        # below, or by the explicit unprepared legacy compatibility adapter.
        live = store.review_command_current_heads(snapshot_id, sorted(pending))
        outgoing = set()
        for obj in live:
            outgoing.update(_outgoing(obj, children=obj['object_id'] in focals))
        pending = outgoing - seen
    histories = store.review_command_window(snapshot_id, sorted(seen))
    if histories is None:
        histories = store.review_command_histories(snapshot_id, sorted(seen))
        current_revisions(histories, snapshot_id=snapshot_id)
    if not any(row['object_id'] == object_id for row in histories):
        raise ConsoleError('unknown_object')
    return histories


def _refuse_static_disposition(command):
    """Apply the kernel's static disposition rule before any input is prepared."""
    from src.review.closed_review_loop_v1 import require_allowed_review_disposition
    from src.review.review_cockpit_v1 import map_eindoordeel
    # A revise with a suitability becomes a structured repair before the kernel
    # reaches this rule; the kernel still applies it to revise itself.
    if map_eindoordeel(str(command.get('eindoordeel') or ''), str(command.get('decision') or '')) != 'revise':
        require_allowed_review_disposition(command)


def _prepare_review_source_inputs(console, envelope, original_ids):
    sid = envelope["snapshot_id"]
    documents = console.workflow_document_store
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
    original_checks = None
    if original_ids is not None:
        from src.integrity_kernel import stable_hash
        original_checks = {}
        if frozen is not None:
            original_rows = documents.review_command_current_heads(sid, original_ids)
            with console._open_original_reader(envelope, frozen) as require:
                for obj in original_rows:
                    try:
                        original_checks[stable_hash(obj)] = {'opened': require(obj)}
                    except ConsoleError as exc:
                        original_checks[stable_hash(obj)] = {'error': exc.code}
    if envelope.get('decision_graph'):
        envelope=console._tree_envelope(sid,envelope=envelope)
    return envelope, source_path, frozen, fragments, source_failure, original_checks


def _command_envelope(documents, snapshot_id):
    try:
        return documents.review_document_input(snapshot_id, command=True)[0]
    except WorkflowDocumentStoreError as exc:
        code = 'unknown_snapshot' if str(exc) == 'unknown_snapshot' else 'workflow_document_unavailable'
        raise ConsoleError(code) from exc


def _invoke_review_kernel(console, command, invoke, inputs, changes, *, compact=False):
    """Invoke the original kernel with its private workspace precondition."""
    internal = dict(command)
    assessment = internal.pop('_review_assessment', None)
    if assessment is not None:
        from src.review.review_assessment_v1 import (
            ReviewAssessment, displayed_review_descriptor, compact_approval_arguments)
        if not isinstance(assessment, ReviewAssessment):
            raise ConsoleError('review_assessment_invalid')
        if internal.get('decision') == 'approve':
            from src.review.beslisboom_path_v1 import review_path_for_klasse
            current = current_revisions(inputs.histories, snapshot_id=inputs.snapshot_id)
            focal = next(row for row in current if row['object_id'] == inputs.target_object_id)
            descriptor = displayed_review_descriptor(focal, current,
                review_path_for_klasse(inputs.envelope['class']),
                bindings=inputs.bindings, fragments=inputs.fragments)
            internal.update(compact_approval_arguments(assessment, descriptor))
    internal['expected_revision'] = changes.revision if command.get('expected_revision') is not None else None
    if (inputs.interaction_id and internal.get('decision') != 'later'
            and internal.get('interaction_evidence') is None):
        from src.review.beslisboom_path_v1 import review_path_for_klasse
        from src.review.review_duty_v1 import review_duty_for
        from src.review.review_interaction_v1 import build_review_interaction_evidence
        live = current_revisions(inputs.histories, snapshot_id=inputs.snapshot_id)
        focal = next(row for row in live if row['object_id'] == inputs.target_object_id)
        duty = review_duty_for(focal, review_path=review_path_for_klasse(inputs.envelope['class']),
                              bindings=inputs.bindings, fragments=inputs.fragments)
        internal['interaction_evidence'] = build_review_interaction_evidence(
            interaction_id=inputs.interaction_id, interaction_kind='contextual',
            reviewer_account_id=internal['actor_id'], snapshot_id=inputs.snapshot_id,
            review_stage=str((duty or {}).get('stage') or 'first_review'), focal=focal,
            objects=live, review_path=review_path_for_klasse(inputs.envelope['class']),
            assessment=assessment)
    if assessment is not None and internal.get('interaction_evidence') is not None:
        evidence = deepcopy(internal['interaction_evidence'])
        recorded = evidence.get('assessment')
        if recorded is not None and recorded != assessment.as_evidence():
            raise ConsoleError('review_assessment_conflict')
        evidence['assessment'] = assessment.as_evidence()
        internal['interaction_evidence'] = evidence
    for key in ('_dependency_ids', '_focal_ids', '_all_headings', '_original_ids', '_interaction_id'):
        internal.pop(key, None)
    try:
        return invoke(internal)
    except ConsoleError as exc:
        from src.review.deterministic_review_repair_v1 import StructuredRepairRequired
        if isinstance(exc, StructuredRepairRequired):
            exc.submission['expected_revision'] = str(command.get('expected_revision') or '')
        exc.review_command_inputs = inputs
        exc.review_source_available = False
        if compact:
            try:
                console._require_open_original(inputs.snapshot_id, inputs.target_object_id)
                exc.review_source_available = True
            except Exception:
                # Best-effort presentation must never mask the domain error.
                pass
        raise


def execute_review_command(console, submitted, invoke, *, completed_command=None,
                           list_result_is_snapshot=True, prepare=True):
    """Enclose the entire existing MRO in one request-owned native command."""
    command = dict(submitted)
    compact = command.pop('_compact_result', False)
    interaction_id = str(command.pop('_interaction_id', '') or '')
    original_ids = command.pop('_original_ids', None)
    if not interaction_id:
        interaction_id = str((command.get('interaction_evidence') or {}).get('interaction_id') or '')
    sid, oid = str(command.get('snapshot_id') or ''), str(command.get('object_id') or '')
    expected = command.get('expected_revision')
    generation = generation_precondition(sid, expected)
    precondition = (GenerationPrecondition(sid, generation) if generation is not None else
        ObjectSetPrecondition(expected) if expected is not None else UnconditionalReview())
    if prepare and compact and generation is not None and completed_command is None:
        return _execute_prepared_command(console,
            {**command, '_interaction_id': interaction_id, '_original_ids': original_ids or [oid]},
            invoke, compact=True, admission_context=False)
    documents, reviews = console.workflow_document_store, console.workflow_review_store
    try:
        reviews.require_command_transaction()
    except WorkflowReviewStoreError as exc:
        raise ConsoleError(str(exc)) from exc
    changes = None
    with detached_document_reads():
        console._require_role(command['actor_id'], 'reviewer')
        envelope = _command_envelope(documents, sid)
        if command['actor_id'] not in envelope.get('named_reviewers', []):
            raise ConsoleError('reviewer_not_named_on_snapshot')
        console._require_mutable_working_revision(sid)
        _refuse_static_disposition(command)
        (envelope, source_path, frozen, fragments, source_failure, original_checks) = (
            _prepare_review_source_inputs(console, envelope, original_ids))
        identity = _source_identity(envelope)
        try:
            with console._store_write_lock():
                owner, token = open_store_command(console)
                owner.fresh = True
                try:
                    with diagnostic_phase('store_transaction'), workflow_transaction(reviews) as con:
                        reviews._lock_authorizations(con)
                        console._lock_document_row(con, sid)
                        console._require_role(command['actor_id'], 'reviewer', current=True, key_share=True)
                        current, counters = documents.review_document_input(sid, command=True)
                        if completed_command is not None and generation is None:
                            completed = completed_command(current)
                            if completed is not None:
                                return completed
                        if _source_identity(current) != identity:
                            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                        if generation is not None:
                            if generation != counters:
                                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                            if completed_command is not None:
                                completed = completed_command(current)
                                if completed is not None:
                                    return completed
                        elif expected is not None:
                            # Explicit old-token compatibility; the compact POST
                            # never enters this whole-objectset equality adapter.
                            actual = documents.objects_revision(sid)
                            if actual != expected:
                                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=actual)
                        histories = capture_histories(console, sid, oid, command,
                            admission_context=original_ids is not None)
                        object_ids = sorted({row['object_id'] for row in histories})
                        if 'decision_graph_evidence' in envelope:
                            if (current.get('_document_inputs') or {}).get('tree')!=(envelope.get('_document_inputs') or {}).get('tree'):
                                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                            current['decision_graph_evidence']=envelope['decision_graph_evidence']
                        current['quality_processing_runs'] = documents.review_command_quality_input(sid, object_ids, envelope=current)
                        bindings = reviews.read_bindings([sid], object_ids=object_ids).get(sid, [])
                        inputs = ReviewCommandInputs(console, sid, current, histories, bindings,
                            fragments, frozen, source_path, oid, interaction_id, precondition, source_failure,
                            original_checks)
                        with review_command_scope(inputs) as changes, buffer_events(console._ledger_path):
                            # The original precondition has just been checked in
                            # its own contract. Nested existing validators use
                            # the captured workspace's internal revision.
                            result = _invoke_review_kernel(console, command, invoke, inputs, changes, compact=compact)
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
    if list_result_is_snapshot and isinstance(result, list):
        with detached_document_reads():
            return console.snapshot_objects(sid)
    return result


def execute_review_batch(console, submitted, invoke, *, headings=False):
    """Supply one selected batch to its original member kernel, atomically."""
    command = dict(submitted)
    ids = list(dict.fromkeys(str(oid).strip() for oid in command['object_ids'] if str(oid).strip()))
    command['object_ids'] = ids
    command['interaction_evidence'] = deepcopy(command.get('interaction_evidence'))
    if not ids:
        # Original role/selection validation owns the empty-input error order.
        return invoke(command)
    if not headings:
        from src.review.proportionate_review_v1 import NORMAL_RISK_BATCH_MAX
        if len(ids) > NORMAL_RISK_BATCH_MAX:
            return invoke(command)
    captured = {'actor_id': command['actor_id'], 'snapshot_id': command['snapshot_id'],
                'object_id': ids[0], 'expected_revision': command.get('expected_revision'),
                '_dependency_ids': ids, '_focal_ids': ids, '_all_headings': headings,
                '_original_ids': ids, 'interaction_evidence': command.get('interaction_evidence')}
    # Preserve one exact original batch/structure interaction manifest for every
    # member. Do not ask the executor to synthesize a singular contextual one.
    def run(internal):
        return invoke({**command, 'expected_revision': internal['expected_revision']})
    if generation_precondition(command['snapshot_id'], command.get('expected_revision')) is not None:
        return _execute_prepared_command(console, captured, run)
    return execute_review_command(console, captured, run, list_result_is_snapshot=False)


def _batch_state(console, command, prepared_envelope, generation, *, admission_context=True):
    """Actual current dependencies; called in each owner's consistent SQL phase."""
    sid, oid = command['snapshot_id'], command['object_id']
    store, reviews = console.workflow_document_store, console.workflow_review_store
    current, counters = store.review_document_input(sid, command=True)
    if counters != generation or _source_identity(current) != _source_identity(prepared_envelope):
        raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
    if command['actor_id'] not in current.get('named_reviewers', []):
        raise ConsoleError('reviewer_not_named_on_snapshot')
    if 'decision_graph_evidence' in prepared_envelope:
        if (current.get('_document_inputs') or {}).get('tree') != (prepared_envelope.get('_document_inputs') or {}).get('tree'):
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
        current['decision_graph_evidence'] = prepared_envelope['decision_graph_evidence']
    histories = capture_histories(console, sid, oid, command, admission_context=admission_context)
    ids = sorted({row['object_id'] for row in histories})
    current['quality_processing_runs'] = store.review_command_quality_input(sid, ids, envelope=current)
    bindings = reviews.read_bindings([sid], object_ids=ids).get(sid, [])
    interaction_id = str(command.get('_interaction_id') or (command.get('interaction_evidence') or {}).get('interaction_id') or '')
    events = reviews.read_review_command_events(sid, ids, interaction_id=interaction_id, include_pending=False)
    return current, histories, bindings, events


def _execute_prepared_command(console, command, invoke, *, compact=False, admission_context=True):
    """Original GEN kernel without SQL; short current-guarded native commit.

    Public m2/None and receipt commands retain their serial implementation.
    The pending buffer exits successfully ONLY inside the write transaction.
    Any earlier exception discards it through normal exceptional unwinding.
    """
    from src.review.revision_window_v1 import RevisionWindow
    from src.review.review_interaction_v1 import validate_review_interaction_identity
    from src.workflows.workflow_transaction_v1 import workflow_read_transaction, without_workflow_io, workflow_transaction_active
    from src.workflows.workflow_documents_postgres_v1 import _json_text
    sid, oid = command['snapshot_id'], command['object_id']
    generation = generation_precondition(sid, command.get('expected_revision'))
    store, reviews = console.workflow_document_store, console.workflow_review_store
    def serial():
        return execute_review_command(console, {**command, '_compact_result': compact}, invoke,
                                      list_result_is_snapshot=False, prepare=False)
    if reviews._buffer.get() is not None or workflow_transaction_active():
        return serial()
    with detached_document_reads():
        console._require_role(command['actor_id'], 'reviewer')
        envelope = _command_envelope(store, sid)
        if command['actor_id'] not in envelope.get('named_reviewers', []):
            raise ConsoleError('reviewer_not_named_on_snapshot')
        console._require_mutable_working_revision(sid, current=True)
        _refuse_static_disposition(command)
        envelope, path, frozen, fragments, source_error, originals = _prepare_review_source_inputs(
            console, envelope, command.get('_original_ids'))
        try:
            with workflow_read_transaction(reviews):
                current, histories, bindings, events = _batch_state(console, command, envelope, generation,
                    admission_context=admission_context)
                account = console._require_role(command['actor_id'], 'reviewer')
                ledger_head = reviews._last_hash()
            if not isinstance(histories, RevisionWindow):
                # Explicit existing-data compatibility until its own preparation.
                return serial()
            interaction_id = str(command.get('_interaction_id') or (command.get('interaction_evidence') or {}).get('interaction_id') or '')
            inputs = ReviewCommandInputs(console, sid, current, histories, bindings, fragments,
                frozen, path, oid, interaction_id, GenerationPrecondition(sid, generation),
                source_error, originals, console._public_account(account), events, ledger_head, True)
            with ExitStack() as pending:
                intent_buffer = pending.enter_context(reviews.prepared_batch_events(ledger_head))
                with review_command_scope(inputs, preparing=True) as changes, without_workflow_io():
                    result = _invoke_review_kernel(console, command, invoke, inputs, changes, compact=compact)
                    plan = (store.prepare_review_changes(sid, inputs.histories, changes.histories,
                        inputs.envelope, changes.envelope, changes.commit_count,
                        transitions=changes.object_transitions) if changes.commit_count else None)
                    intent_buffer.seal()
                with console._store_write_lock():
                    owner, token = open_store_command(console)
                    owner.fresh = True
                    try:
                        with diagnostic_phase('store_transaction'), workflow_transaction(reviews) as con:
                            reviews._lock_authorizations(con)
                            console._lock_document_row(con, sid)
                            live_actor = console._require_role(command['actor_id'], 'reviewer', current=True, key_share=True)
                            console._require_mutable_working_revision(sid, current=True)
                            # Ledger identity and append head stay serialized with
                            # all ordinary appends; the ledger owner assigns the
                            # final audit order after the current-input guards.
                            reviews._lock_review_ledger(con)
                            live = _batch_state(console, command, envelope, generation,
                                admission_context=admission_context)
                            before = (inputs.envelope, inputs.histories, inputs.bindings, inputs.events)
                            if (not isinstance(live[1], RevisionWindow)
                                    or any(_json_text(a) != _json_text(b) for a, b in zip(live, before))
                                    or live[1].frontiers != inputs.histories.frontiers
                                    or _json_text(console._public_account(live_actor)) != _json_text(inputs.account)):
                                raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
                            if command.get('interaction_evidence') is not None:
                                try:
                                    validate_review_interaction_identity(command['interaction_evidence'], live[3])
                                except ValueError as exc:
                                    raise ConsoleError(str(exc)) from exc
                            if changes.commit_count:
                                reviews.apply_review_binding_delta(sid, inputs.bindings, changes.bindings)
                                store.apply_prepared_review_changes(sid, plan)
                            # A failed SQL COMMIT after this close still rolls
                            # the buffered inserts back on this SAME connection.
                            pending.close()
                    finally:
                        close_store_command(token)
            return ReviewCommandResult(sid, oid) if compact else result
        except WorkflowReviewStoreError as exc:
            raise ConsoleError('workflow_review_write_failed') from exc
        except WorkflowDocumentStoreError as exc:
            code = str(exc)
            if code not in {SNAPSHOT_OBJECT_WRITE_CONFLICT, 'published_working_revision_immutable'}:
                code = 'workflow_document_write_failed'
            raise ConsoleError(code) from exc

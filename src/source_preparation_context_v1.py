"""Typed kernel handoff and verified derived extraction in the workflow envelope.

Source bytes remain immutable-store truth. This record neither approves objects
nor replaces the existing attempt/revision/activation authority.
"""
from dataclasses import asdict, dataclass
from copy import deepcopy
from typing import Callable, NotRequired, TypedDict

from src.integrity_kernel import stable_hash

KEY = 'prepared_source_extraction'
VERSION = 'prepared-source-extraction-v1'


def _error(code):
    from src.operations_console_v1 import ConsoleError
    return ConsoleError(code)


@dataclass(frozen=True)
class SourceIdentity:
    snapshot_id: str
    source_id: str
    document_id: str
    sha256: str
    version: str
    content_kind: str

    @classmethod
    def from_envelope(cls, envelope):
        try:
            values = {key: envelope[key] for key in cls.__dataclass_fields__}
        except KeyError as exc:
            raise _error('source_preparation_context_required') from exc
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise _error('source_preparation_context_required')
        return cls(**values)


class FormationContext(TypedDict):
    snapshot_id: str
    source_sha256: str
    semantic_replay: dict | None
    resume_formation: bool
    explicit_decision_graph: bool
    model_call_limits: dict | None
    attempt_deadline: float | None
    diagnostic_checkpoint: Callable | None
    processing_reference: str | None
    retained_fragments: NotRequired[list]
    extraction_checkpoint: NotRequired[Callable[[list], None]]


def extractor_contract(kind):
    """Current raw extraction identity, independent of semantic/model policy."""
    if kind == 'html':
        from src.extract_html_v1 import PARSER_VERSION
        return PARSER_VERSION
    from src.docling_pdf_v1 import enabled
    if enabled():
        from src.docling_contract_v1 import CONTRACT, DOCLING_VERSION, CORE_VERSION, MODEL_REVISIONS, LAYOUT_PRESET
        return stable_hash({'contract': CONTRACT, 'docling': DOCLING_VERSION,
            'core': CORE_VERSION, 'models': MODEL_REVISIONS, 'layout': LAYOUT_PRESET})
    from src.extract_pdf_v2 import PARSER_VERSION
    return PARSER_VERSION


def extraction_record(envelope, fragments, contract):
    rows = deepcopy(list(fragments))
    record = {'version': VERSION, 'source': asdict(SourceIdentity.from_envelope(envelope)),
              'extractor_contract': contract, 'fragments': rows, 'fragments_hash': stable_hash(rows)}
    docling = getattr(fragments, 'extraction_record', None)
    if docling is not None:
        record['docling_record'] = deepcopy(docling)
    record['record_hash'] = stable_hash(record)
    return record


def stored_extraction(envelope, *, required_contract=None):
    """Corruption is an error; legacy absence and changed extractor are distinct."""
    if KEY not in envelope:
        return None
    record = envelope[KEY]
    if (not isinstance(record, dict) or record.get('version') != VERSION
            or record.get('record_hash') != stable_hash({k: v for k, v in record.items() if k != 'record_hash'})
            or not isinstance(record.get('fragments'), list)
            or any(not isinstance(row, dict) for row in record['fragments'])
            or record.get('fragments_hash') != stable_hash(record['fragments'])
            or not isinstance(record.get('extractor_contract'), str) or not record['extractor_contract']):
        raise _error('source_extraction_integrity_failed')
    if record.get('source') != asdict(SourceIdentity.from_envelope(envelope)):
        raise _error('source_extraction_identity_mismatch')
    if required_contract is not None and record['extractor_contract'] != required_contract:
        raise _error('source_extraction_contract_mismatch')
    rows = deepcopy(record['fragments'])
    if 'docling_record' in record:
        from src.docling_contract_v1 import ExtractedFragments
        return ExtractedFragments(rows, deepcopy(record['docling_record']))
    return rows


def build_formation_context(console, *, envelope, actor_id, expected_revision,
                            attempt=None, deadline=None, expected_envelope=None) -> FormationContext:
    """One handoff for initial processing, retry and resume; no optional identity."""
    source = SourceIdentity.from_envelope(envelope)
    if attempt is not None:
        # Legacy synchronous ingest reserves an absent object's revision before
        # registration, then fences the actual empty-set revision for activation.
        # Only that caller supplies its separate registration baseline.
        initial_registration = (expected_envelope is not None
                                and attempt.get('kind') == 'ingest'
                                and attempt['expected_revision'] == '')
        if (attempt['actor_id'] != actor_id or attempt['source_hash'] != source.sha256
                or attempt.get('source_version', source.version) != source.version
                or (attempt['expected_revision'] != expected_revision and not initial_registration)
                or deadline is None):
            raise _error('processing_command_conflict')
    resume = bool(attempt and attempt.get('kind') == 'resume')
    if resume and not envelope.get('semantic_replay'):
        raise _error('source_preparation_checkpoint_required')
    context: FormationContext = {
        'snapshot_id': source.snapshot_id, 'source_sha256': source.sha256,
        'semantic_replay': deepcopy(envelope.get('semantic_replay')),
        'resume_formation': resume,
        'explicit_decision_graph': 'decision_graph' in envelope or bool(envelope.get('review_policy') and envelope['class'] == 'beslisboom'),
        'model_call_limits': {key: attempt['limits'][key] for key in ('connect', 'idle', 'total', 'attempt', 'max_attempts')}
                            if attempt and attempt.get('limits') else None,
        'attempt_deadline': deadline,
        'diagnostic_checkpoint': console._diagnostic_writer(source.snapshot_id, attempt['attempt_id'] if attempt else None),
        'processing_reference': attempt.get('processing_reference') if attempt else None,
    }
    # Dedicated decision-tree construction retains its existing extraction path.
    if source.content_kind not in {'html', 'pdf'} or envelope['class'] == 'beslisboom':
        return context
    contract = extractor_contract(source.content_kind)
    fresh_extraction = not attempt or attempt.get('kind') == 'reextract'
    if not fresh_extraction:
        retained = stored_extraction(envelope, required_contract=contract)
        if retained is None and source.content_kind == 'pdf':
            from src.docling_contract_v1 import stored_fragments
            retained = stored_fragments(envelope)
        if retained is not None:
            context['retained_fragments'] = retained

    def retain(fragments):
        record = extraction_record(envelope, fragments, contract)
        if envelope.get(KEY) == record:
            return
        if attempt is not None or expected_revision is not None:
            from src.processing_retry_v1 import assert_active, now
            from src.source_selection_v1 import authorize, configuration
            import time
            with console._reprocessing_transaction(source.snapshot_id):
                console._assert_source_work_unchanged(expected_envelope or envelope, expected_revision,
                                                      'published_objects_must_not_be_rewritten')
                current = deepcopy(console._envelope(source.snapshot_id))
                active = assert_active(current, attempt['attempt_id'], now()) if attempt else None
                authorize(console, actor_id, current)
                if active is not None and (active['actor_id'] != actor_id or active['source_hash'] != source.sha256
                        or active['expected_revision'] != attempt['expected_revision']
                        or (active.get('processing_configuration') and active['processing_configuration'] != configuration(console))):
                    raise _error('processing_command_conflict')
                if deadline is not None and time.monotonic() >= deadline:
                    raise _error('processing_attempt_expired')
                current[KEY] = record
                console._commit_prepared_store(envelopes={source.snapshot_id: current}, snapshot_id=source.snapshot_id)
        # Update only the producing prepared value after a successful checkpoint.
        # Activation compares this value with the same existing durable envelope.
        envelope[KEY] = deepcopy(record)
        if expected_envelope is not None:
            expected_envelope[KEY] = deepcopy(record)
    context['extraction_checkpoint'] = retain
    return context

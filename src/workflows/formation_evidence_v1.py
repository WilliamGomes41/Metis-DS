"""Complete immutable producer evidence under FormationTaskStore ownership.

Preparation consumes the owner's fenced finalized capture, never request JSON.
This is historical producer evidence, not current review/publication closure.
"""
from dataclasses import dataclass
import json

from src.vorming.semantic_replay_v1 import stable_json_hash, exact_replay_lookup, LOOKUP_HIT
from src.workflows.processing_archives_v1 import source_binding, encoded
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text
from src.workflows.workflow_transaction_v1 import workflow_transaction_active


def fail(reason):
    raise WorkflowDocumentStoreError('formation_evidence_' + reason)


def available(con):
    return con.execute("SELECT to_regclass('workflow.formation_evidence_roots') AS name").fetchone()['name'] is not None


def assert_source_reference(con, snapshot_id, reference):
    """An independent preparation cannot replace an active producer's source."""
    if not available(con):
        return
    active = con.execute('SELECT r.header FROM workflow.documents d JOIN workflow.formation_evidence_roots r '
                         'ON r.proof_id=d.formation_evidence_id WHERE d.snapshot_id=%s', (snapshot_id,)).fetchone()
    if active and active['header']['capture']['source_ref'] != reference:
        fail('source_activation_required')


@dataclass(frozen=True)
class PreparedFormationEvidence:
    header_text: str
    members: tuple


def _gate(receipt):
    return {k: v for k, v in receipt.items() if k not in {'formation_evidence_ref', 'stage'}}


def call_sequence(evidence):
    # These are document-level bounded-formation projections, not provider-call
    # fields. Preserve every other field, plus call multiplicity and order.
    aggregate = {'task_policy','tasks','task_plan','task_plan_summary','recommendation_coverage',
                 'pending_rejections','formation_incomplete','formation_state','formation_progress','supplementary_calls'}
    first = {k:v for k,v in evidence.items() if k not in aggregate}
    return ([first] if first else []) + list(evidence.get('supplementary_calls') or [])


def activation_replay(replay):
    """Existing task-store projection; progress is derived, original stays archived."""
    result = dict(replay)
    if isinstance(result.get('provider_evidence'), dict):
        result['provider_evidence'] = {k:v for k,v in result['provider_evidence'].items() if k != 'formation_progress'}
    return result


def human_reference(envelope):
    from src.workflows.operational_document_inputs_v1 import PreparedOperationalWrite
    prepared = envelope.get('_prepared_document_write')
    pins = json.loads(prepared.next_refs_text) if isinstance(prepared, PreparedOperationalWrite) else envelope.get('_document_inputs')
    reference = (pins or {}).get('human') if pins is not None else envelope.get('human_formation_ref')
    if reference is not None and (not isinstance(reference, dict) or set(reference) != {'layout', 'proof_id'}
            or type(reference['layout']) is not int or reference['layout'] != 2):
        fail('human_reference_invalid')
    return reference


def human_capture(con, snapshot_id, attempt_id):
    row = con.execute('SELECT payload FROM workflow.processing_attempts WHERE snapshot_id=%s AND attempt_id=%s',
                      (snapshot_id, attempt_id)).fetchone()
    if not row or row['payload'].get('kind') != 'human_annotation_build':
        fail('human_attempt_required')
    attempt = row['payload']
    seal = con.execute('SELECT payload FROM workflow.annotation_seals WHERE snapshot_id=%s AND seal_id=%s',
                       (snapshot_id, attempt.get('annotation_seal_id'))).fetchone()
    if seal is None or stable_json_hash(seal['payload']) != attempt['annotation_seal_id']:
        fail('human_seal_missing')
    payload = seal['payload']
    entries = []
    for ref in payload['entries']:
        entry = con.execute('SELECT annotation_id,revision,payload_hash,author_id,payload FROM workflow.annotation_versions '
            'WHERE snapshot_id=%s AND annotation_id=%s AND revision=%s',
            (snapshot_id, ref['annotation_id'], ref['revision'])).fetchone()
        if not entry or entry['payload_hash'] != ref['payload_hash'] or stable_json_hash(entry['payload']) != ref['payload_hash']:
            fail('human_entry_changed')
        entries.append(dict(entry))
    summary = {'annotation_seal_id': attempt['annotation_seal_id'], 'attempt_id': attempt_id,
               'claim_token': (attempt.get('dispatch') or {}).get('token'), 'actor_id': attempt['actor_id'],
               'activation_revision': attempt['expected_revision'],
               'source_ref': (attempt.get('diagnostic') or {}).get('review_source_ref')}
    return summary, payload, entries, attempt


def retain_active_evidence(con, envelope, proof_id):
    """Ordinary curation retains immutable input, independent of new task work."""
    row = con.execute('SELECT header,sealed FROM workflow.formation_evidence_roots WHERE proof_id=%s', (proof_id,)).fetchone()
    if not row or not row['sealed'] or stable_json_hash(row['header']) != proof_id:
        fail('integrity_failed')
    header = row['header']
    if header['source'] != source_binding(envelope):
        fail('source_mismatch')
    source = con.execute('SELECT review_source_ref FROM workflow.documents WHERE snapshot_id=%s',
                         (envelope['snapshot_id'],)).fetchone()
    if not source or source['review_source_ref'] != header['capture']['source_ref']:
        fail('source_basis_mismatch')
    if header.get('layout') == 2:
        if human_reference(envelope) != {'layout':2, 'proof_id':proof_id}:
            fail('human_reference_changed')
        return
    pins=envelope.get('_document_inputs')
    if pins is not None:
        ref=pins.get('replay')
        if not ref or not (ref==header['capture']['replay_ref'] or ref.get('payload_hash')==header['activation_replay_hash']):
            fail('replay_changed')
        return
    if '_document_inputs' in envelope:
        from src.workflows.operational_document_inputs_v1 import replay_reference
        active_replay_ref=replay_reference(envelope)
        if not active_replay_ref or not (active_replay_ref==header['capture']['replay_ref'] or active_replay_ref.get('payload_hash')==header['activation_replay_hash']):
            fail('replay_changed')
    elif stable_json_hash(activation_replay(envelope.get('semantic_replay') or {})) != header['activation_replay_hash']:
        fail('replay_changed')
    original = next((a for a in envelope.get('processing_attempts') or []
                     if a['attempt_id'] == header['capture']['attempt_id']), None)
    if original is not None:
        diagnostic = original.get('diagnostic') or {}
        gate = diagnostic.get('final_validation') or {}
        if (envelope.get('processing_storage') != 'task-v1'
                or encoded(diagnostic.get('validator_input_ref')) != encoded(header['capture']['input_ref'])
                or encoded(_gate(gate)) != encoded(header['capture']['gate'])
                or original.get('expected_revision') != header['capture']['activation_revision']
                or original.get('actor_id') != header['capture']['actor_id']
                or gate.get('stage') != 'sealed' or gate.get('formation_evidence_ref') != {'layout':1,'proof_id':proof_id}):
            fail('active_receipt_changed')


def capture(con, context_id, attempt_id, *, payloads=False):
    """Capture identity/hash membership; activation never reloads member bodies."""
    context = con.execute('SELECT snapshot_id,artifact_id,semantic_identity,semantic_hash,expected_revision,final_validation '
        'FROM workflow.formation_contexts WHERE context_id=%s', (context_id,)).fetchone()
    attempt = con.execute('SELECT payload FROM workflow.processing_attempts WHERE attempt_id=%s AND snapshot_id=%s',
        (attempt_id, context['snapshot_id'] if context else '')).fetchone()
    if context is None or attempt is None:
        fail('context_missing')
    document = con.execute('SELECT revision,review_source_ref,formation_evidence_id,source_sha256,source_version '
                           'FROM workflow.documents WHERE snapshot_id=%s',
                           (context['snapshot_id'],)).fetchone()
    if document is None:
        fail('document_missing')
    diagnostic = attempt['payload'].get('diagnostic') or {}
    ref = diagnostic.get('formation_finalized_ref')
    receipt = context['final_validation']
    if (not ref or not receipt or receipt.get('version') != 3
            or encoded(receipt) != encoded(diagnostic.get('final_validation'))
            or receipt.get('activation_revision') != attempt['payload'].get('expected_revision')
            or attempt['payload'].get('source_hash') != document['source_sha256']
            or attempt['payload'].get('source_version') != document['source_version']
            or (diagnostic.get('validator_input_ref') or {}).get('context_id') != context_id
            or (diagnostic.get('validator_input_ref') or {}).get('artifact_id') != context['artifact_id']):
        fail('finalized_capture_required')
    rows = con.execute('SELECT ranges_hash,result_hash' + (',payload' if payloads else '') +
        ' FROM workflow.formation_task_results WHERE context_id=%s ORDER BY ranges_hash', (context_id,)).fetchall()
    result_hashes = [{k: r[k] for k in ('ranges_hash', 'result_hash')} for r in rows]
    if stable_json_hash(result_hashes) != receipt['result_set_hash']:
        fail('result_set_changed')
    plan = con.execute('SELECT plan_hash' + (',payload' if payloads else '') +
        ' FROM workflow.formation_task_plans WHERE context_id=%s', (context_id,)).fetchone()
    checkpoints = con.execute('SELECT checkpoint_id,phase' + (',payload' if payloads else '') +
        " FROM workflow.processing_checkpoints WHERE attempt_id=%s AND phase IN "
        "('formation_accounted','task_rejected','joint_validation_rejected','budget_exhausted',"
        "'formation_call_basis','formation_call') "
        'ORDER BY checkpoint_id', (attempt_id,)).fetchall()
    summary = {'context_id': context_id, 'artifact_id': context['artifact_id'],
        'semantic_hash': context['semantic_hash'], 'context_revision': context['expected_revision'],
        'attempt_id': attempt_id, 'claim_token': (attempt['payload'].get('dispatch') or {}).get('token'),
        'actor_id': attempt['payload'].get('actor_id'),
        'activation_revision': attempt['payload'].get('expected_revision'), 'input_ref': diagnostic.get('validator_input_ref'),
        'document_revision': document['revision'], 'source_ref': diagnostic.get('review_source_ref'),
        'active_source_ref': document['review_source_ref'],
        'processing_configuration': attempt['payload'].get('processing_configuration'),
        'gate': _gate(receipt), 'replay_ref': ref, 'results': result_hashes,
        'plan_hash': plan['plan_hash'] if plan else None,
        'checkpoints': [{k: row[k] for k in ('checkpoint_id', 'phase')} for row in checkpoints]}
    return summary, context, attempt['payload'], rows, plan, checkpoints


class FormationEvidence:
    def _prepare_human_evidence(self, envelope, attempt_id):
        with self.documents._connect() as con:
            con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            summary, seal, entries, attempt = human_capture(con, envelope['snapshot_id'], attempt_id)
            current = con.execute('SELECT workflow.annotation_seal_current(%s,%s) AS valid',
                (envelope['snapshot_id'], summary['annotation_seal_id'])).fetchone()['valid']
        if not current or not summary['source_ref'] or not summary['claim_token']:
            fail('human_capture_changed')
        from src.vorming.processing_retry_v1 import assert_active, now
        assert_active({'processing_attempts': [attempt]}, attempt_id, now())
        extraction = self.retained_extraction(envelope, seal['extraction_hash'])
        from src.vorming.source_preparation_context_v1 import stored_extraction
        fragments = stored_extraction({**envelope, 'prepared_source_extraction': extraction})
        from src.vorming.human_annotation_materialisation_v1 import build_objects
        extraction_header = {k:v for k,v in extraction.items() if k not in {'fragments', 'docling_record'}}
        fragments = self.read_review_source({**envelope, 'prepared_source_extraction': extraction_header,
                                             '_review_source_ref': summary['source_ref']})
        if fragments is None:
            fail('source_basis_missing')
        objects = build_objects(seal, entries, fragments=fragments)
        candidates = objects
        if seal.get('revision_basis'):
            from src.review.revision_workflow import apply_annotation_revisions
            objects = apply_annotation_revisions(candidates, seal['revision_basis'],
                snapshot_id=envelope['snapshot_id'], fragments=fragments, context=seal['context'])
        members = [('input', '0', seal), ('source', '0', {'reference': summary['source_ref'], 'extraction_header': extraction_header})]
        members += [('annotation', entry['annotation_id'], entry) for entry in entries]
        if seal.get('revision_basis'):
            members += [('candidate', obj['object_id'], obj) for obj in candidates]
        members += [('result', obj['object_id'], obj) for obj in objects]
        records = tuple((role, key, stable_json_hash(value), encoded(value)) for role, key, value in sorted(members))
        header = {'layout': 2, 'variant': 'human-annotation-v1', 'source': source_binding(envelope),
                  'extraction_hash': seal['extraction_hash'], 'capture': summary,
                  'manifest': [[role, key, digest] for role, key, digest, _ in records]}
        if seal.get('revision_basis'):
            header['application'] = 'human-annotation-revision-v1'
        return PreparedFormationEvidence(encoded(header), records)

    def _validate_human_members(self, header, members):
        seal = next((value for role, _, value in members if role == 'input'), None)
        if not seal or stable_json_hash(seal) != header['capture']['annotation_seal_id']:
            fail('human_seal_changed')
        entries_by_id = {key:value for role, key, value in members if role == 'annotation'}
        if set(entries_by_id) != {ref['annotation_id'] for ref in seal['entries']}:
            fail('human_entry_changed')
        entries = [entries_by_id[ref['annotation_id']] for ref in seal['entries']]
        if any({k:entry[k] for k in ('annotation_id', 'revision', 'payload_hash')} != ref
               for entry, ref in zip(entries, seal['entries'])):
            fail('human_entry_changed')
        extraction = self.retained_extraction(header['source'], header['extraction_hash'])
        from src.vorming.source_preparation_context_v1 import stored_extraction
        from src.vorming.human_annotation_materialisation_v1 import build_objects
        objects = build_objects(seal, entries, fragments=stored_extraction(
            {**header['source'], 'prepared_source_extraction': extraction}))
        candidates = {key:value for role, key, value in members if role == 'candidate'}
        if seal.get('revision_basis'):
            if header.get('application') != 'human-annotation-revision-v1':
                fail('human_revision_contract_invalid')
            if candidates != {obj['object_id']:obj for obj in objects}:
                fail('human_candidate_changed')
            from src.review.revision_workflow import apply_annotation_revisions
            objects = apply_annotation_revisions(objects, seal['revision_basis'],
                snapshot_id=seal['snapshot_id'], fragments=stored_extraction(
                    {**header['source'], 'prepared_source_extraction': extraction}), context=seal['context'])
        elif candidates or 'application' in header:
            fail('human_candidate_changed')
        actual = {key:value for role, key, value in members if role == 'result'}
        if actual != {obj['object_id']:obj for obj in objects}:
            fail('human_result_changed')

    def activation_envelope(self, envelope, attempt_id):
        """Prepare the selected immutable extraction outside the activation lock."""
        if attempt_id is None:
            return envelope
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        with self.documents._connect() as con:
            if not available(con):
                return envelope
            attempt = con.execute('SELECT payload FROM workflow.processing_attempts WHERE snapshot_id=%s AND attempt_id=%s',
                (envelope['snapshot_id'], attempt_id)).fetchone()
            reference = ((attempt['payload'].get('diagnostic') or {}).get('formation_evidence_ref')) if attempt else None
            if reference is None:
                return envelope
            row = con.execute('SELECT header,sealed,extraction_hash FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                              (reference.get('proof_id'),)).fetchone()
            if not row or not row['sealed'] or stable_json_hash(row['header']) != reference.get('proof_id'):
                fail('integrity_failed')
            if row['header']['source'] != source_binding(envelope):
                fail('source_mismatch')
            from src.vorming.source_preparation_context_v1 import KEY, stored_extraction
            if (envelope.get(KEY) or {}).get('record_hash') == row['extraction_hash']:
                return envelope
            extraction = con.execute('SELECT payload FROM workflow.prepared_extraction_versions WHERE record_hash=%s',
                                     (row['extraction_hash'],)).fetchone()
        if extraction is None:
            fail('source_basis_missing')
        result = {**envelope, KEY:extraction['payload']}
        stored_extraction(result)
        return result

    def prepare_formation_evidence(self, envelope, *, context_id=None, attempt_id):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        if context_id is None:
            return self._prepare_human_evidence(envelope, attempt_id)
        # One snapshot for owner-derived membership, not caller-supplied counts.
        with self.documents._connect() as con:
            con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            summary, context, attempt, results, plan, checkpoints = capture(con, context_id, attempt_id, payloads=True)
        if envelope['snapshot_id'] != context['snapshot_id']:
            fail('source_mismatch')
        input_ref = (attempt.get('diagnostic') or {}).get('validator_input_ref')
        preparation = self.resolve_preparation(input_ref, expected_snapshot_id=envelope['snapshot_id'])
        replay = self.read_processing_archive(summary['replay_ref'], envelope=envelope)
        identity = replay.get('identity') or {}
        from src.vorming.semantic_proposal_contract_v1 import semantic_contract_version
        parameters = preparation['validator_input']
        expected_contract = semantic_contract_version(field_contract_v2=parameters.get('field_contract_v2', False),
                                                     field_contract_v3=parameters.get('field_contract_v3', False))
        if (identity != context['semantic_identity'] or stable_json_hash(identity) != context['semantic_hash']
                or identity.get('hash') != stable_json_hash(identity.get('components'))
                or identity.get('components', {}).get('semantic_contract_version') != expected_contract
                or any(identity.get('components', {}).get(key) != envelope[field] for key, field in (
                    ('snapshot_id','snapshot_id'), ('document_id','document_id'), ('source_sha256','sha256')))
                or summary['gate'].get('validator_identity') != (attempt.get('diagnostic') or {}).get('validator_identity')
                or exact_replay_lookup(replay, expected_identity=identity).status != LOOKUP_HIT
                or replay.get('proposal_hash') != summary['gate']['proposal_hash']):
            fail('proposal_mismatch')
        from src.vorming.prepared_source_views_v1 import candidate_fragments as _candidate_fragments, evidence_fragments as _evidence_fragments
        from src.vorming.semantic_passage_v1 import semantic_source_blocks
        from src.vorming.source_preparation_context_v1 import KEY
        source = preparation['extraction']['source']
        if any(source[k] != envelope[k] for k in source):
            fail('source_mismatch')
        source_ref = (attempt.get('diagnostic') or {}).get('review_source_ref')
        if not source_ref or encoded(source_ref) != encoded(summary['source_ref']):
            fail('source_basis_missing')
        extraction_header = {k:v for k,v in preparation['extraction'].items() if k not in {'fragments','docling_record'}}
        source_envelope = {**envelope, KEY: extraction_header, '_review_source_ref': source_ref}
        raw = self.read_review_source(source_envelope)
        if raw is None:
            fail('source_basis_missing')
        blocks = semantic_source_blocks(_candidate_fragments(raw))
        evidence_blocks = semantic_source_blocks(_evidence_fragments(raw))
        if stable_json_hash({'source_blocks': blocks, 'evidence_blocks': evidence_blocks}) != identity['components'].get('source_blocks_hash'):
            fail('source_basis_mismatch')
        evidence = replay.get('provider_evidence') or {}
        if preparation['validator_input'].get('field_contract_v3'):
            basis = [r for r in checkpoints if r['phase'] == 'formation_call_basis']
            if basis:
                start = basis[-1]
                expected_calls = self.read_processing_archive(start['payload']['call_ref'], envelope=envelope)['calls']
                for row in checkpoints:
                    if row['phase'] == 'formation_call' and row['checkpoint_id'] > start['checkpoint_id']:
                        expected_calls += self.read_processing_archive(row['payload']['call_ref'], envelope=envelope)['calls']
            else:
                # A pure replay runs no bounded task loop. Its actual retained
                # owner record, not the submitted finalized record, is the basis.
                owner_envelope = self.documents.get_envelope(envelope['snapshot_id'])
                if owner_envelope is None or source_binding(owner_envelope) != source_binding(envelope):
                    fail('source_mismatch')
                if '_document_inputs' in owner_envelope:
                    owner_ref=owner_envelope['_document_inputs'].get('replay')
                    if owner_ref is None:
                        fail('call_basis_missing')
                    prior=self.read_processing_archive(owner_ref,envelope=owner_envelope)
                else:
                    prior = owner_envelope.get('semantic_replay') or {}
                if replay.get('semantic_execution') != 'replay' or prior.get('identity') != identity:
                    fail('call_basis_missing')
                expected_calls = call_sequence(prior.get('provider_evidence') or {})
            if encoded(call_sequence(evidence)) != encoded(expected_calls):
                fail('call_membership_changed')
            accounted = [r for r in checkpoints if r['phase'] == 'formation_accounted']
            if not accounted or encoded(accounted[-1]['payload'].get('provider_evidence')) != encoded(evidence):
                fail('finding_capture_mismatch')
            from src.vorming.recoverable_formation_v1 import pending_rejections
            pending = pending_rejections(evidence, replay['proposal'], blocks=blocks)
            if (encoded(pending) != encoded(evidence.get('pending_rejections'))
                    or evidence.get('formation_incomplete') is not bool(pending)):
                fail('findings_mismatch')
        members = [('replay', '0', replay), ('input', context['artifact_id'], preparation['input']),
                   ('source', '0', {'reference':source_ref, 'extraction_header':extraction_header})]
        if plan is not None:
            if stable_json_hash(plan['payload']) != plan['plan_hash']:
                fail('plan_integrity_failed')
            if evidence.get('task_policy') and encoded(evidence.get('task_plan')) != encoded(plan['payload']):
                fail('plan_mismatch')
            members.append(('plan', plan['plan_hash'], plan['payload']))
        for row in results:
            if stable_json_hash(row['payload']) != row['result_hash']:
                fail('result_integrity_failed')
            members.append(('result', row['ranges_hash'], row['payload']))
        members += [('checkpoint', str(row['checkpoint_id']), row['payload']) for row in checkpoints]
        records = tuple((role, key, stable_json_hash(value), encoded(value)) for role, key, value in sorted(members))
        header = {'layout': 1, 'variant': 'task-v1-semantic', 'source': source_binding(envelope),
            'extraction_hash': preparation['extraction']['record_hash'], 'capture': summary,
            'proposal_hash': replay['proposal_hash'], 'identity': identity,
            'activation_replay_hash': stable_json_hash(activation_replay(replay)),
            'findings_hash': stable_json_hash(evidence.get('pending_rejections')),
            'manifest': [[role, key, digest] for role, key, digest, _ in records]}
        return PreparedFormationEvidence(encoded(header), records)

    def publish_formation_evidence(self, envelope, prepared):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        header = json.loads(prepared.header_text)
        # Re-derive expected membership from the fenced owner capture. A trimmed
        # carrier with self-consistent replacement hashes is still rejected.
        expected = self.prepare_formation_evidence(envelope,
            context_id=header['capture'].get('context_id'), attempt_id=header['capture']['attempt_id'])
        if prepared != expected:
            fail('preparation_changed')
        proof_id = stable_json_hash(header)
        with self.documents._connect() as con:
            if header['layout'] == 2:
                con.execute('INSERT INTO workflow.formation_evidence_roots '
                    '(proof_id,snapshot_id,context_id,extraction_hash,annotation_seal_id,header) VALUES(%s,%s,NULL,%s,%s,%s::jsonb) '
                    'ON CONFLICT DO NOTHING', (proof_id, envelope['snapshot_id'], header['extraction_hash'],
                        header['capture']['annotation_seal_id'], prepared.header_text))
            else:
                con.execute('INSERT INTO workflow.formation_evidence_roots '
                    '(proof_id,snapshot_id,context_id,extraction_hash,header) VALUES(%s,%s,%s,%s,%s::jsonb) '
                    'ON CONFLICT DO NOTHING', (proof_id, envelope['snapshot_id'], header['capture']['context_id'],
                        header['extraction_hash'], prepared.header_text))
            row = con.execute('SELECT header,sealed FROM workflow.formation_evidence_roots WHERE proof_id=%s FOR UPDATE',
                              (proof_id,)).fetchone()
            if encoded(row['header']) != prepared.header_text:
                fail('conflict')
            if not row['sealed']:
                with con.cursor() as cur:
                    cur.executemany('INSERT INTO workflow.formation_evidence_members '
                        '(proof_id,role,member_key,payload_hash,payload_text) VALUES(%s,%s,%s,%s,%s)',
                        [(proof_id, *record) for record in prepared.members])
                con.execute('UPDATE workflow.formation_evidence_roots SET sealed=true WHERE proof_id=%s', (proof_id,))
        return {'layout': header['layout'], 'proof_id': proof_id}

    def read_formation_evidence(self, reference, *, envelope):
        if not isinstance(reference, dict) or type(reference.get('layout')) is not int or reference['layout'] not in {1, 2}:
            fail('layout_unsupported')
        with self.documents._connect() as con:
            row = con.execute('SELECT header,sealed FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                              (reference.get('proof_id'),)).fetchone()
            members = con.execute('SELECT role,member_key,payload_hash,payload_text FROM workflow.formation_evidence_members '
                'WHERE proof_id=%s ORDER BY role COLLATE "C",member_key COLLATE "C"', (reference.get('proof_id'),)).fetchall()
        if row is None:
            fail('missing')
        header = row['header']
        if header.get('layout') != reference['layout']:
            fail('layout_unsupported')
        if not row['sealed'] or stable_json_hash(header) != reference['proof_id']:
            fail('integrity_failed')
        if header['source'] != source_binding(envelope):
            fail('source_mismatch')
        if [[m['role'],m['member_key'],m['payload_hash']] for m in members] != header['manifest']:
            fail('membership_incomplete')
        result = []
        for member in members:
            payload = json.loads(member['payload_text'])
            if stable_json_hash(payload) != member['payload_hash'] or encoded(payload) != member['payload_text']:
                fail('integrity_failed')
            result.append((member['role'], member['member_key'], payload))
        basis = next((value for role, _, value in result if role == 'source'), None)
        if not basis or self.read_review_source({**envelope, 'prepared_source_extraction':basis['extraction_header'],
                                                '_review_source_ref':basis['reference']}) is None:
            fail('source_basis_missing')
        if header['layout'] == 2:
            self._validate_human_members(header, result)
        return {'header': header, 'members': result}


def assert_human_activation(con, envelope, reference, *, objects):
    from src.vorming.human_annotation_build_v1 import require_storage
    require_storage(con)
    latest = next(reversed(envelope.get('processing_attempts') or []), {})
    diagnostic = latest.get('diagnostic') or {}
    gate = diagnostic.get('final_validation') or {}
    if (objects is None or envelope.get('processing_storage') != 'task-v1'
            or gate.get('version') != 3 or gate.get('stage') != 'sealed'
            or gate.get('formation_evidence_ref') != reference
            or diagnostic.get('formation_evidence_ref') != reference
            or human_reference(envelope) != reference):
        fail('sealed_capture_required')
    row = con.execute('SELECT header,sealed FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                      (reference.get('proof_id'),)).fetchone()
    if not row or not row['sealed'] or stable_json_hash(row['header']) != reference.get('proof_id'):
        fail('integrity_failed')
    header = row['header']
    current, seal, _, attempt = human_capture(con, envelope['snapshot_id'], latest.get('attempt_id'))
    valid = con.execute('SELECT workflow.annotation_seal_current(%s,%s) AS valid',
                        (envelope['snapshot_id'], current['annotation_seal_id'])).fetchone()['valid']
    if (header.get('layout') != 2 or header.get('variant') != 'human-annotation-v1' or not valid
            or header['source'] != source_binding(envelope) or current != header['capture']
            or latest.get('annotation_seal_id') != current['annotation_seal_id']
            or latest.get('expected_revision') != seal['objects_revision']):
        fail('activation_changed')
    if seal.get('revision_basis'):
        from src.review.revision_workflow import current_revisions
        actual = [r['payload'] for r in con.execute('SELECT payload FROM workflow.document_objects WHERE snapshot_id=%s ORDER BY position', (envelope['snapshot_id'],)).fetchall()]
        if current_revisions(actual, snapshot_id=envelope['snapshot_id']) != seal['revision_basis']['objects']:
            fail('human_predecessor_changed')
        prior = con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s', (envelope['snapshot_id'],)).fetchone()
        if prior['formation_evidence_id'] != seal['revision_basis']['proof_id']:
            fail('human_predecessor_changed')
        objects = current_revisions(objects, snapshot_id=envelope['snapshot_id'])
    expected = {key:digest for role, key, digest in header['manifest'] if role == 'result'}
    if len(objects) != len(expected) or {obj['object_id']:stable_json_hash(obj) for obj in objects} != expected:
        fail('human_result_changed')
    from src.vorming.processing_retry_v1 import assert_active, now
    from src.vorming.source_selection_v1 import authorize_account
    assert_active({'processing_attempts': [attempt]}, attempt['attempt_id'], now())
    if (attempt.get('dispatch') or {}).get('state') != 'claimed' or not current['claim_token']:
        fail('claim_changed')
    account = con.execute('SELECT account_id,roles,retirement FROM workflow.accounts WHERE account_id=%s FOR SHARE',
                          (attempt['actor_id'],)).fetchone()
    if not account:
        fail('authorization_changed')
    reviewers = [r['account_id'] for r in con.execute('SELECT account_id FROM workflow.document_reviewers WHERE snapshot_id=%s',
                                                    (envelope['snapshot_id'],)).fetchall()]
    authorize_account(account, {'named_reviewers': reviewers})
    assert_active({'processing_attempts': [attempt]}, attempt['attempt_id'], now())
    con.execute('UPDATE workflow.documents SET formation_evidence_id=%s,review_source_ref=%s::jsonb WHERE snapshot_id=%s',
                (reference['proof_id'], encoded(current['source_ref']), envelope['snapshot_id']))


def assert_activation(con, envelope):
    latest = next(reversed(envelope.get('processing_attempts') or []), {})
    diagnostic = latest.get('diagnostic') or {}
    gate = diagnostic.get('final_validation') or {}
    if gate.get('version') != 3:
        return
    ref = diagnostic.get('formation_evidence_ref')
    if not ref or gate.get('stage') != 'sealed' or gate.get('formation_evidence_ref') != ref:
        fail('sealed_capture_required')
    if not isinstance(ref, dict) or ref.get('layout') != 1:
        fail('layout_unsupported')
    row = con.execute('SELECT header,sealed FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                      (ref.get('proof_id'),)).fetchone()
    if not row or not row['sealed'] or stable_json_hash(row['header']) != ref.get('proof_id'):
        fail('integrity_failed')
    header = row['header']
    current, _, active_attempt, _, _, _ = capture(con, header['capture']['context_id'], latest['attempt_id'])
    active = con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s',
                         (envelope['snapshot_id'],)).fetchone()
    already_active = bool(active and active['formation_evidence_id'] == ref['proof_id'])
    if already_active:
        # Explicit idempotent producer retry may retain the same pin after
        # metadata advanced, but still requires the current live authorization.
        # Ordinary curation uses retain_active_evidence instead.
        current['document_revision'] = header['capture']['document_revision']
        current['active_source_ref'] = header['capture']['active_source_ref']
    context_gate = con.execute('SELECT final_validation FROM workflow.formation_contexts WHERE context_id=%s',
                              (header['capture']['context_id'],)).fetchone()['final_validation']
    if (header['source'] != source_binding(envelope) or current != header['capture']
            or encoded(gate) != encoded(context_gate) or latest.get('expected_revision') != gate.get('activation_revision')
            or latest.get('actor_id') != current['actor_id']
            or diagnostic.get('validator_input_ref') != current['input_ref']):
        fail('activation_changed')
    from src.operations_console_v1 import ConsoleError
    from src.vorming.processing_retry_v1 import assert_active, now
    from src.vorming.source_selection_v1 import authorize_account
    try:
        assert_active({'processing_attempts':[active_attempt]}, latest['attempt_id'], now())
        dispatch = active_attempt.get('dispatch') or {}
        if dispatch and (dispatch.get('state') != 'claimed' or not dispatch.get('token')):
            fail('claim_changed')
        account = con.execute('SELECT account_id,roles,retirement FROM workflow.accounts WHERE account_id=%s FOR SHARE',
                              (active_attempt['actor_id'],)).fetchone()
        if not account:
            fail('authorization_changed')
        reviewers = [r['account_id'] for r in con.execute('SELECT account_id FROM workflow.document_reviewers '
                     'WHERE snapshot_id=%s', (envelope['snapshot_id'],)).fetchall()]
        authorize_account(account, {'named_reviewers':reviewers})
    except ConsoleError as error:
        raise WorkflowDocumentStoreError('formation_evidence_activation_not_authorized') from error
    if '_document_inputs' in envelope:
        from src.workflows.operational_document_inputs_v1 import replay_reference
        active_replay_ref=replay_reference(envelope)
        if not active_replay_ref or not (active_replay_ref==header['capture']['replay_ref'] or active_replay_ref.get('payload_hash')==header['activation_replay_hash']):
            fail('replay_changed')
    elif stable_json_hash(activation_replay(envelope.get('semantic_replay') or {})) != header['activation_replay_hash']:
        fail('replay_changed')
    # Account lock waiting and hashing may consume the remaining lease.
    try:
        assert_active({'processing_attempts':[active_attempt]}, latest['attempt_id'], now())
    except ConsoleError as error:
        raise WorkflowDocumentStoreError('formation_evidence_activation_not_authorized') from error
    # The caller's existing object/attempt transaction owns this pin. A later
    # failure rolls the pin back with the same objects/envelope/attempt writes.
    pinned = con.execute('UPDATE workflow.documents SET formation_evidence_id=%s,review_source_ref=%s::jsonb '
                         'WHERE snapshot_id=%s',
                         (ref['proof_id'], _json_text(header['capture']['source_ref']), envelope['snapshot_id']))
    if pinned.rowcount != 1:
        fail('document_missing')

"""Bounded explanations of existing evidence; never a workflow/action authority."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile
from datetime import datetime, timezone

from src.processing_trace_v1 import attempt_id, clean_runtime, digest, mapping, project_attempt, runtime_identity, sha, token
from src.section_incident_v1 import choice, number, timestamp
from src.attempt_diagnostics_v1 import VALIDATOR_FILES

VERSION = 'blockage-report-v1'
MAX_FINDINGS = 256
MAX_ROWS = 50000
MAX_ZIP_BYTES = 32 * 1024 * 1024
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
COUNT_FIELDS = ('planned_task_count', 'terminal_task_count', 'pending_task_count',
                'failed_task_count', 'partial_task_count', 'not_started_task_count',
                'pending_source_range_count', 'pending_source_char_count', 'unknown_pending_count')
DATASETS = ('revision', 'processing_attempts', 'attempt_diagnostics', 'semantic_proposals',
            'formation_progress', 'formation_findings', 'model_calls', 'validation_findings')

# Descriptions of exact codes, not another implementation of their predicates.
EXPLANATIONS = {
    'semantic_evidence_literal_not_found': ('Bronbewijs niet teruggevonden', 'Het aangewezen letterlijke bewijs moet in het opgegeven bronbereik staan.'),
    'semantic_evidence_literal_ambiguous': ('Bronbewijs niet eenduidig', 'Het aangewezen bewijs moet naar één exact bronbereik verwijzen.'),
    'source_bound_field_outside_candidate': ('Veldbewijs buiten de kandidaat', 'Veldbewijs moet binnen de door het broncontract toegestane kandidaat vallen.'),
    'source_assessment_bounds_invalid': ('Ongeldig beoordelingsbereik', 'De beoordeling moet naar een geldig bereik in de opgegeven bron verwijzen.'),
    'semantic_span_hidden_gap': ('Niet-verantwoorde onderbreking', 'Het bronbereik moet voldoen aan het geldende aaneengeslotenheidscontract.'),
    'semantic_dependency_rejected': ('Afhankelijk voorstel afgewezen', 'De benodigde afhankelijkheid moet door de bestaande controle worden geaccepteerd.'),
    'source_task_budget_exhausted': ('Taakbudget bereikt', 'Verwerking moet binnen het geldende taakbudget blijven; de uitvoerhistorie bepaalt welk werk nog openstaat.'),
    'source_formation_incomplete': ('Bronverwerking nog onvolledig', 'Alle vereiste bronverwerking moet volgens de bestaande controles zijn verantwoord.'),
    'review_work_incomplete': ('Review nog niet afgerond', 'De bestaande reviewverplichtingen moeten zijn afgerond.'),
    'review_repair_incomplete': ('Reviewherstel nog open', 'De bestaande herstelverplichtingen moeten zijn afgehandeld.'),
    'source_passage_review_incomplete': ('Beoordeling brontekst nog open', 'De vereiste beoordeling van overige brontekst moet zijn afgerond.'),
    'processing_resume_configuration_incompatible': ('Verwerkingsinstellingen passen niet bij hervatten', 'De huidige instellingen moeten aansluiten op het bestaande hervatcontract.'),
    'readiness_authority_unavailable': ('Publicatiecontrole niet beschikbaar', 'De bestaande publicatiecontrole moet een betrouwbaar resultaat kunnen leveren.'),
}


def code(value):
    return token(value, r'[a-z][a-z0-9_]{0,95}')


def explain(value):
    recognized = code(value)
    title, expected = EXPLANATIONS.get(recognized, ('Controlecode nog niet verklaard', None))
    return {'code': recognized, 'unrecognized_value_sha256': digest(value) if recognized is None else None,
            'title': title, 'expected_condition': expected,
            'explanation_status': 'known_code' if recognized in EXPLANATIONS else 'unexplained_code',
            'expectation_basis': 'code_contract_description_not_an_execution_trace'}


def _ref(dataset, row, field):
    return {'dataset': dataset + '.csv', 'row': row, 'field': field}


def revision_context(snapshot_id, revision, envelope):
    """Explicit observed context; does not make independent reads atomic."""
    configuration = envelope.get('processing_configuration')
    return {'snapshot_id':snapshot_id, 'objects_revision':revision,
        'source_hash':sha(envelope.get('sha256')), 'source_version_sha256':digest(envelope.get('version')),
        'configuration_sha256':digest(json.dumps(configuration, sort_keys=True)) if isinstance(configuration, dict) else None}


def blockage_report(tables, *, checks=None, selected_attempt=None):
    """Project supplied records. Never rerun validation or infer missing decisions."""
    if selected_attempt is not None and attempt_id(selected_attempt) is None:
        raise ValueError('invalid_attempt_selector')
    missing, conflicts = set(), set()
    roots = tables.get('revision') or []
    root = roots[0] if len(roots) == 1 else {}
    if len(roots) != 1 or not root.get('snapshot_id') or not root.get('objects_revision'):
        missing.add('revision_context_missing_or_ambiguous')
    snapshot = root.get('snapshot_id')
    revision = root.get('objects_revision')
    revision_hash = digest(revision)
    compact_revision = 'sha256:' + revision_hash if revision_hash else None
    if root.get('revision_id') and root['revision_id'] != compact_revision:
        conflicts.add('revision_id_disagrees')
    accepted = {}
    for name in DATASETS[1:]:
        rows = tables.get(name) or []
        accepted[name] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                conflicts.add('invalid_row:' + name)
                continue
            row_revision = row.get('objects_revision')
            matches = (row_revision == revision if row_revision is not None else
                       bool(compact_revision and row.get('revision_id') == compact_revision))
            if snapshot and revision and row.get('snapshot_id') == snapshot and matches:
                accepted[name].append((index + 1, row))
            else:
                conflicts.add('row_identity_mismatch:' + name)
        if not rows:
            missing.add('not_recorded:' + name)
    proposals = accepted['semantic_proposals']
    replay = proposals[0][1] if len(proposals) == 1 else {}
    if len(proposals) > 1:
        conflicts.add('proposal_selection_ambiguous')
    identity = mapping(replay.get('identity'))
    components = mapping(identity.get('components'))
    source_hashes = {sha(row.get('source_hash')) for _, row in accepted['processing_attempts']}
    source_hashes.add(sha(root.get('source_hash')))
    source_hashes.add(sha(components.get('source_sha256')))
    source_hashes.discard(None)
    if len(source_hashes) > 1:
        conflicts.add('source_hash_disagrees')
    source_hash = next(iter(source_hashes)) if len(source_hashes) == 1 else None
    if source_hash is None:
        missing.add('source_identity_not_established')
    diagnostics = {row.get('attempt_id'): row.get('diagnostic') for _, row in accepted['attempt_diagnostics']}
    diagnostic_counts = Counter(row.get('attempt_id') for _, row in accepted['attempt_diagnostics'])
    if any(count > 1 for count in diagnostic_counts.values()):
        conflicts.add('duplicate_attempt_diagnostics')
        diagnostics = {key:value for key,value in diagnostics.items() if diagnostic_counts[key] == 1}
    validation_observations = []
    for index, row in accepted['attempt_diagnostics'][-64:]:
        diagnostic = mapping(row.get('diagnostic'))
        validator = mapping(diagnostic.get('validator_identity'))
        validation_observations.append({'attempt_id':attempt_id(row.get('attempt_id')),
            'validator_files':{name:sha(validator.get(name)) for name in VALIDATOR_FILES if sha(validator.get(name))},
            'python_version':token(validator.get('python_version'), r'[0-9.]{1,24}'),
            'field_contract':choice(diagnostic.get('field_contract'), {'v1','v2','v3'}),
            'validator_input_hash':sha(diagnostic.get('validator_input_hash')),
            'resolved_proposal_hash':sha(diagnostic.get('resolved_proposal_hash')),
            'semantic_identity_hash':sha(mapping(diagnostic.get('semantic_identity')).get('hash')),
            'evidence_ref':_ref('attempt_diagnostics', index, 'diagnostic'),
            'finding_attribution':'not_inferred_from_shared_identity'})
    attempts = [project_attempt({**row, 'diagnostic':diagnostics.get(row.get('attempt_id'))})
                for _, row in accepted['processing_attempts'][-64:]]
    eligible = [a for a in attempts if a['attempt_id'] == selected_attempt] if selected_attempt else attempts
    selected = eligible[0] if len(eligible) == 1 and eligible[0]['attempt_id'] else None
    if selected is None:
        missing.add('attempt_selection_ambiguous_or_missing')
    selected_result = None
    if selected:
        row_number = next(index for index,row in accepted['processing_attempts'] if row.get('attempt_id') == selected['attempt_id'])
        selected_result = {'attempt_id':selected['attempt_id'], 'stored_state':selected['stored_state'],
            'error':explain(selected['error_code']) if selected['error_code'] else None,
            'last_checkpoint':selected['checkpoints'][-1] if selected['checkpoints'] else None,
            'evidence_refs':[_ref('processing_attempts', row_number, 'state')],
            'scope':'selected_attempt_not_automatically_current_document_blocker'}
    if any(a['origin_request_id'] is None for a in attempts):
        missing.add('origin_request_not_recorded')
    if any(a['diagnostic_evidence_omitted'] for a in attempts):
        missing.add('attempt_diagnostic_evidence_partial')
    if any(not a['checkpoints'] for a in attempts):
        missing.add('attempt_checkpoints_not_recorded')
    if validation_observations and any(not row['validator_files'] for row in validation_observations):
        missing.add('validator_identity_not_recorded')
    calls = {}
    for index, row in accepted['model_calls']:
        if row.get('call_id'):
            calls.setdefault(row['call_id'], []).append(index)
    findings, counts = [], Counter()
    for dataset in ('formation_findings', 'validation_findings'):
        for index, row in accepted[dataset]:
            if dataset == 'formation_findings':
                state = choice(row.get('state'), {'pending', 'historical'}) or 'unknown'
                if state == 'unknown':
                    missing.add('finding_currentness_not_recorded')
            else:
                # Admission is a stored candidate observation, not publication authority.
                if row.get('gate_result') != 'blocked':
                    continue
                state = 'stored_candidate_admission'
            counts[state] += 1
            if len(findings) >= MAX_FINDINGS:
                continue
            refs = [_ref(dataset, index, 'reason_code')]
            detail = mapping(row.get('finding'))
            if dataset == 'formation_findings':
                refs.append(_ref(dataset, index, 'finding'))
            matches = calls.get(row.get('call_id'), [])
            if len(matches) == 1:
                refs.append(_ref('model_calls', matches[0], 'output_text'))
                refs.append(_ref('model_calls', matches[0], 'request'))
            elif dataset == 'formation_findings':
                missing.add('finding_call_link_ambiguous_or_missing')
            findings.append({**explain(row.get('reason_code')), 'scope':state,
                'field':code(detail.get('field')), 'candidate_index':number(detail.get('candidate_index')),
                'object_id_sha256':digest(row.get('object_id')),
                'observation':'recorded_producer_rejection' if dataset == 'formation_findings' else 'recorded_candidate_admission_block',
                'evidence_refs':refs, 'cause':'not_established', 'rule_execution_trace':'not_recorded'})
    if findings:
        missing.add('individual_rule_execution_trace_not_recorded')
    progress_rows = accepted['formation_progress']
    progress = progress_rows[0][1] if len(progress_rows) == 1 else {}
    if len(progress_rows) > 1:
        conflicts.add('formation_progress_ambiguous')
    progress_values = {k:number(progress.get(k)) for k in COUNT_FIELDS}
    formation_pending = (progress.get('formation_state') == 'pending' or
                         (progress_values['pending_task_count'] or 0) > 0)
    blockers = []
    if formation_pending:
        blockers.append({**explain('source_formation_incomplete'), 'scope':'current_saved_proposal',
                         'evidence_refs':[_ref('formation_progress', progress_rows[0][0], 'pending_task_count')]})
    actions, check_summary = _checked_conditions(checks, snapshot, revision_hash, source_hash, conflicts, missing)
    if check_summary.get('readiness'):
        blockers.extend({**explain(c), 'scope':'observed_current_readiness',
                         'evidence_refs':[{'observation':'current_checks.readiness', 'field':'blockers'}]}
                        for c in check_summary['readiness']['blockers'] if c != 'source_formation_incomplete' or not formation_pending)
        formation_pending = formation_pending or 'source_formation_incomplete' in check_summary['readiness']['blockers']
        if not formation_pending and check_summary['readiness']['curation_blockers']:
            actions.append({'action':'review_obligations', 'observed_conditions_met':None,
                'recommended_investigation':True, 'required_permission':'named_reviewer',
                'evidence_ref':'current_checks.readiness.curation_blockers', 'execution_authorized':False,
                'requires_current_kernel_recheck':True})
    error_counts = Counter(code(row.get('failure_reason') or row.get('error_code'))
                           for _, row in accepted['model_calls'] if row.get('failure_reason') or row.get('error_code'))
    call_errors = [{'code':key, 'count':value, 'currentness':'not_established'}
                   for key, value in sorted(error_counts.items(), key=lambda p: str(p[0]))][:64]
    for item in call_errors:
        refs = [_ref('model_calls', index, 'failure_reason') for index,row in accepted['model_calls']
                if (row.get('failure_reason') or row.get('error_code')) and
                code(row.get('failure_reason') or row.get('error_code')) == item['code']]
        item['evidence_refs'], item['omitted_refs'] = refs[:16], max(0,len(refs)-16)
    if call_errors:
        missing.add('call_error_history_is_not_current_failure_authority')
    if conflicts:
        actions = [{**a, 'observed_conditions_met':None} for a in actions]
    return {'schema':VERSION, 'observed_at':datetime.now(timezone.utc).isoformat(),
        'context':{'snapshot_id':token(snapshot, r'snap-[0-9a-f]{16}-[0-9a-f]{8}'),
            'revision_sha256':revision_hash, 'source_hash':source_hash,
            'source_version_sha256':sha(root.get('source_version_sha256')),
            'configuration_sha256':sha(root.get('configuration_sha256')),
            'semantic_identity_hash':sha(identity.get('hash')),
            'configuration_hash':sha(components.get('model_config_hash'))},
        'authority':'diagnostic_projection_not_workflow_authority',
        'consistency':'independent_observations_not_an_atomic_historical_snapshot',
        'selected_attempt_id':selected['attempt_id'] if selected else None,
        'selected_attempt_state':selected['stored_state'] if selected else None,
        'selected_attempt_result':selected_result,
        'attempts':attempts, 'omitted_attempts':max(0, len(accepted['processing_attempts'])-64),
        'validation_observations':validation_observations,
        'omitted_validation_observations':max(0,len(accepted['attempt_diagnostics'])-64),
        'attempt_state_counts':dict(Counter(a['stored_state'] for a in attempts)),
        'finding_counts':dict(counts), 'findings':findings,
        'omitted_findings':sum(counts.values())-len(findings),
        'formation_progress':progress_values, 'formation_state':choice(progress.get('formation_state'), {'pending', 'complete'}),
        'blockers':blockers, 'next_blocking_stage':'identity_verification' if conflicts else 'source_formation' if formation_pending else
            'publication_conditions' if blockers else 'not_established',
        'call_error_history':call_errors, 'omitted_call_error_groups':max(0,len(error_counts)-64),
        'current_checks':check_summary, 'follow_up':actions,
        'missing_evidence':sorted(missing), 'identity_conflicts':sorted(conflicts),
        'domain_completion':'not_assessed_by_diagnostics'}


def _checked_conditions(checks, snapshot, revision_hash, source_hash, conflicts, missing):
    checks = mapping(checks)
    valid = bool(checks and checks.get('consistent') is True and checks.get('snapshot_id') == snapshot
                 and checks.get('revision_sha256') == revision_hash and source_hash
                 and checks.get('source_hash') == source_hash and not conflicts)
    if checks and not valid:
        conflicts.add('current_check_context_changed_or_mismatched')
    processing = mapping(checks.get('processing')) if valid else {}
    readiness = mapping(checks.get('readiness')) if valid else {}
    errors = {key:code(value) or 'check_unavailable' for key, value in mapping(checks.get('errors')).items()
              if key in {'processing', 'readiness', 'resume_configuration'}}
    for key in ('processing', 'readiness'):
        if not (processing if key == 'processing' else readiness):
            missing.add('current_' + key + '_check_not_available')
    actions = [{'action':name, 'observed_conditions_met':processing.get(field) if type(processing.get(field)) is bool else None,
        'observation_scope':'processing_status_and_resume_configuration' if name == 'resume' else 'processing_status',
        'required_permission':'researcher_or_named_reviewer',
        'evidence_ref':'current_checks.processing.'+field, 'execution_authorized':False,
        'requires_current_kernel_recheck':True} for name, field in (('resume', 'resume_allowed'), ('retry', 'retry_allowed'))]
    return actions, {'observed_at':timestamp(checks.get('observed_at')), 'context_matches':valid,
        'runtime':clean_runtime(checks.get('runtime')),
        'provenance':'supplied_check_observation_not_authenticated_by_report',
        'processing':{**{k:processing.get(k) for k in ('retry_allowed', 'resume_allowed', 'formation_incomplete', 'recovery_available') if type(processing.get(k)) is bool},
            'reason_code':code(processing.get('reason_code')), 'state':choice(processing.get('state'), {'running','succeeded','incomplete_budget','failed','interrupted','expired','not_recorded'}),
            'retry_not_before':timestamp(processing.get('retry_not_before')),
            **{k:number(processing.get(k)) for k in ('max_attempts','retry_attempts_used')}},
        'readiness':({'publication_ready':readiness.get('publication_ready') if type(readiness.get('publication_ready')) is bool else None,
            **{key:[code(c) or 'unrecognized_reason' for c in (readiness.get(key) or [])[:128]]
               for key in ('blockers','curation_blockers','technical_blockers')},
            'omitted_codes':{key:max(0,len(readiness.get(key) or [])-128)
                for key in ('blockers','curation_blockers','technical_blockers')},
            **{key:number(readiness.get(key)) for key in ('review_required_object_count','first_review_duty_count','second_review_duty_count')}} if readiness else {}),
        'errors':errors, 'execution_authorized':False}


def collect_blockage(console, *, actor_id, snapshot_id, current_checks=False, selected_attempt=None):
    """One authorized document. Default path reads only envelope/revision metadata."""
    from src.source_selection_v1 import authorize, assert_resume_configuration
    from src.processing_evidence_export_v1 import recorded_processing_tables
    from src.operations_console_v1 import ConsoleError
    envelope = console._envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    revision = console.objects_revision(snapshot_id)
    tables = recorded_processing_tables(snapshot_id=snapshot_id, revision=revision, envelope=envelope)
    tables['revision'] = [revision_context(snapshot_id, revision, envelope)]
    checks = None
    if current_checks:
        before = digest(json.dumps(envelope, sort_keys=True))
        checks = {'snapshot_id':snapshot_id, 'revision_sha256':digest(revision), 'source_hash':envelope.get('sha256'),
                  'observed_at':datetime.now(timezone.utc).isoformat(), 'runtime':runtime_identity(), 'errors':{}}
        with console.source_selection_read_scope(retained_only=True):
            for name, call in (('processing', lambda: console.processing_status(snapshot_id, actor_id=actor_id)),
                               ('readiness', lambda: console.publication_readiness(snapshot_id))):
                try:
                    if name == 'readiness':
                        from src.source_preparation_context_v1 import stored_extraction
                        from src.docling_contract_v1 import stored_fragments
                        if stored_extraction(envelope) is None and stored_fragments(envelope) is None:
                            checks['errors'][name] = 'retained_source_not_recorded'
                            continue
                    checks[name] = call()
                except Exception as error:
                    checks['errors'][name] = code(getattr(error, 'code', None)) or 'check_unavailable'
            if mapping(checks.get('processing')).get('resume_allowed'):
                try:
                    assert_resume_configuration(console, envelope)
                except ConsoleError as error:
                    checks['processing']['resume_allowed'] = False
                    checks['errors']['resume_configuration'] = code(error.code) or 'check_unavailable'
        try:
            after = console._envelope(snapshot_id)
        except (ConsoleError, OSError, ValueError, TypeError, KeyError):
            checks['consistent'] = False
        else:
            # Revoked access is an access denial, not a partial diagnostic result.
            authorize(console, actor_id, after)
            try:
                checks['consistent'] = (console.objects_revision(snapshot_id) == revision and
                                        digest(json.dumps(after, sort_keys=True)) == before)
            except (ConsoleError, OSError, ValueError, TypeError, KeyError):
                checks['consistent'] = False
    return blockage_report(tables, checks=checks, selected_attempt=selected_attempt)


def read_blockage_zip(path):
    """Read only required existing tables; bound compressed/uncompressed bytes/rows."""
    from src.forensic_trace_v1 import _parse_cell
    path = Path(path)
    if path.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError('evidence_zip_exceeds_limit')
    result = {}
    csv.field_size_limit(MAX_UNPACKED_BYTES)
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if sum(i.file_size for i in entries) > MAX_UNPACKED_BYTES or len(entries) > 1024:
            raise ValueError('unpacked_evidence_exceeds_limit')
        if len({i.filename for i in entries}) != len(entries):
            raise ValueError('duplicate_evidence_entries')
        for name in DATASETS:
            try:
                with archive.open(name + '.csv') as source:
                    raw = source.read(MAX_UNPACKED_BYTES + 1)
            except KeyError:
                continue
            if len(raw) > MAX_UNPACKED_BYTES:
                raise ValueError('evidence_table_exceeds_limit')
            rows = []
            for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                if len(rows) >= MAX_ROWS:
                    raise ValueError('evidence_rows_exceed_limit')
                if None in row or any(value is None for value in row.values()):
                    raise ValueError('invalid_evidence_csv_row')
                parsed = {k:_parse_cell(k, value) for k, value in row.items()}
                for key in COUNT_FIELDS:
                    value = parsed.get(key)
                    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 13:
                        parsed[key] = int(value)
                rows.append(parsed)
            result[name] = rows
    return result


def blockage_summary(report):
    lines = ['Metis — blokkade en bewijs', 'Diagnostiek is geen publicatie- of hersteltoestemming.',
        'Volgende blokkerende stap: ' + report['next_blocking_stage'],
        'Opgeslagen pogingen: ' + json.dumps(report['attempt_state_counts'], ensure_ascii=False),
        'Bevindingen: ' + json.dumps(report['finding_counts'], ensure_ascii=False),
        'Open verwerkingstaken: ' + str(report['formation_progress']['pending_task_count'])]
    for item in report['blockers']:
        lines.append(item['title'] + ' [' + str(item['code']) + ']')
    for action in report['follow_up']:
        value = action['observed_conditions_met']
        lines.append(action['action'] + ': ' + ('bekijk de openstaande reviewverplichtingen' if action['action'] == 'review_obligations' else 'gecontroleerde voorwaarden vastgelegd als voldaan' if value is True else
            'voorwaarden vastgelegd als niet voldaan' if value is False else 'niet gecontroleerd of verouderd'))
    lines += ['Ontbrekend bewijs: ' + ', '.join(report['missing_evidence']),
              'Identiteitsconflicten: ' + ', '.join(report['identity_conflicts'])]
    return '\n'.join(lines) + '\n'

"""A2: attempt records carry semantic contract version and explicit stop_reason;
global structured JSON logging without secrets.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import io
import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import expire_running, finish, reserve
from src.processing_trace_v1 import clean_trace, processing_trace, project_attempt

CONTRACT = 'source-accountability-v2/bounded-formation-v1/recoverable-formation-v1/x'
CLOCK = datetime(2026, 10, 15, tzinfo=timezone.utc)


def _envelope(provider_evidence=None, contract=CONTRACT):
    envelope = {'snapshot_id': 'snap-0123456789abcdef-01234567', 'sha256': 'a' * 64, 'version': '1'}
    if contract is not None:
        envelope['semantic_replay'] = {'identity': {'components': {'semantic_contract_version': contract}},
                                       'provider_evidence': provider_evidence or {}}
    attempt, created = reserve(envelope, command_id='cmd', actor_id='actor', revision='r1', clock=CLOCK)
    assert created
    return envelope, attempt['attempt_id']


BUDGET = {'formation_incomplete': True, 'error_code': 'source_task_budget_exhausted',
          'supplementary_calls': [{'error_code': 'source_task_budget_exhausted'}]}


def test_succeeded_complete_formation_records_done_and_contract_version():
    envelope, aid = _envelope({'formation_incomplete': False})
    stored = finish(envelope, aid, state='succeeded')
    assert stored['stop_reason'] == 'done'
    assert stored['semantic_contract_version'] == CONTRACT
    assert stored['state'] == 'succeeded'  # A2 records; A3 owns the state correction


def test_budget_exhausted_formation_records_budget_exhausted_without_changing_state():
    envelope, aid = _envelope(BUDGET)
    stored = finish(envelope, aid, state='succeeded')
    assert stored['stop_reason'] == 'budget_exhausted'
    assert stored['state'] == 'succeeded'


def test_incomplete_formation_without_budget_code_is_not_called_budget_exhausted():
    envelope, aid = _envelope({'formation_incomplete': True, 'error_code': 'source_task_provider_failed'})
    assert finish(envelope, aid, state='succeeded')['stop_reason'] == 'done'


def test_resume_that_completes_after_budget_history_is_done():
    history = dict(BUDGET, formation_incomplete=False)
    envelope, aid = _envelope(history)
    assert finish(envelope, aid, state='succeeded')['stop_reason'] == 'done'


def test_failed_attempt_records_error_and_never_a_stale_contract_version():
    envelope, aid = _envelope({'formation_incomplete': False})
    stored = finish(envelope, aid, state='failed', error=ConsoleError('processing_dependency_failed'))
    assert stored['stop_reason'] == 'error'
    assert stored['semantic_contract_version'] is None


def test_expired_attempt_records_error():
    envelope, aid = _envelope()
    expire_running(envelope, CLOCK + timedelta(days=1))
    attempt = envelope['processing_attempts'][-1]
    assert attempt['state'] == 'interrupted' and attempt['stop_reason'] == 'error'


def test_success_without_replay_identity_records_no_contract_version():
    envelope, aid = _envelope(contract=None)
    stored = finish(envelope, aid, state='succeeded')
    assert stored['semantic_contract_version'] is None and stored['stop_reason'] == 'done'


def test_trace_projects_stop_reason_and_contract_version_and_legacy_stays_none():
    envelope, aid = _envelope(BUDGET)
    finish(envelope, aid, state='succeeded')
    row = processing_trace(envelope)['attempts'][-1]
    assert row['stop_reason'] == 'budget_exhausted'
    assert row['semantic_contract_version'] == CONTRACT
    legacy = project_attempt({'attempt_id': 'pa_' + '0' * 32, 'state': 'succeeded'})
    assert legacy['stop_reason'] is None and legacy['semantic_contract_version'] is None  # no backfill
    hostile = project_attempt({'stop_reason': 'private text', 'semantic_contract_version': 'x' * 2000})
    assert hostile['stop_reason'] is None and hostile['semantic_contract_version'] is None
    exported = clean_trace(processing_trace(envelope))['attempts'][-1]
    assert exported['stop_reason'] == 'budget_exhausted'
    assert exported['semantic_contract_version'] == CONTRACT


# --- global structured JSON logging -----------------------------------------

def _capture(message, *args, exc=None, **extra):
    from src.structured_logging_v1 import JsonLogFormatter
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger('metis.test.structured')
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    if exc is not None:
        try:
            raise exc
        except Exception:
            logger.exception(message, *args, extra=extra)
    else:
        logger.warning(message, *args, extra=extra)
    return json.loads(stream.getvalue())


def test_json_log_record_has_fixed_fields():
    row = _capture('heading_batch_review_mirror_refresh_failed', request_id='r' * 32)
    assert row['level'] == 'WARNING' and row['logger'] == 'metis.test.structured'
    assert row['message'] == 'heading_batch_review_mirror_refresh_failed'
    assert row['timestamp'].endswith('Z')
    assert row['request_id'] == 'r' * 32
    assert 'commit' in row


@pytest.mark.parametrize('secret', [
    'Authorization: Bearer abc.def.ghi', 'password=hunter2', 'AccountKey=c2VjcmV0PT0=',
    'InstrumentationKey=00000000-0000-0000-0000-000000000001', 'api_key: sk-livesecret123456',
    'postgresql://user:pw@host/db', 'SharedAccessSignature=sig', 'client_secret=topsecret'])
def test_secrets_are_redacted_from_message_and_arguments(secret):
    row = _capture('read failed: %s', secret)
    serialized = json.dumps(row)
    for fragment in ('abc.def.ghi', 'hunter2', 'c2VjcmV0PT0', '00000000-0000-0000-0000-000000000001',
                     'sk-livesecret123456', 'user:pw', '=sig', 'topsecret'):
        assert fragment not in serialized
    assert '[REDACTED]' in row['message']


def test_exceptions_report_type_only_never_prose_or_traceback():
    row = _capture('operation failed', exc=ValueError('private payload password=x'))
    assert row['exc_type'] == 'ValueError'
    assert 'private payload' not in json.dumps(row) and 'Traceback' not in json.dumps(row)


def test_unknown_extra_fields_are_not_logged():
    row = _capture('event', request_id='ok', user_text='private clinical text')
    assert 'user_text' not in row and 'private' not in json.dumps(row)


def test_install_is_global_idempotent_and_keeps_diagnostics_logger():
    from src.request_diagnostics_v1 import _LOGGER
    from src.structured_logging_v1 import JsonLogFormatter, install_structured_logging
    root = logging.getLogger()
    before_handlers, before_level = list(root.handlers), root.level
    diagnostics_handlers = list(_LOGGER.handlers)
    try:
        install_structured_logging()
        install_structured_logging()
        mine = [h for h in root.handlers if isinstance(h.formatter, JsonLogFormatter)]
        assert len(mine) == 1
        assert root.level == logging.INFO
        assert _LOGGER.handlers == diagnostics_handlers  # metis_diagnostic format stays unchanged
    finally:
        root.handlers = before_handlers
        root.setLevel(before_level)


def test_console_entry_installs_structured_logging_first(monkeypatch):
    import src.console_asgi as entry
    calls = []
    monkeypatch.setattr(entry, 'install_structured_logging', lambda: calls.append('install'))

    def stop():
        calls.append('topology')
        raise RuntimeError('stop after install')

    monkeypatch.setattr(entry, 'assert_supported_topology', stop)
    with pytest.raises(RuntimeError, match='stop after install'):
        entry.build_app()
    assert calls == ['install', 'topology']

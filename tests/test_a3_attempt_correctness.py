"""A3: attempt correctness. Fail-first reproduction of two defects.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag stale retry version-compat recovery concurrent
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Rules (B18):
- A budget-exhausted attempt MOET NOOIT als 'succeeded' worden opgeslagen.
- 'Hervatten' MAG NIET worden aangeboden na een wijziging van de semantische
  contractversie.
"""
import pytest
from fastapi.testclient import TestClient

from src.bounded_model_call_v1 import ModelCallLimits
from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.processing_retry_v1 import finish, now, reserve, status
from tests.test_recoverable_formation_v1 import system

BUDGET_REPLAY = {'identity': {'components': {'semantic_contract_version': 'contract-x'}},
                 'provider_evidence': {'formation_incomplete': True, 'error_code': 'source_task_budget_exhausted',
                                       'supplementary_calls': [{'error_code': 'source_task_budget_exhausted'}]}}


def _envelope():
    return {'sha256': 'a' * 64, 'version': '1.0', 'publication_eligibility': PRE_REVIEW_BLOCKED,
            'semantic_replay': BUDGET_REPLAY}


# --- defect 1: budget exhaustion stored as succeeded -------------------------

@pytest.mark.parametrize('kind', ['retry', 'resume'])
def test_budget_exhausted_attempt_is_never_stored_as_succeeded(kind):
    # The cleared execution path (operations_console_v1 _execute_source_attempt) finishes budget-aware.
    envelope = _envelope()
    attempt, fresh = reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now(), kind=kind)
    assert fresh
    stored = finish(envelope, attempt['attempt_id'], state='succeeded', budget_aware=True)
    assert stored['state'] != 'succeeded', 'BUDGET_EXHAUSTED_STORED_AS_SUCCEEDED'
    assert stored['state'] == 'incomplete_budget'
    assert status(envelope)['stored_state'] == 'incomplete_budget'


def test_ingest_path_budget_exhaustion_is_never_succeeded():
    import inspect
    from src.operations_console_v1 import OperationsConsole
    source = inspect.getsource(OperationsConsole.ingest)
    assert 'finish(envelope, attempt_id, state="succeeded", budget_aware=True)' in source


def test_reextract_execution_path_finishes_budget_aware():
    import inspect
    from src.operations_console_v1 import OperationsConsole
    source = inspect.getsource(OperationsConsole.reextract_unpublished)
    assert 'state="succeeded", budget_aware=True' in source


def test_complete_formation_still_succeeds():
    envelope = _envelope()
    envelope['semantic_replay'] = {'provider_evidence': {'formation_incomplete': False}}
    attempt, _ = reserve(envelope, command_id='c', actor_id='a', revision='r', clock=now(), kind='resume')
    assert finish(envelope, attempt['attempt_id'], state='succeeded', budget_aware=True)['state'] == 'succeeded'


def test_incomplete_budget_never_counts_against_retry_cap():
    envelope = _envelope()
    limits = ModelCallLimits(max_attempts=2)
    for index in range(5):
        attempt, fresh = reserve(envelope, command_id=f'b{index}', actor_id='a', revision='r',
                                 clock=now(), limits=limits, kind='resume')
        assert fresh
        attempt['formation_progress_made'] = False  # even without progress
        finish(envelope, attempt['attempt_id'], state='succeeded', budget_aware=True)
    current = status(envelope, policy=limits)
    assert current['retry_attempts_used'] == 0
    assert current['reason_code'] != 'processing_attempt_limit_reached'


def test_budget_exhausted_resume_with_progress_does_not_consume_retry_budget():
    # Guard: the correction MAG NIET turn normal bounded continuation into failures.
    envelope = _envelope()
    limits = ModelCallLimits(max_attempts=2)
    for index in range(4):
        attempt, fresh = reserve(envelope, command_id=f'r{index}', actor_id='a', revision='r',
                                 clock=now(), limits=limits, kind='resume')
        assert fresh
        attempt['formation_progress_made'] = True
        finish(envelope, attempt['attempt_id'], state='succeeded', budget_aware=True)
    assert status(envelope, policy=limits)['reason_code'] != 'processing_attempt_limit_reached'


# --- defect 2: 'Hervatten' offered after a contract-version change ----------

@pytest.fixture
def changed_contract(tmp_path, monkeypatch):
    state, sid, actor, *_ = system(tmp_path)
    assert state.processing_status(sid)['resume_allowed']  # resumable under the stored contract
    import src.pre_review_semantic_v1 as semantic
    monkeypatch.setattr(semantic, 'STRENGTH_BINDING_VERSION', 'recommendation-strength-binding-v999')
    return state, sid, actor


def test_kernel_does_not_allow_resume_after_contract_change(changed_contract):
    state, sid, _ = changed_contract
    assert not state.processing_status(sid)['resume_allowed'], 'RESUME_OFFERED_AFTER_CONTRACT_CHANGE'


def test_resume_command_is_rejected_after_contract_change(changed_contract):
    state, sid, actor = changed_contract
    with pytest.raises(ConsoleError, match='processing_resume_configuration_incompatible'):
        state.resume_formation(actor_id=actor, snapshot_id=sid, command_id='after-change',
                               expected_revision=state.objects_revision(sid))


def test_source_selection_page_does_not_offer_hervatten_after_contract_change(changed_contract):
    from tests.test_availability_repair import installed_app
    state, sid, _ = changed_contract
    app = installed_app(state)
    with TestClient(app, base_url='https://testserver') as client:
        assert client.post('/login', data={'username': 'author', 'password': 'strong-test-password'},
                           follow_redirects=False).status_code == 303
        page = client.get('/source-selection', params={'document': sid}).text
    assert '<button class="btn-primary">Hervatten</button>' not in page, 'HERVATTEN_OFFERED_AFTER_CONTRACT_CHANGE'


def test_concurrent_resumes_after_contract_change_are_all_rejected_before_work(changed_contract):
    from concurrent.futures import ThreadPoolExecutor
    state, sid, actor = changed_contract
    before = list(state._envelope(sid)['processing_attempts'])
    revision = state.objects_revision(sid)

    def attempt(i):
        try:
            state.resume_formation(actor_id=actor, snapshot_id=sid, command_id=f'c{i}', expected_revision=revision)
        except ConsoleError as error:
            return error.code
    with ThreadPoolExecutor(4) as pool:
        codes = list(pool.map(attempt, range(4)))
    assert codes == ['processing_resume_configuration_incompatible'] * 4
    assert state._envelope(sid)['processing_attempts'] == before

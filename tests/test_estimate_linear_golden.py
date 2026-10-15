"""PR-b: estimate is computed from observations built once per request.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Rules (B18):
- De uitkomst van `estimate` MOET identiek zijn aan de oude per-document-lus (golden).
- De Bronselectie-lijst MOET de attempts van alle documenten één keer per verzoek
  doorlopen, NOOIT één keer per document.
"""
import random
from datetime import datetime, timedelta, timezone
from statistics import median

import pytest

import src.source_selection_v1 as selection
from src.source_selection_v1 import _duration, comparable_observations, estimate


def legacy_estimate(envelope, documents):
    """Verbatim copy of estimate on main 7d084fa (golden reference)."""
    size = (envelope.get("received_source") or {}).get("bytes")
    rates = []
    for prior in documents:
        prior_size = (prior.get("received_source") or {}).get("bytes")
        if not size or not prior_size or not .5 <= prior_size / size <= 2:
            continue
        if (prior.get("content_kind"), prior.get("class")) != (envelope.get("content_kind"), envelope.get("class")):
            continue
        for attempt in prior.get("processing_attempts", []):
            if attempt.get("state") != "succeeded" or attempt.get("kind") != "ingest":
                continue
            if prior.get("processing_configuration") != envelope.get("processing_configuration"):
                continue
            if prior.get("semantic_replay", {}).get("provider_evidence", {}).get("formation_incomplete"):
                continue
            elapsed = _duration(attempt.get("started_at"), attempt.get("finished_at"))
            if elapsed and elapsed >= 1:
                rates.append(elapsed / prior_size)
    if len(rates) < 3:
        return {"range_seconds": None, "sample_count": len(rates), "basis": "Onvoldoende vergelijkbare metingen."}
    central = median(rates) * size
    return {"range_seconds": [min(min(rates) * size, central * .5), max(max(rates) * size, central * 2)],
            "sample_count": len(rates), "basis": "Grove bandbreedte uit volledige eerdere pogingen en bestandsgrootte; broncomplexiteit kan afwijken."}


T0 = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def _corpus(seed, n=60):
    rnd = random.Random(seed)
    configs = [{'mode': 'v3', 'model': 'a'}, {'mode': 'v3', 'model': 'b'}, None]
    docs = []
    for i in range(n):
        size = rnd.choice([None, 0, 500, 999, 1000, 1001, 2000, 2001, 4000, rnd.randint(1, 5000)])
        attempts = []
        for _ in range(rnd.randint(0, 4)):
            start = T0 + timedelta(seconds=rnd.randint(0, 999))
            attempts.append({'state': rnd.choice(['succeeded', 'failed', 'incomplete_budget', 'running']),
                             'kind': rnd.choice(['ingest', 'ingest', 'resume', 'retry']),
                             'started_at': start.isoformat(),
                             'finished_at': rnd.choice([None, 'bad', (start + timedelta(seconds=rnd.choice([0, 0.5, 1, 30, 400]))).isoformat()])})
        doc = {'snapshot_id': f's{i}', 'content_kind': rnd.choice(['html', 'pdf']), 'class': rnd.choice(['richtlijn', 'beslisboom']),
               'received_source': {'bytes': size} if size is not None else {}, 'processing_attempts': attempts,
               'processing_configuration': rnd.choice(configs)}
        if rnd.random() < .2:
            doc['semantic_replay'] = {'provider_evidence': {'formation_incomplete': rnd.random() < .5}}
        docs.append(doc)
    return docs, configs


@pytest.mark.parametrize('seed', range(25))
def test_estimate_golden_identical_to_legacy(seed):
    docs, configs = _corpus(seed)
    observations = comparable_observations(docs)
    for env in docs:
        for config in configs:
            probe = {**env, 'processing_configuration': config}
            expected = legacy_estimate(probe, docs)
            assert estimate(probe, docs) == expected
            assert estimate(probe, docs, observations=observations) == expected


def test_boundary_ratios_are_identical():
    cfg = {'mode': 'v3'}
    env = {'content_kind': 'html', 'class': 'richtlijn', 'received_source': {'bytes': 1000}, 'processing_configuration': cfg}
    docs = [{**env, 'received_source': {'bytes': b}, 'processing_attempts': [{'state': 'succeeded', 'kind': 'ingest',
             'started_at': T0.isoformat(), 'finished_at': (T0 + timedelta(seconds=100)).isoformat()}]}
            for b in (499, 500, 2000, 2001, 1000)]
    assert estimate(env, docs) == legacy_estimate(env, docs)
    assert estimate(env, docs)['sample_count'] == 3


def test_source_selection_list_reads_attempts_once_per_request(tmp_path, monkeypatch):
    """Fail-first: the old route scanned every document's attempts once per listed document."""
    from fastapi.testclient import TestClient
    from tests.test_recoverable_formation_v1 import system
    console, sid, author, reviewer, *_ = system(tmp_path)
    envelopes = [console._envelope(sid)]
    from src.operations_console_app import create_console_app
    app = create_console_app(console)
    calls = []
    real = selection.comparable_observations
    monkeypatch.setattr(selection, 'comparable_observations', lambda docs: calls.append(len(docs)) or real(docs))
    import src.source_selection_ui_v1 as ui
    monkeypatch.setattr(ui, 'comparable_observations', selection.comparable_observations, raising=False)
    client = TestClient(app)
    client.post('/login', data={'username': 'author', 'password': 'strong-test-password'})
    page = client.get('/source-selection')
    assert page.status_code == 200
    assert len(calls) == 1, calls

"""C2 (Sherlock 02:55 on #639): one pinned-configuration check at the top of build_formation_context.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag stale retry version-compat
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Rules (B18):
- The check MOET run before every early return (non-HTML/PDF, beslisboom) and before extraction.
- A pinned configuration that differs from the active one MOET give processing_configuration_changed.
- An attempt without a pinned configuration MOET be refused with processing_configuration_unpinned; there is NOOIT an exemption.
- On refusal the extractor MAG NIET be called (exact counter 0).
"""
import time
from copy import deepcopy

import pytest

import src.source_selection_v1 as selection
from src.operations_console_v1 import ConsoleError
from src.source_preparation_context_v1 import build_formation_context
from tests.test_resv1_reservation_configuration import _reextract_ready


def _setup(tmp_path, *, production_console):
    console, sid, actor = _reextract_ready(tmp_path, production_console=production_console)
    envelope = deepcopy(console._envelope(sid))
    attempt = deepcopy(envelope['processing_attempts'][-1])
    assert attempt.get('processing_configuration'), 'fixture MOET have a pinned attempt'
    extracted = {'n': 0}
    real_extract = console._extract

    def sentinel(*args, **kwargs):
        extracted['n'] += 1
        return real_extract(*args, **kwargs)
    console._extract = sentinel
    return console, envelope, attempt, actor, extracted


def _build(console, envelope, attempt, actor):
    return build_formation_context(console, envelope=envelope, actor_id=actor,
        expected_revision=attempt['expected_revision'], attempt=attempt,
        deadline=time.monotonic() + 60)


def _variant(envelope, variant):
    if variant == 'beslisboom':
        envelope['class'] = 'beslisboom'
    elif variant == 'non_html_pdf':
        envelope['content_kind'] = 'docx'
    return envelope


@pytest.mark.parametrize('variant', ['html', 'beslisboom', 'non_html_pdf'])
def test_changed_configuration_refused_before_every_return(tmp_path, variant, *, production_console):
    console, envelope, attempt, actor, extracted = _setup(tmp_path, production_console=production_console)
    attempt['processing_configuration'] = {**attempt['processing_configuration'], 'mode': 'deployed-mid-flight'}
    with pytest.raises(ConsoleError, match='^processing_configuration_changed$'):
        _build(console, _variant(envelope, variant), attempt, actor)
    assert extracted['n'] == 0


@pytest.mark.parametrize('variant', ['html', 'beslisboom', 'non_html_pdf'])
def test_unpinned_attempt_refused_fail_closed(tmp_path, variant, *, production_console):
    console, envelope, attempt, actor, extracted = _setup(tmp_path, production_console=production_console)
    attempt.pop('processing_configuration')
    with pytest.raises(ConsoleError, match='^processing_configuration_unpinned$'):
        _build(console, _variant(envelope, variant), attempt, actor)
    assert extracted['n'] == 0


def test_empty_pinned_configuration_is_unpinned(tmp_path, *, production_console):
    console, envelope, attempt, actor, extracted = _setup(tmp_path, production_console=production_console)
    attempt['processing_configuration'] = {}
    with pytest.raises(ConsoleError, match='^processing_configuration_unpinned$'):
        _build(console, envelope, attempt, actor)
    assert extracted['n'] == 0


def test_matching_pinned_configuration_passes_the_check(tmp_path, *, production_console):
    console, envelope, attempt, actor, extracted = _setup(tmp_path, production_console=production_console)
    assert attempt['processing_configuration'] == selection.configuration(console)
    context = _build(console, envelope, attempt, actor)
    assert context['snapshot_id'] == envelope['snapshot_id']

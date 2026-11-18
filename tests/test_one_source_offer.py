"""# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.human_annotation_passage_offer import bind, window


def test_source_window_respects_contiguous_section():
    blocks = [dict(block_id=str(i), text='voorbeeld', section_path=[s])
              for i,s in enumerate(['A','B','B','A'])]
    assert [b['block_id'] for b in window({'blocks':blocks}, '2')] == ['1','2']


@pytest.mark.parametrize('quote,covered', [('anders',[]),('zorg',[]),
    ('verbetering',[dict(block_id='b',start=0,end=11)])])
def test_refuse_invented_ambiguous_or_already_covered_core(quote,covered):
    blocks=[dict(block_id='b',start=0,text='verbetering zorg zorg')]
    with pytest.raises(ConsoleError):
        bind({'ranges':[dict(block_id='b',role='core',quote=quote)]},blocks,covered)


@pytest.mark.parametrize('case', ['before','during','outsider'])
def test_offer_rechecks_authority_without_writing(production_console, tmp_path, monkeypatch, case):
    from uuid import uuid4
    from src.vorming import human_annotation_passage_offer as offers
    from tests.test_annotation_suggestions import setup, configure, provider, annotation

    console, actor, _, sid, view, cmd, prior = setup(production_console, tmp_path)
    configure(monkeypatch)
    request = dict(snapshot_id=sid, basis=prior['basis'], focus=None)
    calls = []

    def change_source_generation():
        cmd.update(command_id=str(uuid4()), expected_revision=1, expected_generation=view['generation'])
        annotation.save(console, actor_id=actor, **cmd)

    def transport(*args):
        calls.append(True)
        if case == 'during':
            change_source_generation()
        return provider({'ranges': []})

    monkeypatch.setattr(offers.meaning,'logged_post_json',transport)
    if case == 'before':
        change_source_generation()
    requester = actor if case != 'outsider' else console.create_account(
        username='outsider',password='test-secret',roles=('reviewer',))['account_id']
    with pytest.raises(ConsoleError):
        offers.suggest(console, actor_id=requester, request=request)
    assert len(calls) == (1 if case == 'during' else 0)
    entries = annotation.overview(console, actor_id=actor, snapshot_id=sid)['entries']
    assert len(entries) == 1 and entries[0]['revision'] == (1 if case == 'outsider' else 2)

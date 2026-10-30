"""B6 (#933): closed whole-range non-knowledge rules for source accountability.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

import pytest

from src.vorming.source_containers_v1 import accounting_reason, metadata_reason


@pytest.mark.parametrize("text,reason", [
    ("Literatuurconclusies    ................................ ......................    35", "navigation"),
    ("Rationale ................................ ................................", "navigation"),
    ("Module 3: Diagnostiek    ................................ ................................", "navigation"),
    (".......    44", "navigation"),
    ("................................ ...    25", "navigation"),
    ("Conceptrichtlijn Voorbeeld – commentaarronde juli 2026", "page_furniture"),
    ("Jansen, A. B., & Pietersen, C. (2019). Huidzorg bij ouderen: een overzicht. Tijdschrift, 12(3), 1-9. https://doi.org/10.1000/abc",
     "document_metadata"),
    ("(PDF) Voorbeeld, Q. (2021). Een titel over huidplooien. Blad , 30(1), 102–107. https://doi.org/10.1000/xyz", "document_metadata"),
    ("Al - Voorbeeld, N. (2011). Een titel. Tijdschrift, 3(2), 1-9. https://doi.org/10.1000/abc", "document_metadata"),
    ("Eerste, I. H. J., Tweede, J., van der Derde, J. C. M., & Vierde, K. (2021). Titel. Blad, 7, 112-118. https://doi.org/10.1000/abc", "document_metadata"),
    ("Jansen, A., et al. (2020). Titel met et al. Tijdschrift, 4(1). https://doi.org/10.1000/abc", "document_metadata"),
    ("Eerste, A. (2011). Titel een. Blad , 38(4), 359 – 370. https://doi.org/10.1000/a, "
     "del Tweede - Derde, M., & Vierde, I. (2021). Titel twee: een studie. Blad , 63 . https://doi.org/10.1000/b",
     "document_metadata"),
    ("De Vries, K. (n.d.). Een titel zonder jaar. Blad , 143 . https://doi.org/10.1000/abc", "document_metadata"),
    ("Bronnen: (Voorbeeld et al., 2022)", "document_metadata"),
    ("Bronnen: (Voorbeeld & Tweede, 2019; van Derde, 2020a)", "document_metadata"),
    ("Zie bijlage 3.4", "navigation"),
    ("Module 3: Diagnostiek    ................................ ........", "navigation"),
    ("Conceptrichtlijn Voorbeeld – commentaarronde juli 2026    Implementatietabel ..........", "navigation"),
    ("· Mw. Anna Bout - Voorbeeld , Verpleegkundige, namens V&VN", "document_metadata"),
    ("· Mw. Alma Voorbeeld-van Dijk, Verpleegkundige, namens V&VN Wondexpertise", "document_metadata"),
    ("· Mw. Eva Voorbeeld, Ergotherapeut , namens Ergotherapie Nederland (EN)", "document_metadata"),
    ("· Mw. Eva Voorbeeld, dermatoloog, namens de Nederlandse Vereniging voor Dermatologie en Venerologie",
     "document_metadata"),
    ("· Mw. Eva Voorbeeld, Verpleegkundige, namens V&VN Geriatrie & Gerontologie", "document_metadata"),
    ("· Mw. Eva Voorbeeld, Wondconsulent in de intra- en extramurale zorg, namens V&VN Wondexpertise",
     "document_metadata"),
    ("· Mw. Eva Voorbeeld, Specialist Ouderengeneeskunde , namens Verenso", "document_metadata"),
    ("Zie Bijlage 2", "navigation"),
    ("· Mw. Anna Voorbeeld, Verpleegkundige in een ziekenhuis, namens V&VN Wondexpertise", "document_metadata"),
])
def test_closed_non_knowledge_rules_account_the_whole_passage(text, reason):
    assert accounting_reason(text) == reason


@pytest.mark.parametrize("text", [
    # Clinical sentences that resemble a rule must stay human/reviewer work.
    "Gebruik geen zalf in de huidplooi...",
    "Breng zinkzalf aan op de aangedane huid: ........",
    "Naam patiënt: ..................................................",
    "Gebruik zinkzalf. ....................................",
    "Breng zinkzalf dagelijks aan ............................................................",
    "Mw. Jansen. Gebruik dagelijks zinkzalf, verpleegkundige, namens V&VN",
    "Mw. Jansen, verpleegkundige, namens V&VN adviseert dagelijks zinkzalf",
    "Mw. Jansen, adviseert dagelijks zinkzalf, namens V&VN",
    "Jansen, A. (2019). Gebruik dagelijks zinkzalf op de aangedane huid.",
    "Jansen, A. (2019). Gebruik geen zalf. https://voorbeeld.nl",
    "Jansen, A. (2019). Behandel huidplooien gedurende week 1, 2.",
    "Jansen, A. (2019). Gebruik geen zalf. Daarna, 2.",
    "Jansen, A. (2019). Gebruik zinkzalf. Week, 2, 3-4.",
    "Jansen, A. (2019). Huidzorg bij ouderen. Gebruik geen zinkzalf. Tijdschrift, 12, 1-9. https://doi.org/10.1000/abc",
    "Jansen, A. (2019). Huidzorg? Gebruik geen zinkzalf. Tijdschrift, 12, 1-9. https://doi.org/10.1000/abc",
    "Jansen, A. (2019). Huidzorg! Gebruik geen zinkzalf. Tijdschrift, 12, 1-9. https://doi.org/10.1000/abc",
    "Jansen, A. (2019). Huidzorg; gebruik geen zinkzalf. Tijdschrift, 12, 1-9. https://doi.org/10.1000/abc",
    "Mw. Jansen, Verpleegkundige, namens V&VN Gebruik Geen Zinkzalf",
    "Jansen, A. (2019). Gebruik geen zalf. https://doi.org/10.1000/xyz",
    "Jansen, A. (2019). Gebruik zinkzalf 2-3 keer per dag op de aangedane huid.",
    "Bronnen: (gebruik dagelijks zinkzalf bij natte plekken, 2019)",
    "Richtlijn: gebruik geen zinkzalf. Zie module 3 – commentaarronde juli 2026",
    "Mw. Jansen, verpleegkundige in de wond dagelijks zinkzalf, namens V&VN",
    "Controleer de huidplooien dagelijks (Jansen, 2019).",
    "Jansen, A. (2019) beschrijft dat drooghouden smetten voorkomt.",
    "Jansen, A. adviseert de huid dagelijks droog te houden (2019). Dit voorkomt smetten.",
    "Pietersen, B. C. raadt zinkzalf af bij natte plekken (n.d.). Gebruik indifferente crème.",
    "Zie bijlage 3.4 voor de dosering; start pas na overleg met de arts.",
    "Raadpleeg bij twijfel de arts. Zie bijlage 2.",
    "Mw. Jansen, 80 jaar, heeft smetten in de liesplooi.",
    "· Mw. Jansen, verpleegkundige, adviseert dagelijks drooghouden.",
    "Mevr. Jansen, verpleegkundige, adviseert namens de werkgroep dagelijks zinkzalf.",
    "Mw. Jansen, verpleegkundige, namens de werkgroep: gebruik geen zinkzalf",
    "Mw. Jansen, verpleegkundige, namens V&VN. Gebruik geen zinkzalf.",
    "Conceptrichtlijn: gebruik geen zinkzalf bij een natte smetplek.",
    "22",
    "Bronnen van vocht, zoals transpiratie (2019), verhogen het risico.",
])
def test_clinical_or_mixed_text_is_never_machine_accounted(text):
    assert accounting_reason(text) is None


def _remainder(text):
    from src.vorming.passage_register_v1 import apply_passage_register
    from tests.test_recommendation_context_v3 import prepare, source
    fragments = source("Gebruik geen zalf")
    fragments.append({**source(text)[0], "fragment_id": "rest", "fragment_hash": "rest-hash"})
    _, rows, _, _ = prepare("Gebruik geen zalf", fragments=fragments)
    return apply_passage_register(rows)


def test_reference_remainder_is_accounted_without_human_disposition():
    from src.publication.publication_readiness_v1 import source_passage_closure
    from src.vorming.source_containers_v1 import partition
    rows = _remainder("Jansen, A. B. (2019). Huidzorg bij ouderen. Tijdschrift, 12, 1-9. https://doi.org/10.1000/abc")
    record = next(r for r in partition(rows)["source"]
                  if r["record"]["content"]["clean_text"].startswith("Jansen"))
    usage = record["usage"]
    assert usage["accounted"] and usage["human_action"] == "none"
    assert usage["reason"] == "document_metadata"
    # The recommendation itself still awaits review; only the reference is closed.
    assert record["record"]["object_id"] not in source_passage_closure(rows)["unresolved_source_passage_ids"]


def test_clinical_remainder_still_needs_human_disposition():
    from src.vorming.source_containers_v1 import partition
    rows = _remainder("Bij kinderen geldt ander beleid.")
    usage = next(r["usage"] for r in partition(rows)["source"]
                 if r["record"]["content"]["clean_text"].startswith("Bij kinderen"))
    assert not usage["accounted"] and usage["human_action"] == "source_disposition"


@pytest.mark.parametrize("text", [
    "Jansen, A. B. (2019). Huidzorg bij ouderen. Tijdschrift.",
    "Zie bijlage 3.4",
    "· Mw. Anna Voorbeeld, Verpleegkundige, namens Voorbeeldvereniging",
])
def test_formation_planning_rules_are_unchanged(text):
    # Accountability only: formation keeps sending these blocks to the model.
    assert metadata_reason(text) is None


@pytest.mark.parametrize("extra,closed", [
    ("Jansen, A. B. (2019). Huidzorg bij ouderen. Tijdschrift, 12, 1-9. https://doi.org/10.1000/abc", True),
    ("Bij kinderen geldt ander beleid.", False),
])
def test_readiness_blocker_follows_closed_rule_through_the_console(extra, closed, tmp_path, *, production_console):
    """Black box: ingest -> containers -> publication readiness, no direct registry calls."""
    from src.publication.publication_readiness_v1 import SOURCE_PASSAGE_REVIEW_INCOMPLETE
    from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from tests.test_recommendation_context_v3 import response_for
    def make():
        return production_console(processing_binder=lambda console: None, root=tmp_path,
                                  source_store=tmp_path / 'sources', runtime=tmp_path / 'runtime')
    state = make()
    author = state.create_account(username='author', password='strong-test-password', roles=('researcher',))
    reviewer = state.create_account(username='reviewer', password='strong-test-password', roles=('reviewer',))

    def provider(_url, _headers, payload, _timeout):
        blocks = json.loads(payload['input'][1]['content'])['source_blocks']
        answer = (response_for(payload, 'Gebruik geen zalf')
                  if any('Gebruik geen zalf' in b['text'] for b in blocks)
                  else {'objects': [], 'relations': [], 'abstain_reason': 'uncertain'})
        return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(answer)}]}]}
    bind_pre_review_semantic_processing(state, environ={'METIS_PASSAGE_FORMATION_MODE': 'semantic-source-bound-v3',
        'METIS_LLM_API_KEY': 'fixture', 'METIS_LLM_MODEL': 'fixture'}, post_json=provider)
    html = f'<html><body><h1>Aanbevelingen</h1><p>Gebruik geen zalf</p><p>{extra}</p></body></html>'
    sid = state.ingest(actor_id=author['account_id'], filename='source.html', data=html.encode(),
        content_type='text/html', ingest_kind='new', title='Test', version='1', date='2026-10-05', live_url='',
        class_='richtlijn', family='test', named_reviewers=[reviewer['account_id']])['snapshot_id']
    source = state.snapshot_containers(sid)['source']
    assert [r['record']['content']['clean_text'] for r in source] == [extra]
    source_id = source[0]['record']['object_id']
    readiness = state.publication_readiness(sid)
    # Derived at read time, so a restarted console gives the same projection.
    assert make().publication_readiness(sid)['unresolved_source_passage_ids'] == readiness['unresolved_source_passage_ids']
    # Readiness is the publication authority; the reference no longer holds the
    # source-passage blocker open, a clinical remainder still does.
    assert (source_id not in readiness['unresolved_source_passage_ids']) is closed
    assert (source_id not in readiness['source_disposition_object_ids']) is closed
    assert SOURCE_PASSAGE_REVIEW_INCOMPLETE in readiness['curation_blockers']  # The recommendation awaits review.

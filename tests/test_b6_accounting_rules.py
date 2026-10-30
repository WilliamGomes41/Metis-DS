"""B6 (#933): closed whole-range non-knowledge rules for source accountability.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from src.vorming.source_containers_v1 import accounting_reason, metadata_reason


@pytest.mark.parametrize("text,reason", [
    ("Literatuurconclusies    ................................ ......................    35", "navigation"),
    ("Module 3: Diagnostiek    ................................ ................................", "navigation"),
    (".......    44", "navigation"),
    ("Conceptrichtlijn Voorbeeld – commentaarronde juli 2026", "page_furniture"),
    ("Jansen, A. B., & Pietersen, C. (2019). Huidzorg bij ouderen: een overzicht. Tijdschrift, 12(3), 1-9.",
     "document_metadata"),
    ("(PDF) Voorbeeld, Q. (2021). Een titel over huidplooien. Uitgever.", "document_metadata"),
    ("Al - Voorbeeld, N. (2011). Een titel. Tijdschrift, 3(2), 1-9.", "document_metadata"),
    ("Eerste, I. H. J., Tweede, J., van der Derde, J. C. M., & Vierde, K. (2021). Titel. Blad.", "document_metadata"),
    ("Jansen, A., et al. (2020). Titel met et al. Uitgever.", "document_metadata"),
    ("De Vries, K. (n.d.). Een titel zonder jaar. Uitgever.", "document_metadata"),
    ("Bronnen: (Voorbeeld et al., 2022)", "document_metadata"),
    ("Zie bijlage 3.4", "navigation"),
    ("Zie Bijlage 2", "navigation"),
    ("· Mw. Anna Voorbeeld, Verpleegkundige in een ziekenhuis, namens Voorbeeldvereniging", "document_metadata"),
])
def test_closed_non_knowledge_rules_account_the_whole_passage(text, reason):
    assert accounting_reason(text) == reason


@pytest.mark.parametrize("text", [
    # Clinical sentences that resemble a rule must stay human/reviewer work.
    "Gebruik geen zalf in de huidplooi...",
    "Controleer de huidplooien dagelijks (Jansen, 2019).",
    "Jansen, A. (2019) beschrijft dat drooghouden smetten voorkomt.",
    "Jansen, A. adviseert de huid dagelijks droog te houden (2019). Dit voorkomt smetten.",
    "Pietersen, B. C. raadt zinkzalf af bij natte plekken (n.d.). Gebruik indifferente crème.",
    "Zie bijlage 3.4 voor de dosering; start pas na overleg met de arts.",
    "Raadpleeg bij twijfel de arts. Zie bijlage 2.",
    "Mw. Jansen, 80 jaar, heeft smetten in de liesplooi.",
    "· Mw. Jansen, verpleegkundige, adviseert dagelijks drooghouden.",
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
    rows = _remainder("Jansen, A. B. (2019). Huidzorg bij ouderen. Tijdschrift, 12, 1-9.")
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

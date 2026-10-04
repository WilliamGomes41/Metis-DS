"""Smetten diagnosis: unselected source text must not become open curator work.

Red on origin/main: 'Versie: 1' (front matter the semantic proposer did not
select) is stamped not_yet_assessed, lands in the disposition task and blocks
source-passage closure. Green: it is recorded with an explicit extract reason,
while recommendation-section remainders and real candidates are unchanged.
"""
from __future__ import annotations

from src.passage_register_v1 import apply_passage_register, apply_register_from_review
from src.publication_readiness_v1 import review_followup_queues, source_passage_closure
from src.review_disposition_v1 import definitive_review_disposition
from src.review_duty_v1 import review_duty_for

COVERAGE_REMAINDER_OUTSIDE_RECOMMENDATIONS = "coverage_remainder_outside_recommendation_section"
DOC = "console-smetten-richtlijn-smetten-1-0-62dfd76e"
REC_PATH = ["Smetten", "Module 1: Risicofactoren", "Aanbevelingen"]


def _obj(object_id, text, path, *, origin=None, object_type="unclassified", admission=None, proposed=None):
    metadata = {}
    if origin:
        metadata["semantic_passage"] = {"selection_origin": origin, "source_bound": True, "spans": []}
    if admission:
        metadata["admission"] = admission
    row = {
        "object_id": f"{DOC}-{object_id}",
        "object_version": "1.0",
        "object_type": object_type,
        "content": {"clean_text": text},
        "structure": {"section_path": path, "heading": None},
        "governance": {"validation_status": "needs_review"},
        "metadata": metadata,
    }
    if proposed:
        row["proposed_object_type"] = proposed
    return row


def _smetten_objects():
    return [
        {"object_id": f"{DOC}-document", "object_type": "document", "object_version": "1.0"},
        _obj("p001-f002", "Smetten", ["Smetten"], object_type="heading"),
        _obj("semcov-d688d23251b9ef1f", "Versie: 1", ["Smetten"], origin="coverage_remainder"),
        _obj("semcov-overweging", "Er wordt een sterke aanbeveling geformuleerd ...",
             ["Smetten", "Module 1: Risicofactoren", "Van bewijs naar aanbeveling (overwegingen)"],
             origin="coverage_remainder"),
        _obj("semcov-risk-list", "De risicofactoren zijn:", REC_PATH, origin="coverage_remainder"),
        _obj("sem-af6336104011fc04",
             "Breng bij iedere patiënt de risicofactoren voor smetten in kaart, om te bepalen of preventieve maatregelen nodig zijn.",
             REC_PATH, origin="proposal_selected", proposed="recommendation",
             admission={"gate_result": "allowed", "reason_codes": [], "section_path": REC_PATH,
                        "proposed_type": "recommendation"}),
    ]


def _by_text(objects):
    return {str((o.get("content") or {}).get("clean_text") or o["object_id"]): o for o in objects}


def test_versie_1_is_recorded_with_reason_not_open_curator_work():
    objects = apply_passage_register(_smetten_objects())
    versie = _by_text(objects)["Versie: 1"]
    register = versie["metadata"]["passage_register"]
    assert register["status"] == "excluded_with_reason"
    assert register["reason_codes"] == [COVERAGE_REMAINDER_OUTSIDE_RECOMMENDATIONS]
    assert register["source"] == "extract"
    assert definitive_review_disposition(versie)["final"] is True
    queues = review_followup_queues(objects, review_path="richtlijn", bindings=[])
    assert versie["object_id"] not in {o["object_id"] for o in queues["disposition"]}
    assert versie["object_id"] not in source_passage_closure(objects)["unresolved_source_passage_ids"]


def test_recommendation_section_remainder_and_candidate_are_unchanged():
    objects = _by_text(apply_passage_register(_smetten_objects()))
    remainder = objects["De risicofactoren zijn:"]
    assert remainder["metadata"]["passage_register"]["status"] == "not_yet_assessed"
    recommendation = next(o for t, o in objects.items() if t.startswith("Breng bij iedere"))
    assert recommendation["metadata"]["passage_register"]["status"] == "selected_as_candidate"
    duty = review_duty_for(recommendation, review_path="richtlijn", bindings=[])
    assert duty and duty["lane"] == "contextual" and duty["stage"] == "first_review"


def test_document_without_recommendation_sections_keeps_remainders_open():
    rows = [o for o in _smetten_objects() if o.get("structure", {}).get("section_path") != REC_PATH]
    objects = _by_text(apply_passage_register(rows))
    assert objects["Versie: 1"]["metadata"]["passage_register"]["status"] == "not_yet_assessed"


def test_human_review_disposition_overrides_extract_reason():
    objects = apply_passage_register(_smetten_objects())
    versie = _by_text(objects)["Versie: 1"]
    reviewed = apply_register_from_review(versie, suitability="alleen_onderbouwing")
    again = _by_text(apply_passage_register([o if o is not versie else reviewed for o in objects]))
    assert again["Versie: 1"]["metadata"]["passage_register"]["status"] == "linked_as_support"
    assert again["Versie: 1"]["metadata"]["passage_register"]["source"] == "review"


def test_table_cells_after_caption_are_not_recommendation_targets():
    """Smetten Tabel 1 row labels were forced on the model as recommendations."""
    from src.recommendation_coverage_v1 import inventory

    path = ["Smetten", "Module 2: Preventieve maatregelen", "Aanbevelingen"]
    blocks = [
        {"block_id": "b1", "section_path": path, "text": "1. Overweeg (een combinatie van) de volgende preventieve maatregelen [zie Tabel 1] toe te passen bij patiënten met een verhoogd risico op smetten."},
        {"block_id": "b2", "section_path": path, "text": "Zwak – voor"},
        {"block_id": "b3", "section_path": path, "text": "Tabel 1. Preventieve maatregelen"},
        {"block_id": "b4", "section_path": path, "text": "Voorkom overmatig transpireren"},
        {"block_id": "b5", "section_path": path, "text": "Voorkom huid-op-huid contact"},
        {"block_id": "b6", "section_path": path, "text": "2. Gebruik geen poeders of pasta’s bij de preventie van smetten"},
        {"block_id": "b7", "section_path": path, "text": "Voorkom wrijving bij het drogen van de huidplooien."},
    ]
    texts = [row["text"] for row in inventory(blocks)]
    assert "Voorkom overmatig transpireren" not in texts
    assert "Voorkom huid-op-huid contact" not in texts
    assert texts[0].startswith("Overweeg (een combinatie van)")
    assert "Gebruik geen poeders of pasta’s bij de preventie van smetten" in texts
    # A numbered item ends the table; later unnumbered advice is detected again.
    assert "Voorkom wrijving bij het drogen van de huidplooien." in texts

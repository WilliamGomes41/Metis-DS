"""Closed abstain-sentence catalog. No LLM. No generated prose."""
from __future__ import annotations

SENTENCES = {
    "source_locator_missing": (
        "Deze kennis is niet herleidbaar naar de exacte plaats in de gehashte bron."
    ),
    "unclassified_object": (
        "Dit object heeft nog geen bevestigd type en kan niet als ondersteund antwoord dienen."
    ),
    "unconfirmed_proposal": (
        "Een onbevestigd typevoorstel is geen gepubliceerd type."
    ),
    "heading_not_answerable": (
        "Een kop is structuur, geen advies, definitie of uitleg."
    ),
    "type_does_not_fit_question": (
        "Het beschikbare objecttype past niet bij deze vraag."
    ),
    "insufficient_evidence": (
        "Er is onvoldoende herleidbare, gepubliceerde kennis voor deze vraag."
    ),
    "patient_specific_context_not_available": (
        "Patiëntspecifieke context is niet beschikbaar; DS onthoudt zich."
    ),
    "no_candidates": "Er is geen gepubliceerde kennis voor deze vraag.",
    "empty_published_corpus": "Er is geen gepubliceerde projectie voor deze vraag.",
    "unpublished_or_unlocatable": (
        "Deze kennis is niet gepubliceerd of niet herleidbaar en wordt niet ondersteund."
    ),
    "required_relation_not_present": (
        "De gevraagde relatie ontbreekt in de gepubliceerde kennis."
    ),
    "structured_constraint_mismatch": (
        "De gestructureerde voorwaarde in de kennis komt niet overeen met de vraag."
    ),
    "insufficient_concept_coverage": (
        "De gepubliceerde kennis dekt de gevraagde begrippen onvoldoende."
    ),
}


def sentence_for(reason: str | None) -> str:
    if not reason:
        return SENTENCES["insufficient_evidence"]
    return SENTENCES.get(reason, SENTENCES["insufficient_evidence"])

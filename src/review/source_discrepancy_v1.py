"""Reviewer-reported discrepancy between a knowledge object and its source.

A report is optional evidence on the reviewer's own revise/reject decision for
one exact object version. It never changes text, identity, admission or
publication state, and it never replaces the reviewer's decision: an object
with a reported discrepancy cannot be approved unchanged.
"""
from __future__ import annotations

from typing import Any, Iterable

CATEGORIES = {
    "context_ontbreekt": "Context ontbreekt: een voorwaarde, uitzondering, doelgroep of andere begrenzing uit de bron ontbreekt",
    "betekenis_wijkt_af": "Betekenis wijkt af: type, richting of sterkte past niet bij wat de bron zegt",
    "afbakening_onjuist": "Selectie te ruim of te krap: het object bevat te veel of te weinig brontekst",
    "tekst_of_bronplek_wijkt_af": "Tekst of bronplek wijkt af van de originele bron",
}
# Text and source location are reconstructed from exact spans; a report here
# signals a defect in that guarantee, not an ordinary interpretation error.
CRITICAL = frozenset({"tekst_of_bronplek_wijkt_af"})
DETAILS_KEY = "source_discrepancy"
# Formation of the reported version, fixed at report time: a later revision may
# keep the span-derived object id under another route or model.
FORMATION_KEY = "source_discrepancy_formation"


def formation_of(obj: dict[str, Any]) -> dict[str, str]:
    """Route, formation mode and model of exactly this object version."""
    from src.vorming.decision_tree_construction_v1 import FORMATION_MODE as DECISION_TREE_MODE
    from src.settings.quality_evidence_v1 import route_of
    semantic = (obj.get("metadata") or {}).get("semantic_passage") or {}
    route = str(route_of(obj)["route"])
    if route == "unknown" and semantic.get("formation_mode") == DECISION_TREE_MODE:
        # Decision trees are formed by their own source-bound model route.
        route = "semantic"
    return {"route": route,
            "formation_mode": str(semantic.get("formation_mode") or "unknown"),
            "model": str(semantic.get("model") or "unknown")}


def normalize(values: Iterable[Any] | None) -> list[str]:
    """Closed categories in canonical order; unknown values are refused."""
    from src.operations_console_v1 import ConsoleError
    chosen = {str(value or "").strip() for value in values or ()} - {""}
    if chosen - CATEGORIES.keys():
        raise ConsoleError("source_discrepancy_invalid")
    return [code for code in CATEGORIES if code in chosen]


def assert_allowed(categories: list[str], decision: str) -> None:
    """A reported discrepancy rules out unchanged approval and deferral."""
    from src.operations_console_v1 import ConsoleError
    if categories and decision not in {"revise", "reject"}:
        raise ConsoleError("source_discrepancy_requires_correction_or_rejection")

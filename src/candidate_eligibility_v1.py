"""Candidate-eligibility evidence for D2b2-C.

A source passage is not automatically a KnowledgeCandidate. This module owns
only the machine decision whether Admission should run for one current passage.
It does not classify new types, perform Admission, review content, or decide
publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.semantic_passage_v1 import (
    SELECTION_ORIGIN_COVERAGE,
    SELECTION_ORIGIN_PROPOSAL,
)


CANDIDATE_ELIGIBILITY_VERSION = "candidate-eligibility-v1.0.0"

REASON_SEMANTIC_PROPOSAL = "semantic_proposal_selected"
REASON_SEMANTIC_COVERAGE = "semantic_coverage_remainder"
REASON_EXPLICIT_TYPE = "explicit_type_proposal"
REASON_NO_TYPE = "deterministic_no_type_proposal"
REASON_STRUCTURAL = "structural_object"

SOURCE_SEMANTIC = "semantic"
SOURCE_DETERMINISTIC = "deterministic"
SOURCE_STRUCTURE = "structure"


@dataclass(frozen=True)
class CandidateEligibility:
    eligible: bool
    reason: str
    source: str
    version: str = CANDIDATE_ELIGIBILITY_VERSION

    def as_metadata(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "eligible": self.eligible,
            "reason": self.reason,
            "source": self.source,
        }


def candidate_eligibility_of(obj: dict[str, Any]) -> dict[str, Any]:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    value = metadata.get("candidate_eligibility")
    return value if isinstance(value, dict) else {}


def _semantic_origin(obj: dict[str, Any]) -> str:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    semantic = metadata.get("semantic_passage")
    if not isinstance(semantic, dict):
        return ""
    return str(semantic.get("selection_origin") or "").strip()


def assess_candidate_eligibility(obj: dict[str, Any]) -> CandidateEligibility:
    """Return current machine eligibility without consulting stale Admission.

    Semantic source-bound selection evidence is authoritative when present.
    Otherwise deterministic prose requires an explicit, non-structural type
    proposal. No type inference occurs here.
    """

    object_type = str(obj.get("object_type") or "").strip()
    proposed = str(obj.get("proposed_object_type") or "").strip()

    if object_type in {"document", "heading"} or proposed == "heading":
        return CandidateEligibility(False, REASON_STRUCTURAL, SOURCE_STRUCTURE)

    origin = _semantic_origin(obj)
    if origin == SELECTION_ORIGIN_PROPOSAL:
        return CandidateEligibility(True, REASON_SEMANTIC_PROPOSAL, SOURCE_SEMANTIC)
    if origin == SELECTION_ORIGIN_COVERAGE:
        return CandidateEligibility(False, REASON_SEMANTIC_COVERAGE, SOURCE_SEMANTIC)

    if proposed and proposed != "unclassified":
        return CandidateEligibility(True, REASON_EXPLICIT_TYPE, SOURCE_DETERMINISTIC)

    return CandidateEligibility(False, REASON_NO_TYPE, SOURCE_DETERMINISTIC)

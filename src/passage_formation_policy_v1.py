"""Pure passage-formation policy for VSA F1.

The policy decides only how new pre-Review candidates are formed. It does not
own extraction, admission, Review, repair, publication, or serving state.

Every supported new source is formed semantically: prose through the
configured source-bound semantic contract, decision trees through their own
source-bound proposal route. There is no deterministic formation mode and no
operational rollback mode in the runtime; a rollback is a software revert.
"""
from __future__ import annotations

from dataclasses import dataclass
from src.source_bound_fields_v2 import MODE as SEMANTIC_V2_MODE
from src.source_bound_fields_v3 import MODE as SEMANTIC_V3_MODE


# Part of the semantic replay identity: the prose decision is unchanged, so
# retry/resume keep reusing their recorded replays.
PASSAGE_FORMATION_POLICY_VERSION = "passage-formation-policy-v1.0.0"

SEMANTIC_MODE = "semantic-source-bound-v1"

STRATEGY_SEMANTIC = "semantic"
# Recorded heading provenance values, unchanged so heading rows keep their
# canonical hashes. They describe the structural projection of extractor
# headings; no deterministic candidate formation exists.
STRATEGY_HEADING_STRUCTURE = "deterministic"

REASON_SEMANTIC_FREE_TEXT = "semantic_free_text_required"
REASON_HEADING_STRUCTURE = "deterministic_heading_structure"

_ALLOWED_MODES = frozenset({SEMANTIC_MODE, SEMANTIC_V2_MODE, SEMANTIC_V3_MODE})


class PassageFormationPolicyError(ValueError):
    """Closed policy error with one stable reason code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PassageFormationDecision:
    strategy: str
    reason: str
    policy_version: str = PASSAGE_FORMATION_POLICY_VERSION

    def as_metadata(self) -> dict[str, str]:
        return {
            "policy_version": self.policy_version,
            "strategy": self.strategy,
            "reason": self.reason,
        }


def resolve_passage_formation_strategy(*, deployment_mode: str) -> PassageFormationDecision:
    """Validate the configured semantic contract without performing any I/O.

    An unknown or retired mode (including ``deterministic-v1``) is a
    configuration error; it is never mapped to another route.
    """

    mode = str(deployment_mode or "").strip()
    if mode not in _ALLOWED_MODES:
        raise PassageFormationPolicyError("passage_formation_mode_invalid")
    return PassageFormationDecision(STRATEGY_SEMANTIC, REASON_SEMANTIC_FREE_TEXT)


def heading_structure_decision() -> PassageFormationDecision:
    """Extracted headings are source structure, not semantic candidates."""

    return PassageFormationDecision(STRATEGY_HEADING_STRUCTURE, REASON_HEADING_STRUCTURE)

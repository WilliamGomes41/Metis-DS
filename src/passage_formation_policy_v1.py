"""Pure passage-formation policy for VSA F1.

The policy decides only how new pre-Review candidates are formed. It does not
own extraction, admission, Review, repair, publication, or serving state.
"""
from __future__ import annotations

from dataclasses import dataclass


PASSAGE_FORMATION_POLICY_VERSION = "passage-formation-policy-v1.0.0"

DETERMINISTIC_MODE = "deterministic-v1"
SEMANTIC_MODE = "semantic-source-bound-v1"

STRATEGY_DETERMINISTIC = "deterministic"
STRATEGY_SEMANTIC = "semantic"

REASON_AUTHORITATIVE_TREE = "authoritative_tree_structure"
REASON_EXPLICIT_ROLLBACK = "explicit_operational_rollback"
REASON_SEMANTIC_FREE_TEXT = "semantic_free_text_required"
REASON_DETERMINISTIC_HEADING = "deterministic_heading_structure"

_ALLOWED_MODES = frozenset({DETERMINISTIC_MODE, SEMANTIC_MODE})


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


def resolve_passage_formation_strategy(
    *,
    content_kind: str,
    deployment_mode: str,
) -> PassageFormationDecision:
    """Choose one formation strategy without performing any I/O.

    Decision trees carry authoritative path/node/outcome structure and therefore
    stay deterministic even when semantic prose processing is enabled.
    deterministic-v1 is an explicit deployment rollback for ordinary prose;
    semantic provider failures never select it.
    """

    kind = str(content_kind or "").strip()
    mode = str(deployment_mode or "").strip()
    if mode not in _ALLOWED_MODES:
        raise PassageFormationPolicyError("passage_formation_mode_invalid")

    if kind == "boom":
        return PassageFormationDecision(
            STRATEGY_DETERMINISTIC,
            REASON_AUTHORITATIVE_TREE,
        )
    if mode == DETERMINISTIC_MODE:
        return PassageFormationDecision(
            STRATEGY_DETERMINISTIC,
            REASON_EXPLICIT_ROLLBACK,
        )
    return PassageFormationDecision(
        STRATEGY_SEMANTIC,
        REASON_SEMANTIC_FREE_TEXT,
    )


def deterministic_heading_decision() -> PassageFormationDecision:
    """Mixed semantic documents still form headings deterministically."""

    return PassageFormationDecision(
        STRATEGY_DETERMINISTIC,
        REASON_DETERMINISTIC_HEADING,
    )

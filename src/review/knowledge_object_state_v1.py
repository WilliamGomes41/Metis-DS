"""One derived lifecycle state per knowledge object (KO-1, #995).

A knowledge object is one claim held together with its context, its supporting
evidence and its provenance. Its lifecycle is the statechart in the plan
``docs/plans/ko-statechart-program.md``. This module derives that state from
the fields that already carry it and writes nothing: bindings stay the
approval authority, ``metadata.review_passage`` the disposition, the
canonical publication tables the release. A combination the statechart
forbids is reported as an ``invalid`` code, never repaired here.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from src.knowledge_relations_v1 import (
    confirmed_knowledge_relations_of,
    proposed_knowledge_relations_of,
)
from src.review.knowledge_path_v1 import candidate_lifecycle
from src.review.review_disposition_v1 import definitive_review_disposition
from src.review.review_duty_v1 import (
    FIRST_REVIEW, SECOND_REVIEW, authoritative_review_type, exact_current_approver_ids, review_stage,
)
from src.vorming.admission_gate_v1 import GATE_BLOCKED, admission_of
from src.vorming.passage_register_v1 import passage_register_of, register_status_from_suitability

KANDIDAAT = "Kandidaat"
CONTEXT_OPEN = "Context open"
BEWIJS_OPEN = "Bewijs open"
SAMENGESTELD = "Samengesteld"
IN_REVIEW = "In review"
TWEEDE_REVIEW = "Tweede review"
GOEDGEKEURD = "Goedgekeurd"
GEPUBLICEERD = "Gepubliceerd"
VERVANGEN = "Vervangen"
INGETROKKEN = "Ingetrokken"
AFGEWEZEN = "Afgewezen"

KO_STATES = (
    KANDIDAAT, CONTEXT_OPEN, BEWIJS_OPEN, SAMENGESTELD, IN_REVIEW, TWEEDE_REVIEW,
    GOEDGEKEURD, GEPUBLICEERD, VERVANGEN, INGETROKKEN, AFGEWEZEN,
)

# The single definition of the sets that five modules each spell out today.
# KO-4 and KO-5 migrate those callers; until then a test pins them equal.
FINAL_VALIDATION_STATUSES = frozenset({"approved", "rejected", "superseded"})
RETIRED_VALIDATION_STATUSES = frozenset({"rejected", "superseded", "revise"})

# Decision of 2026-11-05: supporting evidence is mandatory for every type.
EVIDENCE_RELATION_TYPES = frozenset({"supported_by", "explains"})
CONTEXT_UNRESOLVED = "context_necessary_unresolved"

INVALID_CODES = (
    "approved_without_current_binding",
    "approved_mirror_with_open_first_review",
    "approved_with_passage_not_assessed",
    "legacy_revise_persisted",
    "second_review_mirror_disagrees",
    "approval_outside_suitability",
    "register_disagrees_with_review",
    "disposition_invalid",
)

# Release history of the object's document. Per-object publication (#991) is
# decided; KO-3 replaces this document-level input with the per-object registry.
_RELEASE_STATE = {"published": GEPUBLICEERD, "superseded": VERVANGEN, "withdrawn": INGETROKKEN}


def is_knowledge_object(obj: dict[str, Any], review_path: str | None = None) -> bool:
    """Documents, headings, boom paths and source records are not knowledge objects."""
    if str(obj.get("object_type") or "") == "document":
        return False
    # On the boom path a ``path`` is structure, never advice (review_lane).
    if review_path == "boom" and authoritative_review_type(obj) == "path":
        return False
    return candidate_lifecycle(obj) not in {"structure", "source"}


def _governance(obj: dict[str, Any]) -> dict[str, Any]:
    value = obj.get("governance")
    return value if isinstance(value, dict) else {}


def has_evidence(obj: dict[str, Any]) -> bool:
    """A proposed or confirmed supporting relation links evidence to the claim."""
    rows = [*proposed_knowledge_relations_of(obj), *confirmed_knowledge_relations_of(obj)]
    return any(str(row.get("relation_type") or "") in EVIDENCE_RELATION_TYPES for row in rows)


def _own_bindings(obj: dict[str, Any], bindings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    object_id = str(obj.get("object_id") or "")
    return [row for row in bindings if str(row.get("object_id") or "") == object_id]


def _disposition_invalid(obj: dict[str, Any], bindings: list[dict[str, Any]]) -> list[str]:
    from src.review.closed_review_loop_v1 import ALLOWED_FINAL_BY_SUITABILITY
    codes: list[str] = []
    register = str(passage_register_of(obj).get("status") or "")
    for row in bindings:
        if not row.get("valid") or row.get("decision") != "approve":
            continue
        suitability = str(row.get("suitability") or "").strip()
        if not suitability:
            continue
        if "approve" not in ALLOWED_FINAL_BY_SUITABILITY.get(suitability, set()):
            codes.append("approval_outside_suitability")
        try:
            expected = register_status_from_suitability(suitability)
        except ValueError:
            codes.append("disposition_invalid")
            continue
        if register != expected:
            codes.append("register_disagrees_with_review")
    if not definitive_review_disposition(obj)["valid"]:
        codes.append("disposition_invalid")
    return codes


def derive_ko_state(
    obj: dict[str, Any],
    *,
    review_path: str,
    bindings: Iterable[dict[str, Any]] = (),
    fragments: Iterable[dict[str, Any]] | None = None,
    release_status: str = "none",
) -> dict[str, Any]:
    """Return ``{"state", "reasons", "invalid"}`` for one current object revision.

    ``state`` is ``None`` for an object that is not a knowledge object. Every
    knowledge object gets exactly one state from ``KO_STATES``.
    """
    if not is_knowledge_object(obj, review_path):
        return {"state": None, "reasons": ["not_knowledge_object"], "invalid": []}
    fragments = list(fragments) if fragments is not None else None
    own = _own_bindings(obj, bindings)
    governance = _governance(obj)
    status = str(governance.get("validation_status") or "")
    invalid = _disposition_invalid(obj, own)

    def result(state: str, *reasons: str) -> dict[str, Any]:
        return {"state": state, "reasons": list(reasons), "invalid": list(dict.fromkeys(invalid))}

    if status == "superseded":
        return result(VERVANGEN, "validation_superseded")
    if status == "rejected":
        return result(AFGEWEZEN, "validation_rejected")
    if status == "revise":
        # Correction creates a new revision; a stored revise is the old way.
        invalid.append("legacy_revise_persisted")
        return result(KANDIDAAT, "legacy_revise")

    admission = admission_of(obj)
    lifecycle = candidate_lifecycle(obj)
    stage = review_stage(obj, review_path=review_path, bindings=own, fragments=fragments)

    if status == "approved":
        if passage_register_of(obj).get("status") == "not_yet_assessed":
            invalid.append("approved_with_passage_not_assessed")
        second = governance.get("second_review")
        mirror_done = isinstance(second, dict) and second.get("status") == "approved"
        # Each check reads the bindings and the mirror on its own, not via the stage alone:
        # review_stage is None when lineage no longer resolves, yet an approval still needs
        # an exact current binding.
        approvers = exact_current_approver_ids(obj, own)
        if not approvers:
            invalid.append("approved_without_current_binding")
        elif stage == FIRST_REVIEW:
            invalid.append("approved_mirror_with_open_first_review")
        if mirror_done and stage in (FIRST_REVIEW, SECOND_REVIEW):
            invalid.append("second_review_mirror_disagrees")
        if stage == FIRST_REVIEW:
            return result(IN_REVIEW, "review_stage_first")
        if stage == SECOND_REVIEW:
            return result(TWEEDE_REVIEW, "review_stage_second")
        released = _RELEASE_STATE.get(release_status)
        if released:
            return result(released, f"release_{release_status}")
        return result(GOEDGEKEURD, "approved")

    if lifecycle == "materialisation_failed":
        return result(KANDIDAAT, "materialisation_failed")
    reason_codes = admission.get("reason_codes") or []
    if CONTEXT_UNRESOLVED in reason_codes:
        return result(CONTEXT_OPEN, CONTEXT_UNRESOLVED)
    if admission.get("gate_result") == GATE_BLOCKED:
        return result(KANDIDAAT, "admission_blocked")
    if not has_evidence(obj):
        return result(BEWIJS_OPEN, "no_supporting_evidence")
    if stage == FIRST_REVIEW:
        return result(IN_REVIEW, "review_stage_first")
    if stage == SECOND_REVIEW:
        return result(TWEEDE_REVIEW, "review_stage_second")
    return result(SAMENGESTELD, "package_complete_no_open_review")


def snapshot_ko_states(console: Any, envelope: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive every current object's state in one snapshot through the console's own reads."""
    from src.review.beslisboom_path_v1 import review_path_for_klasse
    snapshot_id = str(envelope["snapshot_id"])
    # One read operation per snapshot: bindings are read for this snapshot only.
    with console.document_read_operation():
        objects = console.snapshot_objects(snapshot_id, envelope=envelope)
        bindings = console.object_review_bindings(snapshot_id, objects=objects)
        fragments = console.review_source_fragments(snapshot_id, envelope=envelope, objects=objects)
        release = console.document_release_serving_status(snapshot_id, envelope=envelope)
    path = review_path_for_klasse(str(envelope.get("class") or ""))
    return [
        derive_ko_state(obj, review_path=path, bindings=bindings, fragments=fragments,
                        release_status=str(release.get("release_status") or "none"))
        for obj in objects
    ]


def count_states(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Counts only: no identifiers, titles or text leave this function."""
    states: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    not_ko = 0
    for row in rows:
        if row["state"] is None:
            not_ko += 1
            continue
        states[row["state"]] += 1
        invalid.update(row["invalid"])
    return {
        "states": {name: states.get(name, 0) for name in KO_STATES},
        "invalid": {code: invalid.get(code, 0) for code in INVALID_CODES},
        "invalid_total": sum(invalid.values()),
        "not_knowledge_object": not_ko,
        "ko_state_unclassified": sum(n for s, n in states.items() if s not in KO_STATES),
    }

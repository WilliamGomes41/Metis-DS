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
from src.review.knowledge_path_v1 import candidate_lifecycle, content_reviewable, source_lineage_resolves
from src.review.review_disposition_v1 import definitive_review_disposition
from src.review.review_duty_v1 import (
    FIRST_REVIEW, SECOND_REVIEW, authoritative_review_type, exact_current_approver_ids, review_stage,
)
from src.vorming.admission_gate_v1 import GATE_BLOCKED, admission_of, is_boom_object
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
    "approved_provenance_unresolved",
    "approved_with_passage_not_assessed",
    "legacy_revise_persisted",
    "second_review_mirror_disagrees",
    "approval_outside_suitability",
    "register_disagrees_with_review",
    "disposition_invalid",
    "published_not_approved",
)

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


def has_recorded_approval(obj: dict[str, Any]) -> bool:
    """Read an approval stamp; current bindings remain the review authority."""
    return _governance(obj).get("validation_status") == "approved"


def object_release_status(obj: dict[str, Any], membership: dict[str, Any]) -> str:
    """Interpret selected-tuple canonical metadata without deciding serving."""
    from src.integrity_kernel import compute_canonical_object_hash
    identity = (str(obj.get("object_id") or ""), str(obj.get("object_version") or ""),
                compute_canonical_object_hash(obj))
    if identity != tuple(str(membership.get(key) or "")
                         for key in ("object_id", "object_version", "content_hash")):
        return "none"
    registry_matches = (bool(membership.get("registry_release_id"))
            and membership.get("registry_object_version") == identity[1]
            and membership.get("registry_content_hash") == identity[2]
            and bool(membership.get("snapshot_id"))
            and membership.get("registry_snapshot_id") == membership.get("snapshot_id"))
    if registry_matches:
        if membership.get("registry_state") == "active":
            return "published"
        if membership.get("registry_state") == "emergency_unpublished":
            return "withdrawn"
    if not membership.get("release_id"):
        return "none"
    if membership.get("release_status") == "withdrawn" or membership.get("withdrawn_at"):
        return "withdrawn"
    if (membership.get("successor_release_id") or membership.get("later_logical_release_id")
            or membership.get("registry_state") == "active"
            and bool(membership.get("registry_release_id"))
            and bool(membership.get("registry_content_hash"))
            and bool(membership.get("registry_object_version"))
            and membership.get("registry_object_version") != identity[1]):
        return "superseded"
    return "none"


def has_evidence(obj: dict[str, Any], *, bindings=()) -> bool:
    """A proposed or confirmed supporting relation links evidence to the claim."""
    rows = [*proposed_knowledge_relations_of(obj), *confirmed_knowledge_relations_of(obj)]
    from src.review.ko_transitions_v1 import recorded_not_applicable
    return (any(str(row.get("relation_type") or "") in EVIDENCE_RELATION_TYPES for row in rows)
            or recorded_not_applicable(obj, bindings))


def provenance_resolves(obj: dict[str, Any], fragments: Any) -> bool:
    """A package is only complete when its source lineage still resolves.

    Boom objects follow their own construction duty. Without fragments the
    lineage cannot be checked here and the existing review duty decides.
    """
    if is_boom_object(obj):
        return True
    if not content_reviewable(obj):
        return False
    return fragments is None or source_lineage_resolves(obj, fragments=fragments)


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
    fragments: Any = None,
    release_status: str = "none",
) -> dict[str, Any]:
    """Return ``{"state", "reasons", "invalid"}`` for one current object revision.

    ``state`` is ``None`` for an object that is not a knowledge object. Every
    knowledge object gets exactly one state from ``KO_STATES``.
    """
    if not is_knowledge_object(obj, review_path):
        return {"state": None, "reasons": ["not_knowledge_object"], "invalid": []}
    # Hand fragments on unchanged: a prepared source is a ReadSource carrier, not a list.
    own = _own_bindings(obj, bindings)
    governance = _governance(obj)
    status = str(governance.get("validation_status") or "")
    invalid = _disposition_invalid(obj, own)

    def result(state: str, *reasons: str) -> dict[str, Any]:
        if release_status == "published" and (state not in {GOEDGEKEURD, GEPUBLICEERD} or invalid):
            invalid.append("published_not_approved")
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

    if has_recorded_approval(obj):
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
        # A completed second review needs two exact current approvers, open stage or not.
        if mirror_done and (stage in (FIRST_REVIEW, SECOND_REVIEW) or len(approvers) < 2):
            invalid.append("second_review_mirror_disagrees")
        if not provenance_resolves(obj, fragments):
            invalid.append("approved_provenance_unresolved")
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
    if not has_evidence(obj, bindings=own):
        return result(BEWIJS_OPEN, "no_supporting_evidence")
    if stage == FIRST_REVIEW:
        return result(IN_REVIEW, "review_stage_first")
    if stage == SECOND_REVIEW:
        return result(TWEEDE_REVIEW, "review_stage_second")
    if not provenance_resolves(obj, fragments):
        return result(KANDIDAAT, "provenance_unresolved")
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
    path = review_path_for_klasse(str(envelope.get("class") or ""))
    from src.integrity_kernel import compute_canonical_object_hash
    keys = {str(obj["object_id"]): (str(obj["object_id"]), str(obj["object_version"]),
                                   compute_canonical_object_hash(obj))
            for obj in objects if is_knowledge_object(obj, path)
            and obj.get("object_id") and obj.get("object_version")}
    membership = console.canonical_publication_store.object_publication_membership(snapshot_id, list(keys.values()))
    rows = []
    for obj in objects:
        key = keys.get(str(obj.get("object_id") or ""))
        facts = membership.get(key, {})
        released = object_release_status(obj, facts)
        row = derive_ko_state(obj, review_path=path, bindings=bindings, fragments=fragments,
                              release_status=released)
        if facts.get("release_id") and released == "none":
            row["reasons"].append("publication_activation_unconfirmed")
        rows.append(row)
    return rows


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

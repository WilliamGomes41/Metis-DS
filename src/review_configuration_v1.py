"""B10 reviewconfiguratie per document (H2, slice 2b-1: alleen model en leesprojectie).

De uploader MOET per document één optie kiezen:
- ``uploader_sole``: de uploader is de enige reviewer;
- ``two_others``: twee andere, benoemde reviewers (de uploader telt NOOIT);
- ``one_other``: één andere, benoemde reviewer.
Plus ``four_eyes_required``. Een AI is NOOIT reviewer. Lezers (``readers``)
tellen NOOIT mee voor goedkeuring.

OPENVRAAG-B10-1: four-eyes + ``uploader_sole`` wordt geweigerd.

Deze module schrijft NOOIT. ``effective_configuration`` projecteert:
1. een opgeslagen ``review_configuration`` (gevalideerd; ongeldig → keuze nodig);
2. anders een eenmalige mapping van een bestaand ``review_policy`` (H2-1);
3. anders de legacy-default (H2-7 a): ``one_other`` zonder four-eyes, gelijk aan
   het gedrag op main; hoog-risico-objecten eisen four-eyes los hiervan.
Vanaf slice 2b-3 leest de publicatiepoort alleen een ``chosen`` configuratie via
``configured_approval``; legacy_default en migrated_policy houden het huidige gedrag.

``review-configuration-v2`` (besluit William 2026-10-23) scheidt wie mag beoordelen
van hoeveel goedkeuringen verplicht zijn. Opties: ``uploader_sole``, ``one_other``,
``uploader_and_other`` en ``two_others``. Bij twee aangewezen personen kiest de
uploader expliciet ``four_eyes_required``: uit betekent één geldige goedkeuring
van een van beiden, aan betekent beiden. Inhoudsgebonden vier ogen kan die eis
alleen verhogen. v1-configuraties houden hun oorspronkelijke betekenis.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

CONTRACT = "review-configuration-v1"
CONTRACT_V2 = "review-configuration-v2"
OPTIONS = ("uploader_sole", "two_others", "one_other")
OPTIONS_V2 = ("uploader_sole", "one_other", "uploader_and_other", "two_others")
# v2: alleen bij twee aangewezen personen is vier ogen een keuze.
FOUR_EYES_CHOICE_V2 = frozenset({"uploader_and_other", "two_others"})
SOURCES = ("chosen", "legacy_default", "migrated_policy")
FIELDS = frozenset({"contract", "option", "four_eyes_required", "reviewers", "readers", "revision",
                    "locked_at", "source"})
MINIMUM_REVIEWERS = {"uploader_sole": 0, "one_other": 1, "uploader_and_other": 1, "two_others": 2}


def _ids(value: Any, code: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(code)
    return list(value)


def validate_configuration(value: Any, *, uploader_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS or value.get("contract") not in {CONTRACT, CONTRACT_V2}:
        raise ValueError("invalid_review_configuration")
    if not isinstance(uploader_id, str) or not uploader_id.strip():
        raise ValueError("uploader_identity_missing")
    option = value["option"]
    v2 = value["contract"] == CONTRACT_V2
    if option not in (OPTIONS_V2 if v2 else OPTIONS) or type(value["four_eyes_required"]) is not bool:
        raise ValueError("invalid_review_configuration")
    if v2 and value["source"] != "chosen":
        raise ValueError("invalid_review_configuration")
    if v2 and value["four_eyes_required"] and option not in FOUR_EYES_CHOICE_V2:
        # Vier ogen is alleen een keuze bij twee aangewezen personen.
        raise ValueError("review_configuration_four_eyes_needs_two_reviewers")
    if value["source"] not in SOURCES or type(value["revision"]) is not int or value["revision"] < 0:
        raise ValueError("invalid_review_configuration")
    if value["locked_at"] is not None and not isinstance(value["locked_at"], str):
        raise ValueError("invalid_review_configuration")
    if option == "uploader_sole" and value["four_eyes_required"]:
        raise ValueError("review_configuration_four_eyes_uploader_sole_refused")
    reviewers = _ids(value["reviewers"], "invalid_review_configuration")
    readers = _ids(value["readers"], "invalid_review_configuration")
    if len(set(reviewers)) != len(reviewers) or len(set(readers)) != len(readers):
        raise ValueError("review_configuration_duplicate_reviewer")
    if uploader_id in reviewers:
        raise ValueError("review_configuration_uploader_not_other_reviewer")
    if set(readers) & (set(reviewers) | {uploader_id}):
        raise ValueError("review_configuration_reader_is_reviewer")
    if option == "uploader_sole" and reviewers:
        raise ValueError("review_configuration_uploader_sole_has_reviewers")
    if len(reviewers) < MINIMUM_REVIEWERS[option]:
        raise ValueError("review_configuration_reviewers_missing")
    if value["source"] == "chosen" and len(reviewers) != MINIMUM_REVIEWERS[option]:
        # Alleen nieuwe uploadkeuzes; een legacy_default of migrated_policy MAG NIET ongeldig worden.
        raise ValueError("review_configuration_reviewer_count_mismatch")
    from src.four_eyes_v1 import is_forbidden_reviewer
    if any(is_forbidden_reviewer(item) for item in reviewers):
        raise ValueError("forbidden_reviewer_identity")
    if option == "uploader_sole" and is_forbidden_reviewer(uploader_id):
        raise ValueError("forbidden_reviewer_identity")
    return deepcopy(value)


def _projection(value: dict[str, Any], *, needs_choice: bool, invalid_reason: str | None = None) -> dict[str, Any]:
    out = deepcopy(value)
    out["needs_choice"] = needs_choice
    if invalid_reason:
        out["invalid_reason"] = invalid_reason
    return out


def legacy_default(envelope: dict[str, Any]) -> dict[str, Any]:
    uploader = str(envelope.get("uploader_account_id") or "")
    reviewers = [r for r in dict.fromkeys(envelope.get("named_reviewers") or []) if r != uploader]
    value = {"contract": CONTRACT, "option": "one_other", "four_eyes_required": False,
             "reviewers": reviewers, "readers": [], "revision": 0, "locked_at": None,
             "source": "legacy_default"}
    return _projection(value, needs_choice=not reviewers)


def from_review_policy(policy: Any, *, uploader_id: str) -> dict[str, Any]:
    """H2-1: eenmalige, deterministische mapping; niet eenduidig → keuze nodig."""
    from src.review_policy_v1 import archived_required, required_reviewers, object_policy
    base = {"contract": CONTRACT, "option": "one_other", "four_eyes_required": False, "reviewers": [],
            "readers": [], "revision": 0, "locked_at": None, "source": "migrated_policy"}
    try:
        policy = object_policy({"metadata": {"review_policy": policy}}) if (policy or {}).get("contract") != "managed-review-v2" \
            else object_policy({"governance": {"review_policy": policy}})
    except (ValueError, KeyError, TypeError, AttributeError):
        return _projection(base, needs_choice=True, invalid_reason="invalid_review_policy")
    if policy is None or archived_required(policy):
        return _projection(base, needs_choice=True, invalid_reason="review_policy_not_mappable")
    ordered = [policy["primary"], *(r["reviewer_id"] for r in policy["assignments"]
                                    if r["participation"] == "required")]
    required = [r for r in dict.fromkeys(ordered) if r in required_reviewers(policy)]
    others = [r for r in required if r != uploader_id]
    uploader_required = uploader_id in required
    readers = [r["reviewer_id"] for r in policy["assignments"]
               if r["participation"] == "optional" and r.get("status", "active") == "active"
               and r["reviewer_id"] not in required and r["reviewer_id"] != uploader_id]
    if not others and uploader_required:
        option, four_eyes = "uploader_sole", False
    elif len(others) == 1:
        option, four_eyes = "one_other", uploader_required
    elif len(others) == 2 and not uploader_required:
        option, four_eyes = "two_others", False
    else:
        return _projection(base, needs_choice=True, invalid_reason="review_policy_not_mappable")
    value = {**base, "option": option, "four_eyes_required": four_eyes, "reviewers": others, "readers": readers}
    try:
        return _projection(validate_configuration(value, uploader_id=uploader_id), needs_choice=False)
    except ValueError as exc:
        return _projection(base, needs_choice=True, invalid_reason=str(exc))


def effective_configuration(envelope: dict[str, Any]) -> dict[str, Any]:
    """Alleen-lezen projectie van de geldende configuratie; schrijft NOOIT."""
    uploader = str(envelope.get("uploader_account_id") or "")
    stored = envelope.get("review_configuration")
    if stored is not None:
        try:
            return _projection(validate_configuration(stored, uploader_id=uploader), needs_choice=False)
        except ValueError as exc:
            fallback = deepcopy(stored) if isinstance(stored, dict) else {"contract": CONTRACT}
            return _projection(fallback, needs_choice=True, invalid_reason=str(exc))
    if envelope.get("review_policy") is not None:
        return from_review_policy(envelope["review_policy"], uploader_id=uploader)
    return legacy_default(envelope)


def eligible_reviewers(configuration: dict[str, Any], *, uploader_id: str) -> set[str]:
    """Wie mag beoordelen; de uploader alleen als die is aangewezen."""
    reviewers = set(configuration["reviewers"])
    option = configuration["option"]
    if option == "uploader_sole":
        return {uploader_id}
    if option == "uploader_and_other" or (configuration["contract"] == CONTRACT and option == "one_other"
                                          and configuration["four_eyes_required"]):
        return reviewers | {uploader_id}
    return reviewers


def required_approvals(configuration: dict[str, Any], *, content_four_eyes: bool) -> int:
    """v2: verplichte goedkeuringen uit de expliciete keuze; inhoud kan alleen verhogen."""
    return 2 if configuration["four_eyes_required"] or content_four_eyes else 1


def policy_for_configuration(configuration: dict[str, Any], *, uploader_id: str) -> dict[str, Any] | None:
    """v2: de policy die exact dezelfde plicht uitdrukt, of None als geen policy dat kan.

    Een policy vereist iedere verplichte reviewer. Daarom past ze alleen wanneer alle
    aangewezen personen ook verplicht zijn; twee aangewezen personen zonder vier ogen
    kan een policy niet uitdrukken.
    """
    from src.review_policy_v1 import CONTRACT as POLICY_CONTRACT
    option, reviewers = configuration["option"], list(configuration["reviewers"])
    if configuration["contract"] != CONTRACT_V2:
        return None
    if option == "uploader_sole":
        primary, required = uploader_id, []
    elif option == "one_other":
        primary, required = reviewers[0], []
    elif not configuration["four_eyes_required"]:
        return None
    elif option == "uploader_and_other":
        primary, required = uploader_id, reviewers
    else:
        primary, required = reviewers[0], reviewers[1:]
    return {"contract": POLICY_CONTRACT, "revision": 1, "primary": primary,
            "assignments": [{"reviewer_id": r, "participation": "required"} for r in required]}


def configured_approval(configuration: dict[str, Any], approver_ids: set[str], *, uploader_id: str) -> tuple[bool, bool]:
    """2b-3: (reviewplicht vervuld, vier ogen vervuld) voor een gevalideerde ``chosen`` configuratie.

    Alleen de uploader (uploader_sole) of de benoemde reviewers tellen; lezers en
    andere goedkeurders tellen NOOIT. Het exacte aantal geldt alleen voor ``chosen``.
    Onder v2 telt alleen een goedkeuring van een aangewezen persoon; vier ogen is
    vervuld met twee verschillende aangewezen goedkeurders, onder wie een niet-uploader.
    """
    if configuration["contract"] == CONTRACT_V2:
        approved = eligible_reviewers(configuration, uploader_id=uploader_id) & approver_ids
        four_ok = len(approved) >= 2 and bool(approved - {uploader_id})
        met = len(approved) >= required_approvals(configuration, content_four_eyes=False)
        if configuration["option"] == "uploader_sole":
            return met, False
        return met, four_ok
    reviewers = set(configuration["reviewers"])
    option = configuration["option"]
    if option == "uploader_sole":
        # OPENVRAAG-2b3-1: vier ogen (hoog-risico) onder uploader_sole blijft fail-closed.
        return uploader_id in approver_ids, False
    if option == "one_other":
        met = len(reviewers) == 1 and reviewers <= approver_ids
        return met, met and uploader_id in approver_ids
    # B10-besluit Metis: two_others MOET beide benoemde reviewers hebben, met of zonder
    # vier ogen; de uploader telt NOOIT; die twee vervullen vier ogen, NOOIT een derde.
    met = len(reviewers) == 2 and reviewers <= approver_ids
    return met, met

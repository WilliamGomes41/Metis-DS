"""Admission gate for richtlijn inhoudelijke candidates (v2.30 Phase 1+2).

Hard gate only. Soft scores / volume / ship-then-fix MUST NOT open it.
Phase 2 adds the deep context window and full ``context_scan_done``
semantics. Boom path/node/outcome stay on the existing boom path.
Passage register is not an admission prerequisite.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from src.beslisboom_path_v1 import CLOSED_BOOM_TYPES, review_path_for_klasse
from src.object_taxonomy_v1 import has_terminal_sentence_boundary, locator_of


GATE_ALLOWED = "allowed"
GATE_BLOCKED = "blocked"

REQUIRED_CANDIDATE_FIELDS = (
    "candidate_id",
    "document_id",
    "document_version",
    "source_hash",
    "section_path",
    "source_locator_start",
    "source_locator_end",
    "source_text_exact",
    "candidate_text",
    "subject_span",
    "predicate_span",
    "proposed_type",
    "type_evidence_spans",
    "context_before",
    "context_after",
    "conditions_detected",
    "exceptions_detected",
    "comparison_markers",
    "comparison_targets",
    "references_detected",
    "references_resolved",
    "abbreviations_detected",
    "abbreviations_resolved",
    "related_candidates",
    "gate_result",
    "reason_codes",
)

DUTCH_TYPE_NAMES = {
    "Aanbeveling": "recommendation",
    "Definitie": "definition",
    "Voorwaarde": "condition",
    "Uitzondering": "exception",
    "Feitelijke constatering": "factual_finding",
    "Toelichting": "explanation",
}

TYPE_CONTRACT_FIELDS = {
    "recommendation": (
        "actor_of_scope",
        "recommended_action",
        "action_object_or_goal",
        "recommendation_evidence_span",
    ),
    "definition": ("defined_term", "definiens_span"),
    "condition": ("condition_span", "condition_target"),
    "exception": ("exception_span", "exception_target"),
    "factual_finding": ("factual_claim_span",),
    "explanation": ("support_span", "supported_object"),
}

FACTUAL_FINDING_SERVING_TYPE = "explanation"

_ARRAY_FIELDS = frozenset(
    {
        "type_evidence_spans",
        "conditions_detected",
        "exceptions_detected",
        "comparison_markers",
        "comparison_targets",
        "references_detected",
        "references_resolved",
        "abbreviations_detected",
        "abbreviations_resolved",
        "related_candidates",
        "reason_codes",
        "section_path",
    }
)

_VERB_RE = re.compile(
    r"\b(?:adviseert?|aanbeveelt?|overweegt?|gebruik(?:t|en)?|bespreek(?:t)?|"
    r"verwijs(?:t)?|overleg(?:t)?|controleer(?:t)?|start|wordt|zijn|is|komt|"
    r"heeft|hebben|geven|te geven|bestaan|zie|tenzij)\b",
    re.I,
)
_ADVICE_EVIDENCE_RE = re.compile(
    r"\b(?:adviseert?|aanbeveelt?|overweeg(?:t)?)\b|"
    r"^(?:bespreek|gebruik|verwijs|overleg|controleer|start|overweeg)\b",
    re.I,
)
_PREVALENCE_RE = re.compile(
    r"\bwordt\b.+\bgebruikt\b|\bkomt\b.+\bvoor\b|\bvaker gebruikt\b|"
    r"\bvaak voor\b",
    re.I,
)
_COMPARISON_RE = re.compile(
    r"\b(?:vaker|minder vaak|meer dan|vergeleken|ten opzichte|versus|t\.o\.v\.)\b",
    re.I,
)
_COMPARISON_TARGET_RE = re.compile(
    r"\b(?:dan|vergeleken met|ten opzichte van)\s+\S+",
    re.I,
)
_ABBREV_RE = re.compile(r"\b[A-Za-z]{0,3}[A-Z][A-Za-z&]{1,10}\b")
_KNOWN_ABBREVS = {
    "V&VN": "Verpleegkundigen & Verzorgenden Nederland",
}
_REF_RE = re.compile(
    r"\bzie\s+(?:tabel|hoofdstuk|paragraaf|figuur|§)\s*\d*",
    re.I,
)
_EXCEPTION_RE = re.compile(
    r"\b(?:tenzij|behalve|uitgezonderd|uitzondering)\b",
    re.I,
)
_CONDITION_RE = re.compile(
    r"\b(?:wanneer|indien|mits|bij een|voorwaarde)\b",
    re.I,
)
_ACTOR_RE = re.compile(
    r"\b(?:de\s+|het\s+)?(?:werkgroep|richtlijn|verpleegkundige[n]?|"
    r"zorgverlener|zorgvrager|cli[eë]nt|arts|huisarts)\b",
    re.I,
)
_ADVISEERT_PARSE_RE = re.compile(
    r"(?P<subject>De\s+\w+)\s+(?P<predicate>adviseert?|aanbeveelt?)\s+"
    r"(?:(?P<actor>de\s+verpleegkundige[n]?|de\s+zorgverlener|de\s+arts)\s+)?"
    r"(?P<object>.+?)\s+(?P<action>te\s+\w+)",
    re.I,
)
_TE_INF_RE = re.compile(r"\bte\s+\w+\b", re.I)
_IMPLICIET_RE = re.compile(r"\bimpliciet\b", re.I)
_LOCATOR_LINES_RE = re.compile(r"lines:(\d+)-(\d+)")
_DEFINITION_CUE_RE = re.compile(r"\b(?:is een|wordt genoemd|definitie|betekent)\b", re.I)

_LITERAL_CONTRACT_FIELDS = {
    "recommendation": (
        "actor_of_scope",
        "recommended_action",
        "action_object_or_goal",
        "recommendation_evidence_span",
    ),
    "definition": ("defined_term", "definiens_span"),
    "condition": ("condition_span",),
    "exception": ("exception_span",),
    "factual_finding": ("factual_claim_span",),
    "explanation": ("support_span",),
}
_CONTRACT_MISSING_CODES = {
    "recommendation_evidence_span": ("recommendation_evidence_missing",),
    "condition_target": ("condition_target_missing",),
    "exception_target": ("exception_target_missing",),
    "supported_object": ("supported_object_missing",),
}
_TARGET_EXTRAS = (
    ("exception", "exception_target", "exception_target_missing", True),
    ("condition", "condition_target", "condition_target_missing", False),
    ("explanation", "supported_object", "supported_object_missing", True),
)
_ABSENT_FIELD_CODES = {
    "subject_span": "subject_missing",
    "predicate_span": "predicate_missing",
}


def serving_type_for_admission_type(proposed_type: str) -> str:
    if proposed_type == "factual_finding":
        return FACTUAL_FINDING_SERVING_TYPE
    return proposed_type


def admission_of(obj: dict[str, Any]) -> dict[str, Any]:
    md = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    row = md.get("admission")
    return row if isinstance(row, dict) else {}


def is_admission_blocked(obj: dict[str, Any], review_path: str | None = None) -> bool:
    if review_path == "boom" or is_boom_object(obj):
        return False
    return admission_of(obj).get("gate_result") == GATE_BLOCKED


def is_boom_object(obj: dict[str, Any]) -> bool:
    for key in ("confirmed_object_type", "object_type", "proposed_object_type"):
        if obj.get(key) in CLOSED_BOOM_TYPES:
            return True
    return False


def is_inhoudelijk_candidate(obj: dict[str, Any]) -> bool:
    if obj.get("object_type") in {"document", "heading"}:
        return False
    if obj.get("proposed_object_type") == "heading":
        return False
    if is_boom_object(obj):
        return False
    return True


def build_candidate_record(**fields: Any) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for name in REQUIRED_CANDIDATE_FIELDS:
        if name in fields:
            record[name] = fields[name]
        elif name in _ARRAY_FIELDS:
            record[name] = []
        elif name == "gate_result":
            record[name] = None
        else:
            record[name] = ""
    for key, value in fields.items():
        if key not in record:
            record[key] = value
    return record


def _literal(span: Any, source: str) -> bool:
    text = str(span or "").strip()
    if not text:
        return False
    return text in source


def _localize_corpus(candidate: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            str(candidate.get("source_text_exact") or ""),
            str(candidate.get("candidate_text") or ""),
            str(candidate.get("context_before") or ""),
            str(candidate.get("context_after") or ""),
        )
        if part
    )


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, dict)):
        return True
    return str(value).strip() != ""


def _word_count(text: str) -> int:
    blob = re.sub(r"[.!?]+$", "", re.sub(r"\s+", " ", text or "")).strip()
    return len(blob.split()) if blob else 0


def _scan_comparisons(text: str) -> tuple[list[str], list[str]]:
    markers = [m.group(0) for m in _COMPARISON_RE.finditer(text or "")]
    targets = [m.group(0) for m in _COMPARISON_TARGET_RE.finditer(text or "")]
    return markers, targets


def _scan_abbreviations(text: str) -> tuple[list[str], list[str]]:
    detected: list[str] = []
    resolved: list[str] = []
    for match in _ABBREV_RE.finditer(text or ""):
        token = match.group(0)
        caps = sum(1 for char in token if char.isupper())
        if caps < 2 or len(token) > 8:
            continue
        if token not in detected:
            detected.append(token)
        if token in _KNOWN_ABBREVS and token not in resolved:
            resolved.append(token)
    return detected, resolved


def _scan_references(text: str) -> list[str]:
    return [m.group(0) for m in _REF_RE.finditer(text or "")]


def _scan_exceptions(text: str) -> list[str]:
    found: list[str] = []
    for match in _EXCEPTION_RE.finditer(text or ""):
        start = match.start()
        snippet = re.sub(r"\s+", " ", (text or "")[start:]).strip().rstrip(".")
        if snippet and snippet not in found:
            found.append(snippet)
    return found


def _scan_conditions(text: str) -> list[str]:
    found: list[str] = []
    for match in _CONDITION_RE.finditer(text or ""):
        start = match.start()
        snippet = re.sub(r"\s+", " ", (text or "")[start:]).strip().rstrip(".")
        if snippet and snippet not in found:
            found.append(snippet)
    return found


def _has_recommendation_evidence(text: str) -> bool:
    if not text:
        return False
    if _PREVALENCE_RE.search(text):
        return False
    return bool(_ADVICE_EVIDENCE_RE.search(text))


def _fill_absent(row: dict[str, Any], **fields: Any) -> None:
    for key, value in fields.items():
        if value and not row.get(key):
            row[key] = value


def _first_words(text: str, count: int) -> str:
    words = text.split()
    return " ".join(words[:count]) if words else ""


def _cue_or_prefix(pattern: re.Pattern[str], text: str, fallback: str = "") -> list[str]:
    match = pattern.search(text)
    token = match.group(0) if match else (fallback or text[:20])
    return [token] if token else []


def _enrich_recommendation(candidate: dict[str, Any], text: str) -> None:
    parsed = _ADVISEERT_PARSE_RE.search(text)
    advice = _ADVICE_EVIDENCE_RE.search(text)
    evidence = text if _has_recommendation_evidence(text) else ""
    if parsed:
        _fill_absent(
            candidate,
            subject_span=parsed.group("subject"),
            predicate_span=parsed.group("predicate"),
            actor_of_scope=parsed.group("actor") or parsed.group("subject"),
            action_object_or_goal=(parsed.group("object") or "").strip(),
            recommended_action=parsed.group("action"),
            recommendation_evidence_span=evidence,
            type_evidence_spans=[parsed.group("predicate")],
        )
        return
    if not advice:
        return
    _fill_absent(candidate, predicate_span=advice.group(0))
    if not candidate.get("recommended_action"):
        te = _TE_INF_RE.search(text)
        candidate["recommended_action"] = te.group(0) if te else str(candidate.get("predicate_span") or "")
    actors = _ACTOR_RE.findall(text)
    if not actors:
        neighbors = " ".join(
            [
                str(candidate.get("context_before") or ""),
                str(candidate.get("context_after") or ""),
            ]
        )
        actors = _ACTOR_RE.findall(neighbors)
    if actors:
        _fill_absent(candidate, actor_of_scope=actors[-1] if len(actors) > 1 else actors[0])
    if not candidate.get("action_object_or_goal"):
        te = _TE_INF_RE.search(text)
        if te:
            words = text[: te.start()].strip().split()
            candidate["action_object_or_goal"] = " ".join(words[-4:]) if words else ""
        else:
            words = re.sub(r"^[A-Za-zÀ-ÿ]+\s+", "", text).strip().rstrip(".").split()
            candidate["action_object_or_goal"] = " ".join(words[:6])
    _fill_absent(
        candidate,
        recommendation_evidence_span=evidence,
        type_evidence_spans=[candidate["predicate_span"]] if candidate.get("predicate_span") else None,
    )


def _enrich_from_text(candidate: dict[str, Any]) -> None:
    text = str(candidate.get("source_text_exact") or candidate.get("candidate_text") or "")
    _enrich_recommendation(candidate, text)
    _fill_absent(candidate, subject_span=_first_words(text, 3))
    verb = _VERB_RE.search(text)
    if verb:
        _fill_absent(candidate, predicate_span=verb.group(0))
    proposed = candidate.get("proposed_type")
    if proposed == "definition":
        _fill_absent(
            candidate,
            defined_term=_first_words(text, 3),
            definiens_span=text if " is " in f" {text} " else "",
        )
        if not candidate.get("type_evidence_spans"):
            candidate["type_evidence_spans"] = _cue_or_prefix(
                _DEFINITION_CUE_RE, text, str(candidate.get("defined_term") or "")
            )
    elif proposed == "condition":
        _fill_absent(candidate, condition_span=text)
        if not candidate.get("type_evidence_spans"):
            candidate["type_evidence_spans"] = _cue_or_prefix(_CONDITION_RE, text)
    elif proposed == "exception":
        _fill_absent(candidate, exception_span=text)
        if not candidate.get("type_evidence_spans"):
            candidate["type_evidence_spans"] = _cue_or_prefix(_EXCEPTION_RE, text)
    elif proposed == "factual_finding":
        _fill_absent(candidate, factual_claim_span=text)
    elif proposed == "explanation":
        _fill_absent(candidate, support_span=text)
    markers, targets = _scan_comparisons(text)
    detected, resolved = _scan_abbreviations(text)
    _fill_absent(
        candidate,
        conditions_detected=_scan_conditions(text),
        exceptions_detected=_scan_exceptions(text),
        comparison_markers=markers,
        comparison_targets=targets,
        abbreviations_detected=detected,
        abbreviations_resolved=[token for token in detected if token in _KNOWN_ABBREVS] or resolved,
        references_detected=_scan_references(text),
    )


def _has_impliciet_filler(candidate: dict[str, Any]) -> bool:
    keys = (
        "subject_span",
        "predicate_span",
        "actor_of_scope",
        "recommended_action",
        "action_object_or_goal",
        "recommendation_evidence_span",
        "defined_term",
        "definiens_span",
        "condition_span",
        "condition_target",
        "exception_span",
        "exception_target",
        "factual_claim_span",
        "support_span",
        "supported_object",
        "candidate_text",
    )
    for key in keys:
        if _IMPLICIET_RE.search(str(candidate.get(key) or "")):
            return True
    return False


def _require_literal(value: Any, corpus: str, missing: str, codes: list[str]) -> None:
    if not str(value or "").strip():
        codes.append(missing)
    elif corpus and not _literal(value, corpus):
        codes.extend((missing, "span_not_in_source", "source_fidelity_failure"))


def _unique_reason_codes(codes: list[str], *, scan_done: bool) -> list[str]:
    unique: list[str] = []
    for code in codes:
        if code == "context_scan_not_done" and scan_done:
            continue
        if code not in unique:
            unique.append(code)
    return unique


def _has_sentence_continuation(row: dict[str, Any]) -> bool:
    merge = row.get("expand_merge")
    return bool(
        isinstance(merge, dict)
        and merge.get("performed")
        and merge.get("kind") == "sentence_continuation"
    )


def admit_candidate(
    candidate: dict[str, Any],
    *,
    soft_scores: dict[str, Any] | None = None,
    skip_context_scan: bool = False,
    context_unnecessary: bool = False,
    checked_signals: list[str] | None = None,
) -> dict[str, Any]:
    """Hard-admit one candidate. ``soft_scores`` MAY rank only and MUST NOT open."""
    del soft_scores  # ranking only; never opens the gate
    skip_context_scan = bool(skip_context_scan or candidate.get("skip_context_scan"))
    absent_required = [
        field
        for field in REQUIRED_CANDIDATE_FIELDS
        if field not in candidate and field not in {"gate_result", "reason_codes"}
    ]
    row = build_candidate_record(**{k: v for k, v in candidate.items() if k != "skip_context_scan"})
    _enrich_from_text(row)
    codes: list[str] = []
    if skip_context_scan:
        codes.append("context_scan_not_done")
        row["context_scan_done"] = False
    else:
        from src.context_scan_v1 import apply_scan_to_candidate, headings_from_section_path, scan_deep_context

        current, ancestors = headings_from_section_path(row.get("section_path"))
        current = str(row.get("current_heading") or current)
        ancestors = list(row.get("ancestor_headings") or ancestors)
        scan = scan_deep_context(
            candidate_paragraph=str(row.get("candidate_text") or row.get("source_text_exact") or ""),
            previous_paragraph=str(row.get("context_before") or row.get("previous_paragraph") or ""),
            next_paragraph=str(row.get("context_after") or row.get("next_paragraph") or ""),
            current_heading=current,
            ancestor_headings=ancestors,
            section_path=list(row.get("section_path") or []),
            related_candidates=list(row.get("related_candidates") or []),
        )
        row = apply_scan_to_candidate(row, scan)
    recorded_signals = list(checked_signals) if checked_signals is not None else list(row.get("checked_signals") or [])
    if context_unnecessary and not recorded_signals:
        codes.append("context_unnecessary_unrecorded")
    source = str(row.get("source_text_exact") or row.get("candidate_text") or "")
    text = str(row.get("candidate_text") or source)
    corpus = _localize_corpus(row)
    proposed = str(row.get("proposed_type") or "")

    for field in absent_required:
        codes.append(_ABSENT_FIELD_CODES.get(field, "type_contract_incomplete"))
    _require_literal(row.get("subject_span"), corpus, "subject_missing", codes)
    _require_literal(row.get("predicate_span"), corpus, "predicate_missing", codes)
    if _word_count(text) < 3 or not _VERB_RE.search(text):
        codes.append("incomplete_sentence")
        if _word_count(text) < 3:
            codes.append("no_independent_claim")
    codes += ["incomplete_sentence"] * int(not has_terminal_sentence_boundary(text))
    codes += ["incomplete_sentence"] * int(_has_sentence_continuation(row))
    if not str(row.get("source_locator_start") or "").strip() or not str(row.get("source_locator_end") or "").strip():
        codes.append("locator_invalid")
    evidence = [span for span in (row.get("type_evidence_spans") or []) if str(span or "").strip()]
    if not evidence:
        codes.append("type_evidence_missing")
    elif corpus and any(not _literal(span, corpus) for span in evidence):
        codes.extend(("type_evidence_missing", "span_not_in_source", "source_fidelity_failure"))

    for field in TYPE_CONTRACT_FIELDS.get(proposed, ()):
        extra = _CONTRACT_MISSING_CODES.get(field, ())
        if not _present(row.get(field)):
            codes.append("type_contract_incomplete")
            codes.extend(extra)
            break
        if field in _LITERAL_CONTRACT_FIELDS.get(proposed, ()) and corpus and not _literal(row.get(field), corpus):
            codes.extend(("type_contract_incomplete", "span_not_in_source", "source_fidelity_failure"))
            codes.extend(extra)
            break

    if proposed == "recommendation" and (
        not _has_recommendation_evidence(source) or not _present(row.get("recommendation_evidence_span"))
    ):
        codes.append("recommendation_evidence_missing")
    if _has_impliciet_filler(row):
        codes.append("source_fidelity_failure")
    if _EXCEPTION_RE.search(source) and not _EXCEPTION_RE.search(text):
        codes.append("source_fidelity_failure")
        row["exceptions_detected"] = []
    if row.get("comparison_markers") and not row.get("comparison_targets"):
        codes.append("comparison_target_missing")
    detected_ab = [a for a in (row.get("abbreviations_detected") or []) if a not in _KNOWN_ABBREVS]
    resolved_ab = set(row.get("abbreviations_resolved") or [])
    if any(token not in resolved_ab for token in detected_ab):
        codes.append("abbreviation_unresolved")
    if row.get("references_detected") and not row.get("references_resolved"):
        codes.append("unresolved_reference")
    for kind, field, code, independent in _TARGET_EXTRAS:
        if proposed == kind and not _present(row.get(field)):
            codes.append(code)
            codes += ("no_independent_claim",) * bool(independent)

    merge = row.get("expand_merge")
    if (
        isinstance(merge, dict)
        and merge.get("performed")
        and row.get("context_scan_done")
        and row.get("exceptions_detected")
    ):
        codes = [code for code in codes if code != "source_fidelity_failure"]
    scan = row.get("context_scan")
    if not isinstance(scan, dict):
        scan = {}
    if scan.get("necessary_context_disposition") == "block":
        codes.append("context_necessary_unresolved")
    unique = _unique_reason_codes(codes, scan_done=bool(row.get("context_scan_done")))
    row["reason_codes"] = unique
    row["gate_result"] = (GATE_ALLOWED, GATE_BLOCKED)[bool(unique)]
    return row


def _locator_bounds(obj: dict[str, Any]) -> tuple[str, str]:
    loc = locator_of(obj) or {}
    value = str(loc.get("locator_value") or "").strip()
    match = _LOCATOR_LINES_RE.search(value)
    if match:
        token = f"lines:{match.group(1)}-{match.group(2)}"
        return token, token
    if value:
        return value, value
    return "", ""


def _object_text(obj: dict[str, Any]) -> str:
    return str((obj.get("content") or {}).get("clean_text") or obj.get("text") or "").strip()


def _source_text_exact_for_object(
    obj: dict[str, Any],
    fragments_by_id: dict[str, dict[str, Any]] | None = None,
) -> str:
    parts: list[str] = []
    for ref in (obj.get("provenance") or {}).get("source_fragments") or []:
        frag = (fragments_by_id or {}).get(str(ref.get("raw_object_id") or ""))
        if not frag:
            continue
        raw = str(frag.get("raw_text") or frag.get("clean_text") or "").strip()
        if raw and raw not in parts:
            parts.append(raw)
    if parts:
        return " ".join(parts)
    content = obj.get("content") or {}
    raw = str(content.get("raw_text") or "").strip()
    if raw:
        return raw
    return _object_text(obj)


def _is_heading_object(obj: dict[str, Any]) -> bool:
    return obj.get("object_type") == "heading" or obj.get("proposed_object_type") == "heading"


def _neighbor_text(objects: list[dict[str, Any]], index: int, step: int) -> str:
    cursor = index + step
    while 0 <= cursor < len(objects):
        row = objects[cursor]
        if row.get("object_type") == "document":
            cursor += step
            continue
        return _object_text(row)
    return ""


def _paragraph_neighbor_text(objects: list[dict[str, Any]], index: int, step: int) -> str:
    cursor = index + step
    while 0 <= cursor < len(objects):
        row = objects[cursor]
        if row.get("object_type") == "document" or _is_heading_object(row):
            cursor += step
            continue
        return _object_text(row)
    return ""


def _heading_window(obj: dict[str, Any]) -> tuple[str, list[str]]:
    path = [str(part).strip() for part in ((obj.get("structure") or {}).get("section_path") or []) if str(part).strip()]
    heading = str((obj.get("structure") or {}).get("heading") or "").strip()
    if heading:
        ancestors = [part for part in path if part != heading]
        return heading, ancestors
    if path:
        return path[-1], path[:-1]
    return "", []


def _target_for(obj: dict[str, Any], objects: list[dict[str, Any]], index: int) -> str:
    relations = list(obj.get("relations") or [])
    for rel in relations:
        if rel.get("relation_type") in {"applies_if", "except_if", "explains", "supported_by"}:
            target = str(rel.get("target_object_id") or "").strip()
            if target:
                return target
    for peer in objects:
        if peer.get("object_id") == obj.get("object_id"):
            continue
        for rel in peer.get("relations") or []:
            if rel.get("target_object_id") == obj.get("object_id") and rel.get("relation_type") in {
                "except_if",
                "applies_if",
            }:
                return str(peer.get("object_id") or "")
    return ""


def candidate_from_object(
    obj: dict[str, Any],
    *,
    objects: list[dict[str, Any]],
    index: int,
    document_version: str,
    source_hash: str,
    fragments_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    text = _object_text(obj)
    source_exact = _source_text_exact_for_object(obj, fragments_by_id)
    start, end = _locator_bounds(obj)
    proposed = obj.get("proposed_object_type") or ""
    if not proposed and _PREVALENCE_RE.search(text):
        proposed = "recommendation"
    if not proposed and _EXCEPTION_RE.search(text):
        proposed = "exception"
    if not proposed and _CONDITION_RE.search(text):
        proposed = "condition"
    target = _target_for(obj, objects, index)
    current_heading, ancestor_headings = _heading_window(obj)
    previous_paragraph = _paragraph_neighbor_text(objects, index, -1)
    next_paragraph = _paragraph_neighbor_text(objects, index, 1)
    fields: dict[str, Any] = {
        "candidate_id": obj.get("object_id") or f"cand-{index}",
        "document_id": obj.get("document_id") or "",
        "document_version": document_version or str(obj.get("object_version") or ""),
        "source_hash": source_hash or str((obj.get("source") or {}).get("source_checksum") or ""),
        "section_path": (obj.get("structure") or {}).get("section_path") or [],
        "source_locator_start": start,
        "source_locator_end": end,
        "source_text_exact": source_exact,
        "candidate_text": text,
        "proposed_type": proposed,
        "context_before": previous_paragraph or _neighbor_text(objects, index, -1),
        "context_after": next_paragraph or _neighbor_text(objects, index, 1),
        "previous_paragraph": previous_paragraph,
        "next_paragraph": next_paragraph,
        "current_heading": current_heading,
        "ancestor_headings": ancestor_headings,
    }
    if proposed == "condition":
        fields["condition_span"] = text
        fields["condition_target"] = target
    if proposed == "exception":
        fields["exception_span"] = text
        fields["exception_target"] = target
    if proposed == "explanation":
        fields["support_span"] = text
        fields["supported_object"] = target
    if proposed == "factual_finding":
        fields["factual_claim_span"] = text
    return build_candidate_record(**fields)


def apply_admission_gate(
    objects: list[dict[str, Any]],
    *,
    klasse: str,
    fragments: list[dict[str, Any]] | None = None,
    document_version: str,
    source_hash: str,
) -> list[dict[str, Any]]:
    if review_path_for_klasse(klasse) == "boom":
        return objects
    fragments_by_id = {
        str(fragment.get("fragment_id") or ""): fragment
        for fragment in (fragments or [])
        if fragment.get("fragment_id")
    }
    out: list[dict[str, Any]] = []
    for index, obj in enumerate(objects):
        row = obj
        if is_inhoudelijk_candidate(row):
            candidate = candidate_from_object(
                row,
                objects=objects,
                index=index,
                document_version=document_version,
                source_hash=source_hash,
                fragments_by_id=fragments_by_id,
            )
            admitted = admit_candidate(candidate)
            row = dict(row)
            metadata = dict(row.get("metadata") or {})
            metadata["admission"] = admitted
            row["metadata"] = metadata
        out.append(row)
    return out


def blocked_audit_lane(objects: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [obj for obj in objects if admission_of(obj).get("gate_result") == GATE_BLOCKED]


def ordinary_review_queue(
    objects: Iterable[dict[str, Any]],
    review_path: str | None = None,
) -> list[dict[str, Any]]:
    from src.operations_console_v1 import is_slow_review_duty

    return [
        obj
        for obj in objects
        if is_slow_review_duty(obj, review_path=review_path)
        and admission_of(obj).get("gate_result") != GATE_BLOCKED
    ]

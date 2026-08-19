#!/usr/bin/env python3
"""Deterministic answerability/evidence gate for V&VN Data Services protocol v2.1.

The gate deliberately runs *after* candidate retrieval. Retrieval similarity is
not treated as evidence. The gate checks whether returned published knowledge
contains the concepts, relation and explicit numeric constraints requested by
an incoming query.

This module contains no LLM calls and never mutates canonical knowledge.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

GATE_VERSION = "answerability-evidence-gate-v1.0.0"

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

# Query boilerplate and relation words are not useful subject anchors. The list
# is intentionally domain-neutral; clinical/domain nouns remain anchors.
_ANCHOR_STOPWORDS = {
    "aan", "aanvullend", "aanvullende", "advies", "adviseert", "als", "bij", "client",
    "dan", "dat", "de", "deze", "die", "dit", "door", "een", "en", "er", "gebruik",
    "gebruiken", "gebruikt", "geadviseerd", "geldt", "geeft", "gescoord", "hoe", "hoeveel",
    "hoger", "in", "is", "jaar", "kan", "kennisset", "lager", "mag", "meer", "met", "moet",
    "naar", "niet", "nog", "of", "om", "onderzoek", "op", "ouder", "over", "per", "pilotkennisset",
    "punt", "punten", "routinematig", "score", "specifieke", "te", "tot", "uit", "van", "vanaf",
    "altijd", "onvoorwaardelijk", "iedere", "automatisch", "eerste", "signaleringssituatie",
    "voor", "wat", "welke", "wie", "wordt", "worden", "zijn", "volgens", "dag", "dagen", "week",
    "weken", "maand", "maanden", "frequentie", "herhalen", "herhaald", "herhaling", "interval",
    "dosering", "dosis", "duur", "lang", "behandelduur", "hoevaak", "vaak", "maal", "keer",
}

_TIME_UNITS = {"dag", "dagen", "week", "weken", "maand", "maanden", "jaar", "jaren"}
_DOSE_UNITS = {"mg", "milligram", "microgram", "ug", "mcg", "ie", "eenheden"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    replacements = [(">=", " gte "), ("≤", " lte "), ("<=", " lte "), ("≥", " gte "), (">", " gt "), ("<", " lt ")]
    for source, target in replacements:
        text = text.replace(source, target)
    text = text.replace("²", "2").replace("µ", "u")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize(text))


def _stem(token: str) -> str:
    # Small deterministic normalization only; no language model or external NLP.
    t = token
    for suffix in ("ingen", "ering", "ingen", "heden", "lijke", "lijk", "en", "er", "e", "s"):
        if len(t) >= 7 and t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _token_matches(a: str, b: str) -> bool:
    a = _stem(a); b = _stem(b)
    if a == b:
        return True
    if min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)):
        return True
    return False


@dataclass(frozen=True)
class NumericConstraint:
    operator: str
    threshold: float
    unit: str | None = None


@dataclass(frozen=True)
class QuerySpec:
    intent: str
    required_relations: tuple[str, ...] = ()
    anchors: tuple[str, ...] = ()
    numeric_constraints: tuple[NumericConstraint, ...] = ()
    patient_specific: bool = False


@dataclass(frozen=True)
class AnswerabilityConfig:
    max_candidates: int = 5
    min_anchor_coverage: float = 0.5
    min_anchor_matches: int = 1
    filter_results_to_supporting_evidence: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnswerabilityConfig":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class CandidateEvidence:
    object_id: str
    anchor_matches: list[str] = field(default_factory=list)
    anchor_coverage: float = 0.0
    relation_support: dict[str, bool] = field(default_factory=dict)
    numeric_support: list[bool] = field(default_factory=list)
    support: bool = False


def _extract_anchors(query: str) -> tuple[str, ...]:
    out: list[str] = []
    for token in tokens(query):
        if token.isdigit() or token in _ANCHOR_STOPWORDS or token in _TIME_UNITS or token in _DOSE_UNITS:
            continue
        if token in {"gte", "lte", "gt", "lt", "eq"}:
            continue
        if len(token) < 3:
            continue
        if token not in out:
            out.append(token)
    return tuple(out)


def _operator_near_number(text: str, number: str) -> str | None:
    n = normalize(text)
    escaped = re.escape(number)
    patterns = [
        (rf"(?:gte|vanaf|minimaal|ten minste)\s*{escaped}\b", "gte"),
        (rf"\b{escaped}\s*(?:(?:jaar|jaren)\s*)?(?:of meer|of hoger|of ouder|en hoger)\b", "gte"),
        (rf"(?:lte|maximaal|ten hoogste)\s*{escaped}\b", "lte"),
        (rf"\b{escaped}\s*(?:of minder|of lager)\b", "lte"),
        (rf"(?:gt|meer dan|hoger dan)\s*{escaped}\b", "gt"),
        (rf"(?:lt|minder dan|lager dan)\s*{escaped}\b", "lt"),
        (rf"(?:eq|exact)\s*{escaped}\b", "eq"),
    ]
    for pattern, op in patterns:
        if re.search(pattern, n):
            return op
    return None


def _canonical_unit(window: str) -> str | None:
    w = normalize(window)
    if "kg/m" in w or "kg m" in w:
        return "kg/m2"
    if re.search(r"\b(?:jaar|jaren)\b", w):
        return "year"
    if re.search(r"\b(?:punt|punten)\b", w):
        return "points"
    if re.search(r"\b(?:mg|milligram)\b", w):
        return "mg"
    if re.search(r"\b(?:ug|microgram|mcg)\b", w):
        return "ug"
    if re.search(r"\b(?:ie)\b", w):
        return "ie"
    if "eenheden" in w and "dag" in w:
        return "units_per_day"
    return None


def _extract_numeric_constraints(query: str) -> tuple[NumericConstraint, ...]:
    n = normalize(query)
    found: list[NumericConstraint] = []
    for m in re.finditer(r"\b\d+(?:[.,]\d+)?\b", n):
        raw = m.group(0)
        op = _operator_near_number(n[max(0, m.start()-35):m.end()+35], raw)
        if not op:
            continue
        value = float(raw.replace(",", "."))
        window = n[max(0, m.start()-25):m.end()+35]
        found.append(NumericConstraint(op, value, _canonical_unit(window)))
    return tuple(found)


def parse_query(query: str) -> QuerySpec:
    n = normalize(query)
    patient_specific = bool(re.search(r"\b(?:deze|mijn)\s+(?:specifieke\s+)?patient\b", n))

    relations: list[str] = []
    intent = "fact"
    if re.search(r"\bhoe vaak\b|\bfrequentie\b|\bherhaal\w*\b|\binterval\b", n):
        intent = "frequency_lookup"; relations.append("frequency")
    elif re.search(r"\bhoe lang\b|\bduur\b|\bbehandelduur\b", n):
        intent = "duration_lookup"; relations.append("duration")
    elif re.search(r"\bdosering\b|\bdosis\b", n) or ("hoeveel" in n and any(u in tokens(n) for u in _DOSE_UNITS)):
        intent = "dosage_lookup"; relations.append("dosage")
    elif re.search(r"\bhoeveel punten\b|\bgescoord\b|\bscorepunten\b", n):
        intent = "score_points_lookup"; relations.append("score_points")
    elif re.search(r"\bbij welke score\b", n) or ("score" in n and ("verwijs" in n or "verwezen" in n or "huisarts" in n)):
        intent = "score_threshold_lookup"; relations.append("score_threshold")
    elif "t score" in n or "t-score" in (query or "").casefold():
        intent = "diagnostic_threshold_lookup"; relations.append("diagnostic_threshold")
    elif re.search(r"\badviseer\w*\b|\baanbevel\w*\b|\broutinematig\b", n):
        intent = "recommendation_lookup"; relations.append("recommendation")

    return QuerySpec(
        intent=intent,
        required_relations=tuple(relations),
        anchors=_extract_anchors(query),
        numeric_constraints=_extract_numeric_constraints(query),
        patient_specific=patient_specific,
    )


def _record_text(record: dict[str, Any]) -> str:
    return normalize(record.get("retrieval_text") or "")


def _content_evidence_text(record: dict[str, Any]) -> str:
    """Exclude generic projection boilerplate while retaining linked context."""
    raw = record.get("retrieval_text") or ""
    kept = []
    for line in raw.splitlines():
        n = normalize(line)
        if n.startswith("bron:") or n.startswith("sectie:") or n.startswith("context:"):
            continue
        kept.append(line)
    return normalize("\n".join(kept))


def _anchor_evidence(spec: QuerySpec, record: dict[str, Any]) -> tuple[list[str], float]:
    if not spec.anchors:
        return [], 1.0
    rt = tokens(_content_evidence_text(record))
    matched = [a for a in spec.anchors if any(_token_matches(a, b) for b in rt)]
    return matched, len(matched) / len(spec.anchors)


def _relation_supported(relation: str, record: dict[str, Any]) -> bool:
    text = _content_evidence_text(record)
    logic = record.get("structured_logic") or {}
    if relation == "score_points":
        return logic.get("score_points") is not None or bool(re.search(r"\b\d+(?:[.,]\d+)?\s+punt(?:en)?\b", text))
    if relation == "score_threshold":
        rt = logic.get("result_threshold") or {}
        return rt.get("threshold") is not None and "punt" in str(rt.get("unit", "")).casefold()
    if relation == "frequency":
        return bool(re.search(r"\b(?:dagelijks|wekelijks|maandelijks|jaarlijks|frequentie|interval|herhaal\w*)\b", text) or re.search(r"\b(?:\d+|een|twee)\s*(?:x|keer)\s+(?:per|in)\b", text) or re.search(r"\bper\s+(?:dag|week|maand|jaar)\b", text))
    if relation == "dosage":
        # A dose requires a numeric amount and a dose unit in the evidence.
        return bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:mg|milligram|ug|microgram|mcg|ie)\b", text))
    if relation == "duration":
        return bool(re.search(r"\b(?:duur|gedurende|behandelduur|gebruik\w*\s+voor\s+\d+)\b", text) or re.search(r"\b\d+(?:[.,]\d+)?\s+(?:dagen|weken|maanden|jaren)\b", text) and re.search(r"\b(?:behandel\w*|gebruik\w*|therapie)\b", text))
    if relation == "diagnostic_threshold":
        return bool(re.search(r"\bt\s*score\b", text) and re.search(r"\b(?:gte|lte|gt|lt|eq|diagnos\w*)\b", text))
    if relation == "recommendation":
        return bool(re.search(r"\b(?:adviseer\w*|aanbevel\w*|gebruik|verwijs|overleg|controleer|informeer|start\w*)\b", text))
    return True


def _canon_evidence_unit(unit: Any) -> str | None:
    u = normalize(str(unit or ""))
    if not u:
        return None
    if "kg/m" in u or "kg m" in u:
        return "kg/m2"
    if "jaar" in u or u == "year":
        return "year"
    if "punt" in u:
        return "points"
    if "eenheden" in u and "dag" in u:
        return "units_per_day"
    if u in {"mg", "milligram"}:
        return "mg"
    if u in {"ug", "microgram", "mcg"}:
        return "ug"
    if u == "ie":
        return "ie"
    return u


def _iter_logic_constraints(record: dict[str, Any]) -> Iterable[dict[str, Any]]:
    logic = record.get("structured_logic") or {}
    for p in logic.get("predicates") or []:
        if p.get("threshold") is not None:
            yield p
    if (logic.get("result_threshold") or {}).get("threshold") is not None:
        yield logic["result_threshold"]


def _numeric_supported(constraint: NumericConstraint, record: dict[str, Any]) -> bool:
    for item in _iter_logic_constraints(record):
        try:
            val = float(item.get("threshold"))
        except (TypeError, ValueError):
            continue
        if val != constraint.threshold:
            continue
        if item.get("operator") != constraint.operator:
            continue
        iu = _canon_evidence_unit(item.get("unit"))
        if constraint.unit and iu and constraint.unit != iu:
            continue
        return True

    # Recommendations often carry their linked condition only in retrieval text.
    text = _content_evidence_text(record)
    number = f"{constraint.threshold:g}"
    op_pat = re.escape(constraint.operator)
    if not re.search(rf"\b{op_pat}\s*{re.escape(number)}\b", text):
        return False
    if constraint.unit == "year" and "jaar" not in text:
        return False
    if constraint.unit == "points" and "punt" not in text:
        return False
    if constraint.unit == "kg/m2" and "kg/m" not in text and "kg m" not in text:
        return False
    if constraint.unit == "units_per_day" and not ("eenheden" in text and "dag" in text):
        return False
    return True



def _candidate_clusters(candidate_ids: list[str], record_by_object: dict[str, dict[str, Any]]) -> list[list[str]]:
    """Return connected candidate clusters using canonical context/parent links."""
    ids = set(candidate_ids)
    graph: dict[str, set[str]] = {oid: set() for oid in ids}
    for oid in ids:
        md = (record_by_object.get(oid) or {}).get("metadata") or {}
        refs = set(md.get("context_object_ids") or [])
        parent = md.get("parent_object_id")
        if parent:
            refs.add(parent)
        for ref in refs:
            if ref in ids:
                graph[oid].add(ref)
                graph[ref].add(oid)
    seen: set[str] = set()
    clusters: list[list[str]] = []
    for oid in candidate_ids:
        if oid in seen:
            continue
        stack = [oid]; seen.add(oid); cluster: list[str] = []
        while stack:
            cur = stack.pop(); cluster.append(cur)
            for nxt in sorted(graph[cur]):
                if nxt not in seen:
                    seen.add(nxt); stack.append(nxt)
        clusters.append(cluster)
    return clusters


def _cluster_support(
    spec: QuerySpec,
    cluster: list[str],
    evidence_by_id: dict[str, CandidateEvidence],
    config: AnswerabilityConfig,
) -> tuple[bool, dict[str, Any]]:
    anchor_union = sorted({a for oid in cluster for a in evidence_by_id[oid].anchor_matches})
    anchor_coverage = (len(anchor_union) / len(spec.anchors)) if spec.anchors else 1.0
    anchor_ok = (not spec.anchors) or (
        len(anchor_union) >= config.min_anchor_matches and anchor_coverage >= config.min_anchor_coverage
    )
    relation_support = {
        relation: any(evidence_by_id[oid].relation_support.get(relation, False) for oid in cluster)
        for relation in spec.required_relations
    }
    relation_ok = all(relation_support.values()) if relation_support else True
    numeric_support = [
        any((evidence_by_id[oid].numeric_support[i] if i < len(evidence_by_id[oid].numeric_support) else False) for oid in cluster)
        for i, _ in enumerate(spec.numeric_constraints)
    ]
    numeric_ok = all(numeric_support) if numeric_support else True
    return anchor_ok and relation_ok and numeric_ok, {
        "object_ids": cluster,
        "anchor_matches": anchor_union,
        "anchor_coverage": round(anchor_coverage, 6),
        "relation_support": relation_support,
        "numeric_support": numeric_support,
        "support": anchor_ok and relation_ok and numeric_ok,
    }


def evaluate_answerability(
    query: str,
    raw_result: dict[str, Any],
    record_by_object: dict[str, dict[str, Any]],
    config: AnswerabilityConfig | None = None,
) -> dict[str, Any]:
    cfg = config or AnswerabilityConfig()
    spec = parse_query(query)

    base = {
        "gate_version": GATE_VERSION,
        "query_spec": {
            **asdict(spec),
            "numeric_constraints": [asdict(x) for x in spec.numeric_constraints],
        },
    }

    if spec.patient_specific:
        return {
            **base,
            "behavior": "abstain",
            "answerability": "insufficient_evidence",
            "reason": "patient_specific_context_not_available",
            "false_positive_class": "context_mismatch",
            "results": [],
            "candidate_evidence": [],
        }

    if raw_result.get("behavior") != "retrieve" or not raw_result.get("results"):
        return {
            **base,
            "behavior": "abstain",
            "answerability": "insufficient_evidence",
            "reason": raw_result.get("reason") or "no_candidates",
            "false_positive_class": "below_confidence_threshold",
            "results": [],
            "candidate_evidence": [],
        }

    evidence_rows: list[CandidateEvidence] = []
    candidate_ids: list[str] = []
    for item in raw_result.get("results", [])[: cfg.max_candidates]:
        oid = item.get("object_id")
        record = record_by_object.get(oid)
        if not record:
            continue
        candidate_ids.append(oid)
        matched, coverage = _anchor_evidence(spec, record)
        relation_support = {r: _relation_supported(r, record) for r in spec.required_relations}
        numeric_support = [_numeric_supported(c, record) for c in spec.numeric_constraints]
        evidence_rows.append(CandidateEvidence(
            object_id=oid,
            anchor_matches=matched,
            anchor_coverage=round(coverage, 6),
            relation_support=relation_support,
            numeric_support=numeric_support,
            support=False,
        ))

    evidence_by_id = {e.object_id: e for e in evidence_rows}
    cluster_rows: list[dict[str, Any]] = []
    supporting_ids: list[str] = []
    for cluster in _candidate_clusters(candidate_ids, record_by_object):
        ok, row = _cluster_support(spec, cluster, evidence_by_id, cfg)
        cluster_rows.append(row)
        if ok and not supporting_ids:
            supporting_ids = list(cluster)

    if supporting_ids:
        supporting_set = set(supporting_ids)
        for e in evidence_rows:
            e.support = e.object_id in supporting_set
        results = raw_result.get("results", [])
        if cfg.filter_results_to_supporting_evidence:
            results = [r for r in results if r.get("object_id") in supporting_set]
        return {
            **base,
            "behavior": "retrieve",
            "answerability": "supported",
            "reason": "evidence_gate_passed",
            "false_positive_class": None,
            "results": results,
            "candidate_evidence": [asdict(x) for x in evidence_rows],
            "evidence_clusters": cluster_rows,
        }

    # Explain the first failed safety dimension across the candidate set.
    if spec.required_relations and not any(all(c.get("relation_support", {}).values()) for c in cluster_rows):
        reason = "required_relation_not_present"
        fp_class = "relation_mismatch"
    elif spec.numeric_constraints and not any(all(c.get("numeric_support", [])) for c in cluster_rows):
        reason = "structured_constraint_mismatch"
        fp_class = "numeric_confusion"
    elif spec.anchors:
        any_anchor = any(e.anchor_matches for e in evidence_rows)
        reason = "insufficient_concept_coverage"
        fp_class = "concept_overlap" if any_anchor else "semantic_neighbor"
    else:
        reason = "insufficient_evidence"
        fp_class = "semantic_neighbor"

    return {
        **base,
        "behavior": "abstain",
        "answerability": "insufficient_evidence",
        "reason": reason,
        "false_positive_class": fp_class,
        "results": [],
        "candidate_evidence": [asdict(x) for x in evidence_rows],
        "evidence_clusters": cluster_rows,
    }

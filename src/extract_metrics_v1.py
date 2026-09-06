"""Extract-quality metrics (ROADMAP wave 4 / Post-#120 item 4).

Unit: one extracted passage assigned 1:1 to one gold passage on
``source_id`` + exact ``source_text`` (text-only when neither side has a
source_id — regression fixtures). Precision denominator is TP+FP.
Duplicate selected copies of an already-assigned (source, passage) are
``duplicate_predictions`` and count as FP, not extra TP.

``context_completeness`` is scored only against annotated
``expected_context_*``. ``context_scan_done`` alone is never enough.
Neighbor capture without annotations is ``neighbor_context_present``.
``review_burden`` is None unless gold defines an expected ordinary-review
count — it MUST NOT read as progress when undefined.

A quality claim opens only when concrete independent-package checks pass
(source identity, annotation rules, reviewers, locked scope, lock moment
+ versions, train/holdout split at document level, computed overlap).
Status strings and self-declared booleans never open a claim. v231_wave4
fixture gold remains usable for regressions and is fail-closed for claims.

Read-mostly: this module does not write gold or metric files. Metric runs
are idempotent. Old extract-gold schema stays readable; unsupported
schema fail-closed. Truncated/corrupt gold JSON raises ExtractGoldError.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admission_of,
    admit_candidate,
    build_candidate_record,
    ordinary_review_queue,
)
from src.extract_coverage_v1 import coverage_by_section
from src.passage_register_v1 import apply_passage_register, passage_register_of
from src.review_cockpit_v1 import confirmable_proposed_type


EXTRACT_QUALITY_METRICS = (
    "precision",
    "type_accuracy",
    "context_completeness",
    "coverage_vs_gold",
    "review_burden",
)
ASSIGNMENT_UNIT = "source_id+passage"

SUPPORTED_EXTRACT_GOLD_VERSIONS = frozenset({"0.1"})
FIXTURE_GOLD_STATUSES = frozenset(
    {
        "fixture_gold",
        "development",
        "preliminary_pending_clinical_publication",
        "language_variation",
    }
)
INDEPENDENT_GOLD_STATUSES = frozenset({"independent_representative", "locked_holdout"})
DEVELOPMENT_GOLD_SET_IDS = frozenset(
    {
        "v231-wave4-independent-extract-gold-v0.1",
        "v231-wave4-extract-holdout-v0.1",
        "v231-wave4-language-variation-gold-v0.1",
        "v230-phase4-extract-gold-v0.1",
    }
)
FORBIDDEN_REVIEWER_NAME_TOKENS = ("metis", "forge", "auditor")
REQUIRED_SOURCE_IDENTITY_FIELDS = ("document_id", "source_id", "title", "publisher", "version")
GOLD_POSITIVE_ROLES = frozenset({"missed_knowledge", "true_positive_expected"})
GOLD_NEGATIVE_ROLES = frozenset({"false_admit", "true_negative"})
GOLD_NEGATIVE_CLASSES = frozenset({"false_admit", "excluded"})

_REPO_ROOT = Path(__file__).resolve().parents[1]


class ExtractGoldError(ValueError):
    """Fail-closed gold load (truncated, non-JSON, or not an object)."""

    def __init__(self, code: str = "gold_unreadable") -> None:
        self.code = code
        super().__init__(code)


def _text_of(obj: dict[str, Any]) -> str:
    content = obj.get("content") if isinstance(obj.get("content"), dict) else {}
    return str(content.get("clean_text") or obj.get("candidate_text") or "").strip()


def _norm_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _gold_passages(gold: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(gold, dict):
        return []
    rows = gold.get("passages") or []
    return [row for row in rows if isinstance(row, dict)]


def gold_schema_supported(gold: dict[str, Any] | None) -> bool:
    if not isinstance(gold, dict):
        return False
    kind = str(gold.get("kind") or "").strip()
    if kind and kind != "extract_quality":
        return False
    version = str(gold.get("version") or "0.1").strip()
    return version in SUPPORTED_EXTRACT_GOLD_VERSIONS


def _is_gold_positive(row: dict[str, Any]) -> bool:
    role = str(row.get("role") or "").strip()
    cls = str(row.get("class") or "").strip()
    if role in GOLD_NEGATIVE_ROLES or cls == "false_admit":
        return False
    if role in GOLD_POSITIVE_ROLES or cls == "missed":
        return True
    expected = str(row.get("expected_register_status") or "")
    allowed = [str(item) for item in (row.get("allowed_register_statuses") or []) if str(item)]
    if expected == "selected_as_candidate" or "selected_as_candidate" in allowed:
        return True
    return False


def _is_gold_negative(row: dict[str, Any]) -> bool:
    role = str(row.get("role") or "").strip()
    cls = str(row.get("class") or "").strip()
    if role in GOLD_NEGATIVE_ROLES or cls in GOLD_NEGATIVE_CLASSES:
        return True
    return str(row.get("expected_register_status") or "") == "excluded_with_reason"


def _has_missed_knowledge(passages: Iterable[dict[str, Any]]) -> bool:
    return any(
        str(row.get("role") or "") == "missed_knowledge" or str(row.get("class") or "") == "missed"
        for row in passages
    )


def _has_false_admit(passages: Iterable[dict[str, Any]]) -> bool:
    return any(
        str(row.get("role") or "") == "false_admit" or str(row.get("class") or "") == "false_admit"
        for row in passages
    )


def _source_count(gold: dict[str, Any]) -> int:
    sources = gold.get("sources")
    if isinstance(sources, list) and sources:
        return len(sources)
    fixtures = gold.get("source_fixtures")
    if isinstance(fixtures, list) and fixtures:
        return len(fixtures)
    if str(gold.get("source_fixture") or "").strip():
        return 1
    return 0


def _is_development_regression_gold(gold: dict[str, Any] | None) -> bool:
    if not isinstance(gold, dict):
        return True
    if gold.get("development_regression_only") is True:
        return True
    if str(gold.get("status") or "").strip() in FIXTURE_GOLD_STATUSES:
        return True
    gid = str(gold.get("golden_set_id") or "").strip()
    if gid in DEVELOPMENT_GOLD_SET_IDS:
        return True
    if gid.startswith("v231-wave4-") or gid.startswith("v230-phase"):
        return True
    return False


def _source_id_of(obj: dict[str, Any]) -> str:
    source = obj.get("source") if isinstance(obj.get("source"), dict) else {}
    return str(obj.get("source_id") or source.get("source_id") or "").strip()


def _row_source_id(row: dict[str, Any]) -> str:
    return str(row.get("source_id") or "").strip()


def _row_matches_obj(row: dict[str, Any], obj: dict[str, Any]) -> bool:
    row_text = str(row.get("source_text") or "").strip()
    obj_text = _text_of(obj)
    if not row_text or row_text != obj_text:
        return False
    row_src = _row_source_id(row)
    obj_src = _source_id_of(obj)
    if row_src and obj_src:
        return row_src == obj_src
    if row_src and not obj_src:
        return False
    return True


def _collect_identity_values(gold: dict[str, Any] | None, *keys: str) -> set[str]:
    values: set[str] = set()
    if not isinstance(gold, dict):
        return values
    for source in gold.get("sources") or []:
        if not isinstance(source, dict):
            continue
        for key in keys:
            item = str(source.get(key) or "").strip()
            if item:
                values.add(item)
    for row in _gold_passages(gold):
        for key in keys:
            item = str(row.get(key) or "").strip()
            if item:
                values.add(item)
    return values


def _passage_keys_and_texts(gold: dict[str, Any] | None) -> tuple[set[tuple[str, str]], set[str]]:
    keys: set[tuple[str, str]] = set()
    texts: set[str] = set()
    for row in _gold_passages(gold):
        text = str(row.get("source_text") or "").strip()
        if not text:
            continue
        texts.add(text)
        keys.add((_row_source_id(row), text))
    return keys, texts


def train_holdout_source_overlap(
    train: dict[str, Any] | None,
    holdout: dict[str, Any] | None,
) -> dict[str, Any]:
    """Computed overlap — never trust a self-declared passed boolean."""
    train_docs = _collect_identity_values(train, "document_id")
    holdout_docs = _collect_identity_values(holdout, "document_id")
    train_sources = _collect_identity_values(train, "source_id")
    holdout_sources = _collect_identity_values(holdout, "source_id")
    train_keys, train_texts = _passage_keys_and_texts(train)
    holdout_keys, holdout_texts = _passage_keys_and_texts(holdout)
    shared_docs = sorted(train_docs & holdout_docs)
    shared_sources = sorted(train_sources & holdout_sources)
    shared_keys = sorted(train_keys & holdout_keys)
    shared_texts = sorted(train_texts & holdout_texts)
    return {
        "shared_document_ids": shared_docs,
        "shared_source_ids": shared_sources,
        "shared_passage_keys": shared_keys,
        "shared_passage_texts": shared_texts,
        "has_overlap": bool(shared_docs or shared_sources or shared_keys or shared_texts),
    }


def _source_identity_complete(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    if any(not str(source.get(field) or "").strip() for field in REQUIRED_SOURCE_IDENTITY_FIELDS):
        return False
    material = str(
        source.get("material") or source.get("fixture") or source.get("material_path") or ""
    ).strip()
    return bool(material)


def _reviewer_name(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("name") or "").strip()
    return str(row or "").strip()


def _resolve_package(
    gold: dict[str, Any] | None,
    holdout: dict[str, Any] | None,
    lock: dict[str, Any] | None,
    repo_root: Path | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(gold, dict):
        return holdout, lock
    root = Path(repo_root) if repo_root is not None else _REPO_ROOT
    package = gold.get("package") if isinstance(gold.get("package"), dict) else {}
    if holdout is None:
        holdout_path = str(package.get("holdout_path") or "").strip()
        if holdout_path:
            path = root / holdout_path
            if path.is_file():
                try:
                    holdout = load_extract_gold(path)
                except ExtractGoldError:
                    holdout = None
    if lock is None:
        lock_path = str(package.get("lock_path") or "").strip()
        if lock_path:
            path = root / lock_path
            if path.is_file():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    loaded = None
                if isinstance(loaded, dict):
                    lock = loaded
    return holdout, lock


def independent_quality_claim_checks(
    gold: dict[str, Any] | None,
    *,
    holdout: dict[str, Any] | None = None,
    lock: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Concrete checks only. Status strings / booleans never open a claim."""
    failures: list[str] = []
    if not gold_schema_supported(gold) or not isinstance(gold, dict):
        return {"allowed": False, "failures": ["gold_schema_unsupported"]}
    holdout, lock = _resolve_package(gold, holdout, lock, repo_root)
    if _is_development_regression_gold(gold):
        failures.append("fixture_gold_development_only")
    if holdout is not None:
        overlap = train_holdout_source_overlap(gold, holdout)
        if overlap["has_overlap"]:
            failures.append("train_holdout_overlap")
    else:
        failures.append("holdout_missing")
        overlap = train_holdout_source_overlap(gold, {})
    if not isinstance(lock, dict):
        failures.extend(
            [
                "reviewers_missing",
                "annotation_rules_missing",
                "lock_moment_missing",
                "locked_scope_missing",
                "source_identity_incomplete",
            ]
        )
    else:
        reviewers = lock.get("reviewers") if isinstance(lock.get("reviewers"), list) else []
        if not reviewers:
            failures.append("reviewers_missing")
        for row in reviewers:
            name = _reviewer_name(row)
            if not name:
                failures.append("reviewers_missing")
                continue
            lowered = name.lower()
            if any(token in lowered for token in FORBIDDEN_REVIEWER_NAME_TOKENS):
                failures.append("reviewers_forbidden_seat")
        rules = lock.get("annotation_rules") if isinstance(lock.get("annotation_rules"), dict) else {}
        if not str(rules.get("unit") or "").strip():
            failures.append("annotation_rules_missing")
        if not str(lock.get("locked_at") or "").strip():
            failures.append("lock_moment_missing")
        scope = lock.get("scope") if isinstance(lock.get("scope"), dict) else {}
        if scope.get("locked") is not True:
            failures.append("locked_scope_missing")
        lock_sources = lock.get("sources") if isinstance(lock.get("sources"), list) else []
        if not lock_sources or not all(_source_identity_complete(item) for item in lock_sources):
            failures.append("source_identity_incomplete")
        if not str(lock.get("gold_schema_version") or lock.get("version") or "").strip():
            failures.append("versions_missing")
        train_sources = gold.get("sources") if isinstance(gold.get("sources"), list) else []
        holdout_sources = holdout.get("sources") if isinstance(holdout, dict) and isinstance(holdout.get("sources"), list) else []
        if not all(_source_identity_complete(item) for item in train_sources + holdout_sources if isinstance(item, dict)):
            failures.append("source_identity_incomplete")
    package_passages = _gold_passages(gold) + _gold_passages(holdout)
    if not _has_missed_knowledge(package_passages) or not _has_false_admit(package_passages):
        failures.append("package_roles_incomplete")
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for code in failures:
        if code not in seen:
            seen.add(code)
            unique.append(code)
    allowed = not unique
    return {
        "allowed": allowed,
        "failures": unique,
        "overlap": overlap,
        "development_regression_gold": _is_development_regression_gold(gold),
    }


def gold_supports_independent_quality_claim(
    gold: dict[str, Any] | None,
    *,
    holdout: dict[str, Any] | None = None,
    lock: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> bool:
    return independent_quality_claim_checks(
        gold, holdout=holdout, lock=lock, repo_root=repo_root
    )["allowed"]


def extract_quality_claim_allowed(
    objects: list[dict[str, Any]],
    gold: dict[str, Any] | None = None,
    *,
    holdout: dict[str, Any] | None = None,
    lock: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> bool:
    del objects
    return gold_supports_independent_quality_claim(
        gold, holdout=holdout, lock=lock, repo_root=repo_root
    )


def load_extract_gold(path: Path | str) -> dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractGoldError("gold_unreadable") from exc
    if not isinstance(data, dict):
        raise ExtractGoldError("gold_unreadable")
    return data


def _match_object(objects: list[dict[str, Any]], source_text: str) -> dict[str, Any] | None:
    needle = (source_text or "").strip()
    if not needle:
        return None
    exact = [obj for obj in objects if _text_of(obj) == needle]
    if exact:
        return exact[0]
    containing = [obj for obj in objects if needle in _text_of(obj)]
    if not containing:
        return None
    return min(containing, key=lambda obj: len(_text_of(obj)))


def _match_gold_row(rows: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
    needle = (text or "").strip()
    if not needle:
        return None
    exact = [row for row in rows if str(row.get("source_text") or "").strip() == needle]
    if exact:
        return exact[0]
    containing = [row for row in rows if needle in str(row.get("source_text") or "")]
    if containing:
        return min(containing, key=lambda row: len(str(row.get("source_text") or "")))
    contained = [row for row in rows if str(row.get("source_text") or "").strip() in needle]
    if not contained:
        return None
    return min(contained, key=lambda row: len(str(row.get("source_text") or "")))


def _status_ok(live: str, expected: str, allowed: list[str] | None) -> bool:
    if allowed:
        return live in allowed
    return live == expected


def _type_of(obj: dict[str, Any]) -> str:
    admission = admission_of(obj)
    return str(
        obj.get("confirmed_object_type")
        or confirmable_proposed_type(obj)
        or obj.get("proposed_object_type")
        or admission.get("proposed_type")
        or obj.get("object_type")
        or ""
    ).strip()


def _captured_context(obj: dict[str, Any]) -> tuple[str, str]:
    admission = admission_of(obj)
    scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
    before = str(admission.get("context_before") or scan.get("previous_paragraph") or "").strip()
    after = str(admission.get("context_after") or scan.get("next_paragraph") or "").strip()
    return before, after


def _context_complete(obj: dict[str, Any]) -> bool:
    """Captured neighbor context. ``context_scan_done`` alone is not enough."""
    admission = admission_of(obj)
    scan = admission.get("context_scan") if isinstance(admission.get("context_scan"), dict) else {}
    if scan.get("necessary_context_disposition") == "block":
        return False
    before, after = _captured_context(obj)
    return bool(before or after)


def _has_context_annotation(row: dict[str, Any]) -> bool:
    return "expected_context_before" in row or "expected_context_after" in row


def _context_matches_expected(obj: dict[str, Any], row: dict[str, Any]) -> bool:
    got_before, got_after = _captured_context(obj)
    expected_before = row.get("expected_context_before")
    expected_after = row.get("expected_context_after")
    if expected_before is not None:
        expected = _norm_text(expected_before)
        captured = _norm_text(got_before)
        if expected and expected not in captured:
            return False
        if not expected and captured:
            return False
    if expected_after is not None:
        expected = _norm_text(expected_after)
        captured = _norm_text(got_after)
        if expected and expected not in captured:
            return False
        if not expected and captured:
            return False
    return bool(got_before or got_after)


def _assign_rows_one_to_one(
    objects: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    used_objects: set[int] = set()
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        for index, obj in enumerate(objects):
            if index in used_objects:
                continue
            if _row_matches_obj(row, obj):
                used_objects.add(index)
                pairs.append((obj, row))
                break
    return pairs


def _score_selected(
    selected: list[dict[str, Any]],
    gold_rows: list[dict[str, Any]],
) -> tuple[int, int, int, int]:
    used_positive: set[int] = set()
    true_positives = 0
    false_positives = 0
    duplicates = 0
    for obj in selected:
        matched_positive = False
        duplicate = False
        matched_negative = False
        for index, row in enumerate(gold_rows):
            if not _row_matches_obj(row, obj):
                continue
            if _is_gold_positive(row):
                if index in used_positive:
                    duplicate = True
                else:
                    used_positive.add(index)
                    matched_positive = True
                break
            if _is_gold_negative(row) or not _is_gold_positive(row):
                matched_negative = True
                break
        if matched_positive:
            true_positives += 1
        else:
            false_positives += 1
            if duplicate:
                duplicates += 1
            del matched_negative
    gold_positives = [row for row in gold_rows if _is_gold_positive(row)]
    false_negatives = sum(
        1
        for index, row in enumerate(gold_rows)
        if _is_gold_positive(row) and index not in used_positive
    )
    del gold_positives
    return true_positives, false_positives, false_negatives, duplicates


def _review_burden_value(gold: dict[str, Any] | None, ordinary_count: int) -> tuple[float | None, bool]:
    if not isinstance(gold, dict):
        return None, False
    spec = gold.get("review_burden") if isinstance(gold.get("review_burden"), dict) else {}
    expected = gold.get("expected_ordinary_review_count")
    if expected is None:
        expected = spec.get("expected_ordinary_review_count")
    defined = gold.get("review_burden_defined") is True or spec.get("defined") is True or expected is not None
    if not defined:
        return None, False
    try:
        expected_n = float(expected)
    except (TypeError, ValueError):
        return None, True
    if expected_n <= 0:
        return None, True
    return round(ordinary_count / expected_n, 3), True


def _empty_metrics(*, reason: str) -> dict[str, Any]:
    return {
        "quality_claim_allowed": False,
        "reason": reason,
        **{name: None for name in EXTRACT_QUALITY_METRICS},
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "duplicate_predictions": 0,
        "assignment_unit": ASSIGNMENT_UNIT,
        "neighbor_context_present": None,
        "review_burden_defined": False,
        "coverage": {"objectify_every_sentence": False, "duty": "normative_application_critical", "sections": {}},
    }


def compute_extract_metrics(
    objects: list[dict[str, Any]],
    gold: dict[str, Any] | None = None,
    *,
    soft_scores: dict[str, Any] | None = None,
    guideline_count: int | None = None,
    holdout: dict[str, Any] | None = None,
    lock: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del soft_scores, guideline_count
    stamped = apply_passage_register(list(objects))
    passages = [obj for obj in stamped if obj.get("object_type") != "document"]
    gold_rows = _gold_passages(gold)
    if gold is not None and not gold_schema_supported(gold):
        empty = _empty_metrics(reason="gold_schema_unsupported")
        empty["coverage"] = coverage_by_section(passages)
        return empty
    if not gold_rows:
        empty = _empty_metrics(reason="gold_standard_required")
        empty["coverage"] = coverage_by_section(passages)
        return empty

    selected = [obj for obj in passages if passage_register_of(obj).get("status") == "selected_as_candidate"]
    true_positives, false_positives, false_negatives, duplicates = _score_selected(selected, gold_rows)
    pairs = _assign_rows_one_to_one(passages, gold_rows)
    matched = len(pairs)
    type_total = 0
    type_hits = 0
    annotated_total = 0
    annotated_hits = 0
    for obj, row in pairs:
        expected_type = str(row.get("expected_type") or "").strip()
        if expected_type:
            type_total += 1
            if _type_of(obj) == expected_type:
                type_hits += 1
        if _has_context_annotation(row):
            annotated_total += 1
            if _context_matches_expected(obj, row):
                annotated_hits += 1
    neighbor_total = len(selected)
    neighbor_hits = sum(1 for obj in selected if _context_complete(obj))
    ordinary = ordinary_review_queue(passages)
    burden, burden_defined = _review_burden_value(gold if isinstance(gold, dict) else None, len(ordinary))
    claim = gold_supports_independent_quality_claim(
        gold, holdout=holdout, lock=lock, repo_root=repo_root
    )
    if claim:
        reason = ""
    elif gold is not None and not gold_schema_supported(gold):
        reason = "gold_schema_unsupported"
    else:
        reason = "independent_representative_gold_required"
    predicted = true_positives + false_positives
    return {
        "quality_claim_allowed": claim,
        "reason": reason,
        "precision": round(true_positives / predicted, 3) if predicted else 0.0,
        "type_accuracy": round(type_hits / type_total, 3) if type_total else 0.0,
        "context_completeness": (
            round(annotated_hits / annotated_total, 3) if annotated_total else None
        ),
        "coverage_vs_gold": round(matched / len(gold_rows), 3),
        "review_burden": burden,
        "review_burden_defined": burden_defined,
        "neighbor_context_present": (
            round(neighbor_hits / neighbor_total, 3) if neighbor_total else 0.0
        ),
        "assignment_unit": ASSIGNMENT_UNIT,
        "duplicate_predictions": duplicates,
        "coverage": coverage_by_section(passages),
        "matched_gold_passages": matched,
        "gold_passages": len(gold_rows),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def _candidate_from_case(case: dict[str, Any]) -> dict[str, Any]:
    text = str(case.get("source_text") or case.get("candidate_text") or "")
    return build_candidate_record(
        candidate_id=str(case.get("id") or "case"),
        document_id="doc-lang",
        document_version="1.0",
        source_hash="c" * 64,
        section_path=["2 Aanbevelingen"],
        source_locator_start="lines:1-1",
        source_locator_end="lines:1-1",
        source_text_exact=text,
        candidate_text=text,
        proposed_type=str(case.get("proposed_type") or "recommendation"),
        context_before=str(case.get("context_before") or "Vorige alinea over de doelgroep."),
        context_after=str(case.get("context_after") or "Volgende alinea over vervolgonderzoek."),
    )


def _outcome(live: str | None, expected: str) -> str:
    if live == GATE_ALLOWED and expected == GATE_ALLOWED:
        return "true_admit"
    if live == GATE_ALLOWED and expected == GATE_BLOCKED:
        return "false_admit"
    if live != GATE_ALLOWED and expected == GATE_ALLOWED:
        return "miss"
    return "true_block"


def measure_admission_language_variation(
    cases: Iterable[dict[str, Any]] | None = None,
    *,
    gold: dict[str, Any] | None = None,
    objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Measure false admits and misses on language-variation cases.

    Tied to ``admission_gate_v1`` (direct ``admit_candidate``) and, when
    ``objects`` is supplied, to the extract/admission path.
    """
    rows = [dict(row) for row in (cases or [])]
    if not rows and gold:
        rows = [dict(row) for row in _gold_passages(gold)]

    report_cases: list[dict[str, Any]] = []
    buckets: dict[str, list[dict[str, Any]]] = {
        "true_admit": [],
        "false_admit": [],
        "miss": [],
        "true_block": [],
    }
    stamped = apply_passage_register(list(objects)) if objects is not None else None
    for row in rows:
        expected = str(row.get("expected_gate") or GATE_BLOCKED)
        if stamped is not None:
            obj = _match_object(stamped, str(row.get("source_text") or ""))
            live = str(admission_of(obj).get("gate_result") or "") if obj is not None else ""
            if not live and obj is not None and passage_register_of(obj).get("status") == "selected_as_candidate":
                live = GATE_ALLOWED
            codes = list(admission_of(obj).get("reason_codes") or []) if obj is not None else ["not_extracted"]
        else:
            admitted = admit_candidate(_candidate_from_case(row))
            live = str(admitted.get("gate_result") or "")
            codes = list(admitted.get("reason_codes") or [])
        outcome = _outcome(live or None, expected)
        item = {
            **row,
            "live_gate": live or GATE_BLOCKED,
            "outcome": outcome,
            "reason_codes": codes,
        }
        report_cases.append(item)
        buckets[outcome].append(item)

    true_admits = buckets["true_admit"]
    false_admits = buckets["false_admit"]
    misses = buckets["miss"]
    true_blocks = buckets["true_block"]
    tp = len(true_admits)
    fp = len(false_admits)
    fn = len(misses)
    return {
        "cases": report_cases,
        "true_admits": true_admits,
        "false_admits": false_admits,
        "misses": misses,
        "true_blocks": true_blocks,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(tp / (tp + fp), 3) if (tp + fp) else 0.0,
        "recall": round(tp / (tp + fn), 3) if (tp + fn) else 0.0,
    }

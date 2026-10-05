"""Read-only forensic trace of one source span through recorded decisions.

This module does not form passages, call a provider, write a database, or
decide publication. WorkingRevision evidence stays the authority. A missing
stage stays unknown. Text is never used to couple two spans.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZipFile


TRACE_VERSION = "forensic-trace-v1"
EVIDENCE_KIND = "forensic-evidence-v1"
GOLD_VERSION = "forensic-gold-v1"
UNKNOWN = "UNKNOWN"

STAGES = (
    "source",
    "reconstruction",
    "formation_target",
    "provider_decision",
    "semantic_validation",
    "transformation",
    "admission",
    "source_accountability",
    "review_projection",
    "publication_effect",
)
DIVERGENCE_CLASS = {
    "identity": "identity",
    "source": "source",
    "reconstruction": "source",
    "formation_target": "formation",
    "provider_decision": "semantic",
    "semantic_validation": "semantic",
    "transformation": "lifecycle",
    "admission": "lifecycle",
    "source_accountability": "lifecycle",
    "review_projection": "lifecycle",
    "publication_effect": "lifecycle",
}
IDENTITY_FIELDS = (
    "snapshot_id",
    "working_revision_id",
    "objects_revision",
    "source_sha256",
    "deployed_commit",
    "parser_version",
    "source_reconstruction_version",
    "source_reconstruction_hash",
    "passage_formation_mode",
    "field_contract",
    "task_policy",
    "prompt_hash",
    "schema_hash",
    "validator_identity",
    "model",
    "provider_contract_version",
    "attempt_id",
)
NON_OBJECT_FUNCTIONS = frozenset({
    "metadata", "structure", "background", "context", "support", "unresolved",
})
PASSAGE_DISPOSITIONS = frozenset({
    "selected_as_candidate", "used_as_context", "linked_as_support",
    "excluded_with_reason", "not_yet_assessed", "unresolved",
})
CSV_FIELDS = (
    "source_span_id", "page", "section_path", "source_text", "task_id",
    "provider_decision", "proposed_object_type", "source_assessment_role",
    "validator_result", "validator_reason", "object_id", "admission_result",
    "passage_disposition", "review_visible", "expected_function",
    "expected_object_type", "first_divergence_stage", "verdict",
    "trace_evidence_status",
)
DIVERGENCE_FIELDS = (
    "case_id", "source_span_id", "verdict", "first_divergence_stage",
    "divergence_class", "expected_function", "expected_object_type",
    "actual_provider_decision", "actual_proposed_object_type",
)


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_span_id(*, source_sha256: str, source_reconstruction_hash: str,
                   source_fragment_ids: list[str], start: int, end: int) -> str | None:
    """Identity of one reconstructed range. Not defined when a component is missing."""
    if (not source_sha256 or not source_reconstruction_hash
            or not source_fragment_ids or type(start) is not int or type(end) is not int
            or start < 0 or end <= start):
        return None
    if not all(isinstance(item, str) and item for item in source_fragment_ids):
        return None
    return _hash({
        "v": 1,
        "source_sha256": source_sha256,
        "source_reconstruction_hash": source_reconstruction_hash,
        "source_fragment_ids": list(source_fragment_ids),
        "start": start,
        "end": end,
    })


def _unknown_stage() -> dict[str, Any]:
    return {"status": "unknown"}


def _recorded(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "recorded", **payload}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _csv_bytes(fields: tuple[str, ...], rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        cells = {}
        for field in fields:
            cell = _cell(row.get(field))
            if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(("\t", "\r", "\n")):
                cell = "'" + cell
            cells[field] = cell
        writer.writerow(cells)
    return output.getvalue().encode("utf-8-sig")


def _parse_cell(value: str) -> Any:
    text = value.strip()
    if text.startswith("'") and len(text) > 1 and text[1] in "=-+@\t":
        text = text[1:]
    if text == "":
        return None
    if text[:1] in "{[":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _read_csv(archive: ZipFile, name: str) -> list[dict[str, Any]]:
    try:
        raw = archive.read(name)
    except KeyError:
        return []
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    return [{key: _parse_cell(value) for key, value in row.items()} for row in rows]


def _identity_from(components: Mapping[str, Any]) -> dict[str, Any]:
    identity = {field: None for field in IDENTITY_FIELDS}
    aliases = {
        "source_sha256": ("source_sha256",),
        "source_reconstruction_version": ("reconstruction_version", "source_reconstruction_version"),
        "source_reconstruction_hash": ("source_blocks_hash", "source_reconstruction_hash"),
        "parser_version": ("extractor_version", "parser_version"),
        "task_policy": ("formation_policy_version", "task_policy"),
        "field_contract": ("semantic_contract_version", "field_contract"),
        "model": ("model_id", "model"),
        "prompt_hash": ("prompt_hash",),
        "schema_hash": ("schema_hash",),
        "snapshot_id": ("snapshot_id",),
    }
    for field, keys in aliases.items():
        for key in keys:
            if components.get(key) not in (None, ""):
                identity[field] = str(components[key])
                break
    return identity


def _span_shell(*, fragment_ids: list[str], start: int, end: int, raw_text: Any,
                clean_text: Any, page: Any, locator: Any, section_path: Any,
                block_id: Any, block_start: Any, block_end: Any) -> dict[str, Any]:
    source = _unknown_stage() if raw_text in (None, "") else _recorded({
        "source_fragment_ids": list(fragment_ids),
        "raw_text": raw_text,
        "clean_text": clean_text if clean_text not in (None, "") else raw_text,
        "source_page": page,
        "source_locator": locator,
        "section_path": list(section_path or []),
        "start": start,
        "end": end,
    })
    reconstruction = _unknown_stage() if not block_id else _recorded({
        "semantic_block_id": block_id,
        "block_start": block_start,
        "block_end": block_end,
        "section_role": None,
    })
    return {
        "source_fragment_ids": list(fragment_ids),
        "start": start,
        "end": end,
        "source": source,
        "reconstruction": reconstruction,
        "formation": _unknown_stage(),
        "provider": _unknown_stage(),
        "validation": _unknown_stage(),
        "transformation": _unknown_stage(),
        "admission": _unknown_stage(),
        "source_accountability": _unknown_stage(),
        "review_projection": _unknown_stage(),
        "publication_effect": _unknown_stage(),
    }


def _exact_span(candidate: Any, block_id: Any, start: Any, end: Any) -> bool:
    return (isinstance(candidate, dict) and candidate.get("block_id") == block_id
            and candidate.get("start") == start and candidate.get("end") == end)


def _attach_formation(span: dict[str, Any], tasks: list[dict[str, Any]], task_policy: Any) -> None:
    block = (span.get("reconstruction") or {}).get("semantic_block_id")
    start, end = span.get("start"), span.get("end")
    matches = []
    for task in tasks:
        targets = task.get("target_spans") or []
        if isinstance(targets, str):
            continue
        if any(_exact_span(target, block, start, end) for target in targets):
            matches.append(task)
    if len(matches) != 1:
        return
    task = matches[0]
    span["formation"] = _recorded({
        "task_id": task.get("task_id"),
        "phase": task.get("phase"),
        "selectable_range": {"block_id": block, "start": start, "end": end},
        "context_only_block_ids": [],
        "task_policy": task_policy,
        "selectable": task.get("status") not in {"not_selectable", "excluded"},
    })


def _objects_for_span(span: dict[str, Any], objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    block = (span.get("reconstruction") or {}).get("semantic_block_id")
    start, end = span.get("start"), span.get("end")
    found = []
    for obj in objects:
        semantic = ((obj.get("metadata") or {}).get("semantic_passage") or {})
        spans = semantic.get("spans") or []
        if any(_exact_span(item, block, start, end) for item in spans):
            found.append(obj)
    return found


def evidence_from_stored(*, snapshot_id: str, revision: str, envelope: Mapping[str, Any],
                         objects: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Project stored envelope evidence. Absent stages stay unknown."""
    replay = envelope.get("semantic_replay") if isinstance(envelope.get("semantic_replay"), dict) else {}
    components = (replay.get("identity") or {}).get("components") if isinstance(replay.get("identity"), dict) else {}
    components = components if isinstance(components, dict) else {}
    identity = _identity_from(components)
    identity["snapshot_id"] = identity["snapshot_id"] or snapshot_id
    identity["objects_revision"] = revision
    runs = envelope.get("quality_processing_runs") or []
    if runs and not identity["source_sha256"]:
        identity["source_sha256"] = runs[0].get("source_hash")
    provider = replay.get("provider_evidence") if isinstance(replay.get("provider_evidence"), dict) else {}
    if provider.get("task_policy") and not identity["task_policy"]:
        identity["task_policy"] = provider.get("task_policy")
    if provider.get("deployed_commit") and not identity["deployed_commit"]:
        identity["deployed_commit"] = provider.get("deployed_commit")
    omitted: list[str] = []
    for attempt in envelope.get("processing_attempts") or []:
        diagnostic = attempt.get("diagnostic") or {}
        omitted.extend(str(item) for item in (diagnostic.get("omitted_evidence") or []))
        if diagnostic.get("deployed_commit") and not identity["deployed_commit"]:
            identity["deployed_commit"] = diagnostic.get("deployed_commit")
        if diagnostic.get("model") and not identity["model"]:
            identity["model"] = diagnostic.get("model")
        if attempt.get("attempt_id") and not identity["attempt_id"]:
            identity["attempt_id"] = attempt.get("attempt_id")
    proposal = replay.get("proposal") if isinstance(replay.get("proposal"), dict) else {}
    validation = replay.get("validation")
    spans: list[dict[str, Any]] = []
    for raw in proposal.get("objects") or []:
        if not isinstance(raw, dict):
            continue
        for item in raw.get("spans") or []:
            if not isinstance(item, dict):
                continue
            span = _span_shell(
                fragment_ids=[], start=item.get("start"), end=item.get("end"),
                raw_text=None, clean_text=None, page=None, locator=None,
                section_path=raw.get("section_path"), block_id=item.get("block_id"),
                block_start=item.get("start"), block_end=item.get("end"))
            span["provider"] = _recorded({
                "provider_call_id": None,
                "selected": True,
                "proposed_object_type": raw.get("proposed_object_type"),
                "source_assessment_role": None,
                "proposal_ref": "semantic_replay.proposal.objects",
            })
            if validation not in (None, ""):
                span["validation"] = _recorded({
                    "validator_result": "accepted" if validation == "passed" else validation,
                    "reason_code": None,
                    "finding": None,
                })
            spans.append(span)
    for raw in proposal.get("source_assessments") or []:
        if not isinstance(raw, dict) or not isinstance(raw.get("span"), dict):
            continue
        item = raw["span"]
        span = _span_shell(
            fragment_ids=[], start=item.get("start"), end=item.get("end"),
            raw_text=None, clean_text=None, page=None, locator=None,
            section_path=None, block_id=item.get("block_id"),
            block_start=item.get("start"), block_end=item.get("end"))
        span["provider"] = _recorded({
            "provider_call_id": None,
            "selected": False,
            "proposed_object_type": None,
            "source_assessment_role": raw.get("role"),
            "proposal_ref": "semantic_replay.proposal.source_assessments",
        })
        if validation not in (None, ""):
            span["validation"] = _recorded({
                "validator_result": "accepted" if validation == "passed" else validation,
                "reason_code": None,
                "finding": None,
            })
        role = raw.get("role")
        if role in PASSAGE_DISPOSITIONS or role == "unresolved":
            disposition = "unresolved" if role == "unresolved" else None
        else:
            disposition = None
        span["source_accountability"] = _recorded({
            "source_role": role,
            "passage_disposition": disposition,
        })
        spans.append(span)
    tasks = provider.get("tasks") if isinstance(provider.get("tasks"), list) else []
    for span in spans:
        _attach_formation(span, tasks, identity.get("task_policy"))
        if objects is None:
            continue
        matches = _objects_for_span(span, objects)
        if len(matches) != 1:
            continue
        obj = matches[0]
        admission = (obj.get("metadata") or {}).get("admission") or {}
        register = (obj.get("metadata") or {}).get("passage_register") or {}
        span["transformation"] = _recorded({
            "object_id": obj.get("object_id"),
            "object_version": obj.get("object_version"),
            "canonical_object_hash": obj.get("canonical_hash"),
            "proposed_object_type": obj.get("proposed_object_type"),
        })
        if admission:
            span["admission"] = _recorded({
                "gate_result": admission.get("gate_result"),
                "reason_codes": list(admission.get("reason_codes") or []),
            })
            gate = admission.get("gate_result")
            if gate in {"allowed", "blocked"}:
                span["review_projection"] = _recorded({
                    "shown_as_review_candidate": gate == "allowed",
                    "review_status": register.get("status"),
                    "review_decision": None,
                    "evidence_kind": "derived_from_stored_admission_not_a_review_log",
                })
        status = register.get("status")
        if status in PASSAGE_DISPOSITIONS:
            current = span["source_accountability"]
            role = current.get("source_role") if current.get("status") == "recorded" else None
            span["source_accountability"] = _recorded({
                "source_role": role,
                "passage_disposition": status,
            })
    for run in runs:
        for fragment in run.get("source_fragments") or []:
            text = fragment.get("raw_text")
            if not isinstance(text, str) or fragment.get("fragment_id") in (None, ""):
                continue
            spans.append(_span_shell(
                fragment_ids=[str(fragment["fragment_id"])], start=0, end=len(text),
                raw_text=text, clean_text=fragment.get("clean_text"),
                page=fragment.get("source_page"), locator=fragment.get("source_locator"),
                section_path=fragment.get("section_path"), block_id=None,
                block_start=None, block_end=None))
    completeness = "unavailable" if not spans else "partial"
    if omitted:
        completeness = "partial"
    return {
        "evidence_kind": EVIDENCE_KIND,
        "evidence_completeness": completeness,
        "omitted_evidence": sorted(set(omitted)),
        "identity": identity,
        "spans": spans,
        "projection": "stored_evidence_join_not_a_new_authority",
    }


def load_evidence(path: Path) -> dict[str, Any]:
    if path.suffix.casefold() == ".zip":
        return evidence_from_zip(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("evidence_kind") != EVIDENCE_KIND:
        raise ValueError("forensic_evidence_kind_invalid")
    return payload


def evidence_from_zip(path: Path) -> dict[str, Any]:
    with ZipFile(path) as archive:
        revision_rows = _read_csv(archive, "revision.csv")
        proposals = _read_csv(archive, "semantic_proposals.csv")
        tasks = _read_csv(archive, "formation_tasks.csv")
        views = _read_csv(archive, "source_views.csv")
        attempts = _read_csv(archive, "attempt_diagnostics.csv")
        runs = _read_csv(archive, "runs.csv")
        manifest = _read_csv(archive, "manifest.csv")
    revision = revision_rows[0] if revision_rows else {}
    proposal_row = proposals[0] if proposals else {}
    proposal = proposal_row.get("proposal") if isinstance(proposal_row.get("proposal"), dict) else {}
    identity = proposal_row.get("identity") if isinstance(proposal_row.get("identity"), dict) else {}
    omitted: list[str] = []
    attempt_rows = []
    for row in attempts:
        diagnostic = row.get("diagnostic") if isinstance(row.get("diagnostic"), dict) else {}
        omitted.extend(str(item) for item in (diagnostic.get("omitted_evidence") or []))
        attempt_rows.append({
            "attempt_id": row.get("attempt_id"),
            "diagnostic": diagnostic,
        })
    envelope = {
        "semantic_replay": {
            "identity": identity if isinstance(identity, dict) else {},
            "proposal": proposal if isinstance(proposal, dict) else {},
            "validation": proposal_row.get("validation"),
            "provider_evidence": {
                "task_policy": (tasks[0].get("policy_version") if tasks else None),
                "tasks": [{
                    "task_id": task.get("task_id"),
                    "section_path": task.get("section_path"),
                    "target_spans": task.get("target_spans") or [],
                    "phase": task.get("phase"),
                    "status": task.get("status"),
                } for task in tasks],
                "deployed_commit": None,
            },
        },
        "quality_processing_runs": [{
            "source_hash": (runs[0].get("source_hash") if runs else None),
            "source_fragments": [{
                "fragment_id": view.get("fragment_id"),
                "raw_text": view.get("raw_text"),
                "clean_text": view.get("clean_text"),
                "source_page": view.get("source_page"),
                "source_locator": view.get("source_locator"),
            } for view in views if view.get("fragment_id")],
        }] if views or runs else [],
        "processing_attempts": attempt_rows,
    }
    evidence = evidence_from_stored(
        snapshot_id=str(revision.get("snapshot_id") or ""),
        revision=str(revision.get("objects_revision") or revision.get("revision_id") or ""),
        envelope=envelope,
        objects=None,
    )
    partial_datasets = [row.get("dataset") for row in manifest if row.get("availability") in {"partial", "not_recorded", "not_exported"}]
    if partial_datasets or omitted or evidence["evidence_completeness"] != "complete":
        evidence["evidence_completeness"] = "partial" if evidence["spans"] or omitted else "unavailable"
    evidence["omitted_evidence"] = sorted(set([*evidence["omitted_evidence"], *omitted]))
    return evidence


def load_gold(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("gold_version") != GOLD_VERSION:
        raise ValueError("forensic_gold_version_invalid")
    if not isinstance(payload.get("cases"), list):
        raise ValueError("forensic_gold_cases_invalid")
    return payload


def _identity_mismatch(evidence: Mapping[str, Any], gold: Mapping[str, Any]) -> list[str]:
    expected = gold.get("expected_identity") or {}
    recorded = evidence.get("identity") or {}
    mismatched = []
    for key, value in expected.items():
        if key not in IDENTITY_FIELDS or recorded.get(key) != value:
            mismatched.append(key)
    return mismatched


def _case_span_id(case: Mapping[str, Any]) -> str | None:
    return source_span_id(
        source_sha256=str(case.get("source_sha256") or ""),
        source_reconstruction_hash=str(case.get("source_reconstruction_hash") or ""),
        source_fragment_ids=list(case.get("source_fragment_ids") or []),
        start=case.get("start"),
        end=case.get("end"),
    )


def _provider_judgement(case: Mapping[str, Any], provider: Mapping[str, Any]) -> str:
    if provider.get("status") != "recorded":
        return "unknown"
    expected_type = case.get("expected_object_type")
    expected_function = case.get("expected_source_function")
    expected_bearing = case.get("expected_answer_bearing")
    selected = provider.get("selected")
    proposed = provider.get("proposed_object_type")
    role = provider.get("source_assessment_role")
    if expected_type is None:
        if expected_function not in NON_OBJECT_FUNCTIONS:
            return "unknown"
        if selected or proposed not in (None, ""):
            return "fail"
        if role != expected_function:
            return "fail"
        if expected_bearing is True or (expected_bearing is False and role == "answer_bearing"):
            return "fail"
        return "pass"
    if selected is not True or proposed != expected_type:
        return "fail"
    if expected_bearing is False:
        return "fail"
    return "pass"


def _stage_judgement(stage: str, case: Mapping[str, Any], span: Mapping[str, Any]) -> str:
    if stage == "source":
        source = span.get("source") or {}
        if source.get("status") != "recorded":
            return "unknown"
        exact = case.get("exact_raw_text")
        if isinstance(exact, str) and source.get("raw_text") != exact:
            return "fail"
        return "pass"
    if stage == "reconstruction":
        return "pass" if (span.get("reconstruction") or {}).get("status") == "recorded" else "unknown"
    if stage == "formation_target":
        formation = span.get("formation") or {}
        if formation.get("status") != "recorded":
            return "unknown"
        return "fail" if formation.get("selectable") is False else "pass"
    if stage == "provider_decision":
        return _provider_judgement(case, span.get("provider") or {})
    if stage == "semantic_validation":
        validation = span.get("validation") or {}
        if validation.get("status") != "recorded":
            return "unknown"
        expected = case.get("expected_validator_result")
        if expected is not None and validation.get("validator_result") != expected:
            return "fail"
        return "pass"
    if stage == "transformation":
        formed = span.get("transformation") or {}
        if formed.get("status") != "recorded":
            return "unknown"
        expected_type = case.get("expected_object_type")
        actual_id = formed.get("object_id")
        actual_type = formed.get("proposed_object_type")
        if expected_type is None:
            return "fail" if actual_id not in (None, "") else "pass"
        if actual_id in (None, "") or actual_type != expected_type:
            return "fail"
        return "pass"
    if stage == "admission":
        admission = span.get("admission") or {}
        if admission.get("status") != "recorded":
            return "unknown"
        expected = case.get("expected_gate_result")
        if expected is not None and admission.get("gate_result") != expected:
            return "fail"
        return "pass"
    if stage == "source_accountability":
        account = span.get("source_accountability") or {}
        if account.get("status") != "recorded":
            return "unknown"
        expected = case.get("expected_passage_disposition")
        if expected is not None and account.get("passage_disposition") != expected:
            return "fail"
        return "pass"
    if stage == "review_projection":
        review = span.get("review_projection") or {}
        if review.get("status") != "recorded":
            return "unknown"
        expected = case.get("expected_review_visible")
        if expected is not None and review.get("shown_as_review_candidate") is not expected:
            return "fail"
        return "pass"
    publication = span.get("publication_effect") or {}
    if publication.get("status") != "recorded":
        return "unknown"
    expected = case.get("expected_blocks_publication")
    if expected is not None and publication.get("blocks_publication") is not expected:
        return "fail"
    return "pass"


def _grade_span(case: Mapping[str, Any], span: Mapping[str, Any]) -> dict[str, Any]:
    first = None
    verdict = "PASS"
    judgements = {}
    for stage in STAGES:
        judgement = _stage_judgement(stage, case, span)
        judgements[stage] = judgement
        if judgement == "fail":
            first = stage
            verdict = "FAIL"
            break
        if judgement == "unknown":
            first = stage
            verdict = "INCOMPLETE"
            break
    return {
        "verdict": verdict,
        "first_divergence_stage": first,
        "divergence_class": DIVERGENCE_CLASS.get(first or "", None),
        "stage_judgements": judgements,
    }


def _public_span(evidence: Mapping[str, Any], span: Mapping[str, Any]) -> dict[str, Any]:
    identity = evidence.get("identity") or {}
    span_id = source_span_id(
        source_sha256=str(identity.get("source_sha256") or ""),
        source_reconstruction_hash=str(identity.get("source_reconstruction_hash") or ""),
        source_fragment_ids=list(span.get("source_fragment_ids") or []),
        start=span.get("start") if type(span.get("start")) is int else -1,
        end=span.get("end") if type(span.get("end")) is int else -1,
    )
    return {
        "trace_version": TRACE_VERSION,
        "source_span_id": span_id,
        "span_identity_status": "source_span" if span_id else "not_a_source_span",
        "source": span.get("source") or _unknown_stage(),
        "reconstruction": span.get("reconstruction") or _unknown_stage(),
        "formation": span.get("formation") or _unknown_stage(),
        "provider": span.get("provider") or _unknown_stage(),
        "validation": span.get("validation") or _unknown_stage(),
        "transformation": span.get("transformation") or _unknown_stage(),
        "admission": span.get("admission") or _unknown_stage(),
        "source_accountability": span.get("source_accountability") or _unknown_stage(),
        "review_projection": span.get("review_projection") or _unknown_stage(),
        "publication_effect": span.get("publication_effect") or _unknown_stage(),
        "expectation": None,
        "first_divergence": None,
    }


def _index_spans(evidence: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for span in evidence.get("spans") or []:
        public = _public_span(evidence, span)
        span_id = public.get("source_span_id")
        if span_id and span_id not in indexed:
            indexed[span_id] = public
    return indexed


def trace(evidence: Mapping[str, Any], gold: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if evidence.get("evidence_kind") != EVIDENCE_KIND:
        raise ValueError("forensic_evidence_kind_invalid")
    indexed = _index_spans(evidence)
    records = sorted(indexed.values(), key=lambda row: row.get("source_span_id") or "")
    unindexed = []
    for span in evidence.get("spans") or []:
        public = _public_span(evidence, span)
        if public.get("source_span_id") is None:
            unindexed.append(public)
    completeness = evidence.get("evidence_completeness") or "partial"
    omitted = list(evidence.get("omitted_evidence") or [])
    summary: dict[str, Any] = {
        "trace_version": TRACE_VERSION,
        "trace_evidence_status": completeness,
        "omitted_evidence": omitted,
        "identity": {field: (evidence.get("identity") or {}).get(field) for field in IDENTITY_FIELDS},
        "comparison": "ungraded",
        "span_count": len(records),
        "unindexed_span_count": len(unindexed),
        "verdicts": {},
        "first_divergence_counts": {},
        "divergence_classes": {},
    }
    divergences: list[dict[str, Any]] = []
    if gold is None:
        summary["records_without_grades"] = True
        return {"records": [*records, *unindexed], "summary": summary, "divergences": divergences}

    mismatched = _identity_mismatch(evidence, gold)
    if mismatched:
        summary["comparison"] = "TRACE_IDENTITY_MISMATCH"
        summary["mismatched_identity_fields"] = mismatched
        for case in gold.get("cases") or []:
            divergences.append({
                "case_id": case.get("case_id"),
                "source_span_id": _case_span_id(case),
                "verdict": "TRACE_IDENTITY_MISMATCH",
                "first_divergence_stage": "identity",
                "divergence_class": "identity",
                "expected_function": case.get("expected_source_function"),
                "expected_object_type": case.get("expected_object_type"),
                "actual_provider_decision": None,
                "actual_proposed_object_type": None,
            })
        summary["verdicts"] = {"TRACE_IDENTITY_MISMATCH": len(divergences)}
        summary["first_divergence_counts"] = {"identity": len(divergences)}
        summary["divergence_classes"] = {"identity": len(divergences)}
        return {"records": [*records, *unindexed], "summary": summary, "divergences": divergences}

    summary["comparison"] = "compared"
    by_id = {row["source_span_id"]: row for row in records}
    for case in gold.get("cases") or []:
        span_id = _case_span_id(case)
        recorded_hash = (evidence.get("identity") or {}).get("source_reconstruction_hash")
        if case.get("source_reconstruction_hash") != recorded_hash:
            row = {
                "case_id": case.get("case_id"), "source_span_id": span_id,
                "verdict": "INCOMPATIBLE_RECONSTRUCTION", "first_divergence_stage": "reconstruction",
                "divergence_class": "source", "expected_function": case.get("expected_source_function"),
                "expected_object_type": case.get("expected_object_type"),
                "actual_provider_decision": None, "actual_proposed_object_type": None,
            }
            divergences.append(row)
            continue
        public = by_id.get(span_id) if span_id else None
        if public is None:
            divergences.append({
                "case_id": case.get("case_id"), "source_span_id": span_id,
                "verdict": "UNLOCATED", "first_divergence_stage": "source",
                "divergence_class": "source", "expected_function": case.get("expected_source_function"),
                "expected_object_type": case.get("expected_object_type"),
                "actual_provider_decision": None, "actual_proposed_object_type": None,
            })
            continue
        graded = _grade_span(case, public)
        provider = public.get("provider") or {}
        public["expectation"] = {
            "case_id": case.get("case_id"),
            "expected_source_function": case.get("expected_source_function"),
            "expected_answer_bearing": case.get("expected_answer_bearing"),
            "expected_object_type": case.get("expected_object_type"),
        }
        public["first_divergence"] = {
            "stage": graded["first_divergence_stage"],
            "divergence_class": graded["divergence_class"],
            "verdict": graded["verdict"],
            "stage_judgements": graded["stage_judgements"],
        }
        actual_decision = None if provider.get("status") != "recorded" else (
            "selected" if provider.get("selected") else "not_selected")
        divergences.append({
            "case_id": case.get("case_id"),
            "source_span_id": span_id,
            "verdict": graded["verdict"],
            "first_divergence_stage": graded["first_divergence_stage"],
            "divergence_class": graded["divergence_class"],
            "expected_function": case.get("expected_source_function"),
            "expected_object_type": case.get("expected_object_type"),
            "actual_provider_decision": actual_decision,
            "actual_proposed_object_type": provider.get("proposed_object_type") if provider.get("status") == "recorded" else None,
        })
    counts: dict[str, int] = {}
    stages: dict[str, int] = {}
    classes: dict[str, int] = {}
    for row in divergences:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        stage = row.get("first_divergence_stage")
        if stage:
            stages[stage] = stages.get(stage, 0) + 1
            classes[row["divergence_class"]] = classes.get(row["divergence_class"], 0) + 1
    summary["verdicts"] = counts
    summary["first_divergence_counts"] = stages
    summary["divergence_classes"] = classes
    return {"records": [*records, *unindexed], "summary": summary, "divergences": divergences}


def _csv_row(record: Mapping[str, Any], evidence_status: str) -> dict[str, Any]:
    source = record.get("source") or {}
    formation = record.get("formation") or {}
    provider = record.get("provider") or {}
    validation = record.get("validation") or {}
    formed = record.get("transformation") or {}
    admission = record.get("admission") or {}
    account = record.get("source_accountability") or {}
    review = record.get("review_projection") or {}
    expectation = record.get("expectation") or {}
    divergence = record.get("first_divergence") or {}
    section = source.get("section_path") if source.get("status") == "recorded" else None
    return {
        "source_span_id": record.get("source_span_id") or UNKNOWN,
        "page": source.get("source_page") if source.get("status") == "recorded" else UNKNOWN,
        "section_path": " > ".join(section) if isinstance(section, list) else UNKNOWN,
        "source_text": source.get("raw_text") if source.get("status") == "recorded" else UNKNOWN,
        "task_id": formation.get("task_id") if formation.get("status") == "recorded" else UNKNOWN,
        "provider_decision": ("selected" if provider.get("selected") else "not_selected") if provider.get("status") == "recorded" else UNKNOWN,
        "proposed_object_type": provider.get("proposed_object_type") if provider.get("status") == "recorded" else UNKNOWN,
        "source_assessment_role": provider.get("source_assessment_role") if provider.get("status") == "recorded" else UNKNOWN,
        "validator_result": validation.get("validator_result") if validation.get("status") == "recorded" else UNKNOWN,
        "validator_reason": validation.get("reason_code") if validation.get("status") == "recorded" else UNKNOWN,
        "object_id": formed.get("object_id") if formed.get("status") == "recorded" else UNKNOWN,
        "admission_result": admission.get("gate_result") if admission.get("status") == "recorded" else UNKNOWN,
        "passage_disposition": account.get("passage_disposition") if account.get("status") == "recorded" else UNKNOWN,
        "review_visible": review.get("shown_as_review_candidate") if review.get("status") == "recorded" else UNKNOWN,
        "expected_function": expectation.get("expected_source_function"),
        "expected_object_type": expectation.get("expected_object_type"),
        "first_divergence_stage": divergence.get("stage"),
        "verdict": divergence.get("verdict"),
        "trace_evidence_status": evidence_status,
    }


def compare_traces(base: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Differential of two traces of the same frozen source. No heuristic coupling."""
    base_identity = base["summary"]["identity"]
    candidate_identity = candidate["summary"]["identity"]
    if (base_identity.get("source_sha256") != candidate_identity.get("source_sha256")
            or base_identity.get("source_reconstruction_hash") != candidate_identity.get("source_reconstruction_hash")
            or not base_identity.get("source_sha256") or not base_identity.get("source_reconstruction_hash")):
        return {"comparison": "incompatible_reconstruction", "rows": []}
    def actuals(result: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        rows = {}
        for record in result["records"]:
            span_id = record.get("source_span_id")
            if not span_id:
                continue
            provider = record.get("provider") or {}
            formed = record.get("transformation") or {}
            divergence = record.get("first_divergence") or {}
            rows[span_id] = {
                "proposed_object_type": provider.get("proposed_object_type") if provider.get("status") == "recorded" else UNKNOWN,
                "selected": provider.get("selected") if provider.get("status") == "recorded" else UNKNOWN,
                "object_id": formed.get("object_id") if formed.get("status") == "recorded" else UNKNOWN,
                "object_type": formed.get("proposed_object_type") if formed.get("status") == "recorded" else UNKNOWN,
                "first_divergence_stage": divergence.get("stage"),
                "verdict": divergence.get("verdict"),
            }
        return rows
    before, after = actuals(base), actuals(candidate)
    shared = sorted(set(before) & set(after))
    return {
        "comparison": "differential",
        "same_frozen_source": True,
        "spans_unchanged": sum(1 for span_id in shared if before[span_id] == after[span_id]),
        "objects_added": [span_id for span_id in shared if before[span_id]["object_id"] in (None, "", UNKNOWN) and after[span_id]["object_id"] not in (None, "", UNKNOWN)],
        "objects_removed": [span_id for span_id in shared if before[span_id]["object_id"] not in (None, "", UNKNOWN) and after[span_id]["object_id"] in (None, "", UNKNOWN)],
        "object_type_changed": [span_id for span_id in shared if before[span_id]["object_type"] != after[span_id]["object_type"]],
        "source_role_changed": [span_id for span_id in shared if before[span_id]["proposed_object_type"] != after[span_id]["proposed_object_type"] or before[span_id]["selected"] != after[span_id]["selected"]],
        "first_divergence_changed": [span_id for span_id in shared if before[span_id]["first_divergence_stage"] != after[span_id]["first_divergence_stage"] or before[span_id]["verdict"] != after[span_id]["verdict"]],
        "spans_only_in_base": sorted(set(before) - set(after)),
        "spans_only_in_candidate": sorted(set(after) - set(before)),
    }


def write_outputs(result: Mapping[str, Any], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    status = result["summary"]["trace_evidence_status"]
    records = sorted(result["records"], key=lambda row: (row.get("source_span_id") is None, row.get("source_span_id") or ""))
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in records]
    (directory / "forensic_trace.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    (directory / "forensic_trace.csv").write_bytes(_csv_bytes(CSV_FIELDS, [_csv_row(record, status) for record in records]))
    (directory / "forensic_summary.json").write_text(
        json.dumps(result["summary"], ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if result["divergences"]:
        (directory / "first_divergence.csv").write_bytes(_csv_bytes(DIVERGENCE_FIELDS, result["divergences"]))


def rows_for_export(*, snapshot_id: str, revision: str, envelope: Mapping[str, Any],
                    objects: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, str]:
    evidence = evidence_from_stored(snapshot_id=snapshot_id, revision=revision, envelope=envelope, objects=objects)
    projected = trace(evidence)
    rows = [_csv_row(record, evidence["evidence_completeness"]) for record in projected["records"]]
    if not rows and not evidence["spans"]:
        availability = "not_recorded"
    else:
        availability = "partial" if evidence["evidence_completeness"] != "complete" else "derived"
    limitation = (
        "Derived join of recorded evidence by exact block span or exact fragment identity. "
        "Not a source-span identity when fragment ids are absent. Missing stages stay UNKNOWN. "
        "Not approval, publication, or clinical completeness."
    )
    return rows, availability, limitation

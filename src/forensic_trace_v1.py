"""Read-only forensic trace of one source span through recorded decisions.

This module does not form passages, call a provider, write a database, or
decide publication. WorkingRevision evidence stays the authority. A missing
stage stays unknown. Text is never used to couple two spans. The review stage
is a review-queue projection from stored admission and the passage register,
not a human review decision.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
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
                   source_fragment_ids: list[str] | None = None, start: int | None = None,
                   end: int | None = None, fragments: list[dict[str, Any]] | None = None,
                   block_id: str | None = None, block_start: int | None = None,
                   block_end: int | None = None) -> str | None:
    """Identity of one source range, with reconstructed bounds when they are recorded."""
    ranges = fragments
    if ranges is None:
        ids = list(source_fragment_ids or [])
        if len(ids) == 1 and type(start) is int and type(end) is int and 0 <= start < end:
            ranges = [{"fragment_id": ids[0], "start": start, "end": end}]
        else:
            ranges = []
    normalized = []
    for item in ranges:
        if not isinstance(item, dict):
            return None
        fragment_id = item.get("fragment_id")
        lo, hi = item.get("start"), item.get("end")
        if (not isinstance(fragment_id, str) or not fragment_id or type(lo) is not int
                or type(hi) is not int or not 0 <= lo < hi):
            return None
        current = {"fragment_id": fragment_id, "start": lo, "end": hi}
        if (normalized and normalized[-1]["fragment_id"] == fragment_id
                and normalized[-1]["end"] == lo):
            normalized[-1]["end"] = hi
        else:
            normalized.append(current)
    if not source_sha256 or not source_reconstruction_hash or not normalized:
        return None
    material = {
        "v": 2,
        "source_sha256": source_sha256,
        "source_reconstruction_hash": source_reconstruction_hash,
        "fragments": normalized,
    }
    if block_id is not None or block_start is not None or block_end is not None:
        if (not isinstance(block_id, str) or not block_id or type(block_start) is not int
                or type(block_end) is not int or not 0 <= block_start < block_end):
            return None
        material["v"] = 3
        material["reconstructed_span"] = {
            "block_id": block_id,
            "start": block_start,
            "end": block_end,
        }
    return _hash(material)


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
            if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(("'", "\t", "\r", "\n")):
                cell = _escape_formula(cell)
            cells[field] = cell
        writer.writerow(cells)
    return output.getvalue().encode("utf-8-sig")


JSON_COLUMNS = frozenset({
    "diagnostic", "proposal", "identity", "target_spans", "spans", "section_path",
    "admission", "reason_codes", "request", "finding", "limits", "transport",
    "execution", "semantic_identity", "extractor_versions", "source_layout_findings",
    "bbox", "context_scan", "context_evidence", "source_bound_context",
    "expand_merge", "necessary_context_disposition", "context_realization",
    "source_context_review", "validation",
})
OFFSET_COLUMNS = frozenset({
    "start", "end", "block_start", "block_end", "raw_start", "raw_end", "map_start", "map_end",
})


def _escape_formula(cell: str) -> str:
    """Prefix one apostrophe. A leading apostrophe in the source is preserved by doubling."""
    if cell.startswith("'") or cell[:1] in "\t\r\n" or cell.lstrip()[:1] in "=-+@":
        return "'" + cell
    return cell


def _unescape_formula(value: str) -> str:
    """Undo exactly one export apostrophe. A source apostrophe stays."""
    if value.startswith("'"):
        rest = value[1:]
        if rest.startswith("'") or rest[:1] in "\t\r\n" or rest.lstrip()[:1] in "=-+@":
            return rest
    return value


def _parse_cell(column: str | None, value: str) -> Any:
    text = _unescape_formula(value)
    if text == "":
        return None
    if column in JSON_COLUMNS and text[:1] in "{[":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    if column in OFFSET_COLUMNS and re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def _read_csv(archive: ZipFile, name: str) -> list[dict[str, Any]]:
    try:
        raw = archive.read(name)
    except KeyError:
        return []
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    return [{key: _parse_cell(key, value) for key, value in row.items()} for row in rows]


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


def _contains_span(target: Any, block_id: Any, start: Any, end: Any) -> bool:
    return (isinstance(target, dict) and target.get("block_id") == block_id
            and type(target.get("start")) is int and type(target.get("end")) is int
            and type(start) is int and type(end) is int
            and target["start"] <= start and end <= target["end"] and start < end)


def _attach_formation(span: dict[str, Any], tasks: list[dict[str, Any]], task_policy: Any) -> None:
    reconstruction = span.get("reconstruction") or {}
    if reconstruction.get("status") != "recorded":
        return
    block = reconstruction.get("semantic_block_id")
    start, end = reconstruction.get("block_start"), reconstruction.get("block_end")
    matches = []
    for task in tasks:
        targets = task.get("target_spans") or []
        if isinstance(targets, str):
            continue
        if any(_contains_span(target, block, start, end) for target in targets):
            matches.append(task)
    if not matches:
        return
    current = matches[0]
    history: list[dict[str, Any]] = []
    if len(matches) != 1:
        phases = [task.get("phase") for task in matches]
        if set(phases) <= {"initial", "recovery"} and "recovery" in phases:
            last = max(index for index, task in enumerate(matches) if task.get("phase") == "recovery")
            if all(task.get("phase") != "initial" or index < last for index, task in enumerate(matches)):
                current = matches[last]
                history = [task for index, task in enumerate(matches) if index != last]
            else:
                span["formation"] = {"status": "conflict", "task_ids": [task.get("task_id") for task in matches]}
                return
        else:
            span["formation"] = {"status": "conflict", "task_ids": [task.get("task_id") for task in matches]}
            return
    span["formation"] = _recorded({
        "task_id": current.get("task_id"),
        "phase": current.get("phase"),
        "status_recorded": current.get("status"),
        "selectable_range": {"block_id": block, "start": start, "end": end},
        "task_target_spans": current.get("target_spans"),
        "link": "exact" if any(_exact_span(target, block, start, end) for target in (current.get("target_spans") or [])) else "contained",
        "context_only_block_ids": [],
        "task_policy": task_policy,
        "selectable": current.get("status") not in {"not_selectable", "excluded"},
        "history": [{"task_id": task.get("task_id"), "phase": task.get("phase"), "status": task.get("status")} for task in history],
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


def _safe_source_fragments(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for fragment in fragments or []:
        if not isinstance(fragment, dict) or not fragment.get("fragment_id"):
            continue
        item = dict(fragment)
        if not isinstance(item.get("source_locator"), dict):
            item.pop("source_locator", None)
        safe.append(item)
    return safe


def current_reconstruction_identity(fragments: list[dict[str, Any]]) -> dict[str, str]:
    """Identity of a map derived by the code that is running now. Not historical evidence."""
    from src.pre_review_semantic_v1 import _candidate_fragments, _evidence_fragments
    from src.semantic_passage_v1 import semantic_source_blocks
    from src.semantic_replay_v1 import stable_json_hash
    from src.source_reconstruction_v1 import RECONSTRUCTION_VERSION
    safe = _safe_source_fragments(fragments)
    semantic_input = {
        "source_blocks": semantic_source_blocks(_candidate_fragments(safe)),
        "evidence_blocks": semantic_source_blocks(_evidence_fragments(safe)),
    }
    return {
        "reconstruction_version": RECONSTRUCTION_VERSION,
        "source_blocks_hash": stable_json_hash(semantic_input),
    }


def project_source_blocks(fragments: list[dict[str, Any]], recorded_version: Any, recorded_hash: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use a derived block map only when it is proven identical to the recorded replay identity."""
    derived = current_reconstruction_identity(fragments)
    recorded_version = str(recorded_version) if recorded_version not in (None, "") else None
    recorded_hash = str(recorded_hash) if recorded_hash not in (None, "") else None
    base = {
        "recorded_version": recorded_version,
        "recorded_hash": recorded_hash,
        "derived_version": derived["reconstruction_version"],
        "derived_hash": derived["source_blocks_hash"],
    }
    if recorded_version is None or recorded_hash is None:
        return [], {**base, "status": "unavailable"}
    if recorded_version != derived["reconstruction_version"] or recorded_hash != derived["source_blocks_hash"]:
        return [{
            "kind": "reconstruction_identity_mismatch",
            "provenance": "RECONSTRUCTION_IDENTITY_MISMATCH",
            "reconstruction_version": derived["reconstruction_version"],
            "recorded_reconstruction_version": recorded_version,
            "recorded_source_blocks_hash": recorded_hash,
            "derived_source_blocks_hash": derived["source_blocks_hash"],
        }], {**base, "status": "RECONSTRUCTION_IDENTITY_MISMATCH"}
    rows = []
    for row in recorded_source_block_rows(fragments):
        rows.append({
            **row,
            "provenance": "verified_derived",
            "recorded_reconstruction_version": recorded_version,
            "recorded_source_blocks_hash": recorded_hash,
            "derived_source_blocks_hash": derived["source_blocks_hash"],
        })
    return rows, {**base, "status": "verified_derived"}


def recorded_source_block_rows(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive a block map with the current reconstructor. Not historical evidence until verified."""
    from src.semantic_passage_v1 import _reconstructed_blocks
    rows = []
    for public, source in _reconstructed_blocks(_safe_source_fragments(fragments)):
        version = (source.get("source_reconstruction") or {}).get("version")
        for piece in source.get("_raw_source_mapping") or []:
            kind = piece.get("kind") or "fragment_range"
            rows.append({
                "block_id": public["block_id"],
                "reconstruction_version": version,
                "map_start": piece.get("start"),
                "map_end": piece.get("end"),
                "kind": kind,
                "fragment_id": piece.get("fragment_id"),
                "raw_start": piece.get("raw_start"),
                "raw_end": piece.get("raw_end"),
                "text": piece.get("text") if kind == "join_separator" else None,
                "source_page": piece.get("source_page"),
                "left_fragment_id": piece.get("left_fragment_id"),
                "right_fragment_id": piece.get("right_fragment_id"),
            })
    return rows


def slice_block_mapping(rows: list[dict[str, Any]], block_id: Any, start: Any, end: Any) -> list[dict[str, Any]] | None:
    """Exact cover of one block span. A partial or inexact piece is not a source span."""
    if not block_id or type(start) is not int or type(end) is not int or not start < end:
        return None
    pieces = [row for row in rows
              if row.get("block_id") == block_id and row.get("provenance") in {"verified_derived", "recorded"}]
    if not pieces:
        return None
    mapping: list[dict[str, Any]] = []
    covered = 0
    for row in pieces:
        lo, hi = row.get("map_start"), row.get("map_end")
        if type(lo) is not int or type(hi) is not int or lo >= hi:
            return None
        overlap_lo, overlap_hi = max(start, lo), min(end, hi)
        if overlap_lo >= overlap_hi:
            continue
        if row.get("kind") == "join_separator":
            if not (start <= lo and hi <= end) or not isinstance(row.get("text"), str):
                return None
            mapping.append({
                "kind": "join_separator",
                "text": row["text"],
                "left_fragment_id": row.get("left_fragment_id"),
                "right_fragment_id": row.get("right_fragment_id"),
            })
            covered += hi - lo
            continue
        raw_lo, raw_hi = row.get("raw_start"), row.get("raw_end")
        if type(raw_lo) is not int or type(raw_hi) is not int or not row.get("fragment_id"):
            return None
        exact = raw_hi - raw_lo == hi - lo
        if exact:
            mapped_raw_start = raw_lo + overlap_lo - lo
            mapped_raw_end = raw_lo + overlap_hi - lo
        else:
            # A normalized whitespace/layout segment may map one reconstructed
            # character to several raw characters. Only a whole-segment overlap
            # is reversible; a partial overlap is ambiguous and stays unlinked.
            if overlap_lo != lo or overlap_hi != hi:
                return None
            mapped_raw_start, mapped_raw_end = raw_lo, raw_hi
        mapping.append({
            "fragment_id": str(row["fragment_id"]),
            "raw_start": mapped_raw_start,
            "raw_end": mapped_raw_end,
            "source_page": row.get("source_page"),
        })
        covered += overlap_hi - overlap_lo
    if covered != end - start or not any(item.get("fragment_id") for item in mapping):
        return None
    return mapping


def _fragment_text(fragments: Mapping[str, Any], mapping: list[Any]) -> tuple[str | None, list[dict[str, Any]], Any, Any]:
    """Exact slices in mapping order. A missing fragment or offset is not guessed."""
    parts: list[str] = []
    ranges: list[dict[str, Any]] = []
    page = None
    locator = None
    for item in mapping:
        if not isinstance(item, dict):
            return None, [], None, None
        if item.get("kind") == "join_separator":
            if not isinstance(item.get("text"), str):
                return None, [], None, None
            parts.append(item["text"])
            continue
        fragment_id = item.get("fragment_id")
        fragment = fragments.get(str(fragment_id)) if fragment_id is not None else None
        raw = fragment.get("raw_text") if isinstance(fragment, dict) else None
        lo, hi = item.get("raw_start"), item.get("raw_end")
        if not isinstance(raw, str) or type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= len(raw):
            return None, [], None, None
        parts.append(raw[lo:hi])
        ranges.append({"fragment_id": str(fragment_id), "start": lo, "end": hi})
        if page is None:
            page = item.get("source_page") if item.get("source_page") is not None else fragment.get("source_page")
            locator = fragment.get("source_locator")
    if not ranges:
        return None, [], None, None
    return "".join(parts), ranges, page, locator


def _review_stage(obj: Mapping[str, Any], admission: Mapping[str, Any], register: Mapping[str, Any]) -> dict[str, Any]:
    gate = admission.get("gate_result")
    decision = (obj.get("governance") or {}).get("validation_status") or None
    status = register.get("status") or None
    if gate not in {"allowed", "blocked"} and not status and not decision:
        return _unknown_stage()
    return _recorded({
        "kind": "review_queue_projection",
        "shown_as_review_candidate": True if gate == "allowed" else False if gate == "blocked" else None,
        "review_status": status,
        "review_decision": decision,
        "review_decision_status": "recorded" if decision else "not_recorded",
        "evidence_kind": "review_queue_projection_from_stored_admission_and_register",
    })


def _validation_stage(validation: Any) -> dict[str, Any]:
    if validation in (None, ""):
        return _unknown_stage()
    return _recorded({
        "validator_result": "accepted" if validation == "passed" else validation,
        "reason_code": None,
        "finding": None,
        "evidence_kind": "stored_proposal_validation_not_a_span_finding",
    })


def select_producing_run(runs: list[Any], replay_identity: Any) -> tuple[dict[str, Any] | None, str]:
    """Bind the trace to the run whose semantic identity is the active replay."""
    if not isinstance(runs, list) or not runs:
        return None, "unavailable"
    if isinstance(replay_identity, dict) and replay_identity:
        exact = [run for run in runs if isinstance(run, dict) and run.get("semantic_identity") == replay_identity]
        if len(exact) == 1:
            return exact[0], "matched"
        if len(exact) > 1:
            return None, "ambiguous"
    if len(runs) == 1 and isinstance(runs[0], dict):
        return runs[0], "sole_run"
    return None, "unmatched"


def rejection_key(row: Mapping[str, Any]) -> str:
    return json.dumps({
        "kind": row.get("kind"),
        "reason_code": row.get("reason_code"),
        "spans": row.get("spans") or [],
    }, ensure_ascii=False, sort_keys=True, default=str)


def pending_rejection_keys(provider: Mapping[str, Any], proposal: Any) -> set[str] | None:
    """Current open rejections. None means the call chain is not complete enough to decide."""
    recorded = provider.get("pending_rejections") if isinstance(provider, Mapping) else None
    if not isinstance(recorded, list):
        if not isinstance(provider, Mapping) or not isinstance(proposal, dict):
            return None
        try:
            from src.recoverable_formation_v1 import pending_rejections
            recorded = pending_rejections(provider, proposal)
        except (KeyError, TypeError, AttributeError, ValueError):
            return None
    return {rejection_key(row) for row in recorded if isinstance(row, dict)}


def evidence_from_stored(*, snapshot_id: str, revision: str, envelope: Mapping[str, Any],
                         objects: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Join recorded fragments, mappings, proposals and objects. Do not invent a link."""
    replay = envelope.get("semantic_replay") if isinstance(envelope.get("semantic_replay"), dict) else {}
    components = (replay.get("identity") or {}).get("components") if isinstance(replay.get("identity"), dict) else {}
    components = components if isinstance(components, dict) else {}
    identity = _identity_from(components)
    identity["snapshot_id"] = identity["snapshot_id"] or snapshot_id
    identity["objects_revision"] = revision
    runs = envelope.get("quality_processing_runs") or []
    producing, _run_link = select_producing_run(runs, replay.get("identity") if isinstance(replay.get("identity"), dict) else None)
    if producing and not identity["source_sha256"]:
        identity["source_sha256"] = producing.get("source_hash")
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
    if producing and producing.get("attempt_id") not in (None, ""):
        identity["attempt_id"] = str(producing.get("attempt_id"))
    run_modes = []
    if producing:
        blob = producing.get("semantic_identity")
        if isinstance(blob, dict) and blob.get("passage_formation_mode"):
            run_modes.append(blob["passage_formation_mode"])
        components_blob = blob.get("components") if isinstance(blob, dict) and isinstance(blob.get("components"), dict) else {}
        if components_blob.get("passage_formation_mode"):
            run_modes.append(components_blob["passage_formation_mode"])
    if provider.get("passage_formation_mode"):
        run_modes.append(provider["passage_formation_mode"])
    if components.get("passage_formation_mode"):
        run_modes.append(components["passage_formation_mode"])
    object_modes = []
    for obj in objects or []:
        semantic = (obj.get("metadata") or {}).get("semantic_passage") or {}
        admission = (obj.get("metadata") or {}).get("admission") or {}
        if isinstance(semantic, dict):
            mode = semantic.get("formation_mode") or admission.get("field_formation_mode")
            if mode:
                object_modes.append(mode)
    identity_conflicts = []
    if run_modes and object_modes and set(run_modes) != set(object_modes):
        identity_conflicts.append("passage_formation_mode")
    elif len(set(run_modes or object_modes)) == 1:
        identity["passage_formation_mode"] = (run_modes or object_modes)[0]
    elif len(set(run_modes or object_modes)) > 1:
        identity_conflicts.append("passage_formation_mode")
    proposal = replay.get("proposal") if isinstance(replay.get("proposal"), dict) else {}
    validation = replay.get("validation")
    fragments: dict[str, Any] = {}
    for fragment in (producing or {}).get("source_fragments") or []:
        if fragment.get("fragment_id") not in (None, ""):
            fragments[str(fragment["fragment_id"])] = fragment
    by_block: dict[tuple[Any, Any, Any], dict[str, Any]] = {}

    def block_bucket(block_id: Any, start: Any, end: Any) -> dict[str, Any]:
        key = (block_id, start, end)
        return by_block.setdefault(key, {"proposals": [], "assessments": [], "objects": [], "rejections": [], "historical_rejections": []})

    for raw in proposal.get("objects") or []:
        if not isinstance(raw, dict):
            continue
        for item in raw.get("spans") or []:
            if isinstance(item, dict):
                block_bucket(item.get("block_id"), item.get("start"), item.get("end"))["proposals"].append(raw)
    for raw in proposal.get("source_assessments") or []:
        item = raw.get("span") if isinstance(raw, dict) else None
        if isinstance(item, dict):
            block_bucket(item.get("block_id"), item.get("start"), item.get("end"))["assessments"].append(raw)
    for obj in objects or []:
        semantic = (obj.get("metadata") or {}).get("semantic_passage") or {}
        for item in semantic.get("spans") or []:
            if isinstance(item, dict):
                block_bucket(item.get("block_id"), item.get("start"), item.get("end"))["objects"].append(obj)
        if not semantic.get("spans") and semantic.get("source_mapping"):
            block_bucket(None, None, None)["objects"].append(obj)
    open_keys = pending_rejection_keys(provider, proposal)
    for rejection in ((provider.get("formation") or {}).get("rejections") or []):
        if not isinstance(rejection, dict):
            continue
        state = rejection.get("state")
        if state not in {"pending", "historical"}:
            state = None if open_keys is None else ("pending" if rejection_key(rejection) in open_keys else "historical")
        targets = rejection.get("spans") or [None]
        for item in targets:
            if item is None:
                continue
            if not isinstance(item, dict):
                continue
            bucket = block_bucket(item.get("block_id"), item.get("start"), item.get("end"))
            if state == "historical":
                bucket["historical_rejections"].append(rejection)
            else:
                bucket["rejections"].append(rejection)

    tasks = provider.get("tasks") if isinstance(provider.get("tasks"), list) else []
    call_id = (provider.get("response") or {}).get("id") if isinstance(provider.get("response"), dict) else None
    spans: list[dict[str, Any]] = []
    referenced: set[str] = set()

    def provider_stage(proposals: list[dict[str, Any]], assessments: list[dict[str, Any]],
                       rejections: list[dict[str, Any]]) -> dict[str, Any]:
        if proposals and assessments:
            return {"status": "conflict", "proposal_count": len(proposals), "assessment_count": len(assessments)}
        if len(proposals) == 1 and not rejections:
            raw = proposals[0]
            return _recorded({
                "provider_call_id": call_id,
                "selected": True,
                "proposed_object_type": raw.get("proposed_object_type"),
                "source_assessment_role": None,
                "proposal_ref": "semantic_replay.proposal.objects",
            })
        if len(assessments) == 1 and not proposals and not rejections:
            raw = assessments[0]
            return _recorded({
                "provider_call_id": call_id,
                "selected": False,
                "proposed_object_type": None,
                "source_assessment_role": raw.get("role"),
                "proposal_ref": "semantic_replay.proposal.source_assessments",
            })
        if len(rejections) == 1 and not proposals and not assessments:
            raw = rejections[0]
            if raw.get("proposed_object_type"):
                return _recorded({
                    "provider_call_id": call_id,
                    "selected": True,
                    "proposed_object_type": raw.get("proposed_object_type"),
                    "source_assessment_role": None,
                    "proposal_ref": "provider_evidence.formation.rejections",
                })
            if raw.get("kind") == "source_assessment":
                return _recorded({
                    "provider_call_id": call_id,
                    "selected": False,
                    "proposed_object_type": None,
                    "source_assessment_role": raw.get("source_assessment_role"),
                    "proposal_ref": "provider_evidence.formation.rejections",
                })
        if proposals or assessments or rejections:
            return {"status": "conflict"}
        return _unknown_stage()

    seen_objects: set[int] = set()
    for key, bucket in by_block.items():
        obj = bucket["objects"][0] if len(bucket["objects"]) == 1 else None
        if len(bucket["objects"]) > 1:
            obj = None
        semantic = (obj.get("metadata") or {}).get("semantic_passage") or {} if obj else {}
        block_id, start, end = key
        object_spans = semantic.get("spans") or []
        if obj is not None and len(object_spans) == 1 and semantic.get("source_mapping"):
            mapping = list(semantic.get("source_mapping") or [])
        else:
            mapping = slice_block_mapping(list(envelope.get("source_block_map") or []), block_id, start, end) or []
        text, ranges, page, locator = _fragment_text(fragments, mapping) if mapping else (None, [], None, None)
        for item in ranges:
            referenced.add(item["fragment_id"])
        if obj is not None:
            seen_objects.add(id(obj))
        section = None
        if bucket["proposals"]:
            section = bucket["proposals"][0].get("section_path")
        if section is None and obj is not None:
            section = (obj.get("metadata") or {}).get("section_path")
        span = _span_shell(
            fragment_ids=[item["fragment_id"] for item in ranges],
            start=ranges[0]["start"] if len(ranges) == 1 else None,
            end=ranges[0]["end"] if len(ranges) == 1 else None,
            raw_text=text, clean_text=text, page=page, locator=locator,
            section_path=section if isinstance(section, list) else None,
            block_id=block_id, block_start=start, block_end=end)
        if len(ranges) != 1:
            span["fragments"] = ranges
        elif ranges:
            span["fragments"] = ranges
        decided = provider_stage(bucket["proposals"], bucket["assessments"], bucket["rejections"])
        if decided.get("status") == "recorded" and bucket["historical_rejections"]:
            decided = {**decided, "historical_rejections": [
                {"kind": item.get("kind"), "reason_code": item.get("reason_code"), "state": "historical"}
                for item in bucket["historical_rejections"]
            ]}
        if decided.get("status") != "unknown":
            span["provider"] = decided
            rejection = bucket["rejections"][0] if len(bucket["rejections"]) == 1 and not bucket["proposals"] else None
            if rejection is not None:
                span["validation"] = _recorded({
                    "validator_result": "rejected",
                    "reason_code": rejection.get("reason_code"),
                    "finding": rejection.get("finding"),
                    "evidence_kind": "rejected_producer_proposal_not_approved_knowledge",
                })
            else:
                span["validation"] = _validation_stage(validation)
        no_object = not bucket["objects"]
        if no_object and span["provider"].get("status") == "recorded":
            span["transformation"] = _recorded({
                "object_id": None,
                "object_version": None,
                "canonical_object_hash": None,
                "proposed_object_type": None,
            })
            span["admission"] = _recorded({
                "gate_result": None,
                "reason_codes": [],
                "evidence_kind": "not_a_knowledge_object",
            })
            span["review_projection"] = _recorded({
                "kind": "review_queue_projection",
                "shown_as_review_candidate": False,
                "review_status": None,
                "review_decision": None,
                "review_decision_status": "not_recorded",
                "evidence_kind": "no_knowledge_object_so_not_in_review_queue",
            })
            role = span["provider"].get("source_assessment_role")
            if role:
                span["source_accountability"] = _recorded({
                    "source_role": role,
                    "passage_disposition": None,
                })
        if obj is not None and len(bucket["objects"]) == 1:
            admission = (obj.get("metadata") or {}).get("admission") or {}
            register = (obj.get("metadata") or {}).get("passage_register") or {}
            proposed = obj.get("proposed_object_type")
            if proposed in (None, "") and len(bucket["proposals"]) == 1:
                proposed = bucket["proposals"][0].get("proposed_object_type")
            span["transformation"] = _recorded({
                "object_id": obj.get("object_id"),
                "object_version": obj.get("object_version"),
                "canonical_object_hash": obj.get("canonical_hash"),
                "proposed_object_type": proposed,
            })
            if admission:
                span["admission"] = _recorded({
                    "gate_result": admission.get("gate_result"),
                    "reason_codes": list(admission.get("reason_codes") or []),
                })
            span["review_projection"] = _review_stage(obj, admission, register)
            role = None
            if span["provider"].get("status") == "recorded":
                role = span["provider"].get("source_assessment_role")
            disposition = register.get("status") if register.get("status") in PASSAGE_DISPOSITIONS else None
            if disposition or role:
                span["source_accountability"] = _recorded({
                    "source_role": role,
                    "passage_disposition": disposition,
                })
        if len(bucket["objects"]) > 1:
            span["transformation"] = {"status": "conflict", "object_ids": [item.get("object_id") for item in bucket["objects"]]}
        _attach_formation(span, tasks, identity.get("task_policy"))
        spans.append(span)

    for fragment_id, fragment in fragments.items():
        if fragment_id in referenced or not isinstance(fragment.get("raw_text"), str):
            continue
        text = fragment["raw_text"]
        spans.append(_span_shell(
            fragment_ids=[fragment_id], start=0, end=len(text),
            raw_text=text, clean_text=fragment.get("clean_text"),
            page=fragment.get("source_page"), locator=fragment.get("source_locator"),
            section_path=fragment.get("section_path") if isinstance(fragment.get("section_path"), list) else None,
            block_id=None, block_start=None, block_end=None))
    completeness = "unavailable" if not spans else "partial"
    if omitted:
        completeness = "partial"
    return {
        "evidence_kind": EVIDENCE_KIND,
        "evidence_completeness": completeness,
        "omitted_evidence": sorted(set(omitted)),
        "identity": identity,
        "spans": spans,
        "identity_conflicts": identity_conflicts,
        "reconstruction_provenance": dict(envelope.get("reconstruction_provenance") or {"status": "unavailable"}),
        "projection": "stored_evidence_join_not_a_new_authority",
    }


def load_evidence(path: Path) -> dict[str, Any]:
    if path.suffix.casefold() == ".zip":
        return evidence_from_zip(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("evidence_kind") != EVIDENCE_KIND:
        raise ValueError("forensic_evidence_kind_invalid")
    return payload


def _objects_from_export(lineage: list[dict[str, Any]], coverage: list[dict[str, Any]],
                         findings: list[dict[str, Any]], stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild the recorded object join from export tables. Row order is mapping order."""
    objects: dict[str, dict[str, Any]] = {}

    def ensure(object_id: Any) -> dict[str, Any] | None:
        if object_id in (None, ""):
            return None
        return objects.setdefault(str(object_id), {
            "object_id": str(object_id),
            "object_version": None,
            "proposed_object_type": None,
            "metadata": {
                "semantic_passage": {"spans": [], "source_mapping": []},
                "admission": {},
                "passage_register": {},
            },
            "content": {},
            "governance": {},
        })

    for row in lineage:
        current = ensure(row.get("object_id"))
        if current is None:
            continue
        if row.get("object_version") not in (None, ""):
            current["object_version"] = row.get("object_version")
        semantic = current["metadata"]["semantic_passage"]
        relation = row.get("relation")
        if relation == "selected_raw_fragment_range":
            semantic["source_mapping"].append({
                "fragment_id": row.get("target_id"),
                "raw_start": row.get("start"),
                "raw_end": row.get("end"),
                "source_page": row.get("page"),
                "bbox": row.get("bbox"),
            })
        elif relation == "inserted_join_separator":
            semantic["source_mapping"].append({
                "kind": "join_separator",
                "text": row.get("text"),
                "left_fragment_id": row.get("left_fragment_id"),
                "right_fragment_id": row.get("right_fragment_id"),
            })
        elif relation == "selected_block_range":
            semantic["spans"].append({
                "block_id": row.get("target_id"),
                "start": row.get("start"),
                "end": row.get("end"),
            })
    for row in coverage:
        current = ensure(row.get("object_id"))
        if current is None:
            continue
        semantic = current["metadata"]["semantic_passage"]
        if row.get("formation_mode"):
            semantic["formation_mode"] = row.get("formation_mode")
        if row.get("register_status"):
            current["metadata"]["passage_register"]["status"] = row.get("register_status")
        if row.get("gate_result"):
            current["metadata"]["admission"]["gate_result"] = row.get("gate_result")
        if row.get("selection_origin"):
            semantic["selection_origin"] = row.get("selection_origin")
        block = {"block_id": row.get("block_id"), "start": row.get("start"), "end": row.get("end")}
        if block["block_id"] and not any(_exact_span(item, block["block_id"], block["start"], block["end"]) for item in semantic["spans"]):
            semantic["spans"].append(block)
    for row in findings:
        current = ensure(row.get("object_id"))
        if current is None:
            continue
        stored = current["metadata"]["admission"]
        admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
        for key, value in admission.items():
            if key not in stored or stored.get(key) in (None, ""):
                stored[key] = value
        if admission.get("field_formation_mode") and not current["metadata"]["semantic_passage"].get("formation_mode"):
            current["metadata"]["semantic_passage"]["formation_mode"] = admission.get("field_formation_mode")
        if row.get("gate_result") and not stored.get("gate_result"):
            stored["gate_result"] = row.get("gate_result")
        reason = row.get("reason_code")
        if reason:
            codes = stored.setdefault("reason_codes", [])
            if reason not in codes:
                codes.append(reason)
    for row in stages:
        current = ensure(row.get("object_id"))
        if current is None:
            continue
        if row.get("stage") == "current_object_raw_text" and isinstance(row.get("text"), str):
            current["content"]["raw_text"] = row.get("text")
        if row.get("section_path") and not current["metadata"].get("section_path"):
            section = row.get("section_path")
            current["metadata"]["section_path"] = section if isinstance(section, list) else None
    return list(objects.values())


def _fragment_from_view(view: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "fragment_id": view.get("fragment_id"),
        "raw_text": view.get("raw_text"),
        "clean_text": view.get("clean_text"),
        "section_path": view.get("section_path"),
        "heading": view.get("heading"),
        "source_page": view.get("source_page"),
        "source_locator": view.get("source_locator"),
        "source_text_view": view.get("source_text_view"),
        "source_layout_findings": view.get("source_layout_findings"),
    }


def _runs_from_export(run_rows: list[dict[str, Any]], views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not run_rows and not views:
        return []
    if not run_rows:
        return [{
            "source_fragments": [_fragment_from_view(view) for view in views if view.get("fragment_id")],
        }]
    built = []
    for row in run_rows:
        run_id = row.get("run_id")
        fragments = []
        for view in views:
            if not view.get("fragment_id"):
                continue
            view_run = view.get("run_id")
            if run_id not in (None, "") and view_run == run_id:
                fragments.append(_fragment_from_view(view))
            elif run_id in (None, "") and view_run in (None, "") and len(run_rows) == 1:
                fragments.append(_fragment_from_view(view))
        identity = row.get("semantic_identity") if isinstance(row.get("semantic_identity"), dict) else {}
        built.append({
            "run_id": run_id,
            "source_hash": row.get("source_hash"),
            "attempt_id": row.get("attempt_id"),
            "semantic_identity": identity,
            "source_fragments": fragments,
        })
    return built


def evidence_from_zip(path: Path) -> dict[str, Any]:
    with ZipFile(path) as archive:
        revision_rows = _read_csv(archive, "revision.csv")
        proposals = _read_csv(archive, "semantic_proposals.csv")
        tasks = _read_csv(archive, "formation_tasks.csv")
        views = _read_csv(archive, "source_views.csv")
        attempts = _read_csv(archive, "attempt_diagnostics.csv")
        runs = _read_csv(archive, "runs.csv")
        manifest = _read_csv(archive, "manifest.csv")
        calls = _read_csv(archive, "model_calls.csv")
        lineage = _read_csv(archive, "lineage.csv")
        coverage = _read_csv(archive, "coverage.csv")
        findings = _read_csv(archive, "validation_findings.csv")
        stages = _read_csv(archive, "source_stages.csv")
        formation_findings = _read_csv(archive, "formation_findings.csv")
        source_blocks = _read_csv(archive, "source_blocks.csv")
    revision = revision_rows[0] if revision_rows else {}
    proposal_row = proposals[0] if proposals else {}
    proposal = proposal_row.get("proposal") if isinstance(proposal_row.get("proposal"), dict) else {}
    identity = proposal_row.get("identity") if isinstance(proposal_row.get("identity"), dict) else {}
    omitted: list[str] = []
    attempt_rows = []
    for row in attempts:
        diagnostic = row.get("diagnostic") if isinstance(row.get("diagnostic"), dict) else {}
        omitted.extend(str(item) for item in (diagnostic.get("omitted_evidence") or []))
        attempt_rows.append({"attempt_id": row.get("attempt_id"), "diagnostic": diagnostic})
    commits = [row.get("deployed_commit") for row in calls if row.get("deployed_commit")]
    call_ids = [row.get("call_id") for row in calls if row.get("call_id")]
    deployed = commits[0] if len(set(commits)) == 1 else None
    mismatch = next((row for row in source_blocks if row.get("provenance") == "RECONSTRUCTION_IDENTITY_MISMATCH"), None)
    verified = [row for row in source_blocks if row.get("provenance") in {"verified_derived", "recorded"}]
    if mismatch:
        provenance = {
            "status": "RECONSTRUCTION_IDENTITY_MISMATCH",
            "recorded_version": mismatch.get("recorded_reconstruction_version"),
            "recorded_hash": mismatch.get("recorded_source_blocks_hash"),
            "derived_version": mismatch.get("reconstruction_version"),
            "derived_hash": mismatch.get("derived_source_blocks_hash"),
        }
        usable_blocks = []
    elif verified:
        provenance = {"status": "verified_derived" if verified[0].get("provenance") == "verified_derived" else "recorded"}
        usable_blocks = verified
    else:
        provenance = {"status": "unavailable"}
        usable_blocks = []
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
                "deployed_commit": deployed,
                "response": {"id": call_ids[0]} if len(set(call_ids)) == 1 else {},
                "formation": {"rejections": [{
                    "kind": row.get("kind"),
                    "index": row.get("index"),
                    "reason_code": row.get("reason_code"),
                    "spans": row.get("spans") if isinstance(row.get("spans"), list) else [],
                    "proposed_object_type": row.get("proposed_object_type"),
                    "source_assessment_role": row.get("source_assessment_role"),
                    "finding": row.get("finding"),
                    "requires_review": row.get("requires_review"),
                    "state": row.get("state"),
                } for row in formation_findings]},
            },
        },
        "source_block_map": usable_blocks,
        "reconstruction_provenance": provenance,
        "quality_processing_runs": _runs_from_export(runs, views),
        "processing_attempts": attempt_rows,
    }
    evidence = evidence_from_stored(
        snapshot_id=str(revision.get("snapshot_id") or ""),
        revision=str(revision.get("objects_revision") or revision.get("revision_id") or ""),
        envelope=envelope,
        objects=_objects_from_export(lineage, coverage, findings, stages),
    )
    if omitted or any(row.get("availability") in {"partial", "not_recorded", "not_exported"} for row in manifest):
        evidence["evidence_completeness"] = "partial" if evidence["spans"] or omitted else "unavailable"
    evidence["omitted_evidence"] = sorted(set([*evidence["omitted_evidence"], *omitted]))
    if len(set(commits)) > 1:
        evidence["identity"]["deployed_commit"] = None
        evidence.setdefault("identity_conflicts", []).append("deployed_commit")
    return evidence


def load_gold(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("gold_version") != GOLD_VERSION:
        raise ValueError("forensic_gold_version_invalid")
    if not isinstance(payload.get("cases"), list):
        raise ValueError("forensic_gold_cases_invalid")
    return payload


def _identity_gap(evidence: Mapping[str, Any], gold: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    expected = gold.get("expected_identity") or {}
    recorded = evidence.get("identity") or {}
    missing, mismatched = [], []
    for key, value in expected.items():
        if key not in IDENTITY_FIELDS:
            mismatched.append(key)
            continue
        actual = recorded.get(key)
        if actual in (None, ""):
            missing.append(key)
        elif actual != value:
            mismatched.append(key)
    return missing, mismatched


def _case_span_id(case: Mapping[str, Any]) -> str | None:
    reconstruction = case.get("reconstruction") if isinstance(case.get("reconstruction"), Mapping) else {}
    block_id = case.get("block_id") or reconstruction.get("block_id") or reconstruction.get("semantic_block_id")
    block_start = case.get("block_start")
    if block_start is None:
        block_start = reconstruction.get("block_start", reconstruction.get("start"))
    block_end = case.get("block_end")
    if block_end is None:
        block_end = reconstruction.get("block_end", reconstruction.get("end"))
    bounds = {
        "block_id": block_id,
        "block_start": block_start,
        "block_end": block_end,
    } if block_id is not None or block_start is not None or block_end is not None else {}
    fragments = case.get("fragments")
    if isinstance(fragments, list) and fragments:
        return source_span_id(
            source_sha256=str(case.get("source_sha256") or ""),
            source_reconstruction_hash=str(case.get("source_reconstruction_hash") or ""),
            fragments=fragments,
            **bounds,
        )
    return source_span_id(
        source_sha256=str(case.get("source_sha256") or ""),
        source_reconstruction_hash=str(case.get("source_reconstruction_hash") or ""),
        source_fragment_ids=list(case.get("source_fragment_ids") or []),
        start=case.get("start"),
        end=case.get("end"),
        **bounds,
    )


def _provider_judgement(case: Mapping[str, Any], provider: Mapping[str, Any]) -> str:
    if provider.get("status") == "conflict":
        return "conflict"
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
        if formation.get("status") == "conflict":
            return "conflict"
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
        if review.get("status") == "conflict":
            return "conflict"
        if review.get("status") != "recorded":
            return "unknown"
        expected = case.get("expected_review_visible")
        if expected is not None and review.get("shown_as_review_candidate") is not expected:
            return "fail"
        return "pass"
    if "expected_blocks_publication" not in case:
        return "skip"
    publication = span.get("publication_effect") or {}
    if publication.get("status") != "recorded":
        return "unknown"
    if publication.get("blocks_publication") is not case.get("expected_blocks_publication"):
        return "fail"
    return "pass"


def _grade_span(case: Mapping[str, Any], span: Mapping[str, Any]) -> dict[str, Any]:
    first = None
    verdict = "PASS"
    judgements = {}
    for stage in STAGES:
        judgement = _stage_judgement(stage, case, span)
        judgements[stage] = judgement
        if judgement == "skip":
            continue
        if judgement == "conflict":
            first = stage
            verdict = "CONFLICT"
            break
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


def _ranges_of(span: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    fragments = span.get("fragments")
    if isinstance(fragments, list) and fragments:
        return fragments
    return None


def _public_span(evidence: Mapping[str, Any], span: Mapping[str, Any]) -> dict[str, Any]:
    identity = evidence.get("identity") or {}
    ranges = _ranges_of(span)
    source_kwargs: dict[str, Any] = {
        "source_sha256": str(identity.get("source_sha256") or ""),
        "source_reconstruction_hash": str(identity.get("source_reconstruction_hash") or ""),
    }
    if ranges is None:
        source_kwargs.update(
            source_fragment_ids=list(span.get("source_fragment_ids") or []),
            start=span.get("start") if type(span.get("start")) is int else None,
            end=span.get("end") if type(span.get("end")) is int else None,
        )
    else:
        source_kwargs["fragments"] = ranges
    legacy_span_id = source_span_id(**source_kwargs)
    reconstruction = span.get("reconstruction") or {}
    if reconstruction.get("status") == "recorded":
        span_id = source_span_id(
            **source_kwargs,
            block_id=reconstruction.get("semantic_block_id"),
            block_start=reconstruction.get("block_start"),
            block_end=reconstruction.get("block_end"),
        ) or legacy_span_id
    else:
        span_id = legacy_span_id
    return {
        "trace_version": TRACE_VERSION,
        "source_span_id": span_id,
        "legacy_source_span_id": legacy_span_id if legacy_span_id != span_id else None,
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


def _merge_stage(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> dict[str, Any]:
    if not left or left.get("status") == "unknown":
        return dict(right or _unknown_stage())
    if not right or right.get("status") == "unknown":
        return dict(left)
    left_payload = {key: value for key, value in left.items() if key != "status"}
    right_payload = {key: value for key, value in right.items() if key != "status"}
    if left.get("status") == "conflict" or right.get("status") == "conflict" or left_payload != right_payload:
        return {"status": "conflict", "observed": [dict(left), dict(right)]}
    return dict(left)


def _merge_public(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key in ("source", "reconstruction", "formation", "provider", "validation", "transformation",
                "admission", "source_accountability", "review_projection", "publication_effect"):
        merged[key] = _merge_stage(left.get(key), right.get(key))
    return merged


def _index_spans(evidence: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for span in evidence.get("spans") or []:
        public = _public_span(evidence, span)
        span_id = public.get("source_span_id")
        if not span_id:
            continue
        indexed[span_id] = _merge_public(indexed[span_id], public) if span_id in indexed else public
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

    missing, mismatched = _identity_gap(evidence, gold)
    if mismatched or missing:
        comparison = "TRACE_IDENTITY_MISMATCH" if mismatched else "IDENTITY_UNAVAILABLE"
        summary["comparison"] = comparison
        summary["mismatched_identity_fields"] = mismatched
        summary["unavailable_identity_fields"] = missing
        for case in gold.get("cases") or []:
            divergences.append({
                "case_id": case.get("case_id"),
                "source_span_id": _case_span_id(case),
                "verdict": comparison,
                "first_divergence_stage": "identity",
                "divergence_class": "identity",
                "expected_function": case.get("expected_source_function"),
                "expected_object_type": case.get("expected_object_type"),
                "actual_provider_decision": None,
                "actual_proposed_object_type": None,
            })
        summary["verdicts"] = {comparison: len(divergences)}
        summary["first_divergence_counts"] = {"identity": len(divergences)}
        summary["divergence_classes"] = {"identity": len(divergences)}
        return {"records": [*records, *unindexed], "summary": summary, "divergences": divergences}

    summary["comparison"] = "compared"
    by_id = {row["source_span_id"]: row for row in records}
    legacy_candidates: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        legacy = row.get("legacy_source_span_id")
        if legacy:
            legacy_candidates.setdefault(str(legacy), []).append(row)
    for legacy, candidates in legacy_candidates.items():
        if len(candidates) == 1 and legacy not in by_id:
            by_id[legacy] = candidates[0]
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
        provenance = (evidence.get("reconstruction_provenance") or {}).get("status")
        historically_reconstructed = ((public or {}).get("reconstruction") or {}).get("status") == "recorded"
        if provenance == "RECONSTRUCTION_IDENTITY_MISMATCH" and not historically_reconstructed:
            divergences.append({
                "case_id": case.get("case_id"), "source_span_id": span_id,
                "verdict": "RECONSTRUCTION_IDENTITY_MISMATCH", "first_divergence_stage": "reconstruction",
                "divergence_class": "source", "expected_function": case.get("expected_source_function"),
                "expected_object_type": case.get("expected_object_type"),
                "actual_provider_decision": None, "actual_proposed_object_type": None,
            })
            continue
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
            "source_span_id": public.get("source_span_id") or span_id,
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
    if counts and set(counts) == {"RECONSTRUCTION_IDENTITY_MISMATCH"}:
        summary["comparison"] = "RECONSTRUCTION_IDENTITY_MISMATCH"
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
                "source_assessment_role": provider.get("source_assessment_role") if provider.get("status") == "recorded" else UNKNOWN,
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
        "source_role_changed": [span_id for span_id in shared if before[span_id]["source_assessment_role"] != after[span_id]["source_assessment_role"]],
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
    divergence_path = directory / "first_divergence.csv"
    if result["divergences"]:
        divergence_path.write_bytes(_csv_bytes(DIVERGENCE_FIELDS, result["divergences"]))
    else:
        divergence_path.unlink(missing_ok=True)


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
        "Derived join of recorded source_mapping and lineage onto one source span. "
        "Same span ids merge; conflicting recorded stages stay conflict. "
        "Missing stages stay UNKNOWN. Text is not a join key. "
        "Not approval, publication, or clinical completeness."
    )
    return rows, availability, limitation

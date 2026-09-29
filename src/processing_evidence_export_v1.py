"""Read-only CSV projections of recorded evidence, never a pipeline replay."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from src.processing_diagnostics_v1 import passage_export_rows
from src.source_bound_fields_v2 import bound_values


VERSION = "processing-evidence-export-v2"
COMMON = ("snapshot_id", "objects_revision")
SCHEMAS = {
    "runs": ("run_id", "source_hash", "started_at", "finished_at", "outcome", "reason", "extractor_versions", "execution", "semantic_identity", "production_commit_status"),
    "run_candidates": ("run_id", "object_id", "object_version", "canonical_hash", "origin", "structural"),
    "semantic_proposals": ("proposal_hash", "identity", "validation", "semantic_execution", "origin_execution", "replay_from_proposal_hash", "proposal", "evidence_kind"),
    "source_stages": ("object_id", "object_version", "stage", "text", "section_path", "source_checksum", "text_status"),
    "coverage": ("object_id", "object_version", "block_id", "start", "end", "selection_origin", "register_status", "gate_result", "model_decision_status", "offset_text_status"),
    "proposal_fields": ("object_id", "object_version", "field", "value", "value_status", "stage", "producer_status", "contract_version", "source_span", "missing_reason"),
    "validation_findings": ("object_id", "object_version", "gate_result", "reason_code", "evidence_kind", "admission", "rule_execution_trace_status"),
    "context_evidence": ("object_id", "object_version", "context_scan", "expand_merge", "necessary_context_disposition", "evidence_kind"),
    "lineage": ("object_id", "object_version", "relation", "target_id", "start", "end", "locator", "page", "bbox", "raw_content_hash"),
    "model_calls": ("run_id", "call_id", "request", "raw_response", "stop_reason", "input_tokens", "output_tokens"),
    "object_events": ("run_id", "object_id", "event_id", "timestamp", "event", "reason"),
    "reference_review": ("object_id", "source_range", "expected_type", "expected_context", "reviewer", "judgment"),
}
FIELDS = (
    "proposed_type", "type_evidence_spans", "actor_of_scope", "recommended_action",
    "action_object_or_goal", "recommendation_evidence_span",
    "proposed_recommendation_semantics", "recommendation_semantics_evidence",
)


def _csv(fields: tuple[str, ...], rows: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="raise")
    writer.writeheader()
    for row in rows:
        cells = {}
        for field in fields:
            value = row.get(field)
            if isinstance(value, (dict, list, bool)):
                cell = json.dumps(value, ensure_ascii=False)
            else:
                cell = "" if value is None else str(value)
            if cell.lstrip().startswith(("=", "+", "-", "@")) or cell.startswith(("\t", "\r", "\n")):
                cell = "'" + cell
            cells[field] = cell
        writer.writerow(cells)
    return output.getvalue().encode("utf-8-sig")


def _field_producer_status(bound: dict, obj: dict) -> str:
    if not bound:
        return "not_recorded"
    try:
        bound_values(bound, text=str((obj.get("content") or {}).get("clean_text") or ""),
                     proposed_type=str(obj.get("proposed_object_type") or "unclassified"))
    except ValueError as exc:
        return "stale_source_bound_proposal" if str(exc) == "source_bound_fields_stale" else "invalid_source_bound_proposal"
    return "source_bound_proposal"


def processing_evidence_tables(
    *, snapshot_id: str, revision: str, envelope: dict[str, Any],
    objects: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Project stored values; absent data is not reconstructed from current code."""
    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in SCHEMAS}
    common = {"snapshot_id": snapshot_id, "objects_revision": revision}

    def add(name: str, **values: Any) -> None:
        tables[name].append({**common, **values})

    runs = envelope.get("quality_processing_runs") or []
    for run in runs:
        add("runs", **{key: run.get(key) for key in SCHEMAS["runs"] if key != "production_commit_status"},
            production_commit_status="not_recorded")
        for candidate in run.get("candidates") or []:
            add("run_candidates", run_id=run.get("run_id"),
                **{key: candidate.get(key) for key in SCHEMAS["run_candidates"] if key != "run_id"})

    replay = envelope.get("semantic_replay") or {}
    if replay:
        add("semantic_proposals", **{key: replay.get(key) for key in SCHEMAS["semantic_proposals"] if key != "evidence_kind"},
            evidence_kind="stored_validated_proposal_not_raw_response")

    for obj, row in zip([o for o in objects if o.get("object_type") != "document"], passage_export_rows(objects)):
        keys = {"object_id": row["object_id"], "object_version": row["object_version"]}
        content = obj.get("content") or {}
        admission = row["admission"]
        for stage, container, field in (
            ("current_object_raw_text", content, "raw_text"),
            ("current_object_clean_text", content, "clean_text"),
            ("stored_admission_source_text", admission, "source_text_exact"),
        ):
            add("source_stages", **keys, stage=stage, text=container.get(field),
                text_status="recorded" if field in container else "not_recorded",
                section_path=row["section_path"], source_checksum=row["source"].get("source_checksum"))
        semantic = row["semantic_passage"]
        for span in semantic.get("spans") or [{}]:
            add("coverage", **keys, **{k: span.get(k) for k in ("block_id", "start", "end")},
                selection_origin=row["selection_origin"], register_status=row["passage_register"].get("status"),
                gate_result=admission.get("gate_result"), model_decision_status="not_recorded",
                offset_text_status="original_block_text_not_recorded")
            if span.get("block_id"):
                add("lineage", **keys, relation="selected_block_range", target_id=span["block_id"],
                    start=span.get("start"), end=span.get("end"))
        for fragment in (obj.get("provenance") or {}).get("source_fragments") or []:
            add("lineage", **keys, relation="stored_source_fragment", target_id=fragment.get("raw_object_id"),
                locator=fragment.get("source_locator"), page=fragment.get("page"),
                bbox=fragment.get("bbox"), raw_content_hash=fragment.get("raw_content_hash"))
        from src.source_bound_fields_v2 import KEY, FIELDS as BOUND_FIELDS
        bound = (obj.get("metadata") or {}).get(KEY) or {}
        producer_status = _field_producer_status(bound, obj)
        for field in dict.fromkeys((*FIELDS, *(BOUND_FIELDS if bound else ()))):
            evidence = (bound.get("evidence") or {}).get(field) or {}
            add("proposal_fields", **keys, field=field, value=admission.get(field),
                value_status="recorded" if field in admission else "not_recorded",
                stage="stored_admission", producer_status=producer_status,
                contract_version=bound.get("version"), source_span=evidence.get("span"),
                missing_reason=evidence.get("missing_reason"))
        if admission:
            for reason in admission.get("reason_codes") or [None]:
                add("validation_findings", **keys, gate_result=admission.get("gate_result"),
                    reason_code=reason, evidence_kind="stored_admission_summary_not_rule_trace",
                    admission=admission, rule_execution_trace_status="not_recorded")
            if "context_scan" in admission:
                scan = admission["context_scan"] or {}
                add("context_evidence", **keys, context_scan=scan,
                    expand_merge=admission.get("expand_merge"),
                    necessary_context_disposition=scan.get("necessary_context_disposition"),
                    evidence_kind="stored_scan_not_verified_dependency_resolution")

    statuses = {
        "runs": ("recorded" if "quality_processing_runs" in envelope else "not_recorded", "Stored processing runs; objects_revision identifies this export, not a historical run."),
        "run_candidates": ("recorded" if "quality_processing_runs" in envelope else "not_recorded", "Historical candidate identity; compare object_version AND canonical_hash before linking to current state."),
        "semantic_proposals": ("recorded" if replay else "not_recorded", "Latest saved replay record only; not the raw provider response or every attempt."),
        "source_stages": ("partial", "Current object text only; original extraction and reconstruction stages were not retained here."),
        "coverage": ("partial", "Stored selections and register status; does not establish which blocks were sent or explicitly assessed."),
        "proposal_fields": ("partial", "Stored admission fields; field producers and intermediate transformations are not recorded."),
        "validation_findings": ("partial", "Stored results and reasons; no individual execution trace. No reason does not prove all checks passed."),
        "context_evidence": ("partial", "Stored context scan; include does not by itself prove that context was attached."),
        "lineage": ("partial", "Object-to-block and object-to-fragment relations are separate; no inferred block-to-fragment mapping."),
        "model_calls": ("not_recorded", "Original requests, raw responses, usage, stop reasons and failed attempts are unavailable in these records."),
        "object_events": ("not_exported", "This package does not read the review ledger and does not claim that no historical events exist."),
        "reference_review": ("not_exported", "A human reference assessment must be supplied separately; system review state is not a gold standard."),
    }
    manifest = [{**common, "schema_version": VERSION, "dataset": name + ".csv",
                 "row_count": len(tables[name]), "availability": statuses[name][0],
                 "limitation": statuses[name][1]} for name in SCHEMAS]
    return tables, manifest


def processing_evidence_zip(**kwargs: Any) -> bytes:
    tables, manifest = processing_evidence_tables(**kwargs)
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("manifest.csv", _csv(COMMON + ("schema_version", "dataset", "row_count", "availability", "limitation"), manifest))
        for name, fields in SCHEMAS.items():
            archive.writestr(name + ".csv", _csv(COMMON + fields, tables[name]))
        archive.writestr("README.txt", (
            "Metis processing evidence export v1\n"
            f"Exported at: {datetime.now(timezone.utc).isoformat()}\n"
            "Read manifest.csv first. This is a read-only projection of stored evidence.\n"
            "Current object revision is not a run ID or a production commit.\n"
            "No extraction, model inference or validation was rerun. No missing history was invented.\n"
            "Envelope evidence and object revision are not claimed to be an atomic historical pipeline snapshot.\n"
            "recorded with zero rows means explicitly stored empty; not_recorded means unavailable.\n"
            "partial means the dataset lacks the full historical trace; not_exported does not mean absent.\n"
            "CSV: UTF-8 BOM, comma delimiter, JSON for nested values. Formula-like cells have a leading apostrophe.\n"
            "Offsets retain their stored start/end values; do not apply them to current object text.\n"
        ))
    return output.getvalue()

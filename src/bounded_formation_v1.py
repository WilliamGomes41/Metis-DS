"""Bounded source tasks inside the existing atomic semantic preparation.

Tasks are replay evidence, never a second workflow or publication authority.
All source stays in the immutable fragments and source-accountability container.
"""
from copy import deepcopy
from dataclasses import replace
import re
import time

from src.semantic_replay_v1 import stable_json_hash
from src.semantic_passage_v1 import semantic_units_from_proposal, SemanticPassageError
from src.source_accountability_v1 import supplementary_targets
from src.source_containers_v1 import metadata_reason, _covers
from src.recoverable_formation_v1 import restrict_supplement, pending_rejections
from src.recommendation_coverage_v1 import merge_proposals, assess

VERSION = "bounded-formation-v1"
MAX_CANDIDATE_CHARS = 12_000
MAX_CANDIDATE_BLOCKS = 48
MAX_CONTEXT_CHARS = 48_000
MAX_CALL_SECONDS = 120
_REFERENCE = re.compile(r"\b(tabel|figuur|bijlage)\s+(\d+[a-z]?)\b", re.I)


def full_span(block):
    return {"block_id": block["block_id"], "start": 0, "end": len(block["text"])}


def tasks_for(blocks, evidence_blocks, targets=None):
    """Keep section runs together; headings/referenced sections are context only.

    No truncation of source or references: oversized tasks remain explicit open
    work. Canonical block ids/offsets are never rewritten for chunking.
    """
    target_spans = [t["span"] for t in targets] if targets is not None else [full_span(b) for b in blocks]
    selected_ids = {s["block_id"] for s in target_spans}
    groups, group, size, path = [], [], 0, None
    for block in blocks:
        if block["block_id"] not in selected_ids:
            continue
        section = tuple(block.get("section_path") or [])
        if group and (section != path or size + len(block["text"]) > MAX_CANDIDATE_CHARS or len(group) >= MAX_CANDIDATE_BLOCKS):
            groups.append(group); group, size = [], 0
        group.append(block); size += len(block["text"]); path = section
    if group:
        groups.append(group)
    tasks = []
    for group in groups:
        ids = {b["block_id"] for b in group}
        section = tuple(group[0].get("section_path") or [])
        contexts = {b["block_id"]: b for b in evidence_blocks
                    if tuple(b.get("section_path") or []) == section
                    or b.get("heading") in section}
        # Reference closure includes the complete referenced section, not just
        # the table caption. If it does not fit, this task fails explicitly.
        references = {m.group().casefold() for b in [*group, *contexts.values()] for m in _REFERENCE.finditer(b["text"])}
        while references:
            added = {b["block_id"]: b for b in evidence_blocks
                     if any(m.group().casefold() in references for m in _REFERENCE.finditer(b["text"]))}
            paths = {tuple(b.get("section_path") or []) for b in added.values()}
            added.update({b["block_id"]: b for b in evidence_blocks if tuple(b.get("section_path") or []) in paths})
            fresh = [b for bid, b in added.items() if bid not in contexts and bid not in ids]
            contexts.update(added)
            references = {m.group().casefold() for b in fresh for m in _REFERENCE.finditer(b["text"])}
        context = [b for b in evidence_blocks if b["block_id"] in contexts and b["block_id"] not in ids]
        spans = [s for s in target_spans if s["block_id"] in ids]
        task = {"task_id": stable_json_hash({"version": VERSION, "spans": spans}),
                "section_path": list(section), "target_spans": spans,
                "source_blocks": group, "evidence_blocks": context}
        if sum(len(b["text"]) for b in group) > MAX_CANDIDATE_CHARS or sum(len(b["text"]) for b in context) > MAX_CONTEXT_CHARS:
            task["error_code"] = "source_task_context_limit_exceeded"
        tasks.append(task)
    return tasks


def pending_source_extent(evidence):
    """Return current unresolved source extent without double-counting overlaps."""
    by_block = {}
    unknown = 0
    for rejection in evidence.get("pending_rejections") or []:
        spans = list(rejection.get("spans") or [])
        if not spans:
            unknown += 1
            continue
        for span in spans:
            block_id = str(span.get("block_id") or "")
            if not block_id:
                unknown += 1
                continue
            start, end = int(span.get("start", 0)), int(span.get("end", 0))
            if end > start:
                by_block.setdefault(block_id, []).append((start, end))
    merged_count = 0
    chars = 0
    for intervals in by_block.values():
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        merged_count += len(merged)
        chars += sum(end - start for start, end in merged)
    return {
        "unknown_pending_count": unknown,
        "pending_source_range_count": merged_count,
        "pending_source_char_count": chars,
    }


def formation_progress(evidence):
    """Summarize source-task completion against the original bounded plan.

    Recovery may regroup a pending source range and therefore produce a new
    task_id. Progress is consequently derived from overlap with the original
    initial task ranges plus the current pending-rejection truth, not by merely
    counting unique historical task ids.
    """
    history = list(evidence.get("tasks", []))
    initial = [row for row in history if row.get("phase") == "initial"]
    basis = initial or history
    planned = []
    seen = set()
    for row in basis:
        task_id = str(row.get("task_id") or "")
        if not task_id or task_id in seen:
            continue
        seen.add(task_id)
        planned.append(row)

    pending = list(evidence.get("pending_rejections") or [])

    def overlaps(left, right):
        return (
            left.get("block_id") == right.get("block_id")
            and max(int(left.get("start", 0)), int(right.get("start", 0)))
                < min(int(left.get("end", 0)), int(right.get("end", 0)))
        )

    def is_open(task):
        spans = list(task.get("target_spans") or [])
        for rejection in pending:
            refs = list(rejection.get("spans") or [])
            if not refs:
                return True
            if any(overlaps(span, ref) for span in spans for ref in refs):
                return True
        return False

    def latest_status(task):
        spans = list(task.get("target_spans") or [])
        status = str(task.get("status") or "")
        for row in history:
            refs = list(row.get("target_spans") or [])
            if any(overlaps(span, ref) for span in spans for ref in refs):
                status = str(row.get("status") or status)
        return status

    statuses = []
    for task in planned:
        open_ = is_open(task)
        status = latest_status(task)
        if not open_:
            status = "completed"
        elif status == "completed":
            # A recovery subtask may be complete while another source range
            # from the original task remains unresolved.
            status = "partial"
        statuses.append(status)

    terminal = sum(status == "completed" for status in statuses)
    extent = pending_source_extent(evidence)
    return {
        "planned_task_count": len(planned),
        "terminal_task_count": terminal,
        "pending_task_count": len(planned) - terminal,
        "failed_task_count": sum(status == "failed" for status in statuses),
        "partial_task_count": sum(status == "partial" for status in statuses),
        "not_started_task_count": sum(status == "not_started" for status in statuses),
        **extent,
    }


def _remaining_targets(units):
    # Bound context is source use, not a second candidate search. It remains
    # reviewable on its target; source closure depends on target approval.
    context = [e["span"] for u in units for e in u.get("source_bound_context", [])
               if e.get("span") and not e.get("unresolved_reason")]
    return [r for r in supplementary_targets(units)
            if not metadata_reason(r["text"]) and not _covers(r["span"], context)]


from src.source_reconstruction_v1 import with_reconstruction_cache


@with_reconstruction_cache
def execute(*, blocks, evidence_blocks, validator_input, provider, limits,
            proposal=None, evidence=None, checkpoint=None):
    """Initial bounded pass, one targeted recovery pass; resume unfinished work.

    Validated earlier selections remain context-only. Every task result must
    pass exact resolution, target restrictions and joint validation before use.
    """
    from src.operations_console_v1 import ConsoleError
    started = time.monotonic()
    resuming = proposal is not None
    evidence = deepcopy(evidence or {})
    evidence["task_policy"] = VERSION
    evidence.setdefault("tasks", [])
    proposal = deepcopy(proposal or {"objects": [], "relations": [], "source_assessments": [], "abstain_reason": "no_validated_proposals"})
    # Source-role classification is independent of knowledge extraction. These
    # closed whole-range rules cannot classify arbitrary clinical text.
    if not resuming:
        for block in blocks:
            reason = metadata_reason(block["text"])
            if reason:
                proposal["source_assessments"].append({"span": full_span(block),
                    "role": "structure" if reason == "navigation" else "metadata", "reason": reason})
        if proposal["source_assessments"]:
            proposal["abstain_reason"] = None
    def units():
        from src.knowledge_materialisation_v1 import (
            materialise_knowledge_candidates,
            ordered_source_projection,
        )
        from src.semantic_passage_v1 import _project_semantic_selection
        decisions, coverage = _project_semantic_selection(**validator_input, proposal=proposal)
        candidates = materialise_knowledge_candidates(
            decisions,
            document_id=validator_input["document_id"],
            fragments=validator_input["fragments"],
        )
        return ordered_source_projection(
            candidates, decisions, coverage, validator_input["fragments"]
        )
    targets = _remaining_targets(units())
    if resuming:
        pending = evidence.get("pending_rejections") or []
        scope = [s for r in pending for s in r.get("spans", [])]
        if pending and all(r.get("spans") for r in pending):
            targets = [r for r in targets if any(s["block_id"] == r["span"]["block_id"] and
                max(s["start"], r["span"]["start"]) < min(s["end"], r["span"]["end"]) for s in scope)]
    phases = ["recovery"] if resuming else ["initial", "recovery"]
    budget_exhausted = False
    for phase in phases:
        if phase == "recovery" and not resuming:
            targets = _remaining_targets(units())
        phase_tasks = tasks_for(blocks, evidence_blocks, targets)
        for index, task in enumerate(phase_tasks):
            task_record = {key: deepcopy(task[key]) for key in ("task_id", "section_path", "target_spans")}
            task_record["phase"] = phase
            remaining = limits.total - (time.monotonic() - started)
            call = {"task_id": task["task_id"], "target_spans": task["target_spans"]}

            if remaining <= 0:
                # Budget exhaustion is one bounded lifecycle event, not N
                # separate durable checkpoints. Record every unstarted source
                # range in memory so recovery remains complete, persist once,
                # then return control to the caller immediately.
                for pending_task in phase_tasks[index:]:
                    pending_record = {key: deepcopy(pending_task[key])
                                      for key in ("task_id", "section_path", "target_spans")}
                    pending_record.update(phase=phase, status="not_started")
                    pending_call = {
                        "task_id": pending_task["task_id"],
                        "target_spans": deepcopy(pending_task["target_spans"]),
                        "error_code": "source_task_budget_exhausted",
                        "failure_reason": "source_task_budget_exhausted",
                    }
                    evidence["tasks"].append(pending_record)
                    if "target_spans" not in evidence and not evidence.get("supplementary_calls"):
                        evidence.update(pending_call)
                    else:
                        evidence.setdefault("supplementary_calls", []).append(pending_call)
                budget_exhausted = True
                if checkpoint:
                    checkpoint("proposal_received", {"provider_evidence": evidence,
                        "resolved_proposal": proposal, "resolved_proposal_hash": stable_json_hash(proposal)})
                break

            error = task.get("error_code")
            if error:
                call.update(error_code=error, failure_reason=error)
                task_record["status"] = "not_started"
            else:
                call_limits = replace(limits, total=min(remaining, MAX_CALL_SECONDS),
                    connect=min(limits.connect, remaining, MAX_CALL_SECONDS), idle=min(limits.idle, remaining, MAX_CALL_SECONDS))
                task_validator = {**validator_input, "allowed_candidate_block_ids": [b["block_id"] for b in task["source_blocks"]]}
                try:
                    result = provider(blocks=task["source_blocks"], evidence_blocks=task["evidence_blocks"],
                        selection_targets=[{"block_id": s["block_id"], "literal": next(b["text"] for b in blocks if b["block_id"] == s["block_id"])[s["start"]:s["end"]],
                                            "start": s["start"], "end": s["end"]} for s in task["target_spans"]] if phase == "recovery" else None,
                        task={"version": VERSION, "task_id": task["task_id"], "phase": phase,
                              "selectable_ranges": task["target_spans"], "context_only_block_ids": [b["block_id"] for b in task["evidence_blocks"]]},
                        model_limits=call_limits, evidence=call, validator_input=task_validator)
                    result, rejected = restrict_supplement(result, primary=proposal,
                        targets=[{"span": s} for s in task["target_spans"]])
                    call.setdefault("formation", {}).setdefault("rejections", []).extend(rejected)
                    call["formation"]["accepted_object_count"] = len(result["objects"])
                    if call["formation"]["rejections"]:
                        call["formation"]["status"] = "partial"
                    for rejection in call["formation"]["rejections"]:
                        if not rejection.get("spans"):
                            rejection["spans"] = deepcopy(task["target_spans"])
                    merged = merge_proposals(proposal, result)
                    if merged != proposal:
                        semantic_units_from_proposal(**validator_input, proposal=merged)
                    proposal = merged
                    task_record["status"] = "partial" if call["formation"]["rejections"] else "completed"
                except (ConsoleError, SemanticPassageError) as exc:
                    if exc.code.startswith("processing_"):
                        raise
                    call.update(error_code=exc.code, failure_reason=getattr(exc, "pre_review_diagnostics", {}).get("reason_code", exc.code))
                    task_record["status"] = "failed"
            evidence["tasks"].append(task_record)
            # Retain the established evidence/export format: first call plus
            # subsequent calls. No credentials or provider reasoning are stored.
            if "target_spans" not in evidence and not evidence.get("supplementary_calls"):
                evidence.update(call)
            else:
                evidence.setdefault("supplementary_calls", []).append(call)
            if checkpoint:
                checkpoint("proposal_received", {"provider_evidence": evidence,
                    "resolved_proposal": proposal, "resolved_proposal_hash": stable_json_hash(proposal)})
        if budget_exhausted:
            break
    evidence["recommendation_coverage"] = assess(blocks, proposal)
    evidence["pending_rejections"] = pending_rejections(evidence, proposal)
    evidence["formation_incomplete"] = bool(evidence["pending_rejections"])
    evidence["formation_state"] = "pending" if evidence["formation_incomplete"] else "complete"
    evidence["formation_progress"] = formation_progress(evidence)
    return proposal, evidence

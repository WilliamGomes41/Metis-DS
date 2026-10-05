"""Plan-based bounded formation. Tasks stay inside the working-revision evidence.

A resume continues the stored plan. It does not rebuild document processing
and it does not send completed source ranges to the provider again.
"""
from copy import deepcopy
from dataclasses import replace
import time

from src.bounded_formation_v1 import (
    formation_progress,
    full_span,
    tasks_for,
    MAX_CALL_SECONDS,
)
from src.recommendation_coverage_v1 import assess, merge_proposals
from src.recoverable_formation_v1 import pending_rejections, restrict_supplement
from src.semantic_passage_v1 import SemanticPassageError, semantic_units_from_proposal
from src.semantic_replay_v1 import stable_json_hash
from src.source_reconstruction_v1 import with_reconstruction_cache

VERSION = "bounded-formation-v2"
PLAN_VERSION = "formation-plan-v4"


def _overlaps(left, right):
    return (
        left.get("block_id") == right.get("block_id")
        and max(int(left.get("start", 0)), int(right.get("start", 0)))
        < min(int(left.get("end", 0)), int(right.get("end", 0)))
    )


def _public_task(task):
    return {key: deepcopy(task[key]) for key in (
        "task_id", "plan_task_id", "section_path", "target_spans", "context_signature",
    )}


def _context_signature(task):
    return stable_json_hash([
        {"block_id": block["block_id"], "text_hash": stable_json_hash(block["text"])}
        for block in task["evidence_blocks"]
    ])


def plan_tasks(blocks, evidence_blocks):
    """Deterministic tasks for one immutable source and this contract."""
    grouped = tasks_for(blocks, evidence_blocks)
    tasks = []
    for index, task in enumerate(grouped, start=1):
        signature = _context_signature(task)
        identity = {
            "version": VERSION,
            "plan_version": PLAN_VERSION,
            "section_path": task["section_path"],
            "spans": task["target_spans"],
            "context_signature": signature,
        }
        tasks.append({
            **task,
            "task_id": stable_json_hash(identity),
            "plan_task_id": f"T{index:03d}",
            "context_signature": signature,
        })
    return tasks


def build_plan(tasks, identity):
    body = {
        "version": PLAN_VERSION,
        "contract": VERSION,
        "source_hash": str(identity.get("source_hash") or ""),
        "extractor_version": str(identity.get("extractor_version") or ""),
        "reconstruction_version": str(identity.get("reconstruction_version") or ""),
        "semantic_contract_version": str(identity.get("semantic_contract_version") or ""),
        "tasks": [_public_task(task) for task in tasks],
    }
    return {**body, "plan_hash": stable_json_hash(body)}


def _pending_spans(task, evidence):
    pending = []
    for rejection in evidence.get("pending_rejections") or []:
        refs = list(rejection.get("spans") or [])
        if not refs:
            return list(task["target_spans"])
        for ref in refs:
            if any(_overlaps(span, ref) for span in task["target_spans"]) and ref not in pending:
                pending.append(deepcopy(ref))
    return pending


def _task_open(task, evidence):
    history = [row for row in evidence.get("tasks") or [] if row.get("task_id") == task["task_id"]]
    if not history:
        return True
    if not evidence.get("pending_rejections"):
        return False
    return bool(_pending_spans(task, evidence))


def _selection_targets(task, spans, blocks):
    return [{
        "block_id": span["block_id"],
        "literal": next(block["text"] for block in blocks if block["block_id"] == span["block_id"])[span["start"]:span["end"]],
        "start": span["start"],
        "end": span["end"],
    } for span in spans]


def _drop_background_objects(result):
    """A background proposal must not also become an answer-bearing object."""
    background = [row["span"] for row in result.get("source_assessments") or [] if row.get("role") == "background"]
    kept = []
    for obj in result.get("objects") or []:
        if any(_overlaps(span, ref) for span in obj.get("spans") or [] for ref in background):
            continue
        kept.append(obj)
    result = deepcopy(result)
    result["objects"] = kept
    if not kept and not result.get("source_assessments"):
        result["abstain_reason"] = result.get("abstain_reason") or "no_validated_proposals"
    return result


def _accounted_spans(result):
    refs = [item for obj in result.get("objects") or [] for item in obj.get("spans") or []]
    refs.extend(row.get("span") or {} for row in result.get("source_assessments") or [] if isinstance(row.get("span"), dict))
    return refs


def _range_difference(span, covers):
    """Return the parts of one target span that no accounted span covers."""
    start, end = int(span.get("start", 0)), int(span.get("end", 0))
    block_id = span.get("block_id")
    intervals = []
    for ref in covers:
        if ref.get("block_id") != block_id:
            continue
        lo, hi = max(start, int(ref.get("start", 0))), min(end, int(ref.get("end", 0)))
        if lo < hi:
            intervals.append((lo, hi))
    merged = []
    for lo, hi in sorted(intervals):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    gaps = []
    cursor = start
    for lo, hi in merged:
        if cursor < lo:
            gaps.append({**deepcopy(span), "start": cursor, "end": lo})
        cursor = max(cursor, hi)
    if cursor < end:
        gaps.append({**deepcopy(span), "start": cursor, "end": end})
    return gaps


def _unaccounted_ranges(spans, result):
    covers = _accounted_spans(result)
    gaps = []
    for span in spans:
        gaps.extend(_range_difference(span, covers))
    return gaps


def apply_formation_completion(evidence):
    """Formation is complete only when the original plan has no open source."""
    progress = formation_progress(evidence)
    unaccounted = [
        span
        for rejection in evidence.get("pending_rejections") or []
        if rejection.get("reason_code") == "unaccounted_source_range"
        for span in rejection.get("spans") or []
    ]
    plan = evidence.get("formation_plan") or {}
    progress.update(
        unaccounted_source_range_count=len(unaccounted),
        plan_hash=plan.get("plan_hash"),
        plan_version=PLAN_VERSION,
        semantic_contract_version=plan.get("semantic_contract_version"),
    )
    evidence["formation_progress"] = progress
    evidence["formation_incomplete"] = bool(
        progress["pending_task_count"]
        or progress["unknown_pending_count"]
        or progress["pending_source_range_count"]
        or progress["unaccounted_source_range_count"]
    )
    evidence["formation_state"] = "pending" if evidence["formation_incomplete"] else "complete"
    return evidence


def _store_call(evidence, call):
    if "target_spans" not in evidence and not evidence.get("supplementary_calls"):
        evidence.update(call)
    else:
        evidence.setdefault("supplementary_calls", []).append(call)


@with_reconstruction_cache
def execute(*, blocks, evidence_blocks, validator_input, provider, limits,
            proposal=None, evidence=None, checkpoint=None, plan_identity=None):
    """Execute only open plan tasks. Budget exhaustion persists once."""
    from src.operations_console_v1 import ConsoleError
    started = time.monotonic()
    resuming = proposal is not None
    evidence = deepcopy(evidence or {})
    evidence["task_policy"] = VERSION
    evidence.setdefault("tasks", [])
    proposal = deepcopy(proposal or {
        "objects": [], "relations": [], "source_assessments": [],
        "abstain_reason": "no_validated_proposals",
    })
    identity = dict(plan_identity or {})
    identity.setdefault("source_hash", stable_json_hash([full_span(block) | {"text_hash": stable_json_hash(block["text"])} for block in blocks]))
    fresh = plan_tasks(blocks, evidence_blocks)
    stored = (evidence.get("formation_plan") or {}).get("tasks")
    if resuming:
        if not stored:
            raise ConsoleError("formation_plan_missing")
        current = build_plan(fresh, {
            **identity,
            "source_hash": evidence["formation_plan"].get("source_hash") or identity.get("source_hash"),
            "extractor_version": evidence["formation_plan"].get("extractor_version") or identity.get("extractor_version"),
            "reconstruction_version": evidence["formation_plan"].get("reconstruction_version") or identity.get("reconstruction_version"),
            "semantic_contract_version": evidence["formation_plan"].get("semantic_contract_version") or identity.get("semantic_contract_version"),
        })
        if [row["task_id"] for row in current["tasks"]] != [row["task_id"] for row in stored]:
            raise ConsoleError("formation_plan_mismatch")
        by_id = {task["task_id"]: task for task in fresh}
        tasks = [by_id[row["task_id"]] for row in stored]
        plan = evidence["formation_plan"]
    else:
        tasks = fresh
        plan = build_plan(tasks, identity)
        evidence["formation_plan"] = plan
    open_tasks = [task for task in tasks if _task_open(task, evidence)]
    budget_exhausted = False
    for index, task in enumerate(open_tasks):
        remaining = limits.total - (time.monotonic() - started)
        if remaining <= 0:
            for pending_task in open_tasks[index:]:
                pending_record = _public_task(pending_task)
                pending_record.update(phase="initial" if not resuming else "resume", status="not_started")
                _store_call(evidence, {
                    "task_id": pending_task["task_id"],
                    "target_spans": deepcopy(pending_task["target_spans"]),
                    "error_code": "source_task_budget_exhausted",
                    "failure_reason": "source_task_budget_exhausted",
                })
                evidence["tasks"].append(pending_record)
            budget_exhausted = True
            if checkpoint:
                checkpoint("proposal_received", {
                    "provider_evidence": evidence,
                    "resolved_proposal": proposal,
                    "resolved_proposal_hash": stable_json_hash(proposal),
                })
            break
        phase = "initial" if not any(row.get("task_id") == task["task_id"] for row in evidence["tasks"]) else "resume"
        spans = task["target_spans"] if phase == "initial" else _pending_spans(task, evidence) or task["target_spans"]
        task_record = _public_task(task)
        task_record["phase"] = "initial" if phase == "initial" else "resume"
        call = {"task_id": task["task_id"], "target_spans": deepcopy(spans)}
        error = task.get("error_code")
        if error:
            call.update(error_code=error, failure_reason=error)
            task_record["status"] = "not_started"
        else:
            call_limits = replace(
                limits,
                total=min(remaining, MAX_CALL_SECONDS),
                connect=min(limits.connect, remaining, MAX_CALL_SECONDS),
                idle=min(limits.idle, remaining, MAX_CALL_SECONDS),
            )
            task_validator = {**validator_input, "allowed_candidate_block_ids": [block["block_id"] for block in task["source_blocks"]]}
            open_ids = {span["block_id"] for span in spans}
            source_blocks = [block for block in task["source_blocks"] if block["block_id"] in open_ids] if phase == "resume" else task["source_blocks"]
            try:
                result = provider(
                    blocks=source_blocks,
                    evidence_blocks=task["evidence_blocks"],
                    selection_targets=_selection_targets(task, spans, blocks) if phase == "resume" else None,
                    task={
                        "version": VERSION,
                        "task_id": task["task_id"],
                        "plan_task_id": task["plan_task_id"],
                        "phase": phase,
                        "selectable_ranges": spans,
                        "context_only_block_ids": [block["block_id"] for block in task["evidence_blocks"]],
                    },
                    model_limits=call_limits,
                    evidence=call,
                    validator_input=task_validator,
                )
                result = _drop_background_objects(result)
                result, rejected = restrict_supplement(
                    result, primary=proposal, targets=[{"span": span} for span in spans],
                )
                call.setdefault("formation", {}).setdefault("rejections", []).extend(rejected)
                call["formation"]["accepted_object_count"] = len(result["objects"])
                if call["formation"]["rejections"]:
                    call["formation"]["status"] = "partial"
                else:
                    call["formation"]["status"] = "validated"
                for rejection in call["formation"]["rejections"]:
                    if not rejection.get("spans"):
                        rejection["spans"] = deepcopy(spans)
                uncovered = _unaccounted_ranges(spans, result)
                if uncovered:
                    call["formation"]["rejections"].append({
                        "kind": "source_range",
                        "reason_code": "unaccounted_source_range",
                        "spans": uncovered,
                    })
                    call["formation"]["status"] = "partial"
                merged = merge_proposals(proposal, result)
                if merged != proposal:
                    semantic_units_from_proposal(**validator_input, proposal=merged)
                proposal = merged
                task_record["status"] = "partial" if call["formation"]["rejections"] else "completed"
            except (ConsoleError, SemanticPassageError) as exc:
                if getattr(exc, "code", "").startswith("processing_"):
                    raise
                call.update(
                    error_code=getattr(exc, "code", "semantic_proposal_invalid"),
                    failure_reason=getattr(exc, "pre_review_diagnostics", {}).get("reason_code", getattr(exc, "code", "semantic_proposal_invalid")),
                )
                task_record["status"] = "failed"
        evidence["tasks"].append(task_record)
        _store_call(evidence, call)
        if checkpoint and not budget_exhausted:
            checkpoint("proposal_received", {
                "provider_evidence": evidence,
                "resolved_proposal": proposal,
                "resolved_proposal_hash": stable_json_hash(proposal),
            })
    evidence["formation_plan"] = plan
    evidence["recommendation_coverage"] = assess(blocks, proposal)
    evidence["pending_rejections"] = pending_rejections(evidence, proposal)
    apply_formation_completion(evidence)
    return proposal, evidence

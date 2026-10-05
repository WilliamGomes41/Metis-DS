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
    pending_source_extent,
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
    return {key: deepcopy(task[key]) for key in ("task_id", "plan_task_id", "section_path", "target_spans")}


def plan_tasks(blocks, evidence_blocks):
    """Deterministic tasks for one immutable source and this contract."""
    grouped = tasks_for(blocks, evidence_blocks)
    tasks = []
    for index, task in enumerate(grouped, start=1):
        identity = {
            "version": VERSION,
            "plan_version": PLAN_VERSION,
            "section_path": task["section_path"],
            "spans": task["target_spans"],
        }
        tasks.append({
            **task,
            "task_id": stable_json_hash(identity),
            "plan_task_id": f"T{index:03d}",
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
        for span in task["target_spans"]:
            if any(_overlaps(span, ref) for ref in refs) and span not in pending:
                pending.append(deepcopy(span))
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
            try:
                result = provider(
                    blocks=task["source_blocks"],
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
    extent = pending_source_extent(evidence)
    evidence["formation_incomplete"] = bool(evidence["pending_rejections"]) or extent["unknown_pending_count"] > 0
    evidence["formation_state"] = "pending" if evidence["formation_incomplete"] else "complete"
    progress = formation_progress(evidence)
    progress.update(
        plan_hash=plan.get("plan_hash"),
        plan_version=PLAN_VERSION,
        semantic_contract_version=plan.get("semantic_contract_version"),
    )
    evidence["formation_progress"] = progress
    return proposal, evidence

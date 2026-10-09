"""Explicit processing command over existing durable source/attempt authority."""
from copy import deepcopy
from datetime import datetime
from statistics import median

from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.processing_retry_v1 import reserve, now, status


def authorize(console, actor_id, envelope):
    account = console._account(actor_id)
    if not {"researcher", "reviewer"}.intersection(account["roles"]):
        raise ConsoleError("researcher_role_required")
    if "researcher" not in account["roles"] and actor_id not in envelope.get("named_reviewers", []):
        raise ConsoleError("reviewer_not_named_on_snapshot")
    return account


def assert_resume_configuration(console, envelope):
    """A resume continues a persisted V3 checkpoint, never a new strategy.

    Legacy checkpoints predate attempt configuration; their persisted replay
    model/contract remains the compatibility authority. Exact replay validates
    the remaining source/extractor/prompt/schema identity before model work.
    A new deployment may resume a compatible checkpoint; an already accepted
    attempt remains fenced by its full stored configuration.
    """
    from src.source_bound_fields_v3 import MODE
    current = configuration(console)
    components = ((envelope.get("semantic_replay") or {}).get("identity") or {}).get("components") or {}
    if (current.get("mode") != MODE
            or str(current.get("model") or "").strip() != components.get("model_id")
            or "source-bound-fields-v3" not in components.get("semantic_contract_version", "")):
        raise ConsoleError("processing_resume_configuration_incompatible")
    previous = envelope.get("processing_configuration")
    if previous and any(previous.get(key) != current.get(key) for key in ("mode", "model", "docling")):
        raise ConsoleError("processing_resume_configuration_incompatible")
    return current


def reserve_selection(console, *, actor_id, snapshot_id, command_id, expected_revision):
    with console._reprocessing_transaction(snapshot_id):
        envelope = deepcopy(console._envelope(snapshot_id))
        authorize(console, actor_id, envelope)
        if console.snapshot_is_published(snapshot_id):
            raise ConsoleError("published_objects_must_not_be_rewritten")
        previous = next((a for a in envelope.get("processing_attempts", []) if a["command_id"] == command_id), None)
        if previous is not None:
            if (previous["actor_id"] != actor_id or previous["expected_revision"] != expected_revision
                    or previous["source_hash"] != envelope["sha256"]
                    or previous.get("source_version", envelope["version"]) != envelope["version"]):
                raise ConsoleError("processing_command_conflict")
            return deepcopy(previous), False
        objects, revision = console.snapshot_objects_and_revision(snapshot_id, include_blocked=True)
        if revision != expected_revision:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT, current_revision=revision)
        if console._can_resume_formation(snapshot_id):
            kind = "resume"
        else:
            if (objects or console._bindings.get(snapshot_id) or envelope.get("review_passes")
                    or envelope.get("publication_eligibility") != PRE_REVIEW_BLOCKED):
                raise ConsoleError("pre_review_retry_existing_work")
            # A received-but-unformed document may legitimately produce only
            # retained source passages. Recovery has the same activation
            # contract as its first selection, not the legacy blocked retry's
            # additional requirement for an answer-bearing candidate.
            kind = "ingest" if envelope.get("received_source") else "retry"
        if envelope.get("successor_guard"):
            from src.decision_successor_v1 import assert_parent_current
            assert_parent_current(console, envelope)
        envelope["processing_configuration"] = (assert_resume_configuration(console, envelope)
                                                    if kind == "resume" else configuration(console))
        attempt, fresh = reserve(envelope, command_id=command_id, actor_id=actor_id,
                                 revision=revision, clock=now(), limits=console._processing_limits(), kind=kind)
        if fresh:
            attempt["processing_configuration"] = deepcopy(envelope["processing_configuration"])
            attempt["dispatch"] = {"version": "source-dispatch-v1", "state": "pending"}
        console._commit_prepared_store(envelopes={snapshot_id: envelope}, snapshot_id=snapshot_id)
        return deepcopy(attempt), fresh


def configuration(console):
    from src.docling_pdf_v1 import enabled
    from src.attempt_diagnostics_v1 import deployment_identity
    reader = getattr(console, "_processing_configuration_reader", None)
    return {**(reader() if reader else {"mode": "unbound", "model": None}),
            "docling": enabled(), "deployment": deployment_identity()}


def _duration(start, end):
    try:
        return max(0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    except (ValueError, TypeError):
        return None


def estimate(envelope, documents):
    """Coarse range from recorded comparable full first attempts, never an SLA.

    Bytes are an imperfect size proxy. Reject dissimilar size/route/config and
    partial resumes; at least three observations are needed. No estimated
    duration is manufactured from a configured timeout.
    """
    size = (envelope.get("received_source") or {}).get("bytes")
    rates = []
    for prior in documents:
        prior_size = (prior.get("received_source") or {}).get("bytes")
        if not size or not prior_size or not .5 <= prior_size / size <= 2:
            continue
        if (prior.get("content_kind"), prior.get("class")) != (envelope.get("content_kind"), envelope.get("class")):
            continue
        for attempt in prior.get("processing_attempts", []):
            if attempt.get("state") != "succeeded" or attempt.get("kind") != "ingest":
                continue
            if prior.get("processing_configuration") != envelope.get("processing_configuration"):
                continue
            if prior.get("semantic_replay", {}).get("provider_evidence", {}).get("formation_incomplete"):
                continue
            elapsed = _duration(attempt.get("started_at"), attempt.get("finished_at"))
            if elapsed and elapsed >= 1:
                rates.append(elapsed / prior_size)
    if len(rates) < 3:
        return {"range_seconds": None, "sample_count": len(rates), "basis": "Onvoldoende vergelijkbare metingen."}
    central = median(rates) * size
    return {"range_seconds": [min(min(rates) * size, central * .5), max(max(rates) * size, central * 2)],
            "sample_count": len(rates), "basis": "Grove bandbreedte uit volledige eerdere pogingen en bestandsgrootte; broncomplexiteit kan afwijken."}


def projection(console, *, actor_id, snapshot_id, documents):
    from pathlib import Path
    from src.source_accountability_v1 import is_source_record
    from src.admission_gate_v1 import is_admission_blocked
    envelope = console._envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    processing = console.processing_status(snapshot_id, actor_id=actor_id)
    objects = console.snapshot_objects(snapshot_id)
    attempt = next(reversed(envelope.get("processing_attempts") or []), {})
    succeeded = bool(attempt.get("state") == "succeeded" or (not attempt and envelope.get("quality_processing_runs")))
    complete = succeeded and not processing["formation_incomplete"]
    current = processing["state"]
    state = ("bezig" if current == "running" else "onderbroken" if current in {"expired", "interrupted"}
             or (succeeded and not complete) else "mislukt" if current == "failed"
             else "voltooid" if complete else "nog niet gestart")
    elapsed = _duration(attempt.get("started_at"), attempt.get("finished_at") or now().isoformat())
    timing = estimate({**envelope, "processing_configuration": configuration(console)}, documents)
    remaining = None
    if state == "bezig" and timing["range_seconds"] and elapsed is not None:
        lo, hi = timing["range_seconds"]
        # Once the observed upper bound is exceeded, do not show false zero ETA.
        if elapsed < hi:
            remaining = [max(0, lo - elapsed), hi - elapsed]
    candidates = [o for o in objects if o.get("object_type") not in {"document", "heading", "path"} and not is_source_record(o)]
    blocked = sum(is_admission_blocked(o) for o in candidates)
    evidence = (envelope.get("semantic_replay") or {}).get("provider_evidence") or {}
    formation_blockers = len(evidence.get("pending_rejections") or []) if processing["formation_incomplete"] else 0
    if state == "mislukt":
        formation_blockers += 1
    return {"snapshot_id": snapshot_id, "title": envelope["title"],
            "filename": (envelope.get("received_source") or {}).get("filename") or Path(envelope["binary_path"]).name,
            "version": envelope["version"], "bytes": (envelope.get("received_source") or {}).get("bytes"),
            "state": state, "attempt_succeeded": succeeded, "formation_complete": complete,
            "phase": (attempt.get("diagnostic") or {}).get("phase") or attempt.get("phase") or "Nog niet gestart", "elapsed_seconds": elapsed,
            "estimate": timing, "remaining_seconds": remaining, "candidates": len(candidates),
            "source_passages": sum(is_source_record(o) for o in objects), "blocked": blocked,
            "formation_blockers": formation_blockers,
            "review_available": len(candidates) > blocked,
            "can_start": processing["retry_allowed"] or processing["resume_allowed"],
            "revision": console.objects_revision(snapshot_id), "progress": processing.get("formation_progress", {})}

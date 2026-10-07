"""Semantic and structural regression proof for #490.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.document_status_v1 import derive_lifecycle_status
from src.operations_console_v1 import PRE_REVIEW_BLOCKED, ConsoleError
from src.proportionate_review_v1 import ProportionateReviewConsole
from src.publish_authorization_v1 import still_matches, tuple_record
from src.review_policy_v1 import CONTRACT, project_policy
from src.review_workboard_v1 import ReviewWorkInputs, review_work_item, review_workboard_items
from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDocumentRuntimeStore
from src.workflows.workflow_review_postgres_v1 import WorkflowReviewStoreError
from tests.test_vsa_review_workboard_v1 import _obj


class NavigationProbe(_PostgresBadgeCountsMixin, ProportionateReviewConsole):
    """Counting disposable stores, not an alternative implementation of duties."""

    def __init__(self, count=10, documents=2, payload_size=0):
        self.calls = Counter()
        self.account = {"account_id": "reviewer-1", "roles": ["reviewer"]}
        self.envelopes = {}
        self.objects = {}
        self.bindings = {}
        self.releases = {}
        self.canonical_publication_store = object()
        self.workflow_document_store = SimpleNamespace(list_current_objects_batch=self.object_batch)
        self.workflow_review_store = SimpleNamespace(read_bindings=self.binding_batch)
        self._bindings = {}
        for n in range(documents):
            sid = f"synthetic-{n}"
            policy = {"contract": CONTRACT, "revision": 1, "primary": "reviewer-1",
                      "assignments": [{"reviewer_id": "reviewer-2", "participation": "required"}]}
            self.envelopes[sid] = {"snapshot_id": sid, "class": "richtlijn", "title": sid,
                                   "version": "1", "named_reviewers": ["reviewer-1", "reviewer-2"],
                                   "review_policy": policy, "state": "captured_not_published"}
            self.objects[sid] = [_obj(f"{sid}-{i}", "recommendation") for i in range(count)]
            for obj in self.objects[sid]:
                obj["object_version"] = "1"
                obj["confirmed_object_type"] = "recommendation"
                if payload_size:
                    obj["metadata"]["synthetic_evidence"] = [
                        {"sequence": i, "text": "synthetic evidence" * 8} for i in range(payload_size)]
            project_policy(self.objects[sid], policy)
            self.bindings[sid] = []

    def review_source_fragments(self, snapshot_id, **kwargs):
        from test_t4_single_knowledge_path_invariants import _allowed_source
        return _allowed_source()

    def _account(self, account_id):
        assert account_id == self.account["account_id"]
        return dict(self.account)

    def _workflow_badge_row(self, account_id):
        return {"explicit_review_documents": len(self.envelopes), "review": 0}

    def review_workboard_summaries(self, account_id, *, navigation_only=False):
        self.calls["summaries"] += 1
        return {sid: {"envelope": deepcopy(env)} for sid, env in self.envelopes.items()
                if account_id in env["named_reviewers"]
                and env.get("publication_eligibility") != PRE_REVIEW_BLOCKED}

    def _canonical_list_release_rows(self, snapshot_ids):
        self.calls["releases"] += 1
        return {sid: row for sid, row in self.releases.items() if sid in snapshot_ids}

    def object_batch(self, snapshot_ids):
        self.calls["objects"] += 1
        return {sid: deepcopy(self.objects[sid]) for sid in snapshot_ids}

    def binding_batch(self, snapshot_ids):
        self.calls["bindings"] += 1
        return {sid: deepcopy(self.bindings[sid]) for sid in snapshot_ids}

    def snapshot_objects(self, sid):
        self.calls["legacy_objects"] += 1
        return deepcopy(self.objects[sid])

    def object_review_bindings(self, sid):
        self.calls["legacy_bindings"] += 1
        current = {obj["object_id"]: obj for obj in self.snapshot_objects(sid)}
        return [{**row, "valid": bool(current.get(row["object_id"]))
                 and still_matches(row, current[row["object_id"]])} for row in self.bindings[sid]]

    def document_lifecycle_status(self, sid):
        self.calls["readiness"] += 1
        release, serving = self._release_dimensions(self.releases.get(sid))
        return derive_lifecycle_status(readiness={"curation_ready": False},
                                       release_status=release, serving_status=serving)

    def snapshot_is_published(self, sid):
        return sid in self.releases

    def old_review_count(self):
        return sum(item["work_state"] in {"review", "disposition", "technical_repair"}
                   for env in self.envelopes.values()
                   if (item := review_work_item(self, account=self.account, envelope=env)) is not None)

    def approve(self, reviewer):
        for sid, objects in self.objects.items():
            for obj in objects:
                obj["governance"]["validation_status"] = "approved"
                self.bindings[sid].append(tuple_record(
                    object_id=obj["object_id"], object_version=obj["object_version"],
                    canonical_object_hash=obj["provenance"]["canonical_object_hash"],
                    confirmed_object_type="recommendation", reviewer=reviewer,
                    reviewer_id=reviewer, decision="approve"))


@pytest.mark.parametrize("count", [1, 100, 500])
def test_navigation_batches_are_independent_of_passage_count(count):
    probe = NavigationProbe(count=count)
    assert probe.waiting_task_counts("reviewer-1")["review"] == 2
    assert probe.calls == {"summaries": 1, "releases": 1, "objects": 1, "bindings": 1}


@pytest.mark.parametrize("scenario", ["open", "waiting", "second", "done", "repair", "disposition",
                                       "blocked", "published", "withdrawn", "superseded", "unassigned"])
def test_navigation_semantics_match_existing_work_item(scenario):
    probe = NavigationProbe(count=2)
    if scenario in {"waiting", "second", "done"}:
        probe.approve("reviewer-1")
    if scenario == "second":
        probe.account["account_id"] = "reviewer-2"
    if scenario == "done":
        probe.approve("reviewer-2")
    for sid, env in probe.envelopes.items():
        if scenario == "blocked":
            env["publication_eligibility"] = PRE_REVIEW_BLOCKED
        if scenario == "unassigned":
            env["named_reviewers"] = []
        if scenario in {"published", "withdrawn", "superseded"}:
            probe.releases[sid] = {"status": "withdrawn" if scenario == "withdrawn" else "published",
                                   "item_count": 2, "active_same_release": 2 if scenario == "published" else 0,
                                   "active_other_release": 2 if scenario == "superseded" else 0}
        if scenario == "repair":
            for obj in probe.objects[sid]:
                obj["metadata"]["admission"]["gate_result"] = "blocked"
        if scenario == "disposition":
            for obj in probe.objects[sid]:
                obj["metadata"]["passage_register"]["status"] = "not_yet_assessed"
                obj["metadata"]["admission"]["gate_result"] = "blocked"
                obj["governance"]["validation_status"] = "rejected"
    expected = probe.old_review_count()
    before = deepcopy((probe.envelopes, probe.objects, probe.bindings))
    probe.calls.clear()
    assert probe.waiting_task_counts(probe.account["account_id"])["review"] == expected
    assert "readiness" not in probe.calls
    assert "legacy_objects" not in probe.calls
    assert (probe.envelopes, probe.objects, probe.bindings) == before


def test_next_read_observes_changes_and_account_isolation():
    probe = NavigationProbe(count=1)
    assert probe.waiting_task_counts("reviewer-1")["review"] == 2
    probe.approve("reviewer-1")
    assert probe.waiting_task_counts("reviewer-1")["review"] == 0
    probe.account["account_id"] = "reviewer-2"
    assert probe.waiting_task_counts("reviewer-2")["review"] == 2
    probe.approve("reviewer-2")
    assert probe.waiting_task_counts("reviewer-2")["review"] == 0


@pytest.mark.parametrize("roles", [["researcher"], [], ["publisher"]])
def test_non_reviewer_never_materializes_review_inputs(roles):
    probe = NavigationProbe()
    probe.account["roles"] = roles
    probe._published_snapshot_ids = lambda _ids: set()
    assert probe.waiting_task_counts("reviewer-1")["review"] == 0
    assert not probe.calls


def test_stale_envelope_publication_flag_cannot_close_canonical_work():
    probe = NavigationProbe(count=1)
    for envelope in probe.envelopes.values():
        envelope["state"] = "published"
    assert probe.waiting_task_counts("reviewer-1")["review"] == 2


def test_mixed_legacy_and_explicit_policy_uses_same_navigation_work_states():
    probe = NavigationProbe(count=1)
    original = probe.review_workboard_summaries
    probe.envelopes["synthetic-1"].pop("review_policy")
    def mixed(account_id, **kwargs):
        summaries = original(account_id, **kwargs)
        summaries["synthetic-1"].update(review_duties=1, first_review_duties=1,
                                      individual_pending=1, actionable_review_duties=1)
        return summaries
    probe.review_workboard_summaries = mixed
    assert probe.waiting_task_counts("reviewer-1")["review"] == 2
    assert "readiness" not in probe.calls


def test_review_dependency_failure_does_not_hide_work():
    probe = NavigationProbe()
    def unavailable(_ids):
        raise WorkflowReviewStoreError("synthetic read failure")
    probe.workflow_review_store.read_bindings = unavailable
    with pytest.raises(ConsoleError) as failure:
        probe.waiting_task_counts("reviewer-1")
    assert failure.value.code == "workflow_review_unavailable"


@pytest.mark.parametrize("empty", [False, True])
def test_workboard_reuses_policy_item_already_calculated(monkeypatch, empty):
    probe = NavigationProbe(count=1)
    summaries = probe.review_workboard_summaries("reviewer-1")
    for sid, summary in summaries.items():
        summary["work_item"] = (None if empty else
                                review_work_item(probe, account=probe.account, envelope=summary["envelope"]))
    def duplicate(*_args, **_kwargs):
        raise AssertionError("policy work item calculated twice")
    monkeypatch.setattr("src.review_workboard_v1.review_work_item", duplicate)
    assert len(review_workboard_items(probe, account=probe.account, summaries=summaries)) == (0 if empty else 2)


def test_batch_objects_keeps_current_versions_and_order():
    rows = [{"snapshot_id": "one", "position": n, "payload": obj}
            for n, obj in enumerate([{"object_id": "a", "object_version": "1"},
                                     {"object_id": "b", "object_version": "1"},
                                     {"object_id": "a", "object_version": "2"}])]
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, params):
            assert params == (["one"],)
            assert "ORDER BY snapshot_id,position" in sql
            return SimpleNamespace(fetchall=lambda: rows)
    store = object.__new__(PostgresWorkflowDocumentRuntimeStore)
    store._connect = lambda: Connection()
    assert store.list_current_objects_batch(["one"])["one"] == [
        {"object_id": "a", "object_version": "2"}, {"object_id": "b", "object_version": "1"}]


@pytest.mark.parametrize("documents", [1, 20])
def test_review_overview_batches_explicit_policy_inputs_and_keeps_fresh_duties(documents):
    from src.document_status_ui_v1 import _LIFECYCLE_BY_SNAPSHOT
    probe = NavigationProbe(count=3, documents=documents)
    lifecycle = {sid: probe.document_lifecycle_status(sid) for sid in probe.envelopes}
    token = _LIFECYCLE_BY_SNAPSHOT.set(lifecycle)
    try:
        for phase in ("open", "first-approved", "stale-binding"):
            if phase == "first-approved":
                probe.approve("reviewer-1")
            elif phase == "stale-binding":
                for rows in probe.objects.values():
                    rows[0]["object_version"] = "2"
            expected = {sid: review_work_item(probe, account=probe.account, envelope=env)
                        for sid, env in probe.envelopes.items()}
            summaries = probe.review_workboard_summaries("reviewer-1")
            probe.calls.clear()
            probe._enrich_review_workboard_summaries("reviewer-1", summaries)
            assert {sid: row["work_item"] for sid, row in summaries.items()} == expected
            assert probe.calls == {"objects": 1, "bindings": 1}
    finally:
        _LIFECYCLE_BY_SNAPSHOT.reset(token)


def test_review_overview_loads_missing_list_status_once_and_propagates_failure():
    probe = NavigationProbe(count=1, documents=3)
    def statuses(ids):
        probe.calls["list_status"] += 1
        return {sid: derive_lifecycle_status(readiness={"curation_ready": False},
                    release_status="none", serving_status="inactive") for sid in ids}
    probe.list_document_lifecycle_statuses = statuses
    summaries = probe.review_workboard_summaries("reviewer-1")
    probe.calls.clear()
    probe._enrich_review_workboard_summaries("reviewer-1", summaries)
    assert probe.calls == {"list_status": 1, "objects": 1, "bindings": 1}
    def unavailable(ids):
        raise WorkflowReviewStoreError("synthetic unavailable")
    probe.workflow_review_store.read_bindings = unavailable
    with pytest.raises(ConsoleError) as failure:
        probe._enrich_review_workboard_summaries("reviewer-1", summaries)
    assert failure.value.code == "workflow_review_unavailable"

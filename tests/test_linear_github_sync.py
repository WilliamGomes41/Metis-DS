"""Proof for #963: repository-owned projection, never completion authority."""
import copy
import json
from pathlib import Path

import pytest

from scripts import linear_github_sync as sync

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

TEAM = "2766ee91-9cc4-449b-92db-12ce6593d76a"
SHA = "a" * 40


def handoff(**changes):
    value = {"version": 1, "linear_issue": "MET-36", "head": SHA,
             "remaining_work": True, "next_step": "Meet de bestaande bronopdracht.", "evidence": []}
    value.update(changes)
    return "<!-- metis-linear-handoff-v1\n" + json.dumps(value) + "\n-->"


class GitHub:
    def __init__(self):
        self.issue = {"number": 729, "state": "open", "html_url": sync.REPO_URL + "/issues/729", "body": ""}
        self.comments = []
        self.prs = [{"number": 945, "state": "closed", "merged_at": "2026-10-31T00:00:00Z",
                     "body": "Part of MET-36.\n" + handoff(), "head": {"sha": SHA},
                     "html_url": sync.REPO_URL + "/pull/945"}]

    def pulls(self):
        return copy.deepcopy(self.prs)

    def issue_and_comments(self, number):
        assert number == 729
        return copy.deepcopy(self.issue), copy.deepcopy(self.comments)


class Linear:
    def __init__(self):
        self.issue = {"id": "uuid36", "identifier": "MET-36", "team": {"id": TEAM},
                      "updatedAt": "v1", "state": {"name": "In Progress"}, "priority": 1,
                      "assignee": {"id": "william"}, "labels": ["Nu"]}
        self.comments = []
        self.writes = []
        self.reads = 0
        self.conflict = False

    def read(self, identifier):
        assert identifier == "MET-36"
        self.reads += 1
        result = copy.deepcopy(self.issue)
        if self.conflict and self.reads > 1:
            result["updatedAt"] = "new external write"
        return result, copy.deepcopy(self.comments)

    def save_comment(self, issue_id, comment_id, body):
        assert issue_id == "uuid36"
        self.writes.append((comment_id, body))
        if comment_id is None:
            self.comments.append({"id": "owned-comment", "body": body})
        else:
            next(c for c in self.comments if c["id"] == comment_id)["body"] = body


def test_merge_and_closed_github_issue_never_close_linear_or_change_work_choice():
    gh, linear = GitHub(), Linear()
    gh.issue["state"] = "closed"
    before = copy.deepcopy(linear.issue)
    result = sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert result == {"changed": 1, "unchanged": 0}
    assert linear.issue == before
    assert len(linear.writes) == 1
    assert "gemerged" in linear.comments[0]["body"]
    assert "geen volledige oplevering" in linear.comments[0]["body"]


def test_identical_run_does_not_write_and_changed_source_updates_same_comment():
    gh, linear = GitHub(), Linear()
    sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)["changed"] == 0
    assert len(linear.writes) == 1
    gh.issue["state"] = "closed"
    sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert len(linear.comments) == 1
    assert linear.writes[-1][0] == "owned-comment"


def test_foreign_team_or_external_edit_blocks_before_mutation():
    gh, linear = GitHub(), Linear()
    linear.issue["team"]["id"] = "another team"
    with pytest.raises(sync.SyncError, match="team"):
        sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert not linear.writes
    linear.issue["team"]["id"] = TEAM
    linear.reads, linear.conflict = 0, True
    with pytest.raises(sync.SyncError, match="gewijzigd"):
        sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert not linear.writes


def test_dry_run_and_ambiguous_comment_do_not_write():
    gh, linear = GitHub(), Linear()
    sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=False)
    assert not linear.writes
    linear.comments = [{"id": str(n), "body": sync.MARKER} for n in range(2)]
    with pytest.raises(sync.SyncError, match="meerdere"):
        sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert not linear.writes


def test_handoff_gate_rejects_missing_wrong_target_and_stale_head():
    bindings = [sync.Binding(729, "MET-36")]
    for body in ["Part of MET-36.", "Part of MET-36.\n" + handoff(head="b" * 40),
                 "Part of MET-36.\n" + handoff(linear_issue="MET-43"),
                 "Part of MET-36.\n" + handoff(next_step=""),
                 "Part of MET-36. Part of MET-43.\n" + handoff()]:
        with pytest.raises(sync.SyncError):
            sync.validate_pr_handoff(body, SHA, bindings)
    sync.validate_pr_handoff("Part of MET-36.\n" + handoff(), SHA, bindings)


def test_untrusted_handoff_cannot_supply_next_step_and_latest_trusted_one_wins():
    gh, linear = GitHub(), Linear()
    gh.comments = [{"body": handoff(next_step="untrusted action"), "author_association": "NONE",
                    "updated_at": "2026-11-02", "html_url": sync.REPO_URL + "/issues/729#issuecomment-2"},
                   {"body": handoff(next_step="controleer bronbewijs"), "author_association": "OWNER",
                    "updated_at": "2026-11-01", "html_url": sync.REPO_URL + "/issues/729#issuecomment-1"}]
    sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert "controleer bronbewijs" in linear.comments[0]["body"]
    assert "untrusted action" not in linear.comments[0]["body"]


def test_explicit_remaining_package_scope_detects_false_done_without_changing_it():
    gh, linear = GitHub(), Linear()
    gh.prs[0]["author_association"] = "OWNER"
    linear.issue["state"] = {"name": "Done", "type": "completed"}
    before = copy.deepcopy(linear.issue)
    with pytest.raises(sync.SyncError, match="Done conflicteert"):
        sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    assert linear.issue == before
    assert len(linear.comments) == 1


def test_stale_receipt_does_not_accuse_current_done():
    gh, linear = GitHub(), Linear()
    gh.prs[0]["author_association"] = "OWNER"
    gh.prs[0]["head"]["sha"] = "b" * 40
    linear.issue["state"] = {"name": "Done", "type": "completed"}
    assert sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)["changed"] == 1


def test_all_sources_are_preflighted_before_first_write():
    gh, linear = GitHub(), Linear()
    def failing(number):
        if number == 1:
            raise sync.SyncError("bron niet beschikbaar")
        return gh.issue, []
    gh.issue_and_comments = failing
    with pytest.raises(sync.SyncError):
        sync.reconcile([sync.Binding(729, "MET-36"), sync.Binding(1, "MET-37")], gh, linear, apply=True)
    assert not linear.writes


def test_config_rejects_duplicate_or_out_of_scope_bindings(tmp_path):
    value = {"version": 1, "repository": sync.REPOSITORY, "team_id": TEAM,
             "bindings": [{"github_issue": 729, "linear_issue": "MET-36"}]}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value))
    assert sync.load_bindings(path) == [sync.Binding(729, "MET-36")]
    value["bindings"].append(value["bindings"][0])
    path.write_text(json.dumps(value))
    with pytest.raises(sync.SyncError):
        sync.load_bindings(path)
    value["bindings"] = [{"github_issue": 1, "linear_issue": "OTHER-1"}]
    path.write_text(json.dumps(value))
    with pytest.raises(sync.SyncError):
        sync.load_bindings(path)


def test_repository_workflow_uses_only_main_with_credentials_and_has_no_chat_host():
    import yaml
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/linear-github-sync.yml").read_text())
    events = workflow.get("on", workflow.get(True))
    assert {"schedule", "pull_request_target", "issues", "issue_comment", "workflow_dispatch", "pull_request"} <= set(events)
    job = workflow["jobs"]["reconcile"]
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["ref"] == "refs/heads/main"
    assert checkout["with"]["persist-credentials"] is False
    assert workflow["permissions"] == {"contents": "read", "issues": "read", "pull-requests": "read"}
    assert job["concurrency"]["cancel-in-progress"] is False
    for step in job["steps"]:
        assert "github.event." not in step.get("run", "")
    assert "--apply" in str(job["steps"])
    assert "LINEAR_API_KEY" in str(job["steps"])


def test_github_pagination_reads_beyond_first_hundred():
    class Api:
        def __init__(self):
            self.paths = []
        def github(self, path):
            self.paths.append(path)
            return [{"id": n} for n in range(100)] if path.endswith("&page=1") else [{"id": 100}]
    api = Api()
    assert len(sync.GitHub(api).pulls()) == 101
    assert len(api.paths) == 2 and "page=2" in api.paths[1]


def test_linear_pagination_finds_existing_comment_on_later_page():
    class Api:
        def __init__(self):
            self.cursors = []
        def linear(self, query, variables):
            self.cursors.append(variables["after"])
            page2 = variables["after"] == "next"
            return {"viewer": {"id": "bot"}, "issue": {
                "id": "uuid36", "identifier": "MET-36", "updatedAt": "v1", "team": {"id": TEAM},
                "comments": {"nodes": [{"id": "owned", "body": sync.MARKER, "user": {"id": "bot"}}] if page2 else [],
                             "pageInfo": {"hasNextPage": not page2, "endCursor": None if page2 else "next"}}}}
    api = Api()
    _, comments = sync.Linear(api).read("MET-36")
    assert api.cursors == [None, "next"]
    assert sync.owned(comments)["id"] == "owned"


def test_successful_create_with_lost_response_does_not_duplicate_on_retry():
    gh, linear = GitHub(), Linear()
    original = linear.save_comment
    def lost(*args):
        original(*args)
        raise sync.SyncError("response verloren")
    linear.save_comment = lost
    with pytest.raises(sync.SyncError, match="response verloren"):
        sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)
    linear.save_comment = original
    assert sync.reconcile([sync.Binding(729, "MET-36")], gh, linear, apply=True)["changed"] == 0
    assert len(linear.comments) == len(linear.writes) == 1


def test_missing_credentials_and_graphql_errors_fail_without_exposing_tokens(capsys, monkeypatch):
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-appear")
    assert sync.main([]) == 1
    assert "must-not-appear" not in capsys.readouterr().err
    api = sync.Api("github", "linear")
    monkeypatch.setattr(api, "_request", lambda *a: {"errors": [{"message": "secret must-not-appear"}]})
    with pytest.raises(sync.SyncError) as error:
        api.linear("query{}", {})
    assert "must-not-appear" not in str(error.value)

"""Offline fault/race cases at the existing ingest I/O boundaries.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
import time
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest

from src.operations_console_v1 import ConsoleError, SEMANTIC_REPLAY_SPEC_KEY
from .support import HTML, choice, command, console_at, observe, policy

TREE = json.dumps({"kind": "beslisboom-freeze", "paths": [{"id": "p", "text": "Bespreek de situatie"}],
                   "nodes": [{"id": "n", "text": "Is er een vraag?"}],
                   "outcomes": [{"id": "o", "text": "Maak een afspraak.", "applies_if": ["n"]}]}).encode()
CASES = ["immutable", "immutable_error", "immutable_value_error", "fetch_html", "fetch_named", "tree",
         "tree_with_policy", "tree_policy_on_guideline", "tree_empty", "tree_story", "tree_live_missing",
         "tree_live_empty", "tree_live_valid", "tree_live_payload_only", "tree_live_fetch_other_url", "tree_pdf_policy",
         "policy_without_configuration", "unmappable_policy", "new_version",
         "same_document_revision", "replay", "blocked_model", "blocked_docling", "unexpected_extraction_error",
         "bounded", "bounded_model_failure", "bounded_docling_failure", "bounded_other_failure",
         "bounded_deadline_before_check", "bounded_deadline_after_source_check", "bounded_commit_failure",
         "bounded_reservation_failure", "bounded_command_reservation_failure", "bounded_command_commit_failure",
         "registration_guard", "registration_guard_refusal",
         "receive_commit_failure", "receive_command_commit_failure", "plain_commit_failure", "command_commit_failure", "replay_command",
         "replay_received_command", "conflicting_command", "receive_existing_unkeyed",
         "receive_race_match", "receive_race_conflict", "bounded_race_match", "bounded_race_conflict",
         "receive_commit_race_match", "receive_commit_race_conflict", "bounded_commit_race_match",
         "bounded_commit_race_conflict", "final_commit_race_match", "final_commit_race_conflict"]


class ImmutableBytes:
    def __init__(self):
        self.data = None

    def store_verified(self, *, data, sha256, filename):
        self.data = data
        return f"g2:characterization/{sha256}/{filename}"

    def load_verified(self, locator):
        return self.data


@pytest.mark.parametrize("case", CASES)
def test_ingest_boundary_golden(case, tmp_path, monkeypatch, golden):
    import src.operations_console_v1 as op
    console = console_at(tmp_path)
    cmd = command()
    original_prepare = console._fragments_and_spec
    original_commit = console._commit_prepared_store
    if case.startswith("immutable"):
        console.immutable_source_store = ImmutableBytes()
        if case != "immutable":
            def fail_store(**kwargs):
                if case == "immutable_error":
                    raise op.G2SourceStoreError("fixture_unavailable")
                raise ValueError("fixture_invalid")
            monkeypatch.setattr(console.immutable_source_store, "store_verified", fail_store)
    if case.startswith("fetch"):
        cmd.update(url="https://example.test/source", data=None)
        console.url_fetcher = lambda _: (HTML, "text/html", "fetched.html")
        if case == "fetch_named":
            cmd.update(filename=None, content_type=None)
    if case.startswith("tree"):
        cmd.update(class_="beslisboom", data=TREE, filename="tree.json", content_type="application/json")
        if case in {"tree_with_policy", "tree_pdf_policy"}:
            cmd["review_policy"] = policy()
        if case == "tree_policy_on_guideline":
            cmd.update(class_="richtlijn", review_policy=policy())
        if case == "tree_empty":
            cmd["data"] = b'{"kind":"beslisboom-freeze","nodes":[],"outcomes":[]}'
        if case == "tree_story":
            cmd.update(data=HTML, filename="story.html")
        if case.startswith("tree_live"):
            cmd["live_url"] = "https://example.test/wp-json/beslisboom/example"
        if case == "tree_live_missing":
            cmd["data"] = None
        if case == "tree_live_empty":
            cmd["data"] = b'{"kind":"beslisboom-freeze"}'
        if case == "tree_live_payload_only":
            # The classifier sees a complete freeze even though the URL is live.
            cmd["url"] = cmd["live_url"]
            console.url_fetcher = lambda _: (TREE, "application/json", "tree.json")
        if case == "tree_live_fetch_other_url":
            cmd.update(url="https://example.test/export", data=None)
            console.url_fetcher = lambda _: (b"{}", "application/json", "tree.json")
        if case == "tree_pdf_policy":
            import fitz
            with fitz.open() as doc:
                doc.new_page().insert_text((80, 80), "Maak een afspraak.")
                cmd.update(data=doc.tobytes(no_new_id=True), filename="tree.pdf", content_type="application/pdf")
            # PDF/Docling conversion is outside this persistence boundary.
            def pdf_prepare(*args, **kwargs):
                raise ConsoleError("docling_fixture_conversion_unavailable")
            monkeypatch.setattr(console, "_fragments_and_spec", pdf_prepare)
    if case == "policy_without_configuration":
        cmd["review_policy"] = policy()
    if case == "unmappable_policy":
        cmd.update(review_policy=policy(primary="author", required=["reviewer", "other"]), named_reviewers=[],
                   review_choice=choice("two_others", ["reviewer", "other"]))
    if case in {"new_version", "same_document_revision"}:
        prior = console.ingest(**command())
        cmd.update(ingest_kind="new_version", replaces_snapshot_id=prior["snapshot_id"],
                   revision_reason="Synthetic revision")
        if case == "new_version":
            cmd["version"] = "2.0"
        else:
            cmd.update(review_policy=policy(), command_id="revision-command")
    bounded = case.startswith("bounded")
    if bounded:
        monkeypatch.setattr(console, "_bounded_semantic_preparation", lambda *args: True)
    if case == "replay":
        def replay(*args, **kwargs):
            fragments, spec = original_prepare(*args, **kwargs)
            spec[SEMANTIC_REPLAY_SPEC_KEY] = {"identity": {"contract": "fixture-replay"}, "provider_evidence": {}}
            return fragments, spec
        monkeypatch.setattr(console, "_fragments_and_spec", replay)
    if case in {"blocked_model", "blocked_docling", "unexpected_extraction_error", "bounded_model_failure",
                "bounded_docling_failure", "bounded_other_failure"}:
        code = ("docling_fixture_failure" if "docling" in case else
                "other_fixture_failure" if "other" in case or case == "unexpected_extraction_error" else
                "pre_review_llm_provider_unavailable")
        def fail_prepare(*args, **kwargs):
            raise ConsoleError(code)
        monkeypatch.setattr(console, "_fragments_and_spec", fail_prepare)
    if case in {"bounded_deadline_before_check", "bounded_deadline_after_source_check"}:
        clock = time.monotonic()
        values = iter([clock, clock + 10000] if case.endswith("before_check") else [clock, clock, clock + 10000])
        monkeypatch.setattr(op, "time", SimpleNamespace(monotonic=lambda: next(values)))
    if case.startswith("registration_guard"):
        cmd["_receive_only"] = True
        @contextmanager
        def boundary():
            with console._store_write_lock():
                yield
        cmd["_registration_boundary"] = boundary
        def guard(envelope):
            if case.endswith("refusal"):
                raise ConsoleError("fixture_registration_refused")
        cmd["_registration_guard"] = guard
    if case in {"receive_commit_failure", "receive_command_commit_failure", "plain_commit_failure", "command_commit_failure",
                "bounded_commit_failure", "bounded_command_commit_failure", "bounded_reservation_failure",
                "bounded_command_reservation_failure"}:
        if case.startswith("receive"):
            cmd["_receive_only"] = True
        if "command" in case:
            cmd["command_id"] = "fixture-command"
        def fail_commit(*args, **kwargs):
            if case in {"bounded_commit_failure", "bounded_command_commit_failure"} and not kwargs.get("objects", (None, []))[1]:
                return original_commit(*args, **kwargs)
            raise ConsoleError("fixture_commit_failed")
        monkeypatch.setattr(console, "_commit_prepared_store", fail_commit)
    if "race" in case or case in {"replay_command", "replay_received_command", "conflicting_command", "receive_existing_unkeyed"}:
        cmd["command_id"] = "same-command"
        if case == "receive_existing_unkeyed":
            cmd.pop("command_id")
        seed = console.ingest(**(cmd | {"_receive_only": True}))
        if case == "conflicting_command":
            cmd["title"] = "Changed payload"
        if case.startswith("receive") or case == "replay_received_command":
            cmd["_receive_only"] = True
        if case.endswith("conflict"):
            console._envelopes[seed["snapshot_id"]]["ingest_command"]["payload_hash"] = "different-winner"
            console._save_envelopes()
        if "race" in case:
            # Model a stale pre-registration read; real files retain the winning receipt.
            original_list, original_reload = console.list_envelopes, console._reload_store_locked
            calls = {"list": 0, "reload": 0}
            def stale_list():
                calls["list"] += 1
                if calls["list"] == 1:
                    console._envelopes = {}
                    return []
                return original_list()
            def stale_reload():
                calls["reload"] += 1
                original_reload()
                if "commit_race" in case and calls["reload"] == 2:
                    console._envelopes = {}
            monkeypatch.setattr(console, "list_envelopes", stale_list)
            monkeypatch.setattr(console, "_reload_store_locked", stale_reload)
    golden("ingest_boundaries", case, observe(console, lambda: console.ingest(**cmd)))

"""T11 behavioral regressions through existing commands (no invented RED API).
# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import pytest

from src.integrity_kernel import compute_canonical_object_hash
from src.operations_console_v1 import OperationsConsole, ConsoleError
from src.review_duty_v1 import exact_current_approver_ids
from tests.test_t9_review_knowledge_authority import _console, _approve
from tests.test_source_context_review_v1 import _system


def current(console, sid, oid):
    return next(o for o in console.snapshot_objects(sid) if o["object_id"] == oid)


def test_review_type_revision_has_real_predecessor_and_preserves_history(tmp_path):
    console, reviewer, sid, before = _console(tmp_path)
    original = deepcopy(before)
    _approve(console, reviewer, sid, before)
    after = current(console, sid, before["object_id"])
    assert after["object_version"] != original["object_version"]
    assert original in console.snapshot_objects(sid, include_blocked=True)
    assert after["provenance"]["previous_object_version"] == original["object_version"]
    assert after["provenance"]["revision_reason"]
    assert after["provenance"]["revision_patch_hash"]
    bindings = console.object_review_bindings(sid)
    assert exact_current_approver_ids(after, bindings) == (reviewer["account_id"],)


def test_source_context_target_has_explicit_predecessor(tmp_path):
    console, _, _, source, before, command = _system(tmp_path)
    console.confirm_source_context(**command)
    after = current(console, command["snapshot_id"], before["object_id"])
    assert before in console.snapshot_objects(command["snapshot_id"], include_blocked=True)
    assert after["object_version"] != before["object_version"]
    assert after["provenance"]["previous_object_version"] == before["object_version"]
    assert after["provenance"]["revision_reason"]
    assert after["provenance"]["revision_patch_hash"]


@pytest.mark.parametrize("new_version", ["1.0", "0.9"])
def test_correction_cannot_reuse_or_decrease_version(tmp_path, new_version):
    console, reviewer, sid, obj = _console(tmp_path)
    console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_id=obj["object_id"], decision="revise", comment="Expliciete correctie.")
    before = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    with pytest.raises((ValueError, ConsoleError)):
        console.correct_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=obj["object_id"], patch={"reason": "Correctie",
            "new_object_version": new_version,
            "operations": [{"op": "set", "path": "content.clean_text",
                            "value": obj["content"]["clean_text"]}]},
            expected_revision=console.objects_revision(sid))
    assert console.snapshot_objects(sid, include_blocked=True) == before


def test_unchanged_review_retry_keeps_revision_and_legacy_history(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj)
    rows = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    token = console.objects_revision(sid)
    _approve(console, reviewer, sid, obj)
    assert console.objects_revision(sid) == token
    assert console.snapshot_objects(sid, include_blocked=True) == rows
    restarted = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted.snapshot_objects(sid, include_blocked=True) == rows


def test_stale_review_writes_nothing(tmp_path):
    console, reviewer, sid, obj = _console(tmp_path)
    stale = console.objects_revision(sid)
    _approve(console, reviewer, sid, obj)
    rows = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        _approve(console, reviewer, sid, obj, expected_revision=stale)
    assert console.snapshot_objects(sid, include_blocked=True) == rows


def test_forward_cutover_chain_and_old_approval_does_not_carry(tmp_path):
    from src.revision_workflow import current_revisions, LINEAGE_CONTRACT
    console, _, reviewer, source, before, command = _system(tmp_path)
    sid = command["snapshot_id"]
    initial = deepcopy(console.snapshot_objects(sid, include_blocked=True))
    console.confirm_source_context(**command)
    first = current(console, sid, before["object_id"])
    edge = first["metadata"]["revision_lineage"]
    assert edge["contract"] == LINEAGE_CONTRACT
    assert edge["previous_lineage"] == "legacy_unverified"
    assert edge["previous_canonical_object_hash"] == compute_canonical_object_hash(before)
    assert edge["snapshot_id"] == sid
    console.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
        object_id=before["object_id"], decision="approve", confirmed_object_type="definition",
        relation_review_ack=True)
    approved = deepcopy(current(console, sid, before["object_id"]))
    old_bindings = deepcopy(console.object_review_bindings(sid))
    assert exact_current_approver_ids(approved, old_bindings)
    console.confirm_source_context(**{**command, "command_id": "context-second", "reason": "Herbevestigd",
                                    "expected_revision": console.objects_revision(sid)})
    successor = current(console, sid, before["object_id"])
    assert successor["provenance"]["previous_object_version"] == approved["object_version"]
    assert successor["metadata"]["revision_lineage"]["previous_lineage"] == "strict"
    assert exact_current_approver_ids(successor, old_bindings) == ()
    rows = console.snapshot_objects(sid, include_blocked=True)
    assert approved in rows
    assert all(obj in rows for obj in initial)
    assert current_revisions(rows, snapshot_id=sid) == console.snapshot_objects(sid)
    from src.review_closure_v1 import ReviewClosureConsole
    restarted = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted.snapshot_objects(sid, include_blocked=True) == rows


@pytest.mark.parametrize("corruption", ["missing", "hash", "cycle", "scope", "downgrade", "inplace"])
def test_strict_history_corruption_is_rejected_without_writes(tmp_path, corruption):
    from src.revision_workflow import current_revisions, validate_revision_write
    from src.integrity_kernel import stamp_canonical_hashes
    console, reviewer, sid, obj = _console(tmp_path)
    _approve(console, reviewer, sid, obj)
    rows = console.snapshot_objects(sid, include_blocked=True)
    changed = deepcopy(rows)
    last = next(o for o in reversed(changed) if o["object_id"] == obj["object_id"])
    edge = last["metadata"]["revision_lineage"]
    if corruption == "missing":
        changed = [o for o in changed if not (o["object_id"] == obj["object_id"]
                    and o["object_version"] == edge["previous_object_version"])]
    elif corruption == "hash":
        edge["previous_canonical_object_hash"] = "0" * 64
    elif corruption == "cycle":
        edge["previous_object_version"] = last["object_version"]
    elif corruption == "scope":
        edge["snapshot_id"] = "other-working-revision"
    elif corruption == "downgrade":
        last["metadata"].pop("revision_lineage")
    else:
        last["content"]["clean_text"] += " Changed."
    stamp_canonical_hashes(last)
    with pytest.raises(ValueError):
        validate_revision_write(rows, changed, snapshot_id=sid)
    assert console.snapshot_objects(sid, include_blocked=True) == rows


def test_legacy_unknown_is_not_proven_root_and_new_edge_is_exact(tmp_path):
    from src.revision_workflow import revise_object, current_revisions
    from src.integrity_kernel import stamp_canonical_hashes
    console, _, sid, original = _console(tmp_path)
    legacy = deepcopy(original)
    legacy["object_version"] = "1.0.1"
    stamp_canonical_hashes(legacy)
    desired = deepcopy(legacy)
    desired["content"]["clean_text"] += " Mutatie."
    strict = revise_object(legacy, desired, snapshot_id=sid, actor="reviewer", reason="explicit correction")
    assert strict["object_version"] == "1.0.2"
    assert strict["provenance"]["previous_object_version"] == "1.0.1"
    assert strict["metadata"]["revision_lineage"]["previous_lineage"] == "legacy_unverified"
    assert current_revisions([legacy, strict], snapshot_id=sid) == [strict]
    assert legacy["provenance"]["previous_object_version"] is None


def test_relation_supersedes_is_not_a_revision_predecessor(tmp_path):
    from src.revision_workflow import revise_object
    console, _, sid, original = _console(tmp_path)
    desired = deepcopy(original)
    desired["relations"] = [{"relation_type": "supersedes", "target_object_id": "different-object"}]
    strict = revise_object(original, desired, snapshot_id=sid, actor="reviewer", reason="relation confirmation")
    assert strict["provenance"]["previous_object_version"] == original["object_version"]
    assert strict["metadata"]["revision_lineage"]["object_id"] == original["object_id"]
    assert strict["relations"] == desired["relations"]


from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: E402,F401


def test_native_lineage_stale_fork_restart_and_reader_parity(recovery_postgres, tmp_path):
    from src.revision_workflow import revise_object, current_revisions
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console as native_console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    blob = FakeBlobStore()
    state = native_console(tmp_path, recovery_postgres, blob)
    state, _, _, source, before, command = _system(tmp_path, state)
    sid = command["snapshot_id"]
    store = state.workflow_document_store
    old_rows = deepcopy(store.list_document_objects(sid))
    stale = store.objects_revision(sid)
    state.confirm_source_context(**command)
    committed = deepcopy(store.list_document_objects(sid))
    after = current(state, sid, before["object_id"])
    assert before in committed
    assert after["metadata"]["revision_lineage"]["previous_canonical_object_hash"] == compute_canonical_object_hash(before)
    # Attempt a different successor version from the same stale predecessor.
    desired = deepcopy(before)
    desired["object_version"] = "2.0"
    desired["content"]["clean_text"] += " stale fork"
    fork = revise_object(before, desired, snapshot_id=sid, actor="stale", reason="correction")
    with pytest.raises((ValueError, WorkflowDocumentStoreError)):
        store.write_bundle(envelope=state._envelope(sid), objects=old_rows + [fork],
                           expected_revision=stale)
    assert store.list_document_objects(sid) == committed
    assert store.list_current_objects_batch([sid])[sid] == current_revisions(committed, snapshot_id=sid)
    root = tmp_path / "restarted"
    root.mkdir()
    restarted = native_console(root, recovery_postgres, blob)
    assert restarted.snapshot_objects(sid, include_blocked=True) == committed
    assert restarted.confirm_source_context(**command)["idempotent"]


def test_native_deferred_failure_rolls_back_strict_revision_and_review(recovery_postgres, tmp_path):
    import psycopg
    from src.review_ledger import read_events
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console as native_console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    state = native_console(tmp_path, recovery_postgres, FakeBlobStore())
    state, _, _, _, _, command = _system(tmp_path, state)
    sid = command["snapshot_id"]
    rows = deepcopy(state.snapshot_objects(sid, include_blocked=True))
    events = deepcopy(read_events(state._ledger_path))
    bindings = deepcopy(state.object_review_bindings(sid))
    with psycopg.connect(recovery_postgres.dsn) as connection:
        connection.execute("CREATE FUNCTION workflow.fail_t11() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 't11_commit_failure'; END; $$")
        connection.execute("CREATE CONSTRAINT TRIGGER fail_t11 AFTER INSERT ON workflow.document_objects DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.fail_t11()")
    try:
        with pytest.raises(Exception, match="t11_commit_failure"):
            state.confirm_source_context(**command)
        assert state.snapshot_objects(sid, include_blocked=True) == rows
        assert state.object_review_bindings(sid) == bindings
        assert read_events(state._ledger_path) == events
    finally:
        with psycopg.connect(recovery_postgres.dsn) as connection:
            connection.execute("DROP TRIGGER fail_t11 ON workflow.document_objects")
            connection.execute("DROP FUNCTION workflow.fail_t11()")


def test_legacy_history_reorder_cannot_restore_old_current_approval(tmp_path):
    from src.revision_workflow import validate_revision_write
    from src.integrity_kernel import stamp_canonical_hashes
    console, _, sid, first = _console(tmp_path)
    second = deepcopy(first)
    second["object_version"] = "1.0.1"
    stamp_canonical_hashes(second)
    with pytest.raises(ValueError, match="revision_history_reordered"):
        validate_revision_write([first, second], [second, first], snapshot_id=sid)


@pytest.mark.parametrize("attack", ["reorder", "promote_in_place", "alter_predecessor"])
@pytest.mark.parametrize("backend", ["file", "postgres"])
def test_locked_storage_rejects_adversarial_history(attack, backend, recovery_postgres, tmp_path):
    from src.integrity_kernel import stamp_canonical_hashes
    from src.revision_workflow import revise_object
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console as native_console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    if backend == "postgres":
        state = native_console(tmp_path, recovery_postgres, FakeBlobStore())
        state, _, _, _, obj, command = _system(tmp_path, state)
        sid = command["snapshot_id"]
    else:
        state, _, sid, obj = _console(tmp_path)
    original = deepcopy(state.snapshot_objects(sid, include_blocked=True))
    token = state.objects_revision(sid)
    if attack == "promote_in_place":
        changed = deepcopy(original)
        heading = next(o for o in changed if o["object_type"] == "heading")
        heading["object_type"] = heading["confirmed_object_type"] = "definition"
        heading["metadata"]["semantic_passage"] = deepcopy(obj["metadata"]["semantic_passage"])
        stamp_canonical_hashes(heading)
    else:
        desired = deepcopy(obj)
        desired["content"]["clean_text"] += " Corrected."
        strict = revise_object(obj, desired, snapshot_id=sid, actor="reviewer", reason="correction")
        changed = deepcopy(original) + [strict]
        if attack == "reorder":
            # Retained legacy revisions also cannot be reordered. Seed legacy
            # history in an isolated validation call; real storage rejects a
            # successor that appears before its actual predecessor.
            changed.remove(strict)
            changed.insert(0, strict)
        else:
            predecessor = next(o for o in changed if o["object_id"] == obj["object_id"])
            predecessor["governance"]["validated_by"] = "forged historical reviewer"
    with pytest.raises((ValueError, WorkflowDocumentStoreError, ConsoleError)):
        if backend == "file":
            state._save_objects(sid, changed, expected_revision=token)
        else:
            state.workflow_document_store.write_bundle(envelope=state._envelope(sid),
                objects=changed, expected_revision=token)
    assert state.snapshot_objects(sid, include_blocked=True) == original


def test_revision_rebinds_exact_relation_endpoints_and_preserves_predecessor(tmp_path):
    from src.revision_workflow import revise_object
    from src.knowledge_relations_v1 import build_knowledge_relation, validate_knowledge_relation_set
    from src.integrity_kernel import stamp_canonical_hashes
    _, _, sid, candidate = _console(tmp_path)
    original = deepcopy(candidate)
    relation = build_knowledge_relation(source_object_id=original["object_id"],
        source_object_version=original["object_version"], relation_type="supported_by",
        target_object_id="target", target_object_version="1.0")
    original["confirmed_knowledge_relations"] = [relation]
    stamp_canonical_hashes(original)
    before = deepcopy(original)
    proposed = deepcopy(original)
    proposed["content"]["clean_text"] += " Changed."
    revised = revise_object(original, proposed, snapshot_id=sid, actor="reviewer", reason="correction")
    assert original == before
    assert not validate_knowledge_relation_set(revised["confirmed_knowledge_relations"],
        source_object_id=revised["object_id"], source_object_version=revised["object_version"])
    after = revised["confirmed_knowledge_relations"][0]
    assert after["target_object_id"] == relation["target_object_id"]
    assert after["target_object_version"] == relation["target_object_version"]
    assert after["relation_id"] != relation["relation_id"]


def test_reprocessing_retirement_and_reappearance_preserve_strict_history(tmp_path):
    from src.revision_workflow import reprocessed_history, current_revisions
    _, _, sid, candidate = _console(tmp_path)
    retired = reprocessed_history([candidate], [], snapshot_id=sid, actor="researcher")
    assert retired[0] == candidate
    assert len(retired) == 2
    assert retired[-1]["governance"]["validation_status"] == "superseded"
    assert reprocessed_history(retired, [], snapshot_id=sid, actor="researcher") == retired
    restored = reprocessed_history(retired, [candidate], snapshot_id=sid, actor="researcher")
    assert restored[:2] == retired
    assert len(restored) == 3
    latest = current_revisions(restored, snapshot_id=sid)[0]
    assert latest["provenance"]["previous_object_version"] == retired[-1]["object_version"]
    assert latest["governance"]["validation_status"] == "needs_review"


def test_reprocessing_retains_nonknowledge_ancestor_of_promoted_candidate(tmp_path):
    from src.revision_workflow import revise_object, reprocessed_history, current_revisions, knowledge_revision
    from src.integrity_kernel import stamp_canonical_hashes
    _, _, sid, candidate = _console(tmp_path)
    structural = deepcopy(candidate)
    structural["object_type"] = "heading"
    structural.pop("confirmed_object_type", None)
    stamp_canonical_hashes(structural)
    assert not knowledge_revision(structural)
    promoted = revise_object(structural, candidate, snapshot_id=sid, actor="reviewer", reason="type confirmation")
    history = [structural, promoted]
    rebuilt = reprocessed_history(history, [candidate], snapshot_id=sid, actor="researcher")
    assert rebuilt[:2] == history
    assert current_revisions(rebuilt, snapshot_id=sid)


def test_legacy_published_history_remains_readable_but_cannot_gain_successor(tmp_path):
    from src.revision_workflow import revise_object, validate_revision_write, current_revisions
    _, _, sid, candidate = _console(tmp_path)
    published = deepcopy(candidate)
    published["governance"]["publication_status"] = "published"
    before = deepcopy(published)
    assert current_revisions([published], snapshot_id=sid) == [published]
    proposed = deepcopy(published)
    proposed["content"]["clean_text"] += " Correction."
    successor = revise_object(published, proposed, snapshot_id=sid, actor="reviewer", reason="correction")
    with pytest.raises(ValueError, match="published_working_revision_immutable"):
        validate_revision_write([published], [published, successor], snapshot_id=sid)
    assert published == before


def test_actual_file_legacy_publication_seals_type_relation_and_review_after_restart(tmp_path):
    from tests.test_durable_publication_console_v1 import MemorySourceStore
    from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history
    from src.integrity_kernel import stamp_canonical_hashes
    source = MemorySourceStore()
    state = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources",
                              runtime=tmp_path / "runtime", immutable_source_store=source)
    author = state.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = state.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    publisher = state.create_account(username="publisher", password="publisher-secret", roles=("publisher",))
    bind_fixture_selections(state, [("Oedeem is een ophoping van vocht.", "definition")])
    sid = state.ingest(actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=b"<html><body><h1>Begrippen</h1><p>Oedeem is een ophoping van vocht.</p></body></html>",
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-10-07", live_url="",
        class_="richtlijn", family="test", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    rows = state.snapshot_objects(sid)
    obj = next(o for o in rows if o.get("proposed_object_type") == "definition")
    obj["object_type"] = obj["confirmed_object_type"] = "definition"
    stamp_canonical_hashes(obj)
    install_fixture_history(state, sid, rows)
    _approve(state, reviewer, sid, obj)
    assert "revision_lineage" not in current(state, sid, obj["object_id"]).get("metadata", {})
    assert state.publish(actor_id=publisher["account_id"], snapshot_id=sid)["status"] == "PASS"
    before = deepcopy(state.snapshot_objects(sid, include_blocked=True))
    bindings = deepcopy(state.object_review_bindings(sid))
    projection = state._published_projection_path().read_bytes()
    restarted = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources",
                                  runtime=tmp_path / "runtime", immutable_source_store=source)
    assert restarted.snapshot_objects(sid, include_blocked=True) == before
    commands = [
        lambda: restarted.confirm_object_type(actor_id=reviewer["account_id"], snapshot_id=sid,
                    object_id=obj["object_id"], confirmed_object_type="explanation"),
        lambda: restarted.confirm_object_type(actor_id=reviewer["account_id"], snapshot_id=sid,
                    object_id=obj["object_id"], confirmed_object_type="definition"),
        lambda: restarted.confirm_relations(actor_id=reviewer["account_id"], snapshot_id=sid,
                    object_id=obj["object_id"], relations=[]),
        lambda: restarted.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
                    object_id=obj["object_id"], decision="later", suitability="mist_context"),
    ]
    for command in commands:
        with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
            command()
        assert restarted.snapshot_objects(sid, include_blocked=True) == before
        assert restarted.object_review_bindings(sid) == bindings
        assert restarted._published_projection_path().read_bytes() == projection


def test_source_context_rekeys_proposed_relations_before_readmission(tmp_path):
    from tests.test_d4_3_human_relation_confirmation import _console as relation_console, _accounts, _plant_proposals, _html, REC, COND, EXPL
    from tests.semantic_fixture_support import install_fixture_history
    from src.integrity_kernel import stamp_canonical_hashes
    from src.knowledge_relation_proposal_v1 import relation_proposal_admission_codes
    from src.knowledge_relations_v1 import validate_knowledge_relation_set
    state = relation_console(tmp_path)
    accounts = _accounts(state)
    from tests.semantic_fixture_support import bind_fixture_selections
    from tests.context_test_support import bind_detected_context
    bind_fixture_selections(state, [(REC, "recommendation"), (COND, "condition"), (EXPL, "explanation")])
    sid = state.ingest(actor_id=accounts["researcher"]["account_id"], filename="relations.html",
        data=_html(), content_type="text/html", ingest_kind="new", title="Relations",
        version="1.0", date="2026-10-07", live_url="", class_="richtlijn", family="test",
        named_reviewers=[accounts["reviewer"]["account_id"]])["snapshot_id"]
    bind_detected_context(state, sid, accounts["reviewer"]["account_id"])
    target, relations = _plant_proposals(state, sid, include_explanation=False)
    live = state.snapshot_objects(sid)
    source = next(o for o in live if o.get("object_type") == "heading")
    peer = next(o for o in live if o["object_id"] == relations[0]["target_object_id"])
    def spans(obj):
        return [{**span, "source_fragment_ids": [ref["raw_object_id"] for ref in obj["provenance"]["source_fragments"]]}
                for span in obj["metadata"]["semantic_passage"]["spans"]]
    target["metadata"]["knowledge_relation_evidence"] = {
        "version": "knowledge-relation-evidence-v1",
        "relations": [{**{key: relations[0][key] for key in ("relation_id", "relation_type", "target_object_id", "target_object_version")},
                       "source_spans": spans(target), "target_spans": spans(peer), "evidence_spans": spans(target)}]}
    stamp_canonical_hashes(target)
    rows = state.snapshot_objects(sid, include_blocked=True)
    rows = [target if (row["object_id"], row["object_version"]) == (target["object_id"], target["object_version"]) else row for row in rows]
    install_fixture_history(state, sid, rows)
    assert not relation_proposal_admission_codes(target, objects=state.snapshot_objects(sid))
    before = deepcopy(current(state, sid, target["object_id"]))
    state.confirm_source_context(actor_id=accounts["reviewer"]["account_id"], snapshot_id=sid,
        source_object_id=source["object_id"], role="context", target_object_ids=[target["object_id"]],
        reason="Bevestig context opnieuw.", command_id="t11-relation-context",
        expected_revision=state.objects_revision(sid))
    after = current(state, sid, target["object_id"])
    assert before in state.snapshot_objects(sid, include_blocked=True)
    assert not validate_knowledge_relation_set(after["proposed_knowledge_relations"],
        source_object_id=after["object_id"], source_object_version=after["object_version"])
    assert "relation_proposal_invalid" not in after["metadata"]["admission"]["reason_codes"]
    assert after["metadata"]["admission"]["gate_result"] == "allowed", after["metadata"]["admission"]["reason_codes"]


@pytest.mark.parametrize("profile", ["base", "closure"])
def test_scoped_commit_discards_stale_unrelated_published_maps(tmp_path, profile):
    state, reviewer, sid, _ = _console(tmp_path)
    if profile == "closure":
        from src.review_closure_v1 import ReviewClosureConsole
        state = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    # Only envelope/binding state is relevant to this cross-snapshot race.
    unrelated = "snap-unrelated-history"
    state._envelopes[unrelated] = {**deepcopy(state._envelope(sid)), "snapshot_id": unrelated}
    state._save_envelopes()
    stale_envelopes = deepcopy(state._envelopes)
    stale_bindings = deepcopy(state._bindings)
    stale_envelopes[sid]["title"] = "Updated open work"
    competing = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    competing._envelopes[unrelated].update(state="published", published=True)
    competing._save_envelopes()
    published = deepcopy(competing._envelope(unrelated))
    state._commit_prepared_store(envelopes=stale_envelopes, bindings=stale_bindings, snapshot_id=sid)
    assert state._envelope(unrelated) == published
    assert state._envelope(sid)["title"] == "Updated open work"


def test_legacy_duplicate_versions_keep_append_last_projection_and_strict_cutover(tmp_path):
    import json
    from tests.semantic_fixture_support import install_fixture_history
    from src.revision_workflow import revise_object, current_revisions, validate_revision_write
    from src.integrity_kernel import stamp_canonical_hashes
    state, _, sid, candidate = _console(tmp_path)
    first = deepcopy(candidate)
    last = deepcopy(candidate)
    last["content"]["clean_text"] += " Historical correction."
    stamp_canonical_hashes(last)
    rows = [first, last]
    install_fixture_history(state, sid, rows)
    state._envelopes[sid].update(state="published", published=True)
    state._save_envelopes()
    projection = state._published_projection_path()
    projection.write_text(json.dumps({"snapshot_id": sid, **last}) + "\n")
    published_bytes = projection.read_bytes()
    restarted = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted.snapshot_objects(sid) == [last]
    assert restarted.snapshot_objects(sid, include_blocked=True) == rows
    assert restarted.snapshot_is_published(sid)
    assert projection.read_bytes() == published_bytes
    with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
        restarted._save_objects(sid, rows)
    assert projection.read_bytes() == published_bytes
    # Same historical shape in OPEN work can prove a new direct edge.
    proposed = deepcopy(last)
    proposed["content"]["clean_text"] += " New correction."
    strict = revise_object(last, proposed, snapshot_id=sid, actor="reviewer", reason="correction")
    validate_revision_write(rows, rows + [strict], snapshot_id=sid)
    assert current_revisions(rows + [strict], snapshot_id=sid) == [strict]
    assert strict["metadata"]["revision_lineage"]["previous_lineage"] == "legacy_unverified"
    with pytest.raises(ValueError):
        validate_revision_write(rows, rows + [deepcopy(last)], snapshot_id=sid)
    with pytest.raises(ValueError):
        validate_revision_write([], rows, snapshot_id=sid)
    unmarked = deepcopy(last)
    unmarked["object_version"] = "1.0.1"
    stamp_canonical_hashes(unmarked)
    with pytest.raises(ValueError, match="revision_predecessor_required"):
        validate_revision_write([], [first, unmarked], snapshot_id=sid)


def test_identical_legacy_duplicate_ancestor_is_immutable_when_successor_is_added(tmp_path):
    from src.revision_workflow import revise_object, validate_revision_write
    _, _, sid, candidate = _console(tmp_path)
    rows = [deepcopy(candidate), deepcopy(candidate)]
    successor = revise_object(rows[-1], rows[-1], snapshot_id=sid, actor="reviewer",
                              reason="forced review change", force=True)
    tampered = deepcopy(rows)
    tampered[0]["governance"]["validation_status"] = "approved"
    with pytest.raises(ValueError, match="revision_history_changed"):
        validate_revision_write(rows, tampered + [successor], snapshot_id=sid)
    validate_revision_write(rows, rows + [successor], snapshot_id=sid)


def test_unchanged_legacy_duplicate_review_retry_preserves_prior_occurrences(tmp_path):
    from tests.semantic_fixture_support import install_fixture_history
    from src.integrity_kernel import stamp_canonical_hashes
    state, reviewer, sid, candidate = _console(tmp_path)
    candidate["object_type"] = candidate["confirmed_object_type"] = "definition"
    stamp_canonical_hashes(candidate)
    rows = [deepcopy(candidate), deepcopy(candidate)]
    install_fixture_history(state, sid, rows)
    for _ in range(2):
        state.review_object(actor_id=reviewer["account_id"], snapshot_id=sid,
            object_id=candidate["object_id"], decision="later",
            expected_revision=state.objects_revision(sid))
        history = state.snapshot_objects(sid, include_blocked=True)
        assert len(history) == 2
        assert history[0] == rows[0]
        assert history[-1]["object_version"] == candidate["object_version"]
    _approve(state, reviewer, sid, candidate)
    history = state.snapshot_objects(sid, include_blocked=True)
    assert len(history) == 2
    assert history[0] == rows[0]
    assert history[-1]["governance"]["validation_status"] == "approved"

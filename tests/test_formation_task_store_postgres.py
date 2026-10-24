"""#836 durable task boundary; real PostgreSQL, not an in-memory store.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang beschikbaarheid kwaliteit releasebewijs
"""
from copy import deepcopy
from pathlib import Path

import pytest

from src.semantic_replay_v1 import stable_json_hash
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from tests.test_d5_4_review_interaction_evidence import _system


def prepared(tmp_path, production_console):
    console, users, sid, _ = _system(tmp_path, production_console=production_console)
    envelope = console._envelope(sid)
    return console,envelope,validator_data(envelope)


def validator_data(envelope):
    from src.source_preparation_context_v1 import stored_extraction
    from src.pre_review_semantic_v1 import _content_fragments, _evidence_fragments
    from src.semantic_passage_v1 import semantic_source_blocks
    fragments = stored_extraction(envelope)
    data = {"fragments": _content_fragments(fragments), "document_id": envelope["document_id"],
            "evidence_fragments": _evidence_fragments(fragments),
            "allowed_candidate_block_ids": [b["block_id"] for b in semantic_source_blocks(_content_fragments(fragments))],
            "field_contract_v2": False, "field_contract_v3": True}
    return data


def checkpoint_context(console,envelope,data):
    from src.processing_retry_v1 import reserve,now
    from src.source_selection_v1 import configuration
    from src.attempt_diagnostics_v1 import validator_identity
    sid = envelope["snapshot_id"]
    envelope["processing_storage"] = "task-v1"
    attempt,_ = reserve(envelope,command_id="storage-proof",actor_id=envelope["uploader_account_id"],
        revision=console.objects_revision(sid),clock=now(),limits=console._processing_limits(),kind="reextract")
    attempt["processing_configuration"] = configuration(console)
    console.workflow_document_store.write_bundle(envelope=envelope)
    writer = console._diagnostic_writer(sid,attempt["attempt_id"])
    writer("source_reconstructed",{"validator_input":data,"validator_input_hash":stable_json_hash(data),
        "validator_identity":validator_identity(),"semantic_identity":envelope["semantic_replay"]["identity"]})
    return writer


def test_input_reference_survives_replacement_and_detects_corruption(tmp_path, production_console):
    console, envelope, data = prepared(tmp_path, production_console)
    store = FormationTaskStore(console.workflow_document_store)
    with store.documents._connect() as con:
        reference = store.retain_input(con, envelope=envelope, validator_input=data,
            semantic_identity=envelope["semantic_replay"]["identity"], expected_revision=console.objects_revision(envelope["snapshot_id"]))
    assert store.resolve_input(reference) == data
    with pytest.raises(WorkflowDocumentStoreError,match="formation_input_version_unsupported"):
        store.resolve_input({**reference,"version":2})
    with pytest.raises(WorkflowDocumentStoreError,match="formation_input_source_mismatch"):
        store.resolve_input(reference,expected_snapshot_id="another-document")
    with pytest.raises(WorkflowDocumentStoreError,match="formation_input_missing"):
        store.resolve_input({**reference,"artifact_id":"missing"})
    changed = deepcopy(envelope)
    changed.pop("prepared_source_extraction")
    console.workflow_document_store.write_bundle(envelope=changed)
    assert FormationTaskStore(console.workflow_document_store).resolve_input(reference) == data
    with store.documents._connect() as con:
        con.execute("UPDATE workflow.formation_inputs SET payload=payload || '{\"source_hash\":\"wrong\"}'::jsonb WHERE artifact_id=%s",
                    (reference["artifact_id"],))
    with pytest.raises(WorkflowDocumentStoreError, match="formation_record_integrity_failed"):
        store.resolve_input(reference)


def test_task_commit_is_atomic_idempotent_and_attempt_independent(tmp_path, production_console):
    console, envelope, data = prepared(tmp_path, production_console)
    store = FormationTaskStore(console.workflow_document_store)
    sid = envelope["snapshot_id"]
    with store.documents._connect() as con:
        FormationTaskStore.save_attempts(con, sid, envelope["processing_attempts"])
        reference = store.retain_input(con, envelope=envelope, validator_input=data,
            semantic_identity=envelope["semantic_replay"]["identity"], expected_revision=console.objects_revision(sid))
    payload = {"task": {"status": "completed"}, "proposal": {"objects": []}}
    ranges = [{"block_id": "block-1", "start": 0, "end": 5}]
    args = dict(context_id=reference["context_id"], ranges=ranges, payload=payload,
                attempt_id=envelope["processing_attempts"][-1]["attempt_id"], claim_token="claim-1")
    with pytest.raises(RuntimeError, match="crash-before-commit"):
        with store.documents._connect() as con:
            store.commit_task(con, **args)
            raise RuntimeError("crash-before-commit")
    assert store.task_results(reference["context_id"]) == []
    with store.documents._connect() as con:
        assert store.commit_task(con, **args)
    with store.documents._connect() as con:
        assert not store.commit_task(con, **{**args, "claim_token": "claim-2"})
    assert store.task_results(reference["context_id"]) == [payload]
    with pytest.raises(WorkflowDocumentStoreError, match="formation_task_result_conflict"):
        with store.documents._connect() as con:
            store.commit_task(con, **{**args, "payload": {"different": True}})
    with store.documents._connect() as con:
        assert con.execute("SELECT completed_task_count FROM workflow.formation_contexts WHERE context_id=%s",
                           (reference["context_id"],)).fetchone()["completed_task_count"] == 1


def test_new_checkpoint_does_not_reload_archive_or_take_global_write_lock(tmp_path, production_console, monkeypatch):
    from tests.test_console_read_architecture import _received
    from src.source_processing_dispatch_v1 import claim
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    sid = _received(console, users, title="Task checkpoint isolation")
    monkeypatch.setenv("METIS_FORMATION_TASK_STORAGE", "v1")
    attempt, _ = console.reserve_source_selection(actor_id=users["researcher"]["account_id"], snapshot_id=sid,
        command_id="targeted-checkpoint", expected_revision=console.objects_revision(sid))
    claimed = claim(console, snapshot_id=sid, attempt_id=attempt["attempt_id"])
    writer = console._diagnostic_writer(sid, claimed["attempt_id"])
    def forbidden(*args, **kwargs):
        raise AssertionError("checkpoint must not reload archive or use global lock")
    monkeypatch.setattr(console, "_store_write_lock", forbidden)
    monkeypatch.setattr(console, "refresh_workflow_documents", forbidden)
    writer("model_request", {"current_task": {"task_id": "task-1", "status": "running"}})
    with console.workflow_document_store._connect() as con:
        row = con.execute("SELECT envelope_payload FROM workflow.documents WHERE snapshot_id=%s", (sid,)).fetchone()
    assert "processing_attempts" not in row["envelope_payload"]
    assert console._envelope(sid)["processing_attempts"][-1]["diagnostic"]["phase"] == "model_request"
    from src.operations_console_v1 import ConsoleError
    console._record_processing_failure(sid,claimed["attempt_id"],ConsoleError("processing_test_failure"),
        claim_token=claimed["dispatch"]["token"])
    assert console._envelope(sid)["processing_attempts"][-1]["state"] == "failed"


@pytest.mark.parametrize("stop",["provider","joint"])
def test_resume_uses_committed_tasks_without_partial_activation(tmp_path, production_console, monkeypatch,stop):
    import json
    from src.operations_console_v1 import ConsoleError
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.source_bound_fields_v3 import MODE
    from tests.test_recommendation_context_v3 import response_for
    from tests.production_support import restart_production
    console, users, _, _ = _system(tmp_path, production_console=production_console)
    actor = users["researcher"]["account_id"]
    sid = console.receive_source(actor_id=actor,filename="three-tasks.html",content_type="text/html",
        data=b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p><h1>Drie</h1><p>Was dagelijks de handen.</p></body></html>',
        ingest_kind="new",title="Drie taken",version="1",date="2026-10-24",live_url="",class_="richtlijn",family="test",
        named_reviewers=[users["reviewer_a"]["account_id"]])["snapshot_id"]
    monkeypatch.setenv("METIS_FORMATION_TASK_STORAGE","v1")
    calls = []
    def provider(_url,_headers,payload,_timeout):
        data = json.loads(payload["input"][1]["content"])
        text = data["source_blocks"][0]["text"]
        calls.append(text)
        if stop == "provider" and len(calls) == 2:
            raise ConsoleError("processing_test_interrupted")
        proposal = response_for(payload,text)
        return {"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(proposal)}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console,environ={"METIS_PASSAGE_FORMATION_MODE":MODE,
            "METIS_LLM_API_KEY":"fixture","METIS_LLM_MODEL":"test"},post_json=provider)
    bind(console)
    import src.semantic_passage_v1 as semantic
    joint_counts = []
    rejected = []
    project = semantic._project_semantic_selection
    def counted(*args,**kwargs):
        count = len(kwargs["proposal"]["objects"])
        if count > 1:
            joint_counts.append(count)
            if stop == "joint" and not rejected:
                rejected.append(True)
                error = semantic.SemanticPassageError("semantic_proposal_invalid")
                error.finding["candidate_index"] = 1
                raise error
        return project(*args,**kwargs)
    monkeypatch.setattr(semantic,"_project_semantic_selection",counted)
    attempt,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id="initial",
        expected_revision=console.objects_revision(sid))
    with pytest.raises(ConsoleError,match="processing_test_interrupted" if stop == "provider" else "semantic_proposal_invalid"):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    first = calls[0]
    envelope = console._envelope(sid)
    assert "semantic_replay" not in envelope
    assert not console.snapshot_objects(sid)
    assert envelope["processing_attempts"][-1]["diagnostic"]["validator_input_ref"]
    restarted = restart_production(console)
    bind(restarted)
    following,_ = restarted.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id="resume",
        expected_revision=restarted.objects_revision(sid))
    assert following["kind"] == "resume"
    restarted.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    assert calls.count(first) == 1
    assert len(calls) == 4  # first success, interrupted call, two remaining calls
    assert joint_counts == ([3] if stop == "provider" else [3,3]), "One joint gate per changed complete result set"
    final = restarted._envelope(sid)
    assert final["processing_attempts"][-1]["state"] == "succeeded"
    assert restarted.snapshot_objects(sid)
    with restarted.workflow_document_store._connect() as con:
        stored = con.execute("SELECT envelope_payload FROM workflow.documents WHERE snapshot_id=%s",(sid,)).fetchone()["envelope_payload"]
        count = con.execute("SELECT COUNT(*) AS n FROM workflow.formation_task_results").fetchone()["n"]
    assert "processing_attempts" not in stored and count == 3
    from src.attempt_diagnostics_v1 import resolve_validator_input
    from src.processing_evidence_export_v1 import processing_evidence_tables
    task_store = FormationTaskStore(restarted.workflow_document_store)
    tables,_ = processing_evidence_tables(snapshot_id=sid,revision=restarted.objects_revision(sid),envelope=final,
        objects=restarted.snapshot_objects(sid),input_resolver=task_store.resolve_input,diagnostic_reader=task_store.diagnostic)
    assert len(tables["validator_inputs"]) == 1
    portable = tables["validator_inputs"][0]
    assert resolve_validator_input(final["processing_attempts"][-1]["diagnostic"],
        lambda ref: portable["validator_input"]) == task_store.resolve_input(portable["reference"])
    # Diagnostic history belongs to its original attempt, not later recovery.
    historical = task_store.diagnostic(final["processing_attempts"][0])
    assert len(historical["resolved_proposal"]["objects"]) == (1 if stop == "provider" else 3)
    if stop == "joint":
        with restarted.workflow_document_store._connect() as con:
            assert con.execute("SELECT COUNT(*) AS n FROM workflow.formation_task_result_history").fetchone()["n"] == 1


def test_explicit_migration_preserves_history_and_blocks_old_writers(tmp_path,production_console):
    import psycopg
    from scripts.migrate_processing_attempts import migrate
    console,envelope,_ = prepared(tmp_path,production_console)
    store = console.workflow_document_store
    sid = envelope["snapshot_id"]
    before = store.get_envelope(sid)
    assert not migrate(store,sid)["applied"]
    assert store.get_envelope(sid) == before
    result = migrate(store,sid,apply=True)
    assert result["applied"]
    after = store.get_envelope(sid)
    for attempt in after["processing_attempts"]:
        attempt.pop("_record_version")  # storage CAS metadata, not historical evidence
    assert after["processing_attempts"] == before["processing_attempts"]
    assert {k:v for k,v in after.items() if k != "processing_storage"} == before
    assert migrate(store,sid,apply=True)["status"] == "already_migrated"
    with pytest.raises(psycopg.Error,match="processing_storage_compatible_writer_required"):
        with store._connect() as con:
            con.execute("UPDATE workflow.documents SET envelope_payload=envelope_payload || '{\"processing_attempts\":[]}'::jsonb WHERE snapshot_id=%s",(sid,))


def test_process_kill_then_new_process_reuses_committed_work(tmp_path,production_console,monkeypatch):
    import json
    import subprocess
    import sys
    import time
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.source_bound_fields_v3 import MODE
    console,users,_,_ = _system(tmp_path,production_console=production_console)
    actor = users["researcher"]["account_id"]
    sid = console.receive_source(actor_id=actor,filename="crash.html",content_type="text/html",
        data=b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p></body></html>',
        ingest_kind="new",title="Procesherstart",version="1",date="2026-10-24",live_url="",class_="richtlijn",family="test",
        named_reviewers=[users["reviewer_a"]["account_id"]])["snapshot_id"]
    bind_pre_review_semantic_processing(console,environ={"METIS_PASSAGE_FORMATION_MODE":MODE,
        "METIS_LLM_API_KEY":"fixture","METIS_LLM_MODEL":"test"},post_json=lambda *_:None)
    monkeypatch.setenv("METIS_FORMATION_TASK_STORAGE","v1")
    attempt,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id="before-kill",expected_revision=console.objects_revision(sid))
    marker = tmp_path/"committed"
    command = [sys.executable,"-m","tests.formation_process_probe",str(console.root),console.workflow_document_store.config.dsn,
               sid,attempt["attempt_id"],actor,"crash",str(marker)]
    with (tmp_path/"child.log").open("w") as log:
        child = subprocess.Popen(command,stdout=log,stderr=log)
        try:
            deadline = time.monotonic()+20
            while not marker.exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(.02)
            assert marker.exists(), (tmp_path/"child.log").read_text()
        finally:
            child.kill()
            child.wait(timeout=5)
    # Advance the persisted expiry to model elapsed time. Recovery grants no
    # implicit deadline extension and follows the existing reserve/expire rules.
    with console.workflow_document_store._connect() as con:
        con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{expires_at}',"
                    "to_jsonb((CURRENT_TIMESTAMP-interval '1 second')::text)) WHERE attempt_id=%s",(attempt["attempt_id"],))
    assert not console.snapshot_objects(sid)
    following,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id="after-kill",expected_revision=console.objects_revision(sid))
    command[6] = following["attempt_id"]
    command[8] = "resume"
    completed = subprocess.run(command,capture_output=True,text=True,timeout=25)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.splitlines()[-1])["state"] == "succeeded"
    calls = [json.loads(line) for line in Path(str(marker)+".calls").read_text().splitlines()]
    assert calls.count(calls[0]) == 1 and len(calls) == 3


def test_checkpoint_cost_is_independent_of_archive_and_task_number(tmp_path,production_console,monkeypatch):
    import hashlib
    import json
    import os
    from statistics import median
    import time
    from src.console_performance_v1 import performance_scope
    console,envelope,data = prepared(tmp_path,production_console)
    sid = envelope["snapshot_id"]
    writer = checkpoint_context(console,envelope,data)
    writer.plan_tasks(130)
    measurements = {"tasks":[],"archive":[]}
    def sample(phase,values):
        started = time.perf_counter()
        with performance_scope() as metrics:
            writer(phase,values)
        return {"seconds":time.perf_counter()-started,"queries":metrics.queries,"json_bytes":metrics.json_bytes}
    def forbidden(*args,**kwargs):
        raise AssertionError("task checkpoint touched archive/global write lock")
    with monkeypatch.context() as patch:
        patch.setattr(console,"refresh_workflow_documents",forbidden)
        patch.setattr(console,"_store_write_lock",forbidden)
        for i in range(130):
            task = {"task_id":f"task-{i:03}","target_spans":[{"block_id":f"block-{i:03}","start":0,"end":20}],"status":"completed"}
            with performance_scope() as metrics:
                started = time.perf_counter()
                writer.commit_task(task=task,proposal={"objects":[],"relations":[],"source_assessments":[],"abstain_reason":"uncertain"},
                    evidence={"call":"fixed-size-call"},timing={"index":i})
            if i+1 in {10,50,100,130}:
                measurements["tasks"].append({"task_count":i+1,"seconds":time.perf_counter()-started,
                    "queries":metrics.queries,"json_bytes":metrics.json_bytes})
        baseline_bytes = measurements["tasks"][0]["json_bytes"]
        assert all(row["json_bytes"] == baseline_bytes for row in measurements["tasks"])
    bulk = [{"i":i,"text":hashlib.sha256(str(i).encode()).hexdigest()*4} for i in range(4000)]
    other = {k:v for k,v in envelope.items() if k not in {
        "processing_storage","processing_attempts","logical_document_id","working_revision_id",
        "working_revision_number","source_snapshot_id","source_version"}}
    other["archive_fixture"] = bulk
    from src.processing_retry_v1 import reserve,now
    from src.source_selection_v1 import configuration
    legacy = dict(other,snapshot_id="legacy-baseline",processing_attempts=[],processing_configuration=configuration(console))
    legacy.pop("archive_fixture")
    legacy_attempt,_ = reserve(legacy,command_id="legacy-baseline",actor_id=envelope["uploader_account_id"],
        revision=console.objects_revision(sid),clock=now(),limits=console._processing_limits(),kind="reextract")
    legacy_attempt["processing_configuration"] = configuration(console)
    console.workflow_document_store.write_bundle(envelope=legacy)
    legacy_writer = console._diagnostic_writer("legacy-baseline",legacy_attempt["attempt_id"])
    total = 0
    for target in (1,10,100):
        while total < target:
            other["snapshot_id"] = f"archive-{total:03}"
            console.workflow_document_store.write_bundle(envelope=other)
            total += 1
        sample("model_request",{"current_task":{"task_id":"fixed-size-task","status":"running"}})
        with monkeypatch.context() as patch:
            patch.setattr(console,"refresh_workflow_documents",forbidden)
            patch.setattr(console,"_store_write_lock",forbidden)
            rows = [sample("model_request",{"current_task":{"task_id":"fixed-size-task","status":"running"}}) for _ in range(15)]
        times = sorted(row["seconds"] for row in rows)
        before = []
        for _ in range(3):
            started = time.perf_counter()
            with performance_scope() as metrics:
                legacy_writer("model_request",{"current_task":{"task_id":"fixed-size-task","status":"running"}})
            before.append({"seconds":time.perf_counter()-started,"json_bytes":metrics.json_bytes})
        measurements["archive"].append({"other_documents":target,"median_seconds":median(times),"p95_seconds":times[-1],
            "json_bytes":rows[0]["json_bytes"],"queries":rows[0]["queries"],
            "legacy_median_seconds":median(row["seconds"] for row in before),"legacy_json_bytes":before[0]["json_bytes"]})
    assert len({r["json_bytes"] for r in measurements["archive"]}) == 1
    assert len({r["queries"] for r in measurements["archive"]}) == 1
    assert measurements["archive"][-1]["legacy_json_bytes"] > 10*measurements["archive"][0]["legacy_json_bytes"]
    with console.workflow_document_store._connect() as con:
        raw = con.execute("SELECT envelope_payload FROM workflow.documents WHERE snapshot_id=%s",(sid,)).fetchone()["envelope_payload"]
    assert "processing_attempts" not in raw
    report = os.environ.get("METIS_836_SCALING_REPORT")
    if report:
        Path(report).write_text(json.dumps(measurements,indent=2))
    print("FORMATION_SCALING",json.dumps(measurements))


@pytest.mark.parametrize("mutation,code",[("claim","processing_command_conflict"),
    ("expired","processing_attempt_expired"),("objects","processing_command_conflict"),
    ("source","processing_command_conflict"),("role","researcher_role_required")])
def test_checkpoint_fencing_rejects_without_writing(tmp_path,production_console,mutation,code):
    from src.operations_console_v1 import ConsoleError
    console,envelope,data = prepared(tmp_path,production_console)
    writer = checkpoint_context(console,envelope,data)
    with console.workflow_document_store._connect() as con:
        if mutation == "claim":
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{dispatch}',"
                "'{\"state\":\"claimed\",\"token\":\"new-owner\"}'::jsonb) WHERE attempt_id=%s",(writer.attempt_id,))
        elif mutation == "expired":
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{expires_at}',"
                "to_jsonb((CURRENT_TIMESTAMP-interval '1 second')::text)) WHERE attempt_id=%s",(writer.attempt_id,))
        elif mutation == "objects":
            con.execute("UPDATE workflow.documents SET object_generation=object_generation+1 WHERE snapshot_id=%s",(writer.snapshot_id,))
        elif mutation == "source":
            con.execute("UPDATE workflow.processing_attempts SET payload=jsonb_set(payload,'{source_hash}','\"wrong\"'::jsonb) WHERE attempt_id=%s",(writer.attempt_id,))
        else:
            con.execute("UPDATE workflow.accounts SET roles=ARRAY['publisher'] WHERE account_id=%s",(envelope["uploader_account_id"],))
        before = con.execute("SELECT COUNT(*) AS n FROM workflow.processing_checkpoints").fetchone()["n"]
    with pytest.raises(ConsoleError,match=code):
        writer("model_request",{"current_task":{"task_id":"forbidden"}})
    with console.workflow_document_store._connect() as con:
        assert con.execute("SELECT COUNT(*) AS n FROM workflow.processing_checkpoints").fetchone()["n"] == before
    if mutation == "claim":
        console._record_processing_failure(writer.snapshot_id,writer.attempt_id,ConsoleError("processing_test_failure"),claim_token=writer.claim_token)
        assert console._envelope(writer.snapshot_id)["processing_attempts"][-1]["state"] == "running"


def test_live_checkpoint_keeps_overview_and_document_readable(tmp_path,production_console,production_app,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    import psycopg
    from src.request_diagnostics_v1 import current_request_id
    from tests.test_insight_v1 import _login
    console,users,sid,_ = _system(tmp_path,production_console=production_console)
    envelope = console._envelope(sid)
    data = validator_data(envelope)
    writer = checkpoint_context(console,envelope,data)
    client = _login(console,users["researcher"]["username"],production_app=production_app)
    original = writer.store.checkpoint
    written,release = Event(),Event()
    def paused(*args,**kwargs):
        original(*args,**kwargs)
        written.set()
        assert release.wait(15)
    monkeypatch.setattr(writer.store,"checkpoint",paused)
    mutations = []
    execute = psycopg.Connection.execute
    def observed(connection,query,*args,**kwargs):
        if current_request_id() and isinstance(query,str) and query.lstrip().upper().startswith(("INSERT","UPDATE","DELETE")):
            if "workflow." in query:
                mutations.append(query.split()[0])
        return execute(connection,query,*args,**kwargs)
    monkeypatch.setattr(psycopg.Connection,"execute",observed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer,"model_request",{"current_task":{"task_id":"live","status":"running"}})
        try:
            assert written.wait(10)
            for _ in range(3):
                for url,limit in (("/source-selection",3),(f"/source-selection?document={envelope['snapshot_id']}",5)):
                    started = time.perf_counter()
                    response = client.get(url)
                    assert response.status_code == 200,response.text[:200]
                    assert time.perf_counter()-started < limit
            assert mutations == []
        finally:
            release.set()
        future.result(timeout=10)


def test_budget_stop_without_new_progress_consumes_retry_budget(tmp_path,production_console,monkeypatch):
    import json
    from types import SimpleNamespace
    import time
    import src.bounded_formation_v1 as bounded
    from src.bounded_model_call_v1 import ModelCallLimits
    from src.operations_console_v1 import ConsoleError
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
    from src.source_bound_fields_v3 import MODE
    from tests.test_recommendation_context_v3 import response_for
    console,users,_,_ = _system(tmp_path,production_console=production_console)
    actor = users["researcher"]["account_id"]
    sid = console.receive_source(actor_id=actor,filename="budget.html",content_type="text/html",
        data=b'<html><body><h1>Een</h1><p>Gebruik geen zalf.</p><h1>Twee</h1><p>Controleer dagelijks de huid.</p></body></html>',
        ingest_kind="new",title="Budget",version="1",date="2026-10-24",live_url="",class_="richtlijn",family="test",
        named_reviewers=[users["reviewer_a"]["account_id"]])["snapshot_id"]
    elapsed = [0]
    def provider(_url,_headers,payload,_timeout):
        text = json.loads(payload["input"][1]["content"])["source_blocks"][0]["text"]
        proposal = response_for(payload,text)
        elapsed[0] = 2
        return {"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(proposal)}]}]}
    bind_pre_review_semantic_processing(console,environ={"METIS_PASSAGE_FORMATION_MODE":MODE,
        "METIS_LLM_API_KEY":"fixture","METIS_LLM_MODEL":"test"},post_json=provider)
    monkeypatch.setenv("METIS_FORMATION_TASK_STORAGE","v1")
    monkeypatch.setattr(console,"_model_call_limits_reader",lambda:ModelCallLimits(total=1))
    monkeypatch.setattr(bounded,"time",SimpleNamespace(monotonic=lambda:time.monotonic()+elapsed[0]))
    attempt,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id="budget-first",expected_revision=console.objects_revision(sid))
    with pytest.raises(ConsoleError,match="source_task_budget_exhausted"):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    first = console._envelope(sid)["processing_attempts"][-1]
    assert first["state"] == "incomplete_budget" and first["formation_progress_made"] is True
    assert not console.snapshot_objects(sid)
    monkeypatch.setattr(console,"_model_call_limits_reader",lambda:ModelCallLimits(total=0))
    following,_ = console.reserve_source_selection(actor_id=actor,snapshot_id=sid,command_id="budget-empty",expected_revision=console.objects_revision(sid))
    with pytest.raises(ConsoleError,match="source_task_budget_exhausted"):
        console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=following)
    latest = console._envelope(sid)["processing_attempts"][-1]
    assert latest["state"] == "incomplete_budget" and latest["formation_progress_made"] is False
    assert console.processing_status(sid)["retry_attempts_used"] == 1


def test_concurrent_task_commits_keep_one_durable_result(tmp_path,production_console):
    from concurrent.futures import ThreadPoolExecutor
    from src.formation_checkpoint_v1 import task_checkpoint_writer
    console,envelope,data = prepared(tmp_path,production_console)
    first = checkpoint_context(console,envelope,data)
    first.plan_tasks(1)
    second = task_checkpoint_writer(console,first.snapshot_id,first.attempt_id)
    payload = {"task":{"task_id":"same-task","status":"completed","target_spans":[{"block_id":"block","start":0,"end":10}]},
        "proposal":{"objects":[],"relations":[],"source_assessments":[],"abstain_reason":"uncertain"},"evidence":{},"timing":{}}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(writer.commit_task,**payload) for writer in (first,second)]
        for future in results:
            future.result(timeout=10)
    assert len(first.task_results()) == 1
    assert first.store.progress(first.input_reference["context_id"])["terminal_task_count"] == 1


def test_stale_document_write_cannot_erase_newer_checkpoint(tmp_path,production_console):
    console,envelope,data = prepared(tmp_path,production_console)
    writer = checkpoint_context(console,envelope,data)
    stale = console._envelope(writer.snapshot_id)
    writer("model_request",{"current_task":{"task_id":"newer-checkpoint"}})
    stale["title"] = "Independent document metadata edit"
    console.workflow_document_store.write_bundle(envelope=stale)
    current = console._envelope(writer.snapshot_id)
    assert current["title"] == stale["title"]
    assert current["processing_attempts"][-1]["diagnostic"]["phase"] == "model_request"

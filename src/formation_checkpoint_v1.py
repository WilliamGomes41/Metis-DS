"""Fenced task checkpoints without StoreCommand's archive/process-lock reload.

Only this checkpoint operation bypasses the shared in-process command maps. It
uses PostgreSQL-owned document, account and attempt records in a short transaction.
"""
from contextlib import contextmanager
from copy import deepcopy

from src.operations_console_v1 import ConsoleError
from src.processing_retry_v1 import assert_active, now
from src.source_selection_v1 import authorize_account, configuration
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import _json_text, WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_transaction_active


class TaskCheckpointWriter:
    def __init__(self, console, snapshot_id, attempt):
        self.console, self.snapshot_id = console, snapshot_id
        self.store = FormationTaskStore(console.workflow_document_store)
        self.attempt_id = attempt["attempt_id"]
        self.claim_token = (attempt.get("dispatch") or {}).get("token")
        self.configuration = deepcopy(attempt.get("processing_configuration"))
        if not self.configuration:
            raise ConsoleError("processing_configuration_unpinned")
        self.preparation = None
        self.source_payload = None
        self.source_reference = deepcopy((attempt.get("diagnostic") or {}).get("source_views_ref"))
        self.plan_reference = deepcopy((attempt.get("diagnostic") or {}).get("task_plan_ref"))
        self.input_reference = deepcopy((attempt.get("diagnostic") or {}).get("validator_input_ref"))
        if attempt.get("kind")=="resume" and self.source_reference is not None and self.input_reference is None:
            raise ConsoleError("formation_input_required")

    @contextmanager
    def _locked(self):
        if workflow_transaction_active():
            raise ConsoleError("formation_checkpoint_requires_independent_transaction")
        if self.configuration and self.configuration != configuration(self.console):
            raise ConsoleError("processing_configuration_changed")
        with self.store.documents._connect() as con:
            with con.transaction():
                con.execute("SET LOCAL lock_timeout='5s'")
                document = con.execute(
                    "SELECT snapshot_id,source_sha256 AS sha256,source_version AS version,document_id,"
                    "state,working_revision_id,object_generation,processing_storage_version "
                    "FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE", (self.snapshot_id,)).fetchone()
                if not document or document["processing_storage_version"] != 1:
                    raise ConsoleError("processing_storage_compatible_writer_required")
                row = con.execute("SELECT payload,object_generation FROM workflow.processing_attempts "
                                  "WHERE snapshot_id=%s AND attempt_id=%s FOR UPDATE",
                                  (self.snapshot_id,self.attempt_id)).fetchone()
                if not row:
                    raise ConsoleError("processing_attempt_not_active")
                active = assert_active({"processing_attempts": [row["payload"]]}, self.attempt_id, now())
                if (active["source_hash"] != document["sha256"]
                        or active["source_version"] != document["version"]
                        or row["object_generation"] != document["object_generation"]
                        or active.get("processing_configuration") != self.configuration
                        or (active.get("dispatch") or {}).get("token") != self.claim_token):
                    raise ConsoleError("processing_command_conflict")
                dispatch = active.get("dispatch") or {}
                if dispatch and (dispatch.get("state") != "claimed" or not self.claim_token):
                    raise ConsoleError("processing_command_conflict")
                account = con.execute("SELECT account_id,roles,retirement FROM workflow.accounts "
                                      "WHERE account_id=%s FOR SHARE", (active["actor_id"],)).fetchone()
                if not account:
                    raise ConsoleError("not_authenticated")
                document["named_reviewers"] = [r["account_id"] for r in con.execute(
                    "SELECT account_id FROM workflow.document_reviewers WHERE snapshot_id=%s",(self.snapshot_id,)).fetchall()]
                authorize_account(account, document)
                if self.store.documents._release_history_locked(con, self.snapshot_id):
                    raise ConsoleError("published_objects_must_not_be_rewritten")
                yield con, active
                # Expiry may occur while waiting for another actor's row lock.
                assert_active({"processing_attempts": [active]}, self.attempt_id, now())
                con.execute("UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s",
                            (_json_text(active),self.attempt_id))
                self.store.checkpoint_summary(con,self.snapshot_id,active)

    def __call__(self, phase, values):
        # Timings are attempt evidence, but each checkpoint carries only its
        # latest task measurement, never the cumulative list.
        values = dict(values)
        if "formation_timings" in values:
            values["formation_timings"] = values["formation_timings"][-1:]
        reference = None
        if "validator_input" in values and self.preparation is not None:
            from src.semantic_replay_v1 import stable_json_hash
            data=values.pop("validator_input")
            if stable_json_hash(data)!=self.input_reference["validator_input_hash"]:
                raise ConsoleError("processing_resume_context_incompatible")
            with self._locked() as (con,active):
                identity=con.execute("SELECT semantic_identity FROM workflow.formation_contexts WHERE context_id=%s",
                    (self.input_reference["context_id"],)).fetchone()
                if not identity or identity["semantic_identity"]!=values["semantic_identity"]:
                    raise ConsoleError("processing_resume_context_incompatible")
                self.store.checkpoint(con,self.attempt_id,phase,{**values,"validator_input_ref":self.input_reference})
                active.setdefault("diagnostic",{}).update(phase=phase,**values,validator_input_ref=self.input_reference)
        elif "validator_input" in values:
            envelope = self.console._envelope(self.snapshot_id)
            with self._locked() as (con, active):
                reference = self.store.retain_input(con, envelope=envelope,
                    validator_input=values.pop("validator_input"), semantic_identity=values["semantic_identity"],
                    expected_revision=active["expected_revision"])
                if active.get("kind") == "resume" and self.input_reference and reference != self.input_reference:
                    raise ConsoleError("processing_resume_context_incompatible")
                values["validator_input_ref"] = reference
                self.store.checkpoint(con,self.attempt_id,phase,values)
                active.setdefault("diagnostic", {}).update(phase=phase, **values)
            self.input_reference = reference
        else:
            with self._locked() as (con, active):
                self.store.checkpoint(con,self.attempt_id,phase,values)
                active.setdefault("diagnostic", {})["phase"] = phase
                if phase=="extraction_reused":
                    active["diagnostic"]["extraction_checkpoint"]=values["extraction_checkpoint"]
        from src.processing_trace_v1 import observe
        observe("processing_checkpoint",self.snapshot_id,active,phase=phase)

    def before_task(self):
        from src.worker_handover_v1 import before_task
        return before_task(self)

    def task_results(self):
        if not self.input_reference:
            return []
        return self.store.task_results(self.input_reference["context_id"])

    def validate_resume_input(self):
        if self.input_reference:
            try:
                self.preparation = self.store.resolve_preparation(self.input_reference,expected_snapshot_id=self.snapshot_id)
            except WorkflowDocumentStoreError as error:
                raise ConsoleError(str(error)) from error

    def source_from_extraction(self,extraction):
        try:
            root=self.store.load_source_views({"extraction":extraction},self.source_reference)
        except WorkflowDocumentStoreError as error:
            raise ConsoleError(str(error)) from error
        if root is None:
            return None
        self.source_payload=root.payload
        return root.fragments

    def retained_source(self,required_contract):
        if self.preparation is None:
            self.validate_resume_input()
        if self.preparation is None:
            raise ConsoleError("formation_input_required")
        extraction=self.preparation["extraction"]
        if extraction["extractor_contract"]!=required_contract:
            raise ConsoleError("source_extraction_contract_mismatch")
        try:
            root=self.store.load_source_views(self.preparation,self.source_reference)
        except WorkflowDocumentStoreError as error:
            raise ConsoleError(str(error)) from error
        if root is not None:
            self.source_payload=root.payload
            return root.fragments,extraction["source"],{k:extraction[k] for k in ("record_hash","fragments_hash")}
        from src.source_preparation_context_v1 import KEY,stored_extraction
        return stored_extraction({**extraction["source"],KEY:extraction}),extraction["source"],{k:extraction[k] for k in ("record_hash","fragments_hash")}

    def retain_source_views(self,payload):
        if payload is self.source_payload and self.source_reference is not None:
            return
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        prepared=self.store.prepare_source_views(self.input_reference,payload)
        with self._locked() as (con,active):
            reference=self.store.retain_source_views(con,self.input_reference,payload,prepared=prepared)
            if self.source_reference is not None and self.source_reference!=reference:
                raise ConsoleError("source_views_reference_invalid")
            active.setdefault("diagnostic",{})["source_views_ref"]=reference
            self.store.checkpoint(con,self.attempt_id,"source_views_pinned",{"source_views_ref":reference})
        self.source_reference=reference
        self.source_payload=payload

    def load_task_plan(self):
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        if self.plan_reference is not None and (set(self.plan_reference) != {"context_id", "plan_hash"}
                or not isinstance(self.plan_reference.get("plan_hash"), str)
                or len(self.plan_reference["plan_hash"]) != 64
                or self.plan_reference.get("context_id") != self.input_reference["context_id"]):
            raise ConsoleError("formation_task_plan_conflict")
        plan = self.store.load_task_plan(self.input_reference["context_id"],
            expected_hash=(self.plan_reference or {}).get("plan_hash"))
        if plan is not None and not self.plan_reference:
            return self.retain_task_plan(plan)
        return plan

    def retain_task_plan(self, plan):
        from src.semantic_replay_v1 import stable_json_hash
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        with self._locked() as (con, active):
            retained = self.store.retain_task_plan(con,self.input_reference["context_id"],plan)
            reference = {"context_id":self.input_reference["context_id"], "plan_hash":stable_json_hash(retained)}
            active.setdefault("diagnostic", {})["task_plan_ref"] = reference
            self.store.checkpoint(con,self.attempt_id,"task_plan_pinned",{"task_plan_ref":reference})
        self.plan_reference = reference
        return retained

    def plan_tasks(self, count):
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        with self._locked() as (con, active):
            con.execute("UPDATE workflow.formation_contexts SET planned_task_count=GREATEST(planned_task_count,%s) "
                        "WHERE context_id=%s",(count,self.input_reference["context_id"]))

    def commit_task(self, *, task, proposal, evidence, timing):
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        # Provider and validation have finished before opening this transaction.
        payload = {"task": task, "proposal": proposal, "evidence": evidence, "timing": timing}
        with self._locked() as (con, active):
            self.store.commit_task(con,context_id=self.input_reference["context_id"],ranges=task["target_spans"],
                payload=payload,attempt_id=self.attempt_id,claim_token=self.claim_token)
            active.setdefault("diagnostic", {})["phase"] = "proposal_received"
        self.committed_this_worker = True

    def final_validation(self, proposal):
        """Bind the one successful joint gate to the exact committed result set."""
        from src.semantic_replay_v1 import stable_json_hash
        from src.attempt_diagnostics_v1 import validator_identity
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        with self.store.documents._connect() as con:
            rows = con.execute("SELECT ranges_hash,result_hash FROM workflow.formation_task_results "
                               "WHERE context_id=%s ORDER BY ranges_hash",(self.input_reference["context_id"],)).fetchall()
        evidence = {"version":1,"result_set_hash":stable_json_hash(rows),
                    "proposal_hash":stable_json_hash(proposal),"validator_identity":validator_identity()}
        with self._locked() as (con, active):
            current = con.execute("SELECT ranges_hash,result_hash FROM workflow.formation_task_results "
                                  "WHERE context_id=%s ORDER BY ranges_hash",(self.input_reference["context_id"],)).fetchall()
            if current != rows:
                raise ConsoleError("formation_result_set_changed")
            con.execute("UPDATE workflow.formation_contexts SET final_result_hash=%s,final_validation=%s::jsonb WHERE context_id=%s",
                        (evidence["result_set_hash"],_json_text(evidence),self.input_reference["context_id"]))
            active.setdefault("diagnostic", {})["final_validation"] = evidence

    def reject_final(self, proposal, finding):
        """Invalidate only an exactly located task; retain all original proof.

        An unlocated global finding is recorded explicitly without inventing a
        repair target. Existing finite retry rules still apply.
        """
        index = finding.get("candidate_index")
        refs = proposal["objects"][index]["spans"] if type(index) is int and 0 <= index < len(proposal["objects"]) else []
        from src.semantic_replay_v1 import stable_json_hash
        results = self.task_results()
        located = [row for row in results if any(obj["spans"] == refs for obj in row["proposal"]["objects"])] if refs else []
        with self._locked() as (con, active):
            for result in located:
                ranges_hash = stable_json_hash(self.store.canonical_ranges(result["task"]["target_spans"]))
                inserted = con.execute("INSERT INTO workflow.formation_task_findings(context_id,ranges_hash,result_hash,finding) "
                    "VALUES(%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING RETURNING ranges_hash",
                    (self.input_reference["context_id"],ranges_hash,stable_json_hash(result),_json_text(finding))).fetchone()
                if inserted:
                    con.execute("UPDATE workflow.formation_contexts SET completed_task_count=completed_task_count-%s,"
                        "final_result_hash=NULL,final_validation=NULL WHERE context_id=%s",
                        (int(result["task"].get("status") == "completed"),self.input_reference["context_id"]))
            self.store.checkpoint(con,self.attempt_id,"joint_validation_rejected",{
                "finding":finding,"repair_target_spans":refs,"located_task_count":len(located)})


def task_checkpoint_writer(console, snapshot_id, attempt_id):
    """Explicit legacy/new-format dispatch; no envelope or archive read."""
    store = console.workflow_document_store
    with store._connect() as con:
        row = con.execute("SELECT d.processing_storage_version,a.payload FROM workflow.documents d "
                          "LEFT JOIN workflow.processing_attempts a ON a.snapshot_id=d.snapshot_id AND a.attempt_id=%s "
                          "WHERE d.snapshot_id=%s",(attempt_id,snapshot_id)).fetchone()
    if row and row["processing_storage_version"] == 1:
        if row["payload"] is None:
            raise ConsoleError("processing_attempt_not_active")
        return TaskCheckpointWriter(console,snapshot_id,row["payload"])
    return None


def record_task_failure(console,snapshot_id,attempt_id,error,*,claim_token):
    """Stop an owned new-format attempt without archive reload on error.

    Recording failure consumes no new processing/publication authority. A
    revoked actor's already accepted worker may record its stop; it cannot
    checkpoint results, activate work or fail another claim.
    """
    store = FormationTaskStore(console.workflow_document_store)
    enclosing_transaction = workflow_transaction_active()
    with store.documents._connect() as con:
        with con.transaction():
            document = con.execute("SELECT processing_storage_version FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE",
                                   (snapshot_id,)).fetchone()
            if not document or document["processing_storage_version"] != 1:
                return False
            if enclosing_transaction:
                raise ConsoleError("formation_checkpoint_requires_independent_transaction")
            row = con.execute("SELECT payload FROM workflow.processing_attempts WHERE snapshot_id=%s AND attempt_id=%s FOR UPDATE",
                              (snapshot_id,attempt_id)).fetchone()
            if not row:
                raise ConsoleError("processing_attempt_not_active")
            active = row["payload"]
            if active["state"] != "running" or (active.get("dispatch") or {}).get("token") != claim_token:
                return True
            dispatch = active.get("dispatch") or {}
            if dispatch.get("version") == "source-dispatch-v2":
                from datetime import datetime
                if (dispatch.get("state") == "claimed" and datetime.fromisoformat(dispatch["lease_expires_at"]) <= now()
                        and datetime.fromisoformat(active["expires_at"]) > now()
                        and (not dispatch.get("budget_expires_at") or datetime.fromisoformat(dispatch["budget_expires_at"]) > now())):
                    # The old worker no longer has authority to fail this command.
                    dispatch.update(state="pending",token=None,released_at=now().isoformat(),release_reason="lease_expired")
                    con.execute("UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s",
                                (_json_text(active),attempt_id))
                    store.checkpoint_summary(con,snapshot_id,active)
                    return True
            if dispatch.get("version") == "source-dispatch-v2":
                if datetime.fromisoformat(active["expires_at"]) <= now():
                    error = ConsoleError("processing_attempt_expired")
                elif dispatch.get("budget_expires_at") and datetime.fromisoformat(dispatch["budget_expires_at"]) <= now():
                    error = ConsoleError("source_task_budget_exhausted")
            budget = getattr(error,"code",None) == "source_task_budget_exhausted"
            from src.processing_retry_v1 import finish
            finish({"processing_attempts":[active]},attempt_id,state="incomplete_budget" if budget else "failed",error=error)
            if (active.get("dispatch") or {}).get("version") == "source-dispatch-v2":
                active["dispatch"].update(state="blocked", blocked_reason=getattr(error,"code","processing_dependency_failed"),
                    required_action="Los de blokkade op en start opnieuw met de bestaande herstelautorisatie waar vereist.")
            if budget:
                active["stop_reason"] = "budget_exhausted"
                active["formation_progress_made"] = con.execute("SELECT EXISTS(SELECT 1 FROM workflow.formation_task_results WHERE attempt_id=%s) AS made",
                                                                (attempt_id,)).fetchone()["made"]
            con.execute("UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s",
                        (_json_text(active),attempt_id))
            store.checkpoint_summary(con,snapshot_id,active)
    from src.processing_trace_v1 import observe
    observe("processing_finished",snapshot_id,active)
    return True

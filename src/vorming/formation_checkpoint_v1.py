"""Fenced task checkpoints without StoreCommand's archive/process-lock reload.

Only this checkpoint operation bypasses the shared in-process command maps. It
uses PostgreSQL-owned document, account and attempt records in a short transaction.
"""
from src.vorming.processing_document_budget_v1 import leased, document_scoped, budget as document_budget

from contextlib import contextmanager
from copy import deepcopy
import json

from src.operations_console_v1 import ConsoleError
from src.vorming.processing_retry_v1 import assert_active
from src.vorming import processing_retry_v1 as retry_clock
from src.vorming.source_selection_v1 import authorize_account, configuration
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import _json_text, WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_transaction_active


def now():
    return retry_clock.now()


class TaskCheckpointWriter:
    def __init__(self, console, snapshot_id, attempt):
        self.console, self.snapshot_id = console, snapshot_id
        self.store = FormationTaskStore(console.workflow_document_store)
        self.attempt_id = attempt["attempt_id"]
        self.expected_revision = attempt['expected_revision']
        with self.store.documents._connect() as con:
            self.source_envelope = con.execute('SELECT snapshot_id,source_id,document_id,source_sha256 AS sha256,'
                'source_version AS version,content_kind,logical_document_id,working_revision_id '
                'FROM workflow.documents WHERE snapshot_id=%s', (snapshot_id,)).fetchone()
        if self.source_envelope is None:
            raise ConsoleError('unknown_snapshot')
        self.claim_token = (attempt.get("dispatch") or {}).get("token")
        self.configuration = deepcopy(attempt.get("processing_configuration"))
        if not self.configuration:
            raise ConsoleError("processing_configuration_unpinned")
        self._formation_cursor = deepcopy((attempt.get("dispatch") or {}).get("formation_cursor"))
        self._cursor_enabled = leased(attempt)
        self._next_cursor = None
        self.document_scoped = document_scoped(attempt)
        self.document_plan_bound = bool((document_budget(attempt) or {}).get("plan_hash"))
        self.max_output_tokens = (document_budget(attempt) or {}).get("max_output_tokens")
        self.preparation = None
        self.source_payload = None
        self.source_reference = deepcopy((attempt.get("diagnostic") or {}).get("source_views_ref"))
        self.review_source_reference = deepcopy((attempt.get("diagnostic") or {}).get("review_source_ref"))
        self.plan_reference = deepcopy((attempt.get("diagnostic") or {}).get("task_plan_ref"))
        self.input_reference = deepcopy((attempt.get("diagnostic") or {}).get("validator_input_ref"))
        self.staged_extraction = None
        staged_hash = (attempt.get('diagnostic') or {}).get('staged_extraction_hash')
        if staged_hash is not None:
            with self.store.documents._connect() as con:
                staged = con.execute('SELECT payload FROM workflow.prepared_extraction_versions '
                    'WHERE record_hash=%s AND snapshot_id=%s', (staged_hash, snapshot_id)).fetchone()
            if staged is None:
                raise ConsoleError('formation_extraction_required')
            from src.vorming.source_preparation_context_v1 import KEY, stored_extraction
            stored_extraction({**self.source_envelope, KEY:staged['payload']})
            self.staged_extraction = staged['payload']
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
        call_ref = None
        if phase == 'task_rejected' and 'evidence' in values:
            call_ref = self._archive_calls([values['evidence']], 'call')
        elif phase == 'budget_exhausted' and 'formation_calls' in values:
            call_ref = self._archive_calls(values.pop('formation_calls'), 'budget')
        if "formation_timings" in values:
            values["formation_timings"] = values["formation_timings"][-1:]
        reference = None
        if "validator_input" in values and self.preparation is not None:
            from src.vorming.semantic_replay_v1 import stable_json_hash
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
            if self.staged_extraction is not None:
                from src.vorming.source_preparation_context_v1 import KEY
                envelope = {**envelope, KEY:self.staged_extraction}
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
                if phase == "model_request" and self.document_scoped:
                    from src.vorming.processing_document_budget_v1 import reserve_call
                    values["document_budget"] = reserve_call(active)
                self.store.checkpoint(con,self.attempt_id,phase,values)
                if call_ref is not None:
                    self.store.checkpoint(con,self.attempt_id,'formation_call',{'call_ref':call_ref})
                if phase == "task_rejected":
                    self._commit_cursor(active)
                active.setdefault("diagnostic", {})["phase"] = phase
                if phase=="extraction_reused":
                    active["diagnostic"]["extraction_checkpoint"]=values["extraction_checkpoint"]
        if phase == "task_rejected" and self._cursor_enabled:
            self._formation_cursor = deepcopy(self._next_cursor)
        from src.vorming.processing_trace_v1 import observe
        observe("processing_checkpoint",self.snapshot_id,active,phase=phase)

    def skip_task(self, phase, position):
        if not self._cursor_enabled:
            return False
        cursor = self._formation_cursor or {"phase":"initial", "position":-1}
        order = {"initial":0, "recovery":1}
        if (order[phase] < order[cursor["phase"]]
                or (phase == cursor["phase"] and position <= cursor["position"])):
            return True
        self._next_cursor = {"phase":phase,"position":position}
        return False

    def _commit_cursor(self, active):
        if self._cursor_enabled and self._next_cursor is not None:
            active["dispatch"]["formation_cursor"] = deepcopy(self._next_cursor)

    def task_failures(self):
        if not self._cursor_enabled:
            return []
        with self.store.documents._connect() as con:
            rows = con.execute("SELECT payload FROM workflow.processing_checkpoints WHERE attempt_id=%s "
                "AND phase='task_rejected' ORDER BY checkpoint_id", (self.attempt_id,)).fetchall()
        return [row["payload"] for row in rows]

    def before_task(self):
        from src.vorming.worker_handover_v1 import before_task
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
        from src.vorming.source_preparation_context_v1 import KEY,stored_extraction
        return stored_extraction({**extraction["source"],KEY:extraction}),extraction["source"],{k:extraction[k] for k in ("record_hash","fragments_hash")}

    def retain_source_views(self,payload):
        if payload is self.source_payload and self.source_reference is not None and self.review_source_reference is not None:
            return
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        prepared=self.store.prepare_source_views(self.input_reference,payload)
        with self.store.documents._connect() as con:
            records_available = con.execute("SELECT to_regclass('workflow.source_read_roots') AS available").fetchone()['available']
        read_reference = None
        from src.workflows.formation_evidence_v1 import available
        if records_available:
            read_prepared = self.store.prepare_review_source(self.input_reference, payload)
            read_reference = self.store.publish_review_source(read_prepared)
        with self.store.documents._connect() as con:
            evidence_available = available(con)
        with self._locked() as (con,active):
            reference=self.store.retain_source_views(con,self.input_reference,payload,prepared=prepared)
            if self.source_reference is not None and self.source_reference!=reference:
                raise ConsoleError("source_views_reference_invalid")
            active.setdefault("diagnostic",{})["source_views_ref"]=reference
            if read_reference is not None:
                pinned = con.execute("UPDATE workflow.documents SET review_source_ref=%s::jsonb,review_read_envelope=NULL WHERE snapshot_id=%s "
                    "AND envelope_payload#>>'{prepared_source_extraction,record_hash}'=%s "
                    + ("AND formation_evidence_id IS NULL" if evidence_available else ""),
                    (_json_text(read_reference),self.snapshot_id,read_reference['extraction_hash']))
                if pinned.rowcount != 1:
                    active_proof = con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s',
                        (self.snapshot_id,)).fetchone()
                    if not active_proof or active_proof['formation_evidence_id'] is None:
                        raise ConsoleError('processing_command_conflict')
                active['diagnostic']['review_source_ref'] = read_reference
            self.store.checkpoint(con,self.attempt_id,"source_views_pinned",{"source_views_ref":reference})
        self.source_reference=reference
        self.review_source_reference=read_reference
        self.source_payload=payload

    def stage_extraction(self, record):
        """Keep active Review input intact while preparing a successor result."""
        from src.vorming.source_preparation_context_v1 import KEY, stored_extraction
        from src.workflows.formation_evidence_v1 import available
        with self.store.documents._connect() as con:
            if not available(con):
                return False
            current = con.execute('SELECT formation_evidence_id FROM workflow.documents WHERE snapshot_id=%s',
                                  (self.snapshot_id,)).fetchone()
        if not current or current['formation_evidence_id'] is None:
            return False
        stored_extraction({**self.source_envelope, KEY:record})
        if workflow_transaction_active():
            raise ConsoleError('formation_checkpoint_requires_independent_transaction')
        # Retain the large immutable input before taking the document claim lock.
        with self.store.documents._connect() as con:
            self.store._immutable(con, 'prepared_extraction_versions', 'record_hash', record['record_hash'],
                                  ['snapshot_id'], [self.snapshot_id], record)
        with self._locked() as (con, active):
            active.setdefault('diagnostic', {})['staged_extraction_hash'] = record['record_hash']
            self.store.checkpoint(con, self.attempt_id, 'extraction_staged', {'record_hash':record['record_hash']})
        self.staged_extraction = record
        return True

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
        if plan is not None and self.document_scoped and not self.document_plan_bound:
            from src.vorming.processing_document_budget_v1 import pin_plan
            with self._locked() as (con, active):
                pin_plan(active, self.plan_reference, len(plan["tasks"]))
            self.document_plan_bound = True
        return plan

    def retain_task_plan(self, plan):
        from src.vorming.semantic_replay_v1 import stable_json_hash
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        with self._locked() as (con, active):
            retained = self.store.retain_task_plan(con,self.input_reference["context_id"],plan)
            reference = {"context_id":self.input_reference["context_id"], "plan_hash":stable_json_hash(retained)}
            from src.vorming.processing_document_budget_v1 import pin_plan
            pin_plan(active, reference, len(retained["tasks"]))
            active.setdefault("diagnostic", {})["task_plan_ref"] = reference
            self.store.checkpoint(con,self.attempt_id,"task_plan_pinned",{"task_plan_ref":reference})
        self.plan_reference = reference
        self.document_plan_bound = self.document_scoped
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
        call_ref = self._archive_calls([evidence], 'call')
        with self._locked() as (con, active):
            committed = self.store.commit_task(con,context_id=self.input_reference["context_id"],ranges=task["target_spans"],
                payload=payload,attempt_id=self.attempt_id,claim_token=self.claim_token)
            self._commit_cursor(active)
            if call_ref is not None:
                self.store.checkpoint(con,self.attempt_id,'formation_call',{'call_ref':call_ref})
            if committed:
                active["formation_progress_made"] = True
            active.setdefault("diagnostic", {})["phase"] = "proposal_received"
        if self._cursor_enabled:
            self._formation_cursor = deepcopy(self._next_cursor)
        self.committed_this_worker = True

    def _archive_calls(self, calls, label):
        from src.workflows.formation_evidence_v1 import available
        from src.vorming.semantic_replay_v1 import stable_json_hash
        with self.store.documents._connect() as con:
            if not available(con):
                return None
        prepared = self.store.prepare_processing_archive(self.source_envelope, kind='semantic_replay',
            record_key=label + ':' + self.attempt_id + ':' + stable_json_hash(calls),
            observed_revision=self.expected_revision, payload={'calls':calls})
        return self.store.retain_processing_archive(prepared)

    def begin_formation_calls(self, evidence, *, resuming):
        from src.workflows.formation_evidence_v1 import call_sequence, available
        from src.workflows.processing_archives_v1 import encoded
        with self.store.documents._connect() as con:
            if not available(con):
                return
        prior = self.console._envelope(self.snapshot_id).get('semantic_replay') or {}
        expected = call_sequence(prior.get('provider_evidence') or {}) if resuming else []
        expected += [row['evidence'] for row in self.task_results()]
        expected += [row['evidence'] for row in self.task_failures()]
        actual = call_sequence(evidence)
        if encoded(expected) != encoded(actual):
            raise ConsoleError('formation_evidence_call_basis_changed')
        reference = self._archive_calls(actual, 'basis')
        if reference is not None:
            with self._locked() as (con, active):
                self.store.checkpoint(con,self.attempt_id,'formation_call_basis',{'call_ref':reference})

    def final_validation(self, proposal):
        """Bind the one successful joint gate to the exact committed result set."""
        from src.vorming.semantic_replay_v1 import stable_json_hash
        from src.vorming.attempt_diagnostics_v1 import validator_identity
        if not self.input_reference:
            raise ConsoleError("formation_input_required")
        from src.workflows.formation_evidence_v1 import available
        with self.store.documents._connect() as con:
            version = 3 if available(con) else 2
            rows = con.execute("SELECT ranges_hash,result_hash FROM workflow.formation_task_results "
                               "WHERE context_id=%s ORDER BY ranges_hash",(self.input_reference["context_id"],)).fetchall()
        evidence = {"version":version,"result_set_hash":stable_json_hash(rows),
                    "proposal_hash":stable_json_hash(proposal),"validator_identity":validator_identity()}
        with self._locked() as (con, active):
            current = con.execute("SELECT ranges_hash,result_hash FROM workflow.formation_task_results "
                                  "WHERE context_id=%s ORDER BY ranges_hash",(self.input_reference["context_id"],)).fetchall()
            if current != rows:
                raise ConsoleError("formation_result_set_changed")
            # The preparation context stays pinned across partial activation;
            # a later resume fences its own current object revision separately.
            evidence["activation_revision"] = active["expected_revision"]
            con.execute("UPDATE workflow.formation_contexts SET final_result_hash=%s,final_validation=%s::jsonb WHERE context_id=%s",
                        (evidence["result_set_hash"],_json_text(evidence),self.input_reference["context_id"]))
            active.setdefault("diagnostic", {})["final_validation"] = evidence

    def seal_formation(self, replay):
        """Producer hook after complete accounting, before object activation."""
        from src.workflows.formation_evidence_v1 import available, capture
        from src.vorming.semantic_replay_v1 import stable_json_hash
        with self.store.documents._connect() as con:
            if not available(con):
                return
        if not self.input_reference:
            raise ConsoleError('formation_input_required')
        envelope = self.console._envelope(self.snapshot_id)
        archive = self.store.prepare_processing_archive(envelope, kind='semantic_replay',
            record_key='final:' + self.attempt_id + ':' + stable_json_hash(replay),
            observed_revision=self.console.objects_revision(self.snapshot_id), payload=replay)
        reference = self.store.retain_processing_archive(archive)
        with self._locked() as (con, active):
            gate = (active.get('diagnostic') or {}).get('final_validation') or {}
            if gate.get('version') != 3 or gate.get('proposal_hash') != replay.get('proposal_hash'):
                raise ConsoleError('formation_final_validation_required')
            active['diagnostic']['formation_finalized_ref'] = reference
        prepared = self.store.prepare_formation_evidence(envelope,
            context_id=self.input_reference['context_id'], attempt_id=self.attempt_id)
        sealed = self.store.publish_formation_evidence(envelope, prepared)
        expected = json.loads(prepared.header_text)['capture']
        with self._locked() as (con, active):
            current, _, _, _, _, _ = capture(con, self.input_reference['context_id'], self.attempt_id)
            if current != expected:
                raise ConsoleError('formation_evidence_activation_changed')
            gate = {**active['diagnostic']['final_validation'], 'stage': 'sealed', 'formation_evidence_ref': sealed}
            active['diagnostic'].update(final_validation=gate, formation_evidence_ref=sealed)
            con.execute('UPDATE workflow.formation_contexts SET final_validation=%s::jsonb WHERE context_id=%s',
                        (_json_text(gate), self.input_reference['context_id']))

    def reject_final(self, proposal, finding):
        """Invalidate only an exactly located task; retain all original proof.

        An unlocated global finding is recorded explicitly without inventing a
        repair target. Existing finite retry rules still apply.
        """
        index = finding.get("candidate_index")
        refs = proposal["objects"][index]["spans"] if type(index) is int and 0 <= index < len(proposal["objects"]) else []
        from src.vorming.semantic_replay_v1 import stable_json_hash
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


def finish_task_failure(con, active, error):
    """One stop classification and retry-accounting rule for native attempts."""
    from src.vorming.processing_retry_v1 import finish
    budget = getattr(error, "code", None) in {"source_task_budget_exhausted", "processing_document_call_budget_exhausted"}
    finish({"processing_attempts":[active]}, active["attempt_id"],
           state="incomplete_budget" if budget else "failed", error=error)
    if budget:
        active["stop_reason"] = "budget_exhausted"
        active["formation_progress_made"] = con.execute(
            "SELECT EXISTS(SELECT 1 FROM workflow.formation_task_results WHERE attempt_id=%s) AS made",
            (active["attempt_id"],)).fetchone()["made"]


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
            from datetime import datetime
            from src.vorming.processing_document_budget_v1 import worker_expired
            if (document_scoped(active) and worker_expired(active, now())
                    and datetime.fromisoformat(active["expires_at"]) > now()
                    and getattr(error,"code",None) in {"processing_worker_deadline_reached","processing_attempt_expired"}):
                dispatch.update(state="pending",token=None,released_at=now().isoformat(),release_reason="worker_deadline")
                con.execute("UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s",
                    (_json_text(active),attempt_id))
                store.checkpoint_summary(con,snapshot_id,active)
                return "handover"
            if leased(active):
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
            if leased(active):
                if datetime.fromisoformat(active["expires_at"]) <= now():
                    error = ConsoleError("source_task_budget_exhausted" if document_scoped(active) else "processing_attempt_expired")
                elif dispatch.get("budget_expires_at") and datetime.fromisoformat(dispatch["budget_expires_at"]) <= now():
                    error = ConsoleError("source_task_budget_exhausted")
            finish_task_failure(con, active, error)
            if leased(active):
                active["dispatch"].update(state="blocked", blocked_reason=getattr(error,"code","processing_dependency_failed"),
                    required_action="Los de blokkade op en start opnieuw met de bestaande herstelautorisatie waar vereist.")
            con.execute("UPDATE workflow.processing_attempts SET payload=%s::jsonb,record_version=record_version+1 WHERE attempt_id=%s",
                        (_json_text(active),attempt_id))
            store.checkpoint_summary(con,snapshot_id,active)
    from src.vorming.processing_trace_v1 import observe
    observe("processing_finished",snapshot_id,active)
    return True

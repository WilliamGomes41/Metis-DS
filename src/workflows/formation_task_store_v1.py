"""Task-sized persistence within the existing PostgreSQL workflow authority.

Callers own domain validation. This boundary enforces atomic commits, exact
context identity, idempotency and provenance; it never creates candidates.
"""
from copy import deepcopy

from src.semantic_replay_v1 import stable_json_hash
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError, _json_text

STORAGE_VERSION = 1


def integrity(value, expected, code="formation_record_integrity_failed"):
    if stable_json_hash(value) != expected:
        raise WorkflowDocumentStoreError(code)
    return value


class FormationTaskStore:
    def __init__(self, document_store):
        self.documents = document_store

    def _immutable(self, con, table, identity_column, identity, columns, values, payload):
        # All SQL identifiers are module-owned literals, never caller input.
        names = [identity_column, *columns, "payload"]
        con.execute(
            f"INSERT INTO workflow.{table}({','.join(names)}) VALUES("
            + ",".join(["%s"] * (len(names) - 1)) + ",%s::jsonb) ON CONFLICT DO NOTHING",
            (identity, *values, _json_text(payload)),
        )
        row = con.execute(f"SELECT payload FROM workflow.{table} WHERE {identity_column}=%s", (identity,)).fetchone()
        if not row or row["payload"] != payload:
            raise WorkflowDocumentStoreError("formation_immutable_record_conflict")

    def retain_input(self, con, *, envelope, validator_input, semantic_identity, expected_revision):
        from src.source_preparation_context_v1 import KEY, stored_extraction
        from src.pre_review_semantic_v1 import _content_fragments, _evidence_fragments
        extraction = envelope.get(KEY)
        fragments = stored_extraction(envelope)
        if fragments is None:
            raise WorkflowDocumentStoreError("formation_extraction_required")
        components = semantic_identity.get("components") if isinstance(semantic_identity,dict) else None
        if (not isinstance(components,dict) or semantic_identity.get("hash") != stable_json_hash(components)
                or any(components.get(k) != envelope[v] for k,v in (
                    ("snapshot_id","snapshot_id"),("source_sha256","sha256"),("document_id","document_id")))):
            raise WorkflowDocumentStoreError("formation_semantic_identity_mismatch")
        parameters = {k: deepcopy(v) for k, v in validator_input.items()
                      if k not in {"fragments", "evidence_fragments"}}
        reconstructed = {**parameters, "fragments": _content_fragments(fragments),
                         "evidence_fragments": _evidence_fragments(fragments)}
        if reconstructed != validator_input:
            raise WorkflowDocumentStoreError("formation_input_reconstruction_mismatch")
        self._immutable(con, "prepared_extraction_versions", "record_hash", extraction["record_hash"],
                        ["snapshot_id"], [envelope["snapshot_id"]], extraction)
        payload = {"version": 1, "snapshot_id": envelope["snapshot_id"],
                   "source_hash": envelope["sha256"], "source_version": envelope["version"],
                   "expected_revision": expected_revision, "extraction_hash": extraction["record_hash"],
                   "parameters": parameters, "validator_input_hash": stable_json_hash(validator_input)}
        artifact_id = stable_json_hash(payload)
        self._immutable(con, "formation_inputs", "artifact_id", artifact_id,
                        ["snapshot_id", "extraction_hash"], [envelope["snapshot_id"], extraction["record_hash"]], payload)
        semantic_hash = stable_json_hash(semantic_identity)
        context_id = stable_json_hash({"artifact_id": artifact_id, "semantic_hash": semantic_hash,
                                       "expected_revision": expected_revision})
        con.execute("INSERT INTO workflow.formation_contexts(context_id,snapshot_id,artifact_id,semantic_identity,semantic_hash,expected_revision) "
                    "VALUES(%s,%s,%s,%s::jsonb,%s,%s) ON CONFLICT DO NOTHING",
                    (context_id,envelope["snapshot_id"],artifact_id,_json_text(semantic_identity),semantic_hash,expected_revision))
        return {"version": 1, "artifact_id": artifact_id, "context_id": context_id,
                "snapshot_id":envelope["snapshot_id"],"source_hash":envelope["sha256"],
                "source_version":envelope["version"],
                "validator_input_hash": payload["validator_input_hash"]}

    def resolve_input(self, reference, *, expected_snapshot_id=None):
        return self.resolve_preparation(reference,expected_snapshot_id=expected_snapshot_id)["validator_input"]

    def resolve_preparation(self, reference, *, expected_snapshot_id=None):
        if reference.get("version") != STORAGE_VERSION:
            raise WorkflowDocumentStoreError("formation_input_version_unsupported")
        if expected_snapshot_id is not None and reference.get("snapshot_id") != expected_snapshot_id:
            raise WorkflowDocumentStoreError("formation_input_source_mismatch")
        with self.documents._connect() as con:
            row = con.execute("SELECT i.payload,e.payload AS extraction FROM workflow.formation_inputs i "
                              "JOIN workflow.prepared_extraction_versions e ON e.record_hash=i.extraction_hash "
                              "WHERE i.artifact_id=%s", (reference["artifact_id"],)).fetchone()
        if not row:
            raise WorkflowDocumentStoreError("formation_input_missing")
        payload = integrity(row["payload"], reference["artifact_id"])
        if payload.get("version") != STORAGE_VERSION:
            raise WorkflowDocumentStoreError("formation_input_version_unsupported")
        if any(reference.get(k) != payload.get(k) for k in ("snapshot_id","source_hash","source_version")):
            raise WorkflowDocumentStoreError("formation_input_source_mismatch")
        extraction = row["extraction"]
        from src.source_preparation_context_v1 import KEY, stored_extraction
        from src.pre_review_semantic_v1 import _content_fragments, _evidence_fragments
        source = extraction.get("source") or {}
        if (extraction.get("record_hash") != payload["extraction_hash"]
                or source.get("snapshot_id") != payload["snapshot_id"]
                or source.get("sha256") != payload["source_hash"]
                or source.get("version") != payload["source_version"]):
            raise WorkflowDocumentStoreError("formation_input_source_mismatch")
        fragments = stored_extraction({**source, KEY: extraction})
        result = {**payload["parameters"], "fragments": _content_fragments(fragments),
                  "evidence_fragments": _evidence_fragments(fragments)}
        integrity(result, payload["validator_input_hash"], "formation_input_integrity_failed")
        integrity(result, reference["validator_input_hash"], "formation_input_integrity_failed")
        return {"validator_input":result,"extraction":extraction,"input":payload}

    @staticmethod
    def canonical_ranges(ranges):
        if (not isinstance(ranges, list) or not ranges or any(
                not isinstance(r, dict) or set(r) != {"block_id","start","end"}
                or not isinstance(r["block_id"], str) or not r["block_id"]
                or type(r["start"]) is not int or type(r["end"]) is not int
                or not 0 <= r["start"] < r["end"] for r in ranges)):
            raise WorkflowDocumentStoreError("formation_task_ranges_invalid")
        result = sorted(ranges, key=lambda r: (r["block_id"],r["start"],r["end"]))
        if any(a["block_id"] == b["block_id"] and a["end"] > b["start"]
               for a,b in zip(result,result[1:])):
            raise WorkflowDocumentStoreError("formation_task_ranges_invalid")
        return result

    def load_source_views(self, preparation, reference=None):
        from src.prepared_source_views_v1 import contract,VERSION,PreparedSource
        extraction=preparation["extraction"]
        extraction_hash=extraction["record_hash"]
        views_id=stable_json_hash({"extraction_hash":extraction_hash,"contract":contract()})
        if reference is not None:
            if (set(reference)!={"version","views_id","extraction_hash","payload_hash"}
                    or reference.get("version")!=VERSION or reference.get("extraction_hash")!=extraction_hash):
                raise WorkflowDocumentStoreError("source_views_reference_invalid")
            if reference["views_id"]!=views_id:
                raise WorkflowDocumentStoreError("source_views_contract_mismatch")
        with self.documents._connect() as con:
            row=con.execute("SELECT extraction_hash,payload_hash,payload FROM workflow.formation_source_views WHERE views_id=%s",
                            (views_id,)).fetchone()
        if not row:
            if reference is not None:
                raise WorkflowDocumentStoreError("source_views_missing")
            return None
        if row["extraction_hash"]!=extraction_hash or row["payload"].get("extraction_hash")!=extraction_hash:
            raise WorkflowDocumentStoreError("source_views_source_mismatch")
        integrity(row["payload"],row["payload_hash"],"source_views_integrity_failed")
        if reference is not None and row["payload_hash"]!=reference["payload_hash"]:
            raise WorkflowDocumentStoreError("source_views_integrity_failed")
        if row["payload"].get("extractor_contract")!=extraction["extractor_contract"]:
            raise WorkflowDocumentStoreError("source_views_extractor_mismatch")
        return PreparedSource(extraction["fragments"],row["payload"],docling_record=extraction.get("docling_record"))

    def _source_views_header(self,con,input_reference):
        return con.execute("SELECT i.payload->>'extraction_hash' AS extraction_hash,"
            "e.payload->>'fragments_hash' AS fragments_hash,e.payload->>'extractor_contract' AS extractor_contract "
            "FROM workflow.formation_inputs i JOIN workflow.prepared_extraction_versions e ON e.record_hash=i.extraction_hash "
            "WHERE i.artifact_id=%s AND i.snapshot_id=%s",
            (input_reference["artifact_id"],input_reference["snapshot_id"])).fetchone()

    def prepare_source_views(self,input_reference,payload,*,con=None):
        if con is None:
            with self.documents._connect() as connection:
                return self.prepare_source_views(input_reference,payload,con=connection)
        from src.prepared_source_views_v1 import contract
        header=self._source_views_header(con,input_reference)
        if not header or payload.get("fragments_hash")!=header["fragments_hash"] or payload.get("contract")!=contract():
            raise WorkflowDocumentStoreError("source_views_source_mismatch")
        record={**payload,"extraction_hash":header["extraction_hash"],"extractor_contract":header["extractor_contract"]}
        # Hashing and JSON serialization happen before the protected write.
        return {"header":header,"views_id":stable_json_hash({"extraction_hash":header["extraction_hash"],"contract":contract()}),
                "payload_hash":stable_json_hash(record),"encoded":_json_text(record)}

    def retain_source_views(self,con,input_reference,payload,*,prepared=None):
        from src.prepared_source_views_v1 import VERSION
        prepared=prepared if prepared is not None else self.prepare_source_views(input_reference,payload,con=con)
        header=self._source_views_header(con,input_reference)
        if header!=prepared["header"]:
            raise WorkflowDocumentStoreError("source_views_source_mismatch")
        con.execute("INSERT INTO workflow.formation_source_views(views_id,extraction_hash,payload_hash,payload) "
            "VALUES(%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
            (prepared["views_id"],header["extraction_hash"],prepared["payload_hash"],prepared["encoded"]))
        row=con.execute("SELECT extraction_hash,payload_hash,payload=%s::jsonb AS same FROM workflow.formation_source_views WHERE views_id=%s",
            (prepared["encoded"],prepared["views_id"])).fetchone()
        if (not row or not row["same"] or row["extraction_hash"]!=header["extraction_hash"]
                or row["payload_hash"]!=prepared["payload_hash"]):
            raise WorkflowDocumentStoreError("formation_immutable_record_conflict")
        return {"version":VERSION,"views_id":prepared["views_id"],"extraction_hash":header["extraction_hash"],"payload_hash":prepared["payload_hash"]}

    def load_task_plan(self, context_id, *, expected_hash=None, con=None):
        if con is None:
            with self.documents._connect() as connection:
                return self.load_task_plan(context_id,expected_hash=expected_hash,con=connection)
        row = con.execute("SELECT plan_hash,payload FROM workflow.formation_task_plans WHERE context_id=%s",
                          (context_id,)).fetchone()
        if not row:
            if expected_hash:
                raise WorkflowDocumentStoreError("formation_task_plan_missing")
            return None
        if expected_hash and row["plan_hash"] != expected_hash:
            raise WorkflowDocumentStoreError("formation_task_plan_conflict")
        plan = integrity(row["payload"],row["plan_hash"],"formation_task_plan_integrity_failed")
        from src.recommendation_task_plan_v1 import VERSION
        if plan.get("version") != VERSION:
            raise WorkflowDocumentStoreError("formation_task_plan_version_unsupported")
        return plan

    def retain_task_plan(self, con, context_id, plan):
        con.execute("INSERT INTO workflow.formation_task_plans(context_id,plan_hash,payload) "
                    "VALUES(%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                    (context_id,stable_json_hash(plan),_json_text(plan)))
        # Concurrent creators use the first committed immutable plan. Grouping
        # policy is not part of a semantic result's identity.
        return self.load_task_plan(context_id,con=con)

    def commit_task(self, con, *, context_id, ranges, payload, attempt_id, claim_token):
        ranges = self.canonical_ranges(ranges)
        ranges_hash, result_hash = stable_json_hash(ranges), stable_json_hash(payload)
        # The document/attempt/claim lock and domain checks are owned by the
        # caller's short transaction. The result and its count commit together.
        inserted = con.execute(
            "INSERT INTO workflow.formation_task_results(context_id,ranges_hash,source_ranges,result_hash,payload,attempt_id,claim_token) "
            "VALUES(%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s) ON CONFLICT DO NOTHING RETURNING ranges_hash",
            (context_id,ranges_hash,_json_text(ranges),result_hash,_json_text(payload),attempt_id,claim_token)).fetchone()
        if not inserted:
            row = con.execute("SELECT source_ranges,result_hash,payload FROM workflow.formation_task_results "
                              "WHERE context_id=%s AND ranges_hash=%s",(context_id,ranges_hash)).fetchone()
            if not row or row["source_ranges"] != ranges:
                raise WorkflowDocumentStoreError("formation_task_result_conflict")
            if row["result_hash"] == result_hash and row["payload"] == payload:
                return False
            rejected = con.execute("SELECT 1 FROM workflow.formation_task_findings WHERE context_id=%s "
                                   "AND ranges_hash=%s AND result_hash=%s",(context_id,ranges_hash,row["result_hash"])).fetchone()
            if not rejected:
                raise WorkflowDocumentStoreError("formation_task_result_conflict")
            # The current row is the unique active-result projection. Preserve
            # its complete immutable version before a targeted correction.
            con.execute("INSERT INTO workflow.formation_task_result_history "
                "SELECT context_id,ranges_hash,result_hash,source_ranges,payload,attempt_id,claim_token,committed_at "
                "FROM workflow.formation_task_results WHERE context_id=%s AND ranges_hash=%s ON CONFLICT DO NOTHING",
                (context_id,ranges_hash))
            con.execute("UPDATE workflow.formation_task_results SET result_hash=%s,payload=%s::jsonb,attempt_id=%s,"
                        "claim_token=%s,committed_at=CURRENT_TIMESTAMP WHERE context_id=%s AND ranges_hash=%s",
                        (result_hash,_json_text(payload),attempt_id,claim_token,context_id,ranges_hash))
        con.execute("UPDATE workflow.formation_contexts SET completed_task_count=completed_task_count+%s, "
                    "final_result_hash=NULL,final_validation=NULL WHERE context_id=%s",
                    (int(payload.get("task",{}).get("status") == "completed"),context_id))
        return True

    @staticmethod
    def assert_activation(con, envelope):
        if envelope.get("processing_storage") != "task-v1":
            return
        latest = next(reversed(envelope.get("processing_attempts") or []),{})
        reference = (latest.get("diagnostic") or {}).get("validator_input_ref")
        # Decision-tree formation has its own existing activation contract.
        if not reference:
            return
        row = con.execute("SELECT final_validation,semantic_identity,expected_revision FROM workflow.formation_contexts "
                          "WHERE context_id=%s AND snapshot_id=%s",(reference["context_id"],envelope["snapshot_id"])).fetchone()
        proof = row["final_validation"] if row else None
        replay = envelope.get("semantic_replay") or {}
        if (not proof or proof.get("version") not in {1, 2}
                or proof.get("version") == 2 and not isinstance(proof.get("activation_revision"), str)
                or proof != (latest.get("diagnostic") or {}).get("final_validation")
                or proof.get("proposal_hash") != stable_json_hash(replay.get("proposal"))
                or row["semantic_identity"] != replay.get("identity")
                or proof.get("activation_revision", row["expected_revision"]) != latest.get("expected_revision")):
            raise WorkflowDocumentStoreError("formation_final_validation_required")
        hashes = con.execute("SELECT ranges_hash,result_hash FROM workflow.formation_task_results "
                             "WHERE context_id=%s ORDER BY ranges_hash",(reference["context_id"],)).fetchall()
        integrity(hashes,proof["result_set_hash"],"formation_result_set_changed")

    def task_results(self, context_id, *, attempt_id=None, diagnostic=False):
        with self.documents._connect() as con:
            context = con.execute("SELECT artifact_id,semantic_hash,semantic_identity,expected_revision FROM workflow.formation_contexts "
                                  "WHERE context_id=%s",(context_id,)).fetchone()
            if not context:
                raise WorkflowDocumentStoreError("formation_context_missing")
            integrity(context["semantic_identity"],context["semantic_hash"])
            integrity({k:context[k] for k in ("artifact_id","semantic_hash","expected_revision")},context_id)
            rows = con.execute("SELECT r.ranges_hash,r.source_ranges,r.result_hash,r.payload FROM workflow.formation_task_results r "
                               "WHERE r.context_id=%s" + (" AND r.attempt_id=%s" if attempt_id else "")
                               + ("" if diagnostic else " AND NOT EXISTS(SELECT 1 FROM workflow.formation_task_findings f "
                                  "WHERE f.context_id=r.context_id AND f.ranges_hash=r.ranges_hash AND f.result_hash=r.result_hash)")
                               + " ORDER BY r.committed_at,r.ranges_hash",
                               ((context_id,attempt_id) if attempt_id else (context_id,))).fetchall()
            if diagnostic and attempt_id:
                rows.extend(con.execute("SELECT ranges_hash,source_ranges,result_hash,payload FROM workflow.formation_task_result_history "
                    "WHERE context_id=%s AND attempt_id=%s ORDER BY committed_at,ranges_hash",(context_id,attempt_id)).fetchall())
        for row in rows:
            integrity(row["payload"], row["result_hash"])
            integrity(self.canonical_ranges(row["source_ranges"]),row["ranges_hash"])
            if (row["payload"].get("task",{}).get("target_spans") is not None
                    and self.canonical_ranges(row["payload"]["task"]["target_spans"]) != row["source_ranges"]):
                raise WorkflowDocumentStoreError("formation_task_ranges_mismatch")
        return [row["payload"] for row in rows]

    @staticmethod
    def checkpoint(con, attempt_id, phase, values):
        con.execute("INSERT INTO workflow.processing_checkpoints(attempt_id,phase,payload) VALUES(%s,%s,%s::jsonb)",
                    (attempt_id,phase,_json_text(values)))

    @staticmethod
    def attempts(con, snapshot_id, *, include_versions=False):
        return [{**row["payload"], **({"_record_version":row["record_version"]} if include_versions else {})} for row in con.execute(
            "SELECT payload,record_version FROM workflow.processing_attempts WHERE snapshot_id=%s ORDER BY started_at,attempt_id",
            (snapshot_id,)).fetchall()]

    @staticmethod
    def save_attempts(con, snapshot_id, attempts):
        for attempt in attempts:
            attempt = dict(attempt)
            expected_version = attempt.pop("_record_version",None)
            existing = con.execute("SELECT snapshot_id,command_id,payload,record_version FROM workflow.processing_attempts WHERE attempt_id=%s FOR UPDATE",
                                   (attempt["attempt_id"],)).fetchone()
            if existing and (existing["snapshot_id"] != snapshot_id or existing["command_id"] != attempt["command_id"]):
                raise WorkflowDocumentStoreError("processing_command_conflict")
            if existing:
                if existing["payload"] == attempt:
                    continue
                if expected_version != existing["record_version"]:
                    # An unchanged historical/active view is not an instruction
                    # to overwrite newer checkpoint diagnostics.
                    if {k:v for k,v in attempt.items() if k != "diagnostic"} == {
                            k:v for k,v in existing["payload"].items() if k != "diagnostic"}:
                        continue
                    raise WorkflowDocumentStoreError("processing_attempt_write_conflict")
            con.execute("INSERT INTO workflow.processing_attempts(attempt_id,snapshot_id,command_id,started_at,object_generation,payload) "
                        "SELECT %s,snapshot_id,%s,%s,object_generation,%s::jsonb FROM workflow.documents WHERE snapshot_id=%s "
                        "ON CONFLICT(attempt_id) DO UPDATE SET payload=EXCLUDED.payload,record_version=workflow.processing_attempts.record_version+1",
                        (attempt["attempt_id"],attempt["command_id"],attempt["started_at"],_json_text(attempt),snapshot_id))
        if attempts:
            latest = con.execute("SELECT payload FROM workflow.processing_attempts WHERE attempt_id=%s",
                                 (attempts[-1]["attempt_id"],)).fetchone()["payload"]
            summary = {"processing_attempts": [{k: deepcopy(v) for k,v in latest.items() if k != "diagnostic"}],
                       "ingest_observations": [{k: a.get(k) for k in ("started_at","finished_at")}
                           for a in attempts if a.get("state") == "succeeded" and a.get("kind") == "ingest"]}
            summary["processing_attempts"][0]["diagnostic"] = {"phase": (latest.get("diagnostic") or {}).get("phase")}
            reference = (latest.get("diagnostic") or {}).get("validator_input_ref")
            if reference:
                progress = con.execute("SELECT planned_task_count,completed_task_count FROM workflow.formation_contexts WHERE context_id=%s",
                                       (reference["context_id"],)).fetchone()
                if progress:
                    summary["formation_progress"] = FormationTaskStore._progress(progress)
            con.execute("INSERT INTO workflow.processing_document_summaries(snapshot_id,payload) VALUES(%s,%s::jsonb) "
                        "ON CONFLICT(snapshot_id) DO UPDATE SET payload=EXCLUDED.payload",
                        (snapshot_id,_json_text(summary)))

    @staticmethod
    def checkpoint_summary(con, snapshot_id, active):
        phase = (active.get("diagnostic") or {}).get("phase")
        compact = {k:v for k,v in active.items() if k not in {"diagnostic","_record_version"}}
        compact["diagnostic"] = {"phase":phase}
        con.execute("UPDATE workflow.processing_document_summaries SET payload=jsonb_set(payload,"
                    "'{processing_attempts,0}',%s::jsonb) WHERE snapshot_id=%s",
                    (_json_text(compact),snapshot_id))
        reference = (active.get("diagnostic") or {}).get("validator_input_ref")
        if reference:
            row = con.execute("SELECT planned_task_count,completed_task_count FROM workflow.formation_contexts WHERE context_id=%s",
                              (reference["context_id"],)).fetchone()
            if row:
                progress = FormationTaskStore._progress(row)
                con.execute("UPDATE workflow.processing_document_summaries SET payload=jsonb_set(payload,"
                            "'{formation_progress}',%s::jsonb) WHERE snapshot_id=%s",(_json_text(progress),snapshot_id))

    @staticmethod
    def _progress(row):
        planned = row["planned_task_count"]
        completed = min(planned,row["completed_task_count"])
        return {"planned_task_count":planned,"terminal_task_count":completed,"pending_task_count":planned-completed}

    def progress(self, context_id):
        with self.documents._connect() as con:
            row = con.execute("SELECT planned_task_count,completed_task_count FROM workflow.formation_contexts WHERE context_id=%s",
                              (context_id,)).fetchone()
        if not row:
            raise WorkflowDocumentStoreError("formation_context_missing")
        return self._progress(row)

    def diagnostic(self, attempt):
        """Explicit evidence read; task history is assembled only on demand."""
        diagnostic = deepcopy(attempt.get("diagnostic") or {})
        with self.documents._connect() as con:
            rows = con.execute("SELECT phase,payload,recorded_at FROM workflow.processing_checkpoints "
                               "WHERE attempt_id=%s ORDER BY checkpoint_id",(attempt["attempt_id"],)).fetchall()
        diagnostic.setdefault("checkpoints", [])
        rejected_tasks = []
        for row in rows:
            diagnostic.update(row["payload"])
            diagnostic["checkpoints"].append({"phase":row["phase"],"at":row["recorded_at"].isoformat()})
            if row["phase"] == "task_rejected" and isinstance(row["payload"].get("evidence"),dict):
                rejected_tasks.append(row["payload"])
        reference = diagnostic.get("validator_input_ref")
        if reference:
            plan_reference = diagnostic.get("task_plan_ref")
            plan = self.load_task_plan(reference["context_id"], expected_hash=(plan_reference or {}).get("plan_hash"))
            if plan is not None:
                diagnostic["task_plan"] = plan
            from src.bounded_formation_v1 import _merge_task_proposals
            results = self.task_results(reference["context_id"],attempt_id=attempt["attempt_id"],diagnostic=True)
            if results or "resolved_proposal" not in diagnostic:
                proposal = _merge_task_proposals([row["proposal"] for row in results])
                diagnostic["resolved_proposal"] = proposal
                diagnostic["resolved_proposal_hash"] = stable_json_hash(proposal)
            task_evidence = sorted([*results,*rejected_tasks],key=lambda row:(
                row["task"].get("phase") != "initial",(row.get("timing") or {}).get("index",0)))
            calls = [row["evidence"] for row in task_evidence]
            if calls:
                diagnostic["provider_evidence"] = {**calls[0], "supplementary_calls": calls[1:],
                    "task_policy":"bounded-formation-v1","tasks":[row["task"] for row in task_evidence]}
                if plan is not None:
                    from src.recommendation_task_plan_v1 import report
                    from src.bounded_formation_v1 import _durable_targets
                    from src.semantic_passage_v1 import semantic_source_blocks
                    data = self.resolve_input(reference)
                    blocks = semantic_source_blocks(data["fragments"])
                    proposal = diagnostic["resolved_proposal"]
                    diagnostic["provider_evidence"].update(task_plan=plan,
                        task_plan_summary=report(plan,proposal,_durable_targets(blocks,proposal),
                            selection_scope="attempt_recorded_proposals"))
        return diagnostic

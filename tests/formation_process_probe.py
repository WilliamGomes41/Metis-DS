"""Worker process for #836 crash/restart proof; deterministic model transport."""
import json
from pathlib import Path
import signal
import sys

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.source_bound_fields_v3 import MODE
from tests.production_support import production_application
from tests.test_recommendation_context_v3 import response_for


def run():
    root,dsn,sid,attempt_id,actor,phase,marker = sys.argv[1:]
    calls = []
    def provider(_url,_headers,payload,_timeout):
        text = json.loads(payload["input"][1]["content"])["source_blocks"][0]["text"]
        calls.append(text)
        with Path(marker+".calls").open("a") as log:
            log.write(json.dumps(text)+"\n")
        if phase == "crash" and len(calls) == 2:
            Path(marker).write_text("first-task-committed")
            signal.pause()  # parent kills this owned process, not a simulated exception
        return {"status":"completed","output":[{"type":"message","content":[{
            "type":"output_text","text":json.dumps(response_for(payload,text))}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console,environ={"METIS_PASSAGE_FORMATION_MODE":MODE,
            "METIS_LLM_API_KEY":"fixture","METIS_LLM_MODEL":"test"},post_json=provider)
    console = production_application(Path(root),PostgresCanonicalConfig(dsn=dsn),processing_binder=bind,
        source_store=Path(root)/"sources"/"private",runtime=Path(root)/"runtime"/"console").state.operations_kernel
    if phase == "resume":
        def forbidden(*args,**kwargs):
            raise AssertionError("New worker must read committed source views without extraction/reconstruction")
        console._extract = forbidden
        import src.source_reconstruction_v1 as reconstruction
        reconstruction._with_status = forbidden
    attempt = next(a for a in console._envelope(sid)["processing_attempts"] if a["attempt_id"] == attempt_id)
    console.execute_source_selection(actor_id=actor,snapshot_id=sid,attempt=attempt)
    print(json.dumps({"state":console._envelope(sid)["processing_attempts"][-1]["state"],"calls":calls}))


if __name__ == "__main__":
    run()

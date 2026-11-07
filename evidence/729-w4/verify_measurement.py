"""Run the unchanged source-reuse measurement, then verify a fresh runtime.

Use from either checkout; W4_RESTART_OUT receives hashes/counts only. The added
verification runs after the harness's resume timer, before its database cleanup.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import tests.postgres_support as support
from tests.production_support import restart_production
from src.operations_console_v1 import OperationsConsole

original_database = support.database
original_execute = OperationsConsole.execute_source_selection
completed = []


def execute(self, *args, **kwargs):
    result = original_execute(self, *args, **kwargs)
    completed.append((self, kwargs['snapshot_id']))
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


@contextmanager
def database(*args, **kwargs):
    with original_database(*args, **kwargs) as config:
        yield config
        proofs = []
        for console, sid in completed:
            objects = console.snapshot_objects(sid)
            source = console._verified_source_bytes(console._envelope(sid))[1]
            with console.workflow_document_store._connect() as con:
                tasks = con.execute('SELECT context_id,ranges_hash,result_hash,payload '
                    'FROM workflow.formation_task_results ORDER BY context_id,ranges_hash').fetchall()
                generation = con.execute('SELECT object_generation FROM workflow.documents '
                    'WHERE snapshot_id=%s', (sid,)).fetchone()['object_generation']
            fresh = restart_production(console)
            assert fresh.snapshot_objects(sid) == objects
            assert fresh._verified_source_bytes(fresh._envelope(sid))[1] == source
            assert fresh._envelope(sid)['processing_attempts'][-1]['state'] == 'succeeded'
            assert not fresh.publication_readiness(sid)['publish_allowed']
            with fresh.workflow_document_store._connect() as con:
                assert con.execute('SELECT context_id,ranges_hash,result_hash,payload '
                    'FROM workflow.formation_task_results ORDER BY context_id,ranges_hash').fetchall() == tasks
            assert len(tasks) == 130 and len(objects) == 261
            proofs.append({'task_count': len(tasks), 'object_count': len(objects),
                'object_generation': generation, 'ordered_objects_sha256': digest(objects),
                'committed_tasks_sha256': digest(tasks), 'source_sha256': hashlib.sha256(source).hexdigest(),
                'restart_exact_objects_tasks_source': True, 'publish_allowed': False})
        Path(os.environ['W4_RESTART_OUT']).write_text(json.dumps(proofs, indent=2) + '\n')


support.database = database
OperationsConsole.execute_source_selection = execute
runpy.run_path(str(ROOT / 'scripts/measure_source_task_reuse.py'), run_name='__main__')

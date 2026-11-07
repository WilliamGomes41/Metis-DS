"""Profile successful resume on a dedicated disposable PostgreSQL cluster.

Resets cluster-wide pg_stat_statements counters; never use a shared server.
The original source-reuse harness and its timer remain unchanged.
"""
from pathlib import Path
from collections import defaultdict
from functools import wraps
import json
import os
import runpy
import sys
import threading
import time

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
import psycopg
from psycopg.rows import dict_row
import tests.postgres_support as support
from src.operations_console_v1 import OperationsConsole
import src.workflows.object_delta_postgres_v1 as delta
from src.workflows.formation_task_store_v1 import FormationTaskStore

OUT = Path(os.environ['W4_PROFILE_OUT'])
OUT.mkdir(parents=True, exist_ok=True)
active = False
calls = 0
groups = defaultdict(lambda: {'calls': 0, 'seconds': 0.0})
phases = defaultdict(lambda: {'calls': 0, 'seconds': 0.0})
waits = defaultdict(int)
original_execute = psycopg.Connection.execute
original_schema = support.install_schema
original_run = OperationsConsole.execute_source_selection

def schema(dsn):
    original_schema(dsn)
    with psycopg.connect(dsn, autocommit=True) as con:
        original_execute(con, 'CREATE EXTENSION pg_stat_statements')

def execute(self, query, *args, **kwargs):
    if not active:
        return original_execute(self, query, *args, **kwargs)
    key = ' '.join((query if isinstance(query, str) else query.as_string(self)).split())
    started = time.perf_counter()
    try:
        return original_execute(self, query, *args, **kwargs)
    finally:
        row = groups[key]
        row['calls'] += 1
        row['seconds'] += time.perf_counter() - started

def phase(fn, name):
    @wraps(fn)
    def measured(*args, **kwargs):
        if not active:
            return fn(*args, **kwargs)
        started = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            phases[name]['calls'] += 1
            phases[name]['seconds'] += time.perf_counter() - started
    return measured

def sample_waits(dsn, stop):
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as con:
        while not stop.is_set():
            rows = original_execute(con, 'SELECT state,wait_event_type,wait_event FROM pg_stat_activity '
                'WHERE datname=current_database() AND pid<>pg_backend_pid()').fetchall()
            for row in rows:
                waits['/'.join(str(row[k]) for k in ('state','wait_event_type','wait_event'))] += 1
            stop.wait(.025)

def run(self, *args, **kwargs):
    global calls, active
    calls += 1
    if calls != 2:
        return original_run(self, *args, **kwargs)
    dsn = self.workflow_document_store.config.dsn
    with psycopg.connect(dsn, autocommit=True) as con:
        original_execute(con, 'SELECT pg_stat_statements_reset()')
        original_execute(con, 'SELECT pg_stat_reset()')
    stop = threading.Event()
    sampler = threading.Thread(target=sample_waits, args=(dsn, stop))
    sampler.start()
    started = time.perf_counter()
    active = True
    try:
        result = original_run(self, *args, **kwargs)
    finally:
        active = False
        elapsed = time.perf_counter() - started
        stop.set()
        sampler.join()
        with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as con:
            queries = original_execute(con, 'SELECT query,calls,total_plan_time,total_exec_time,rows,'
                'shared_blks_hit,shared_blks_read,wal_bytes FROM pg_stat_statements '
                'WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) '
                'ORDER BY total_exec_time DESC').fetchall()
            functions = original_execute(con, 'SELECT schemaname,funcname,calls,total_time,self_time '
                'FROM pg_stat_user_functions ORDER BY total_time DESC').fetchall()
        payload = {'scope':'Successful resume only; separate instrumented observation, not latency acceptance',
            'seconds':elapsed, 'client_queries':sorted([dict(query=k,**v) for k,v in groups.items()],key=lambda r:-r['seconds']),
            'phases':dict(phases), 'server_queries':queries, 'server_functions':functions,
            'wait_samples_25ms':dict(waits)}
        text = json.dumps(payload, indent=2, default=str)
        assert 'postgresql://' not in text and 'postgres://' not in text
        (OUT/'profile.json').write_text(text+'\n')
    return result

support.install_schema = schema
psycopg.Connection.execute = execute
OperationsConsole.execute_source_selection = run
delta.write = phase(delta.write, 'object_delta.write')
delta.VerifiedObjectDelta.seal = phase(delta.VerifiedObjectDelta.seal, 'object_delta.seal')
FormationTaskStore.checkpoint = staticmethod(phase(FormationTaskStore.checkpoint, 'formation.checkpoint'))
sys.argv = ['measure_source_task_reuse.py','--counts','130','--output',str(OUT/'result.json')]
runpy.run_path(str(ROOT/'scripts/measure_source_task_reuse.py'),run_name='__main__')

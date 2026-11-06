"""Fresh ordinary production restart; no fixture seed, capture observer or GC changes."""
import gc
import json
import os
from pathlib import Path
import sys
import uvicorn
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from tests.production_support import production_application

config = json.loads(Path(sys.argv[1]).read_text())
app = production_application(Path(config['root']), PostgresCanonicalConfig(dsn=config['dsn']),
    runtime=Path(config['runtime']), source_store=Path(config['source_store']))
console = app.state.operations_kernel
Path(config['ready_metadata']).write_text(json.dumps({
    'pid': os.getpid(), 'gc_enabled': gc.isenabled(), 'gc_threshold': gc.get_threshold(),
    'root': str(console.root), 'runtime': str(console.runtime), 'source_store': str(console.source_store),
    'console_type': type(console).__name__,
    'workflow_store_type': type(console.workflow_document_store).__name__,
    'sha': config['sha'], 'parent_pid': os.getppid(),
}))
uvicorn.run(app, host='127.0.0.1', port=config['port'], access_log=False, log_level='warning',
    ssl_keyfile='/tmp/ko2-perf/server-v4.key', ssl_certfile='/tmp/ko2-perf/server-v4.crt')

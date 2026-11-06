"""KO3 fresh production restart over parent-persisted authorities; no seeding."""
from dataclasses import asdict
from pathlib import Path
import gc
import json
import os
import sys
import time

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from tests.production_support import production_application

config=json.loads(Path(sys.argv[1]).read_text())
app=production_application(Path(config['root']),PostgresCanonicalConfig(dsn=config['dsn']),
    runtime=Path(config['runtime']),source_store=Path(config['source_store']))
console=app.state.operations_kernel
metadata={'pid':os.getpid(),'parent_pid':os.getppid(),'gc_enabled':gc.isenabled(),
    'gc_threshold':gc.get_threshold(),'root':str(console.root),'runtime':str(console.runtime),
    'source_store':str(console.source_store),'console_type':type(console).__name__,'sha':config['sha']}
if config['mode']=='consider':
    started=time.perf_counter()
    result=console.consider_publish(actor_id=config['publisher'],snapshot_id=config['snapshot'])
    wall_ms=(time.perf_counter()-started)*1000
    # This second, warm call is attribution only; it is never the wall sample.
    from src.console_performance_v1 import performance_scope
    with performance_scope() as counters:
        attribution=console.consider_publish(actor_id=config['publisher'],snapshot_id=config['snapshot'])
    Path(config['output']).write_text(json.dumps({'metadata':metadata,'wall_ms':wall_ms,
        'result':result,'attribution_result':attribution,'attribution_only':asdict(counters),
        'attribution_note':'Separate untimed second call; counters do NOT describe the measured first call.'}))
elif config['mode']=='http':
    import uvicorn
    Path(config['metadata']).write_text(json.dumps(metadata))
    uvicorn.run(app,host='127.0.0.1',port=config['port'],access_log=False,log_level='warning',
        ssl_certfile='/tmp/ko3-perf/server.crt',ssl_keyfile='/tmp/ko3-perf/server.key')
else:
    raise ValueError('Unknown probe mode')

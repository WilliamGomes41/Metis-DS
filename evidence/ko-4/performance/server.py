"""Production application for one ordinary Gunicorn worker; no fixture seeding."""
from pathlib import Path
import gc
import json
import os
import subprocess

from gunicorn.config import Config
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from tests.production_support import production_application

config = json.loads(Path(os.environ['KO4_SERVER_CONFIG']).read_text())
root = Path(config['checkout'])
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
assert sha == config['sha']
app = production_application(Path(config['root']), PostgresCanonicalConfig(dsn=config['dsn']),
    runtime=Path(config['runtime']), source_store=Path(config['source_store']))
metadata = {
    'pid': os.getpid(), 'parent_pid': os.getppid(), 'sha': sha,
    'gc_enabled': gc.isenabled(), 'gc_threshold': list(gc.get_threshold()),
    'gunicorn_default_timeout_seconds': Config().timeout,
    'console_type': type(app.state.operations_kernel).__name__,
}
Path(config['metadata']).write_text(json.dumps(metadata))

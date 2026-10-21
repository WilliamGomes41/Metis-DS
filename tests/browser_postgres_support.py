"""Owned PostgreSQL/ASGI composition for standalone browser fixture processes."""
import atexit
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from tests.postgres_support import ROOT, database, install_schema
from tests.production_support import production_application


def browser_application(name, **options):
    resources = ExitStack()
    try:
        directory = Path(resources.enter_context(TemporaryDirectory(prefix='metis-' + name + '-')))
        state = directory / 'postgres-state.json'
        env = {**os.environ, 'PYTHON': sys.executable, 'METIS_TEST_POSTGRES_STATE_FILE': str(state)}
        started = subprocess.run(['bash', str(ROOT / 'scripts/test_postgres.sh')],
                                 env=env, text=True, capture_output=True, check=True, timeout=60)
        if state.exists():
            resources.callback(subprocess.run,
                               ['bash', str(ROOT / 'scripts/test_postgres.sh'), '--stop', str(state)],
                               env=env, check=True, timeout=30, capture_output=True)
        config = resources.enter_context(database(started.stdout.strip()))
        install_schema(config.dsn)
        app = production_application(directory / 'console', config, **options)
        app.state.browser_test_resources = resources
        atexit.register(resources.close)
        return app
    except BaseException:
        resources.close()
        raise

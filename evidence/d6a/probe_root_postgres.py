"""Run as root with PostgreSQL 16 available; no Docker or network installation needed."""
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

import psycopg

assert os.geteuid() == 0, "This probe verifies the root startup branch"
script = Path(__file__).resolve().parents[2] / "scripts/test_postgres.sh"
environment = {**os.environ, "PYTHON": sys.executable}
for name in ("METIS_TEST_POSTGRES_DSN", "METIS_TEST_POSTGRES_STATE_FILE"):
    environment.pop(name, None)
started = subprocess.run(["bash", str(script)], env=environment, capture_output=True, text=True)
assert started.returncode == 0, started.stderr
state_path = Path(re.search(r"Disposable server state: ([^;]+);", started.stderr)[1])
state = json.loads(state_path.read_text())
try:
    assert state_path.stat().st_uid == 0
    assert state_path.stat().st_mode & 0o777 == 0o600
    owner_uid = pwd.getpwnam(state["owner"]).pw_uid
    assert owner_uid != 0 and Path(state["directory"], "data").stat().st_uid == owner_uid
    with psycopg.connect(started.stdout.strip()) as connection:
        version = connection.info.server_version
        assert 160000 <= version < 170000
        assert connection.execute("SELECT 1").fetchone() == (1,)
finally:
    subprocess.run(["bash", str(script), "--stop", str(state_path)], env=environment, check=True)
assert not Path(state["directory"]).exists() and not state_path.exists()
print(json.dumps(dict(root=True, server_user=state["owner"], postgres_version=version,
                      caller_owned_control_state=True, control_mode="0600", cleanup=True)))

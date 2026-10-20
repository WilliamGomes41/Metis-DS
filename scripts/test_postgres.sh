#!/usr/bin/env bash
# stdout is only the DSN; diagnostics go to stderr. No network installation here.
set -euo pipefail
exec "${PYTHON:-python3}" - "$@" <<'PY'
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import tempfile

import psycopg


def command(args, owner=None):
    executable = Path(args[0]).name
    if owner:
        args = ["runuser", "-u", owner, "--", *args]
    try:
        return subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"{executable} failed: {error.stderr.strip()}") from None


def stop(state):
    command([str(Path(state["pgbin"]) / "pg_ctl"), "-D", state["directory"] + "/data",
             "-m", "immediate", "-w", "stop"], state["owner"])
    shutil.rmtree(state["directory"])


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--stop":
        path = Path(sys.argv[2])
        stop(json.loads(path.read_text()))
        path.unlink(missing_ok=True)
        return
    if len(sys.argv) != 1:
        raise RuntimeError("usage: scripts/test_postgres.sh [--stop STATE_FILE]")
    supplied = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if supplied:
        try:
            with psycopg.connect(supplied, connect_timeout=3) as con:
                con.execute("SELECT 1")
            print(supplied)
            return
        except psycopg.Error:
            print("Configured test PostgreSQL is unreachable; trying a disposable server.", file=sys.stderr)

    pgbin = Path(os.environ.get("PGBIN", "/usr/lib/postgresql/16/bin"))
    if not (pgbin / "initdb").is_file():
        found = shutil.which("initdb")
        if found and "PGBIN" not in os.environ:
            pgbin = Path(found).parent
        else:
            raise RuntimeError("PostgreSQL 16 is unavailable; install it during setup and set PGBIN, "
                               "or configure a reachable METIS_TEST_POSTGRES_DSN with CREATEDB rights")
    if not command([str(pgbin / "postgres"), "--version"]).stdout.startswith("postgres (PostgreSQL) 16."):
        raise RuntimeError("PGBIN must point to PostgreSQL 16")

    owner = None
    directory = tempfile.mkdtemp(prefix="metis-test-postgres-")
    if os.geteuid() == 0:
        try:
            account = pwd.getpwnam("postgres")
        except KeyError:
            account = pwd.getpwnam("nobody")
        owner = account.pw_name
        os.chown(directory, account.pw_uid, account.pw_gid)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    state = dict(directory=directory, pgbin=str(pgbin), owner=owner)
    started = False
    try:
        command([str(pgbin / "initdb"), "-D", directory + "/data", "-U", "postgres",
                 "--encoding=UTF8", "--no-locale", "--auth-local=trust", "--auth-host=trust"], owner)
        command([str(pgbin / "pg_ctl"), "-D", directory + "/data", "-l", directory + "/server.log",
                 "-o", f"-h 127.0.0.1 -p {port} -k {directory}", "-w", "start"], owner)
        started = True
        dsn = f"postgresql://postgres@127.0.0.1:{port}/postgres"
        with psycopg.connect(dsn, connect_timeout=3) as con:
            con.execute("SELECT 1")
        state_file = os.environ.get("METIS_TEST_POSTGRES_STATE_FILE")
        if state_file:
            Path(state_file).write_text(json.dumps(state))
        else:
            # Keep control metadata owned by the caller, outside the directory
            # owned by the unprivileged PostgreSQL process (especially as root).
            descriptor, state_file = tempfile.mkstemp(prefix="metis-test-postgres-state-", suffix=".json")
            with os.fdopen(descriptor, "w") as stream:
                json.dump(state, stream)
            print(f"Disposable server state: {state_file}; stop with "
                  f"scripts/test_postgres.sh --stop {state_file}", file=sys.stderr)
        print(dsn)
    except BaseException:
        if started:
            stop(state)
        else:
            shutil.rmtree(directory)
        raise


try:
    main()
except Exception as error:
    # Never expose a supplied DSN/password or subprocess output in pytest errors.
    detail = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    print(f"test_postgres_unavailable: {detail}", file=sys.stderr)
    sys.exit(1)
PY

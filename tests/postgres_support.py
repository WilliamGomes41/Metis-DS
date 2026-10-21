"""Session schema template and independently committed, disposable test databases."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig


ROOT = Path(__file__).resolve().parents[1]
_copies = {}


class _DatabaseCopies:
    """Prepare one fresh copy while a test runs; never reuse a dirty database.

    The single worker also removes returned copies. Its bounded queue prevents
    fast tests from leaving an unbounded cleanup backlog. Capture administrative
    connection methods before test-local SQL spies are installed.
    """

    def __init__(self, dsn, template):
        self.dsn, self.template = dsn, template
        self.admin = psycopg.connect(dsn, autocommit=True)
        self.execute = psycopg.Connection.execute
        self.owned = set()
        self.drops = []
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="metis-test-database")
        self.ready = self.worker.submit(self.create)

    def create(self):
        name = "metis_718_" + uuid4().hex
        self.execute(self.admin, sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
            sql.Identifier(name), sql.Identifier(self.template)))
        self.owned.add(name)
        return name

    def drop(self, name):
        self.execute(self.admin, sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        self.owned.remove(name)

    def acquire(self):
        self.flush(completed_only=True)
        name = self.ready.result()
        self.ready = self.worker.submit(self.create)
        return name

    def release(self, name):
        self.drops.append(self.worker.submit(self.drop, name))
        if len(self.drops) > 2:
            self.drops.pop(0).result()

    def flush(self, *, completed_only=False):
        while self.drops and (not completed_only or self.drops[0].done()):
            self.drops.pop(0).result()

    def close(self):
        self.worker.shutdown(wait=True)
        errors = []
        for future in [self.ready, *self.drops]:
            try:
                future.result()
            except Exception as error:
                errors.append(error)
        for name in list(self.owned):
            try:
                self.drop(name)
            except Exception as error:
                errors.append(error)
        self.admin.close()
        if errors:
            raise ExceptionGroup("Could not prepare or remove owned PostgreSQL test databases", errors)


@contextmanager
def prefetched_databases(dsn, template):
    key = dsn, template
    if key in _copies:
        raise ValueError("Database template already has a copy worker")
    copies = _DatabaseCopies(dsn, template)
    _copies[key] = copies
    try:
        yield copies
    finally:
        del _copies[key]
        copies.close()


def install_schema(dsn):
    with psycopg.connect(dsn, autocommit=True) as con:
        for path in [ROOT / "db/schema_v2.sql", *sorted((ROOT / "db/migrations").glob("*.sql"))]:
            con.execute(path.read_text(encoding="utf-8"))


@contextmanager
def database(dsn, *, template="template0"):
    copies = _copies.get((dsn, template))
    if copies is not None:
        name = copies.acquire()
        try:
            yield PostgresCanonicalConfig(dsn=make_conninfo(dsn, dbname=name))
        finally:
            copies.release(name)
        return
    # Keep the owned-database prefix used by the D4/D5 destructive reset proofs.
    name = "metis_718_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
            sql.Identifier(name), sql.Identifier(template)))
    try:
        yield PostgresCanonicalConfig(dsn=make_conninfo(dsn, dbname=name))
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))

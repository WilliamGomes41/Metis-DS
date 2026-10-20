"""Session schema template and independently committed, disposable test databases."""
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig


ROOT = Path(__file__).resolve().parents[1]


def install_schema(dsn):
    with psycopg.connect(dsn, autocommit=True) as con:
        for path in [ROOT / "db/schema_v2.sql", *sorted((ROOT / "db/migrations").glob("*.sql"))]:
            con.execute(path.read_text(encoding="utf-8"))


@contextmanager
def database(dsn, *, template="template0"):
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

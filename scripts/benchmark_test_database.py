#!/usr/bin/env python3
"""Compare schema rebuild, template clone and rollback on the same commit/read probe.

The independent observer is essential: a faster rollback-only fixture must not
turn a restart/concurrency test into a read of its own uncommitted transaction.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from psycopg.conninfo import conninfo_to_dict
from tests.postgres_support import database, install_schema


def probe(connection, dsn):
    connection.execute("INSERT INTO workflow.topics(topic_id,identity_key,display_name) VALUES ('probe','probe','Probe')")
    with psycopg.connect(dsn) as observer:
        return observer.execute("SELECT count(*) FROM workflow.topics WHERE topic_id='probe'").fetchone()[0] == 1


@contextmanager
def committed(dsn):
    with psycopg.connect(dsn, autocommit=True) as con:
        yield con


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    dsn = os.environ["METIS_TEST_POSTGRES_DSN"]
    rows = {}
    with database(dsn) as template:
        start = time.perf_counter()
        install_schema(template.dsn)
        schema_seconds = time.perf_counter() - start
        name = conninfo_to_dict(template.dsn)["dbname"]
        for method in ("schema", "template", "rollback"):
            samples, visible = [], []
            for _ in range(args.repeats):
                start = time.perf_counter()
                if method == "rollback":
                    with psycopg.connect(template.dsn) as con:
                        visible.append(probe(con, template.dsn))
                        con.rollback()
                else:
                    with database(dsn, template=name if method == "template" else "template0") as config:
                        if method == "schema":
                            install_schema(config.dsn)
                        with committed(config.dsn) as con:
                            visible.append(probe(con, config.dsn))
                samples.append(time.perf_counter() - start)
            rows[method] = dict(repeats=len(samples), median_seconds=round(statistics.median(samples), 6),
                                total_seconds=round(sum(samples), 6), independent_commit_visible=all(visible))
    print(json.dumps(dict(schema_once_seconds=round(schema_seconds, 6), methods=rows), indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Measure real ASGI composition on an isolated PG database, without schema caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repeats", type=int, default=25)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    root = args.checkout.resolve()
    sys.path.insert(0, str(root))
    import psycopg
    import pytest
    from tests.postgres_support import database, install_schema
    from tests.production_support import production_application

    samples, connections, route_sets = [], [], []
    with database(os.environ["METIS_TEST_POSTGRES_DSN"]) as config, tempfile.TemporaryDirectory() as directory:
        install_schema(config.dsn)
        with psycopg.connect(config.dsn) as connection:
            version = connection.info.server_version
            durability = {name: connection.execute("SELECT current_setting(%s)", (name,)).fetchone()[0]
                          for name in ("fsync", "synchronous_commit", "full_page_writes")}
        assert version // 10000 == 16 and set(durability.values()) == {"on"}
        connect = psycopg.connect
        for number in range(args.repeats):
            attempts = []

            def observed(*values, **options):
                attempts.append(1)
                return connect(*values, **options)

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(psycopg, "connect", observed)
                started = time.perf_counter()
                app = production_application(Path(directory) / str(number), config,
                                             processing_binder=lambda console: None)
                samples.append(time.perf_counter() - started)
            connections.append(len(attempts))
            route_sets.append(sorted((route.path, sorted(route.methods or []))
                                     for route in app.routes if hasattr(route, "methods")))
        assert all(routes == route_sets[0] for routes in route_sets)
    report = dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                  python=platform.python_version(), postgres_version=version, durability=durability,
                  repeats=args.repeats, median_seconds=statistics.median(samples), total_seconds=sum(samples),
                  connection_counts=sorted(set(connections)), routes=len(route_sets[0]),
                  route_sha256=hashlib.sha256(json.dumps(route_sets[0]).encode()).hexdigest())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

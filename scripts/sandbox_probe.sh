#!/usr/bin/env bash
# Egress/db evidence from inside the runner. Exit 0 only if egress fails AND db is up.
ok=0
echo "== DNS lookup example.com"; if getent hosts example.com; then echo "FAIL: DNS resolved"; ok=1; else echo "PASS: DNS failed"; fi
echo "== HTTP https://example.com"; if python -c "import urllib.request;urllib.request.urlopen('https://example.com',timeout=5)" 2>&1; then echo "FAIL: HTTP reachable"; ok=1; else echo "PASS: HTTP failed"; fi
echo "== HTTP 1.1.1.1:443 by IP"; if python -c "import socket;socket.create_connection(('1.1.1.1',443),timeout=5)" 2>&1; then echo "FAIL: IP reachable"; ok=1; else echo "PASS: IP unreachable"; fi
echo "== sandbox-db"; if python -c "import psycopg;c=psycopg.connect('postgresql://metis_sandbox:sandbox-only@sandbox-db:5432/metis_security_test',connect_timeout=5);print('db:',c.execute('select current_database()').fetchone()[0])"; then echo "PASS: db reachable"; else echo "FAIL: db unreachable"; ok=1; fi
echo "== read-only root"; if touch /.ro-probe 2>&1; then echo "FAIL: / writable"; ok=1; else echo "PASS: / read-only"; fi
echo "== read-only repo"; if touch /workspaces/metis/.ro-probe 2>&1; then echo "FAIL: repo writable"; ok=1; else echo "PASS: repo read-only"; fi
echo "== no docker socket"; if test ! -S /var/run/docker.sock; then echo "PASS: no docker socket"; else echo "FAIL: docker socket present"; ok=1; fi
exit $ok

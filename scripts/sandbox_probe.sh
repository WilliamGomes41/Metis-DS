#!/usr/bin/env bash
# Egress/db evidence from inside the runner. Exit 0 only if egress fails AND db is up.
ok=0
echo "== diag: resolv.conf"; cat /etc/resolv.conf 2>&1
echo "== diag: ipv4 addresses"; (ip -4 addr 2>/dev/null || cat /proc/net/fib_trie 2>/dev/null | head -n 40)
echo "== diag: /proc/net/route"; cat /proc/net/route 2>&1
echo "== diag: /proc/net/ipv6_route (default)"; awk '$1=="00000000000000000000000000000000"' /proc/net/ipv6_route 2>&1
echo "== DNS lookup example.com"; if getent hosts example.com; then echo "FAIL: DNS resolved"; ok=1; else echo "PASS: DNS failed"; fi
echo "== HTTP https://example.com"; if python -c "
import sys, urllib.request
sys.path.insert(0, 'scripts'); import security_sandbox as s
try: urllib.request.urlopen('https://example.com', timeout=5)
except Exception as e: print(repr(e)); sys.exit(0 if s.egress_error_is_explicit(e) else 1)
print('reachable'); sys.exit(1)" 2>&1; then echo "PASS: HTTP explicit unreachable/DNS failure"; else echo "FAIL: HTTP reachable or failure not explicit (timeout/TLS is no proof)"; ok=1; fi
echo "== HTTP 1.1.1.1:443 by IP (same gate as test/scan/rt)"; if python -c "import sys; sys.path.insert(0, 'scripts'); import security_sandbox as s; s.assert_isolated_network()" 2>&1; then echo "PASS: isolation gate"; else echo "FAIL: isolation gate"; ok=1; fi
echo "== sandbox-db"; if python -c "import psycopg;c=psycopg.connect('postgresql://metis_sandbox:sandbox-only@sandbox-db:5432/metis_security_test',connect_timeout=5);print('db:',c.execute('select current_database()').fetchone()[0])"; then echo "PASS: db reachable"; else echo "FAIL: db unreachable"; ok=1; fi
echo "== read-only root (mount flag)"; if python -c "import sys; sys.path.insert(0, 'scripts'); import security_sandbox as s; sys.exit(0 if s.mount_is_readonly(open('/proc/self/mountinfo').read(), '/') else 1)" 2>&1; then echo "PASS: / mounted ro"; else echo "FAIL: / not mounted ro"; ok=1; fi
echo "== read-only repo"; if touch /workspaces/metis/.ro-probe 2>&1; then echo "FAIL: repo writable"; ok=1; else echo "PASS: repo read-only"; fi
echo "== no docker socket"; if test ! -S /var/run/docker.sock; then echo "PASS: no docker socket"; else echo "FAIL: docker socket present"; ok=1; fi
exit $ok

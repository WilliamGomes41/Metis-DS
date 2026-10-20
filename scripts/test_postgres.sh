#!/usr/bin/env bash
# Start (or reuse) a disposable local PostgreSQL for Metis tests.
#
#   scripts/test_postgres.sh          start or reuse; prints the DSN on stdout
#   scripts/test_postgres.sh --export print "export METIS_TEST_POSTGRES_DSN=..."
#   scripts/test_postgres.sh stop     stop the server this script started
#
# Exit codes: 0 ready, 1 failed to start, 3 PostgreSQL binaries not installed.
#
# A reachable METIS_TEST_POSTGRES_DSN is reused unchanged (CI, devcontainer).
# Otherwise a throwaway cluster is created under METIS_TEST_PG_DIR with trust
# auth on 127.0.0.1 only. Test data only: never point this at real data.
# initdb refuses to run as root, so as root the cluster runs as an unprivileged
# user (METIS_TEST_PG_USER, default "metis-pg", created when missing).
set -euo pipefail

PG_DIR="${METIS_TEST_PG_DIR:-${TMPDIR:-/tmp}/metis-test-pg-$(id -u)}"
PG_PORT="${METIS_TEST_PG_PORT:-54329}"
PG_RUN_USER="${METIS_TEST_PG_USER:-metis-pg}"
DATA="$PG_DIR/data"
LOG="$PG_DIR/server.log"
DSN="postgresql://postgres@127.0.0.1:${PG_PORT}/postgres"

die() { echo "test_postgres: $*" >&2; exit 1; }

emit() {
  if [ "${MODE}" = "--export" ]; then
    echo "export METIS_TEST_POSTGRES_DSN=$1"
  else
    echo "$1"
  fi
}

reachable() {
  command -v psql >/dev/null 2>&1 || return 1
  PGCONNECT_TIMEOUT=3 psql "$1" -Atqc 'select 1' >/dev/null 2>&1
}

find_bindir() {
  if [ -n "${PGBIN:-}" ] && [ -x "$PGBIN/initdb" ]; then echo "$PGBIN"; return; fi
  if command -v pg_config >/dev/null 2>&1; then
    local d; d="$(pg_config --bindir)"
    if [ -x "$d/initdb" ]; then echo "$d"; return; fi
  fi
  local newest
  newest="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)"
  if [ -n "$newest" ] && [ -x "$newest/initdb" ]; then echo "$newest"; return; fi
  if command -v initdb >/dev/null 2>&1; then dirname "$(command -v initdb)"; return; fi
  return 1
}

as_owner() {
  # Run a command as the cluster owner (root cannot own a cluster).
  if [ "$(id -u)" -eq 0 ]; then
    if command -v runuser >/dev/null 2>&1; then
      runuser -u "$PG_RUN_USER" -- "$@"
    else
      su -s /bin/sh "$PG_RUN_USER" -c "$(printf '%q ' "$@")"
    fi
  else
    "$@"
  fi
}

ensure_owner() {
  [ "$(id -u)" -eq 0 ] || return 0
  if ! id "$PG_RUN_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$PG_RUN_USER" 2>/dev/null \
      || useradd -r -M -s /bin/false "$PG_RUN_USER" \
      || die "cannot create user $PG_RUN_USER for the cluster"
  fi
  chown -R "$PG_RUN_USER" "$PG_DIR"
  as_owner test -w "$PG_DIR" \
    || die "$PG_RUN_USER cannot reach $PG_DIR (a parent directory is private); set METIS_TEST_PG_DIR under /tmp"
}

MODE="${1:-}"

if [ "$MODE" = "stop" ]; then
  BIN="$(find_bindir)" || die "PostgreSQL binaries not found"
  [ -d "$DATA" ] || exit 0
  as_owner "$BIN/pg_ctl" -D "$DATA" -m fast stop >/dev/null 2>&1 || true
  exit 0
fi
case "$MODE" in ""|--export) ;; *) die "unknown argument: $MODE" ;; esac

if [ -n "${METIS_TEST_POSTGRES_DSN:-}" ] && reachable "$METIS_TEST_POSTGRES_DSN"; then
  emit "$METIS_TEST_POSTGRES_DSN"; exit 0
fi

if ! BIN="$(find_bindir)"; then
  echo "test_postgres: PostgreSQL 16 binaries not found; install them (see docs/STACK_SETUP_BASELINE.md) or set PGBIN" >&2
  exit 3
fi

mkdir -p "$PG_DIR"
chmod 0755 "$PG_DIR"
ensure_owner

if [ ! -s "$DATA/PG_VERSION" ]; then
  as_owner "$BIN/initdb" -D "$DATA" -U postgres --auth=trust -E UTF8 --no-instructions >/dev/null \
    || die "initdb failed in $DATA"
fi

if ! as_owner "$BIN/pg_ctl" -D "$DATA" status >/dev/null 2>&1; then
  as_owner "$BIN/pg_ctl" -D "$DATA" -l "$LOG" -w -t 30 \
    -o "-p $PG_PORT -c listen_addresses=127.0.0.1 -k $PG_DIR -c fsync=off -c synchronous_commit=off -c full_page_writes=off" \
    start >/dev/null || die "server did not start; see $LOG"
fi

reachable "$DSN" || die "server started but $DSN is not reachable; see $LOG"
emit "$DSN"

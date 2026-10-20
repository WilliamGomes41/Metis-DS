#!/usr/bin/env bash
# Setup phase only (Ubuntu 24.04). Never start the test server here.
set -euo pipefail
if [ ! -x "${PGBIN:-/usr/lib/postgresql/16/bin}/initdb" ]; then
  # Debian package post-install hooks must not start a service during setup.
  policy=/usr/sbin/policy-rc.d
  saved_policy=$(mktemp -d)
  if [ -e "$policy" ]; then cp -a "$policy" "$saved_policy/original"; fi
  restore_policy() {
    rm -f "$policy"
    if [ -e "$saved_policy/original" ]; then mv "$saved_policy/original" "$policy"; fi
    rmdir "$saved_policy"
  }
  trap restore_policy EXIT
  printf '#!/bin/sh\nexit 101\n' > "$policy"
  chmod +x "$policy"
  apt-get update
  apt-get install -y postgresql-16 postgresql-client-16
  restore_policy
  trap - EXIT
fi
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .

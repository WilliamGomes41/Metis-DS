#!/usr/bin/env bash
# Setup phase only (Ubuntu 24.04). Never start the test server here.
set -euo pipefail
if [ ! -x "${PGBIN:-/usr/lib/postgresql/16/bin}/initdb" ]; then
  if [ "$(id -u)" != 0 ]; then
    sudo -n --preserve-env=PGBIN,HTTP_PROXY,HTTPS_PROXY,NO_PROXY,http_proxy,https_proxy,no_proxy,SSL_CERT_FILE \
      bash "$0" --postgres-only
  else
    # Debian package post-install hooks must not start a service during setup.
    policy=/usr/sbin/policy-rc.d
    saved_policy=$(mktemp -d)
    if [ -e "$policy" ] || [ -L "$policy" ]; then cp -a "$policy" "$saved_policy/original"; fi
    restore_policy() {
      rm -f "$policy"
      if [ -e "$saved_policy/original" ] || [ -L "$saved_policy/original" ]; then mv "$saved_policy/original" "$policy"; fi
      rmdir "$saved_policy"
    }
    trap restore_policy EXIT
    rm -f "$policy"
    printf '#!/bin/sh\nexit 101\n' > "$policy"
    chmod +x "$policy"
    apt-get update
    apt-get install -y postgresql-16 postgresql-client-16
    restore_policy
    trap - EXIT
  fi
fi
if [ "${1:-}" = --postgres-only ]; then exit 0; fi
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .

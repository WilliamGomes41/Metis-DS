#!/bin/sh
# Lean kernel checker only; no change to the Metis runtime.
set -eu
test "$(uname -s)-$(uname -m)" = Linux-x86_64 || {
  echo 'This pinned CI installer supports Linux x86_64 only.' >&2; exit 1;
}
destination=${METIS_LEAN_HOME:-$HOME/.local/share/metis-lean-4.34.0}
mkdir -p "$destination"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 20 --max-time 240 \
  https://github.com/leanprover/lean4/releases/download/v4.34.0/lean-4.34.0-linux.tar.zst \
  -o "$tmp/lean.tar.zst"
echo 'caaa98356098c85dc0fcbbd28e1ec66f39eb6551829972b752ff20e1286b646b  '"$tmp/lean.tar.zst" | sha256sum -c -
tar --no-same-owner --zstd -xf "$tmp/lean.tar.zst" -C "$destination" --strip-components=1
"$destination/bin/lean" --version
echo "Add $destination/bin to PATH for bend --verdict."

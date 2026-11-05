#!/usr/bin/env bash
# Run probe_p4b.py at trunk and head checkouts, alternating trunk and head.
# usage: run_p4b.sh <trunk-checkout> <head-checkout> <out-dir> [runs]
set -euo pipefail
trunk=$(cd "$1" && pwd); head=$(cd "$2" && pwd); out=$(mkdir -p "$3" && cd "$3" && pwd)
runs=${4:-5}
probe=$(cd "$(dirname "$0")" && pwd)/probe_p4b.py
python=${PYTHON:-python}

run() {  # label checkout run
  local status=0
  rm -f "$out/$1/perf-$3.json"  # never keep a receipt from an earlier attempt
  cp "$probe" "$2/tests/p4b_probe_tmp.py"
  (cd "$2" && P4B_OUT="$out" P4B_LABEL="$1" P4B_RUN="$3" \
     "$python" -m pytest -q -p no:warnings -p no:cacheprovider tests/p4b_probe_tmp.py \
     > "$out/$1-$3.log" 2>&1) || status=$?
  rm -f "$2/tests/p4b_probe_tmp.py"
  echo "$1 $3: $(grep -E "passed|failed" "$out/$1-$3.log" | tail -1)"
  if [ "$status" -ne 0 ]; then
    echo "$1 $3 failed (exit $status), see $out/$1-$3.log; receipts are incomplete" >&2
    exit "$status"
  fi
}

for i in $(seq 1 "$runs"); do
  run trunk "$trunk" "$i"
  run head "$head" "$i"
done

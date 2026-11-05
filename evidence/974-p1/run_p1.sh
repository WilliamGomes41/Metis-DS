#!/usr/bin/env bash
# Run probe_p1.py at trunk and head checkouts; perf runs interleave.
# usage: run_p1.sh <trunk-checkout> <head-checkout> <out-dir> <lanes|perf> [runs]
set -euo pipefail
trunk=$(cd "$1" && pwd); head=$(cd "$2" && pwd); out=$(mkdir -p "$3" && cd "$3" && pwd)
part=$4; runs=${5:-5}
probe=$(cd "$(dirname "$0")" && pwd)/probe_p1.py
python=${PYTHON:-python}

run() {  # label checkout selector run
  cp "$probe" "$2/tests/p1_probe_tmp.py"
  (cd "$2" && P1_OUT="$out" P1_LABEL="$1" P1_RUN="$4" \
     "$python" -m pytest -q -p no:warnings -p no:cacheprovider -rs tests/p1_probe_tmp.py -k "$3" \
     > "$out/$1-$3-$4.log" 2>&1) || echo "$1 $3 $4 failed, see $out/$1-$3-$4.log"
  rm -f "$2/tests/p1_probe_tmp.py"
  grep -E "passed|failed|skipped" "$out/$1-$3-$4.log" | tail -1
}

if [ "$part" = perf ]; then
  for i in $(seq 1 "$runs"); do
    run trunk "$trunk" perf "$i"
    run head "$head" perf "$i"
  done
else
  run trunk "$trunk" lane 0
  run head "$head" lane 0
fi

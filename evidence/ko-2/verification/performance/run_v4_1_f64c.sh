#!/usr/bin/env bash
set -euo pipefail
perf_dir=/tmp/ko2-perf
run_out=/workspace/ko2-perf-evidence/v4.1-f64c476b
mkdir -p "$run_out"
[ "$(git -C "$perf_dir/head" rev-parse HEAD)" = f64c476b9cde822af650397c1c938a98c83dcb09 ]
[ "$(git -C "$perf_dir/base" rev-parse HEAD)" = 595fe8f233fdee98dfb67609bd5c7206136ee956 ]
[ "$(sha256sum "$perf_dir/probe_v4_finalized.py" | cut -d' ' -f1)" = fb391e729d961d9bdf54c09627f6a5b9deb346ed918c609f4421d0464f238722 ]
[ "$(sha256sum "$perf_dir/server_v4.py" | cut -d' ' -f1)" = c35ff047ca57ca548f20dcf0db9968e5ea0e42db0dd9061f94de8b2d4851b749 ]
cp "$perf_dir/probe_v4_finalized.py" "$run_out/probe.py"
cp "$perf_dir/server_v4.py" "$run_out/server.py"
sha256sum "$perf_dir/probe_v4_finalized.py" "$perf_dir/server_v4.py" > "$run_out/source.sha256"
for run in 1 2 3 4 5; do
 uptime >> "$run_out/load.txt"
 for fixture in legacy native; do
  for label in base head; do
   checkout="$perf_dir/$label"
   if [ "$label" = base ]; then expected_receipt=0; else expected_receipt=1; fi
   cp "$perf_dir/probe_v4_finalized.py" "$checkout/tests/ko2_perf_probe_tmp.py"
   (cd "$checkout" && PATH=/workspace/.postgres/usr/lib/postgresql/17/bin:$PATH METIS_TEST_POSTGRES_DSN=postgresql://postgres@127.0.0.1:55432/postgres KO2_OUT="$run_out" KO2_FIXTURE="$fixture" KO2_LABEL="$label" KO2_ROUND="$run" KO2_EXPECT_RECEIPT="$expected_receipt" /workspace/.venvs/metis-ds/bin/python -m pytest -q tests/ko2_perf_probe_tmp.py > "$run_out/$fixture-$label-$run.log" 2>&1)
   rm "$checkout/tests/ko2_perf_probe_tmp.py"
   printf '%s %s %s completed\n' "$run" "$fixture" "$label"
  done
 done
 printf '%s complete AB pair across both fixtures\n' "$run"
done

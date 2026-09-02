#!/usr/bin/env bash
# Create a reproducible source ZIP from one checked-out Git commit.
# Runtime data deliberately lives outside this archive in /home/data.
set -euo pipefail

output_path="${1:?usage: create_azure_deploy_package.sh <output-path>}"

git diff --exit-code
git diff --cached --exit-code
git archive --format=zip --output "$output_path" HEAD

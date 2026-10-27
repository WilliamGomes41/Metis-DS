#!/usr/bin/env bash
# Build the Metis console release image in Azure Container Registry.
# Same recipe as production: Dockerfile.docling --target runtime, built from a
# clean `git archive` of one exact main commit plus config/deployed_commit.txt,
# so /health can prove the running commit. Adds a tag to the registry only;
# never changes the web app. Swapping the app to the printed digest is a
# separate step (docs/AZURE_RELEASE_RUNBOOK.md).
#
# usage: bash scripts/build_azure_release_image.sh --registry <acr-name> --repository <image-repo> [--commit <sha>] [--dry-run]
set -euo pipefail

registry=""
repository=""
commit=""
dry_run=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --registry) registry="${2:?}"; shift 2 ;;
    --repository) repository="${2:?}"; shift 2 ;;
    --commit) commit="${2:?}"; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    *) echo "release_image_argument_invalid" >&2; exit 2 ;;
  esac
done
if [ -z "${registry}" ] || [ -z "${repository}" ]; then
  echo "release_image_registry_and_repository_required" >&2
  exit 2
fi

if [ -n "${commit}" ] && ! [[ "${commit}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "release_image_commit_must_be_full_sha" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git -C "${ROOT}" fetch --quiet origin main
commit="${commit:-$(git -C "${ROOT}" rev-parse origin/main)}"
if ! git -C "${ROOT}" merge-base --is-ancestor "${commit}" origin/main; then
  echo "release_image_commit_not_on_main" >&2
  exit 2
fi

context="$(mktemp -d)"
trap 'rm -rf "${context}"' EXIT
git -C "${ROOT}" archive "${commit}" | tar -x -C "${context}"
printf '%s\n' "${commit}" > "${context}/config/deployed_commit.txt"
PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}" "${PYTHON:-python3}" "${ROOT}/scripts/stamp_console_release.py" \
  --source "${ROOT}" --target "${context}" --commit "${commit}"
image="${repository}:${commit}"

echo "release_image_commit=${commit}"
echo "release_image_tag=${image}"
if [ "${dry_run}" -eq 1 ]; then
  echo "release_image_dry_run: context prepared, no build started"
  exit 0
fi

az acr build \
  --registry "${registry}" \
  --image "${image}" \
  --file Dockerfile.docling \
  --target runtime \
  --build-arg "METIS_BUILD_COMMIT=${commit}" \
  "${context}"
digest="$(az acr repository show --name "${registry}" --image "${image}" --query digest --output tsv)"
# The login server is not always <name>.azurecr.io (domain name label scope).
login_server="$(az acr show --name "${registry}" --query loginServer --output tsv)"
echo "release_image_digest=${digest}"
echo "release_image_reference=${login_server}/${repository}@${digest}"

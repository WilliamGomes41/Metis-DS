#!/usr/bin/env bash
# APT reads lowercase proxies; sudo and Playwright's nested sudo otherwise drop
# the runner's inherited settings. Run dependency setup as root once, retaining
# only these network variables. Never print or put proxy values in arguments.
set -euo pipefail
export http_proxy="${http_proxy:-${HTTP_PROXY:-}}"
export https_proxy="${https_proxy:-${HTTPS_PROXY:-}}"
export no_proxy="${no_proxy:-${NO_PROXY:-}}"
exec sudo --preserve-env=http_proxy,https_proxy,no_proxy,HTTP_PROXY,HTTPS_PROXY,NO_PROXY "$@"

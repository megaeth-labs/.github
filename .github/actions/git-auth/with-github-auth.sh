#!/usr/bin/env bash
# Supply HTTPS credentials to this process tree without changing Git config files.
set +x
set -euo pipefail
[[ -n "${GITHUB_AUTH_TOKEN:-}" ]] || { echo '::error::GitHub token is required' >&2; exit 1; }
[[ "$#" -gt 0 ]] || { echo '::error::command is required' >&2; exit 1; }
auth_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export GIT_ASKPASS="$auth_dir/askpass.sh"
export GIT_TERMINAL_PROMPT=0
export LC_ALL=C
export CARGO_NET_GIT_FETCH_WITH_CLI=true
# Ignore runner-level credentials and URL rewrites. Reset persisted checkout
# headers and helpers for this process, without touching the checkout's files.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_CONFIG_COUNT=6
export GIT_CONFIG_KEY_0=credential.helper GIT_CONFIG_VALUE_0=''
export GIT_CONFIG_KEY_1=http.extraHeader GIT_CONFIG_VALUE_1=''
export GIT_CONFIG_KEY_2=http.https://github.com/.extraHeader GIT_CONFIG_VALUE_2=''
export GIT_CONFIG_KEY_3=credential.useHttpPath GIT_CONFIG_VALUE_3=false
# Preserve the CI slow-mirror and container-workspace settings in memory only.
export GIT_CONFIG_KEY_4=http.lowSpeedLimit GIT_CONFIG_VALUE_4=0
export GIT_CONFIG_KEY_5=safe.directory GIT_CONFIG_VALUE_5="${GITHUB_WORKSPACE:-$PWD}"
exec "$@"

#!/usr/bin/env bash
# Git invokes this script with a prompt; never return credentials to other hosts.
set +x
set -euo pipefail
case "${1:-}" in
  "Username for 'https://github.com': "*) printf '%s\n' x-access-token ;;
  "Password for 'https://x-access-token@github.com': "*)
    printf '%s\n' "${GITHUB_AUTH_TOKEN:?missing GitHub token}" ;;
  *) exit 1 ;;
esac

#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == run || ${1:-} == create ]]; then
  verb=$1; shift
  exec "$SELF_CONFIGURE_DOCKER" "$verb" --label campaign=dekopon "$@"
elif [[ ${1:-} == network && ${2:-} == create ]]; then
  shift 2
  exec "$SELF_CONFIGURE_DOCKER" network create --label campaign=dekopon "$@"
fi
exec "$SELF_CONFIGURE_DOCKER" "$@"

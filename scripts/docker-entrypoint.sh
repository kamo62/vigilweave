#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  mkdir -p /data
  chown -R vigilweave:vigilweave /data
  quoted_command="$(printf ' %q' "$@")"
  exec su -s /bin/bash vigilweave -c "exec${quoted_command}"
fi

exec "$@"

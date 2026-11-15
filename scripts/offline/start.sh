#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
python="$root/.venv-offline/bin/python"
if [ ! -x "$python" ]; then
    echo 'First run: sh scripts/offline/setup.sh' >&2
    exit 1
fi
# Never inherit application credentials or settings from the preparation machine/shell.
exec env -i HOME="$HOME" PATH=/usr/bin:/bin \
    "$python" -I "$root/scripts/offline/run.py" "$@"

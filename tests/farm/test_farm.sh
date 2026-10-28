#!/bin/sh
# Resolve paths relative to this file, including execution from tests/farm/.
set -eu
FARM_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${FARM_PYTHON:-}" ]; then
    PYTHON=$FARM_PYTHON
elif [ -x "$FARM_DIR/../../.venv/bin/python" ]; then
    PYTHON="$FARM_DIR/../../.venv/bin/python"
else
    PYTHON=python3
fi
exec "$PYTHON" "$FARM_DIR/farm.py" "$@"

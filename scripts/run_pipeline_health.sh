#!/bin/bash
set -euo pipefail
umask 077

SCRIPT_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -f "$SCRIPT_PROJECT_DIR/scripts/pipeline_health.py" ]]; then
    PROJECT_DIR="$SCRIPT_PROJECT_DIR"
else
    PROJECT_DIR="${SGH_VOICE_PROJECT_DIR:-/Users/lin/voice-input}"
fi
if [[ -n "${SGH_VOICE_PYTHON:-}" ]]; then
    PYTHON_RUNNER="$SGH_VOICE_PYTHON"
elif [[ -x "$PROJECT_DIR/venv/bin/python3" ]]; then
    PYTHON_RUNNER="$PROJECT_DIR/venv/bin/python3"
elif ! PYTHON_RUNNER="$(command -v python3)"; then
    PYTHON_RUNNER=""
fi

if [[ ! -x "$PYTHON_RUNNER" ]]; then
    echo "SGH Voice Python is unavailable: ${PYTHON_RUNNER:-not found}" >&2
    exit 78
fi

exec "$PYTHON_RUNNER" "$PROJECT_DIR/scripts/pipeline_health.py" "$@"

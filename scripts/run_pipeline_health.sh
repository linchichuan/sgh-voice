#!/bin/bash
set -euo pipefail
umask 077

SCRIPT_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ -f "$SCRIPT_PROJECT_DIR/scripts/pipeline_health.py" ]]; then
    PROJECT_DIR="$SCRIPT_PROJECT_DIR"
else
    PROJECT_DIR="${SGH_VOICE_PROJECT_DIR:-/Users/lin/voice-input}"
fi
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "SGH Voice virtualenv Python is unavailable: $VENV_PYTHON" >&2
    exit 78
fi

exec "$VENV_PYTHON" "$PROJECT_DIR/scripts/pipeline_health.py" "$@"

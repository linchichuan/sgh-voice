#!/bin/bash
set -euo pipefail

TASK="${1:-}"
if [[ -z "$TASK" ]]; then
    echo "Usage: run_scheduled_task.sh TASK [--self-test]" >&2
    exit 64
fi
shift

SCRIPT_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ -d "$SCRIPT_PROJECT_DIR/scripts" ]]; then
    PROJECT_DIR="$SCRIPT_PROJECT_DIR"
else
    PROJECT_DIR="${SGH_VOICE_PROJECT_DIR:-/Users/lin/voice-input}"
fi
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
export SGH_VOICE_PROJECT_DIR="$PROJECT_DIR"

case "$TASK" in
    dict-update)
        TARGET="$PROJECT_DIR/scripts/dict-update.py"
        RUNNER="$VENV_PYTHON"
        ;;
    promote-corrections)
        TARGET="$PROJECT_DIR/scripts/dictionary_promote_from_history.py"
        RUNNER="$VENV_PYTHON"
        ;;
    maintenance-loop)
        TARGET="$RUNNER_DIR/maintenance_loop.sh"
        [[ -f "$TARGET" ]] || TARGET="$PROJECT_DIR/scripts/maintenance_loop.sh"
        RUNNER="/bin/bash"
        ;;
    hf-watch)
        TARGET="$RUNNER_DIR/hf-model-watch.sh"
        [[ -f "$TARGET" ]] || TARGET="$PROJECT_DIR/scripts/hf-model-watch.sh"
        RUNNER="/bin/bash"
        ;;
    *)
        echo "Unsupported SGH Voice scheduled task: $TASK" >&2
        exit 64
        ;;
esac

if [[ ! -x "$RUNNER" || ! -f "$TARGET" ]]; then
    echo "Scheduled task dependency unavailable: $RUNNER $TARGET" >&2
    exit 78
fi

if [[ "${1:-}" == "--self-test" ]]; then
    exit 0
fi

case "$TASK" in
    dict-update)
        exec "$RUNNER" "$TARGET" --dry-run
        ;;
    promote-corrections)
        exec "$RUNNER" "$TARGET"
        ;;
    *)
        exec "$RUNNER" "$TARGET"
        ;;
esac

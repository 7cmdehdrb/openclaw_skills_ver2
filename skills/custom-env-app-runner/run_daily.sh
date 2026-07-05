#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="/home/soyu/.openclaw/workspace/skills/custom-env-app-runner"
PY_BIN="$SKILL_DIR/.venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  PY_BIN="python3"
fi

cd "$SKILL_DIR"
exec "$PY_BIN" daily_runner.py "$@"

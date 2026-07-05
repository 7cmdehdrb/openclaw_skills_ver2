#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/home/soyu/.openclaw/workspace"
GC_SCRIPT="$WORKSPACE/skills/paper-summary-to-notion/scripts/temp_artifact_gc.py"
LOG_FILE="$WORKSPACE/logs/temp_artifact_gc.log"

mkdir -p "$(dirname "$LOG_FILE")"

started_at="$(date '+%Y-%m-%d %H:%M:%S %Z')"
set +e
output="$(/usr/bin/python3 "$GC_SCRIPT" 2>&1)"
status=$?
set -e

{
  printf '[%s] temp artifact gc exit=%s\n' "$started_at" "$status"
  printf '%s\n' "$output"
} >> "$LOG_FILE"

if [ "$status" -ne 0 ]; then
  exit "$status"
fi

deleted="$(printf '%s\n' "$output" | /usr/bin/python3 -c 'import json,sys
try:
    print(int(json.load(sys.stdin).get("deleted", 0)))
except Exception:
    print(0)
')"

if [ "$deleted" -gt 0 ]; then
  openclaw system event --mode now --text "임시 아티팩트 정리 완료: 만료 항목 ${deleted}개를 삭제했습니다." >/dev/null 2>&1 || true
fi

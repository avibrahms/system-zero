#!/usr/bin/env bash
set -euo pipefail
PROFILE="$SZ_PROFILE_PATH"
[ -f "$PROFILE" ] || { echo "no profile yet"; exit 0; }

CMD="${SZ_SETPOINT_run_command:-}"
GLOB="${SZ_SETPOINT_expected_output_glob:-}"

if [ -z "$CMD" ]; then
  LANG=$(jq -r '.language' "$PROFILE")
  case "$LANG" in
    python)
      MODULE=$(jq -r '.frameworks[0]? // ""' "$PROFILE")
      if [ -z "$MODULE" ] || [ "$MODULE" = "null" ]; then
        MODULE=$(jq -r '.purpose | gsub(" "; "_") | ascii_downcase' "$PROFILE")
      fi
      CMD="python3 -m ${MODULE}.post 2>/dev/null || python3 -m weatherbot.post 2>/dev/null || true"
      ;;
    javascript) CMD="node ." ;;
    typescript) CMD="npm start" ;;
    *)          CMD="" ;;
  esac
fi

if [ -z "$GLOB" ]; then
  GLOB="posts/$(date -u +%Y-%m-%d).txt"
fi

cd "$SZ_REPO_ROOT"

# Idempotent: only run if today's expected output is missing.
if compgen -G "$GLOB" >/dev/null; then
  exit 0
fi

if [ -n "$CMD" ]; then
  bash -c "$CMD" || true
  sz bus emit goal.executed "$(jq -nc --arg cmd "$CMD" --arg glob "$GLOB" '{cmd:$cmd, glob:$glob}')"
fi

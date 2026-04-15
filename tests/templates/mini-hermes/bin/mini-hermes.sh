#!/usr/bin/env bash
set -euo pipefail
INTERVAL="${MINI_HERMES_INTERVAL:-5}"
LOGF="${MINI_HERMES_LOG:-pulse.log}"
HOOKS=()
# Read on_tick hooks from .hermes/config.yaml at startup AND after each iteration (so adopt-mode hot-loads).
load_hooks() {
  HOOKS=()
  while IFS= read -r line; do HOOKS+=("$line"); done < <(python3 -c "import yaml,sys; d=yaml.safe_load(open('.hermes/config.yaml')) or {}; [print(x) for x in d.get('hooks',{}).get('on_tick',[]) or []]")
}
while true; do
  echo "$(date -u +%FT%TZ) alive" >> "$LOGF"
  load_hooks
  for h in "${HOOKS[@]:-}"; do
    bash -c "$h" || true
  done
  sleep "$INTERVAL"
done

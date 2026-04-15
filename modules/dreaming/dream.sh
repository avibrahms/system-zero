#!/usr/bin/env bash
set -euo pipefail
history_lines="${SZ_SETPOINT_max_history_lines:-50}"
prompt_file="$SZ_MODULE_DIR/dream-prompt.txt"
{
  printf 'Generate one concise operational hypothesis from this recent System Zero bus history.\n'
  printf 'Return plain text only.\n\n'
  sz bus tail --last "$history_lines"
} > "$prompt_file"
response="$(sz llm invoke --prompt-file "$prompt_file" --max-tokens 300)"
text="$(printf '%s' "$response" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("text",""))')"
payload="$(jq -nc --arg text "$text" --argjson novelty "${SZ_SETPOINT_novelty_threshold:-0.7}" '{text:$text, novelty_score:$novelty}')"
sz bus emit hypothesis.generated "$payload" --module dreaming

#!/usr/bin/env bash
set -euo pipefail
history_lines="${SZ_SETPOINT_max_history_lines:-50}"
novelty_threshold="${SZ_SETPOINT_novelty_threshold:-0.7}"
sz_bin="${SZ_LLM_BIN:-sz}"
history_file="$SZ_MODULE_DIR/dream-history.json"
error_file="$SZ_MODULE_DIR/dream-llm-error.txt"

"$sz_bin" bus tail --last "$history_lines" > "$history_file"

if ! response="$("$sz_bin" llm invoke \
  --template-id dreaming-hypothesis \
  --template-var-file BUS_HISTORY="$history_file" \
  --template-var NOVELTY_THRESHOLD="$novelty_threshold" \
  --schema dreaming-hypothesis \
  --max-tokens 300 2>"$error_file")"; then
  details="$(cat "$error_file")"
  payload="$(jq -nc --arg template_id "dreaming-hypothesis" --arg details "$details" '{template_id:$template_id, details:$details}')"
  "$sz_bin" bus emit llm.call.failed "$payload" --module dreaming
  exit 1
fi

parsed="$(LLM_RESPONSE="$response" python3 - "$novelty_threshold" <<'PY'
import json
import os
import sys

threshold = float(sys.argv[1])
envelope = json.loads(os.environ["LLM_RESPONSE"])
body = envelope.get("parsed")
if not isinstance(body, dict):
    raise SystemExit("validated LLM response did not include parsed object")

hypothesis = str(body["hypothesis"]).strip()
novelty_score = float(body["novelty_score"])
confidence = float(body["confidence"])
rationale = str(body["rationale"]).strip()
payload = {
    "hypothesis": hypothesis,
    "text": hypothesis,
    "novelty_score": novelty_score,
    "confidence": confidence,
    "rationale": rationale,
}
print(json.dumps({"emit": novelty_score >= threshold, "payload": payload}, separators=(",", ":")))
PY
)"

should_emit="$(PARSED="$parsed" python3 -c 'import json,os; print(str(json.loads(os.environ["PARSED"])["emit"]).lower())')"
if [ "$should_emit" = "true" ]; then
  payload="$(PARSED="$parsed" python3 -c 'import json,os; print(json.dumps(json.loads(os.environ["PARSED"])["payload"], separators=(",", ":")))')"
  "$sz_bin" bus emit hypothesis.generated "$payload" --module dreaming
fi

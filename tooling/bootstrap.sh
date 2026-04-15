#!/usr/bin/env bash
set -euo pipefail
echo "== System Zero bootstrap check =="
python3 --version
for c in git curl jq tar unzip make bash openssl dig node npm gh fly; do
  command -v "$c" >/dev/null || { echo "MISSING: $c"; exit 1; }
done
python3 -c "import yaml, jsonschema, click, rich, platformdirs, fastapi, uvicorn, stripe, httpx, supabase, resend"
mkdir -p ~/.sz
echo "OK"

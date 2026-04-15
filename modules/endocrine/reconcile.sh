#!/usr/bin/env bash
set -euo pipefail
addr=$(sz discovery resolve health.snapshot 2>/dev/null || echo "none")
jq -nc --arg addr "$addr" '{health_snapshot_address: $addr}' > "$SZ_MODULE_DIR/runtime.json"

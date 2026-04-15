#!/usr/bin/env bash
set -euo pipefail
addr=$(sz discovery resolve anomaly.detection 2>/dev/null || echo "none")
jq -nc --arg addr "$addr" '{anomaly_detection_address: $addr}' > "$SZ_MODULE_DIR/runtime.json"

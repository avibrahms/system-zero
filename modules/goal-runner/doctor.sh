#!/usr/bin/env bash
set -euo pipefail
[ -f "$SZ_MODULE_DIR/runtime.json" ] && exit 0 || exit 1

#!/usr/bin/env bash
set -euo pipefail

# Initialize database on module install
python3 -m modules.persistent-memory.entry init 2>/dev/null || true

# Create runtime info
jq -n '{
    module: "persistent-memory",
    status: "ready",
    storage: "SQLite with WAL mode"
}' > "$SZ_MODULE_DIR/runtime.json"
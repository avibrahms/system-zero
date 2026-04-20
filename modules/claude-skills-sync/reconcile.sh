#!/usr/bin/env bash
set -euo pipefail

# Check storage interface
storage_addr=$(sz discovery resolve storage 2>/dev/null || echo "none")

# Initialize skills directory
SKILLS_DIR="${SZ_SETPOINT_skills_dir:-docs/skills}"
mkdir -p "$SKILLS_DIR"

jq -nc --arg storage "$storage_addr" --arg dir "$SKILLS_DIR" '{
    module: "claude-skills-sync",
    status: "ready",
    interfaces: {
        storage: $storage
    },
    skills_directory: $dir,
    features: {
        selective_install: true,
        version_pinning: true,
        auto_update: false
    }
}' > "$SZ_MODULE_DIR/runtime.json"
#!/usr/bin/env bash
set -euo pipefail

# Check required interfaces
memory_addr=$(sz discovery resolve memory 2>/dev/null || echo "none")
bus_addr=$(sz discovery resolve bus 2>/dev/null || echo "none")
llm_addr=$(sz discovery resolve llm 2>/dev/null || echo "none")

jq -nc --arg memory "$memory_addr" --arg bus "$bus_addr" --arg llm "$llm_addr" '{
    module: "sdd-orchestrator",
    status: "ready",
    interfaces: {
        memory: $memory,
        bus: $bus,
        llm: $llm
    },
    token_optimization: {
        templates: true,
        caching: true,
        delta_specs: true
    }
}' > "$SZ_MODULE_DIR/runtime.json"
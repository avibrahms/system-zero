#!/usr/bin/env bash
set -euo pipefail

# Check bus interface
bus_addr=$(sz discovery resolve bus 2>/dev/null || echo "none")

# Initialize approval directory
APPROVAL_DIR="${SZ_MODULE_DIR:-.sz/approval-gate}"
mkdir -p "$APPROVAL_DIR"

jq -nc --arg bus "$bus_addr" --arg mode "${SZ_SETPOINT_mode:-approve}" '{
    module: "approval-gate",
    status: "ready",
    interfaces: {
        bus: $bus
    },
    config: {
        mode: $mode,
        notify_before: true,
        auto_low_threshold: "low"
    },
    features: {
        risk_assessment: true,
        decision_logging: true,
        notifications: true
    }
}' > "$SZ_MODULE_DIR/runtime.json"
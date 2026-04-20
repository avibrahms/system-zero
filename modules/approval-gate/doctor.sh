#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Checking Approval Gate..."

# Check mode
MODE="${SZ_SETPOINT_mode:-approve}"
echo "📋 Mode: $MODE"

# Check approvals directory
APPROVAL_DIR="${SZ_MODULE_DIR:-.sz/approval-gate}"
DECISIONS_FILE="$APPROVAL_DIR/decisions.jsonl"

if [ -f "$DECISIONS_FILE" ]; then
    TOTAL=$(wc -l < "$DECISIONS_FILE" | xargs)
    PENDING=$(grep -c '"pending"' "$DECISIONS_FILE" 2>/dev/null || echo "0")
    APPROVED=$(grep -c '"approved"' "$DECISIONS_FILE" 2>/dev/null || echo "0")
    REJECTED=$(grep -c '"rejected"' "$DECISIONS_FILE" 2>/dev/null || echo "0")
    
    echo "📊 Total proposals: $TOTAL"
    echo "   - Pending: $PENDING"
    echo "   - Approved: $APPROVED"
    echo "   - Rejected: $REJECTED"
else
    echo "⚠️  No decisions file yet (submit a proposal first)"
fi

# Check for approval bypass risks
if [ "$MODE" = "auto-all" ]; then
    echo "⚠️  WARNING: Mode is 'auto-all' - all changes will be auto-approved!"
    echo "   This is dangerous for production systems."
elif [ "$MODE" = "auto-low" ]; then
    echo "✅ Mode is 'auto-low' - low-risk changes auto-approved"
else
    echo "✅ Mode is '$MODE' - all changes require approval"
fi

exit 0
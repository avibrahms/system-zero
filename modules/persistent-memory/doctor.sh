#!/usr/bin/env bash
set -euo pipefail

# Check database health
DB_PATH="${SZ_MODULE_DIR:-.sz/persistent-memory}/memory.db"

if [ -f "$DB_PATH" ]; then
    # Check SQLite integrity
    if sqlite3 "$DB_PATH" "PRAGMA integrity_check;" | grep -q "ok"; then
        echo "✅ Database integrity: OK"
    else
        echo "❌ Database integrity: FAILED"
        exit 1
    fi
    
    # Check table exists
    if sqlite3 "$DB_PATH" ".tables" | grep -q "observations"; then
        echo "✅ Schema: OK"
    else
        echo "❌ Schema: Missing tables"
        exit 1
    fi
    
    # Count observations
    COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM observations;" 2>/dev/null || echo "0")
    echo "📊 Observations stored: $COUNT"
else
    echo "⚠️  Database not initialized (run 'sz mem init' or tick the module)"
fi

exit 0
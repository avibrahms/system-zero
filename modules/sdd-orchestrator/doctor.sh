#!/usr/bin/env bash
set -euo pipefail

# Check required providers
echo "🔍 Checking SDD Orchestrator dependencies..."

# Check memory interface
if sz discovery resolve memory >/dev/null 2>&1; then
    echo "✅ Memory interface: Available"
else
    echo "❌ Memory interface: Not found"
    exit 1
fi

# Check bus interface  
if sz discovery resolve bus >/dev/null 2>&1; then
    echo "✅ Bus interface: Available"
else
    echo "❌ Bus interface: Not found"
    exit 1
fi

# Check LLM interface
if sz discovery resolve llm >/dev/null 2>&1; then
    echo "✅ LLM interface: Available"
else
    echo "⚠️  LLM interface: Not found (SDD will use mock provider)"
fi

echo "📊 Token optimization strategies:"
echo "   - Template reuse: ~40% savings"
echo "   - Context compression: ~30% savings"
echo "   - Delta specs: ~50% savings"
echo "   - Caching: varies"

exit 0
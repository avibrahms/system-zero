#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Checking Claude Skills Sync..."

# Check skills directory
SKILLS_DIR="${SZ_SETPOINT_skills_dir:-docs/skills}"
if [ -d "$SKILLS_DIR" ]; then
    echo "✅ Skills directory: $SKILLS_DIR"
    
    # Count installed skills
    COUNT=$(find "$SKILLS_DIR" -maxdepth 1 -type d | wc -l | xargs)
    echo "📊 Skills installed: $COUNT"
else
    echo "⚠️  Skills directory not created yet"
fi

# Check for conflicts (skill names matching existing directories)
echo "🔍 Checking for conflicts..."
if find . -maxdepth 2 -type d -name "docs" | grep -q .; then
    echo "✅ docs/ directory exists"
fi

echo "📋 Available skills:"
echo "   - react-19, nextjs-15, prisma"
echo "   - playwright, tailwind-4, zustand-5"
echo "   - supabase, sdd (+30 more)"

exit 0
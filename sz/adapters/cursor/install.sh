#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES="$REPO_ROOT/.cursorrules"
MARKER_BEGIN="# >>> sz-cursor >>>"
MARKER_END="# <<< sz-cursor <<<"
touch "$RULES"
if grep -q "$MARKER_BEGIN" "$RULES"; then
  :
else
  {
    cat "$RULES"
    echo ""
    echo "$MARKER_BEGIN"
    echo "When you finish a coherent change, run: sz tick --reason cursor"
    echo "$MARKER_END"
  } > "$RULES.tmp"
  mv "$RULES.tmp" "$RULES"
fi
bash "$ADAPTER_DIR/../generic/install.sh"
echo "cursor adapter installed (Install mode)"

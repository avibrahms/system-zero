#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES="$REPO_ROOT/.cursorrules"
MARKER_BEGIN="# >>> sz-cursor >>>"
MARKER_END="# <<< sz-cursor <<<"
if [ -f "$RULES" ]; then
  python3 - "$RULES" "$MARKER_BEGIN" "$MARKER_END" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
begin = sys.argv[2]
end = sys.argv[3]
out = []
skipping = False
for line in path.read_text().splitlines():
    if line == begin:
        skipping = True
        continue
    if line == end:
        skipping = False
        continue
    if not skipping:
        out.append(line)
path.write_text("\n".join(out).rstrip() + ("\n" if out else ""))
PY
fi
bash "$ADAPTER_DIR/../generic/uninstall.sh"
echo "cursor adapter uninstalled"

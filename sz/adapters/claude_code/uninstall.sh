#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
rm -f "$REPO_ROOT/.claude/hooks/sz-on-prompt.sh" "$REPO_ROOT/.claude/hooks/sz-on-stop.sh"

python3 - "$REPO_ROOT/.claude/settings.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists() or not path.read_text().strip():
    raise SystemExit(0)
data = json.loads(path.read_text())

def scrub(value):
    if isinstance(value, str):
        return None if "sz-on-" in value else value
    if isinstance(value, list):
        out = []
        for item in value:
            cleaned = scrub(item)
            if cleaned not in (None, [], {}):
                out.append(cleaned)
        return out
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            cleaned = scrub(item)
            if cleaned not in (None, [], {}):
                out[key] = cleaned
        return out
    return value

path.write_text(json.dumps(scrub(data) or {}, indent=2, sort_keys=False) + "\n")
PY

bash "$ADAPTER_DIR/../generic/uninstall.sh"
echo "claude_code adapter uninstalled"

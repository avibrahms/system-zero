#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_DIR="$REPO_ROOT/.claude/hooks"
mkdir -p "$HOOK_DIR"

cat > "$HOOK_DIR/sz-on-prompt.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
sz bus emit host.session.started '{"source":"claude_code"}' || true
EOF
cat > "$HOOK_DIR/sz-on-stop.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
sz bus emit host.session.ended '{"source":"claude_code"}' || true
sz tick --reason claude_code || true
EOF
chmod +x "$HOOK_DIR/sz-on-prompt.sh" "$HOOK_DIR/sz-on-stop.sh"

python3 - "$REPO_ROOT/.claude/settings.json" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
if path.exists() and path.read_text().strip():
    data = json.loads(path.read_text())
else:
    data = {}
hooks = data.setdefault("hooks", {})

def add_hook(event, command):
    entries = hooks.setdefault(event, [])
    wanted = {"hooks": [{"type": "command", "command": command}]}
    if wanted not in entries:
        entries.append(wanted)

add_hook("UserPromptSubmit", "bash .claude/hooks/sz-on-prompt.sh")
add_hook("Stop", "bash .claude/hooks/sz-on-stop.sh")
path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
PY

bash "$ADAPTER_DIR/../generic/install.sh"
echo "claude_code adapter installed (Install mode)"

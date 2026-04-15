#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK_DIR="$REPO_ROOT/.opencode/hooks"
mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/sz-session-end.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
sz bus emit host.session.ended '{"source":"opencode"}' || true
sz tick --reason opencode || true
EOF
chmod +x "$HOOK_DIR/sz-session-end.sh"
bash "$ADAPTER_DIR/../generic/install.sh"
echo "opencode adapter installed (Install mode)"

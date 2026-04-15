#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$ADAPTER_DIR/../generic/install.sh"
cat > "$REPO_ROOT/.aider.sz.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
sz tick --reason aider || true
EOF
chmod +x "$REPO_ROOT/.aider.sz.sh"
echo "aider adapter installed (Install mode)"

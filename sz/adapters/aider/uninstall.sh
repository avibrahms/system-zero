#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
ADAPTER_DIR="$(cd "$(dirname "$0")" && pwd)"
rm -f "$REPO_ROOT/.aider.sz.sh"
bash "$ADAPTER_DIR/../generic/uninstall.sh"
echo "aider adapter uninstalled"

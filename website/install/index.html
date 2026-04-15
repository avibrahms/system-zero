#!/usr/bin/env bash
set -euo pipefail
echo "== System Zero installer =="
PYTHON="${PYTHON:-python3}"
$PYTHON --version >/dev/null 2>&1 || { echo "Need python3 (3.10+). Install it first." >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_WHEEL="${SYSTEM_ZERO_WHEEL:-}"
if [ -z "$LOCAL_WHEEL" ] && [ -f "$SCRIPT_DIR/dist/system_zero-0.1.0-py3-none-any.whl" ]; then
  LOCAL_WHEEL="$SCRIPT_DIR/dist/system_zero-0.1.0-py3-none-any.whl"
fi
TARGET="${LOCAL_WHEEL:-git+https://github.com/avibrahms/system-zero@v0.1.0}"

if command -v pipx >/dev/null; then
  echo "Using pipx."
  pipx install --force "$TARGET"
elif $PYTHON -m pip --version >/dev/null 2>&1; then
  echo "Using pip --user."
  $PYTHON -m pip install --user --upgrade "$TARGET"
else
  echo "Need pip or pipx." >&2; exit 1
fi

echo ""
echo "Installed. Try: sz --help"
echo "Quick start:"
echo "  cd your/repo"
echo "  sz init     # this will run Repo Genesis"

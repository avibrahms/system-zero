#!/usr/bin/env bash
set -euo pipefail
REPORT="${REPORT:-$PWD/.test-reports/phase-09.json}"
mkdir -p "$(dirname "$REPORT")"
results='[]'

record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

# 1) PyPI-equivalent: install from local wheel via pipx
TMP=$(mktemp -d)
WHEEL=$(ls "$PWD/dist"/system_zero-0.1.0-py3-none-any.whl)
PIPX_HOME="$TMP/pipx" PIPX_BIN_DIR="$TMP/bin" pipx install "$WHEEL" --force
"$TMP/bin/sz" --version | grep -q "0.1.0" && record "channel: pip wheel" pass "$WHEEL" || record "channel: pip wheel" fail ""

# 2) curl bootstrap
PIPX_HOME="$TMP/pipx2" PIPX_BIN_DIR="$TMP/bin2" SYSTEM_ZERO_WHEEL="$WHEEL" bash install.sh
"$TMP/bin2/sz" --version | grep -q "0.1.0" && record "channel: install.sh" pass "" || record "channel: install.sh" fail ""

# 3) npm wrapper
( cd npm-wrapper && npm pack --silent )
TGZ=$(ls "$PWD/npm-wrapper"/system-zero-0.1.0.tgz)
trap 'rm -f "$TGZ"' EXIT
NPM_PREFIX="$TMP/npm"
mkdir -p "$NPM_PREFIX"
PIPX_HOME="$TMP/pipx3" PIPX_BIN_DIR="$TMP/bin3" PATH="$TMP/bin3:$PATH" SYSTEM_ZERO_WHEEL="$WHEEL" npm i -g --prefix "$NPM_PREFIX" "$TGZ"
NPM_CONFIG="$(npm root -g --prefix "$NPM_PREFIX")/system-zero/.system-zero-cli.json"
CLI_REAL=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$TMP/bin3/sz")
jq -e --arg cli "$CLI_REAL" '.cliPath == $cli' "$NPM_CONFIG" >/dev/null && record "channel: npm cli path" pass "$NPM_CONFIG" || record "channel: npm cli path" fail "$NPM_CONFIG"
if NPM_OUTPUT=$(PATH="$NPM_PREFIX/bin:$TMP/bin3:$PATH" python3 - "$NPM_PREFIX/bin/sz" <<'PY'
import os
import subprocess
import sys

try:
    result = subprocess.run(
        [sys.argv[1], "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=10,
        env=os.environ,
    )
except subprocess.TimeoutExpired:
    print("npm wrapper timed out; possible recursive sz resolution")
    sys.exit(124)

print(result.stdout, end="")
sys.exit(result.returncode)
PY
); then
  echo "$NPM_OUTPUT" | grep -q "0.1.0" && record "channel: npm" pass "$TGZ" || record "channel: npm" fail "$NPM_OUTPUT"
else
  record "channel: npm" fail "$NPM_OUTPUT"
fi

echo "$results" | jq . > "$REPORT"
echo "Channels report at $REPORT"
FAILED=$(jq '[.[] | select(.status=="fail")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 09 FAILED ($FAILED)"; exit 1; }
echo "PHASE 09 PASSED"

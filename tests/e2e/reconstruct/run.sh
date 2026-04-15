#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/Users/avi/Documents/Projects/system0-natural"
REPORT="$REPO_ROOT/.test-reports/phase-16.json"
mkdir -p "$(dirname "$REPORT")"

# Fresh clone of the reference repo.
WORK=$(mktemp -d)
cd "$WORK"
gh repo clone "${SZ_GITHUB_OWNER:-avibrahms}/connection-engine-reference"
cd connection-engine-reference
bash bootstrap.sh

# Must end up alive.
LIST_OUTPUT="$(sz list)"
printf '%s\n' "$LIST_OUTPUT" | grep -Eq "heartbeat|immune|subconscious" || { echo "no core modules"; exit 1; }
printf '%s\n' "$LIST_OUTPUT" | grep -q "skill-library-ce" || { echo "no rewritten skill library"; exit 1; }
sz tick --reason reconstruct-check
sz tick --reason reconstruct-check
sz bus tail --last 50 --filter "health.snapshot" | grep -q . || { echo "no snapshot"; exit 1; }
CE_SNAPSHOTS="$(sz bus tail --last 200 --filter "ce.*.snapshot" | jq 'length')"
[ "$CE_SNAPSHOTS" -gt 0 ] || { echo "no reconstructed module snapshots"; exit 1; }

# Anonymization sweep — no HITs in the entire checkout.
rm -f .sz/bin/sz
if ! python3 "$REPO_ROOT/tools/anonymize.py" . >/tmp/anon.out 2>&1; then
  cat /tmp/anon.out
  echo "anonymization violated"; exit 1
fi
if [ -s /tmp/anon.out ]; then
  cat /tmp/anon.out
  echo "anonymization violated"; exit 1
fi

MODULES="$(sz list | wc -l | tr -d " ")"
printf '{"status":"PASSED","modules":%s,"ce_snapshot_events":%s,"catalog":"public"}\n' "$MODULES" "$CE_SNAPSHOTS" > "$REPORT"
echo "PHASE 16 PASSED"

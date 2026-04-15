#!/usr/bin/env bash
set -euo pipefail
ROOT="$PWD"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
REPORT="$ROOT/.test-reports/phase-13.json"
source "$ROOT/tests/e2e/absorb/fixtures.sh"
source "$ROOT/tests/e2e/sz-shim.sh"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

WORK=$(mktemp -d)
install_local_sz_shim "$ROOT" "$WORK/bin"
export PATH="$WORK/bin:$PATH"
cp -R tests/templates/mini-hermes "$WORK/repo"
cd "$WORK/repo"
git init -q
git config user.email "t@t" && git config user.name "t"
git config commit.gpgsign false
git add -A && git commit -qm "init"

PROFILE_JSON='{
  "purpose":"keep pulse.log growing forever",
  "language":"shell",
  "frameworks":["mini-hermes"],
  "existing_heartbeat":"hermes",
  "goals":["append a heartbeat line to pulse.log every interval"],
  "recommended_modules":[
    {"id":"immune","reason":"detect anomalies"},
    {"id":"subconscious","reason":"aggregate health"},
    {"id":"prediction","reason":"predict next event"},
    {"id":"goal-runner","reason":"verify the daemon is producing output"},
    {"id":"changed-file-detector","reason":"absorbed OS feature: report git diffs on pulse"}
  ],
  "risk_flags":[]
}'

# Pre-absorb the OS feature (changed-file-detector) before genesis so the catalog contains it.
CACHE="$HOME/.sz/cache/test-fixtures/absorb"
ensure_absorb_fixture_cache "$CACHE"

# Run genesis in Adopt mode (default) via the tests/-only canned helper (no SZ_FORCE_* in shipping code).
sz init --host hermes --no-genesis --yes
python3 /Users/avi/Documents/Projects/system0-natural/tests/helpers/run_genesis_with_profile.py --profile "$PROFILE_JSON"

host_mode_check=$(python3 -c "import yaml; d=yaml.safe_load(open('.sz.yaml')); print('yes' if d.get('host') == 'hermes' and d.get('host_mode') == 'adopt' else 'no')")
[ "$host_mode_check" = "yes" ] && record "dynamic: host=hermes adopt mode" pass "" || record "dynamic: host=hermes adopt mode" fail "$host_mode_check"

# heartbeat must NOT be installed; the others must be.
jq -e '.modules.heartbeat | not' .sz/registry.json >/dev/null && record "dynamic: heartbeat correctly excluded" pass "" || record "dynamic: heartbeat correctly excluded" fail ""

# >=3 CE modules installed + >=1 OS absorbed module installed.
CE_COUNT=0
for m in immune subconscious prediction metabolism endocrine dreaming; do
  jq -e --arg m "$m" '.modules[$m]' .sz/registry.json >/dev/null 2>&1 && CE_COUNT=$((CE_COUNT+1))
done
[ "$CE_COUNT" -ge 3 ] && record "dynamic: >=3 CE modules installed" pass "count=$CE_COUNT" || record "dynamic: >=3 CE modules installed" fail "count=$CE_COUNT"

# Absorb the OS feature (post-genesis, as a real user would).
export SZ_ABSORB_CANNED=/Users/avi/Documents/Projects/system0-natural/tests/e2e/absorb/canned
python3 /Users/avi/Documents/Projects/system0-natural/tests/helpers/absorb_with_canned.py "$CACHE/changed-files" changed-file-detector
jq -e '.modules["changed-file-detector"]' .sz/registry.json >/dev/null && record "dynamic: >=1 OS module absorbed" pass "" || record "dynamic: >=1 OS module absorbed" fail ""

# The Hermes config now contains the sz hook.
yq_check=$(python3 -c "import yaml; d=yaml.safe_load(open('.hermes/config.yaml')); print('yes' if 'sz tick --reason hermes' in (d.get('hooks',{}).get('on_tick') or []) else 'no')")
[ "$yq_check" = "yes" ] && record "dynamic: hermes hook patched" pass "" || record "dynamic: hermes hook patched" fail "$yq_check"

# In Adopt mode SZ must NOT have started its own heartbeat.
[ ! -f .sz/heartbeat.pid ] && record "dynamic: no double pulse (adopt)" pass "" || record "dynamic: no double pulse (adopt)" fail "heartbeat.pid exists"

# Start the existing daemon, watch for 30 seconds.
( cd "$WORK/repo" && bash bin/mini-hermes.sh ) &
DAEMON=$!
sleep 30
kill $DAEMON 2>/dev/null || true
wait $DAEMON 2>/dev/null || true

# pulse.log grew normally
PULSES=$(wc -l < pulse.log | tr -d ' ')
[ "$PULSES" -ge 5 ] && record "dynamic: pulse.log grew" pass "$PULSES" || record "dynamic: pulse.log grew" fail "$PULSES"

# bus has events that came from the adopted pulse
TICKS=$(sz bus tail --last 200 --filter tick | jq 'length')
SNAPSHOTS=$(sz bus tail --last 200 --filter "health.snapshot" | jq 'length')
PREDICTIONS=$(sz bus tail --last 200 --filter "prediction.next" | jq 'length')
GOALS=$(sz bus tail --last 200 --filter "goal.executed" | jq 'length')
[ "$TICKS" -ge 3 ] && record "dynamic: ticks via adopted pulse" pass "$TICKS" || record "dynamic: ticks via adopted pulse" fail "$TICKS"
[ "$SNAPSHOTS" -ge 1 ] && record "dynamic: subconscious ran" pass "$SNAPSHOTS" || record "dynamic: subconscious ran" fail "$SNAPSHOTS"
[ "$PREDICTIONS" -ge 1 ] && record "dynamic: prediction ran" pass "$PREDICTIONS" || record "dynamic: prediction ran" fail "$PREDICTIONS"
[ "$GOALS" -ge 1 ] && record "dynamic: goal-runner ran" pass "$GOALS" || record "dynamic: goal-runner ran" fail "$GOALS"

# ---------- MERGE MODE SECOND-PASS ----------
# Re-init the same repo in merge mode; verify both pulses coexist; dedup works.
sz host install hermes --mode merge
merge_mode_check=$(python3 -c "import yaml; d=yaml.safe_load(open('.sz.yaml')); print('yes' if d.get('host_mode') == 'merge' else 'no')")
[ "$merge_mode_check" = "yes" ] && record "dynamic: merge mode set" pass "" || record "dynamic: merge mode set" fail "$merge_mode_check"
# Generic adapter also installed a cron line (heartbeat.pid may not exist because we don't `sz start`;
# instead the cron entry fires sz tick every N min — we validate by forcing two ticks close together).
BEFORE_DEDUP=$(sz bus tail --last 200 --filter tick | jq 'length')
sz tick --reason merge-test
sz tick --reason merge-test
AFTER_DEDUP=$(sz bus tail --last 200 --filter tick | jq 'length')
DEDUPED=$((AFTER_DEDUP - BEFORE_DEDUP))
# With a 30s default dedup window, the second tick should be swallowed.
[ "$DEDUPED" -le 1 ] && record "dynamic: merge dedup works" pass "$DEDUPED" || record "dynamic: merge dedup works" fail "$DEDUPED"

# Reconcile idempotent after all the dance.
sz reconcile --reason check
A=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
sz reconcile --reason check
B=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
[ "$A" = "$B" ] && record "dynamic: reconcile idempotent" pass "$A" || record "dynamic: reconcile idempotent" fail ""

echo "$results" | jq . > "$REPORT"
FAILED=$(jq '[.[] | select(.status=="fail")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 13 FAILED ($FAILED)"; exit 1; }
echo "PHASE 13 PASSED"

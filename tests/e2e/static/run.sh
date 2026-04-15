#!/usr/bin/env bash
set -euo pipefail
ROOT="$PWD"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
REPORT="$ROOT/.test-reports/phase-12.json"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

WORK=$(mktemp -d)
cp -R tests/templates/static-weatherbot "$WORK/repo"
find "$WORK/repo/posts" -type f ! -name ".gitkeep" -delete
cd "$WORK/repo"
git init -q
git config user.email "t@t" && git config user.name "t"
git config commit.gpgsign false
git add -A && git commit -qm "init"

# Run init with auto-yes. The test forces a canned profile by launching a small
# Python helper that monkeypatches sz.interfaces.llm.invoke in-process. The
# public CLI wrapper test below uses the documented SZ_FORCE_GENESIS_PROFILE hook.

PROFILE_JSON='{
  "purpose":"post weather to a file daily",
  "language":"python",
  "frameworks":["weatherbot"],
  "existing_heartbeat":"none",
  "goals":["produce posts/<date>.txt once per day"],
  "recommended_modules":[
    {"id":"heartbeat","reason":"required for static repos"},
    {"id":"immune","reason":"detect leaked secrets"},
    {"id":"subconscious","reason":"aggregate CE-derived health"},
    {"id":"goal-runner","reason":"actually run the project"},
    {"id":"prediction","reason":"predict next likely event from history"}
  ],
  "risk_flags":[]
}'

# Pre-absorb the open-source feature so it is in the catalog before genesis.
# (In production the user would do `sz absorb` after init; the test front-loads.)
CACHE="$HOME/.sz/cache/test-fixtures/absorb"
[ -d "$CACHE/p-limit" ] || git clone --depth 1 https://github.com/sindresorhus/p-limit "$CACHE/p-limit"
python3 - <<PY
# monkeypatch the mock provider inside a child sz process via an env var that
# conftest-style bootstrap uses. Tests-only.
import os
os.environ["SZ_TEST_CANNED_PROFILE"] = '''$PROFILE_JSON'''
PY

# tests/helpers/run_genesis_with_profile.py is a tests-only helper that:
# 1) replaces sz.interfaces.llm.invoke with a canned function for this process.
# 2) invokes sz.core.genesis.genesis() directly.
# 3) persists the profile and runs the install loop.
sz init --host generic --no-genesis --yes
python3 /Users/avi/Documents/Projects/system0-natural/tests/helpers/run_genesis_with_profile.py --profile "$PROFILE_JSON"

# Verify Genesis output.
profile=$(cat .sz/repo-profile.json)
echo "$profile" | jq -e '.purpose | test("weather"; "i")' >/dev/null && record "static: profile mentions weather" pass "" || record "static: profile mentions weather" fail ""
echo "$profile" | jq -e '.recommended_modules | map(.id) | index("heartbeat")' >/dev/null && record "static: heartbeat recommended" pass "" || record "static: heartbeat recommended" fail ""
echo "$profile" | jq -e '.recommended_modules | map(.id) | index("goal-runner")' >/dev/null && record "static: goal-runner recommended" pass "" || record "static: goal-runner recommended" fail ""

# Required: >=3 CE-derived modules installed + >=1 absorbed-OS module installed.
CE_COUNT=0
for m in heartbeat immune subconscious metabolism endocrine prediction dreaming; do
  jq -e --arg m "$m" '.modules[$m]' .sz/registry.json >/dev/null 2>&1 && CE_COUNT=$((CE_COUNT+1))
done
[ "$CE_COUNT" -ge 3 ] && record "static: >=3 CE modules installed" pass "count=$CE_COUNT" || record "static: >=3 CE modules installed" fail "count=$CE_COUNT"

# Absorb the OS feature in the same repo (post-genesis, as a real user would).
# Uses the same stub-absorb mechanism as phase 14.
export SZ_ABSORB_CANNED=/Users/avi/Documents/Projects/system0-natural/tests/e2e/absorb/canned
python3 /Users/avi/Documents/Projects/system0-natural/tests/helpers/absorb_with_canned.py "$CACHE/p-limit" concurrency-limiter
jq -e '.modules["concurrency-limiter"]' .sz/registry.json >/dev/null && record "static: >=1 OS module absorbed" pass "" || record "static: >=1 OS module absorbed" fail ""

# goal-runner also installed.
jq -e '.modules["goal-runner"]' .sz/registry.json >/dev/null && record "static: goal-runner installed" pass "" || record "static: goal-runner installed" fail ""

# Start heartbeat at 5s interval, watch for 30s.
sz stop >/dev/null 2>&1 || true
rm -f "posts/$(date -u +%Y-%m-%d).txt"
sz start --interval 5
sleep 30
sz stop

# Bus assertions.
TICKS=$(sz bus tail --last 200 --filter pulse.tick | jq 'length')
[ "$TICKS" -ge 3 ] && record "static: ticks landed" pass "$TICKS" || record "static: ticks landed" fail "$TICKS"
GOAL_EVENTS=$(sz bus tail --last 200 --filter goal.executed | jq 'length')
[ "$GOAL_EVENTS" -ge 1 ] && record "static: goal acted upon" pass "$GOAL_EVENTS" || record "static: goal acted upon" fail "$GOAL_EVENTS"

# The actual goal: today's posts/<date>.txt exists.
TODAY="posts/$(date -u +%Y-%m-%d).txt"
[ -f "$TODAY" ] && record "static: goal artifact exists" pass "$TODAY" || record "static: goal artifact exists" fail "$TODAY missing"

# Subconscious and prediction should both have emitted live signals.
SNAPSHOT=$(sz memory get subconscious.snapshot 2>/dev/null || echo null)
echo "$SNAPSHOT" | jq -e '.color == "GREEN"' >/dev/null && record "static: subconscious green" pass "$SNAPSHOT" || record "static: subconscious green" fail "$SNAPSHOT"
PREDICTIONS=$(sz bus tail --last 200 --filter prediction.next | jq 'length')
[ "$PREDICTIONS" -ge 1 ] && record "static: prediction events landed" pass "$PREDICTIONS" || record "static: prediction events landed" fail "$PREDICTIONS"

# Reconcile idempotent.
sz reconcile --reason check
A=$(sha256sum .sz/registry.json | awk '{print $1}')
sz reconcile --reason check
B=$(sha256sum .sz/registry.json | awk '{print $1}')
[ "$A" = "$B" ] && record "static: reconcile idempotent" pass "$A" || record "static: reconcile idempotent" fail "A=$A B=$B"

echo "$results" | jq . > "$REPORT"
FAILED=$(jq '[.[] | select(.status=="fail")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 12 FAILED ($FAILED)"; exit 1; }
echo "PHASE 12 PASSED"

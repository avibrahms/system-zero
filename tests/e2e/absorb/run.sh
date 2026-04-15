#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
REPORT="$REPO_ROOT/.test-reports/phase-14.json"
source "$SCRIPT_DIR/fixtures.sh"
source "$REPO_ROOT/tests/e2e/sz-shim.sh"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

MOD="$REPO_ROOT/modules"
SOURCE_HOME="$HOME"
CACHE="${SZ_ABSORB_SOURCE_CACHE:-$SOURCE_HOME/.sz/cache/test-fixtures/absorb}"
ensure_absorb_fixture_cache "$CACHE"

WORK_ROOT=$(mktemp -d)
WORK="$WORK_ROOT/repo"
HOST_PYTHONUSERBASE="$(python3 -m site --user-base 2>/dev/null || true)"
export HOME="$WORK_ROOT/home"
export PYTHONUSERBASE="$HOST_PYTHONUSERBASE"
install_local_sz_shim "$REPO_ROOT" "$WORK_ROOT/bin"
export PATH="$WORK_ROOT/bin:$PATH"
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"
mkdir -p "$HOME" "$WORK"
cd "$WORK"
git init -q
git config user.email "t@t"
git config user.name "t"
git config commit.gpgsign false
echo init > README.md; git add -A; git commit -qm "init"

# Init in adopt-skip mode (just for the test; real users do `sz init`).
sz init --host generic --no-genesis
for m in heartbeat immune subconscious metabolism; do sz install "$m" --source "$MOD/$m"; done

# Use canned mock for absorb.
export SZ_LLM_PROVIDER=mock
export SZ_ABSORB_CANNED="$REPO_ROOT/tests/e2e/absorb/canned"

bus_count() { sz bus tail | jq 'length'; }
pulse_count() { sz bus tail --filter pulse.tick | jq 'length'; }
snapshot_anomaly_count() { sz memory get subconscious.snapshot | jq -r '.anomaly_count // 0'; }

record_reaction() {
  local name="$1" before_bus="$2" before_pulse="$3" before_snapshot="$4"
  local after_bus after_pulse after_snapshot detail
  after_bus=$(bus_count)
  after_pulse=$(pulse_count)
  after_snapshot=$(snapshot_anomaly_count)
  detail="bus:$before_bus->$after_bus pulse:$before_pulse->$after_pulse subconscious.anomaly_count:$before_snapshot->$after_snapshot"
  if [ "$after_bus" -gt "$before_bus" ] && [ "$after_pulse" -gt "$before_pulse" ] && [ "$after_snapshot" -gt "$before_snapshot" ]; then
    record "$name" pass "$detail"
  else
    record "$name" fail "$detail"
  fi
}

initial_bus=$(bus_count)
initial_snapshot=$(snapshot_anomaly_count)

# Absorption 1: p-limit.
before_bus=$(bus_count); before_pulse=$(pulse_count); before_snapshot=$(snapshot_anomaly_count)
installed=$(sz absorb "$CACHE/p-limit" --feature "concurrency limiter" | jq -r '.installed')
[ "$installed" = "concurrency-limiter" ] && record "absorb1: real sz absorb installed concurrency-limiter" pass "$installed" || record "absorb1: real sz absorb installed concurrency-limiter" fail "$installed"
echo "FIXME absorb one reaction" > anomaly-1.md
sz tick --reason post-absorb-1
peak=$(sz bus tail --last 50 --filter limiter.metric | jq -r '.[-1].payload.peak // 99')
[ "$peak" -le 4 ] && record "absorb1: limiter caps at 4" pass "peak=$peak" || record "absorb1: limiter caps at 4" fail "peak=$peak"
record_reaction "absorb1: installed modules react after p-limit" "$before_bus" "$before_pulse" "$before_snapshot"

# Absorption 2: changed-files. Make a commit, fire the event, verify the payload.
before_bus=$(bus_count); before_pulse=$(pulse_count); before_snapshot=$(snapshot_anomaly_count)
installed=$(sz absorb "$CACHE/changed-files" --feature "changed file detector" | jq -r '.installed')
[ "$installed" = "changed-file-detector" ] && record "absorb2: real sz absorb installed changed-file-detector" pass "$installed" || record "absorb2: real sz absorb installed changed-file-detector" fail "$installed"
echo "FIXME absorb two reaction" > anomaly-2.md
git add -A; git commit -qm "baseline before changed-files check" || true
echo x > a.txt; echo y > b.txt; git add a.txt b.txt; git commit -qm "two"
sz bus emit host.commit.made "$(jq -nc --arg sha "$(git rev-parse HEAD)" '{sha:$sha}')"
sz tick --reason post-absorb-2
sleep 1
files=$(sz bus tail --last 50 --filter changed.files | jq -r '.[-1].payload.files | sort | join(",")')
[ "$files" = "a.txt,b.txt" ] && record "absorb2: changed.files exact match" pass "$files" || record "absorb2: changed.files exact match" fail "$files"
record_reaction "absorb2: installed modules react after changed-files" "$before_bus" "$before_pulse" "$before_snapshot"

# Absorption 3: llm-bridge. Ask, expect a response.
before_bus=$(bus_count); before_pulse=$(pulse_count); before_snapshot=$(snapshot_anomaly_count)
installed=$(sz absorb "$CACHE/llm" --feature "llm provider bridge" | jq -r '.installed')
[ "$installed" = "llm-provider-bridge" ] && record "absorb3: real sz absorb installed llm-provider-bridge" pass "$installed" || record "absorb3: real sz absorb installed llm-provider-bridge" fail "$installed"
echo "FIXME absorb three reaction" > anomaly-3.md
sz bus emit ask.llm '{"prompt":"hi"}'
sz tick --reason post-absorb-3
got=$(sz bus tail --last 50 --filter llm.invoked | jq -r '.[-1].payload.text // empty')
[ -n "$got" ] && record "absorb3: llm bridge responds" pass "" || record "absorb3: llm bridge responds" fail ""
record_reaction "absorb3: installed modules react after llm bridge" "$before_bus" "$before_pulse" "$before_snapshot"

registry_modules=$(jq -r '.modules | keys | sort | join(",")' .sz/registry.json)
if [[ ",$registry_modules," == *",concurrency-limiter,"* ]] && [[ ",$registry_modules," == *",changed-file-detector,"* ]] && [[ ",$registry_modules," == *",llm-provider-bridge,"* ]]; then
  record "absorb: registry contains all three absorbed modules" pass "$registry_modules"
else
  record "absorb: registry contains all three absorbed modules" fail "$registry_modules"
fi

# Cross-module reaction: subconscious snapshot exists and reflects increased event volume.
if sz memory get subconscious.snapshot | jq . > /dev/null; then
  final_bus=$(bus_count)
  final_snapshot=$(snapshot_anomaly_count)
  if [ "$final_bus" -gt "$initial_bus" ] && [ "$final_snapshot" -gt "$initial_snapshot" ]; then
    record "cross: subconscious snapshot reflects event-volume increase" pass "bus:$initial_bus->$final_bus anomaly_count:$initial_snapshot->$final_snapshot"
  else
    record "cross: subconscious snapshot reflects event-volume increase" fail "bus:$initial_bus->$final_bus anomaly_count:$initial_snapshot->$final_snapshot"
  fi
else
  record "cross: subconscious snapshot reflects event-volume increase" fail "snapshot not well-formed"
fi

# Reconcile idempotent across all 3 absorptions.
sz reconcile --reason check-1
A=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
sz reconcile --reason check-2
B=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
[ "$A" = "$B" ] && record "absorb: reconcile idempotent" pass "$A" || record "absorb: reconcile idempotent" fail ""

# All required bindings satisfied (no errors).
unsat=$(jq '.unsatisfied | length' .sz/registry.json)
[ "$unsat" = "0" ] && record "absorb: zero unsatisfied" pass "$unsat" || record "absorb: zero unsatisfied" fail "$unsat"

echo "$results" | jq . > "$REPORT"
FAILED=$(jq '[.[] | select(.status=="fail")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 14 FAILED ($FAILED)"; exit 1; }
echo "ABSORB E2E PASSED"

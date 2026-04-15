#!/usr/bin/env bash
set -euo pipefail
REPORT="$PWD/.test-reports/phase-14.json"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

MOD=/Users/avi/Documents/Projects/system0-natural/modules
CACHE="$HOME/.sz/cache/test-fixtures/absorb"
WORK=$(mktemp -d); cd "$WORK"
git init -q; git config user.email "t@t"; git config user.name "t"
echo init > README.md; git add -A; git commit -qm "init"

# Init in adopt-skip mode (just for the test; real users do `sz init`).
sz init --host generic --no-genesis
for m in heartbeat immune subconscious metabolism; do sz install "$m" --source "$MOD/$m"; done

# Use canned mock for absorb.
export SZ_LLM_PROVIDER=mock
export SZ_ABSORB_CANNED=$(realpath /Users/avi/Documents/Projects/system0-natural/tests/e2e/absorb/canned)

absorb_local() {
  local src="$1" feature="$2"
  python3 - <<PY > .draft.json
import json, os, pathlib
src = "$src"
canned = pathlib.Path(os.environ["SZ_ABSORB_CANNED"])
if "p-limit" in src:        f = canned / "p-limit.json"
elif "changed-files" in src: f = canned / "changed-files.json"
elif "/llm" in src:         f = canned / "llm.json"
else: print('{"error":"no_match"}'); raise SystemExit(2)
print(f.read_text())
PY
  module_id=$(jq -r '.module_id' .draft.json)
  staging="$WORK/.staging-$module_id"
  rm -rf "$staging"; mkdir -p "$staging"
  python3 - <<PY
import json, pathlib, shutil, yaml
draft = json.load(open(".draft.json"))
src = pathlib.Path("$src")
target = pathlib.Path("$staging")
manifest = {
  "id": draft["module_id"], "version": "0.1.0",
  "category": draft.get("category","absorbed"),
  "description": draft.get("description",""),
  "entry": draft["entry"], "triggers": draft.get("triggers",[{"on":"tick"}]),
  "provides": draft.get("provides",[]), "requires": draft.get("requires",[]),
  "setpoints": draft.get("setpoints",{}),
  "hooks": {"reconcile":"reconcile.sh"},
}
(target/"module.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
for s in draft.get("files_to_copy",[]):
    src_p = (src / s["from"]).resolve()
    dst_p = (target / s["to"]).resolve()
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    if src_p.exists(): shutil.copy2(src_p, dst_p)
e = target / draft["entry"]["command"]
e.parent.mkdir(parents=True, exist_ok=True)
e.write_text(draft["entry_script"]); e.chmod(0o755)
r = target / "reconcile.sh"
r.write_text(draft["reconcile_script"]); r.chmod(0o755)
PY
  sz install "$module_id" --source "$staging"
}

# Absorption 1: p-limit.
absorb_local "$CACHE/p-limit" "concurrency limiter"
sz tick --reason post-absorb-1
peak=$(sz bus tail --last 50 --filter limiter.metric | jq -r '.[-1].payload.peak // 99')
[ "$peak" -le 4 ] && record "absorb1: limiter caps at 4" pass "peak=$peak" || record "absorb1: limiter caps at 4" fail "peak=$peak"

# Absorption 2: changed-files. Make a commit, fire the event, verify the payload.
absorb_local "$CACHE/changed-files" "changed file detector"
git add -A; git commit -qm "baseline before changed-files check" || true
echo x > a.txt; echo y > b.txt; git add a.txt b.txt; git commit -qm "two"
sz bus emit host.commit.made "$(jq -nc --arg sha "$(git rev-parse HEAD)" '{sha:$sha}')"
sz tick --reason post-absorb-2
sleep 1
files=$(sz bus tail --last 50 --filter changed.files | jq -r '.[-1].payload.files | sort | join(",")')
[ "$files" = "a.txt,b.txt" ] && record "absorb2: changed.files exact match" pass "$files" || record "absorb2: changed.files exact match" fail "$files"

# Absorption 3: llm-bridge. Ask, expect a response.
absorb_local "$CACHE/llm" "llm provider bridge"
sz bus emit ask.llm '{"prompt":"hi"}'
sz tick --reason post-absorb-3
got=$(sz bus tail --last 50 --filter llm.invoked | jq -r '.[-1].payload.text // empty')
[ -n "$got" ] && record "absorb3: llm bridge responds" pass "" || record "absorb3: llm bridge responds" fail ""

# Cross-module reaction: subconscious snapshot exists.
sz memory get subconscious.snapshot | jq . > /dev/null && record "cross: subconscious snapshot well-formed" pass "" || record "cross: subconscious snapshot well-formed" fail ""

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

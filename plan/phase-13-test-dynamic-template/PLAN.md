# Phase 13 — End-to-end Test on a DYNAMIC Template Repo (Adopt Existing Heartbeat)

## Goal

Prove System Zero's promise on Persona B: a repo that already has its own autonomous loop. After `sz init --yes`, S0 must:

1. Detect the existing heartbeat algorithmically.
2. Refuse to install its own heartbeat module (`personas: [static]` excludes it).
3. Install an Adopt-mode adapter that registers `sz tick` as a callback inside the existing loop.
4. Install the recommended modules (no double pulse).
5. Modules talk to each other on the adopted pulse.
6. The repo's own goal continues uninterrupted.

This is the strongest proof that S0 delivers "framework-agnostic standard for self-improvement" on Persona B.

## The dynamic template repo

Name: `s0-test-mini-hermes`. A tiny self-contained "Hermes-style" autonomous repo that we vendor — no external dependency on the real Hermes/OpenClaw codebases. It looks like Hermes to the autodetect, but is actually a 50-line shell loop.

Stated goal (in the README): "Every 5 seconds, append a line to `pulse.log` saying we're alive."

Layout:
```
mini-hermes/
├── README.md
├── pyproject.toml
├── .hermes/
│   └── config.yaml         # the marker file s0 detects
├── bin/
│   └── mini-hermes.sh      # the existing autonomous loop
└── pulse.log               # the goal output
```

`.hermes/config.yaml`:
```yaml
name: mini-hermes
hooks:
  on_tick: []
```

`bin/mini-hermes.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
INTERVAL="${MINI_HERMES_INTERVAL:-5}"
LOGF="${MINI_HERMES_LOG:-pulse.log}"
HOOKS=()
# Read on_tick hooks from .hermes/config.yaml at startup AND after each iteration (so adopt-mode hot-loads).
load_hooks() {
  HOOKS=()
  while IFS= read -r line; do HOOKS+=("$line"); done < <(python3 -c "import yaml,sys; d=yaml.safe_load(open('.hermes/config.yaml')) or {}; [print(x) for x in d.get('hooks',{}).get('on_tick',[]) or []]")
}
while true; do
  echo "$(date -u +%FT%TZ) alive" >> "$LOGF"
  load_hooks
  for h in "${HOOKS[@]:-}"; do
    bash -c "$h" || true
  done
  sleep "$INTERVAL"
done
```

`README.md`:
```markdown
# mini-hermes

A tiny dynamic repo. It already has an autonomous loop in `bin/mini-hermes.sh`. The loop appends a line to `pulse.log` every 5 seconds.

Goal: keep `pulse.log` growing as long as the daemon runs.

If you install System Zero into this repo, it must NOT start a competing daemon. It must adopt this one.
```

## What S0 must achieve on this template

1. `sz init` runs Repo Genesis. Genesis calls `heartbeat_detect.detect()` algorithmically; the result is `existing_heartbeat: "hermes"`.
2. The forced profile (or the LLM, if real) recommends modules excluding `heartbeat`, including `immune`, `subconscious`, `prediction`, and `goal-runner`.
3. The Adopt-mode `hermes` adapter installs cleanly: appends `sz tick --reason hermes` to `.hermes/config.yaml`'s `on_tick` list.
4. Only one daemon is running (`bin/mini-hermes.sh`); S0's own heartbeat is NOT started (`.sz/heartbeat.pid` does not exist).
5. While `bin/mini-hermes.sh` runs, it triggers `sz tick` on every pulse, which in turn fires the installed modules.
6. `pulse.log` continues to grow at the expected rate (the Hermes loop is uninterrupted).
7. Bus shows `tick`, `anomaly.detected` (if planted), `health.snapshot`, `prediction.next`, `goal.executed` events.

## Inputs

- Phases 00–12 complete.

## Outputs

- `tests/templates/mini-hermes/`.
- `tests/e2e/dynamic/run.sh`.
- `tests/e2e/dynamic/test_dynamic_template.py`.
- `.test-reports/phase-13.json`.
- Branch `phase-13-test-dynamic-template`.

## Atomic steps

### Step 13.1 — Branch + dirs

```bash
git checkout main
git checkout -b phase-13-test-dynamic-template
mkdir -p tests/templates/mini-hermes/{.hermes,bin}
mkdir -p tests/e2e/dynamic .test-reports
```

### Step 13.2 — Materialize the template

Write all files described in the layout above. `chmod +x tests/templates/mini-hermes/bin/mini-hermes.sh`.

Verify: launching the daemon manually for 6 seconds appends 1-2 lines to `pulse.log`:
```bash
( cd tests/templates/mini-hermes && bash bin/mini-hermes.sh ) &
PID=$!
sleep 6
kill $PID
wc -l tests/templates/mini-hermes/pulse.log
```

### Step 13.3 — The driver script

`tests/e2e/dynamic/run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPORT="$PWD/.test-reports/phase-13.json"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

WORK=$(mktemp -d)
cp -R tests/templates/mini-hermes "$WORK/repo"
cd "$WORK/repo"
git init -q
git config user.email "t@t" && git config user.name "t"
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
[ -d "$CACHE/changed-files" ] || git clone --depth 1 https://github.com/tj-actions/changed-files "$CACHE/changed-files"

# Run genesis in Adopt mode (default) via the tests/-only canned helper (no SZ_FORCE_* in shipping code).
python3 /Users/avi/Documents/Projects/system0-natural/tests/helpers/run_genesis_with_profile.py --profile "$PROFILE_JSON"

jq -e '.host == "hermes" and .host_mode == "adopt"' .sz.yaml >/dev/null && record "dynamic: host=hermes adopt mode" pass "" || record "dynamic: host=hermes adopt mode" fail ""

# heartbeat must NOT be installed; the others must be.
jq -e '.modules.heartbeat | not' .sz/registry.json >/dev/null && record "dynamic: heartbeat correctly excluded" pass "" || record "dynamic: heartbeat correctly excluded" fail ""

# ≥3 CE modules installed + ≥1 OS absorbed module installed.
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
TICKS=$(sz bus tail --last 200 --filter tick | wc -l | tr -d ' ')
SNAPSHOTS=$(sz bus tail --last 200 --filter "health.snapshot" | wc -l | tr -d ' ')
[ "$TICKS" -ge 3 ] && record "dynamic: ticks via adopted pulse" pass "$TICKS" || record "dynamic: ticks via adopted pulse" fail "$TICKS"
[ "$SNAPSHOTS" -ge 1 ] && record "dynamic: subconscious ran" pass "$SNAPSHOTS" || record "dynamic: subconscious ran" fail "$SNAPSHOTS"

# ---------- MERGE MODE SECOND-PASS ----------
# Re-init the same repo in merge mode; verify both pulses coexist; dedup works.
sz host install hermes --mode merge
jq -e '.host_mode == "merge"' .sz.yaml >/dev/null && record "dynamic: merge mode set" pass "" || record "dynamic: merge mode set" fail ""
# Generic adapter also installed a cron line (heartbeat.pid may not exist because we don't `sz start`;
# instead the cron entry fires sz tick every N min — we validate by forcing two ticks close together).
sz tick --reason merge-test
sz tick --reason merge-test
DEDUPED=$(sz bus tail --last 50 --filter tick | wc -l | tr -d ' ')
# With a 30s default dedup window, the second tick should be swallowed.
[ "$DEDUPED" -le 1 ] && record "dynamic: merge dedup works" pass "$DEDUPED" || record "dynamic: merge dedup works" fail "$DEDUPED"

# Reconcile idempotent after all the dance.
sz reconcile --reason check
A=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
sz reconcile --reason check
B=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
[ "$A" = "$B" ] && record "dynamic: reconcile idempotent" pass "$A" || record "dynamic: reconcile idempotent" fail ""

echo "$results" | jq . > "$REPORT"
FAILED=$(jq '[.[] | select(.status==\"fail\")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 13 FAILED ($FAILED)"; exit 1; }
echo "PHASE 13 PASSED"
```

`chmod +x tests/e2e/dynamic/run.sh`.

### Step 13.4 — Pytest wrapper

`tests/e2e/dynamic/test_dynamic_template.py`:
```python
import os, json, shutil, subprocess, time
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("sz") is None, reason="s0 missing")
def test_dynamic_template_adopts(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(HERE / "tests" / "templates" / "mini-hermes", repo)
    cwd = Path.cwd()
    os.chdir(repo)
    try:
        subprocess.run(["git", "init", "-q"], check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "config", "user.name",  "t"], check=True)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-qm", "init"], check=True)

        env = os.environ.copy()
        env["SZ_LLM_PROVIDER"] = "mock"
        env["SZ_FORCE_GENESIS_PROFILE"] = json.dumps({
            "purpose":"keep pulse.log growing forever",
            "language":"shell",
            "frameworks":["mini-hermes"],
            "existing_heartbeat":"hermes",
            "goals":["append a heartbeat line to pulse.log every interval"],
            "recommended_modules":[
                {"id":"immune","reason":"detect anomalies"},
                {"id":"subconscious","reason":"aggregate health"},
                {"id":"prediction","reason":"predict"},
                {"id":"goal-runner","reason":"verify daemon output"}
            ],
            "risk_flags":[]
        })
        subprocess.run(["sz", "init", "--yes"], env=env, check=True)

        cfg = (repo / ".sz.yaml").read_text()
        assert "host: hermes" in cfg
        assert "host_mode: adopt" in cfg
        assert not (repo / ".sz" / "heartbeat.pid").exists()

        reg = json.loads((repo / ".sz" / "registry.json").read_text())
        assert "heartbeat" not in reg["modules"]
        assert {"immune","subconscious","prediction","goal-runner"}.issubset(set(reg["modules"]))

        # Verify the hermes config patch.
        import yaml
        h = yaml.safe_load((repo / ".hermes" / "config.yaml").read_text())
        assert "sz tick --reason hermes" in (h.get("hooks", {}).get("on_tick") or [])

        # Run the existing daemon briefly; collect bus events.
        proc = subprocess.Popen(["bash", "bin/mini-hermes.sh"])
        time.sleep(20)
        proc.terminate(); proc.wait(timeout=5)

        with open(repo / ".sz" / "bus.jsonl") as f:
            types = [json.loads(line)["type"] for line in f]
        assert types.count("tick") >= 2
        assert types.count("health.snapshot") >= 1
        # The daemon's own goal continued.
        assert (repo / "pulse.log").read_text().count("alive") >= 3
    finally:
        os.chdir(cwd)
```

### Step 13.5 — Run

```bash
bash tests/e2e/dynamic/run.sh
python3 -m pytest tests/e2e/dynamic -q
```

Verify: script ends with `PHASE 13 PASSED`; pytest is green.

### Step 13.6 — Commit

```bash
git add tests/templates/mini-hermes tests/e2e/dynamic .test-reports/phase-13.json plan/phase-13-test-dynamic-template
git commit -m "phase 13: dynamic template repo adopts existing heartbeat end-to-end"
```

## Acceptance criteria

1. Driver script ends with `PHASE 13 PASSED`.
2. Pytest is green.
3. After `sz init`, `host_mode: adopt`, `host: hermes`, NO `.sz/heartbeat.pid` exists.
4. The template's `bin/mini-hermes.sh`'s `pulse.log` continues to grow uninterrupted while S0 modules also fire on the adopted pulse.
5. Reconcile is byte-identical across two consecutive runs.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Hermes loop ignores newly-added hook | `load_hooks` not re-reading config each iteration | the template's `bin/mini-hermes.sh` already calls `load_hooks` per iteration; verify it is in place |
| `pulse.log` stops growing during the test window | S0 errored out and somehow killed the daemon | the daemon is in a different subprocess; check S0 logs at `.sz/heartbeat.log` |
| `heartbeat.pid` appears | S0 init mistakenly started Owned heartbeat | the genesis flow must skip `sz start` when `host_mode == adopt`; verify in `_continue_genesis` |
| Hermes hook patched twice | non-idempotent install | adapter idempotency must be tested in phase 05 |

## Rollback

`git checkout main && git branch -D phase-13-test-dynamic-template`.

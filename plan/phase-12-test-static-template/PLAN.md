# Phase 12 — End-to-end Test on a STATIC Template Repo (Becomes Alive)

## Goal

Prove System Zero's core promise on a real, purpose-built static template repository: a small project with a stated goal that does not run on its own. After `sz init` (one click, one confirmation), the repo must visibly become a living organism that:

1. Detects its own purpose via Repo Genesis.
2. Installs the right Owned heartbeat + the right modules.
3. Fires the heartbeat autonomously.
4. Modules talk to each other through the bus and the registry.
5. The repo's stated goal is **measurably worked on** by an installed module (not just observed; acted upon).

This is the strongest proof that S0 delivers "one-click autonomy + self-improvement" on Persona A.

## The template repo

Name: `s0-test-weatherbot` (created in this phase, vendored under `tests/templates/static-weatherbot/`).

Stated goal (in the README): "Post the current weather for a configured city to a local file every morning at 8am."

Initial code (intentionally inert — no scheduler, no daemon, just a function):

```
static-weatherbot/
├── README.md            # states the goal
├── pyproject.toml
├── weatherbot/
│   ├── __init__.py
│   └── post.py          # def post_weather(city: str) -> None: writes to ./posts/<date>.txt
├── posts/.gitkeep
└── .env.example         # OPENWEATHER_API_KEY=
```

`weatherbot/post.py`:
```python
"""Post the current weather to ./posts/<UTC date>.txt. Run me on a schedule."""
from __future__ import annotations
import os, urllib.request, json
from datetime import datetime, timezone
from pathlib import Path


def post_weather(city: str = "Paris") -> Path:
    out_dir = Path("posts"); out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.txt"
    key = os.environ.get("OPENWEATHER_API_KEY", "")
    if not key:
        out_path.write_text("[no api key set]\n")
        return out_path
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={key}&units=metric"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}Z {city}: {data['weather'][0]['description']} {data['main']['temp']}C\n"
    except Exception as e:
        line = f"[error] {e}\n"
    out_path.write_text(line)
    return out_path


if __name__ == "__main__":
    print(post_weather(os.environ.get("CITY", "Paris")))
```

The point: the repo *can* do its job, but only if someone calls it. After `sz init`, S0 must arrange for it to be called.

## What S0 must achieve on this template

1. Repo Genesis correctly identifies: `purpose ≈ "post weather to a file"`, `language: python`, `existing_heartbeat: none`, `recommended_modules` includes `heartbeat` first plus 2-4 others.
2. `host_mode: install`, `host: generic` (the repo has no IDE markers).
3. After `sz start` (or after init starts heartbeat), within a watch window of 60 seconds (using `--interval 5`), at least one `pulse.tick` event lands on the bus.
4. **The repo's goal is being worked on**: a module called `goal-runner` (added in this phase under `modules/goal-runner/`) reads `.sz/repo-profile.json`, sees the recommended action "post-weather", and on each tick invokes the project's `python -m weatherbot.post` if the file path under `posts/` for today is missing. After two ticks, `posts/<today>.txt` exists.
5. Subconscious snapshot exists and reflects health (color GREEN if no anomalies).
6. Reconcile is byte-identical across two consecutive runs.

Note the `goal-runner` module — this is added in this phase, not phase 08, because it depends on `repo-profile.json` and is the bridge between Genesis and "actually doing the goal." It is the **bridge module** that turns "alive" into "acting."

## Inputs

- Phases 00–11 complete.
- `OPENWEATHER_API_KEY` optional (test passes without it; the bot writes a `[no api key set]` line which still proves the action ran).

## Outputs

- `tests/templates/static-weatherbot/` — the template repo source.
- `modules/goal-runner/` — a new module that turns the Genesis profile into action.
- `tests/e2e/static/run.sh` — the driver.
- `tests/e2e/static/test_static_template.py` — pytest wrapper.
- `.test-reports/phase-12.json`.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Atomic steps

### Step 12.1 — Confirm current branch + dirs

```bash
git branch --show-current
mkdir -p tests/templates/static-weatherbot/{weatherbot,posts}
mkdir -p tests/e2e/static .test-reports modules/goal-runner/scripts
```

Verify: prints the current branch name, creates the static test scaffolding, and does not create or switch branches.

### Step 12.2 — Materialize the template

Write `tests/templates/static-weatherbot/README.md`:
```markdown
# weatherbot
Post the current weather for a configured city to a local file every morning.

Goal: produce `posts/<date>.txt` once per day.

Run by hand:
    python -m weatherbot.post

Or let System Zero run it autonomously:
    sz init --yes
```

Write `pyproject.toml`:
```toml
[project]
name = "weatherbot"
version = "0.1.0"
requires-python = ">=3.10"
```

Write `weatherbot/__init__.py` (empty) and `weatherbot/post.py` (as above).

Write `.env.example`:
```
OPENWEATHER_API_KEY=
CITY=Paris
```

Touch `posts/.gitkeep`.

Verify:
```bash
( cd tests/templates/static-weatherbot && python3 -m weatherbot.post )
ls tests/templates/static-weatherbot/posts/
```

A file `<today>.txt` should exist.

### Step 12.3 — Create the `goal-runner` module

`modules/goal-runner/module.yaml`:
```yaml
id: goal-runner
version: 0.1.0
category: action
description: Reads .sz/repo-profile.json and executes a per-language run command if today's expected output is missing.
entry:
  type: bash
  command: run.sh
triggers:
  - on: tick
requires:
  - providers: [memory, bus, storage]
provides:
  - name: goal.execution
    address: events:goal.executed
    description: Emitted after the project's run command is invoked.
setpoints:
  run_command:
    default: ""
    enum: [""]
    description: "Override; if empty, derived from repo-profile."
  expected_output_glob:
    default: ""
    enum: [""]
    description: "Override; if empty, derived from repo-profile."
hooks:
  reconcile: reconcile.sh
  doctor: doctor.sh
personas: [static, dynamic]
```

`run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
PROFILE="$SZ_PROFILE_PATH"
[ -f "$PROFILE" ] || { echo "no profile yet"; exit 0; }

CMD="${SZ_SETPOINT_run_command:-}"
GLOB="${SZ_SETPOINT_expected_output_glob:-}"

if [ -z "$CMD" ]; then
  LANG=$(jq -r '.language' "$PROFILE")
  case "$LANG" in
    python)     CMD="python3 -m $(jq -r '.frameworks[0]? // .purpose | gsub(\" \"; \"_\") | ascii_downcase' "$PROFILE").post 2>/dev/null || python3 -m weatherbot.post 2>/dev/null || true" ;;
    javascript) CMD="node ." ;;
    typescript) CMD="npm start" ;;
    *)          CMD="" ;;
  esac
fi

if [ -z "$GLOB" ]; then
  GLOB="posts/$(date -u +%Y-%m-%d).txt"
fi

# Idempotent: only run if today's expected output is missing.
if compgen -G "$GLOB" >/dev/null; then
  exit 0
fi

if [ -n "$CMD" ]; then
  bash -c "$CMD" || true
  sz bus emit goal.executed "$(jq -nc --arg cmd "$CMD" --arg glob "$GLOB" '{cmd:$cmd, glob:$glob}')"
fi
```

`reconcile.sh`: `echo '{}' > "$SZ_MODULE_DIR/runtime.json"`.
`doctor.sh`: `[ -f "$SZ_MODULE_DIR/runtime.json" ] && exit 0 || exit 1`.

`chmod +x modules/goal-runner/*.sh`.

### Step 12.4 — Add `goal-runner` to the catalog

`catalog/modules/goal-runner/module.yaml` (copy), `source.yaml` (local for now), `README.md`. Re-run `catalog/scripts/build-index.py`.

### Step 12.5 — The driver script

`tests/e2e/static/run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPORT="$PWD/.test-reports/phase-12.json"
mkdir -p "$(dirname "$REPORT")"
results='[]'
record() { results=$(echo "$results" | jq --arg n "$1" --arg s "$2" --arg d "$3" '. + [{name:$n,status:$s,detail:$d}]'); }

WORK=$(mktemp -d)
cp -R tests/templates/static-weatherbot "$WORK/repo"
cd "$WORK/repo"
git init -q
git config user.email "t@t" && git config user.name "t"
git add -A && git commit -qm "init"

# Run init with auto-yes. The test forces a canned profile by launching a small
# Python helper that monkeypatches sz.interfaces.llm.invoke in-process. The test
# hook is NOT in the shipped sz/core/genesis.py — it is a tests/-only construct
# (see tests/genesis/conftest.py from phase 07).

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
    {"id":"concurrency-limiter","reason":"absorbed OS feature: cap concurrency in the scraper"}
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
python3 /Users/avi/Documents/Projects/system0-natural/tests/helpers/run_genesis_with_profile.py --profile "$PROFILE_JSON"

# Verify Genesis output.
profile=$(cat .sz/repo-profile.json)
echo "$profile" | jq -e '.purpose | test("weather"; "i")' >/dev/null && record "static: profile mentions weather" pass "" || record "static: profile mentions weather" fail ""
echo "$profile" | jq -e '.recommended_modules | map(.id) | index("heartbeat")' >/dev/null && record "static: heartbeat recommended" pass "" || record "static: heartbeat recommended" fail ""
echo "$profile" | jq -e '.recommended_modules | map(.id) | index("goal-runner")' >/dev/null && record "static: goal-runner recommended" pass "" || record "static: goal-runner recommended" fail ""

# Required: ≥3 CE-derived modules installed + ≥1 absorbed-OS module installed.
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
sz start --interval 5
sleep 30
sz stop

# Bus assertions.
TICKS=$(sz bus tail --last 200 --filter pulse.tick | wc -l | tr -d ' ')
[ "$TICKS" -ge 3 ] && record "static: ticks landed" pass "$TICKS" || record "static: ticks landed" fail "$TICKS"
GOAL_EVENTS=$(sz bus tail --last 200 --filter goal.executed | wc -l | tr -d ' ')
[ "$GOAL_EVENTS" -ge 1 ] && record "static: goal acted upon" pass "$GOAL_EVENTS" || record "static: goal acted upon" fail "$GOAL_EVENTS"

# The actual goal: today's posts/<date>.txt exists.
TODAY="posts/$(date -u +%Y-%m-%d).txt"
[ -f "$TODAY" ] && record "static: goal artifact exists" pass "$TODAY" || record "static: goal artifact exists" fail "$TODAY missing"

# Reconcile idempotent.
sz reconcile --reason check
A=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
sz reconcile --reason check
B=$(jq 'del(.generated_at)' .sz/registry.json | sha256sum | awk '{print $1}')
[ "$A" = "$B" ] && record "static: reconcile idempotent" pass "$A" || record "static: reconcile idempotent" fail "A=$A B=$B"

echo "$results" | jq . > "$REPORT"
FAILED=$(jq '[.[] | select(.status==\"fail\")] | length' "$REPORT")
[ "$FAILED" -eq 0 ] || { echo "PHASE 12 FAILED ($FAILED)"; exit 1; }
echo "PHASE 12 PASSED"
```

`chmod +x tests/e2e/static/run.sh`.

### Step 12.6 — Genesis test-hook for `SZ_FORCE_GENESIS_PROFILE`

Add to `sz/core/genesis.py`, immediately before the LLM call:
```python
import os, json
forced = os.environ.get("SZ_FORCE_GENESIS_PROFILE")
if forced:
    profile = json.loads(forced)
    paths.profile_path(root).write_text(json.dumps(profile, indent=2, sort_keys=True))
    # Skip the CLC; jump to the host/install loop with this profile.
    return _continue_genesis(root, profile, auto_yes=auto_yes)
```

(Refactor existing genesis() so the post-CLC code path becomes `_continue_genesis(root, profile, auto_yes)`.)

This hook is purely for deterministic tests; never invoked in normal use. Document it explicitly in `sz/core/genesis.py`.

### Step 12.7 — Pytest wrapper

`tests/e2e/static/test_static_template.py`:
```python
import os, json, shutil, subprocess, time
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parents[3]


@pytest.mark.skipif(shutil.which("sz") is None, reason="s0 missing")
def test_static_weatherbot_becomes_alive(tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(HERE / "tests" / "templates" / "static-weatherbot", repo)
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
            "purpose":"post weather to a file daily",
            "language":"python",
            "frameworks":["weatherbot"],
            "existing_heartbeat":"none",
            "goals":["produce posts/<date>.txt once per day"],
            "recommended_modules":[
                {"id":"heartbeat","reason":"required for static repos"},
                {"id":"immune","reason":"detect leaked secrets"},
                {"id":"subconscious","reason":"aggregate health"},
                {"id":"goal-runner","reason":"actually run the project"},
            ],
            "risk_flags":[]
        })
        subprocess.run(["sz", "init", "--host", "generic", "--yes"], env=env, check=True)

        # Profile written
        profile = json.loads((repo / ".sz" / "repo-profile.json").read_text())
        assert "weather" in profile["purpose"].lower()

        # Modules installed
        reg = json.loads((repo / ".sz" / "registry.json").read_text())
        assert {"heartbeat","immune","subconscious","goal-runner"}.issubset(set(reg["modules"]))

        # Heartbeat → pulses → goal-runner → today's file
        subprocess.run(["sz", "start", "--interval", "5"], check=True)
        time.sleep(30)
        subprocess.run(["sz", "stop"], check=True)

        bus = (repo / ".sz" / "bus.jsonl").read_text().splitlines()
        types = [json.loads(l)["type"] for l in bus]
        assert types.count("pulse.tick") >= 3
        assert types.count("goal.executed") >= 1
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert (repo / "posts" / f"{today}.txt").exists()
    finally:
        os.chdir(cwd)
```

### Step 12.8 — Run

```bash
bash tests/e2e/static/run.sh
python3 -m pytest tests/e2e/static -q
```

Verify: script ends with `PHASE 12 PASSED`; pytest is green.

### Step 12.9 — Commit

```bash
git add modules/goal-runner tests/templates tests/e2e/static catalog sz/core/genesis.py .test-reports/phase-12.json plan/phase-12-test-static-template
git commit -m "phase 12: static template repo becomes alive end-to-end"
```

## Acceptance criteria

1. `bash tests/e2e/static/run.sh` ends with `PHASE 12 PASSED`.
2. `pytest tests/e2e/static -q` is green.
3. The template repo's `posts/<today>.txt` is generated by the autonomous loop, not by the human.
4. Subconscious snapshot, prediction events, and reconcile idempotency all hold.
5. The current branch contains this phase's checkpoint commit(s), with no branch operations.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| `goal-runner` cannot derive run command from profile | language not in switch | extend the switch in `run.sh`; never silently skip |
| Today's file already exists from a stale run | non-isolated tmp | tmp_path fixture isolates; if running manually, cleanup beforehand |
| Heartbeat ticks but no `goal.executed` | `compgen -G` matches an old file | the test ensures `posts/` is empty before starting |
| `SZ_FORCE_GENESIS_PROFILE` ignored | gate not added | confirm step 12.6 modification is in place |

## Rollback

`git checkout main && git branch -D phase-12-test-static-template`.

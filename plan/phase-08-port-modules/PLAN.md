# Phase 08 — Port the First Self-Improvement Modules

## Goal

Take seven self-improvement modules already implemented (in concept or code) inside connection-engine and re-shape them as S0-conformant modules. After this phase, all seven live under `modules/` in this repo, validate against the spec, install on any S0-equipped repo, demonstrate cross-module wiring through the standard reconcile cycle, and work in both Static and Dynamic personas.

## The seven modules

1. **heartbeat** — periodic pulse marker. Static-only (Dynamic repos use the adopted heartbeat).
2. **immune** — passive anomaly detector.
3. **subconscious** — RED/AMBER/GREEN health snapshots.
4. **dreaming** — generates novel hypotheses (uses LLM).
5. **metabolism** — rotates `bus.jsonl`.
6. **endocrine** — modulates other modules' setpoints based on aggregate health.
7. **prediction** — predicts the next likely event from recent bus history (no LLM, frequency-based).

These seven cover every interface, every trigger type, both personas, and at least one CLC consumer.

## Inputs

- Phases 00–07 complete.
- `/Users/avi/Documents/Misc/connection-engine/` exists locally.

## Outputs

- `modules/{heartbeat,immune,subconscious,dreaming,metabolism,endocrine,prediction}/`.
- Each contains `module.yaml`, entry, `reconcile.sh`, `doctor.sh`, plus vendored scripts.
- `tests/modules/test_install_all.py`, `test_personas.py`.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Porting recipe (apply to every module)

1. Locate the original code in connection-engine.
2. Create `modules/<id>/`.
3. Write `module.yaml` declaring id, version `0.1.0`, category, description, entry, triggers, provides, requires, setpoints, hooks, `personas`.
4. Copy minimum source files into `modules/<id>/scripts/`. Strip `core.system.scripts.*` imports; replace with `sz` CLI calls.
5. Write `entry` — small, wraps the vendored script, uses S0-injected env vars (`S0_*`).
6. Write `reconcile.sh` — for modules with no requires, body is `:`. For modules with requires, resolve capabilities and write `runtime.json`.
7. Write `doctor.sh` — returns 0 if state files are intact.
8. Test in tmp repo: `sz install <id> --source modules/<id>` succeeds; `sz tick` does not error; `sz doctor <id>` returns 0.

## Atomic steps

### Step 8.1 — Confirm current branch + folders

```bash
git branch --show-current
mkdir -p modules/{heartbeat,immune,subconscious,dreaming,metabolism,endocrine,prediction}/scripts
mkdir -p tests/modules
```

Verify: prints the current branch name, creates the module folders, and does not create or switch branches.

### Step 8.2 — heartbeat

`modules/heartbeat/module.yaml`:
```yaml
id: heartbeat
version: 0.1.0
category: physiology
description: Periodic pulse marker. The minimum living signal.
entry:
  type: bash
  command: pulse.sh
triggers:
  - on: tick
provides:
  - name: pulse
    address: events:pulse.tick
    description: Emitted on every heartbeat tick.
setpoints:
  log_state:
    default: true
    enum: [true, false]
    description: Whether to log to memory.
hooks:
  doctor: doctor.sh
personas: [static]
```

`pulse.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
sz bus emit pulse.tick "$(jq -nc --arg ts "$(date -u +%FT%TZ)" '{ts:$ts}')"
sz memory set heartbeat.last "$(date -u +%FT%TZ)"
```

`doctor.sh`:
```bash
#!/usr/bin/env bash
last=$(sz memory get heartbeat.last 2>/dev/null || echo "")
echo "last=$last"
exit 0
```

### Step 8.3 — immune

`modules/immune/module.yaml`:
```yaml
id: immune
version: 0.1.0
category: physiology
description: Passive anomaly detector.
entry:
  type: python
  command: scan.py
triggers:
  - on: tick
  - on: event
    match: "host.commit.made"
provides:
  - name: anomaly.detection
    address: events:anomaly.detected
    description: Anomaly events with severity and location.
setpoints:
  severity_threshold:
    default: medium
    enum: [low, medium, high]
    description: Minimum severity to emit.
hooks:
  reconcile: reconcile.sh
  doctor: doctor.sh
personas: [static, dynamic]
```

`scan.py`: regex-based scanner over the repo's source files (`.py`, `.js`, `.ts`, `.sh`, `.yaml`, `.yml`, `.md`, `.env`). Patterns: hardcoded password, AWS key, TODO/FIXME. Uses `subprocess.run(["sz", "bus", "emit", "anomaly.detected", payload])`. Reads `SZ_REPO_ROOT`, `SZ_SETPOINT_severity_threshold`. Stops at one finding per file.

`reconcile.sh`: `echo '{}' > "$SZ_MODULE_DIR/runtime.json"`.
`doctor.sh`: `[ -f "$SZ_MODULE_DIR/runtime.json" ] && exit 0 || exit 1`.

### Step 8.4 — subconscious

`module.yaml`:
```yaml
id: subconscious
version: 0.1.0
category: cognition
description: Aggregates anomalies into colored health snapshots.
entry:
  type: python
  command: evaluate.py
triggers:
  - on: tick
  - on: event
    match: "anomaly.*"
requires:
  - name: anomaly.detection
    optional: false
    on_missing: warn
  - providers: [memory, bus]
provides:
  - name: health.snapshot
    address: memory:subconscious.snapshot
    description: Latest health snapshot.
setpoints:
  red_threshold:    {default: 5, range: [1, 100], description: "Anomaly count to go RED."}
  amber_threshold:  {default: 2, range: [1, 50],  description: "Anomaly count to go AMBER."}
hooks:
  reconcile: reconcile.sh
  doctor: doctor.sh
personas: [static, dynamic]
```

`evaluate.py`: subscribes to `anomaly.*`, increments running count in memory, emits `health.snapshot` with color (GREEN/AMBER/RED), writes JSON to memory key `subconscious.snapshot`. Uses `sz bus subscribe`, `sz memory get/set`, `sz bus emit`.

`reconcile.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
addr=$(sz discovery resolve anomaly.detection 2>/dev/null || echo "none")
jq -nc --arg addr "$addr" '{anomaly_detection_address: $addr}' > "$SZ_MODULE_DIR/runtime.json"
```

### Step 8.5 — dreaming

`module.yaml`:
```yaml
id: dreaming
version: 0.1.0
category: cognition
description: Generates novel hypotheses from accumulated bus history during quiet periods.
entry:
  type: bash
  command: dream.sh
triggers:
  - cron: "0 3 * * *"
requires:
  - providers: [llm, memory, bus]
provides:
  - name: hypothesis
    address: events:hypothesis.generated
    description: A drafted hypothesis with a novelty score.
setpoints:
  novelty_threshold: {default: 0.7, range: [0.0, 1.0], description: "Min novelty to emit."}
  max_history_lines: {default: 50,  range: [10, 500],  description: "Bus lines to consider."}
hooks:
  reconcile: reconcile.sh
  doctor: doctor.sh
personas: [static, dynamic]
```

`dream.sh`: assembles a prompt from `sz bus tail --last $N`, calls `sz llm invoke`, emits `hypothesis.generated` with the response text.

### Step 8.6 — metabolism

`module.yaml`:
```yaml
id: metabolism
version: 0.1.0
category: physiology
description: Rotates the bus log; archives older files.
entry:
  type: bash
  command: compact.sh
triggers:
  - cron: "30 4 * * 0"
  - on: tick
requires:
  - providers: [bus, memory, storage]
setpoints:
  rotate_after_days: {default: 14, range: [1, 365],  description: "Rotate when older than N days."}
  rotate_after_mb:   {default: 50, range: [1, 1024], description: "Rotate when larger than N MB."}
hooks:
  doctor: doctor.sh
personas: [static, dynamic]
```

`compact.sh`: rotates by mtime AND size (whichever fires first); writes archive to `.sz/archive/`; updates `metabolism.last` in memory.

### Step 8.7 — endocrine (NEW)

`module.yaml`:
```yaml
id: endocrine
version: 0.1.0
category: physiology
description: Modulates other modules' setpoints based on aggregate health snapshots.
entry:
  type: python
  command: regulate.py
triggers:
  - on: event
    match: "health.snapshot"
requires:
  - name: health.snapshot
    optional: false
    on_missing: warn
hooks:
  reconcile: reconcile.sh
  doctor: doctor.sh
personas: [static, dynamic]
```

`regulate.py`: subscribes to `health.snapshot`. RED → lower `immune.severity_threshold` to `low`. N consecutive GREEN → raise to `high`. Calls `sz setpoint set immune severity_threshold <value>` (this helper is added to phase 03 by amendment if not present).

### Step 8.8 — prediction (NEW)

`module.yaml`:
```yaml
id: prediction
version: 0.1.0
category: cognition
description: Predicts the next likely event type from recent bus history.
entry:
  type: python
  command: predict.py
triggers:
  - on: tick
provides:
  - name: prediction.next
    address: events:prediction.next
    description: Top-K predicted next event types.
setpoints:
  history_window: {default: 200, range: [10, 5000], description: "Recent bus events to consider."}
  top_k:          {default: 3,   range: [1, 20],    description: "Predictions to return."}
hooks:
  doctor: doctor.sh
personas: [static, dynamic]
```

`predict.py`: pure Python, reads recent bus, builds Markov-1 frequency table over event types, emits top-K next types as a JSON list.

### Step 8.9 — Make every script executable

```bash
chmod +x modules/*/*.sh modules/*/*.py
```

### Step 8.10 — Validate every manifest

```bash
for d in modules/*; do
  tools/validate-spec.py spec/v0.1.0/manifest.schema.json "$d/module.yaml"
done
```

Verify: every line prints `OK`.

### Step 8.11 — Tests

`tests/modules/test_install_all.py`: install all seven into a tmp repo (with `sz init --no-genesis`). Assert registry contains all seven. Assert binding `subconscious.anomaly.detection -> immune` exists. Assert binding `endocrine.health.snapshot -> subconscious` exists.

`tests/modules/test_tick_runs.py`: install heartbeat + immune + subconscious + endocrine + prediction; plant `password = "x"` in a `.py` file; run `sz tick` twice; assert bus contains `pulse.tick`, `anomaly.detected`, `health.snapshot`, `prediction.next`.

`tests/modules/test_personas.py`:
- Static fixture: heartbeat installs OK.
- Dynamic fixture (planted `.hermes/config.yaml`): heartbeat install rejected by personas check; the other six install OK; tick still produces `health.snapshot` via the adopted pulse (simulated by manually firing `sz tick` since Hermes is not actually running).

Run:
```bash
python3 -m pytest tests/modules -q
```

Verify: all tests pass.

### Step 8.12 — Manual smoke

```bash
TMP=$(mktemp -d); cd "$TMP"
git init -q
sz init --host generic --no-genesis
for m in heartbeat immune subconscious dreaming metabolism endocrine prediction; do
  sz install "$m" --source /Users/avi/Documents/Projects/system0-natural/modules/$m
done
echo 'password = "hardcoded"' > leak.py
git add -A && git commit -qm "leak"
sz tick --reason demo
sz tick --reason demo
sz bus tail --last 60
sz memory get subconscious.snapshot
sz bus tail --last 30 --filter "prediction.next"
```

Verify: subconscious snapshot color is AMBER or RED; `prediction.next` shows real frequencies; bus shows endocrine adjusting immune setpoint.

### Step 8.13 — Commit

```bash
git add modules tests/modules plan/phase-08-port-modules
git commit -m "phase 08: seven self-improvement modules ported"
```

## Acceptance criteria

1. All seven manifests validate.
2. `sz install` works for each in any order.
3. Registry shows expected bindings (subconscious→immune; endocrine→subconscious).
4. `sz tick` produces `pulse.tick`, `anomaly.detected`, `health.snapshot`, `prediction.next`.
5. heartbeat is rejected in Dynamic persona; the other six install fine.
6. `pytest tests/modules -q` passes.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| `jq` missing | not installed | `brew install jq` / `apt-get install jq` |
| Endocrine cannot edit setpoints | `sz setpoint set` not implemented | add helper command in phase 03 amendment |
| Predictor surfaces only `tick` | window too small | raise `history_window` setpoint |
| Dreaming hits real LLM in tests | mock not pinned | tests must `monkeypatch` the mock provider |

## Rollback

`git checkout main && git branch -D phase-08-port-modules`.

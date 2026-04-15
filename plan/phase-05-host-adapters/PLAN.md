# Phase 05 — Host Adapters + Adopt Mode

## Goal

S0 must work inside any developer environment. This phase ships nine concrete adapters across two modes:

**Install mode** (S0 owns the heartbeat):
- `generic` — git + cron, works anywhere.
- `claude_code` — hooks into Claude Code session events.
- `cursor` — `.cursorrules` + edit watcher.
- `opencode` — hooks into OpenCode session events.
- `aider` — git post-commit + cron tuned for Aider's workflow.

**Adopt mode** (an existing scheduler in the host already pulses; S0 subscribes):
- `hermes` — hooks into Hermes scheduler.
- `openclaw` — hooks into OpenClaw autonomous loop.
- `metaclaw` — hooks into MetaClaw loop.
- `connection_engine` — adopts circadian-daemon.

Adopt-mode adapters are tiny and almost identical: each detects a known marker (file, env var, or running process), registers a callback or hook, and writes `host_mode: adopt` into `.sz.yaml`. The user's existing daemon then calls `sz tick` on its own pulse. There is exactly one heartbeat in the system at any time.

## Inputs

- Phases 00–04 complete.

## Outputs

- `sz/adapters/<name>/{install.sh,uninstall.sh,manifest.yaml,detect.sh}` for each of the nine adapters.
- `sz/adapters/registry.py` — picks adapter by name, applies install/uninstall, calls detect.
- `sz/commands/init.py` — extended to invoke the adapter's install hook.
- `sz/commands/host.py` — `host install <name>`, `host uninstall`, `host list`, `host current`, `host detect`.
- Tests for each adapter, with explicit Install vs Adopt tests.
- Current-branch git checkpoint history for this phase, with no branch operations.

## Atomic steps

### Step 5.1 — Confirm current branch and stay on it

```bash
git branch --show-current
```

Verify: prints the current branch name; do not create, switch, rename, or delete any branch during this phase.


### Step 5.2 — Adapter directory layout

```bash
for n in generic claude_code cursor opencode aider hermes openclaw metaclaw connection_engine; do
  mkdir -p "sz/adapters/$n"
done
mkdir -p tests/adapters
```

### Step 5.3 — `generic` adapter (Install mode)

`sz/adapters/generic/manifest.yaml`:
```yaml
id: generic
mode: install
provides: [clock_only, commit_events]
description: Works anywhere. Uses git post-commit hook + a user-level cron entry.
```

`sz/adapters/generic/install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
HOOK="$REPO_ROOT/.git/hooks/post-commit"
MARKER_BEGIN="# >>> sz-generic >>>"
MARKER_END="# <<< sz-generic <<<"

if [ -d "$REPO_ROOT/.git" ]; then
  mkdir -p "$REPO_ROOT/.git/hooks"
  if [ -f "$HOOK" ] && grep -q "$MARKER_BEGIN" "$HOOK"; then
    :
  else
    {
      [ -f "$HOOK" ] && cat "$HOOK"
      echo ""
      echo "$MARKER_BEGIN"
      echo "sz bus emit host.commit.made \"\$(jq -nc --arg sha \"\$(git rev-parse HEAD)\" '{sha:\$sha}')\"  || true"
      echo "$MARKER_END"
    } > "$HOOK.tmp"
    mv "$HOOK.tmp" "$HOOK"
    chmod +x "$HOOK"
  fi
fi

CRON_LINE="*/5 * * * *  cd '$REPO_ROOT' && sz tick --reason cron >> '$REPO_ROOT/.sz/heartbeat.log' 2>&1"
TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null > "$TMP_CRON" || : > "$TMP_CRON"
if grep -Fq "sz tick --reason cron" "$TMP_CRON"; then
  :
else
  echo "$CRON_LINE" >> "$TMP_CRON"
  crontab "$TMP_CRON" 2>/dev/null || echo "warning: crontab install failed; sz tick must be invoked manually."
fi
rm -f "$TMP_CRON"
echo "generic adapter installed (Install mode)"
```

`sz/adapters/generic/uninstall.sh`: reverse of install (strip marker block, drop cron line). Same pattern as sz.

`sz/adapters/generic/detect.sh`:
```bash
#!/usr/bin/env bash
# Always available; this is the fallback.
echo "generic"
exit 0
```

### Step 5.4 — `claude_code` adapter (Install mode)

`manifest.yaml`:
```yaml
id: claude_code
mode: install
provides: [clock_only, commit_events, session_lifecycle, command_palette]
description: Hooks into Claude Code's UserPromptSubmit and Stop events.
```

`install.sh`: drops `.claude/hooks/sz-on-prompt.sh` (emits `host.session.started`), `.claude/hooks/sz-on-stop.sh` (emits `host.session.ended` + calls `sz tick`), and patches `.claude/settings.json` to register them. Then chains `bash $(dirname "$0")/../generic/install.sh` for cron + post-commit.

`uninstall.sh`: removes the hook files, scrubs `.claude/settings.json` of any entries containing `sz-on-`, then chains `generic/uninstall.sh`.

`detect.sh`:
```bash
#!/usr/bin/env bash
[ -d "${SZ_REPO_ROOT:-$(pwd)}/.claude" ] && echo "claude_code" || exit 1
```

### Step 5.5 — `cursor` adapter (Install mode)

`manifest.yaml`:
```yaml
id: cursor
mode: install
provides: [clock_only, commit_events, edit_events, command_palette]
description: Drops a .cursorrules snippet and chains generic.
```

`install.sh`: appends marker block to `.cursorrules` containing the line `When you finish a coherent change, run: sz tick --reason cursor`; then chains generic.

`uninstall.sh`: removes the marker block; chains generic uninstall.

`detect.sh`:
```bash
#!/usr/bin/env bash
[ -f "${SZ_REPO_ROOT:-$(pwd)}/.cursorrules" ] || [ -d "${SZ_REPO_ROOT:-$(pwd)}/.cursor" ] && echo "cursor" || exit 1
```

### Step 5.6 — `opencode` adapter (Install mode)

`manifest.yaml`:
```yaml
id: opencode
mode: install
provides: [clock_only, commit_events, session_lifecycle]
description: Hooks into OpenCode events.
```

`install.sh`: writes `.opencode/hooks/sz-session-end.sh` (emits `host.session.ended` + calls `sz tick`); chains generic.

`uninstall.sh`: removes the hook; chains generic.

`detect.sh`:
```bash
#!/usr/bin/env bash
[ -d "${SZ_REPO_ROOT:-$(pwd)}/.opencode" ] && echo "opencode" || exit 1
```

### Step 5.7 — `aider` adapter (Install mode)

`manifest.yaml`:
```yaml
id: aider
mode: install
provides: [clock_only, commit_events, session_lifecycle]
description: Aider creates frequent commits; we hook post-commit to fire ticks.
```

`install.sh`: chains generic; additionally writes `.aider.sz.sh` that Aider's `--auto-commits` picks up (Aider users source it manually).

`detect.sh`:
```bash
#!/usr/bin/env bash
[ -f "${SZ_REPO_ROOT:-$(pwd)}/.aider.conf.yml" ] && echo "aider" || exit 1
```

### Step 5.8 — `hermes` adapter (Adopt mode)

`sz/adapters/hermes/manifest.yaml`:
```yaml
id: hermes
mode: adopt
provides: [external_heartbeat, session_lifecycle]
description: Adopts Hermes' existing scheduler; does not install a second daemon.
```

`sz/adapters/hermes/install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
# Hermes config conventionally at .hermes/config.yaml
HCONF="$REPO_ROOT/.hermes/config.yaml"
[ -f "$HCONF" ] || { echo "no .hermes/config.yaml; cannot adopt"; exit 2; }

# Idempotent: add s0-tick to Hermes hooks if not present.
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("$HCONF")
data = yaml.safe_load(p.read_text()) or {}
hooks = data.setdefault("hooks", {})
on_tick = hooks.setdefault("on_tick", [])
cmd = "sz tick --reason hermes"
if cmd not in on_tick:
    on_tick.append(cmd)
p.write_text(yaml.safe_dump(data, sort_keys=False))
PY

# Mark the sz config as adopt mode.
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("$REPO_ROOT/.sz.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
cfg["host"] = "hermes"
cfg["host_mode"] = "adopt"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY

echo "hermes adapter installed (Adopt mode) — Hermes will now call sz tick on each pulse."
```

`sz/adapters/hermes/uninstall.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
HCONF="$REPO_ROOT/.hermes/config.yaml"
[ -f "$HCONF" ] || { echo "no .hermes/config.yaml; nothing to remove"; exit 0; }
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("$HCONF")
data = yaml.safe_load(p.read_text()) or {}
hooks = data.get("hooks", {})
on_tick = [c for c in hooks.get("on_tick", []) if c != "sz tick --reason hermes"]
hooks["on_tick"] = on_tick
data["hooks"] = hooks
p.write_text(yaml.safe_dump(data, sort_keys=False))
PY
echo "hermes adapter uninstalled"
```

`sz/adapters/hermes/detect.sh`:
```bash
#!/usr/bin/env bash
[ -f "${SZ_REPO_ROOT:-$(pwd)}/.hermes/config.yaml" ] && echo "hermes" || exit 1
```

### Step 5.9 — `openclaw`, `metaclaw` adapters (Adopt mode)

Identical pattern to `hermes`, with adapter-specific config paths and hook keys. Each:

- Detects via a marker file (`.openclaw/`, `.metaclaw/`).
- Adds `sz tick --reason <name>` to that framework's tick-hook list.
- Sets `.sz.yaml.host_mode: adopt`.
- Idempotent install + clean uninstall.

`detect.sh` files check the marker directory.

### Step 5.10 — `connection_engine` adapter (Adopt mode)

`manifest.yaml`:
```yaml
id: connection_engine
mode: adopt
provides: [external_heartbeat, session_lifecycle]
description: Adopts connection-engine's circadian-daemon as the heartbeat source.
```

`install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
# connection-engine's maintenance registry is YAML; add a task that calls sz tick.
REG="$REPO_ROOT/core/system/maintenance-registry.yaml"
[ -f "$REG" ] || { echo "no maintenance-registry.yaml; cannot adopt"; exit 2; }
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("$REG")
data = yaml.safe_load(p.read_text()) or {}
tasks = data.setdefault("tasks", {})
key = "sz--tick"
if key not in tasks:
    tasks[key] = {
        "frequency": "5m",
        "command": "sz tick --reason connection_engine",
        "outcome_file": "core/system/data/outcomes/s0-tick.json",
    }
    p.write_text(yaml.safe_dump(data, sort_keys=False))
PY
python3 - <<PY
import yaml, pathlib
p = pathlib.Path("$REPO_ROOT/.sz.yaml")
cfg = yaml.safe_load(p.read_text()) or {}
cfg["host"] = "connection_engine"
cfg["host_mode"] = "adopt"
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
echo "connection_engine adapter installed (Adopt mode)"
```

`uninstall.sh`: reverse — pop `sz--tick` from tasks.
`detect.sh`: `[ -d "${SZ_REPO_ROOT:-$(pwd)}/core/system" ] && [ -f "${SZ_REPO_ROOT:-$(pwd)}/core/system/maintenance-registry.yaml" ] && echo "connection_engine" || exit 1`.

### Step 5.10b — Generic heartbeat detection for unknown frameworks

Some repos have an autonomous loop that does not match any registered framework. SZ must still detect it and still offer all three modes.

Add `sz/adapters/unknown/manifest.yaml`:
```yaml
id: unknown
mode: adopt
provides: [external_heartbeat]
description: Detected a heartbeat-like marker but the framework is not recognized. User picks the mode.
```

`sz/adapters/unknown/detect.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${SZ_REPO_ROOT:-$(pwd)}"
found=""
# Heuristic 1: any YAML with `on_tick` key.
if command -v grep >/dev/null && grep -lr --include='*.yaml' --include='*.yml' -E '^\s*on_tick:\s*' "$REPO_ROOT" 2>/dev/null | head -n1 | grep -q .; then
  found="yaml-on_tick"
fi
# Heuristic 2: any crontab entry referencing this repo.
if [ -z "$found" ] && crontab -l 2>/dev/null | grep -Fq "$REPO_ROOT"; then
  found="cron-in-this-repo"
fi
# Heuristic 3: any launchd plist or systemd unit referencing this repo.
if [ -z "$found" ]; then
  if ls "$HOME/Library/LaunchAgents" 2>/dev/null | xargs -I{} grep -l "$REPO_ROOT" "$HOME/Library/LaunchAgents/{}" 2>/dev/null | head -n1 | grep -q .; then
    found="launchd-plist"
  fi
fi
[ -n "$found" ] && echo "unknown" || exit 1
```

`sz/adapters/unknown/install.sh`: no-op (just records `host: unknown`, `host_mode: adopt` in .sz.yaml + warns user that manual wiring is required to route the unknown daemon's pulse into `sz tick`). Prints clear instructions.

`sz/adapters/unknown/uninstall.sh`: strips only the marker from .sz.yaml.

### Step 5.10c — Merge mode (NEW — applies to every Adopt-mode adapter)

Merge mode runs BOTH the host's existing pulse AND S0's own heartbeat. It is implemented as a flag on the install flow, NOT as a separate adapter.

Add `sz/commands/host.py` sub-command `install --mode merge`:

```python
# inside sz/commands/host.py
@group.command(name="install")
@click.argument("name")
@click.option("--mode", type=click.Choice(["install","adopt","merge","auto"]), default="auto")
def _install(name, mode):
    # ... existing flow, then:
    if mode == "merge":
        # Always run Adopt first (if the adapter supports it).
        # Then also run the Install-mode plumbing of `generic` to install SZ's own cron heartbeat.
        generic_script = host_registry.install_script("generic")
        subprocess.run(["bash", str(generic_script)],
                       env={**os.environ, "SZ_REPO_ROOT": str(root)}, check=True)
        cfg = repo_config.read(root)
        cfg["host_mode"] = "merge"
        repo_config.write(root, cfg)
```

Add `sz/commands/tick.py` deduplication: the first line of `cmd` consults `.sz/memory/kv.json.last_tick_ts`; if within `dedup_window_seconds` (default 30), return silently.

```python
# inside tick.cmd
from sz.interfaces import memory
from datetime import datetime, timezone
mem = paths.s0_dir(root) / "memory"
last = memory.get(mem, "last_tick_ts")
window = int(os.environ.get("SZ_DEDUP_WINDOW_SECONDS", "30"))
if last:
    delta = (datetime.now(timezone.utc) - datetime.fromisoformat(last.rstrip("Z")).replace(tzinfo=timezone.utc)).total_seconds()
    if delta < window:
        # Silent no-op; emit a debug event only if SZ_DEBUG=1
        if os.environ.get("SZ_DEBUG") == "1":
            bus.emit(paths.bus_path(root), "sz", "tick.deduped", {"delta": delta})
        return
memory.set_(mem, "last_tick_ts", datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))
```

### Step 5.10d — Init flow always offers the choice when a heartbeat is detected

Update `sz/commands/init.py` so that when Repo Genesis reports `existing_heartbeat != "none"`, the user is asked:

```
I detected an existing heartbeat: <host>.
  1) Adopt   — use only the existing heartbeat (recommended).
  2) Merge   — run both (existing + SZ's own slower pulse).
  3) Install — replace the existing heartbeat with SZ's own.
Choose [1]: _
```

With `--yes`, default is Adopt. With `--host-mode merge|install|adopt`, that choice is honored without asking.

### Step 5.11 — Adapter registry

`sz/adapters/registry.py`:
```python
"""Resolve an adapter name to its install/uninstall scripts and detect."""
from __future__ import annotations
from pathlib import Path
import subprocess
import yaml

HERE = Path(__file__).resolve().parent

def list_names() -> list[str]:
    return sorted(p.name for p in HERE.iterdir() if (p / "manifest.yaml").exists())

def manifest(name: str) -> dict:
    return yaml.safe_load((HERE / name / "manifest.yaml").read_text())

def install_script(name: str) -> Path:
    return HERE / name / "install.sh"

def uninstall_script(name: str) -> Path:
    return HERE / name / "uninstall.sh"

def detect_script(name: str) -> Path:
    return HERE / name / "detect.sh"

def autodetect(repo_root: Path) -> str:
    """Run all detect.sh in priority order; first hit wins.
    Adopt-mode adapters checked first so an existing heartbeat is not overridden."""
    priority = ["hermes", "openclaw", "metaclaw", "connection_engine",
                "claude_code", "cursor", "opencode", "aider", "generic"]
    import os
    env = {**os.environ, "SZ_REPO_ROOT": str(repo_root)}
    for n in priority:
        d = detect_script(n)
        if not d.exists(): continue
        r = subprocess.run(["bash", str(d)], env=env, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip() == n:
            return n
    return "generic"
```

### Step 5.12 — `sz host` command group

```python
from __future__ import annotations
import os, subprocess, click
from sz.adapters import registry as host_registry
from sz.core import paths, repo_config


@click.group(help="Manage host adapter.")
def group(): pass


@group.command(name="list")
def _list():
    for n in host_registry.list_names():
        m = host_registry.manifest(n)
        click.echo(f"{n:20s} mode={m.get('mode'):8s} {m.get('description','')}")


@group.command(name="current")
def _current():
    cfg = repo_config.read(paths.repo_root())
    click.echo(f"{cfg.get('host','(none)')} ({cfg.get('host_mode','install')})")


@group.command(name="detect")
def _detect():
    click.echo(host_registry.autodetect(paths.repo_root()))


@group.command(name="install")
@click.argument("name")
def _install(name):
    if name not in host_registry.list_names():
        raise SystemExit(f"unknown host: {name}")
    root = paths.repo_root()
    cfg = repo_config.read(root)
    prev = cfg.get("host")
    if prev and prev != name:
        subprocess.run(["bash", str(host_registry.uninstall_script(prev))],
                       env={**os.environ, "SZ_REPO_ROOT": str(root)}, check=False)
    subprocess.run(["bash", str(host_registry.install_script(name))],
                   env={**os.environ, "SZ_REPO_ROOT": str(root)}, check=True)
    # The adapter writes host + host_mode itself for adopt-mode; for install-mode set defaults.
    cfg = repo_config.read(root)
    cfg["host"] = name
    if "host_mode" not in cfg:
        cfg["host_mode"] = host_registry.manifest(name).get("mode", "install")
    repo_config.write(root, cfg)
    click.echo(f"host: {name} ({cfg['host_mode']})")


@group.command(name="uninstall")
def _uninstall():
    root = paths.repo_root()
    cfg = repo_config.read(root)
    name = cfg.get("host")
    if not name: click.echo("no host installed"); return
    subprocess.run(["bash", str(host_registry.uninstall_script(name))],
                   env={**os.environ, "SZ_REPO_ROOT": str(root)}, check=False)
    cfg["host"] = "generic"; cfg["host_mode"] = "install"
    repo_config.write(root, cfg)
    click.echo("host uninstalled, defaulted to 'generic'")
```

### Step 5.13 — `sz init --host auto` uses autodetect

In `sz/commands/init.py`, when `host` is not explicitly passed (or is `auto`), call `host_registry.autodetect(root)`. Then run that adapter's install script.

### Step 5.14 — Tests

`tests/adapters/test_install_modes.py`: parametrize over `[claude_code, cursor, opencode, aider, generic]`. For each: tmp git repo, `sz init --host <X>`, verify the expected files exist (hooks, cron line, marker block), `host current` returns `(install)`, uninstall cleans everything.

`tests/adapters/test_adopt_modes.py`: parametrize over `[hermes, openclaw, metaclaw, connection_engine]`. For each: tmp git repo, plant the marker file (e.g., empty `.hermes/config.yaml`), `sz host install <X>`, verify:
- `host current` returns `(adopt)`.
- The framework's config now contains `sz tick --reason <X>` as a hook entry.
- No cron entry was added (Adopt-mode does NOT chain generic).
- Uninstall removes only the s0-introduced lines; framework config is otherwise untouched.

`tests/adapters/test_autodetect.py`: in repos that have multiple markers (e.g., both `.claude/` and `.hermes/`), autodetect picks Adopt-mode first.

Run:
```bash
python3 -m pytest tests/adapters -q
```

Verify: all tests pass.

### Step 5.15 — Commit

```bash
git add sz tests/adapters plan/phase-05-host-adapters
git commit -m "phase 05: host adapters + adopt mode complete"
```

## Acceptance criteria

1. `sz host list` prints all nine adapters with their modes.
2. `sz init --host claude_code` installs hooks + cron idempotently.
3. `sz init --host hermes` (in a Hermes repo) does NOT install cron, but adds `sz tick` to Hermes' `on_tick` hook list.
4. `sz host detect` correctly identifies the host in autodetect priority order.
5. Swapping host (`sz host install X` after `Y` was active) cleanly uninstalls Y first.
6. `pytest tests/adapters -q` passes for both Install and Adopt mode tests.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| Adopt adapter installs but framework never fires `sz tick` | the framework was not actually running its scheduler | document: user must start their framework's daemon before adoption takes effect |
| `crontab` missing on minimal Linux | not installed | adapter falls back with a warning; user runs heartbeat manually |
| Two adapters' markers coexist | autodetect priority handles | document priority order; user can override with explicit `--host` |
| YAML edits clobber framework config | wrong key path | each adapter's install.sh uses targeted python merge, not regex |

## Rollback

`git checkout main && git branch -D phase-05-host-adapters`.

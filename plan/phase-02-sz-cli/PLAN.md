# Phase 02 — Build the `sz` CLI

## Goal

Implement the user-facing `sz` command. End of phase: `sz init` creates `.sz/` in any directory; `sz install <id>` copies a module into place; `sz list`, `sz doctor`, `sz uninstall` work; the heartbeat starts and stops cleanly. Universal interfaces (memory, bus, llm, etc.) are scaffolded as sub-commands but defer their internals to phase 03. Reconciliation is scaffolded but defers internals to phase 04. Repo Genesis is scaffolded but defers internals to phase 07. Adopt mode is scaffolded but defers internals to phase 05.

## Inputs

- Phases 00–01 complete.
- `spec/v0.1.0/*.schema.json` exists.

## Outputs

- A Python package `sz/` at the repo root (importable as `sz`).
- A console entry point `sz` installable via `pipx install -e .`.
- `pyproject.toml` declaring the package.
- `tests/cli/` with smoke tests for every sub-command.
- Branch `phase-02-sz-cli` with one commit.

## Atomic steps

### Step 2.1 — Branch

```bash
git checkout main
git checkout -b phase-02-sz-cli
```

### Step 2.2 — Create the package skeleton

```bash
mkdir -p sz/{adapters,commands,core,interfaces,templates,cloud}
touch sz/__init__.py
touch sz/{adapters,commands,core,interfaces,templates,cloud}/__init__.py
mkdir -p tests/cli
```

Verify: `find s0 -type f -name '__init__.py' | wc -l` prints `7`.

### Step 2.3 — Write `pyproject.toml`

```toml
[project]
name = "system-zero"
version = "0.1.0"
description = "One-click autonomy and self-improvement for any repository."
requires-python = ">=3.10"
dependencies = [
  "pyyaml>=6.0",
  "jsonschema>=4.20",
  "click>=8.1",
  "rich>=13.7",
  "platformdirs>=4.2",
]

[project.scripts]
s0 = "sz.commands.cli:main"

[project.urls]
Homepage = "https://systemzero.dev"
Source   = "https://github.com/systemzero-dev/system-zero"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["s0*"]
```

### Step 2.4 — Write `sz/core/paths.py`

```python
"""Filesystem layout helpers."""
from __future__ import annotations
from pathlib import Path
import os


def repo_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / ".sz").is_dir():
            return candidate
    raise FileNotFoundError("No .sz/ found in this directory or any parent.")


def s0_dir(root: Path) -> Path:
    return root / ".sz"


def module_dir(root: Path, mod_id: str) -> Path:
    return s0_dir(root) / mod_id


def bus_path(root: Path) -> Path:
    return s0_dir(root) / "bus.jsonl"


def registry_path(root: Path) -> Path:
    return s0_dir(root) / "registry.json"


def profile_path(root: Path) -> Path:
    return s0_dir(root) / "repo-profile.json"


def repo_config_path(root: Path) -> Path:
    return root / ".sz.yaml"


def user_config_dir() -> Path:
    return Path(os.path.expanduser("~/.sz"))
```

### Step 2.5 — Write `sz/core/manifest.py`

Loader + JSON Schema validator using `sz/core/manifest.py`. Resolves spec path to `spec/v0.1.0/manifest.schema.json` at the repo root (walked up from `__file__`).

### Step 2.6 — Write `sz/core/repo_config.py`

Defaults:

```python
DEFAULT = {
    "sz_version": "0.1.0",
    "host": "generic",
    "host_mode": "install",
    "modules": {},
    "providers": {},
    "cloud": {"tier": "free", "endpoint": "https://api.systemzero.dev", "telemetry": False},
}
```

### Step 2.7 — Write `sz/core/bus.py`

Append-only JSONL with `os.fsync`. UTC ISO-8601 timestamps with `Z`. Single-line JSON.

### Step 2.8 — Write `sz/commands/cli.py` (entry point)

```python
"""s0 CLI entry point."""
from __future__ import annotations
import click
from sz.commands import (init, install, uninstall, ls, doctor, tick, start, stop,
                         reconcile, absorb, genesis, host, memory, bus, llm,
                         schedule, discovery, catalog)


@click.group(help="System Zero — one-click autonomy + self-improvement for any repository.")
@click.version_option("0.1.0")
def cli() -> None:
    pass


cli.add_command(init.cmd, name="init")
cli.add_command(install.cmd, name="install")
cli.add_command(uninstall.cmd, name="uninstall")
cli.add_command(ls.cmd, name="list")
cli.add_command(doctor.cmd, name="doctor")
cli.add_command(tick.cmd, name="tick")
cli.add_command(start.cmd, name="start")
cli.add_command(stop.cmd, name="stop")
cli.add_command(reconcile.cmd, name="reconcile")
cli.add_command(absorb.cmd, name="absorb")
cli.add_command(genesis.cmd, name="genesis")
cli.add_command(catalog.cmd, name="catalog")

cli.add_command(host.group,      name="host")
cli.add_command(memory.group,    name="memory")
cli.add_command(bus.group,       name="bus")
cli.add_command(llm.group,       name="llm")
cli.add_command(schedule.group,  name="schedule")
cli.add_command(discovery.group, name="discovery")


def main() -> None:
    cli(standalone_mode=True)
```

### Step 2.9 — Write each sub-command file

For every file (`init.py`, `install.py`, `uninstall.py`, `ls.py`, `doctor.py`, `tick.py`, `start.py`, `stop.py`, `reconcile.py`, `absorb.py`, `genesis.py`, `catalog.py`, `host.py`, `memory.py`, `bus.py`, `llm.py`, `schedule.py`, `discovery.py`), write a complete file. R21 applies — no `...`, no "TODO".

Key adjustments from a sz scaffold:
- All env vars use `S0_*` prefix: `SZ_REPO_ROOT`, `SZ_MODULE_DIR`, `SZ_MODULE_ID`, `SZ_BUS_PATH`, `SZ_MEMORY_DIR`, `SZ_REGISTRY_PATH`, `SZ_PROFILE_PATH`.
- `init.cmd` accepts `--host` from the expanded enum (`claude_code|cursor|opencode|aider|hermes|openclaw|metaclaw|connection_engine|generic`) and `--host-mode` (`install|adopt|auto`, default `auto`).
- `init.cmd` writes the `cloud` block with default `tier: free`.
- `genesis.cmd` is a stub that prints "Repo Genesis is implemented in phase 07."
- `host.group` is a stub that prints "Host management is implemented in phase 05."
- `absorb.cmd` is a stub that prints "Absorb is implemented in phase 06."
- `catalog.cmd` is a stub that prints "Catalog is implemented in phase 09."
- `reconcile.cmd` is a stub that prints "Reconcile is implemented in phase 04."
- Universal-interface command groups (memory/bus/llm/schedule/discovery) are stubs in phase 02; they get filled in phase 03.

`init.cmd` body (verbatim scaffold):

```python
from __future__ import annotations
from pathlib import Path
import os, stat
import click
from sz.core import paths, repo_config, bus

HOSTS = ["claude_code", "cursor", "opencode", "aider", "hermes", "openclaw", "metaclaw", "connection_engine", "generic"]


@click.command(help="Initialize an S0 runtime in the current repo.")
@click.option("--host", type=click.Choice(HOSTS), default="generic", show_default=True)
@click.option("--host-mode", type=click.Choice(["install", "adopt", "auto"]), default="auto", show_default=True)
@click.option("--force", is_flag=True, help="Reinitialize even if .sz/ exists.")
@click.option("--yes", "auto_yes", is_flag=True, help="Skip Repo Genesis confirmation.")
def cmd(host: str, host_mode: str, force: bool, auto_yes: bool) -> None:
    root = Path.cwd()
    sub = paths.s0_dir(root)
    if sub.exists() and not force:
        click.echo(f"Already initialized at {sub}. Use --force to reinitialize.")
        return

    sub.mkdir(parents=True, exist_ok=True)
    (sub / "bin").mkdir(exist_ok=True)
    (sub / "memory").mkdir(exist_ok=True)
    (sub / "memory" / "streams").mkdir(exist_ok=True)
    (sub / "memory" / "cursors").mkdir(exist_ok=True)
    (sub / "shared").mkdir(exist_ok=True)
    paths.bus_path(root).touch()

    hb = sub / "bin" / "heartbeat.sh"
    hb.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "INTERVAL=\"${SZ_INTERVAL:-300}\"\n"
        "while true; do\n"
        "  sz tick --reason heartbeat || true\n"
        "  sleep \"$INTERVAL\"\n"
        "done\n"
    )
    hb.chmod(hb.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    cfg = repo_config.read(root)
    cfg["host"] = host
    if host_mode != "auto":
        cfg["host_mode"] = host_mode
    repo_config.write(root, cfg)

    bus.emit(paths.bus_path(root), "sz", "sz.initialized",
             {"host": host, "host_mode": cfg.get("host_mode", "install")})

    click.echo(f"Initialized S0 ({host}) at {sub}")
    if not auto_yes:
        click.echo("Next: run `sz genesis` to make this repo alive (one-click).")
```

Apply analogous discipline to the other 17 command files.

### Step 2.10 — Install the package locally

```bash
pipx install -e . --force
which s0
sz --version
```

Verify: prints `0.1.0`.

### Step 2.11 — Smoke test in a temporary directory

```bash
TMP=$(mktemp -d)
cd "$TMP"
sz init --host generic
ls -la .sz
cat .sz.yaml
```

Verify: `.sz/bus.jsonl`, `.sz/bin/heartbeat.sh`, `.sz/memory/streams/`, `.sz/memory/cursors/`, `.sz/shared/` all exist. `.sz.yaml` has `host: generic`, `host_mode: install`, `cloud.tier: free`.

### Step 2.12 — Smoke test install with a synthetic module

Same as the sz version, with `sz` substituted. Install + tick + doctor + uninstall must all succeed; bus must contain `sz.initialized`, `module.installed`, `tick`, `module.uninstalled`.

### Step 2.13 — Pytest

`tests/cli/test_smoke.py` mirrors the sz smoke test, with `sz` substituted everywhere and the env vars renamed.

### Step 2.14 — Commit

```bash
git add sz pyproject.toml tests/cli plan/phase-02-sz-cli
git commit -m "phase 02: s0 CLI complete"
```

## Acceptance criteria

1. `pipx install -e .` succeeds; `sz --version` prints `0.1.0`.
2. `sz init`, `install --source`, `list`, `tick`, `doctor`, `uninstall` all work on a temp dir.
3. The bus log accumulates the expected event types in the expected order.
4. `pytest tests/cli -q` passes.
5. Branch `phase-02-sz-cli` exists with one commit.

## Failure modes and recovery

| Symptom | Cause | Action |
|---|---|---|
| `pipx install -e .` fails on `setuptools` | old setuptools | upgrade and retry |
| `sz init` says "Already initialized" but wasn't | leftover `.sz/` | `rm -rf .sz` and retry |
| `sz list` empty after install | repo config write silently failed validation | check `.sz.yaml` against schema |
| `start` returns immediately and `stop` says "no heartbeat" | shell or PATH | confirm `bash` is in PATH |

## Rollback

`git checkout main && git branch -D phase-02-sz-cli && pipx uninstall system-zero`.

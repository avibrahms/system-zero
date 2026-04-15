from __future__ import annotations

import stat
from pathlib import Path

import click

from sz.core import bus, paths, registry, repo_config, util

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
    paths.bin_dir(root).mkdir(exist_ok=True)
    paths.memory_dir(root).mkdir(exist_ok=True)
    paths.streams_dir(root).mkdir(exist_ok=True)
    paths.cursors_dir(root).mkdir(exist_ok=True)
    paths.shared_dir(root).mkdir(exist_ok=True)
    paths.bus_path(root).touch()

    hb = paths.heartbeat_script_path(root)
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

    util.atomic_write_json(paths.registry_path(root), registry.empty_registry())
    util.atomic_write_json(
        paths.profile_path(root),
        {
            "purpose": "Pending Repo Genesis",
            "language": "other",
            "frameworks": [],
            "existing_heartbeat": "none",
            "goals": ["Run Repo Genesis"],
            "recommended_modules": [{"id": "heartbeat", "reason": "Repo Genesis pending"}],
            "risk_flags": ["genesis_pending"],
        },
    )

    bus.emit(
        paths.bus_path(root),
        "s0",
        "sz.initialized",
        {"host": host, "host_mode": cfg.get("host_mode", "install"), "initialized_at": util.utc_now()},
    )

    click.echo(f"Initialized S0 ({host}) at {sub}")
    if not auto_yes:
        click.echo("Next: run `sz genesis` to make this repo alive (one-click).")

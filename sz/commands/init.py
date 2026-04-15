from __future__ import annotations

import stat
from pathlib import Path

import click

from sz.core import bus, paths, registry, repo_config, util
from sz.adapters import registry as host_registry
from sz.commands import host as host_command

HOSTS = ["auto", "claude_code", "cursor", "opencode", "aider", "hermes", "openclaw", "metaclaw", "connection_engine", "unknown", "generic"]


@click.command(help="Initialize an S0 runtime in the current repo.")
@click.option("--host", type=click.Choice(HOSTS), default="auto", show_default=True)
@click.option("--host-mode", type=click.Choice(["install", "adopt", "merge", "auto"]), default="auto", show_default=True)
@click.option("--force", is_flag=True, help="Reinitialize even if .sz/ exists.")
@click.option("--yes", "auto_yes", is_flag=True, help="Skip Repo Genesis confirmation.")
def cmd(host: str, host_mode: str, force: bool, auto_yes: bool) -> None:
    root = Path.cwd()
    selected_host = host_registry.autodetect(root) if host == "auto" else host
    selected_mode = host_mode
    detected_manifest = host_registry.manifest(selected_host)
    if selected_mode == "auto":
        if detected_manifest.get("mode") == "adopt":
            if auto_yes:
                selected_mode = "adopt"
            else:
                click.echo(f"I detected an existing heartbeat: {selected_host}.")
                click.echo("  1) Adopt   - use only the existing heartbeat (recommended).")
                click.echo("  2) Merge   - run both (existing + SZ's own slower pulse).")
                click.echo("  3) Install - replace the existing heartbeat with SZ's own.")
                choice = click.prompt("Choose", default="1", show_default=True)
                selected_mode = {"1": "adopt", "2": "merge", "3": "install"}.get(str(choice).strip(), "adopt")
        else:
            selected_mode = "install"

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
    cfg["host"] = selected_host
    cfg["host_mode"] = selected_mode
    repo_config.write(root, cfg)
    configured_host, configured_mode = host_command.install_adapter(
        root,
        selected_host,
        selected_mode,
        uninstall_previous=False,
    )

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
        {"host": configured_host, "host_mode": configured_mode, "initialized_at": util.utc_now()},
    )

    click.echo(f"Initialized S0 ({configured_host}) at {sub}")
    if not auto_yes:
        click.echo("Next: run `sz genesis` to make this repo alive (one-click).")

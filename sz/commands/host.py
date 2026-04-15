from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click

from sz.adapters import registry as host_registry
from sz.core import paths, repo_config


def _repo_root_or_cwd() -> Path:
    try:
        return paths.repo_root()
    except FileNotFoundError:
        return Path.cwd()


def _run_adapter(name: str, action: str, root: Path, check: bool = True) -> None:
    script = host_registry.install_script(name) if action == "install" else host_registry.uninstall_script(name)
    subprocess.run(
        ["bash", str(script)],
        env={**os.environ, "SZ_REPO_ROOT": str(root)},
        check=check,
    )


def install_adapter(root: Path, name: str, mode: str = "auto", uninstall_previous: bool = True) -> tuple[str, str]:
    """Install a host adapter and return the configured (host, host_mode)."""
    names = host_registry.list_names()
    if name not in names:
        raise click.ClickException(f"unknown host: {name}")

    adapter_mode = host_registry.manifest(name).get("mode", "install")
    effective_mode = adapter_mode if mode == "auto" else mode

    if effective_mode == "merge" and adapter_mode != "adopt":
        raise click.ClickException("merge mode requires an Adopt-mode adapter")
    if effective_mode == "adopt" and adapter_mode != "adopt":
        raise click.ClickException(f"{name} does not support adopt mode")

    cfg = repo_config.read(root)
    previous = cfg.get("host")
    if uninstall_previous and previous and previous != name and previous in names:
        _run_adapter(previous, "uninstall", root, check=False)

    if effective_mode == "install" and adapter_mode == "adopt":
        if previous and previous != "generic" and previous in names:
            _run_adapter(previous, "uninstall", root, check=False)
        _run_adapter("generic", "install", root)
        cfg = repo_config.read(root)
        cfg["host"] = "generic"
        cfg["host_mode"] = "install"
        repo_config.write(root, cfg)
        return "generic", "install"

    _run_adapter(name, "install", root)
    cfg = repo_config.read(root)
    cfg["host"] = name
    cfg["host_mode"] = effective_mode
    repo_config.write(root, cfg)

    if effective_mode == "merge":
        _run_adapter("generic", "install", root)
        cfg = repo_config.read(root)
        cfg["host"] = name
        cfg["host_mode"] = "merge"
        repo_config.write(root, cfg)
        return name, "merge"

    return name, effective_mode


@click.group(help="Manage host adapter.")
def group() -> None:
    pass


@group.command(name="list")
def _list() -> None:
    for name in host_registry.list_names():
        manifest = host_registry.manifest(name)
        click.echo(f"{name:20s} mode={manifest.get('mode', ''):8s} {manifest.get('description', '')}")


@group.command(name="current")
def _current() -> None:
    cfg = repo_config.read(paths.repo_root())
    click.echo(f"{cfg.get('host', '(none)')} ({cfg.get('host_mode', 'install')})")


@group.command(name="detect")
def _detect() -> None:
    click.echo(host_registry.autodetect(_repo_root_or_cwd()))


@group.command(name="install")
@click.argument("name")
@click.option("--mode", type=click.Choice(["install", "adopt", "merge", "auto"]), default="auto", show_default=True)
def _install(name: str, mode: str) -> None:
    root = paths.repo_root()
    host, host_mode = install_adapter(root, name, mode)
    click.echo(f"host: {host} ({host_mode})")


@group.command(name="uninstall")
def _uninstall() -> None:
    root = paths.repo_root()
    cfg = repo_config.read(root)
    name = cfg.get("host")
    if not name:
        click.echo("no host installed")
        return
    if name in host_registry.list_names():
        _run_adapter(name, "uninstall", root, check=False)
    if cfg.get("host_mode") == "merge":
        _run_adapter("generic", "uninstall", root, check=False)
    cfg["host"] = "generic"
    cfg["host_mode"] = "install"
    repo_config.write(root, cfg)
    click.echo("host uninstalled, defaulted to 'generic'")

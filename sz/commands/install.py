from __future__ import annotations

import shutil
from pathlib import Path

import click

from sz.core import bus, manifest, paths, reconcile as engine, repo_config, runtime


@click.command(help="Install a module into the current repo.")
@click.argument("module_id", required=False)
@click.option("--source", type=click.Path(exists=True, file_okay=False, path_type=Path), required=True, help="Local module source directory.")
@click.option("--force", is_flag=True, help="Replace an existing module with the same id.")
def cmd(module_id: str | None, source: Path, force: bool) -> None:
    root = paths.repo_root()
    manifest_path = source / "module.yaml"
    if not manifest_path.exists():
        raise click.ClickException(f"No module.yaml found in {source}.")

    data = manifest.load(manifest_path)
    resolved_module_id = module_id or data["id"]
    if resolved_module_id != data["id"]:
        raise click.ClickException(f"Requested module id {resolved_module_id!r} does not match manifest id {data['id']!r}.")

    destination = paths.module_dir(root, resolved_module_id)
    if destination.exists():
        if not force:
            click.echo(f"Module {resolved_module_id} is already installed. Use --force to replace it.")
            return
        shutil.rmtree(destination)

    shutil.copytree(source, destination)
    hook_path = data.get("hooks", {}).get("install")
    if hook_path:
        result = runtime.run_hook(root, resolved_module_id, destination, "install", hook_path)
        if result.returncode != 0:
            raise click.ClickException(result.stderr.strip() or result.stdout.strip() or f"Install hook failed for {resolved_module_id}.")

    cfg = repo_config.read(root)
    cfg["modules"][resolved_module_id] = {"version": data["version"], "enabled": True}
    repo_config.write(root, cfg)
    bus.emit(
        paths.bus_path(root),
        "s0",
        "module.installed",
        {"module_id": resolved_module_id, "version": data["version"], "source": str(source)},
    )
    engine.reconcile(root, reason=f"install:{resolved_module_id}")
    click.echo(f"Installed {resolved_module_id} from {source}")

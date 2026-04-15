from __future__ import annotations

import shutil

import click

from sz.core import bus, manifest, paths, registry, repo_config, runtime


@click.command(help="Uninstall a module from the current repo.")
@click.argument("module_id")
@click.option("--confirm", is_flag=True, help="Confirm destructive removal.")
def cmd(module_id: str, confirm: bool) -> None:
    root = paths.repo_root()
    module_dir = paths.module_dir(root, module_id)
    if not module_dir.exists():
        raise click.ClickException(f"Module {module_id} is not installed.")

    if not confirm:
        click.confirm(f"Remove module {module_id}?", default=False, abort=True)

    data = manifest.load(module_dir / "module.yaml")
    hook_path = data.get("hooks", {}).get("uninstall")
    if hook_path:
        result = runtime.run_hook(root, module_id, module_dir, "uninstall", hook_path)
        if result.returncode != 0:
            raise click.ClickException(result.stderr.strip() or result.stdout.strip() or f"Uninstall hook failed for {module_id}.")

    shutil.rmtree(module_dir)
    cfg = repo_config.read(root)
    cfg["modules"].pop(module_id, None)
    repo_config.write(root, cfg)
    registry.rebuild(root)
    bus.emit(paths.bus_path(root), "s0", "module.uninstalled", {"module_id": module_id})
    click.echo(f"Uninstalled {module_id}")

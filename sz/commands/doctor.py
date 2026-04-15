from __future__ import annotations

import click

from sz.core import manifest, paths, registry, runtime


@click.command(help="Run module diagnostics.")
@click.argument("module_id", required=False)
def cmd(module_id: str | None) -> None:
    root = paths.repo_root()
    current = registry.rebuild(root)
    module_ids = [module_id] if module_id else sorted(current["modules"])
    if not module_ids:
        click.echo("No modules installed.")
        return

    failures = 0
    for item in module_ids:
        module_dir = paths.module_dir(root, item)
        if not module_dir.exists():
            raise click.ClickException(f"Module {item} is not installed.")
        data = manifest.load(module_dir / "module.yaml")
        doctor_hook = data.get("hooks", {}).get("doctor")
        if not doctor_hook:
            click.echo(f"{item}: no doctor hook")
            continue
        result = runtime.run_hook(root, item, module_dir, "doctor", doctor_hook)
        if result.returncode == 0:
            click.echo(f"{item}: ok")
        else:
            failures += 1
            click.echo(f"{item}: failed")
    if failures:
        raise SystemExit(1)

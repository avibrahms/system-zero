from __future__ import annotations

import click

from sz.core import paths, registry


@click.command(help="List installed modules.")
def cmd() -> None:
    root = paths.repo_root()
    current = registry.rebuild(root)
    modules = current["modules"]
    if not modules:
        click.echo("No modules installed.")
        return

    for module_id in sorted(modules):
        record = modules[module_id]
        click.echo(f"{module_id}\t{record['version']}\t{record['status']}")

from __future__ import annotations

import click


@click.command(help="Interact with the module catalog.")
def cmd() -> None:
    click.echo("Catalog is implemented in phase 09.")

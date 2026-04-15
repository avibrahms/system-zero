from __future__ import annotations

import click


@click.command(help="Absorb an external feature as a module.")
def cmd() -> None:
    click.echo("Absorb is implemented in phase 06.")

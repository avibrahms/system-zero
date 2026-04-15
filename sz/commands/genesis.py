from __future__ import annotations

import click


@click.command(help="Run Repo Genesis.")
def cmd() -> None:
    click.echo("Repo Genesis is implemented in phase 07.")

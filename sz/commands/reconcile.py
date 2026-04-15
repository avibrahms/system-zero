from __future__ import annotations

import click


@click.command(help="Run module reconciliation.")
def cmd() -> None:
    click.echo("Reconcile is implemented in phase 04.")

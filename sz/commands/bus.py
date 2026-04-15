from __future__ import annotations

import click


@click.group(help="Bus interface commands.", invoke_without_command=True)
@click.pass_context
def group(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo("Bus interface is implemented in phase 03.")

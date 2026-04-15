from __future__ import annotations

import click


@click.group(help="Manage host adapters.", invoke_without_command=True)
@click.pass_context
def group(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo("Host management is implemented in phase 05.")
